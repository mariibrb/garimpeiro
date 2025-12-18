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
    initial_sidebar_state="collapsed"
)

# CSS PERSONALIZADO
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
    div[data-testid="metric-container"] { border-left: 5px solid #FF6F00; background-color: #FFF3E0; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# --- 2. SIDEBAR: O CENTRO DE COMANDO DAS BASES ---
# ==============================================================================
with st.sidebar:
    caminho_logo = ".streamlit/nascel sem fundo.png"
    if os.path.exists(caminho_logo): st.image(caminho_logo, use_column_width=True)
    elif os.path.exists("nascel sem fundo.png"): st.image("nascel sem fundo.png", use_column_width=True)
    else: st.markdown("<h1 style='color:#FF6F00; text-align:center;'>Nascel</h1>", unsafe_allow_html=True)
    
    st.markdown("---")

    # --- A. BAIXAR O QUE JÁ EXISTE (Para não perder dados) ---
    with st.expander("⬇️ 1. BAIXAR BASES ATUAIS", expanded=True):
        st.caption("Baixe a planilha que já está no sistema para adicionar novos itens.")
        
        # Função para achar arquivo
        def get_file(name):
            paths = [f".streamlit/{name}", name]
            for p in paths:
                if os.path.exists(p): return p
            return None

        # Botão ICMS
        f_icms = get_file("base_icms.xlsx")
        if f_icms:
            with open(f_icms, "rb") as f:
                st.download_button("📥 Baixar ICMS Atual", f, "base_icms_ATUAL.xlsx")
        else:
            st.warning("Sem base ICMS.")

        # Botão TIPI
        f_tipi = get_file("tipi.xlsx")
        if f_tipi:
            with open(f_tipi, "rb") as f:
                st.download_button("📥 Baixar TIPI Atual", f, "tipi_ATUAL.xlsx")
        else:
            st.warning("Sem base TIPI.")

        # Botão PIS/COFINS
        f_pc = get_file("CST_Pis_Cofins.xlsx")
        if f_pc:
            with open(f_pc, "rb") as f:
                st.download_button("📥 Baixar PIS/COF Atual", f, "pis_cofins_ATUAL.xlsx")
        else:
            st.warning("Sem base PIS/COF.")

    # --- B. SUBIR ATUALIZAÇÃO (Sobrescreve) ---
    with st.expander("⬆️ 2. SUBIR BASES ATUALIZADAS"):
        st.caption("Suba a planilha editada aqui.")
        
        up_icms = st.file_uploader("Nova Base ICMS", type=['xlsx'], key='up_icms')
        if up_icms:
            with open(".streamlit/base_icms.xlsx", "wb") as f: f.write(up_icms.getbuffer())
            st.success("Salvo!")

        up_tipi = st.file_uploader("Nova TIPI", type=['xlsx'], key='up_tipi')
        if up_tipi:
            with open(".streamlit/tipi.xlsx", "wb") as f: f.write(up_tipi.getbuffer())
            st.success("Salvo!")
            
        up_pc = st.file_uploader("Nova PIS/COF", type=['xlsx'], key='up_pc')
        if up_pc:
            with open(".streamlit/CST_Pis_Cofins.xlsx", "wb") as f: f.write(up_pc.getbuffer())
            st.success("Salvo!")

# --- 3. TÍTULO PRINCIPAL ---
caminho_titulo = ".streamlit/Sentinela.png"
if os.path.exists(caminho_titulo):
    col_c1, col_tit, col_c2 = st.columns([3, 4, 3])
    with col_tit: st.image(caminho_titulo, use_column_width=True)
elif os.path.exists("Sentinela.png"):
    col_c1, col_tit, col_c2 = st.columns([3, 4, 3])
    with col_tit: st.image("Sentinela.png", use_column_width=True)
else:
    st.markdown("<h1 style='text-align: center; color: #FF6F00; margin-bottom:0;'>SENTINELA</h1>", unsafe_allow_html=True)

# --- 4. GABARITOS (Para começar do zero) ---
with st.expander("📂 Não tem bases ainda? Baixe Modelos em Branco"):
    c1, c2, c3 = st.columns(3)
    with c1:
        df_m = pd.DataFrame({'NCM': ['00000000'], 'CST': ['00'], 'ALIQ': [18.0]})
        b = io.BytesIO(); 
        with pd.ExcelWriter(b, engine='xlsxwriter') as w: df_m.to_excel(w, index=False)
        st.download_button("Modelo ICMS", b.getvalue(), "modelo_icms.xlsx")
    with c2:
        df_m = pd.DataFrame({'NCM': ['00000000'], 'ALIQ': [0.0]})
        b = io.BytesIO(); 
        with pd.ExcelWriter(b, engine='xlsxwriter') as w: df_m.to_excel(w, index=False)
        st.download_button("Modelo TIPI", b.getvalue(), "modelo_tipi.xlsx")
    with c3:
        df_m = pd.DataFrame({'NCM': ['00000000'], 'CST_ENT': ['50'], 'CST_SAI': ['01']})
        b = io.BytesIO(); 
        with pd.ExcelWriter(b, engine='xlsxwriter') as w: df_m.to_excel(w, index=False)
        st.download_button("Modelo PIS/COF", b.getvalue(), "modelo_pc.xlsx")

# --- 5. UPLOADS XML ---
st.markdown("---")
col_ent, col_sai = st.columns(2, gap="large")
with col_ent:
    st.markdown("### 📥 1. Entradas")
    st.markdown("---")
    up_ent_xml = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="ent_xml")
    up_ent_aut = st.file_uploader("🔍 Sefaz", type=['xlsx', 'csv'], key="ent_aut")
