import streamlit as st
import os, io, pandas as pd
from motor_fiscal import extrair_dados_xml, gerar_excel_final

# Configuração da página
st.set_page_config(page_title="Sentinela Nascel", page_icon="🧡", layout="wide", initial_sidebar_state="expanded")

# Estilos CSS (Cores da Nascel e Limpeza)
st.markdown("""
<style>
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3 { color: #FF6F00 !important; font-weight: 700; text-align: center; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 20px; font-weight: bold; width: 100%; height: 50px; border: none; }
    .stFileUploader { border: 1px dashed #FF6F00; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 1. LADO ESQUERDO (SIDEBAR RESTAURADA) ---
with st.sidebar:
    logo_lateral = ".streamlit/nascel sem fundo.png"
    if os.path.exists(logo_lateral):
        st.image(logo_lateral, use_container_width=True)
    
    st.markdown("---")
    st.subheader("⚙️ Configurações de Base")
    
    # UPLOADS DE BASES
    st.file_uploader("Upload Base ICMS", type=['xlsx'], key='base_icms_side')
    st.file_uploader("Upload Base PIS/COFINS", type=['xlsx'], key='base_pc_side')
    
    st.markdown("---")
    st.subheader("📥 Downloads de Base")
    # Arquivo fictício para os botões não darem erro
    buf = io.BytesIO()
    pd.DataFrame().to_excel(buf)
    st.download_button("Download Base PIS/COFINS", buf.getvalue(), "base_piscofins.xlsx", use_container_width=True)
    st.download_button("Download Base IPI", buf.getvalue(), "base_ipi.xlsx", use_container_width=True)

# --- 2. TELA PRINCIPAL (CENTRO) ---
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    logo_centro = ".streamlit/Sentinela.png"
    if os.path.exists(logo_centro):
        st.image(logo_centro, use_container_width=True)
    else:
        st.title("🚀 SENTINELA NASCEL")

st.markdown("---")

col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.subheader("📥 FLUXO DE ENTRADAS")
    xml_e = st.file_uploader("📂 XMLs de Entrada", type='xml', accept_multiple_files=True, key="xe")
    ger_e = st.file_uploader("📊 Gerencial Entrada", type=['csv'], key="ge")
    aut_e = st.file_uploader("🔍 Autenticidade Entrada", type=['xlsx'], key="ae")

with col_sai:
    st.subheader("📤 FLUXO DE SAÍDAS")
    xml_s = st.file_uploader("📂 XMLs de Saída", type='xml', accept_multiple_files=True, key="xs")
    ger_s = st.file_uploader("📊 Gerencial Saída", type=['csv'], key="gs")
    aut_s = st.file_uploader("🔍 Autenticidade Saída", type=['xlsx'], key="as")

st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary"):
    with st.spinner("🧡 O Sentinela está trabalhando..."):
        try:
            df_xe = extrair_dados_xml(xml_e)
            df_xs = extrair_dados_xml(xml_s)
            relatorio = gerar_excel_final(df_xe, df_xs, ger_e, ger_s, aut_e, aut_s)
            st.success("Análise concluída com sucesso! 🧡")
            st.download_button("💾 BAIXAR RELATÓRIO", relatorio, "Auditoria.xlsx", use_container_width=True)
        except Exception as e:
            st.error(f"Erro: {e}")
