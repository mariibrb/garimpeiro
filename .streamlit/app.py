import streamlit as st
import zipfile
import io
import os
import re
import pandas as pd
import random

# --- CONFIGURAÇÃO E ESTILO (INTEGRIDADE TOTAL) ---
st.set_page_config(page_title="O GARIMPEIRO | Premium Edition", layout="wide", page_icon="⛏️")

def aplicar_estilo_premium():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;800&family=Plus+Jakarta+Sans:wght@400;700&display=swap');
        header, [data-testid="stHeader"] { display: none !important; }
        .stApp { background: radial-gradient(circle at top right, #FFDEEF 0%, #F8F9FA 100%) !important; }
        [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-right: 1px solid #FFDEEF !important; min-width: 400px !important; }
        div.stButton > button { color: #6C757D !important; background-color: #FFFFFF !important; border: 1px solid #DEE2E6 !important; border-radius: 15px !important; font-family: 'Montserrat', sans-serif !important; font-weight: 800 !important; height: 60px !important; text-transform: uppercase; width: 100% !important; }
        div.stButton > button:hover { border-color: #FF69B4 !important; color: #FF69B4 !important; }
        div.stDownloadButton > button { background-color: #FF69B4 !important; color: white !important; font-weight: 700 !important; border-radius: 15px !important; width: 100% !important; }
        h1, h2, h3 { font-family: 'Montserrat', sans-serif; font-weight: 800; color: #FF69B4 !important; text-align: center; }
        .instrucoes-card { background-color: rgba(255, 255, 255, 0.7); border-radius: 15px; padding: 20px; border-left: 5px solid #FF69B4; margin-bottom: 20px; min-height: 280px; }
        [data-testid="stMetric"] { background: white !important; border-radius: 20px !important; border: 1px solid #FFDEEF !important; padding: 15px !important; }
        </style>
    """, unsafe_allow_html=True)

aplicar_estilo_premium()

# --- MOTOR DE IDENTIFICAÇÃO (EXTREMA PRECISÃO FISCAL) ---
def identify_xml_info(content_bytes, client_cnpj, file_name):
    client_cnpj_clean = "".join(filter(str.isdigit, str(client_cnpj))) if client_cnpj else ""
    nome_puro = os.path.basename(file_name)
    if nome_puro.startswith('.') or nome_puro.startswith('~') or not nome_puro.lower().endswith('.xml'):
        return None, False
    
    resumo = {
        "Arquivo": nome_puro, "Chave": "", "Tipo": "Outros", "Série": "0",
        "Número": 0, "Status": "NORMAIS", "Pasta": "OUTROS", "Valor": 0.0, 
        "Conteúdo": content_bytes, "Ano": "0000", "Mes": "00"
    }
    
    try:
        content_str = content_bytes[:45000].decode('utf-8', errors='ignore')
        tag_l = content_str.lower()
        if '<?xml' not in tag_l and '<inf' not in tag_l and '<retinut' not in tag_l: return None, False
        
        # 1. TRATAMENTO DE INUTILIZAÇÃO (Baseado no seu exemplo real)
        if '<inut' in tag_l or '<retinut' in tag_l:
            resumo["Status"], resumo["Tipo"] = "INUTILIZADOS", "NF-e"
            resumo["Série"] = re.search(r'<serie>(\d+)</', tag_l).group(1) if re.search(r'<serie>(\d+)</', tag_l) else "0"
            n_match = re.search(r'<nnfini>(\d+)</', tag_l)
            resumo["Número"] = int(n_match.group(1)) if n_match else 0
            resumo["Chave"] = f"INUT_{resumo['Série']}_{resumo['Número']}"
            ano_match = re.search(r'<ano>(\d{2})</', tag_l)
            resumo["Ano"] = "20" + ano_match.group(1) if ano_match else "0000"
        
        # 2. TRATAMENTO VIA CHAVE (NF-e, CT-e, Cancelamentos)
        else:
            match_ch = re.search(r'<(?:chNFe|chCTe|chMDFe)>(\d{44})</', content_str, re.IGNORECASE)
            if not match_ch:
                match_ch = re.search(r'Id=["\'](?:NFe|CTe|MDFe)?(\d{44})["\']', content_str, re.IGNORECASE)
            
            if match_ch:
                resumo["Chave"] = match_ch.group(1) if len(match_ch.groups()) > 0 else match_ch.group(0)
                resumo["Série"] = str(int(resumo["Chave"][22:25]))
                resumo["Número"] = int(resumo["Chave"][25:34])
                resumo["Ano"], resumo["Mes"] = "20" + resumo["Chave"][2:4], resumo["Chave"][4:6]

            tipo = "NF-e"
            if '<mod>65</mod>' in tag_l: tipo = "NFC-e"
            elif '<mod>57</mod>' in tag_l or '<infcte' in tag_l: tipo = "CT-e"
            
            status = "NORMAIS"
            if '110111' in tag_l or '<cstat>101</cstat>' in tag_l: 
                status = "CANCELADOS"
            
            resumo["Tipo"], resumo["Status"] = tipo, status
            if status == "NORMAIS":
                v_match = re.search(r'<(?:vnf|vtprest|vreceb)>([\d.]+)</', tag_l)
                resumo["Valor"] = float(v_match.group(1)) if v_match else 0.0

        cnpj_xml = re.search(r'<cnpj>(\d+)</cnpj>', tag_l).group(1) if re.search(r'<cnpj>(\d+)</cnpj>', tag_l) else ""
        if not cnpj_xml and resumo["Chave"] and not resumo["Chave"].startswith("INUT_"):
            cnpj_xml = resumo["Chave"][6:20]
        
        is_p = (cnpj_xml == client_cnpj_clean)
        resumo["Pasta"] = f"{'EMITIDOS_CLIENTE' if is_p else 'RECEBIDOS_TERCEIROS'}/{resumo['Tipo']}/{resumo['Status']}/{resumo['Ano']}/{resumo['Mes']}/Serie_{resumo['Série']}"
        return resumo, is_p
    except: return None, False

# --- FUNÇÃO RECURSIVA ---
def extrair_recursivo(conteudo_bytes, nome_arquivo):
    itens = []
    if nome_arquivo.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(io.BytesIO(conteudo_bytes)) as z:
                for sub_nome in z.namelist():
                    if sub_nome.startswith('__MACOSX') or os.path.basename(sub_nome).startswith('.'): continue
                    sub_conteudo = z.read(sub_nome)
                    if sub_nome.lower().endswith('.zip'): itens.extend(extrair_recursivo(sub_conteudo, sub_nome))
                    elif sub_nome.lower().endswith('.xml'): itens.append((os.path.basename(sub_nome), sub_conteudo))
        except: pass
    elif nome_arquivo.lower().endswith('.xml'): itens.append((os.path.basename(nome_arquivo), conteudo_bytes))
    return itens

# --- INTERFACE ---
st.markdown("<h1>⛏️ O GARIMPEIRO</h1>", unsafe_allow_html=True)
with st.container():
    c_m1, c_m2 = st.columns(2)
    with c_m1:
        st.markdown("""<div class="instrucoes-card"><h3>📖 Dupla Checagem Fiscal</h3><ul><li><b>1. Validação de Buraco:</b> Identifica quebras na sequência.</li><li><b>2. Cruzamento de Canceladas:</b> Remove do buraco notas canceladas.</li><li><b>3. Cruzamento de Inutilizadas:</b> Remove do buraco notas inutilizadas via XML real.</li></ul></div>""", unsafe_allow_html=True)
    with c_m2:
        st.markdown("""<div class="instrucoes-card"><h3>📊 Resultados</h3><ul><li><b>Peneira em 3 Colunas:</b> Visão clara do que realmente falta.</li><li><b>ZIP Organizado:</b> Estrutura completa para fiscalização.</li></ul></div>""", unsafe_allow_html=True)

st.markdown("---")
keys_to_init = ['garimpo_ok', 'confirmado', 'z_org', 'z_todos', 'relatorio', 'df_resumo', 'df_faltantes', 'df_canceladas', 'df_inutilizadas', 'st_counts']
for k in keys_to_init:
    if k not in st.session_state:
        if 'df' in k: st.session_state[k] = pd.DataFrame()
        elif 'z_' in k: st.session_state[k] = None
        elif k == 'st_counts': st.session_state[k] = {"CANCELADOS": 0, "INUTILIZADOS": 0}
        else: st.session_state[k] = False

with st.sidebar:
    cnpj_input = st.text_input("CNPJ DO CLIENTE", placeholder="00.000.000/0001-00")
    cnpj_limpo = "".join(filter(str.isdigit, cnpj_input))
    if len(cnpj_limpo) == 14 and st.button("✅ LIBERAR OPERAÇÃO"): st.session_state['confirmado'] = True
    if st.button("🗑️ RESETAR SISTEMA"): st.session_state.clear(); st.rerun()

if st.session_state['confirmado']:
    if not st.session_state['garimpo_ok']:
        uploaded_files = st.file_uploader("Arraste os ficheiros aqui:", accept_multiple_files=True)
        if uploaded_files and st.button("🚀 INICIAR GRANDE GARIMPO"):
            lote_dict, st_counts = {}, {"CANCELADOS": 0, "INUTILIZADOS": 0}
            buf_org, buf_todos = io.BytesIO(), io.BytesIO()
            with zipfile.ZipFile(buf_org, "w") as z_org, zipfile.ZipFile(buf_todos, "w") as z_todos:
                for f in uploaded_files:
                    for name, xml_data in extrair_recursivo(f.read(), f.name):
                        res, is_p = identify_xml_info(xml_data, cnpj_limpo, name)
                        if res:
                            key = res["Chave"]
                            if key in lote_dict:
                                if res["Status"] in ["CANCELADOS", "INUTILIZADOS"]: lote_dict[key] = (res, is_p)
                            else:
                                lote_dict[key] = (res, is_p)
                                z_org.writestr(f"{res['Pasta']}/{name}", xml_data); z_todos.writestr(name, xml_data)

            rel_list, audit_map, canc_list, inut_list = [], {}, [], []
            for k, (res, is_p) in lote_dict.items():
                rel_list.append(res)
                if is_p:
                    if res["Status"] == "CANCELADOS": st_counts["CANCELADOS"] += 1
                    elif res["Status"] == "INUTILIZADOS": st_counts["INUTILIZADOS"] += 1
                    if res["Número"] > 0:
                        if res["Status"] == "CANCELADOS": canc_list.append({"Modelo": res["Tipo"], "Série": res["Série"], "Nota": res["Número"]})
                        elif res["Status"] == "INUTILIZADOS": inut_list.append({"Modelo": "NF-e", "Série": res["Série"], "Nota": res["Número"]})
                        sk = ("NF-e" if res["Tipo"] == "Inutilizacoes" else res["Tipo"], res["Série"])
                        if sk not in audit_map: audit_map[sk] = {"nums": set(), "valor": 0.0}
                        audit_map[sk]["nums"].add(res["Número"]); audit_map[sk]["valor"] += res["Valor"]

            res_f, fal_f = [], []
            for (t, s), d in audit_map.items():
                ns = sorted(list(d["nums"]))
                if ns:
                    res_f.append({"Doc": t, "Série": s, "Início": ns[0], "Fim": ns[-1], "Qtde": len(ns), "Valor": round(d["valor"], 2)})
                    for b in sorted(list(set(range(ns[0], ns[-1] + 1)) - set(ns))):
                        fal_f.append({"Tipo": t, "Série": s, "Faltante": b})

            st.session_state.update({'z_org': buf_org.getvalue(), 'z_todos': buf_todos.getvalue(), 'relatorio': rel_list, 'df_resumo': pd.DataFrame(res_f), 'df_faltantes': pd.DataFrame(fal_f), 'df_canceladas': pd.DataFrame(canc_list), 'df_inutilizadas': pd.DataFrame(inut_list), 'st_counts': st_counts, 'garimpo_ok': True})
            st.rerun()
    else:
        sc = st.session_state['st_counts']
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 VOLUME CLIENTE", len(st.session_state['relatorio']))
        c2.metric("❌ CANCELADAS", sc["CANCELADOS"])
        c3.metric("🚫 INUTILIZADAS", sc["INUTILIZADOS"])
        st.dataframe(st.session_state['df_resumo'], use_container_width=True, hide_index=True)
        st.markdown("---")
        col_a, col_c, col_i = st.columns(3)
        with col_a:
            st.markdown("### ⚠️ BURACOS REAIS")
            st.dataframe(st.session_state['df_faltantes'], use_container_width=True, hide_index=True) if not st.session_state['df_faltantes'].empty else st.info("✅ Tudo OK")
        with col_c:
            st.markdown("### ❌ CANCELADAS")
            st.dataframe(st.session_state['df_canceladas'], use_container_width=True, hide_index=True) if not st.session_state['df_canceladas'].empty else st.info("ℹ️ Nenhuma")
        with col_i:
            st.markdown("### 🚫 INUTILIZADAS")
            st.dataframe(st.session_state['df_inutilizadas'], use_container_width=True, hide_index=True) if not st.session_state['df_inutilizadas'].empty else st.info("ℹ️ Nenhuma")
        st.divider()
        st.download_button("📂 BAIXAR ORGANIZADO", st.session_state['z_org'], "organizado.zip", use_container_width=True)
        if st.button("⛏️ NOVO GARIMPO"): st.session_state.clear(); st.rerun()
else:
    st.warning("👈 Insira o CNPJ na barra lateral para começar.")
