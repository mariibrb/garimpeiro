import streamlit as st
import zipfile
import io
import os
import re
import pandas as pd
import random
import gc

# --- CONFIGURAÇÃO E ESTILO ---
st.set_page_config(page_title="O GARIMPEIRO | Análise Leve", layout="wide", page_icon="⛏️")

def aplicar_estilo_premium():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;800&family=Plus+Jakarta+Sans:wght@400;700&display=swap');
        header, [data-testid="stHeader"] { display: none !important; }
        .stApp { background: radial-gradient(circle at top right, #FFDEEF 0%, #F8F9FA 100%) !important; }
        [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-right: 1px solid #FFDEEF !important; min-width: 400px !important; }
        div.stButton > button { color: #6C757D !important; background-color: #FFFFFF !important; border: 1px solid #DEE2E6 !important; border-radius: 15px !important; font-family: 'Montserrat', sans-serif !important; font-weight: 800 !important; height: 60px !important; text-transform: uppercase; width: 100% !important; box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important; }
        div.stButton > button:hover { transform: translateY(-5px) !important; box-shadow: 0 10px 20px rgba(255,105,180,0.2) !important; border-color: #FF69B4 !important; color: #FF69B4 !important; }
        [data-testid="stFileUploader"] { border: 2px dashed #FF69B4 !important; border-radius: 20px !important; background: #FFFFFF !important; padding: 20px !important; }
        div.stDownloadButton > button { background-color: #FF69B4 !important; color: white !important; border: 2px solid #FFFFFF !important; font-weight: 700 !important; border-radius: 15px !important; box-shadow: 0 0 15px rgba(255, 105, 180, 0.3) !important; text-transform: uppercase; width: 100% !important; }
        h1, h2, h3 { font-family: 'Montserrat', sans-serif; font-weight: 800; color: #FF69B4 !important; text-align: center; }
        .instrucoes-card { background-color: rgba(255, 255, 255, 0.7); border-radius: 15px; padding: 20px; border-left: 5px solid #FF69B4; margin-bottom: 20px; min-height: 280px; }
        [data-testid="stMetric"] { background: white !important; border-radius: 20px !important; border: 1px solid #FFDEEF !important; padding: 15px !important; }
        </style>
    """, unsafe_allow_html=True)

aplicar_estilo_premium()

# --- MOTOR DE IDENTIFICAÇÃO (MANTIDO ÍNTEGRO) ---
def identify_xml_info(content_bytes, client_cnpj, file_name):
    client_cnpj_clean = "".join(filter(str.isdigit, str(client_cnpj))) if client_cnpj else ""
    nome_puro = os.path.basename(file_name)
    if nome_puro.startswith('.') or nome_puro.startswith('~') or not nome_puro.lower().endswith('.xml'):
        return None, False
    
    resumo = {
        "Arquivo": nome_puro, "Chave": "", "Tipo": "Outros", "Série": "0",
        "Número": 0, "Status": "NORMAIS", "Valor": 0.0, "Ano": "0000", "Mes": "00"
    }
    
    try:
        content_str = content_bytes[:45000].decode('utf-8', errors='ignore')
        tag_l = content_str.lower()
        if '<?xml' not in tag_l and '<inf' not in tag_l and '<inut' not in tag_l and '<retinut' not in tag_l: return None, False
        
        # 1. INUTILIZADAS
        if '<inutnfe' in tag_l or '<retinutnfe' in tag_l or '<procinut' in tag_l:
            resumo["Status"], resumo["Tipo"] = "INUTILIZADOS", "NF-e"
            if '<mod>65</mod>' in tag_l: resumo["Tipo"] = "NFC-e"
            elif '<mod>57</mod>' in tag_l: resumo["Tipo"] = "CT-e"
            
            resumo["Série"] = re.search(r'<serie>(\d+)</', tag_l).group(1) if re.search(r'<serie>(\d+)</', tag_l) else "0"
            ini = re.search(r'<nnfini>(\d+)</', tag_l).group(1) if re.search(r'<nnfini>(\d+)</', tag_l) else "0"
            fin = re.search(r'<nnffin>(\d+)</', tag_l).group(1) if re.search(r'<nnffin>(\d+)</', tag_l) else ini
            
            resumo["Número"] = int(ini)
            resumo["Range"] = (int(ini), int(fin))
            resumo["Ano"] = "20" + re.search(r'<ano>(\d+)</', tag_l).group(1)[-2:] if re.search(r'<ano>(\d+)</', tag_l) else "0000"
            resumo["Chave"] = f"INUT_{resumo['Série']}_{ini}"

        else:
            match_ch = re.search(r'<(?:chNFe|chCTe|chMDFe)>(\d{44})</', content_str, re.IGNORECASE)
            if not match_ch:
                match_ch = re.search(r'Id=["\'](?:NFe|CTe|MDFe)?(\d{44})["\']', content_str, re.IGNORECASE)
                resumo["Chave"] = match_ch.group(1) if match_ch else ""
            else:
                resumo["Chave"] = match_ch.group(1)

            if resumo["Chave"]:
                resumo["Ano"], resumo["Mes"] = "20" + resumo["Chave"][2:4], resumo["Chave"][4:6]
                resumo["Série"] = str(int(resumo["Chave"][22:25]))
                resumo["Número"] = int(resumo["Chave"][25:34])
            else:
                data_match = re.search(r'<(?:dhemi|dhregevento)>(\d{4})-(\d{2})', tag_l)
                if data_match: resumo["Ano"], resumo["Mes"] = data_match.group(1), data_match.group(2)

            tipo = "NF-e"
            if '<mod>65</mod>' in tag_l: tipo = "NFC-e"
            elif '<mod>57</mod>' in tag_l: tipo = "CT-e"
            elif '<mod>58</mod>' in tag_l: tipo = "MDF-e"
            
            status = "NORMAIS"
            if '110111' in tag_l or '<cstat>101</cstat>' in tag_l: status = "CANCELADOS"
            elif '110110' in tag_l: status = "CARTA_CORRECAO"
                
            resumo["Tipo"], resumo["Status"] = tipo, status
            if status == "NORMAIS":
                v_match = re.search(r'<(?:vnf|vtprest|vreceb)>([\d.]+)</', tag_l)
                resumo["Valor"] = float(v_match.group(1)) if v_match else 0.0
            
        cnpj_emit = re.search(r'<cnpj>(\d+)</cnpj>', tag_l).group(1) if re.search(r'<cnpj>(\d+)</cnpj>', tag_l) else ""
        if not cnpj_emit and resumo["Chave"] and not resumo["Chave"].startswith("INUT_"): cnpj_emit = resumo["Chave"][6:20]
        
        is_p = (cnpj_emit == client_cnpj_clean)
        return resumo, is_p
    except: return None, False

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
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.markdown("""<div class="instrucoes-card"><h3>📖 Instruções</h3><ul><li><b>Modo Turbo:</b> Otimizado para alto volume de dados.</li><li><b>Foco:</b> Análise e geração de Relatório Excel.</li><li><b>Atenção:</b> A geração de ZIPs foi desativada para economizar memória.</li></ul></div>""", unsafe_allow_html=True)
    with m_col2:
        st.markdown("""<div class="instrucoes-card"><h3>📊 Resultados</h3><ul><li><b>Auditoria Completa:</b> Buracos, Canceladas e Inutilizadas.</li><li><b>Relatório Excel:</b> Download com 4 abas detalhadas.</li><li><b>Dashboard:</b> Visualização rápida na tela.</li></ul></div>""", unsafe_allow_html=True)

st.markdown("---")

keys_to_init = ['garimpo_ok', 'confirmado', 'df_resumo', 'df_faltantes', 'df_canceladas', 'df_inutilizadas', 'st_counts']
for k in keys_to_init:
    if k not in st.session_state:
        st.session_state[k] = pd.DataFrame() if 'df' in k else ({"CANCELADOS": 0, "INUTILIZADOS": 0} if k == 'st_counts' else False)

with st.sidebar:
    st.markdown("### 🔍 Configuração")
    cnpj_input = st.text_input("CNPJ DO CLIENTE", placeholder="00.000.000/0001-00")
    cnpj_limpo = "".join(filter(str.isdigit, cnpj_input))
    if len(cnpj_limpo) == 14:
        if st.button("✅ LIBERAR OPERAÇÃO"): st.session_state['confirmado'] = True
    if st.button("🗑️ RESETAR SISTEMA"): st.session_state.clear(); st.rerun()

if st.session_state['confirmado']:
    if not st.session_state['garimpo_ok']:
        uploaded_files = st.file_uploader("Arraste seus arquivos aqui:", accept_multiple_files=True)
        if uploaded_files and st.button("🚀 INICIAR GARIMPO LEVE"):
            audit_map, canc_list, inut_list = {}, [], []
            progresso_bar = st.progress(0)
            status_text = st.empty()
            total_arquivos = len(uploaded_files)
            
            with st.status("⛏️ Processando em modo leve...", expanded=True) as status_box:
                for i, f in enumerate(uploaded_files):
                    if i % 100 == 0: gc.collect()
                    if total_arquivos > 0 and i % max(1, int(total_arquivos * 0.05)) == 0:
                        progresso_bar.progress((i + 1) / total_arquivos)
                        status_text.text(f"Lendo: {f.name}")
                    
                    try:
                        content = f.read()
                        todos_xmls = extrair_recursivo(content, f.name)
                        del content
                        
                        for name, xml_data in todos_xmls:
                            res, is_p = identify_xml_info(xml_data, cnpj_limpo, name)
                            if res and is_p:
                                sk = (res["Tipo"], res["Série"])
                                if sk not in audit_map: audit_map[sk] = {"nums": set(), "valor": 0.0}
                                
                                if res["Status"] == "INUTILIZADOS":
                                    r = res.get("Range", (res["Número"], res["Número"]))
                                    for n in range(r[0], r[1] + 1):
                                        audit_map[sk]["nums"].add(n)
                                        inut_list.append({"Modelo": res["Tipo"], "Série": res["Série"], "Nota": n})
                                else:
                                    if res["Número"] > 0:
                                        audit_map[sk]["nums"].add(res["Número"])
                                        if res["Status"] == "CANCELADOS":
                                            canc_list.append({"Modelo": res["Tipo"], "Série": res["Série"], "Nota": res["Número"]})
                                        audit_map[sk]["valor"] += res["Valor"]
                        del todos_xmls
                    except: continue

                status_box.update(label="✅ Finalizado!", state="complete", expanded=False)
                progresso_bar.empty(); status_text.empty()

            res_final, fal_final = [], []
            for (t, s), dados in audit_map.items():
                ns = sorted(list(dados["nums"]))
                if ns:
                    res_final.append({"Doc": t, "Série": s, "Início": ns[0], "Fim": ns[-1], "Qtde": len(ns), "Valor": round(dados["valor"], 2)})
                    for b in sorted(list(set(range(ns[0], ns[-1] + 1)) - set(ns))):
                        fal_final.append({"Tipo": t, "Série": s, "Faltante": b})

            st.session_state.update({
                'df_resumo': pd.DataFrame(res_final),
                'df_faltantes': pd.DataFrame(fal_final),
                'df_canceladas': pd.DataFrame(canc_list),
                'df_inutilizadas': pd.DataFrame(inut_list),
                'st_counts': {"CANCELADOS": len(canc_list), "INUTILIZADOS": len(inut_list)},
                'garimpo_ok': True
            })
            st.rerun()
    else:
        sc = st.session_state['st_counts']
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 VOLUME", len(st.session_state['df_resumo']))
        c2.metric("❌ CANCELADAS", sc["CANCELADOS"])
        c3.metric("🚫 INUTILIZADAS", sc["INUTILIZADOS"])
        
        st.dataframe(st.session_state['df_resumo'], use_container_width=True, hide_index=True)
        st.markdown("---")
        
        col_audit, col_canc, col_inut = st.columns(3)
        with col_audit:
            st.markdown("### ⚠️ BURACOS")
            if not st.session_state['df_faltantes'].empty: st.dataframe(st.session_state['df_faltantes'], use_container_width=True, hide_index=True)
            else: st.info("✅ OK")
        with col_canc:
            st.markdown("### ❌ CANCELADAS")
            if not st.session_state['df_canceladas'].empty: st.dataframe(st.session_state['df_canceladas'], use_container_width=True, hide_index=True)
            else: st.info("ℹ️ Nenhuma")
        with col_inut:
            st.markdown("### 🚫 INUTILIZADAS")
            if not st.session_state['df_inutilizadas'].empty: st.dataframe(st.session_state['df_inutilizadas'], use_container_width=True, hide_index=True)
            else: st.info("ℹ️ Nenhuma")

        st.divider()
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            for n, df in [('Resumo', 'df_resumo'), ('Buracos', 'df_faltantes'), ('Canceladas', 'df_canceladas'), ('Inutilizadas', 'df_inutilizadas')]:
                st.session_state[df].to_excel(writer, sheet_name=n, index=False)
        
        st.download_button("📊 BAIXAR RELATÓRIO EXCEL", buffer.getvalue(), "auditoria.xlsx", use_container_width=True)
        if st.button("⛏️ NOVO GARIMPO"): st.session_state.clear(); st.rerun()
else:
    st.warning("👈 Insira o CNPJ na barra lateral para começar.")
