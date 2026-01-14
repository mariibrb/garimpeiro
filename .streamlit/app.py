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
    resumo_nota = {
        "Arquivo": file_name, "Chave": "", "Tipo": "Outros", "Série": "0",
        "Número": 0, "Pasta": "RECEBIDOS_TERCEIROS/OUTROS", "Conteúdo": content_bytes
    }
    try:
        content_str = content_bytes.decode('utf-8', errors='ignore')
        match_ch = re.search(r'\d{44}', content_str)
        resumo_nota["Chave"] = match_ch.group(0) if match_ch else ""
        tag_lower = content_str.lower()
        d_type = "NF-e"
        if '<mod>65</mod>' in tag_lower: d_type = "NFC-e"
        elif '<infcte' in tag_lower: d_type = "CT-e"
        elif '<infmdfe' in tag_lower: d_type = "MDF-e"
        
        status = "NORMAIS"
        if '<procevento' in tag_lower or '<revento' in tag_lower:
            status = "EVENTOS_CANCELAMENTOS"
            if '110111' in tag_lower: status = "CANCELADOS"
            elif '110110' in tag_lower: status = "CARTA_CORRECAO"
        elif '<inutnfe' in tag_lower or '<procinut' in tag_lower:
            status = "INUTILIZADOS"
            d_type = "Inutilizacoes"
            
        resumo_nota["Tipo"] = d_type
        s_match = re.search(r'<(?:serie|serie)>(\d+)</?:serie|serie>', content_str)
        resumo_nota["Série"] = s_match.group(1) if s_match else "0"
        n_match = re.search(r'<(?:nNF|nCT|nMDF|nNFIni)>(\d+)</(?:nNF|nCT|nMDF|nNFIni)>', content_str)
        resumo_nota["Número"] = int(n_match.group(1)) if n_match else 0
        
        emit_match = re.search(r'<(?:emit|infInut|detEvento)>.*?<CNPJ>(\d+)</CNPJ>', content_str, re.DOTALL)
        cnpj_emit = emit_match.group(1) if emit_match else ""
        
        is_p = False
        if client_cnpj_clean:
            if cnpj_emit == client_cnpj_clean: is_p = True
            elif resumo_nota["Chave"] and client_cnpj_clean in resumo_nota["Chave"][6:20]: is_p = True
            
        if is_p:
            resumo_nota["Pasta"] = f"EMITIDOS_CLIENTE/{d_type}/{status}/Serie_{resumo_nota['Série']}"
        else:
            resumo_nota["Pasta"] = f"RECEBIDOS_TERCEIROS/{d_type}"
            
        return resumo_nota, is_p
    except:
        return resumo_nota, False

def format_cnpj(cnpj):
    cnpj = "".join(filter(str.isdigit, cnpj))
    if len(cnpj) > 14: cnpj = cnpj[:14]
    if len(cnpj) <= 2: return cnpj
    if len(cnpj) <= 5: return f"{cnpj[:2]}.{cnpj[2:]}"
    if len(cnpj) <= 8: return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:]}"
    if len(cnpj) <= 12: return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:]}"
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

