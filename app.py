import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import re
import os

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Sentinela - Nascel", page_icon="🛡️", layout="wide")

# --- 2. CSS PERSONALIZADO ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .main-title { font-size: 2.5rem; font-weight: 700; color: #555555; margin-bottom: 0px; }
    .sub-title { font-size: 1rem; color: #FF8C00; font-weight: 600; margin-bottom: 30px; }
    
    /* Cards */
    .feature-card {
        background-color: white; padding: 20px; border-radius: 10px;
        border: 1px solid #E0E0E0; text-align: center; height: 100%;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); transition: all 0.3s ease;
    }
    .feature-card:hover { transform: translateY(-3px); border-color: #FF8C00; }
    .card-icon { font-size: 2rem; display: block; margin-bottom: 10px; }
    
    /* Botões */
    .stButton button { width: 100%; border-radius: 8px; font-weight: 600; margin-top: 10px; }
    
    /* Uploaders */
    [data-testid='stFileUploader'] section { background-color: #FFF8F0; border: 1px dashed #FF8C00; }
</style>
""", unsafe_allow_html=True)

# --- 3. FUNÇÕES (Lógica básica) ---
def extrair_xml(arquivos):
    lista = []
    for arq in arquivos:
        try:
            arq.seek(0)
            xml_str = arq.read().decode('utf-8', errors='ignore')
            xml_str = re.sub(r' xmlns="[^"]+"', '', xml_str) # Remove namespaces
            root = ET.fromstring(xml_str)
            
            inf = root.find('.//infNFe')
            ide = root.find('.//ide')
            if inf is not None:
                lista.append({
                    'Chave': inf.attrib.get('Id', '')[3:],
                    'Número': ide.find('nNF').text if ide is not None else '0'
                })
        except: pass
    return pd.DataFrame(lista)

def ler_status(arquivo):
    if not arquivo: return {}
    try:
        if arquivo.name.endswith('.xlsx'): df = pd.read_excel(arquivo, dtype=str)
        else: df = pd.read_csv(arquivo, dtype=str)
        # Ajuste as colunas conforme seu arquivo da Sefaz (ex: col 0 = chave, col 5 = status)
        return dict(zip(df.iloc[:, 0].str.replace(r'\D', '', regex=True), df.iloc[:, 5]))
    except: return {}

# --- 4. CABEÇALHO ---
col_logo, col_text = st.columns([1, 5])
with col_logo:
    path = "nascel sem fundo.png" if os.path.exists("nascel sem fundo.png") else ".streamlit/nascel sem fundo.png"
    if os.path.exists(path): st.image(path, width=150)
    else: st.markdown("### NASCEL")

with col_text:
    st.markdown('<div class="main-title">Sentinela Fiscal</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Central de Auditoria e Compliance</div>', unsafe_allow_html=True)

st.divider()

# =========================================================
# 1. IMPORTAÇÃO DOS XMLS (MATÉRIA PRIMA)
# =========================================================
st.markdown("### 📂 1. Arquivos XML")
c1, c2 = st.columns(2, gap="medium")

with c1:
    st.markdown('<div class="feature-card"><span class="card-icon">📥</span><b>Entradas XML</b></div>', unsafe_allow_html=True)
    xml_ent = st.file_uploader("Entradas XML", type=["xml"], accept_multiple_files=True, label_visibility="collapsed", key="xml_in")

with c2:
    st.markdown('<div class="feature-card"><span class="card-icon">📤</span><b>Saídas XML</b></div>', unsafe_allow_html=True)
    xml_sai = st.file_uploader("Saídas XML", type=["xml"], accept_multiple_files=True, label_visibility="collapsed", key="xml_out")

st.markdown("<br>", unsafe_allow_html=True)

# =========================================================
# 2. AUTENTICIDADE (UPLOADS SEPARADOS + BOTÕES DE AÇÃO)
# =========================================================
st.markdown("### 🛡️ 2. Validação de Autenticidade")
c3, c4 = st.columns(2, gap="medium")

# --- LADO ESQUERDO: AUTENTICIDADE ENTRADAS ---
with c3:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown('<span class="card-icon">📋</span><b>Relatório Sefaz (Entradas)</b>', unsafe_allow_html=True)
    
    # 1. Upload específico para Entradas
    file_status_ent = st.file_uploader("Relatório Entradas", type=["xlsx", "csv"], label_visibility="collapsed", key="st_in")
    
    # 2. Botão de Verificar Entradas
    if st.button("🔍 Validar Entradas", type="primary"):
        if xml_ent and file_status_ent:
            df = extrair_xml(xml_ent)
            status = ler_status(file_status_ent)
            if not df.empty:
                df['Status Sefaz'] = df['Chave'].map(status).fillna("Não encontrado")
                st.success("Validado!")
                st.dataframe(df, use_container_width=True, height=200)
        else:
            st.warning("⚠️ Preciso dos XMLs de Entrada (item 1) e do Relatório acima.")
    st.markdown('</div>', unsafe_allow_html=True)


# --- LADO DIREITO: AUTENTICIDADE SAÍDAS ---
with c4:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown('<span class="card-icon">📋</span><b>Relatório Sefaz (Saídas)</b>', unsafe_allow_html=True)
    
    # 1. Upload específico para Saídas
    file_status_sai = st.file_uploader("Relatório Saídas", type=["xlsx", "csv"], label_visibility="collapsed", key="st_out")
    
    # 2. Botão de Verificar Saídas
    if st.button("🔍 Validar Saídas", type="primary"):
        if xml_sai and file_status_sai:
            df = extrair_xml(xml_sai)
            status = ler_status(file_status_sai)
            if not df.empty:
                df['Status Sefaz'] = df['Chave'].map(status).fillna("Não encontrado")
                st.success("Validado!")
                st.dataframe(df, use_container_width=True, height=200)
        else:
            st.warning("⚠️ Preciso dos XMLs de Saída (item 1) e do Relatório acima.")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# =========================================================
# 3. RELATÓRIOS GERENCIAIS
# =========================================================
st.markdown("### 📊 3. Relatórios Gerenciais")
c5, c6 = st.columns(2, gap="medium")

with c5:
    if st.button("📈 Gerar Gerencial Entradas", use_container_width=True):
        if xml_ent:
            st.toast("Gerando Dashboard de Entradas...")
            # Coloque sua lógica gerencial aqui
            st.dataframe(extrair_xml(xml_ent).head()) 
        else:
            st.error("Faltam os XMLs de Entrada.")

with c6:
    if st.button("📈 Gerar Gerencial Saídas", use_container_width=True):
        if xml_sai:
            st.toast("Gerando Dashboard de Saídas...")
            # Coloque sua lógica gerencial aqui
            st.dataframe(extrair_xml(xml_sai).head())
        else:
            st.error("Faltam os XMLs de Saída.")
