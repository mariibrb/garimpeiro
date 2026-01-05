import streamlit as st
import os
import io
import pandas as pd
from motor_fiscal import extrair_dados_xml, gerar_excel_final

# Configurações iniciais
st.set_page_config(page_title="Sentinela", page_icon="🧡", layout="wide")

# Estilos CSS
st.markdown("""
<style>
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3 { color: #FF6F00 !important; font-weight: 700; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 20px; font-weight: bold; width: 100%; }
</style>
""", unsafe_allow_html=True)

# Função para garantir dados de download
def download_data():
    buf = io.BytesIO()
    pd.DataFrame().to_excel(buf)
    return buf.getvalue()

# --- BARRA LATERAL ---
with st.sidebar:
    # Verificação da logo de forma simples para evitar erro de impressão
    logo_path = ".streamlit/nascel sem fundo.png"
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    else:
        st.title("🧡 Sentinela")
    
    st.markdown("---")
    st.subheader("⚙️ Configurações")
    
    with st.expander("🔄 Upload de Bases"):
        st.file_uploader("Base ICMS", type='xlsx', key='b1')
        st.file_uploader("Base PIS/COF", type='xlsx', key='b2')

    with st.expander("📥 Gabaritos"):
        st.download_button("📄 PIS/COF", download_data(), "piscof.xlsx")
        st.download_button("📄 ICMS", download_data(), "icms.xlsx")

# --- TELA PRINCIPAL ---
st.header("🚀 Auditoria Fiscal Sentinela")
st.markdown("---")

col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.subheader("📥 Entradas")
    xml_e = st.file_uploader("XMLs Entrada", type='xml', accept_multiple_files=True, key="xe")
    ger_e = st.file_uploader("Gerencial Entrada", type='csv', key="ge")
    aut_e = st.file_uploader("Autenticidade Entrada", type='xlsx', key="ae")

with col_sai:
    st.subheader("📤 Saídas")
    xml_s = st.file_uploader("XMLs Saída", type='xml', accept_multiple_files=True, key="xs")
    ger_s = st.file_uploader("Gerencial Saída", type='csv', key="gs")
    aut_s = st.file_uploader("Autenticidade Saída", type='xlsx', key="as")

st.markdown("---")
if st.button("🚀 EXECUTAR PROCESSO"):
    if xml_e or xml_s:
        with st.spinner("🧡 Processando..."):
            df_xe = extrair_dados_xml(xml_e)
            df_xs = extrair_dados_xml(xml_s)
            relat = gerar_excel_final(df_xe, df_xs, ger_e, ger_s, aut_e, aut_s)
            st.success("Concluído!")
            st.download_button("💾 BAIXAR RELATÓRIO", relat, "Sentinela.xlsx")
    else:
        st.warning("Selecione os arquivos XML.")
