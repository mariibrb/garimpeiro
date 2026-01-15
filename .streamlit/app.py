import streamlit as st
import zipfile
import io
import os
import re
import pandas as pd
import random

# --- MOTOR DE IDENTIFICAÇÃO ---
def identify_xml_info(content_bytes, client_cnpj, file_name):
    client_cnpj_clean = "".join(filter(str.isdigit, str(client_cnpj))) if client_cnpj else ""
    nome_puro = os.path.basename(file_name)
    
    resumo = {
        "Arquivo": nome_puro, "Chave": "", "Tipo": "Outros", "Série": "0",
        "Número": 0, "Pasta": "RECEBIDOS_TERCEIROS/OUTROS", "Conteúdo": content_bytes
    }
    try:
        # Usamos uma amostra do início do arquivo para ser mais rápido
        content_str = content_bytes[:5000].decode('utf-8', errors='ignore')
        match_ch = re.search(r'\d{44}', content_str)
        resumo["Chave"] = match_ch.group(0) if match_ch else ""
        tag_lower = content_str.lower()
        
        d_type = "NF-e"
        if '<mod>65</mod>' in tag_lower: d_type = "NFC-e"
        elif '<infcte' in tag_lower: d_type = "CT-e"
        elif '<infmdfe' in tag_lower: d_type = "MDF-e"
        
        status = "NORMAIS"
        if '110111' in tag_lower: status = "CANCELADOS"
        elif '110110' in tag_lower: status = "CARTA_CORRECAO"
        elif '<inutnfe' in tag_lower or '<procinut' in tag_lower:
            status = "INUTILIZADOS"
            d_type = "Inutilizacoes"
            
        resumo["Tipo"] = d_type
        resumo["Série"] = re.search(r'<(?:serie)>(\d+)</', tag_lower).group(1) if re.search(r'<(?:serie)>(\d+)</', tag_lower) else "0"
        n_match = re.search(r'<(?:nnf|nct|nmdf|nnfini)>(\d+)</', tag_lower)
        resumo["Número"] = int(n_match.group(1)) if n_match else 0
        
        cnpj_emit = re.search(r'<cnpj>(\d+)</cnpj>', tag_lower).group(1) if re.search(r'<cnpj>(\d+)</cnpj>', tag_lower) else ""
        is_p = (cnpj_emit == client_cnpj_clean) or (resumo["Chave"] and client_cnpj_clean in resumo["Chave"][6:20])
            
        if is_p:
            resumo["Pasta"] = f"EMITIDOS_CLIENTE/{d_type}/{status}/Serie_{resumo['Série']}"
        else:
            resumo["Pasta"] = f"RECEBIDOS_TERCEIROS/{d_type}"
            
        return resumo, is_p
    except:
        return resumo, False

