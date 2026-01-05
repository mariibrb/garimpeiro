import streamlit as st
import os, io, pandas as pd
from motor_fiscal import extrair_dados_xml, gerar_excel_final

# CONFIGURAÇÃO DE PÁGINA
st.set_page_config(
    page_title="Sentinela Nascel", 
    page_icon="🧡", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# ESTILIZAÇÃO CSS
st.markdown("""
<style>
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3 { color: #FF6F00 !important; font-weight: 700; text-align: center; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 20px; font-weight: bold; width: 100%; height: 50px; border: none; }
    .stButton>button:hover { background-color: #E65100; cursor: pointer; }
    .stFileUploader { border: 1px dashed #FF6F00; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR (LADO ESQUERDO) ---
with st.sidebar:
    logo_sidebar = ".streamlit/nascel sem fundo.png"
    if os.path.exists(logo_sidebar):
        st.image(logo_sidebar, use_container_width=True)
    else:
        st.header("Menu Sentinela")
    
    st.markdown("---")
    st.subheader("⚙️ Configurações de Base")
    with st.expander("🔄 Upload de Bases", expanded=False):
        st.file_uploader("Base ICMS (XLSX)", type=['xlsx'], key='up_icms')
        st.file_uploader("Base PIS/COFINS (XLSX)", type=['xlsx'], key='up_pc')
        if st.button("Salvar Configurações"):
            st.toast("Bases salvas!", icon="✅")

    with st.expander("📥 Download de Bases", expanded=False):
        # Botões de download vazios para não dar erro de Stream
        buf = io.BytesIO()
        pd.DataFrame().to_excel(buf)
        st.download_button("Baixar Base PIS/COF", buf.getvalue(), "base_pc.xlsx", use_container_width=True)
        st.download_button("Baixar Base IPI", buf.getvalue(), "base_ipi.xlsx", use_container_width=True)

# --- TELA PRINCIPAL (CENTRO) ---
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    soldadinho = ".streamlit/Sentinela.png"
    if os.path.exists(soldadinho):
        st.image(soldadinho, use_container_width=True)
    else:
        st.title("🚀 SENTINELA NASCEL")

st.markdown("---")

col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.subheader("📥 FLUXO DE ENTRADAS")
    xml_e = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="main_xe")
    ger_e = st.file_uploader("📊 Gerencial (CSV)", type=['csv'], key="main_ge")
    aut_e = st.file_uploader("🔍 Autenticidade (XLSX)", type=['xlsx'], key="main_ae")

with col_sai:
    st.subheader("📤 FLUXO DE SAÍDAS")
    xml_s = st.file_uploader("📂 XMLs ", type='xml', accept_multiple_files=True, key="main_xs")
    ger_s = st.file_uploader("📊 Gerencial (CSV) ", type=['csv'], key="main_gs")
    aut_s = st.file_uploader("🔍 Autenticidade (XLSX) ", type=['xlsx'], key="main_as")

st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary"):
    if not xml_e and not xml_s:
        st.warning("🧡 Por favor, carregue os arquivos XML para começar.")
    else:
        with st.spinner("🧡 O Sentinela está auditando os dados..."):
            try:
                df_xe = extrair_dados_xml(xml_e, "Entrada")
                df_xs = extrair_dados_xml(xml_s, "Saída")
                relatorio = gerar_excel_final(df_xe, df_xs, ger_e, ger_s, aut_e, aut_s)
                
                st.success("Auditoria concluída com sucesso! 🧡")
                st.download_button(
                    label="💾 BAIXAR RELATÓRIO FINAL",
                    data=relatorio,
                    file_name="Auditoria_Sentinela.xlsx",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Erro crítico no processamento: {e}")
