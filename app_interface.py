import streamlit as st
import os
import io
import pandas as pd
from datetime import datetime
from motor_fiscal import extrair_dados_xml, gerar_excel_final

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Nascel | Sentinela", page_icon="🧡", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3, h4 { color: #FF6F00 !important; font-weight: 700; }
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        background-color: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetricValue"] { color: #FF6F00 !important; font-size: 2.2rem !important; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 25px; font-weight: bold; width: 100%; border: none; padding: 12px; }
    .stButton>button:hover { background-color: #E65100; transform: scale(1.02); }
    .stFileUploader { padding: 5px; border: 1px dashed #FF6F00; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO DE ESTADO PARA LIMPEZA ---
if 'xml_e_key' not in st.session_state: st.session_state.xml_e_key = 0
if 'xml_s_key' not in st.session_state: st.session_state.xml_s_key = 0

# --- BARRA LATERAL (RESTAURADA) ---
with st.sidebar:
    if os.path.exists(".streamlit/nascel sem fundo.png"):
        st.image(".streamlit/nascel sem fundo.png", use_container_width=True)
    
    st.markdown("---")
    
    with st.expander("📥 **Baixar Gabaritos**", expanded=False):
        df_modelo = pd.DataFrame(columns=['CHAVE', 'STATUS'])
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_modelo.to_excel(writer, index=False)
        st.download_button("📄 Modelo ICMS", buffer.getvalue(), "modelo_icms.xlsx", use_container_width=True)
        st.download_button("📄 Modelo PIS/COFINS", buffer.getvalue(), "modelo_pis_cofins.xlsx", use_container_width=True)

    st.markdown("### ⚙️ Configurações de Base")
    
    with st.expander("🔄 **Atualizar Base ICMS**"):
        up_icms = st.file_uploader("Arquivo ICMS", type=['xlsx'], key='base_i', label_visibility="collapsed")
        if up_icms:
            with open(".streamlit/Base_ICMS.xlsx", "wb") as f: f.write(up_icms.getbuffer())
            st.toast("Base ICMS atualizada!", icon="✅")

    with st.expander("🔄 **Atualizar Base PIS/COF**"):
        up_pis = st.file_uploader("Arquivo PIS", type=['xlsx'], key='base_p', label_visibility="collapsed")
        if up_pis:
            with open(".streamlit/Base_CST_Pis_Cofins.xlsx", "wb") as f: f.write(up_pis.getbuffer())
            st.toast("Base PIS/COF atualizada!", icon="✅")

# --- ÁREA CENTRAL ---
c1, c2, c3 = st.columns([3, 4, 3])
with c2:
    if os.path.exists(".streamlit/Sentinela.png"):
        st.image(".streamlit/Sentinela.png", use_container_width=True)

st.markdown("---")

col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    h1, h2 = st.columns([3, 1])
    h1.markdown("### 📥 1. Entradas")
    if h2.button("🗑️ Limpar", key="clr_e"): 
        st.session_state.xml_e_key += 1
        st.rerun()
    xml_ent = st.file_uploader("📂 XMLs Entradas", type='xml', accept_multiple_files=True, key=f"e_{st.session_state.xml_e_key}")
    ger_ent = st.file_uploader("📊 Gerencial Entradas (CSV)", type=['csv'], key="ge")

with col_sai:
    h3, h4 = st.columns([3, 1])
    h3.markdown("### 📤 2. Saídas")
    if h4.button("🗑️ Limpar", key="clr_s"): 
        st.session_state.xml_s_key += 1
        st.rerun()
    xml_sai = st.file_uploader("📂 XMLs Saídas", type='xml', accept_multiple_files=True, key=f"s_{st.session_state.xml_s_key}")
    ger_sai = st.file_uploader("📊 Gerencial Saídas (CSV)", type=['csv'], key="gs")

# --- EXECUÇÃO ---
st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 EXECUTAR SENTINELA", type="primary", use_container_width=True):
    if not (xml_ent or xml_sai or ger_ent or ger_sai):
        st.error("Por favor, carregue os arquivos (XML ou Gerencial) para iniciar.")
    else:
        try:
            with st.spinner("Compilando dados... 🧡"):
                df_e_xml = extrair_dados_xml(xml_ent, "Entrada") if xml_ent else pd.DataFrame()
                df_s_xml = extrair_dados_xml(xml_sai, "Saída") if xml_sai else pd.DataFrame()
                
                excel_bin, stats = gerar_excel_final(df_e_xml, df_s_xml, file_ger_ent=ger_ent, file_ger_sai=ger_sai)
                
                if excel_bin:
                    st.success("Cálculos Finalizados!")
                    if ger_ent or ger_sai:
                        t1, t2 = st.tabs(["💰 PIS/COFINS", "🧾 ICMS e IPI"])
                        with t1:
                            m1, m2, m3 = st.columns(3)
                            m1.metric("Débitos Totais", f"R$ {stats['total_deb']:,.2f}")
                            m2.metric("Créditos Totais", f"R$ {stats['total_cred']:,.2f}")
                            saldo_pc = stats['total_deb'] - stats['total_cred']
                            m3.metric("Saldo Período", f"R$ {abs(saldo_pc):,.2f}", delta="A PAGAR" if saldo_pc > 0 else "CREDOR")
                        with t2:
                            c1, c2 = st.columns(2)
                            s_icms = stats['icms_deb'] - stats['icms_cred']
                            c1.metric("Saldo ICMS", f"R$ {abs(s_icms):,.2f}", delta="A PAGAR" if s_icms > 0 else "CREDOR")
                            s_ipi = stats['ipi_deb'] - stats['ipi_cred']
                            c2.metric("Saldo IPI", f"R$ {abs(s_ipi):,.2f}", delta="A PAGAR" if s_ipi > 0 else "CREDOR")
                    
                    st.download_button("💾 BAIXAR RELATÓRIO COMPLETO", excel_bin, "Auditoria_Sentinela.xlsx", use_container_width=True)
        except Exception as e:
            st.error(f"Erro crítico: {e}")
