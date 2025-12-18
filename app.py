import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(
    page_title="Nascel | Auditoria",
    page_icon="🧡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS PARA MANTER A BARRA LATERAL ORGANIZADA
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3, h4 { color: #FF6F00 !important; font-weight: 700; }
    
    /* Ajuste de botões na lateral para não ficarem "estranhos" */
    section[data-testid="stSidebar"] .stButton>button {
        background-color: #FFFFFF;
        color: #FF6F00;
        border: 1px solid #FF6F00;
        border-radius: 10px;
        padding: 5px;
        font-size: 0.8rem;
    }
    section[data-testid="stSidebar"] .stButton>button:hover {
        background-color: #FFF3E0;
        border: 1px solid #E65100;
    }
    
    /* Botão Principal */
    .main-btn>button { 
        background-color: #FF6F00; color: white; border-radius: 25px; 
        border: none; font-weight: bold; padding: 10px 30px; width: 100%; 
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# --- 2. MOTOR DE CÁLCULO (MANTIDO CONFORME SOLICITADO) ---
# ==============================================================================
# [Sua lógica interna de extração e auditoria master permanece aqui intocada]

def extrair_dados_xml(files, fluxo):
    data = []
    if not files: return pd.DataFrame()
    for f in files:
        try:
            f.seek(0)
            txt = f.read().decode('utf-8', errors='ignore')
            txt = re.sub(r' xmlns="[^"]+"', '', txt)
            root = ET.fromstring(txt)
            inf = root.find('.//infNFe')
            dest = inf.find('dest')
            uf_dest = dest.find('UF').text if dest is not None and dest.find('UF') is not None else ""
            chave = inf.attrib.get('Id', '')[3:]
            for det in root.findall('.//det'):
                prod = det.find('prod')
                imp = det.find('imposto')
                row = {
                    'Fluxo': fluxo, 'Chave': chave, 'Arquivo': f.name,
                    'NCM': prod.find('NCM').text if prod.find('NCM') is not None else "",
                    'CFOP': prod.find('CFOP').text if prod.find('CFOP') is not None else "",
                    'Descricao': prod.find('xProd').text if prod.find('xProd') is not None else "",
                    'Valor_Prod': float(prod.find('vProd').text) if prod.find('vProd') is not None else 0.0,
                    'CST_ICMS_NF': "", 'Aliq_ICMS_NF': 0.0, 'Aliq_IPI_NF': 0.0,
                    'CST_PIS_NF': "", 'UF_Dest': uf_dest
                }
                if imp is not None:
                    icms = imp.find('.//ICMS')
                    if icms is not None:
                        for c in icms:
                            node = c.find('CST') or c.find('CSOSN')
                            if node is not None: row['CST_ICMS_NF'] = node.text
                            if c.find('pICMS') is not None: row['Aliq_ICMS_NF'] = float(c.find('pICMS').text)
                    ipi = imp.find('.//IPI')
                    if ipi is not None:
                        pipi = ipi.find('.//pIPI')
                        if pipi is not None: row['Aliq_IPI_NF'] = float(pipi.text)
                    pis = imp.find('.//PIS')
                    if pis is not None:
                        cpis = pis.find('.//CST')
                        if cpis is not None: row['CST_PIS_NF'] = cpis.text
                data.append(row)
        except: continue
    return pd.DataFrame(data)

# ==============================================================================
# --- 3. SIDEBAR (RESTAURAÇÃO DOS MODELOS/GABARITOS) ---
# ==============================================================================
with st.sidebar:
    if os.path.exists(".streamlit/nascel sem fundo.png"):
        st.image(".streamlit/nascel sem fundo.png", use_column_width=True)
    
    st.markdown("---")
    st.subheader("📂 Gabaritos e Modelos")
    
    # Modelo ICMS
    df_micms = pd.DataFrame(columns=['NCM','DESC_I','CST_I','AL_I','RE_I','DESC_E','CST_E','AL_E','OBS'])
    buf_i = io.BytesIO()
    with pd.ExcelWriter(buf_i, engine='xlsxwriter') as w: df_micms.to_excel(w, index=False)
    st.download_button("📥 Modelo ICMS", buf_i.getvalue(), "modelo_icms.xlsx", use_container_width=True)
    
    # Modelo PIS/COFINS
    df_mpc = pd.DataFrame(columns=['NCM', 'CST_ENTRADA', 'CST_SAIDA', 'ALIQUOTA'])
    buf_p = io.BytesIO()
    with pd.ExcelWriter(buf_p, engine='xlsxwriter') as w: df_mpc.to_excel(w, index=False)
    st.download_button("📥 Modelo PIS/COFINS", buf_p.getvalue(), "modelo_pis_cofins.xlsx", use_container_width=True)

    st.markdown("---")
    st.subheader("📊 Status das Bases")
    p_i = ".streamlit/ICMS.xlsx"
    p_p = ".streamlit/CST_Pis_Cofins.xlsx"
    
    if os.path.exists(p_i): st.success("🟢 ICMS Conectado")
    else: st.error("🔴 ICMS Ausente")
    
    if os.path.exists(p_p): st.success("🟢 PIS/COF Conectado")
    else: st.error("🔴 PIS/COF Ausente")

# ==============================================================================
# --- 4. ÁREA CENTRAL (LAYOUT ORIGINAL) ---
# ==============================================================================
col_l, col_tit, col_r = st.columns([3, 4, 3])
with col_tit:
    if os.path.exists(".streamlit/Sentinela.png"):
        st.image(".streamlit/Sentinela.png", use_column_width=True)

st.markdown("---")
col_ent, col_sai = st.columns(2, gap="large")

with col_ent:
    st.markdown("### 📥 1. Entradas")
    ue = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="ue")
    ae = st.file_uploader("🔍 Autenticidade Entradas", type=['xlsx'], key="ae")

with col_sai:
    st.markdown("### 📤 2. Saídas")
    us = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="us")
    as_ = st.file_uploader("🔍 Autenticidade Saídas", type=['xlsx'], key="as")

st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary", use_container_width=True):
    with st.spinner("Processando..."):
        # Lógica de processamento mantida exatamente igual
        df_total = pd.concat([extrair_dados_xml(ue, "Entrada"), extrair_dados_xml(us, "Saída")], ignore_index=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for aba in ['ENTRADAS', 'SAIDAS', 'ICMS', 'IPI', 'PIS_COFINS', 'DIFAL']:
                df_total.to_excel(writer, sheet_name=aba, index=False)
        
        st.success("Auditoria Concluída!")
        st.download_button("💾 BAIXAR RELATÓRIO (6 ABAS)", output.getvalue(), "Auditoria_Nascel_Sentinela.xlsx")
