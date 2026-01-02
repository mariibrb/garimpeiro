import streamlit as st
import os
import io
import pandas as pd
from motor_fiscal import extrair_dados_xml, gerar_excel_final

st.set_page_config(page_title="Sentinela Nascel", page_icon="🧡", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3, h4 { color: #FF6F00 !important; font-weight: 700; }
    div[data-testid="stMetricValue"] { color: #FF6F00 !important; font-size: 2rem !important; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 25px; font-weight: bold; width: 100%; border: none; padding: 12px; }
    .stButton>button:hover { background-color: #E65100; transform: scale(1.02); }
    </style>
""", unsafe_allow_html=True)

if 'xml_e_key' not in st.session_state: st.session_state.xml_e_key = 0
if 'xml_s_key' not in st.session_state: st.session_state.xml_s_key = 0

# --- BARRA LATERAL (OBRIGATÓRIO APARECER) ---
with st.sidebar:
    if os.path.exists(".streamlit/nascel sem fundo.png"):
        st.image(".streamlit/nascel sem fundo.png", use_container_width=True)
    st.markdown("---")
    with st.expander("📥 **Gabaritos**", expanded=False):
        df_mod = pd.DataFrame(columns=['CHAVE', 'STATUS'])
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer: df_mod.to_excel(writer, index=False)
        st.download_button("📄 Modelo ICMS", buffer.getvalue(), "modelo_icms.xlsx", use_container_width=True)
    st.markdown("### ⚙️ Configurações")
    with st.expander("🔄 **Atualizar Bases**"):
        st.file_uploader("Base ICMS", type=['xlsx'], key='base_i')
        st.file_uploader("Base PIS/COF", type=['xlsx'], key='base_p')

# --- ÁREA CENTRAL ---
c1, c2, c3 = st.columns([3, 4, 3])
with c2:
    if os.path.exists(".streamlit/Sentinela.png"):
        st.image(".streamlit/Sentinela.png", use_container_width=True)

st.markdown("---")
col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    h1, h2 = st.columns([3, 1])
    h1.markdown("### 📥 1. Entradas")
    if h2.button("🗑️ Limpar", key="clr_e"):
        st.session_state.xml_e_key += 1; st.rerun()
    xml_ent = st.file_uploader("XMLs Entradas", type='xml', accept_multiple_files=True, key=f"e_{st.session_state.xml_e_key}")
    ger_ent = st.file_uploader("Gerencial Entradas (CSV)", type=['csv'], key="ge")

with col_sai:
    h3, h4 = st.columns([3, 1])
    h3.markdown("### 📤 2. Saídas")
    if h4.button("🗑️ Limpar", key="clr_s"):
        st.session_state.xml_s_key += 1; st.rerun()
    xml_sai = st.file_uploader("XMLs Saídas", type='xml', accept_multiple_files=True, key=f"s_{st.session_state.xml_s_key}")
    ger_sai = st.file_uploader("Gerencial Saídas (CSV)", type=['csv'], key="gs")

if st.button("🚀 EXECUTAR SENTINELA", type="primary", use_container_width=True):
    try:
        with st.spinner("🧡 Cruzando dados..."):
            df_e = extrair_dados_xml(xml_ent, "Entrada") if xml_ent else pd.DataFrame()
            df_s = extrair_dados_xml(xml_sai, "Saída") if xml_sai else pd.DataFrame()
            excel_bin, stats = gerar_excel_final(df_e, df_s, file_ger_ent=ger_ent, file_ger_sai=ger_sai)
            
            if excel_bin:
                st.success("Análise concluída!")
                tab1, tab2 = st.tabs(["💰 PIS/COFINS", "🧾 ICMS e IPI"])
                with tab1:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Débitos", f"R$ {stats['total_deb']:,.2f}")
                    m2.metric("Créditos", f"R$ {stats['total_cred']:,.2f}")
                    m3.metric("Saldo", f"R$ {abs(stats['total_deb']-stats['total_cred']):,.2f}")
                with tab2:
                    c1, c2 = st.columns(2)
                    c1.metric("Débito ICMS", f"R$ {stats['icms_deb']:,.2f}")
                    c2.metric("Débito IPI", f"R$ {stats['ipi_deb']:,.2f}")
                st.download_button("💾 BAIXAR RELATÓRIO", excel_bin, "Auditoria_Nascel.xlsx", use_container_width=True)
    except Exception as e:
        st.error(f"Erro: {e}")
