@@ -1,208 +1,132 @@
import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
import re
import io
import streamlit as st
import os
import io
import pandas as pd
from datetime import datetime
from motor_fiscal import extrair_dados_xml, gerar_excel_final

def extrair_dados_xml(files, fluxo, df_autenticidade=None):
    dados_lista = []
    if not files: return pd.DataFrame()
    for f in files:
        try:
            f.seek(0)
            conteudo_bruto = f.read()
            texto_xml = conteudo_bruto.decode('utf-8', errors='replace')
            texto_xml = re.sub(r'<\?xml[^?]*\?>', '', texto_xml)
            texto_xml = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', texto_xml)
            root = ET.fromstring(texto_xml)
            def buscar(caminho, raiz=root):
                alvo = raiz.find(f'.//{caminho}')
                return alvo.text if alvo is not None and alvo.text is not None else ""
            inf_nfe = root.find('.//infNFe')
            chave_acesso = inf_nfe.attrib.get('Id', '')[3:] if inf_nfe is not None else ""
            for det in root.findall('.//det'):
                prod = det.find('prod'); imp = det.find('imposto')
                ncm_limpo = re.sub(r'\D', '', buscar('NCM', prod)).zfill(8)
                linha = {
                    "CHAVE_ACESSO": chave_acesso, "NUM_NF": buscar('nNF'),
                    "DATA_EMISSAO": pd.to_datetime(buscar('dhEmi')).replace(tzinfo=None) if buscar('dhEmi') else None,
                    "UF_EMIT": buscar('UF', root.find('.//emit')), "UF_DEST": buscar('UF', root.find('.//dest')),
                    "AC": int(det.attrib.get('nItem', '0')), "CFOP": buscar('CFOP', prod), "NCM": ncm_limpo,
                    "COD_PROD": buscar('cProd', prod), "DESCR": buscar('xProd', prod),
                    "VPROD": float(buscar('vProd', prod)) if buscar('vProd', prod) else 0.0,
                    "CST-ICMS": "", "BC-ICMS": 0.0, "VLR-ICMS": 0.0, "ALQ-ICMS": 0.0, "ICMS-ST": 0.0,
                    "CST-PIS": "", "CST-COF": "", "VAL-PIS": 0.0, "VAL-COF": 0.0, "BC-FED": 0.0,
                    "CST-IPI": "", "VAL-IPI": 0.0, "BC-IPI": 0.0, "ALQ-IPI": 0.0, "VAL-DIFAL": 0.0,
                    "VAL-FCP": 0.0, "VAL-FCPST": 0.0 
                }
                if imp is not None:
                    icms_n = imp.find('.//ICMS')
                    if icms_n is not None:
                        for n in icms_n:
                            cst = n.find('CST') if n.find('CST') is not None else n.find('CSOSN')
                            if cst is not None: linha["CST-ICMS"] = cst.text.zfill(2)
                            if n.find('vBC') is not None: linha["BC-ICMS"] = float(n.find('vBC').text)
                            if n.find('vICMS') is not None: linha["VLR-ICMS"] = float(n.find('vICMS').text)
                            if n.find('pICMS') is not None: linha["ALQ-ICMS"] = float(n.find('pICMS').text)
                            if n.find('vICMSST') is not None: linha["ICMS-ST"] = float(n.find('vICMSST').text)
                            if n.find('vFCP') is not None: linha["VAL-FCP"] = float(n.find('vFCP').text)
                            if n.find('vFCPST') is not None: linha["VAL-FCPST"] = float(n.find('vFCPST').text)
                    pis = imp.find('.//PIS')
                    if pis is not None:
                        for p in pis:
                            if p.find('CST') is not None: linha["CST-PIS"] = p.find('CST').text.zfill(2)
                            if p.find('vBC') is not None: linha["BC-FED"] = float(p.find('vBC').text)
                            if p.find('vPIS') is not None: linha["VAL-PIS"] = float(p.find('vPIS').text)
                    cof = imp.find('.//COFINS')
                    if cof is not None:
                        for c in cof:
                            if c.find('CST') is not None: linha["CST-COF"] = c.find('CST').text.zfill(2)
                            if c.find('vCOFINS') is not None: linha["VAL-COF"] = float(c.find('vCOFINS').text)
                    ipi_n = imp.find('.//IPI')
                    if ipi_n is not None:
                        cst_i = ipi_n.find('.//CST')
                        if cst_i is not None: linha["CST-IPI"] = cst_i.text.zfill(2)
                        if ipi_n.find('.//vBC') is not None: linha["BC-IPI"] = float(ipi_n.find('.//vBC').text)
                        if ipi_n.find('.//pIPI') is not None: linha["ALQ-IPI"] = float(ipi_n.find('.//pIPI').text)
                        if ipi_n.find('.//vIPI') is not None: linha["VAL-IPI"] = float(ipi_n.find('.//vIPI').text)
                    dif_n = imp.find('.//ICMSUFDest')
                    if dif_n is not None:
                        if dif_n.find('vICMSUFDest') is not None: linha["VAL-DIFAL"] = float(dif_n.find('vICMSUFDest').text)
                        if dif_n.find('vFCPUFDest') is not None: linha["VAL-FCP"] += float(dif_n.find('vFCPUFDest').text)
                dados_lista.append(linha)
        except: continue
    return pd.DataFrame(dados_lista)
# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Sentinela", page_icon="🧡", layout="wide")

def gerar_excel_final(df_ent, df_sai, file_ger_ent=None, file_ger_sai=None):
    def limpar_txt(v): return str(v).replace('.0', '').strip()
    def format_brl(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Quicksand', sans-serif; }
    .stApp { background-color: #F7F7F7; }
    h1, h2, h3, h4 { color: #FF6F00 !important; font-weight: 700; }
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        background-color: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    .stButton>button { background-color: #FF6F00; color: white; border-radius: 25px; font-weight: bold; width: 100%; border: none; padding: 12px; }
    .stButton>button:hover { background-color: #E65100; transform: scale(1.02); }
    .stFileUploader { padding: 5px; border: 1px dashed #FF6F00; border-radius: 10px; }
    /* Botão de Limpeza */
    .clear-btn > div > button { 
        background-color: #f8f9fa !important; color: #dc3545 !important; border: 1px solid #dc3545 !important; 
        padding: 5px !important; font-size: 0.8rem !important; height: auto !important; width: auto !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO DE ESTADO PARA LIMPEZA ---
if 'xml_ent_key' not in st.session_state: st.session_state.xml_ent_key = 0
if 'xml_sai_key' not in st.session_state: st.session_state.xml_sai_key = 0

# --- BARRA LATERAL ---
with st.sidebar:
    if os.path.exists(".streamlit/nascel sem fundo.png"):
        st.image(".streamlit/nascel sem fundo.png", use_container_width=True)

    try:
        base_icms = pd.read_excel(".streamlit/Base_ICMS.xlsx")
        base_icms['NCM_KEY'] = base_icms.iloc[:, 0].apply(limpar_txt).str.replace(r'\D', '', regex=True).str.zfill(8)
        base_icms['CST_KEY'] = base_icms.iloc[:, 2].apply(limpar_txt).str.zfill(2)
    except: base_icms = pd.DataFrame()
    try:
        base_pc = pd.read_excel(".streamlit/Base_CST_Pis_Cofins.xlsx")
        base_pc['NCM_KEY'] = base_pc.iloc[:, 0].apply(limpar_txt).str.replace(r'\D', '', regex=True).str.zfill(8)
        base_pc.columns = [c.upper() for c in base_pc.columns]
    except: base_pc = pd.DataFrame()
    st.markdown("---")
    
    with st.expander("📥 **Baixar Gabaritos**", expanded=False):
        df_modelo = pd.DataFrame(columns=['CHAVE', 'STATUS'])
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_modelo.to_excel(writer, index=False)
        st.download_button("📄 Modelo ICMS", buffer.getvalue(), "modelo_icms.xlsx", use_container_width=True)
        st.download_button("📄 Modelo PIS/COFINS", buffer.getvalue(), "modelo_pis_cofins.xlsx", use_container_width=True)

    if df_sai is None: df_sai = pd.DataFrame()
    if df_ent is None: df_ent = pd.DataFrame()
    st.markdown("### ⚙️ Configurações de Base")
    
    with st.expander("🔄 **Atualizar Base ICMS**"):
        up_icms = st.file_uploader("Arquivo ICMS", type=['xlsx'], key='base_i', label_visibility="collapsed")
        if up_icms:
            with open(".streamlit/Base_ICMS.xlsx", "wb") as f: f.write(up_icms.getbuffer())
            st.toast("Base ICMS atualizada!", icon="✅")

    # --- ABA ICMS ---
    df_icms_audit = df_sai.copy(); tem_e = not df_ent.empty
    ncm_st = df_ent[(df_ent['CST-ICMS']=="60") | (df_ent['ICMS-ST'] > 0)]['NCM'].unique().tolist() if tem_e else []
    def audit_icms(row):
        ncm = str(row['NCM']).zfill(8); info = base_icms[base_icms['NCM_KEY'] == ncm] if not base_icms.empty else pd.DataFrame()
        st_e = "✅ ST Localizado" if ncm in ncm_st else "❌ Sem ST na Entrada" if tem_e else "⚠️ Sem Entrada"
        if info.empty: return pd.Series([st_e, "NCM Ausente", format_brl(row['VPROD']), "R$ 0,00", "Cadastrar NCM", "R$ 0,00"])
        cst_e, aliq_e = str(info.iloc[0]['CST_KEY']), float(info.iloc[0, 3]) if row['UF_EMIT'] == row['UF_DEST'] else 12.0
        diag, acao = [], []
        if str(row['CST-ICMS']).zfill(2) != cst_e.zfill(2): diag.append("CST: Divergente"); acao.append(f"Cc-e (CST {cst_e})")
        if abs(row['ALQ-ICMS'] - aliq_e) > 0.01: diag.append("Aliq: Divergente"); acao.append("Ajustar Alíquota")
        return pd.Series([st_e, "; ".join(diag) if diag else "✅ Correto", format_brl(row['VPROD']), format_brl(row['BC-ICMS']*aliq_e/100), " + ".join(acao) if acao else "✅ Correto", format_brl(max(0, (aliq_e-row['ALQ-ICMS'])*row['BC-ICMS']/100))])
    if not df_icms_audit.empty:
        df_icms_audit[['ST na Entrada', 'Diagnóstico', 'ICMS XML', 'ICMS Esperado', 'Ação', 'Complemento']] = df_icms_audit.apply(audit_icms, axis=1)
    with st.expander("🔄 **Atualizar Base PIS/COF**"):
        up_pis = st.file_uploader("Arquivo PIS", type=['xlsx'], key='base_p', label_visibility="collapsed")
        if up_pis:
            with open(".streamlit/Base_CST_Pis_Cofins.xlsx", "wb") as f: f.write(up_pis.getbuffer())
            st.toast("Base PIS/COF atualizada!", icon="✅")

    # --- ABA PIS/COFINS ---
    df_pc = df_sai.copy()
    def audit_pc(row):
        ncm = str(row['NCM']).zfill(8); info = base_pc[base_pc['NCM_KEY'] == ncm] if not base_pc.empty else pd.DataFrame()
        if info.empty: return pd.Series(["NCM não mapeado", f"P/C: {row['CST-PIS']}/{row['CST-COF']}", "-", "Cadastrar NCM"])
        try: cp_e, cc_e = str(info.iloc[0]['CST_PIS']).zfill(2), str(info.iloc[0]['CST_COFINS']).zfill(2)
        except: cp_e, cc_e = "01", "01"
        diag, acao = [], []
        if str(row['CST-PIS']) != cp_e: diag.append("PIS: Divergente"); acao.append(f"Cc-e (CST PIS {cp_e})")
        if str(row['CST-COF']) != cc_e: diag.append("COF: Divergente"); acao.append(f"Cc-e (CST COF {cc_e})")
        return pd.Series(["; ".join(diag) if diag else "✅ Correto", f"P/C: {row['CST-PIS']}/{row['CST-COF']}", f"P/C: {cp_e}/{cc_e}", " + ".join(acao) if acao else "✅ Correto"])
    if not df_pc.empty:
        df_pc[['Diagnóstico', 'CST XML (P/C)', 'CST Esperado (P/C)', 'Ação']] = df_pc.apply(audit_pc, axis=1)
    with st.expander("🔄 **Atualizar Base TIPI**"):
        up_tipi = st.file_uploader("Arquivo TIPI", type=['xlsx'], key='base_t', label_visibility="collapsed")
        if up_tipi:
            with open(".streamlit/Base_IPI_Tipi.xlsx", "wb") as f: f.write(up_tipi.getbuffer())
            st.toast("Base TIPI atualizada!", icon="✅")

    # --- ABA IPI ---
    df_ipi = df_sai.copy()
    def audit_ipi(row):
        ncm = str(row['NCM']).zfill(8); info = base_pc[base_pc['NCM_KEY'] == ncm] if not base_pc.empty else pd.DataFrame()
        if info.empty: return pd.Series(["NCM não mapeado", row['CST-IPI'], "-", format_brl(row['VAL-IPI']), "R$ 0,00", "Cadastrar NCM", "R$ 0,00"])
        try: ci_e, ai_e = str(info.iloc[0]['CST_IPI']).zfill(2), float(info.iloc[0]['ALQ_IPI'])
        except: ci_e, ai_e = "50", 0.0
        v_e = row['BC-IPI'] * (ai_e/100); diag, acao = [] ,[]
        if str(row['CST-IPI']) != ci_e: diag.append("CST: Divergente"); acao.append(f"Cc-e (CST IPI {ci_e})")
        if abs(row['VAL-IPI'] - v_e) > 0.01: diag.append("Valor: Divergente"); acao.append("Complementar" if row['VAL-IPI'] < v_e else "Estornar")
        return pd.Series(["; ".join(diag) if diag else "✅ Correto", row['CST-IPI'], ci_e, format_brl(row['VAL-IPI']), format_brl(v_e), " + ".join(acao) if acao else "✅ Correto", format_brl(max(0, v_e-row['VAL-IPI']))])
    if not df_ipi.empty:
        df_ipi[['Diagnóstico', 'CST XML', 'CST Base', 'IPI XML', 'IPI Esperado', 'Ação', 'Complemento']] = df_ipi.apply(audit_ipi, axis=1)
# --- ÁREA CENTRAL ---
c1, c2, c3 = st.columns([3, 4, 3])
with c2:
    if os.path.exists(".streamlit/Sentinela.png"):
        st.image(".streamlit/Sentinela.png", use_container_width=True)

    # --- ABA DIFAL ---
    df_difal = df_sai.copy()
    def audit_difal(row):
        is_i = row['UF_EMIT'] != row['UF_DEST']; cfop = str(row['CFOP']); diag, acao = [], []
        if is_i:
            if cfop in ['6107', '6108', '6933', '6404']:
                if row['VAL-DIFAL'] == 0: diag.append(f"CFOP {cfop}: DIFAL Obrigatório"); acao.append("Complementar DIFAL")
                else: diag.append("✅ Correto"); acao.append("✅ Correto")
            else: diag.append("✅ Correto"); acao.append("✅ Correto")
        else: diag.append("✅ Correto"); acao.append("✅ Correto")
        return pd.Series(["; ".join(diag), format_brl(row['VAL-DIFAL']), "; ".join(acao)])
    if not df_difal.empty:
        df_difal[['Diagnóstico', 'DIFAL XML', 'Ação']] = df_difal.apply(audit_difal, axis=1)
st.markdown("---")

    # --- ABA ICMS_DESTINO ---
    if not df_sai.empty:
        df_dest = df_sai.groupby('UF_DEST').agg({'ICMS-ST': 'sum', 'VAL-DIFAL': 'sum', 'VAL-FCP': 'sum', 'VAL-FCPST': 'sum'}).reset_index()
        df_dest.columns = ['ESTADO', 'ST', 'DIFAL', 'FCP', 'FCP-ST']
        for col in ['ST', 'DIFAL', 'FCP', 'FCP-ST']: df_dest[col] = df_dest[col].apply(format_brl)
    else: df_dest = pd.DataFrame()
col_ent, col_sai = st.columns(2, gap="large")

    # --- BLOCO GERENCIAIS (BLINDAGEM CONTRA LENGTH MISMATCH) ---
    def load_gerencial_flexible(f, target_cols):
        if not f: return pd.DataFrame()
        try:
            f.seek(0)
            raw = f.read().decode('utf-8-sig', errors='replace')
            sep = ';' if raw.count(';') > raw.count(',') else ','
            df = pd.read_csv(io.StringIO(raw), sep=sep, header=None, engine='python', dtype={0: str})
with col_ent:
    head_e1, head_e2 = st.columns([3, 1])
    with head_e1: st.markdown("### 📥 1. Entradas")
    with head_e2:
        if st.button("🗑️ Limpar", key="btn_clear_ent", help="Excluir todos os XMLs de Entrada"):
            st.session_state.xml_ent_key += 1
            st.rerun()

            if df.shape[0] > 0 and not str(df.iloc[0, 0]).strip().isdigit():
                df = df.iloc[1:]
    xml_ent = st.file_uploader("📂 XMLs de Entrada", type='xml', accept_multiple_files=True, key=f"xml_e_{st.session_state.xml_ent_key}")
    aut_ent = st.file_uploader("🔍 Autenticidade Entrada", type=['xlsx'], key="ae")
    ger_ent = st.file_uploader("📊 Gerenc. Entradas (CSV)", type=['csv'], key="ge")

            # Resolve o erro de "Length mismatch": pega apenas o número de colunas necessário
            num_cols_df = df.shape[1]
            num_cols_target = len(target_cols)
            
            if num_cols_df > num_cols_target:
                df = df.iloc[:, :num_cols_target] # Corta colunas extras
            elif num_cols_df < num_cols_target:
                for i in range(num_cols_target - num_cols_df):
                    df[f'Vazia_{i}'] = "" # Adiciona colunas se faltarem
            
            df.columns = target_cols
            return df
        except Exception as e:
            return pd.DataFrame([{"ERRO": f"Falha na leitura: {str(e)}"}])
with col_sai:
    head_s1, head_s2 = st.columns([3, 1])
    with head_s1: st.markdown("### 📤 2. Saídas")
    with head_s2:
        if st.button("🗑️ Limpar", key="btn_clear_sai", help="Excluir todos os XMLs de Saída"):
            st.session_state.xml_sai_key += 1
            st.rerun()

    c_sai = ['NF','DATA_EMISSAO','CNPJ','Ufp','VC','AC','CFOP','COD_ITEM','VUNIT','QTDE','VITEM','DESC','FRETE','SEG','OUTRAS','VC_ITEM','CST','Coluna2','Coluna3','BC_ICMS','ALIQ_ICMS','ICMS','BC_ICMSST','ICMSST','IPI','CST_PIS','BC_PIS','PIS','CST_COF','BC_COF','COF']
    c_ent = ['NUM_NF','DATA_EMISSAO','CNPJ','UF','VLR_NF','AC','CFOP','COD_PROD','DESCR','NCM','UNID','VUNIT','QTDE','VPROD','DESC','FRETE','SEG','DESP','VC','CST-ICMS','Coluna2','BC-ICMS','VLR-ICMS','BC-ICMS-ST','ICMS-ST','VLR_IPI','CST_PIS','BC_PIS','VLR_PIS','CST_COF','BC_COF','VLR_COF']
    
    df_ge = load_gerencial_flexible(file_ger_ent, c_ent)
    df_gs = load_gerencial_flexible(file_ger_sai, c_sai)
    xml_sai = st.file_uploader("📂 XMLs de Saída", type='xml', accept_multiple_files=True, key=f"xml_s_{st.session_state.xml_sai_key}")
    aut_sai = st.file_uploader("🔍 Autenticidade Saída", type=['xlsx'], key="as")
    ger_sai = st.file_uploader("📊 Gerenc. Saídas (CSV)", type=['csv'], key="gs")

    mem = io.BytesIO()
    with pd.ExcelWriter(mem, engine='xlsxwriter') as wr:
        if not df_ent.empty: df_ent.to_excel(wr, sheet_name='ENTRADAS', index=False)
        if not df_sai.empty: df_sai.to_excel(wr, sheet_name='SAIDAS', index=False)
        if not df_icms_audit.empty: df_icms_audit.to_excel(wr, sheet_name='ICMS', index=False)
        if not df_pc.empty: df_pc.to_excel(wr, sheet_name='PIS_COFINS', index=False)
        if not df_ipi.empty: df_ipi.to_excel(wr, sheet_name='IPI', index=False)
        if not df_difal.empty: df_difal.to_excel(wr, sheet_name='DIFAL', index=False)
        if not df_dest.empty: df_dest.to_excel(wr, sheet_name='ICMS_Destino', index=False)
        if not df_ge.empty: df_ge.to_excel(wr, sheet_name='Gerenc. Entradas', index=False)
        if not df_gs.empty: df_gs.to_excel(wr, sheet_name='Gerenc. Saídas', index=False)
# --- EXECUÇÃO ---
st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 EXECUTAR AUDITORIA", type="primary", use_container_width=True):
    if not xml_ent and not xml_sai:
        st.error("Por favor, carregue os arquivos XML.")
    else:
        try:
            with st.spinner("O Sentinela está processando... 🧡"):
                df_autent_data = None
                arq_aut = aut_sai if aut_sai else aut_ent
                if arq_aut:
                    df_autent_data = pd.read_excel(arq_aut)

        wb = wr.book; f_txt = wb.add_format({'num_format': '@'})
        for s in ['Gerenc. Entradas', 'Gerenc. Saídas']:
            if s in wr.sheets: wr.sheets[s].set_column('A:A', 20, f_txt)
                df_e = extrair_dados_xml(xml_ent, "Entrada", df_autenticidade=df_autent_data)
                df_s = extrair_dados_xml(xml_sai, "Saída", df_autenticidade=df_autent_data)

    return mem.getvalue()
                excel_binario = gerar_excel_final(df_e, df_s, file_ger_ent=ger_ent, file_ger_sai=ger_sai)
                
                if excel_binario:
                    st.success("Análise concluída! 🧡")
                    st.download_button(
                        label="💾 BAIXAR RELATÓRIO",
                        data=excel_binario,
                        file_name="Auditoria_Sentinela_Completa.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
        except Exception as e:
            st.error(f"Erro crítico no processamento: {e}")