with col_sai:
    st.markdown("### 📤 2. Saídas")
    st.markdown("---")
    up_sai_xml = st.file_uploader("📂 XMLs", type='xml', accept_multiple_files=True, key="sai_xml")
    up_sai_aut = st.file_uploader("🔍 Sefaz", type=['xlsx', 'csv'], key="sai_aut")

# ==============================================================================
# --- 6. LÓGICA DO SISTEMA ---
# ==============================================================================

@st.cache_data(ttl=5)
def carregar_bases():
    icms, tipi, pc = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    def ler(nome, cols_renomear):
        ps = [f".streamlit/{nome}", nome, f".streamlit/{nome.lower()}", nome.lower()]
        for p in ps:
            if os.path.exists(p):
                try:
                    df = pd.read_excel(p, dtype=str)
                    # Pega colunas pelo indice para evitar erro de nome
                    df = df.iloc[:, list(range(len(cols_renomear)))]
                    df.columns = cols_renomear
                    # Tratamento NCM
                    df['NCM'] = df['NCM'].str.replace(r'\D', '', regex=True).str.zfill(8)
                    # Tratamento Aliquota (se tiver)
                    if 'ALIQ' in df.columns:
                        df['ALIQ'] = df['ALIQ'].str.replace('NT','0').str.replace(',','.').astype(float)
                    return df
                except: pass
        return pd.DataFrame()

    icms = ler("base_icms.xlsx", ['NCM', 'CST', 'ALIQ'])
    tipi = ler("tipi.xlsx", ['NCM', 'ALIQ'])
    pc = ler("CST_Pis_Cofins.xlsx", ['NCM', 'CST_ENT', 'CST_SAI'])
    
    return icms, tipi, pc

df_icms, df_tipi, df_pc = carregar_bases()

# Dicionários
bases = {"ICMS": {}, "TIPI": {}, "PC": {}}
if not df_icms.empty: bases["ICMS"] = df_icms.set_index('NCM').to_dict('index')
if not df_tipi.empty: bases["TIPI"] = dict(zip(df_tipi['NCM'], df_tipi['ALIQ']))
if not df_pc.empty: bases["PC"] = dict(zip(df_pc['NCM'], df_pc['CST_SAI']))

# --- EXTRAÇÃO ---
def extrair(files, origem):
    data, erro = [], []
    for f in files:
        try:
            raw = f.read()
            try: txt = raw.decode('utf-8')
            except: txt = raw.decode('latin-1')
            root = ET.fromstring(re.sub(r' xmlns="[^"]+"', '', txt))
            
            if 'resNFe' in root.tag: continue
            inf = root.find('.//infNFe')
            if not inf: continue
            
            chave = inf.attrib.get('Id','')[3:]
            
            for det in root.findall('.//det'):
                prod = det.find('prod')
                imp = det.find('imposto')
                
                def v(n, t, fl=False):
                    if n is None: return 0.0 if fl else ""
                    x = n.find(t)
                    return (float(x.text) if fl else x.text) if x else (0.0 if fl else "")

                row = {
                    "Origem": origem, "Arquivo": f.name, "Chave": chave,
                    "NCM": v(prod, 'NCM'), "Descricao": v(prod, 'xProd'), 
                    "Valor": v(prod, 'vProd', True), "CFOP": v(prod, 'CFOP'),
                    "CST_ICMS": "", "Aliq_ICMS": 0.0, "Aliq_IPI": 0.0, 
                    "CST_PIS": "", "CST_COFINS": ""
                }
                
                if imp:
                    # ICMS
                    icms = imp.find('ICMS')
                    if icms:
                        for c in icms:
                            if c.find('CST') is not None: row['CST_ICMS'] = c.find('CST').text
                            elif c.find('CSOSN') is not None: row['CST_ICMS'] = c.find('CSOSN').text
                            if c.find('pICMS') is not None: row['Aliq_ICMS'] = float(c.find('pICMS').text)
                    # IPI
                    ipi = imp.find('IPI')
                    if ipi:
                        for c in ipi:
                            if c.find('pIPI') is not None: row['Aliq_IPI'] = float(c.find('pIPI').text)
                    # PIS/COF
                    pis = imp.find('PIS')
                    if pis: 
                        for c in pis: 
                             if c.find('CST') is not None: row['CST_PIS'] = c.find('CST').text
                    cof = imp.find('COFINS')
                    if cof: 
                        for c in cof: 
                             if c.find('CST') is not None: row['CST_COFINS'] = c.find('CST').text
                
                data.append(row)
        except: erro.append(f.name)
    return pd.DataFrame(data), erro

