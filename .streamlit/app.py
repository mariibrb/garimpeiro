import streamlit as st
import zipfile
import io
import os
import re
import pandas as pd
import random

# --- MOTOR DE IDENTIFICAÇÃO (PRECISÃO INDUSTRIAL) ---
def identify_xml_info(content_bytes, client_cnpj, file_name):
    client_cnpj_clean = "".join(filter(str.isdigit, str(client_cnpj))) if client_cnpj else ""
    nome_puro = os.path.basename(file_name)
    resumo = {
        "Arquivo": nome_puro, "Chave": "", "Tipo": "Outros", "Série": "0",
        "Número": 0, "Pasta": "RECEBIDOS_TERCEIROS/OUTROS"
    }
    try:
        # Analisamos apenas os primeiros 8kb para velocidade máxima
        content_str = content_bytes[:8192].decode('utf-8', errors='ignore')
        match_ch = re.search(r'\d{44}', content_str)
        resumo["Chave"] = match_ch.group(0) if match_ch else ""
        tag_l = content_str.lower()
        
        tipo = "NF-e"
        if '<mod>65</mod>' in tag_l: tipo = "NFC-e"
        elif '<infcte' in tag_l: tipo = "CT-e"
        elif '<infmdfe' in tag_l: tipo = "MDF-e"
        
        status = "NORMAIS"
        if '110111' in tag_l: status = "CANCELADOS"
        elif '110110' in tag_l: status = "CARTA_CORRECAO"
        elif '<inutnfe' in tag_l or '<procinut' in tag_l:
            status = "INUTILIZADOS"
            tipo = "Inutilizacoes"
            
        resumo["Tipo"] = tipo
        s_match = re.search(r'<(?:serie)>(\d+)</', tag_l)
        resumo["Série"] = s_match.group(1) if s_match else "0"
        n_match = re.search(r'<(?:nnf|nct|nmdf|nnfini)>(\d+)</', tag_l)
        resumo["Número"] = int(n_match.group(1)) if n_match else 0
        
        cnpj_emit = re.search(r'<cnpj>(\d+)</cnpj>', tag_l).group(1) if re.search(r'<cnpj>(\d+)</cnpj>', tag_l) else ""
        
        is_p = (cnpj_emit == client_cnpj_clean) or (resumo["Chave"] and client_cnpj_clean in resumo["Chave"][6:20])
        resumo["Pasta"] = f"EMITIDOS_CLIENTE/{tipo}/{status}/Serie_{resumo['Série']}" if is_p else f"RECEBIDOS_TERCEIROS/{tipo}"
        return resumo, is_p
    except:
        return resumo, False