# --- DESIGN LUXO ---
st.set_page_config(page_title="O Garimpeiro", layout="wide", page_icon="⛏️")
st.markdown("""
    <style>
    #MainMenu, footer, header, .stAppDeployButton {visibility: hidden !important;}
    .stApp { background-color: #f7f3f0; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #EADBC8 0%, #D2B48C 100%) !important; border-right: 3px solid #b8860b; }
    [data-testid="stSidebar"] * { color: #2b1e16 !important; font-weight: 900 !important; }
    h1, h2, h3, h4, p, label, .stMetric label { color: #2b1e16 !important; font-family: 'Playfair Display', serif; font-weight: 900 !important; }
    [data-testid="stMetric"] { background: linear-gradient(135deg, #ffffff 0%, #fff9e6 100%); border: 2px solid #d4af37; border-radius: 20px; padding: 25px; box-shadow: 8px 8px 20px rgba(0,0,0,0.12); }
    div.stButton > button { background: linear-gradient(180deg, #fcf6ba 0%, #d4af37 40%, #aa771c 100%) !important; color: #2b1e16 !important; border: 2px solid #8a6d3b !important; padding: 20px !important; font-weight: 900 !important; border-radius: 50px !important; width: 100% !important; text-transform: uppercase !important; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>⛏️ O GARIMPEIRO</h1>", unsafe_allow_html=True)

if 'garimpo_ok' not in st.session_state: st.session_state['garimpo_ok'] = False
if 'confirmado' not in st.session_state: st.session_state['confirmado'] = False

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

if st.session_state['confirmado']:
    if not st.session_state['garimpo_ok']:
        uploaded_files = st.file_uploader("Suba seus arquivos (ZIP ou XML):", accept_multiple_files=True)
        if uploaded_files and st.button("🚀 INICIAR GRANDE GARIMPO"):
            keys, rel, seq = set(), [], {}
            buf = io.BytesIO()
            
            # ZIP_STORED é mais rápido e evita timeout de rede
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
                for file in uploaded_files:
                    f_bytes = file.read()
                    temp_contents = []
                    if file.name.lower().endswith('.zip'):
                        with zipfile.ZipFile(io.BytesIO(f_bytes)) as z_in:
                            for name in z_in.namelist():
                                if name.lower().endswith('.xml'):
                                    temp_contents.append((os.path.basename(name), z_in.read(name)))
                    else:
                        temp_contents.append((os.path.basename(file.name), f_bytes))

                    for name, xml_data in temp_contents:
                        res, is_p = identify_xml_info(xml_data, cnpj_limpo, name)
                        key = res["Chave"] if len(res["Chave"]) == 44 else name
                        if key not in keys:
                            keys.add(key)
                            # Grava nas pastas e na pasta TODOS
                            zf.writestr(f"{res['Pasta']}/{name}", xml_data)
                            zf.writestr(f"TODOS/{name}", xml_data)
                            
                            # Guardamos apenas o necessário para o relatório (sem o conteúdo pesado)
                            rel.append({k: v for k, v in res.items() if k != "Conteúdo"})
                            if is_p and res["Número"] > 0:
                                s_k = (res["Tipo"], res["Série"])
                                if s_k not in seq: seq[s_k] = set()
                                seq[s_k].add(res["Número"])
                    # Limpa memória a cada loop
                    del temp_contents

            faltantes = []
            for (t, s), nums in seq.items():
                if len(nums) > 1:
                    ideal = set(range(min(nums), max(nums) + 1))
                    for b in sorted(list(ideal - nums)):
                        faltantes.append({"Documento": t, "Série": s, "Nº Faltante": b})

            st.session_state.update({'zip': buf.getvalue(), 'rel': rel, 'fal': pd.DataFrame(faltantes), 'garimpo_ok': True})
            st.rerun()
    else:
        st.success(f"⛏️ Garimpo Concluído! {len(st.session_state['rel'])} pepitas únicas.")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 VOLUME", len(st.session_state['rel']))
        c2.metric("⚠️ BURACOS", len(st.session_state['fal']))
        
        st.divider()
        st.download_button("📂 BAIXAR GARIMPO COMPLETO (Com pasta TODOS)", st.session_state['zip'], "garimpo.zip", use_container_width=True)

        st.divider()
        st.markdown("### 🔍 PENEIRA INDIVIDUAL")
        df = pd.DataFrame(st.session_state['rel'])
        busca = st.text_input("Número da Nota:")
        if busca:
            filtro = df[df['Número'].astype(str).str.contains(busca)]
            st.dataframe(filtro[["Arquivo", "Tipo", "Série", "Número"]], use_container_width=True, hide_index=True)
            st.info("Para baixar em volume, use o botão dourado acima.")

        st.markdown("### ⚠️ AUDITORIA DE SEQUÊNCIA")
        st.dataframe(st.session_state['fal'], use_container_width=True, hide_index=True)

        if st.button("⛏️ NOVO GARIMPO"):
            st.session_state['garimpo_ok'] = False
            st.rerun()
