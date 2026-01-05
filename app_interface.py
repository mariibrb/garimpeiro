import streamlit as st
import os, io, pandas as pd
from motor_fiscal import extrair_dados_xml, gerar_excel_final

# Configuração da página - Removemos qualquer sidebar indesejada
st.set_page_config(page_title="Sentinela Nascel", page_icon="🧡", layout="wide", initial_sidebar_state="collapsed")

# Estilos CSS
st.markdown("""
<style>
    [data-testid="stSidebar"] { display: none; }
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3 { color: #FF6F00 !important; font-weight: 700; text-align: center; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 20px; font-weight: bold; width: 100%; height: 50px; border: none; }
    .stButton>button:hover { background-color: #E65100; }
    .stFileUploader { border: 1px dashed #FF6F00; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- LOGO CENTRALIZADO (RESOLVENDO O ERRO DE TEXTO) ---
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    # Usamos o caminho absoluto ou relativo direto para evitar que o Python imprima o objeto
    logo = ".streamlit/Sentinela.png"
    if os.path.exists(logo):
        st.image(logo, use_container_width=True)
    else:
        st.title("🚀 SENTINELA NASCEL")

st.markdown("---")

# --- ÁREA DE UPLOADS ---
col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.subheader("📥 FLUXO DE ENTRADAS")
    xml_e = st.file_uploader("📂 XMLs de Entrada", type='xml', accept_multiple_files=True, key="xe")
    ger_e = st.file_uploader("📊 Gerencial Entradas", type='csv', key="ge")
    aut_e = st.file_uploader("🔍 Autenticidade Entrada", type=['xlsx'], key="ae")

with col_sai:
    st.subheader("📤 FLUXO DE SAÍDAS")
    xml_s = st.file_uploader("📂 XMLs de Saída", type='xml', accept_multiple_files=True, key="xs")
    ger_s = st.file_uploader("📊 Gerencial Saídas", type='csv', key="gs")
    aut_s = st.file_uploader("🔍 Autenticidade Saída", type=['xlsx'], key="as")

st.markdown("<br>", unsafe_allow_html=True)

# --- BOTÃO DE EXECUÇÃO ---
if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary"):
    if not (xml_e or xml_s):
        st.warning("🧡 Por favor, carregue os arquivos XML para começar.")
    else:
        with st.spinner("🧡 O Sentinela está trabalhando..."):
            try:
                df_xe = extrair_dados_xml(xml_e)
                df_xs = extrair_dados_xml(xml_s)
                relatorio = gerar_excel_final(df_xe, df_xs, ger_e, ger_s, aut_e, aut_s)
                
                st.success("Análise concluída com sucesso! 🧡")
                st.download_button(
                    label="💾 BAIXAR RELATÓRIO FINAL",
                    data=relatorio,
                    file_name="Auditoria_Sentinela.xlsx",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Erro no processamento: {e}")
