import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- 1. CONFIGURAÇÃO VISUAL (ORIGINAL RESTAURADA) ---
st.set_page_config(
    page_title="Nascel | Auditoria",
    page_icon="🧡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS PERSONALIZADO (MANTIDO CONFORME SUA APROVAÇÃO)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    div.block-container { padding-top: 2rem !important; padding-bottom: 1rem !important; }
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3, h4 { color: #FF6F00 !important; font-weight: 700; }
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        background-color: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    .stFileUploader { padding: 10px; border: 2px dashed #FFCC80; border-radius: 15px; text-align: center; }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 25px; border: none; font-weight: bold; padding: 10px 30px; width: 100%; }
    .stButton>button:hover { background-color: #E65100; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# --- 2. MOTORES DE AUDITORIA (ICMS, PIS, COFINS) ---
# ==============================================================================

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
            if inf is None: continue
            chave = inf.attrib.get('Id', '')[3:]
            for det in root.findall('.//det'):
                prod = det.find('prod')
                imp = det.find('imposto')
                row = {
                    'Fluxo': fluxo, 'Chave': chave, 'Arquivo': f.name,
                    'NCM': prod.find('NCM').text if prod.find('NCM') is not None else "",
                    'CFOP': prod.find('CFOP').text if prod.find('CFOP') is not None else "",
                    'Valor': float(prod.find('vProd').text) if prod.find('vProd') is not None else 0.0,
                    'CST_ICMS_NF': "", 'CST_PIS_NF': "", 'CST_COFINS_NF': ""
                }
                # Captura ICMS
                icms = imp.find('.//ICMS')
                if icms is not None:
                    for c in icms:
                        node = c.find('CST') or c.find('CSOSN')
                        if node is not None: row['CST_ICMS_NF'] = node.text
                # Captura PIS/COFINS
                pis = imp.find('.//PIS')
                if pis is not None:
                    for p in pis:
                        node = p.find('CST')
                        if node is not None: row['CST_PIS_NF'] = node.text
                cof = imp.find('.//COFINS')
                if cof is not None:
                    for c in cof:
                        node = c.find('CST')
                        if node is not None: row['CST_COFINS_NF'] = node.text
                data.append(row)
        except: continue
    return pd.DataFrame(data)

def realizar_auditoria(df, b_icms, b_pc):
    if df.empty: return df
    
    # Normalização de NCM para busca
    df['NCM_L'] = df['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)

    # 1. Auditoria ICMS (Base Rosa A-I)
    if b_icms is not None:
        # Pega NCM(0), CST Interno(2) e CST Externo(6)
        rules_icms = b_icms.iloc[:, [0, 2, 6]].copy()
        rules_icms.columns = ['NCM_R', 'CST_INT_R', 'CST_EXT_R']
        rules_icms['NCM_R'] = rules_icms['NCM_R'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(8)
        df = pd.merge(df, rules_icms, left_on='NCM_L', right_on='NCM_R', how='left')
        
        def validar_icms(r):
            if pd.isna(r['NCM_R']): return "NCM NÃO CADASTRADO"
            esp = str(r['CST_INT_R']) if str(r['CFOP']).startswith('5') else str(r['CST_EXT_R'])
            esp = str(esp).split('.')[0].zfill(2)
            return "OK" if str(r['CST_ICMS_NF']).zfill(2) == esp else f"ERRO (Esp: {esp})"
        df['ANALISE_ICMS'] = df.apply(validar_icms, axis=1)

    # 2. Auditoria PIS/COFINS
    if b_pc is not None:
        rules_pc = b_pc.iloc[:, [0, 1, 2]].copy() # NCM, ENT, SAI
        rules_pc.columns = ['NCM_P', 'CST_E_P', 'CST_S_P']
        rules_pc['NCM_P'] = rules_pc['NCM_P'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(8)
        df = pd.merge(df, rules_pc, left_on='NCM_L', right_on='NCM_P', how='left')
        
        def validar_pc(r):
            if pd.isna(r['NCM_P']): return "NCM NÃO CADASTRADO"
            esp = str(r['CST_E_P']) if str(r['CFOP'])[0] in '123' else str(r['CST_S_P'])
            esp = str(esp).split('.')[0].zfill(2)
            return "OK" if str(r['CST_PIS_NF']).zfill(2) == esp else f"ERRO (Esp: {esp})"
        df['ANALISE_PIS_COFINS'] = df.apply(validar_pc, axis=1)

    return df

# ==============================================================================
# --- 3. INTERFACE (SIDEBAR E ÁREA CENTRAL ORIGINAL) ---
# ==============================================================================

with st.sidebar:
    # Logo Nascel
    logo = ".streamlit/nascel sem fundo.png"
    if os.path.exists(logo): st.image(logo)
    else: st.title("Nascel")
    
    st.markdown("---")
    
    def load_b(name):
        p = f".streamlit/{name}" if os.path.exists(f".streamlit/{name}") else name
        return pd.read_excel(p, dtype=str) if os.path.exists(p) else None

    st.subheader("📊 Status das Bases")
    b_icms = load_b("base_icms.xlsx")
    b_pc = load_b("CST_Pis_Cofins.xlsx")
    
    st.success("🟢 ICMS OK") if b_icms is not None else st.error("🔴 ICMS Ausente")
    st.success("🟢 PIS/COF OK") if b_pc is not None else st.error("🔴 PIS/COF Ausente")

    with st.expander("💾 Gerenciar Bases (Subir/Baixar)"):
        up_i = st.file_uploader("Nova Base ICMS", type='xlsx', key='usi')
        if up_i: 
            with open("base_icms.xlsx", "wb") as f: f.write(up_i.getbuffer())
            st.rerun()
        up_p = st.file_uploader("Nova Base PIS/COF", type='xlsx', key='usp')
        if up_p:
            with open("CST_Pis_Cofins.xlsx", "wb") as f: f.write(up_p.getbuffer())
            st.rerun()

    with st.expander("📂 Gabaritos"):
        df_micms = pd.DataFrame(columns=['NCM','DESC_I','CST_I','AL_I','RE_I','DESC_E','CST_E','AL_E','OBS'])
        buf_i = io.BytesIO()
        with pd.ExcelWriter(buf_i, engine='xlsxwriter') as w: df_micms.to_excel(w, index=False)
        st.download_button("Gabarito ICMS", buf_i.getvalue(), "modelo_icms.xlsx")

# ÁREA CENTRAL
st.markdown("<h1 style='text-align: center; color: #FF6F00;'>SENTINELA</h1>", unsafe_allow_html=True)

col_ent, col_sai = st.columns(2, gap="large")
with col_ent:
    st.markdown("### 📥 1. Entradas")
    xml_e = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="xe")
    aut_e = st.file_uploader("🔍 Autenticidade Entradas", type=['xlsx','csv'], key="ae")
with col_sai:
    st.markdown("### 📤 2. Saídas")
    xml_s = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="xs")
    aut_s = st.file_uploader("🔍 Autenticidade Saídas", type=['xlsx','csv'], key="as")

st.markdown("---")
if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary", use_container_width=True):
    if not xml_e and not xml_s:
        st.warning("Carregue os arquivos XML.")
    else:
        with st.spinner("Realizando análises tributárias..."):
            df_e = extrair_dados_xml(xml_e, "Entrada")
            df_s = extrair_dados_xml(xml_s, "Saída")
            df_total = pd.concat([df_e, df_s], ignore_index=True)
            
            # Realiza Auditoria
            df_final = realizar_auditoria(df_total, b_icms, b_pc)
            
            st.success("Auditoria Finalizada com Sucesso!")
            st.dataframe(df_final, use_container_width=True)
            
            # GERAÇÃO DO EXCEL COM ABAS
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, sheet_name='RELATORIO_GERAL', index=False)
                # Aba de Divergências (Filtra o que não é OK)
                erros = df_final[(df_final.get('ANALISE_ICMS','') != 'OK') | (df_final.get('ANALISE_PIS_COFINS','') != 'OK')]
                erros.to_excel(writer, sheet_name='DIVERGENCIAS', index=False)
            
            st.download_button("💾 BAIXAR PLANILHA COM TODAS AS ABAS", output.getvalue(), "Auditoria_Consolidada.xlsx")
