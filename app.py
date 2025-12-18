import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- 1. CONFIGURAÇÃO VISUAL (ORIGINAL) ---
st.set_page_config(
    page_title="Nascel | Auditoria",
    page_icon="🧡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS PERSONALIZADO (RESTABELECIDO)
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
# --- 2. MOTORES DE CÁLCULO (O MECANISMO PERFEITO) ---
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
                    'CST_ICMS_NF': "", 'Aliq_ICMS_NF': 0.0, 'Aliq_IPI_NF': 0.0,
                    'CST_PIS_NF': "", 'CST_COFINS_NF': ""
                }
                # ICMS
                icms = imp.find('.//ICMS')
                if icms is not None:
                    for c in icms:
                        node = c.find('CST') or c.find('CSOSN')
                        if node is not None: row['CST_ICMS_NF'] = node.text
                        if c.find('pICMS') is not None: row['Aliq_ICMS_NF'] = float(c.find('pICMS').text)
                # IPI
                ipi = imp.find('.//IPI')
                if ipi is not None:
                    for i in ipi:
                        if i.find('pIPI') is not None: row['Aliq_IPI_NF'] = float(i.find('pIPI').text)
                # PIS/COFINS
                pis = imp.find('.//PIS')
                if pis is not None:
                    for p in pis:
                        if p.find('CST') is not None: row['CST_PIS_NF'] = p.find('CST').text
                data.append(row)
        except: continue
    return pd.DataFrame(data)

