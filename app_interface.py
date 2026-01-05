import streamlit as st
import os, io, pandas as pd
from motor_fiscal import extrair_dados_xml, gerar_excel_final

# Configuração da página
st.set_page_config(page_title="Sentinela Nascel", page_icon="🧡", layout="wide", initial_sidebar_state="expanded")

# Estilo CSS
st.markdown("""
    <style>
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3 { color: #FF6F00 !important; font-weight: 700; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 20px; font-weight: bold; width: 100%; }
    .stFileUploader { border: 1px dashed #FF6F00; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# Função para evitar erro no download vazio
def get_empty_excel():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as wr:
        pd.DataFrame().to_excel(wr, sheet_name='Modelos')
    return output.getvalue()

empty_data = get_empty_excel()

# --- SIDEBAR (CORRIGIDA) ---
with st.sidebar:
    # Lógica da logo separada para não imprimir texto indesejado
    if os.path.exists(".streamlit/nascel sem fundo.png"):
        st.image(".streamlit/nascel sem fundo.png", use_container_width=True)
    else:
        st.title("🧡 Sentinela")
    
    st.markdown("---")
    st.subheader("⚙️ Configurações de Base")
    
    with st.expander("🔄 Upload de Bases", expanded=False):
        st.file_uploader("Base ICMS (xlsx)", type='xlsx', key='u_icms')
        st.file_uploader("Base PIS/COFINS (xlsx)", type='xlsx', key='u_pc')
        if st.button("Salvar Bases"):
            st.toast("Bases atualizadas!", icon="✅")

    with st.expander("📥 Download de Modelos", expanded=False):
        st.download_button("📄 Gabarito PIS/COF/IPI", empty_data, "modelo_piscof_ipi.xlsx", use_container_width=True)
        st.download_button("📄 Gabarito ICMS", empty_data, "modelo_icms.xlsx", use_container_width=True)

# --- TELA PRINCIPAL ---
st.header("🚀 Sentinela: Auditoria Fiscal")
st.markdown("---")

col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.subheader("📥 1. Fluxo de Entradas")
    xml_e = st.file_uploader("📂 XMLs de Entrada", type='xml', accept_multiple_files=True, key="xe")
    ger_e = st.file_uploader("📊 Gerencial Entradas (CSV)", type=['csv'], key="ge")
    aut_e = st.file_uploader("🔍 Autenticidade Entradas (XLSX)", type=['xlsx'], key="ae")

with col_sai:
    st.subheader("📤 2. Fluxo de Saídas")
    xml_s = st.file_uploader("📂 XMLs de Saída", type='xml', accept_multiple_files=True, key="xs")
    ger_s = st.file_uploader("📊 Gerencial Saídas (CSV)", type=['csv'], key="gs")
    aut_s = st.file_uploader("🔍 Autenticidade Saídas (XLSX)", type=['xlsx'], key="as")

st.markdown("---")
if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary", use_container_width=True):
    if not (xml_e or xml_s):
        st.warning("Carregue os XMLs para começar.")
    else:
        with st.spinner("🧡 Processando Auditoria..."):
            try:
                df_xe = extrair_dados_xml(xml_e)
                df_xs = extrair_dados_xml(xml_s)
                relatorio = gerar_excel_final(df_xe, df_xs, ger_e, ger_s, aut_e, aut_s)
                st.success("Auditoria concluída!")
                st.download_button("💾 BAIXAR RELATÓRIO", relatorio, "Relatorio_Sentinela.xlsx", use_container_width=True)
            except Exception as e:
                st.error(f"Erro ao processar: {e}")
