import streamlit as st
import os, io, pandas as pd
from motor_fiscal import extrair_dados_xml, gerar_excel_final

# MATA A SIDEBAR E O ERRO TECNICO
st.set_page_config(page_title="Sentinela Nascel", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* Força o sumiço da sidebar e de qualquer mensagem de erro do sistema */
    [data-testid="stSidebar"], [data-testid="collapsedControl"], .stException { display: none !important; }
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3 { color: #FF6F00 !important; font-weight: 700; text-align: center; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 20px; font-weight: bold; width: 100%; height: 50px; border: none; }
</style>
""", unsafe_allow_html=True)

# Logo Central (Soldadinho) - Isolado para não dar erro DeltaGenerator
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    logo = ".streamlit/Sentinela.png"
    if os.path.exists(logo):
        st.image(logo, use_container_width=True)
    else:
        st.title("🚀 SENTINELA NASCEL")

st.markdown("---")

col1, col2 = st.columns(2)
with col1:
    st.subheader("📥 ENTRADAS")
    xml_e = st.file_uploader("XMLs Entrada", accept_multiple_files=True, key="xe")
    ger_e = st.file_uploader("Gerencial Entrada (CSV)", key="ge")

with col2:
    st.subheader("📤 SAÍDAS")
    xml_s = st.file_uploader("XMLs Saída", accept_multiple_files=True, key="xs")
    ger_s = st.file_uploader("Gerencial Saída (CSV)", key="gs")

if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary"):
    with st.spinner("Analisando..."):
        try:
            df_xe = extrair_dados_xml(xml_e)
            df_xs = extrair_dados_xml(xml_s)
            relat = gerar_excel_final(df_xe, df_xs, ger_e, ger_s)
            st.success("Concluído!")
            st.download_button("💾 BAIXAR RELATÓRIO", relat, "Auditoria.xlsx", use_container_width=True)
        except:
            st.error("Erro nos arquivos.")
