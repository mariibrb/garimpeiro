import streamlit as st
import os
import io
import pandas as pd
from datetime import datetime
from motor_fiscal import extrair_dados_xml, gerar_excel_final

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Nascel | Sentinela Dashboard", page_icon="🧡", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3, h4 { color: #FF6F00 !important; font-weight: 700; }
    div[data-testid="stMetricValue"] { color: #FF6F00 !important; font-size: 1.8rem !important; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 25px; font-weight: bold; width: 100%; border: none; padding: 12px; }
    .stButton>button:hover { background-color: #E65100; transform: scale(1.01); }
    </style>
""", unsafe_allow_html=True)

if 'xml_ent_key' not in st.session_state: st.session_state.xml_ent_key = 0
if 'xml_sai_key' not in st.session_state: st.session_state.xml_sai_key = 0

# --- BARRA LATERAL ---
with st.sidebar:
    if os.path.exists(".streamlit/nascel sem fundo.png"):
        st.image(".streamlit/nascel sem fundo.png", use_container_width=True)
    st.markdown("---")
    st.info("Carregue os arquivos Gerenciais para gerar o Dashboard de PIS/COFINS.")

# --- ÁREA CENTRAL ---
c1, c2, c3 = st.columns([3, 4, 3])
with c2:
    if os.path.exists(".streamlit/Sentinela.png"):
        st.image(".streamlit/Sentinela.png", use_container_width=True)

st.markdown("---")

col_ent, col_sai = st.columns(2, gap="large")
with col_ent:
    st.markdown("### 📥 1. Entradas")
    xml_ent = st.file_uploader("📂 XMLs de Entrada", type='xml', accept_multiple_files=True, key=f"xml_e_{st.session_state.xml_ent_key}")
    ger_ent = st.file_uploader("📊 Gerenc. Entradas (CSV)", type=['csv'], key="ge")

with col_sai:
    st.markdown("### 📤 2. Saídas")
    xml_sai = st.file_uploader("📂 XMLs de Saída", type='xml', accept_multiple_files=True, key=f"xml_s_{st.session_state.xml_sai_key}")
    ger_sai = st.file_uploader("📊 Gerenc. Saídas (CSV)", type=['csv'], key="gs")

st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀 PROCESSAR DASHBOARD E AUDITORIA", type="primary", use_container_width=True):
    if not (ger_ent or ger_sai or xml_ent or xml_sai):
        st.error("Por favor, carregue ao menos os arquivos Gerenciais.")
    else:
        try:
            with st.spinner("Compilando dados para o Dashboard... 🧡"):
                # Processamento de XMLs (opcional)
                df_e = extrair_dados_xml(xml_ent, "Entrada") if xml_ent else pd.DataFrame()
                df_s = extrair_dados_xml(xml_sai, "Saída") if xml_sai else pd.DataFrame()
                
                # Motor gera o Excel e as métricas do Dash
                excel_binario, stats = gerar_excel_final(df_e, df_s, file_ger_ent=ger_ent, file_ger_sai=ger_sai)
                
                if excel_binario:
                    st.success("Dados processados com sucesso!")
                    
                    # --- DASHBOARD (O que você pediu) ---
                    st.markdown("### 📊 Resultado da Apuração PIS/COFINS")
                    m1, m2, m3 = st.columns(3)
                    
                    with m1:
                        st.metric("Débitos (Saídas)", f"R$ {stats['deb']:,.2f}")
                    with m2:
                        st.metric("Créditos (Entradas)", f"R$ {stats['cred']:,.2f}")
                    with m3:
                        saldo = stats['deb'] - stats['cred']
                        cor = "normal" if saldo > 0 else "inverse"
                        st.metric("Saldo a Pagar / Credor", f"R$ {abs(saldo):,.2f}", 
                                  delta="A PAGAR" if saldo > 0 else "CREDOR", delta_color=cor)

                    st.markdown("---")
                    st.download_button(
                        label="💾 BAIXAR RELATÓRIO EXCEL COMPLETO",
                        data=excel_binario,
                        file_name="Apuração_Sentinela.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
        except Exception as e:
            st.error(f"Erro no processamento: {e}")