def auditoria_completa(df, b_icms, b_pc, b_tipi):
    if df.empty: return df
    df['NCM_L'] = df['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)

    # 1. AUDITORIA ICMS (Lógica Interna vs Interestadual)
    if b_icms is not None and len(b_icms.columns) >= 7:
        rules_i = b_icms.iloc[:, [0, 2, 6]].copy()
        rules_i.columns = ['NCM_R', 'CST_INT_R', 'CST_EXT_R']
        rules_i['NCM_R'] = rules_i['NCM_R'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(8)
        df = pd.merge(df, rules_i, left_on='NCM_L', right_on='NCM_R', how='left')
        
        def audit_icms(r):
            if pd.isna(r['NCM_R']): return "NCM NÃO CADASTRADO"
            cfop = str(r['CFOP'])
            esp = str(r['CST_INT_R']) if cfop.startswith('5') else str(r['CST_EXT_R'])
            esp = str(esp).split('.')[0].zfill(2)
            return "OK" if str(r['CST_ICMS_NF']).zfill(2) == esp else f"ERRO (Esp: {esp})"
        df['AUDIT_ICMS'] = df.apply(audit_icms, axis=1)

    # 2. AUDITORIA PIS/COFINS
    if b_pc is not None and len(b_pc.columns) >= 3:
        rules_p = b_pc.iloc[:, [0, 1, 2]].copy()
        rules_p.columns = ['NCM_P', 'CST_E_P', 'CST_S_P']
        rules_p['NCM_P'] = rules_p['NCM_P'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(8)
        df = pd.merge(df, rules_p, left_on='NCM_L', right_on='NCM_P', how='left')
        
        def audit_pc(r):
            if pd.isna(r['NCM_P']): return "NCM NÃO CADASTRADO"
            cfop = str(r['CFOP'])
            esp = str(r['CST_E_P']) if cfop[0] in '123' else str(r['CST_S_P'])
            esp = str(esp).split('.')[0].zfill(2)
            return "OK" if str(r['CST_PIS_NF']).zfill(2) == esp else f"ERRO (Esp: {esp})"
        df['AUDIT_PIS_COFINS'] = df.apply(audit_pc, axis=1)

    # 3. AUDITORIA IPI (TIPI)
    if b_tipi is not None:
        b_tipi.columns = ['NCM_T', 'ALIQ_T']
        b_tipi['NCM_T'] = b_tipi['NCM_T'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(8)
        df = pd.merge(df, b_tipi, left_on='NCM_L', right_on='NCM_T', how='left')
        df['AUDIT_IPI'] = df.apply(lambda r: "OK" if pd.isna(r['ALIQ_T']) or abs(r['Aliq_IPI_NF'] - float(r['ALIQ_T'])) < 0.1 else "DIVERGENTE", axis=1)

    return df

# ==============================================================================
# --- 3. SIDEBAR E LAYOUT ORIGINAL ---
# ==============================================================================

with st.sidebar:
    # Logo Nascel
    for l in [".streamlit/nascel sem fundo.png", "nascel sem fundo.png"]:
        if os.path.exists(l): st.image(l); break
    
    st.markdown("---")
    def get_f(n):
        for p in [f".streamlit/{n}", n]:
            if os.path.exists(p): return p
        return None

    st.subheader("📊 Status das Bases")
    p_i = get_f("ICMS.xlsx") or get_f("base_icms.xlsx")
    p_p = get_f("CST_Pis_Cofins.xlsx")
    p_t = get_f("tipi.xlsx")

    st.success("🟢 ICMS OK") if p_i else st.error("🔴 ICMS OFF")
    st.success("🟢 PIS/COF OK") if p_p else st.error("🔴 PIS/COF OFF")
    st.success("🟢 TIPI OK") if p_t else st.error("🔴 TIPI OFF")

    with st.expander("💾 Gestão de Bases"):
        up_i = st.file_uploader("Trocar ICMS", type=['xlsx'], key='ui')
        if up_i:
            with open("ICMS.xlsx", "wb") as f: f.write(up_i.getbuffer())
            st.rerun()

    with st.expander("📂 Gabaritos"):
        df_micms = pd.DataFrame(columns=['NCM','DESC_I','CST_I','AL_I','RE_I','DESC_E','CST_E','AL_E','OBS'])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as w: df_micms.to_excel(w, index=False)
        st.download_button("Gabarito ICMS", buf.getvalue(), "modelo_icms.xlsx")

# --- ÁREA CENTRAL (LAYOUT MANTIDO) ---
for s in [".streamlit/Sentinela.png", "Sentinela.png"]:
    if os.path.exists(s):
        col_l, col_tit, col_r = st.columns([3, 4, 3])
        with col_tit: st.image(s, use_column_width=True); break

st.markdown("---")
col_ent, col_sai = st.columns(2, gap="large")
with col_ent:
    st.markdown("### 📥 1. Entradas")
    ue = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="ue")
    ae = st.file_uploader("🔍 Autenticidade Entradas", type=['xlsx', 'csv'], key="ae")
with col_sai:
    st.markdown("### 2. Saídas")
    us = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="us")
    as_ = st.file_uploader("🔍 Autenticidade Saídas", type=['xlsx', 'csv'], key="as")

st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 EXECUTAR AUDITORIA COMPLETA", type="primary", use_container_width=True):
    if not ue and not us:
        st.warning("Carregue os arquivos.")
    else:
        with st.spinner("Calculando ICMS, IPI, PIS e COFINS..."):
            bi = pd.read_excel(p_i, dtype=str) if p_i else None
            bp = pd.read_excel(p_p, dtype=str) if p_p else None
            bt = pd.read_excel(p_t, dtype=str) if p_t else None
            
            df_total = pd.concat([extrair_dados_xml(ue, "Entrada"), extrair_dados_xml(us, "Saída")], ignore_index=True)
            df_final = auditoria_completa(df_total, bi, bp, bt)
            
            st.success("Análise Finalizada!")
            st.dataframe(df_final, use_container_width=True)
            
            # DOWNLOAD COM TODAS AS ABAS
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, sheet_name='RELATORIO_GERAL', index=False)
                # Cria abas específicas por tributo para facilitar
                if 'AUDIT_ICMS' in df_final:
                    df_final[df_final['AUDIT_ICMS'] != 'OK'].to_excel(writer, sheet_name='ERROS_ICMS', index=False)
                if 'AUDIT_PIS_COFINS' in df_final:
                    df_final[df_final['AUDIT_PIS_COFINS'] != 'OK'].to_excel(writer, sheet_name='ERROS_PIS_COFINS', index=False)
            
            st.download_button("💾 BAIXAR RELATÓRIO COMPLETO (ABAS)", output.getvalue(), "Auditoria_Nascel_Sentinela.xlsx")