# --- DESIGN PREMIUM E BLINDAGEM ---
st.set_page_config(page_title="O Garimpeiro", layout="wide", page_icon="⛏️")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;} footer {visibility: hidden !important;} header {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    .stApp { background-color: #f7f3f0; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #EADBC8 0%, #D2B48C 100%) !important; border-right: 3px solid #b8860b; }
    [data-testid="stSidebar"] * { color: #2b1e16 !important; font-weight: 900 !important; }
    [data-testid="stSidebar"] div.stButton > button { background: linear-gradient(180deg, #fcf6ba 0%, #d4af37 100%) !important; color: #2b1e16 !important; border: 2px solid #8a6d3b !important; font-weight: 900 !important; }
    h1, h2, h3, h4, p, label, .stMetric label { color: #2b1e16 !important; font-family: 'Playfair Display', serif; font-weight: 900 !important; }
    h1 { font-size: 3.5rem !important; text-shadow: 2px 2px 0px #fff; }
    [data-testid="stMetric"] { background: linear-gradient(135deg, #ffffff 0%, #fff9e6 100%); border: 2px solid #d4af37; border-radius: 20px; padding: 25px; box-shadow: 8px 8px 20px rgba(0,0,0,0.12); }
    [data-testid="stMetricValue"] { color: #a67c00 !important; font-weight: 900 !important; font-size: 2.5rem !important; }
    
    /* Botões Principais */
    div.stButton > button:first-child {
        background: linear-gradient(180deg, #fcf6ba 0%, #d4af37 40%, #aa771c 100%);
        color: #2b1e16 !important; border: 2px solid #8a6d3b; padding: 20px 40px;
        font-size: 22px; font-weight: 900 !important; border-radius: 50px; box-shadow: 0 6px 20px rgba(0,0,0,0.25);
        width: 100%; text-transform: uppercase;
    }
    
    /* Botões de Download */
    .stDownloadButton > button {
        background: linear-gradient(180deg, #fcf6ba 0%, #d4af37 40%, #aa771c 100%) !important;
        color: #2b1e16 !important; border: 2px solid #8a6d3b !important;
        padding: 20px !important; font-weight: 900 !important; font-size: 18px !important;
        border-radius: 15px !important; width: 100% !important; text-transform: uppercase !important;
    }
    
    .gold-item { position: fixed; top: -50px; z-index: 9999; pointer-events: none; animation: drop 3.5s linear forwards; }
    @keyframes drop { 0% { transform: translateY(0) rotate(0deg); opacity: 1; } 100% { transform: translateY(110vh) rotate(720deg); opacity: 0; } }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>⛏️ O GARIMPEIRO</h1>", unsafe_allow_html=True)

if 'garimpo_ok' not in st.session_state: st.session_state['garimpo_ok'] = False
if 'confirmado' not in st.session_state: st.session_state['confirmado'] = False

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### ⛏️ Painel de Extração")
    raw_cnpj = st.text_input("CNPJ DO CLIENTE", placeholder="Digite os números")
    cnpj_limpo = "".join(filter(str.isdigit, raw_cnpj))
    if len(cnpj_limpo) == 14:
        st.markdown(f"**CLIENTE ATIVO:**\n`{format_cnpj(raw_cnpj)}`")
        if st.button("✅ LIBERAR OPERAÇÃO"):
            st.session_state['confirmado'] = True
            st.rerun()
    st.divider()
    if st.button("🗑️ RESETAR SISTEMA"):
        st.session_state.clear()
        st.rerun()

# --- ÁREA DE TRABALHO ---
if not st.session_state['confirmado']:
    st.info("💰 Para iniciar, identifique o CNPJ no menu lateral e clique em **LIBERAR OPERAÇÃO**.")
else:
    if not st.session_state['garimpo_ok']:
        st.markdown(f"### 📦 JAZIDA DE ARQUIVOS: {format_cnpj(raw_cnpj)}")
        uploaded_files = st.file_uploader("Arraste seus XMLs ou ZIPs aqui:", accept_multiple_files=True)
        if uploaded_files:
            if st.button("🚀 INICIAR GRANDE GARIMPO"):
                processed_keys, relatorio_lista, sequencias = set(), [], {}
                buf_org = io.BytesIO()
                buf_todos = io.BytesIO()
                
                with st.status("⛏️ Minerando...", expanded=True) as status:
                    with zipfile.ZipFile(buf_org, "w", zipfile.ZIP_DEFLATED) as z_org, \
                         zipfile.ZipFile(buf_todos, "w", zipfile.ZIP_DEFLATED) as z_todos:
                        
                        for file in uploaded_files:
                            f_bytes = file.read()
                            contents = []
                            if file.name.lower().endswith('.zip'):
                                with zipfile.ZipFile(io.BytesIO(f_bytes)) as z_in:
                                    for name in z_in.namelist():
                                        if name.lower().endswith('.xml'): contents.append((name, z_in.read(name)))
                            else:
                                contents.append((file.name, f_bytes))

                            for name, xml_data in contents:
                                res, is_p = identify_xml_info(xml_data, cnpj_limpo, name)
                                key = res["Chave"] if len(res["Chave"]) == 44 else name
                                if key not in processed_keys:
                                    processed_keys.add(key)
                                    z_org.writestr(f"{res['Pasta']}/{name}", xml_data)
                                    z_todos.writestr(f"TODOS/{name}", xml_data)
                                    relatorio_lista.append(res)
                                    
                                    if is_p and res["Número"] > 0 and "EMITIDOS" in res["Pasta"]:
                                        s_key = (res["Tipo"], res["Série"])
                                        if s_key not in sequencias: sequencias[s_key] = set()
                                        sequencias[s_key].add(res["Número"])

                # Auditoria
                faltantes = []
                for (t, s), nums in sequencias.items():
                    if len(nums) > 1:
                        ideal = set(range(min(nums), max(nums) + 1))
                        for b in sorted(list(ideal - nums)):
                            faltantes.append({"Documento": t, "Série": s, "Nº Faltante": b})

                st.session_state.update({
                    'zip_org': buf_org.getvalue(),
                    'zip_todos': buf_todos.getvalue(),
                    'relatorio': relatorio_lista,
                    'df_faltantes': pd.DataFrame(faltantes),
                    'garimpo_ok': True
                })
                st.rerun()
    else:
        # --- EXIBIÇÃO DOS RESULTADOS ---
        icons = ["💰", "✨", "💎", "🥇"]
        rain_html = "".join([f'<div class="gold-item" style="left:{random.randint(0,95)}%; animation-delay:{random.uniform(0,2)}s; font-size:{random.randint(25,45)}px;">{random.choice(icons)}</div>' for i in range(50)])
        st.markdown(rain_html, unsafe_allow_html=True)
        
        st.success(f"⛏️ Garimpo Finalizado! {len(st.session_state['relatorio'])} arquivos processados.")
        
        df_res = pd.DataFrame(st.session_state['relatorio'])
        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("📦 VOLUME TOTAL", len(df_res))
        emitidas = len(df_res[df_res['Pasta'].str.contains("EMITIDOS")])
        c_m2.metric("✨ NOTAS CLIENTE", emitidas)
        c_m3.metric("⚠️ BURACOS", len(st.session_state['df_faltantes']))

        st.divider()
        st.markdown("### 📥 EXTRAIR TESOURO")
        col_down1, col_down2 = st.columns(2)
        with col_down1:
            st.download_button("📂 BAIXAR GARIMPO FINAL (ORGANIZADO)", st.session_state['zip_org'], "garimpo_final.zip", "application/zip", use_container_width=True)
            st.caption("Organizado por Pastas: Emitidas, Recebidas, Série e Status.")
        with col_down2:
            st.download_button("📦 BAIXAR TODOS (PASTA ÚNICA)", st.session_state['zip_todos'], "TODOS.zip", "application/zip", use_container_width=True)
            st.caption("Todos os arquivos únicos dentro de uma pasta única chamada 'TODOS'.")

        st.divider()
        st.markdown("### 🔍 PENEIRA INDIVIDUAL")
        busca = st.text_input("Número ou Chave:", placeholder="Ex: 1234")
        if busca:
            filtro = df_res[df_res['Número'].astype(str).str.contains(busca) | df_res['Chave'].str.contains(busca)]
            for _, row in filtro.iterrows():
                st.download_button(f"📥 XML Nº {row['Número']}", row['Conteúdo'], row['Arquivo'], key=f"dl_{row['Chave']}_{random.random()}")

        st.markdown("### ⚠️ AUDITORIA DE SEQUÊNCIA")
        if not st.session_state['df_faltantes'].empty:
            st.dataframe(st.session_state['df_faltantes'], use_container_width=True, hide_index=True)
        else:
            st.success("Mina íntegra! Sequência completa.")

        if st.button("⛏️ NOVO GARIMPO"):
            st.session_state['garimpo_ok'] = False
            st.rerun()
