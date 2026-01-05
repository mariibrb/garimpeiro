import streamlit as st
import os, io, pandas as pd
from motor_fiscal import extrair_dados_xml, gerar_excel_final

# 1. Configuração de Página
st.set_page_config(page_title="Sentinela Nascel", page_icon="🧡", layout="wide", initial_sidebar_state="expanded")

# 2. Estilo CSS para limpeza total
st.markdown("""
<style>
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3 { color: #FF6F00 !important; font-weight: 700; text-align: center; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 20px; font-weight: bold; width: 100%; height: 50px; border: none; }
    .stFileUploader { border: 1px dashed #FF6F00; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 3. SIDEBAR (LADO ESQUERDO) ---
with st.sidebar:
    # LOGO NASCEL - Limpo e isolado
    logo_path = ".streamlit/nascel sem fundo.png"
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    
    st.markdown("---")
    st.subheader("🔄 Upload de Bases")
    st.file_uploader("Base ICMS", type=['xlsx'], key='base_i')
    st.file_uploader("Base PIS/COFINS", type=['xlsx'], key='base_p')
    
    st.markdown("---")
    st.subheader("📥 Download de Bases")
    buf = io.BytesIO()
    pd.DataFrame().to_excel(buf)
    st.download_button("Download Base PIS/COF", buf.getvalue(), "base_pc.xlsx", use_container_width=True)
    st.download_button("Download Base IPI", buf.getvalue(), "base_ipi.xlsx", use_container_width=True)

# --- 4. TELA PRINCIPAL (CENTRO) ---
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    # SOLDADINHO - Limpo e isolado
    soldado_path = ".streamlit/Sentinela.png"
    if os.path.exists(soldado_path):
        st.image(soldado_path, use_container_width=True)
    else:
        st.title("🚀 SENTINELA NASCEL")

st.markdown("---")

col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.subheader("📥 FLUXO DE ENTRADAS")
    xml_e = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="main_xe")
    ger_e = st.file_uploader("📊 Gerencial (CSV)", type=['csv'], key="main_ge")
    aut_e = st.file_uploader("🔍 Autenticidade", type=['xlsx'], key="main_ae")

with col_sai:
    st.subheader("📤 FLUXO DE SAÍDAS")
    xml_s = st.file_uploader("📂 XMLs ", type='xml', accept_multiple_files=True, key="main_xs")
    ger_s = st.file_uploader("📊 Gerencial (CSV) ", type=['csv'], key="main_gs")
    aut_s = st.file_uploader("🔍 Autenticidade ", type=['xlsx'], key="main_as")

st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary"):
    with st.spinner("🧡 O Sentinela está auditando..."):
        try:
            df_xe = extrair_dados_xml(xml_e)
            df_xs = extrair_dados_xml(xml_s)
            relatorio = gerar_excel_final(df_xe, df_xs, ger_e, ger_s, aut_e, aut_s)
            st.success("Auditoria concluída com sucesso! 🧡")
            st.download_button("💾 BAIXAR RELATÓRIO", relatorio, "Auditoria_Sentinela.xlsx", use_container_width=True)
        except Exception as e:
            st.error(f"Erro: {e}")
