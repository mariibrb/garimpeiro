import streamlit as st
import os, io, pandas as pd
from motor_fiscal import extrair_dados_xml, gerar_excel_final

# 1. Configuração da página (Para que não apareça nada estranho no carregamento)
st.set_page_config(page_title="Sentinela Nascel", page_icon="🧡", layout="wide", initial_sidebar_state="expanded")

# 2. Estilos CSS (Cores da Nascel e sumir com bordas técnicas)
st.markdown("""
<style>
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3 { color: #FF6F00 !important; font-weight: 700; text-align: center; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 20px; font-weight: bold; width: 100%; height: 50px; border: none; }
    .stFileUploader { border: 1px dashed #FF6F00; border-radius: 10px; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; }
</style>
""", unsafe_allow_html=True)

# Auxiliar para evitar erro de stream nos botões
def get_model_data():
    buf = io.BytesIO()
    pd.DataFrame().to_excel(buf)
    return buf.getvalue()

empty_data = get_model_data()

# --- 3. LADO ESQUERDO (SIDEBAR LIMPA) ---
with st.sidebar:
    # Mostra a logo Nascel
    path_logo_nascel = ".streamlit/nascel sem fundo.png"
    if os.path.exists(path_logo_nascel):
        st.image(path_logo_nascel, use_container_width=True)
    
    st.markdown("---")
    
    # Upload de Bases
    st.subheader("🔄 Upload de Bases")
    st.file_uploader("Base de Dados ICMS", type=['xlsx'], key='base_icms_side')
    st.file_uploader("Base de Dados PIS/COFINS", type=['xlsx'], key='base_pc_side')
    
    st.markdown("---")
    
    # Download de Bases
    st.subheader("📥 Download de Bases")
    st.download_button("Download Base PIS/COFINS", empty_data, "base_piscofins.xlsx", use_container_width=True)
    st.download_button("Download Base IPI", empty_data, "base_ipi.xlsx", use_container_width=True)

# --- 4. TELA PRINCIPAL (CENTRO) ---
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    path_soldadinho = ".streamlit/Sentinela.png"
    if os.path.exists(path_soldadinho):
        st.image(path_soldadinho, use_container_width=True)
    else:
        st.title("🚀 SENTINELA NASCEL")

st.markdown("---")

col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.subheader("📥 FLUXO DE ENTRADAS")
    xml_e = st.file_uploader("📂 XMLs de Entrada", type='xml', accept_multiple_files=True, key="main_xe")
    ger_e = st.file_uploader("📊 Gerencial Entrada", type=['csv'], key="main_ge")
    aut_e = st.file_uploader("🔍 Autenticidade Entrada", type=['xlsx'], key="main_ae")

with col_sai:
    st.subheader("📤 FLUXO DE SAÍDAS")
    xml_s = st.file_uploader("📂 XMLs de Saída", type='xml', accept_multiple_files=True, key="main_xs")
    ger_s = st.file_uploader("📊 Gerencial Saída", type=['csv'], key="main_gs")
    aut_s = st.file_uploader("🔍 Autenticidade Saída", type=['xlsx'], key="main_as")

st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary"):
    with st.spinner("🧡 O Sentinela está auditando seus dados..."):
        try:
            df_xe = extrair_dados_xml(xml_e)
            df_xs = extrair_dados_xml(xml_s)
            relatorio = gerar_excel_final(df_xe, df_xs, ger_e, ger_s, aut_e, aut_s)
            st.success("Análise concluída com sucesso! 🧡")
            st.download_button("💾 BAIXAR RELATÓRIO", relatorio, "Auditoria_Sentinela.xlsx", use_container_width=True)
        except Exception as e:
            st.error(f"Erro: {e}")
