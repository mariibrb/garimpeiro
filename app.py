# -*- coding: utf-8 -*-
"""
Garimpeiro — núcleo para Django (sem Streamlit)
==============================================

Copie este ficheiro para o seu projeto Django (ex.: apps/core/services/app3.py) e importe:

    from .app3 import executar_garimpo_django, serializar_resultado_garimpo

Fluxo típico na view:
  1. Receber uploads e gravar numa pasta (ex.: MEDIA_ROOT / "garimpo" / job_id /).
  2. Chamar executar_garimpo_django(cnpj_14_digitos, essa_pasta).
  3. Guardar em BD o retorno de serializar_resultado_garimpo(...) ou usar os DataFrames.

Dependências: pandas (e openpyxl se exportar Excel noutro sítio).

Não importa streamlit — seguro para manage.py / ASGI / WSGI.

Deploy Streamlit (ex.: GitHub + Streamlit Cloud): o comando é sempre sobre um ficheiro
com interface Streamlit (ex.: app.py). Este ficheiro não é esse ponto de entrada —
é biblioteca Python para integrar num projeto Django (ou script próprio) com pasta de uploads.
"""

from __future__ import annotations

import gc
import io
import json
import os
import re
import shutil
import zipfile
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# --- Constantes (alinhadas com app.py / appV2.py) ---
MAX_XML_PER_ZIP = 10000
MAX_SALTO_ENTRE_NOTAS_CONSECUTIVAS = 25000


