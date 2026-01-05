import streamlit as st
import os, io, pandas as pd
from motor_fiscal import extrair_dados_xml, gerar_excel_final

# 1. Configuração da Página (Sem firulas para não bugar)
st.set_page_config(page_title="Sentinela Nascel", page_icon="🧡", layout="wide", initial_sidebar_state="expanded")

# 2. Estilo CSS (Cores da Nascel)
st.markdown("""
<style>
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3 { color: #FF6F00 !important; font-weight: 700; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 20px; font-weight: bold; width: 100%; height: 50px; border: none; }
    .stFileUploader { border: 1px dashed #FF6F00; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 3. LADO ESQUERDO (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Configurações")
    st.markdown("---")
    
    st.subheader("🔄 Upload de Bases")
    st.file_uploader("Base ICMS", type=['xlsx'], key='up_icms')
    st.file_uploader("Base PIS/COFINS", type=['xlsx'], key='up_pc')
    
    st.markdown("---")
    st.subheader("📥 Download de Bases")
    # Criando um arquivo vazio para o botão não dar erro de Stream
    buf = io.BytesIO()
    pd.DataFrame().to_excel(buf)
    st.download_button("Baixar Base PIS/COFINS", buf.getvalue(), "base_pis_cofins.xlsx")
    st.download_button("Baixar Base IPI", buf.getvalue(), "base_ipi.xlsx")

# --- 4. TELA PRINCIPAL (CENTRO) ---
# O Soldadinho centralizado
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    # IMPORTANTE: O arquivo tem que estar na pasta .streamlit/Sentinela.png
    if os.path.exists(".streamlit/Sentinela.png"):
        st.image(".streamlit/Sentinela.png", use_container_width=True)
    else:
        st.title("🚀 SENTINELA NASCEL")

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

st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀 EXECUTAR AUDITORIA COMPLETA"):
    with st.spinner("🧡 O Sentinela está trabalhando..."):
        try:
            df_xe = extrair_dados_xml(xml_e)
            df_xs = extrair_dados_xml(xml_s)
            relatorio = gerar_excel_final(df_xe, df_xs)
            st.success("Análise concluída com sucesso! 🧡")
            st.download_button("💾 BAIXAR RELATÓRIO", relatorio, "Resultado.xlsx")
        except Exception as e:
            st.error(f"Erro: {e}")
