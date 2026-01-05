import streamlit as st
import os, io, pandas as pd
from motor_fiscal import extrair_dados_xml, gerar_excel_final

# CONFIGURAÇÃO DE PÁGINA (ESTADO EXPANDIDO OBRIGATÓRIO)
st.set_page_config(
    page_title="Sentinela Nascel", 
    page_icon="🧡", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# LIMPEZA DE CSS E CORES
st.markdown("""
<style>
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3 { color: #FF6F00 !important; font-weight: 700; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 20px; font-weight: bold; width: 100%; height: 50px; }
    .stFileUploader { border: 1px dashed #FF6F00; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- LADO ESQUERDO (SIDEBAR) ---
# Aqui moram os uploads de base e downloads que você pediu
with st.sidebar:
    # Tenta carregar a imagem do soldadinho aqui também se quiser
    if os.path.exists(".streamlit/Sentinela.png"):
        st.image(".streamlit/Sentinela.png", use_container_width=True)
    
    st.title("⚙️ Configurações")
    st.markdown("---")
    
    st.subheader("🔄 Upload de Bases")
    st.file_uploader("Base de Dados ICMS", type=['xlsx'], key='base_icms_up')
    st.file_uploader("Base de Dados PIS/COFINS", type=['xlsx'], key='base_pc_up')
    
    st.markdown("---")
    st.subheader("📥 Downloads")
    # Botão de exemplo para não dar erro de stream
    buf = io.BytesIO()
    pd.DataFrame().to_excel(buf)
    st.download_button("Download Base PIS/COFINS", buf.getvalue(), "base_pis_cofins.xlsx", use_container_width=True)
    st.download_button("Download Base IPI", buf.getvalue(), "base_ipi.xlsx", use_container_width=True)

# --- TELA PRINCIPAL (CENTRO) ---
# Soldadinho Centralizado
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    # Caminho direto. Se o arquivo estiver na pasta .streamlit, ele vai aparecer.
    st.image(".streamlit/Sentinela.png", use_container_width=True)

st.markdown("---")

col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.subheader("📥 ENTRADAS")
    xml_e = st.file_uploader("📂 XMLs de Entrada", type='xml', accept_multiple_files=True, key="xe")
    ger_e = st.file_uploader("📊 Gerenciais Entrada", type='csv', key="ge")
    aut_e = st.file_uploader("🔍 Autenticidade Entrada", type=['xlsx'], key="ae")

with col_sai:
    st.subheader("📤 SAÍDAS")
    xml_s = st.file_uploader("📂 XMLs de Saída", type='xml', accept_multiple_files=True, key="xs")
    ger_s = st.file_uploader("📊 Gerenciais Saída", type='csv', key="gs")
    aut_s = st.file_uploader("🔍 Autenticidade Saída", type=['xlsx'], key="as")

if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary"):
    with st.spinner("🧡 O Sentinela está trabalhando..."):
        df_xe = extrair_dados_xml(xml_e)
        df_xs = extrair_dados_xml(xml_s)
        relatorio = gerar_excel_final(df_xe, df_xs)
        st.success("Análise concluída!")
        st.download_button("💾 BAIXAR RELATÓRIO", relatorio, "Auditoria.xlsx", use_container_width=True)