# --- AUDITORIAS ---
def audit(df):
    if df.empty: return df
    
    # Sefaz (Placeholder se não tiver arquivo)
    df['Status_Sefaz'] = "N/A"
    
    # IPI
    if bases["TIPI"]:
        def chk_ipi(r):
            esp = bases["TIPI"].get(str(r['NCM']))
            if not esp: return "NCM Off"
            if str(esp) == '0.0': return "OK"
            return "OK" if abs(r['Aliq_IPI'] - float(esp)) < 0.1 else "Divergente"
        df['Audit_IPI'] = df.apply(chk_ipi, axis=1)
        
    # ICMS
    if bases["ICMS"]:
        def chk_icms(r):
            regra = bases["ICMS"].get(str(r['NCM']))
            if not regra: return "Sem Base"
            err = []
            if str(r['CST_ICMS']) != str(regra['CST']): err.append(f"CST {r['CST_ICMS']}!={regra['CST']}")
            if abs(r['Aliq_ICMS'] - float(regra['ALIQ'])) > 0.1: err.append(f"Aliq {r['Aliq_ICMS']}!={regra['ALIQ']}")
            return " | ".join(err) if err else "OK"
        df['Audit_ICMS'] = df.apply(chk_icms, axis=1)
        
    return df

# --- STATUS SEFAZ ---
def cruzamento_sefaz(df, file):
    if df.empty or not file: return df
    try:
        if file.name.endswith('xlsx'): s = pd.read_excel(file, dtype=str)
        else: s = pd.read_csv(file, dtype=str)
        m = dict(zip(s.iloc[:,0].str.replace(r'\D','',regex=True), s.iloc[:,-1]))
        df['Status_Sefaz'] = df['Chave'].map(m).fillna("Não Localizado")
    except: pass
    return df

# --- EXECUÇÃO ---
df_e, _ = extrair(up_ent_xml, "Entrada")
df_e = cruzamento_sefaz(df_e, up_ent_aut)

df_s, _ = extrair(up_sai_xml, "Saída")
df_s = cruzamento_sefaz(df_s, up_sai_aut)
df_s = audit(df_s)

st.markdown("---")

if df_e.empty and df_s.empty:
    st.info("👆 Carregue arquivos para começar.")
else:
    t1, t2, t3 = st.tabs(["Resumo", "Entradas", "Saídas"])
    with t1:
        c1, c2, c3 = st.columns(3)
        c1.metric("Notas", len(df_e)+len(df_s))
        
        err_icms = len(df_s[df_s['Audit_ICMS'].str.contains('CST|Aliq', na=False)]) if 'Audit_ICMS' in df_s else 0
        c2.metric("Erros ICMS", err_icms)
        
        sem_base = len(df_s[df_s['Audit_ICMS'] == 'Sem Base']) if 'Audit_ICMS' in df_s else 0
        c3.metric("Sem Cadastro ICMS", sem_base)
        
    with t2: st.dataframe(df_e)
    with t3: st.dataframe(df_s)

    # --- INTELIGÊNCIA (SUGESTÃO) ---
    st.markdown("---")
    st.subheader("🧠 Sugestões para Atualização")
    
    all_ncm = pd.concat([df_e['NCM'] if not df_e.empty else pd.Series(), df_s['NCM'] if not df_s.empty else pd.Series()]).unique()
    
    # Novos ICMS
    novos = [n for n in all_ncm if n not in bases["ICMS"]]
    if novos:
        st.warning(f"Existem {len(novos)} produtos novos. Baixe a planilha, preencha e suba em 'Atualizar Bases'.")
        df_new = pd.DataFrame({'NCM': novos, 'CST': '', 'ALIQ': ''})
        b = io.BytesIO()
        with pd.ExcelWriter(b, engine='xlsxwriter') as w: df_new.to_excel(w, index=False)
        st.download_button("🧠 Baixar Novos Itens para ICMS", b.getvalue(), "novos_icms.xlsx")
    else:
        st.success("Base de ICMS completa!")

    # --- DOWNLOAD FINAL ---
    st.markdown("<br>", unsafe_allow_html=True)
    b = io.BytesIO()
    with pd.ExcelWriter(b, engine='xlsxwriter') as w:
        if not df_e.empty: df_e.to_excel(w, sheet_name='Ent', index=False)
        if not df_s.empty: df_s.to_excel(w, sheet_name='Sai', index=False)
    st.download_button("💾 BAIXAR RELATÓRIO", b.getvalue(), "Relatorio.xlsx")