def identify_xml_info(content_bytes: bytes, client_cnpj: str, file_name: str) -> Tuple[Optional[dict], bool]:
    client_cnpj_clean = "".join(filter(str.isdigit, str(client_cnpj))) if client_cnpj else ""
    nome_puro = os.path.basename(file_name)
    if nome_puro.startswith(".") or nome_puro.startswith("~") or not nome_puro.lower().endswith(".xml"):
        return None, False

    resumo = {
        "Arquivo": nome_puro,
        "Chave": "",
        "Tipo": "Outros",
        "Série": "0",
        "Número": 0,
        "Status": "NORMAIS",
        "Pasta": "",
        "Valor": 0.0,
        "Conteúdo": b"",
        "Ano": "0000",
        "Mes": "00",
        "Operacao": "SAIDA",
        "Data_Emissao": "",
        "CNPJ_Emit": "",
        "Nome_Emit": "",
        "Doc_Dest": "",
        "Nome_Dest": "",
    }

    try:
        content_str = content_bytes[:45000].decode("utf-8", errors="ignore")
        tag_l = content_str.lower()
        if "<?xml" not in tag_l and "<inf" not in tag_l and "<inut" not in tag_l and "<retinut" not in tag_l:
            return None, False

        tp_nf_match = re.search(r"<tpnf>([01])</tpnf>", tag_l)
        if tp_nf_match:
            resumo["Operacao"] = "ENTRADA" if tp_nf_match.group(1) == "0" else "SAIDA"

        resumo["CNPJ_Emit"] = (
            re.search(r"<emit>.*?<cnpj>(\d+)</cnpj>", tag_l, re.S).group(1)
            if re.search(r"<emit>.*?<cnpj>(\d+)</cnpj>", tag_l, re.S)
            else ""
        )
        resumo["Nome_Emit"] = (
            re.search(r"<emit>.*?<xnome>(.*?)</xnome>", tag_l, re.S).group(1).upper()
            if re.search(r"<emit>.*?<xnome>(.*?)</xnome>", tag_l, re.S)
            else ""
        )
        resumo["Doc_Dest"] = (
            re.search(r"<dest>.*?<(?:cnpj|cpf)>(.*?)</(?:cnpj|cpf)>", tag_l, re.S).group(1)
            if re.search(r"<dest>.*?<(?:cnpj|cpf)>(.*?)</(?:cnpj|cpf)>", tag_l, re.S)
            else ""
        )
        resumo["Nome_Dest"] = (
            re.search(r"<dest>.*?<xnome>(.*?)</xnome>", tag_l, re.S).group(1).upper()
            if re.search(r"<dest>.*?<xnome>(.*?)</xnome>", tag_l, re.S)
            else ""
        )

        data_match = re.search(r"<(?:dhemi|demi|dhregevento|dhrecbto)>(\d{4})-(\d{2})-(\d{2})", tag_l)
        if data_match:
            resumo["Data_Emissao"] = f"{data_match.group(1)}-{data_match.group(2)}-{data_match.group(3)}"
            resumo["Ano"] = data_match.group(1)
            resumo["Mes"] = data_match.group(2)

        if "<inutnfe" in tag_l or "<retinutnfe" in tag_l or "<procinut" in tag_l:
            resumo["Status"] = "INUTILIZADOS"
            resumo["Tipo"] = "NF-e"
            if "<mod>65</mod>" in tag_l:
                resumo["Tipo"] = "NFC-e"
            elif "<mod>57</mod>" in tag_l:
                resumo["Tipo"] = "CT-e"
            resumo["Série"] = (
                re.search(r"<serie>(\d+)</", tag_l).group(1) if re.search(r"<serie>(\d+)</", tag_l) else "0"
            )
            ini = re.search(r"<nnfini>(\d+)</", tag_l).group(1) if re.search(r"<nnfini>(\d+)</", tag_l) else "0"
            fin = re.search(r"<nnffin>(\d+)</", tag_l).group(1) if re.search(r"<nnffin>(\d+)</", tag_l) else ini
            resumo["Número"] = int(ini)
            resumo["Range"] = (int(ini), int(fin))
            if resumo["Ano"] == "0000":
                ano_match = re.search(r"<ano>(\d+)</", tag_l)
                if ano_match:
                    resumo["Ano"] = "20" + ano_match.group(1)[-2:]
            resumo["Chave"] = f"INUT_{resumo['Série']}_{ini}"
        else:
            match_ch = re.search(r"<(?:chnfe|chcte|chmdfe)>(\d{44})</", tag_l)
            if not match_ch:
                match_ch = re.search(r'id=["\'](?:nfe|cte|mdfe)?(\d{44})["\']', tag_l)
                if match_ch:
                    resumo["Chave"] = match_ch.group(1)
                else:
                    resumo["Chave"] = ""
            else:
                resumo["Chave"] = match_ch.group(1)

            if resumo["Chave"] and len(resumo["Chave"]) == 44:
                resumo["Ano"] = "20" + resumo["Chave"][2:4]
                resumo["Mes"] = resumo["Chave"][4:6]
                resumo["Série"] = str(int(resumo["Chave"][22:25]))
                resumo["Número"] = int(resumo["Chave"][25:34])
                if not resumo["Data_Emissao"]:
                    resumo["Data_Emissao"] = f"{resumo['Ano']}-{resumo['Mes']}-01"

            tipo = "NF-e"
            if "<mod>65</mod>" in tag_l:
                tipo = "NFC-e"
            elif "<mod>57</mod>" in tag_l or "<infcte" in tag_l:
                tipo = "CT-e"
            elif "<mod>58</mod>" in tag_l or "<infmdfe" in tag_l:
                tipo = "MDF-e"

            status = "NORMAIS"
            if "110111" in tag_l or "<cstat>101</cstat>" in tag_l:
                status = "CANCELADOS"
            elif "110110" in tag_l:
                status = "CARTA_CORRECAO"

            resumo["Tipo"] = tipo
            resumo["Status"] = status

            if status == "NORMAIS":
                v_match = re.search(r"<(?:vnf|vtprest|vreceb)>([\d.]+)</", tag_l)
                resumo["Valor"] = float(v_match.group(1)) if v_match else 0.0

        if not resumo["CNPJ_Emit"] and resumo["Chave"] and not resumo["Chave"].startswith("INUT_"):
            resumo["CNPJ_Emit"] = resumo["Chave"][6:20]

        if resumo["Mes"] == "00":
            resumo["Mes"] = "01"
        if resumo["Ano"] == "0000":
            resumo["Ano"] = "2000"

        is_p = resumo["CNPJ_Emit"] == client_cnpj_clean
        if is_p:
            resumo["Pasta"] = (
                f"EMITIDOS_CLIENTE/{resumo['Operacao']}/{resumo['Tipo']}/{resumo['Status']}/"
                f"{resumo['Ano']}/{resumo['Mes']}/Serie_{resumo['Série']}"
            )
        else:
            resumo["Pasta"] = (
                f"RECEBIDOS_TERCEIROS/{resumo['Operacao']}/{resumo['Tipo']}/"
                f"{resumo['Ano']}/{resumo['Mes']}"
            )
        return resumo, is_p
    except Exception:
        return None, False