# --- DESIGN PREMIUM ---
st.set_page_config(page_title="O Garimpeiro", layout="wide", page_icon="⛏️")
st.markdown("""
    <style>
    #MainMenu, footer, header, .stAppDeployButton {visibility: hidden !important; display: none !important;}
    .stApp { background-color: #f7f3f0; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #EADBC8 0%, #D2B48C 100%) !important; border-right: 3px solid #b8860b; }
    [data-testid="stSidebar"] * { color: #2b1e16 !important; font-weight: 900 !important; }
    h1, h2, h3, h4, p, label, .stMetric label { color: #2b1e16 !important; font-family: 'Playfair Display', serif; font-weight: 900 !important; }
    [data-testid="stMetric"] { background: linear-gradient(135deg, #ffffff 0%, #fff9e6 100%); border: 2px solid #d4af37; border-radius: 20px; padding: 20px; box-shadow: 8px 8px 15px rgba(0,0,0,0.1); }
    div.stButton > button { background: linear-gradient(180deg, #fcf6ba 0%, #d4af37 40%, #aa771c 100%) !important; color: #2b1e16 !important; border: 2px solid #8a6d3b; padding: 20px !important; font-weight: 900 !important; border-radius: 50px !important; width: 100% !important; text-transform: uppercase !important; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>⛏️ O GARIMPEIRO</h1>", unsafe_allow_html=True)

if 'garimpo_ok' not in st.session_state: st.session_state['garimpo_ok'] = False
if 'confirmado' not in st.session_state: st.session_state['confirmado'] = False

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### ⛏️ Painel de Extração")
    raw_cnpj = st.text_input("CNPJ DO CLIENTE")
    cnpj_limpo = "".join(filter(str.isdigit, raw_cnpj))
    if len(cnpj_limpo) == 14:
        if st.button("✅ LIBERAR OPERAÇÃO"):
            st.session_state['confirmado'] = True
            st.rerun()
    if st.button("🗑️ RESETAR SISTEMA"):
        st.session_state.clear()
        st.rerun()

# --- ÁREA DE TRABALHO ---
if st.session_state['confirmado']:
    if not st.session_state['garimpo_ok']:
        uploaded_files = st.file_uploader("Suba seus XMLs (até 7 mil notas):", accept_multiple_files=True)
        if uploaded_files:
            if st.button("🚀 INICIAR GRANDE GARIMPO"):
                processed_keys, relatorio, sequencias = set(), [], {}
                buf = io.BytesIO()
                
                with st.status("⛏️ Minerando jazida profunda...", expanded=True) as status:
                    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
                        for file in uploaded_files:
                            f_bytes = file.read()
                            # Processamento direto para economizar RAM
                            if file.name.lower().endswith('.zip'):
                                with zipfile.ZipFile(io.BytesIO(f_bytes)) as z_in:
                                    for name in z_in.namelist():
                                        if name.lower().endswith('.xml'):
                                            xml_data = z_in.read(name)
                                            res, is_p = identify_xml_info(xml_data, cnpj_limpo, name)
                                            key = res["Chave"] if len(res["Chave"]) == 44 else name
                                            if key not in processed_keys:
                                                processed_keys.add(key)
                                                zf.writestr(f"{res['Pasta']}/{res['Arquivo']}", xml_data)
                                                zf.writestr(f"TODOS/{res['Arquivo']}", xml_data)
                                                relatorio.append(res)
                                                if is_p and res["Número"] > 0 and "EMITIDOS" in res["Pasta"]:
                                                    s_k = (res["Tipo"], res["Série"])
                                                    if s_k not in sequencias: sequencias[s_k] = set()
                                                    sequencias[s_k].add(res["Número"])
                            else:
                                res, is_p = identify_xml_info(f_bytes, cnpj_limpo, file.name)
                                key = res["Chave"] if len(res["Chave"]) == 44 else file.name
                                if key not in processed_keys:
                                    processed_keys.add(key)
                                    zf.writestr(f"{res['Pasta']}/{res['Arquivo']}", f_bytes)
                                    zf.writestr(f"TODOS/{res['Arquivo']}", f_bytes)
                                    relatorio.append(res)
                                    if is_p and res["Número"] > 0 and "EMITIDOS" in res["Pasta"]:
                                        s_k = (res["Tipo"], res["Série"])
                                        if s_k not in sequencias: sequencias[s_k] = set()
                                        sequencias[s_k].add(res["Número"])

                # Auditoria de Faltantes
                faltantes = []
                for (t, s), nums in sequencias.items():
                    if len(nums) > 1:
                        ideal = set(range(min(nums), max(nums) + 1))
                        for b in sorted(list(ideal - nums)):
                            faltantes.append({"Documento": t, "Série": s, "Nº Faltante": b})

                st.session_state.update({
                    'zip_final': buf.getvalue(),
                    'relatorio': relatorio,
                    'df_faltantes': pd.DataFrame(faltantes),
                    'garimpo_ok': True
                })
                st.rerun()
    else:
        # --- EXIBIÇÃO ---
        st.success(f"⛏️ Garimpo Concluído! {len(st.session_state['relatorio'])} arquivos únicos processados.")
        df_res = pd.DataFrame(st.session_state['relatorio'])
        
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 VOLUME TOTAL", len(df_res))
        emitidas = len(df_res[df_res['Pasta'].str.contains("EMITIDOS")])
        c2.metric("✨ NOTAS CLIENTE", emitidas)
        c3.metric("⚠️ BURACOS", len(st.session_state['df_faltantes']))

        st.divider()
        st.download_button("📂 BAIXAR GARIMPO COMPLETO (Inclui pasta TODOS)", st.session_state['zip_final'], "garimpo_7mil.zip", use_container_width=True)

        st.divider()
        st.markdown("### 🔍 PENEIRA INDIVIDUAL (BUSCA)")
        busca = st.text_input("Número da Nota ou Chave:")
        if busca:
            filtro = df_res[df_res['Número'].astype(str).contains(busca) | df_res['Chave'].contains(busca)]
            st.dataframe(filtro[["Arquivo", "Tipo", "Série", "Número"]], use_container_width=True, hide_index=True)
            st.caption("Para baixar o volume total, utilize o botão dourado de download acima.")

        st.markdown("### ⚠️ AUDITORIA DE SEQUÊNCIA")
        st.dataframe(st.session_state['df_faltantes'], use_container_width=True, hide_index=True)

        if st.button("⛏️ NOVO GARIMPO"):
            st.session_state['garimpo_ok'] = False
            st.rerun()
