import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re
import os

# --- 1. CONFIGURAÇÃO VISUAL PREMIUM (ESTILO NASCE) ---
st.set_page_config(
    page_title="Nasce | Sentinela Fiscal",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Personalizado para o visual "Aprovado"
st.markdown("""
    <style>
    /* Fundo geral mais limpo */
    .stApp {
        background-color: #f4f6f9;
    }
    /* Cards de métricas brancos com sombra suave */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e1e4e8;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    /* Títulos com cor corporativa */
    h1, h2, h3 {
        color: #2c3e50;
        font-family: 'Segoe UI', sans-serif;
    }
    /* Sidebar mais profissional */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #ddd;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. CABEÇALHO E SIDEBAR ---
with st.sidebar:
    # Espaço para Logo
    st.markdown("## 🦅 NASCE")
    st.caption("Inteligência e Auditoria Fiscal")
    
    st.markdown("---")
    st.header("🎛️ Painel de Controle")

    # --- OS 6 BOTÕES DE UPLOAD (COM CHAVES ÚNICAS CORRIGIDAS) ---
    
    with st.expander("📥 1. ENTRADAS", expanded=True):
        st.markdown("**Arquivos Obrigatórios:**")
        up_ent_xml = st.file_uploader("XMLs de Entrada", type='xml', accept_multiple_files=True, key="ent_xml")
        up_ent_aut = st.file_uploader("Autenticidade (Sefaz)", type=['xlsx', 'csv'], key="ent_aut")
        up_ent_ger = st.file_uploader("Gerencial (Regras)", type=['xlsx'], key="ent_ger")

    with st.expander("📤 2. SAÍDAS", expanded=True):
        st.markdown("**Arquivos Obrigatórios:**")
        up_sai_xml = st.file_uploader("XMLs de Saída", type='xml', accept_multiple_files=True, key="sai_xml")
        up_sai_aut = st.file_uploader("Autenticidade (Sefaz)", type=['xlsx', 'csv'], key="sai_aut")
        up_sai_ger = st.file_uploader("Gerencial (Regras)", type=['xlsx'], key="sai_ger")

    st.info("💡 O sistema cruza automaticamente os XMLs com o status da Sefaz.")

# --- 3. CARREGAR BASES DO SISTEMA (AUTO) ---
@st.cache_data
def carregar_bases_sistema():
    bases = {"TIPI": {}, "PIS_COFINS": {}}
    # Tenta carregar TIPI
    if os.path.exists("TIPI.xlsx"):
        try:
            df = pd.read_excel("TIPI.xlsx", dtype=str)
            df['NCM'] = df.iloc[:, 0].str.replace(r'\D', '', regex=True)
            df['ALIQ'] = df.iloc[:, 1].str.replace(',', '.')
            bases["TIPI"] = dict(zip(df['NCM'], df['ALIQ']))
        except: pass
    # Tenta carregar PIS/COFINS
    if os.path.exists("Pis_Cofins.xlsx"):
        try:
            df = pd.read_excel("Pis_Cofins.xlsx", dtype=str)
            df['NCM'] = df.iloc[:, 0].str.replace(r'\D', '', regex=True)
            bases["PIS_COFINS"] = dict(zip(df['NCM'], df.iloc[:, 2]))
        except: pass
    return bases

bases_sistema = carregar_bases_sistema()

# --- 4. ENGINE DE PROCESSAMENTO ---
def extrair_xml(arquivos, origem):
    dados = []
    for arq in arquivos:
        try:
            # Leitura segura
            raw = arq.read()
            try: xml = raw.decode('utf-8')
            except: xml = raw.decode('latin-1')
            
            # Limpeza
            xml = re.sub(r' xmlns="[^"]+"', '', xml)
            xml = re.sub(r' xmlns:xsi="[^"]+"', '', xml)
            root = ET.fromstring(xml)
            
            # Filtros
            if "resNFe" in root.tag or "procEvento" in root.tag: continue
            inf = root.find('.//infNFe')
            if inf is None: continue
            
            chave = inf.attrib.get('Id', '')[3:]
            emit = root.find('.//emit/xNome').text if root.find('.//emit/xNome') is not None else ""
            nat_op = root.find('.//ide/natOp').text if root.find('.//ide/natOp') is not None else ""
            
            dets = root.findall('.//det')
            for det in dets:
                prod = det.find('prod')
                imposto = det.find('imposto')
                
                # Helper
                def val(node, tag, is_float=False):
                    if node is None: return 0.0 if is_float else ""
                    x = node.find(tag)
                    if x is not None and x.text:
                        return float(x.text) if is_float else x.text
                    return 0.0 if is_float else ""

                item = {
                    "Origem": origem,
                    "Arquivo": arq.name,
                    "Chave": chave,
                    "Emitente": emit,
                    "Natureza": nat_op,
                    "NItem": det.attrib.get('nItem'),
                    "NCM": val(prod, 'NCM'),
                    "CFOP": val(prod, 'CFOP'),
                    "Valor Prod": val(prod, 'vProd', True),
                    "CST ICMS": "", "Aliq ICMS": 0.0,
                    "CST IPI": "", "Aliq IPI": 0.0,
                    "CST PIS": "", "CST COFINS": ""
                }
                
                if imposto:
                    # ICMS
                    icms = imposto.find('ICMS')
                    if icms:
                        for c in icms:
                            if c.find('CST') is not None: item['CST ICMS'] = c.find('CST').text
                            elif c.find('CSOSN') is not None: item['CST ICMS'] = c.find('CSOSN').text
                            if c.find('pICMS') is not None: item['Aliq ICMS'] = float(c.find('pICMS').text)
                    # IPI
                    ipi = imposto.find('IPI')
                    if ipi:
                        for c in ipi:
                            if c.find('CST') is not None: item['CST IPI'] = c.find('CST').text
                            if c.find('pIPI') is not None: item['Aliq IPI'] = float(c.find('pIPI').text)
                    # PIS/COF
                    pis = imposto.find('PIS')
                    if pis:
                        for c in pis: 
                            if c.find('CST') is not None: item['CST PIS'] = c.find('CST').text
                    cof = imposto.find('COFINS')
                    if cof:
                        for c in cof: 
                            if c.find('CST') is not None: item['CST COFINS'] = c.find('CST').text
                
                dados.append(item)
        except: pass
    return pd.DataFrame(dados)

# --- 5. LOGICA DE ANÁLISE ---
def aplicar_analises(df, status_file):
    if df.empty: return df
    
    # 1. Autenticidade (Sefaz)
    if status_file:
        try:
            if status_file.name.endswith('xlsx'): df_st = pd.read_excel(status_file, dtype=str)
            else: df_st = pd.read_csv(status_file, dtype=str)
            # Dicionario Chave -> Status
            status_map = dict(zip(df_st.iloc[:, 0].str.replace(r'\D', '', regex=True), df_st.iloc[:, -1]))
            df['Status Sefaz'] = df['Chave'].map(status_map).fillna("Não Localizado")
        except:
            df['Status Sefaz'] = "Erro na Leitura do Status"
    else:
        df['Status Sefaz'] = "Arquivo não enviado"

    # 2. Auditoria Tributária (Bases Sistema)
    # IPI
    if bases_sistema["TIPI"]:
        def check_ipi(row):
            ncm = str(row['NCM'])
            aliq_xml = row['Aliq IPI']
            aliq_tipi = bases_sistema["TIPI"].get(ncm)
            if aliq_tipi is None: return "NCM fora da TIPI"
            if aliq_tipi == "NT": return "OK (NT)"
            try:
                if abs(aliq_xml - float(aliq_tipi)) > 0.1: return f"Divergente (XML: {aliq_xml}% | TIPI: {aliq_tipi}%)"
                return "OK"
            except: return "Erro"
        df['Auditoria IPI'] = df.apply(check_ipi, axis=1)

    # PIS COFINS
    if bases_sistema["PIS_COFINS"]:
        def check_pc(row):
            ncm = str(row['NCM'])
            cst_xml = str(row['CST PIS'])
            cst_esp = bases_sistema["PIS_COFINS"].get(ncm)
            if not cst_esp: return "Sem Base"
            if cst_xml != cst_esp: return f"Div: {cst_xml} | Esp: {cst_esp}"
            return "OK"
        df['Auditoria PIS/COF'] = df.apply(check_pc, axis=1)
        
    return df

# Execução
df_ent = extrair_xml(up_ent_xml, "Entrada") if up_ent_xml else pd.DataFrame()
df_ent_final = aplicar_analises(df_ent, up_ent_aut)

df_sai = extrair_xml(up_sai_xml, "Saída") if up_sai_xml else pd.DataFrame()
df_sai_final = aplicar_analises(df_sai, up_sai_aut)

# --- 6. DASHBOARD VISUAL ---

st.title("🛡️ Sentinela Fiscal")
st.markdown("### Auditoria Inteligente e Validação de Autenticidade")

if df_ent_final.empty and df_sai_final.empty:
    st.info("👋 Olá! Use a barra lateral para carregar seus arquivos XML e Tabelas de Autenticidade.")

else:
    # ABAS
    tab1, tab2, tab3 = st.tabs(["📊 Visão Gerencial", "📥 Entradas Detalhadas", "📤 Saídas Detalhadas"])
    
    with tab1:
        st.subheader("Resumo da Operação")
        c1, c2, c3, c4 = st.columns(4)
        
        # Cálculos de Erros
        err_ent = 0
        if not df_ent_final.empty and 'Status Sefaz' in df_ent_final.columns:
            err_ent = len(df_ent_final[~df_ent_final['Status Sefaz'].str.contains("Autoriz|OK", na=False, case=False)])
        
        err_sai = 0
        if not df_sai_final.empty and 'Status Sefaz' in df_sai_final.columns:
            err_sai = len(df_sai_final[~df_sai_final['Status Sefaz'].str.contains("Autoriz|OK", na=False, case=False)])
        
        c1.metric("Total de Notas", len(df_ent_final) + len(df_sai_final))
        c2.metric("Entradas", len(df_ent_final))
        c3.metric("Saídas", len(df_sai_final))
        c4.metric("Alertas de Autenticidade", err_ent + err_sai, delta_color="inverse")
        
        st.markdown("---")
        g1, g2 = st.columns(2)
        
        if not df_ent_final.empty and 'Status Sefaz' in df_ent_final.columns:
            with g1:
                st.markdown("**Status Entradas**")
                st.bar_chart(df_ent_final['Status Sefaz'].value_counts())

        if not df_sai_final.empty and 'Status Sefaz' in df_sai_final.columns:
            with g2:
                st.markdown("**Status Saídas**")
                st.bar_chart(df_sai_final['Status Sefaz'].value_counts())

    with tab2:
        st.subheader("📥 Detalhamento de Entradas")
        if not df_ent_final.empty:
            st.dataframe(df_ent_final, use_container_width=True)
        else:
            st.warning("Nenhum dado de entrada processado.")

    with tab3:
        st.subheader("📤 Detalhamento de Saídas")
        if not df_sai_final.empty:
            st.dataframe(df_sai_final, use_container_width=True)
        else:
            st.warning("Nenhum dado de saída processado.")

    # --- 7. EXPORTAÇÃO ---
    st.markdown("---")
    if st.button("💾 Baixar Relatório Completo (Excel)"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            if not df_ent_final.empty: 
                df_ent_final.to_excel(writer, index=False, sheet_name='Entradas')
            if not df_sai_final.empty: 
                df_sai_final.to_excel(writer, index=False, sheet_name='Saídas')
                
        st.download_button(
            label="📥 Clique para Download",
            data=buffer.getvalue(),
            file_name="Relatorio_Sentinela_Nasce.xlsx",
            mime="application/vnd.ms-excel"
        )