def extrair_recursivo(conteudo_ou_file, nome_arquivo: str, extract_dir: str):
    os.makedirs(extract_dir, exist_ok=True)
    if nome_arquivo.lower().endswith(".zip"):
        try:
            file_obj = conteudo_ou_file if hasattr(conteudo_ou_file, "read") else io.BytesIO(conteudo_ou_file)
            with zipfile.ZipFile(file_obj) as z:
                for sub_nome in z.namelist():
                    if sub_nome.startswith("__MACOSX") or os.path.basename(sub_nome).startswith("."):
                        continue
                    if sub_nome.lower().endswith(".zip"):
                        temp_path = z.extract(sub_nome, path=extract_dir)
                        try:
                            with open(temp_path, "rb") as f_temp:
                                yield from extrair_recursivo(f_temp, sub_nome, extract_dir)
                        finally:
                            try:
                                os.remove(temp_path)
                            except OSError:
                                pass
                    elif sub_nome.lower().endswith(".xml"):
                        yield (os.path.basename(sub_nome), z.read(sub_nome))
        except Exception:
            return
    elif nome_arquivo.lower().endswith(".xml"):
        if hasattr(conteudo_ou_file, "read"):
            yield (os.path.basename(nome_arquivo), conteudo_ou_file.read())
        else:
            yield (os.path.basename(nome_arquivo), conteudo_ou_file)


def enumerar_buracos_por_segmento(
    nums_sorted: List[int],
    tipo_doc: str,
    serie_str: str,
    gap_max: int = MAX_SALTO_ENTRE_NOTAS_CONSECUTIVAS,
) -> List[dict]:
    out = []
    if not nums_sorted:
        return out
    segmentos = [[nums_sorted[0]]]
    for i in range(1, len(nums_sorted)):
        if nums_sorted[i] - nums_sorted[i - 1] > gap_max:
            segmentos.append([nums_sorted[i]])
        else:
            segmentos[-1].append(nums_sorted[i])
    for seg in segmentos:
        lo, hi = seg[0], seg[-1]
        seg_set = set(seg)
        for b in range(lo, hi + 1):
            if b not in seg_set:
                out.append({"Tipo": tipo_doc, "Série": serie_str, "Num_Faltante": b})
    return out


