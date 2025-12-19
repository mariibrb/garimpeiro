import pandas as pd
import xml.etree.ElementTree as ET
import re
import io
import streamlit as st

def extrair_dados_xml(files, fluxo, df_autenticidade=None):
    dados_lista = []
    if not files: return pd.DataFrame()

    container_status = st.empty()
    progresso = st.progress(0)
    total_arquivos = len(files)
    
    for i, f in enumerate(files):
        try:
            f.seek(0)
            conteudo_bruto = f.read()
            texto_xml = conteudo_bruto.decode('utf-8', errors='replace')
            texto_xml = re.sub(r'<\?xml[^?]*\?>', '', texto_xml)
            texto_xml = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', texto_xml)
            root = ET.fromstring(texto_xml)
            
            def buscar(caminho, raiz=root):
                alvo = raiz.find(f'.//{caminho}')
                return alvo.text if alvo is not None and alvo.text is not None else ""

            inf_nfe = root.find('.//infNFe')
            chave_acesso = inf_nfe.attrib.get('Id', '')[3:] if inf_nfe is not None else ""
            num_nf = buscar('nNF')
            data_emi = buscar('dhEmi')
            
            emit_uf = buscar('UF', root.find('.//emit'))
            dest_uf = buscar('UF', root.find('.//dest'))
            
            for det in root.findall('.//det'):
                prod = det.find('prod')
                imp = det.find('imposto')
                
                linha = {
                    "CHAVE_ACESSO": chave_acesso, "NUM_NF": num_nf,
                    "DATA_EMISSAO": pd.to_datetime(data_emi).replace(tzinfo=None) if data_emi else None,
                    "UF_EMIT": emit_uf, "UF_DEST": dest_uf, "AC": int(det.attrib.get('nItem', '0')),
                    "CFOP": buscar('CFOP', prod), "NCM": buscar('NCM', prod),
                    "COD_PROD": buscar('cProd', prod), "DESCR": buscar('xProd', prod),
                    "VPROD": float(buscar('vProd', prod)) if buscar('vProd', prod) else 0.0,
                    "FRETE": float(buscar('vFrete', prod)) if buscar('vFrete', prod) else 0.0,
                    "SEG": float(buscar('vSeg', prod)) if buscar('vSeg', prod) else 0.0,
                    "DESP": float(buscar('vOutro', prod)) if buscar('vOutro', prod) else 0.0,
                    "DESC": float(buscar('vDesc', prod)) if buscar('vDesc', prod) else 0.0,
                    "CST-ICMS": "", "BC-ICMS": 0.0, "VLR-ICMS": 0.0, "ALQ-ICMS": 0.0,
                    "BC-ICMS-ST": 0.0, "ICMS-ST": 0.0, "pRedBC": 0.0, "STATUS": ""
                }

                if imp is not None:
                    icms_nodo = imp.find('.//ICMS')
                    if icms_nodo is not None:
                        for nodo in icms_nodo:
                            cst = nodo.find('CST') if nodo.find('CST') is not None else nodo.find('CSOSN')
                            if cst is not None: linha["CST-ICMS"] = cst.text.zfill(2)
                            if nodo.find('vBC') is not None: linha["BC-ICMS"] = float(nodo.find('vBC').text)
                            if nodo.find('vICMS') is not None: linha["VLR-ICMS"] = float(nodo.find('vICMS').text)
                            if nodo.find('pICMS') is not None: linha["ALQ-ICMS"] = float(nodo.find('pICMS').text)
                            if nodo.find('pRedBC') is not None: linha["pRedBC"] = float(nodo.find('pRedBC').text)

                linha["VC"] = linha["VPROD"] + linha["ICMS-ST"] + linha["DESP"] - linha["DESC"]
                dados_lista.append(linha)
            progresso.progress((i + 1) / total_arquivos)
        except: continue
    
    df_res = pd.DataFrame(dados_lista)
    if not df_res.empty and df_autenticidade is not None:
        df_res['CHAVE_ACESSO'] = df_res['CHAVE_ACESSO'].astype(str).str.strip()
        map_auth = dict(zip(df_autenticidade.iloc[:, 0].astype(str).str.strip(), df_autenticidade.iloc[:, 5]))
        df_res['STATUS'] = df_res['CHAVE_ACESSO'].map(map_auth).fillna("Não encontrada")
    return df_res