def compactar_dataframe_memoria(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    n = len(out)
    for col in out.columns:
        if out[col].dtype != object and not str(out[col].dtype).startswith("string"):
            continue
        nu = out[col].nunique(dropna=False)
        if nu <= 1 or nu > min(4096, max(48, n // 2)):
            continue
        try:
            out[col] = out[col].astype("category")
        except (TypeError, ValueError):
            pass
    for col in out.select_dtypes(include=["float64"]).columns:
        out[col] = pd.to_numeric(out[col], downcast="float")
    for col in out.select_dtypes(include=["int64"]).columns:
        out[col] = pd.to_numeric(out[col], downcast="integer")
    return out


def filtrar_df_geral_para_exportacao(
    df_base: pd.DataFrame,
    filtro_origem: List[str],
    filtro_meses: List[str],
    aplicar_mes_so_na_propria: bool,
    filtro_modelos: List[str],
    filtro_series: List[str],
    filtro_status: List[str],
    filtro_operacao: List[str],
) -> pd.DataFrame:
    if df_base is None or df_base.empty:
        return df_base
    out = df_base.copy()
    if len(filtro_origem) > 0:
        pat = "|".join([re.escape(o.split()[0]) for o in filtro_origem])
        out = out[out["Origem"].str.contains(pat, regex=True, na=False)]
    if len(filtro_meses) > 0:
        out = out.copy()
        out["Mes_Comp"] = out["Ano"].astype(str) + "/" + out["Mes"].astype(str)
        if aplicar_mes_so_na_propria:
            out = out[(out["Mes_Comp"].isin(filtro_meses)) | (out["Origem"].str.contains("TERCEIROS", na=False))]
        else:
            out = out[out["Mes_Comp"].isin(filtro_meses)]
    if len(filtro_modelos) > 0:
        out = out[out["Modelo"].isin(filtro_modelos)]
    if len(filtro_series) > 0:
        out = out[out["Série"].astype(str).isin(filtro_series)]
    if len(filtro_status) > 0:
        out = out[out["Status Final"].isin(filtro_status)]
    if len(filtro_operacao) > 0 and "Operação" in out.columns:
        out = out[out["Operação"].isin(filtro_operacao)]
    return out


def _varrer_pasta_uploads(pasta_ficheiros: str, cnpj_limpo: str, extract_dir: str) -> Dict[str, Tuple[dict, bool]]:
    lote_dict: Dict[str, Tuple[dict, bool]] = {}
    nomes = sorted(os.listdir(pasta_ficheiros))
    for i, f_name in enumerate(nomes):
        if i % 50 == 0:
            gc.collect()
        caminho = os.path.join(pasta_ficheiros, f_name)
        if not os.path.isfile(caminho):
            continue
        try:
            with open(caminho, "rb") as file_obj:
                for name, xml_data in extrair_recursivo(file_obj, f_name, extract_dir):
                    res, is_p = identify_xml_info(xml_data, cnpj_limpo, name)
                    if res:
                        key = res["Chave"]
                        if key in lote_dict:
                            if res["Status"] in ["CANCELADOS", "INUTILIZADOS"]:
                                lote_dict[key] = (res, is_p)
                        else:
                            lote_dict[key] = (res, is_p)
                    del xml_data
        except Exception:
            continue
    return lote_dict


def _montar_tabelas_a_partir_do_lote(lote_dict: Dict[str, Tuple[dict, bool]]) -> Dict[str, Any]:
    rel_list: List[dict] = []
    audit_map: Dict[Tuple[str, str], dict] = {}
    canc_list: List[dict] = []
    inut_list: List[dict] = []
    aut_list: List[dict] = []
    geral_list: List[dict] = []

    for _k, (res, is_p) in lote_dict.items():
        rel_list.append(res)
        if is_p:
            origem_label = f"EMISSÃO PRÓPRIA ({res['Operacao']})"
        else:
            origem_label = f"TERCEIROS ({res['Operacao']})"

        registro_base = {
            "Origem": origem_label,
            "Operação": res["Operacao"],
            "Modelo": res["Tipo"],
            "Série": res["Série"],
            "Nota": res["Número"],
            "Data Emissão": res["Data_Emissao"],
            "CNPJ Emitente": res["CNPJ_Emit"],
            "Nome Emitente": res["Nome_Emit"],
            "Doc Destinatário": res["Doc_Dest"],
            "Nome Destinatário": res["Nome_Dest"],
            "Chave": res["Chave"],
            "Status Final": res["Status"],
            "Valor": res["Valor"],
            "Ano": res["Ano"],
            "Mes": res["Mes"],
        }

        if res["Status"] == "INUTILIZADOS":
            r = res.get("Range", (res["Número"], res["Número"]))
            for n in range(r[0], r[1] + 1):
                item_inut = registro_base.copy()
                item_inut.update({"Nota": n, "Status Final": "INUTILIZADA", "Valor": 0.0})
                geral_list.append(item_inut)
        else:
            geral_list.append(registro_base)

        if is_p:
            sk = (res["Tipo"], res["Série"])
            if sk not in audit_map:
                audit_map[sk] = {"nums": set(), "valor": 0.0}

            if res["Status"] == "INUTILIZADOS":
                r = res.get("Range", (res["Número"], res["Número"]))
                for n in range(r[0], r[1] + 1):
                    audit_map[sk]["nums"].add(n)
                    inut_list.append({"Modelo": res["Tipo"], "Série": res["Série"], "Nota": n})
            else:
                if res["Número"] > 0:
                    audit_map[sk]["nums"].add(res["Número"])
                    if res["Status"] == "CANCELADOS":
                        canc_list.append(registro_base)
                    elif res["Status"] == "NORMAIS":
                        aut_list.append(registro_base)
                    audit_map[sk]["valor"] += res["Valor"]

    res_final = []
    fal_final = []
    for (t, s), dados in audit_map.items():
        ns = sorted(list(dados["nums"]))
        if ns:
            res_final.append(
                {
                    "Documento": t,
                    "Série": s,
                    "Início": ns[0],
                    "Fim": ns[-1],
                    "Quantidade": len(ns),
                    "Valor Contábil (R$)": round(dados["valor"], 2),
                }
            )
            fal_final.extend(enumerar_buracos_por_segmento(ns, t, s))

    return {
        "relatorio": rel_list,
        "df_resumo": pd.DataFrame(res_final),
        "df_faltantes": pd.DataFrame(fal_final),
        "df_canceladas": pd.DataFrame(canc_list),
        "df_inutilizadas": pd.DataFrame(inut_list),
        "df_autorizadas": pd.DataFrame(aut_list),
        "df_geral": pd.DataFrame(geral_list),
        "st_counts": {
            "CANCELADOS": len(canc_list),
            "INUTILIZADOS": len(inut_list),
            "AUTORIZADAS": len(aut_list),
        },
    }


def _dfs_vazios() -> Dict[str, pd.DataFrame]:
    e = pd.DataFrame()
    return {
        "df_resumo": e,
        "df_faltantes": e,
        "df_canceladas": e,
        "df_inutilizadas": e,
        "df_autorizadas": e,
        "df_geral": e,
    }


def executar_garimpo_django(
    cnpj_emitente: str,
    pasta_ficheiros: str,
    *,
    pasta_extracao: Optional[str] = None,
    limpar_extracao_antes: bool = True,
    compactar_dfs: bool = True,
) -> Dict[str, Any]:
    """
    Processa todos os XML/ZIP diretamente sob `pasta_ficheiros` (ficheiros já gravados pelo Django).

    :param cnpj_emitente: CNPJ do emitente (com ou sem máscara).
    :param pasta_ficheiros: diretório absoluto com os uploads.
    :param pasta_extracao: onde extrair ZIPs aninhados; default: <pasta_ficheiros>/_garimpeiro_extract
    :return: dict com ok, erro, relatorio, DataFrames, st_counts
    """
    cnpj_limpo = "".join(filter(str.isdigit, str(cnpj_emitente)))
    base_vazio = {
        "ok": False,
        "erro": None,
        "relatorio": [],
        **_dfs_vazios(),
        "st_counts": {"CANCELADOS": 0, "INUTILIZADOS": 0, "AUTORIZADAS": 0},
    }

    if len(cnpj_limpo) != 14:
        base_vazio["erro"] = "CNPJ do emitente deve ter 14 dígitos."
        return base_vazio
    if not os.path.isdir(pasta_ficheiros):
        base_vazio["erro"] = f"Pasta inexistente: {pasta_ficheiros}"
        return base_vazio

    ext = pasta_extracao or os.path.join(pasta_ficheiros, "_garimpeiro_extract")
    try:
        if limpar_extracao_antes and os.path.exists(ext):
            shutil.rmtree(ext, ignore_errors=True)
        os.makedirs(ext, exist_ok=True)

        lote = _varrer_pasta_uploads(pasta_ficheiros, cnpj_limpo, ext)
        out = _montar_tabelas_a_partir_do_lote(lote)
        out["ok"] = True
        out["erro"] = None

        if compactar_dfs:
            for key in (
                "df_geral",
                "df_resumo",
                "df_faltantes",
                "df_canceladas",
                "df_inutilizadas",
                "df_autorizadas",
            ):
                df = out.get(key)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    out[key] = compactar_dataframe_memoria(df)

        gc.collect()
        return out
    except Exception as exc:
        base_vazio["erro"] = str(exc)
        return base_vazio


def serializar_resultado_garimpo(resultado: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converte o retorno de executar_garimpo_django em estrutura JSON-friendly (para JsonResponse / DRF).
    """
    keys_df = (
        "df_geral",
        "df_resumo",
        "df_faltantes",
        "df_canceladas",
        "df_inutilizadas",
        "df_autorizadas",
    )
    out: Dict[str, Any] = {
        "ok": resultado.get("ok", False),
        "erro": resultado.get("erro"),
        "st_counts": resultado.get("st_counts"),
        "relatorio": resultado.get("relatorio") or [],
    }
    for k in keys_df:
        df = resultado.get(k)
        if isinstance(df, pd.DataFrame) and not df.empty:
            out[k] = json.loads(df.to_json(orient="records", date_format="iso"))
        else:
            out[k] = []
    return out


def gravar_uploads_django(request_files, destino_dir: str) -> List[str]:
    """
    Exemplo: na view, request.FILES.getlist('ficheiros').
    Grava ficheiros em destino_dir e devolve lista de caminhos absolutos.
    """
    os.makedirs(destino_dir, exist_ok=True)
    paths = []
    for f in request_files:
        nome = getattr(f, "name", "upload") or "upload"
        # Evita path traversal
        nome = os.path.basename(nome)
        caminho = os.path.join(destino_dir, nome)
        with open(caminho, "wb") as out:
            if hasattr(f, "chunks"):
                for chunk in f.chunks():
                    out.write(chunk)
            else:
                out.write(f.read() if hasattr(f, "read") else bytes(f))
        paths.append(caminho)
    return paths