def gerar_excel_final(df_ent, df_sai):
    try:
        base_t = pd.read_excel(".streamlit/Base_ICMS.xlsx")
        base_t['NCM_KEY'] = base_t.iloc[:, 0].astype(str).str.strip()
    except: base_t = pd.DataFrame(columns=['NCM_KEY'])

    df_icms_audit = df_sai.copy() if not df_sai.empty else pd.DataFrame()

    if not df_icms_audit.empty:
        ncms_ent_st = []
        if not df_ent.empty:
            ncms_ent_st = df_ent[(df_ent['CST-ICMS']=="60") | (df_ent['ICMS-ST'] > 0)]['NCM'].unique().tolist()

        def auditoria_completa(row):
            if "Cancelada" in str(row['STATUS']):
                return pd.Series(["NF Cancelada", "R$ 0,00", "R$ 0,00", "NF Cancelada", "R$ 0,00", "Não se aplica"])

            info_ncm = base_t[base_t['NCM_KEY'] == str(row['NCM']).strip()]
            cst_esp = str(info_ncm.iloc[0, 2]).zfill(2) if not info_ncm.empty else "NCM não encontrado"
            
            is_interna = row['UF_EMIT'] == row['UF_DEST']
            aliq_esp = float(info_ncm.iloc[0, 3]) if not info_ncm.empty and is_interna else (float(info_ncm.iloc[0, 29]) if not info_ncm.empty and len(info_ncm.columns) > 29 else 12.0)

            mensagens = []
            cst_atual = str(row['CST-ICMS']).strip()

            if cst_atual == "60":
                if row['VLR-ICMS'] > 0:
                    mensagens.append("CST 060 com destaque indevido")
                if row['NCM'] not in ncms_ent_st:
                    mensagens.append(f"Inconsistência: NCM {row['NCM']} sem histórico de ST na Entrada")
                aliq_esp = 0.0
            else:
                if aliq_esp > 0 and row['VLR-ICMS'] == 0:
                    mensagens.append("Imposto não destacado")
                if cst_atual != cst_esp and cst_esp != "NCM não encontrado":
                    mensagens.append(f"CST Errado (XML:{cst_atual}|Base:{cst_esp})")
                if row['ALQ-ICMS'] != aliq_esp and aliq_esp > 0:
                    mensagens.append(f"Aliq. Errada ({row['ALQ-ICMS']}% vs {aliq_esp}%)")

            complemento = (aliq_esp - row['ALQ-ICMS']) * row['BC-ICMS'] / 100 if (row['ALQ-ICMS'] < aliq_esp and cst_atual != "60") else 0.0
            diag = "; ".join(mensagens) if mensagens else "✅ Correto"
            
            # --- MENSAGENS DE AÇÃO MAIS LÓGICAS ---
            if "sem histórico" in diag:
                acao = "Vincular XML de Entrada com ST ou alterar CST de Saída"
            elif "destaque indevido" in diag:
                acao = "Zerar ICMS no XML e usar CST 060"
            elif "não destacado" in diag:
                acao = "Emitir NF Complementar de ICMS"
            elif diag == "✅ Correto":
                acao = "Manter conforme XML"
            else:
                acao = "Ajustar parâmetro tributário no ERP"

            cce = "Cc-e disponível" if "CST" in diag and "060" not in diag else "Não permitido"

            def f_brl(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return pd.Series([diag, f_brl(row['VLR-ICMS']), f_brl(row['BC-ICMS'] * aliq_esp / 100 if aliq_esp>0 else 0), acao, f_brl(complemento), cce])

        df_icms_audit[['Diagnóstico Detalhado', 'ICMS XML', 'ICMS Esperado', 'Ação Sugerida', 'Complemento', 'Cc-e']] = df_icms_audit.apply(auditoria_completa, axis=1)

    mem = io.BytesIO()
    with pd.ExcelWriter(mem, engine='xlsxwriter') as wr:
        if not df_ent.empty: df_ent.to_excel(wr, sheet_name='ENTRADAS', index=False)
        if not df_sai.empty:
            df_sai.to_excel(wr, sheet_name='SAIDAS', index=False)
            df_icms_audit.to_excel(wr, sheet_name='ICMS', index=False)
            for aba in ['IPI', 'PIS_COFINS', 'DIFAL']: df_sai.to_excel(wr, sheet_name=aba, index=False)
    return mem.getvalue()
