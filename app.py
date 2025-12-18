import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import os

st.set_page_config(page_title="Sentinela Fiscal Pro", layout="wide")
st.title("🛡️ Sentinela Fiscal: Auditoria Completa")

# --- 1. CARREGAR BASES MESTRE ---
@st.cache_data
def carregar_bases_mestre():
    caminho_mestre = "Sentinela_MIRÃO_Outubro2025.xlsx"
    if os.path.exists(caminho_mestre):
        xls = pd.ExcelFile(caminho_mestre)
        df_gerencial = pd.read_excel(xls, 'Entradas Gerencial', dtype=str)
        df_tribut = pd.read_excel(xls, 'Bases Tribut', dtype=str)
        # Tenta carregar a matriz interestadual na aba Bases Tribut (Colunas AC e AD)
        try:
            df_inter = pd.read_excel(xls, 'Bases Tribut', usecols="AC:AD", dtype=str).dropna()
        except:
            df_inter = pd.DataFrame()
        return df_gerencial, df_tribut, df_inter
    return None, None, None

df_gerencial, df_tribut, df_inter = carregar_bases_mestre()

# --- 2. FUNÇÃO DE EXTRAÇÃO (FORMATO BASE_XML APROVADO) ---
def extrair_tags_completo(xml_content):
    ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
    try:
        root = ET.fromstring(xml_content)
    except: return []
    
    infNFe = root.find('.//nfe:infNFe', ns)
    chave = infNFe.attrib['Id'][3:] if infNFe is not None else ""
    ide = root.find('.//nfe:ide', ns)
    emit = root.find('.//nfe:emit', ns)
    dest = root.find('.//nfe:dest', ns)
    
    itens = []
    for det in root.findall('.//nfe:det', ns):
        prod = det.find('nfe:prod', ns)
        imposto = det.find('nfe:imposto', ns)
        
        registro = {
            "Natureza Operação": ide.find('nfe:natOp', ns).text if ide is not None else "",
            "Número NF": ide.find('nfe:nNF', ns).text if ide is not None else "",
            "Finalidade": ide.find('nfe:finNFe', ns).text if ide is not None else "",
            "UF Emit": emit.find('nfe:enderEmit/nfe:UF', ns).text if emit is not None else "",
            "CNPJ Emit": emit.find('nfe:CNPJ', ns).text if emit is not None else "",
            "UF Dest": dest.find('nfe:enderDest/nfe:UF', ns).text if dest is not None else "",
            "dest.CNPJ": dest.find('nfe:CNPJ', ns).text if dest is not None and dest.find('nfe:CNPJ', ns) is not None else "",
            "nItem": det.attrib['nItem'],
            "Cód Prod": prod.find('nfe:cProd', ns).text if prod is not None else "",
            "Desc Prod": prod.find('nfe:xProd', ns).text if prod is not None else "",
            "NCM": prod.find('nfe:NCM', ns).text if prod is not None else "",
            "CFOP": prod.find('nfe:CFOP', ns).text if prod is not None else "",
            "vProd": float(prod.find('nfe:vProd', ns).text) if prod is not None else 0.0,
            "CST ICMS": imposto.find('.//nfe:CST', ns).text if imposto.find('.//nfe:CST', ns) is not None else "",
            "BC ICMS": float(imposto.find('.//nfe:vBC', ns).text) if imposto.find('.//nfe:vBC', ns) is not None else 0.0,
            "Alq ICMS": float(imposto.find('.//nfe:pICMS', ns).text) if imposto.find('.//nfe:pICMS', ns) is not None else 0.0,
            "ICMS": float(imposto.find('.//nfe:vICMS', ns).text) if imposto.find('.//nfe:vICMS', ns) is not None else 0.0,
            "pRedBC ICMS": float(imposto.find('.//nfe:pRedBC', ns).text) if imposto.find('.//nfe:pRedBC', ns) is not None else 0.0,
            "BC ICMS-ST": float(imposto.find('.//nfe:vBCST', ns).text) if imposto.find('.//nfe:vBCST', ns) is not None else 0.0,
            "ICMS-ST": float(imposto.find('.//nfe:vICMSST', ns).text) if imposto.find('.//nfe:vICMSST', ns) is not None else 0.0,
            "Chave de Acesso": chave
        }
        itens.append(registro)
    return itens

# --- 3. INTERFACE ---
with st.sidebar:
    st.header("📂 Upload de Ficheiros")
    xml_saidas = st.file_uploader("1. Notas de SAÍDA", accept_multiple_files=True, type='xml')
    xml_entradas = st.file_uploader("2. Notas de ENTRADA", accept_multiple_files=True, type='xml')
    rel_status = st.file_uploader("3. Relatório Autenticidade", type=['xlsx', 'csv'])

# --- 4. PROCESSAMENTO ---
if (xml_saidas or xml_entradas) and rel_status:
    # Mapear Status SEFAZ
    df_st_rel = pd.read_excel(rel_status, dtype=str) if rel_status.name.endswith('.xlsx') else pd.read_csv(rel_status, dtype=str)
    status_dict = dict(zip(df_st_rel.iloc[:, 0].str.replace(r'\D', '', regex=True), df_st_rel.iloc[:, 5]))

    # Extrair Dados
    list_s = []
    for f in xml_saidas: list_s.extend(extrair_tags_completo(f.read()))
    df_s = pd.DataFrame(list_s)
    
    list_e = []
    for f in xml_entradas: list_e.extend(extrair_tags_completo(f.read()))
    df_e = pd.DataFrame(list_e)

    if not df_s.empty:
        df_s['AP'] = df_s['Chave de Acesso'].str.replace(r'\D', '', regex=True).map(status_dict).fillna("Pendente")
        
        # --- PREPARAÇÃO PARA AUDITORIA ---
        map_tribut_cst = dict(zip(df_tribut.iloc[:, 0].astype(str), df_tribut.iloc[:, 2].astype(str)))
        map_tribut_aliq = dict(zip(df_tribut.iloc[:, 0].astype(str), df_tribut.iloc[:, 3].astype(str)))
        map_gerencial_cst = dict(zip(df_gerencial.iloc[:, 0].astype(str), df_gerencial.iloc[:, 1].astype(str)))
        map_inter = dict(zip(df_inter.iloc[:, 0].astype(str), df_inter.iloc[:, 1].astype(str)))

        df_icms = df_s.copy()

        # A. Análise CST ICMS (Cruzada)
        def f_analise_cst(row):
            status, cst, ncm = str(row['AP']), str(row['CST ICMS']).strip(), str(row['NCM']).strip()
            if "Cancelamento" in status: return "NF cancelada"
            cst_esp = map_tribut_cst.get(ncm)
            cst_ent = map_gerencial_cst.get(ncm)
            if not cst_esp: return "NCM não encontrado"
            if cst_ent == "60" and cst != "60": return f"Divergente — CST informado: {cst} | Esperado: 60 (Entrada ST)"
            return "Correto" if cst == cst_esp else f"Divergente — CST informado: {cst} | Esperado: {cst_esp}"

        # B. CST x BC (Matemática da Nota)
        def f_cst_bc(row):
            if "Cancelamento" in str(row['AP']): return "NF Cancelada"
            cst, v_p, bc, pred = str(row['CST ICMS']), row['vProd'], row['BC ICMS'], row['pRedBC ICMS']
            bc_st, icms_st = row['BC ICMS-ST'], row['ICMS-ST']
            msgs = []
            if cst == "00" and abs(bc - v_p) > 0.02: msgs.append("Base ICMS diferente do produto")
            if cst == "20":
                if pred == 0: msgs.append("CST 020 sem redução")
                if abs(bc - (v_p * (1 - pred/100))) > 0.02: msgs.append("Base incorreta após redução")
            if cst in ["10", "30", "70"] and (bc_st < 0.01 or icms_st < 0.01): msgs.append("ST não preenchido")
            if cst in ["40", "41", "50"] and (bc > 0 or row['ICMS'] > 0): msgs.append("CST isento com destaque")
            if cst == "60" and (bc_st > 0 or icms_st > 0): msgs.append("CST 060 com ST indevido")
            if cst in ["90", "99"] and row['ICMS'] == 0: msgs.append("CST 090/099 sem destaque")
            return "; ".join(msgs) if msgs else "Correto"

        # C. Analise Aliq ICMS (Interna e Interestadual)
        def f_aliq(row):
            if "Cancelamento" in str(row['AP']): return "NF Cancelada"
            ncm, uf_e, uf_d, aliq_xml = str(row['NCM']), row['UF Emit'], row['UF Dest'], row['Alq ICMS']
            if uf_e == uf_d:
                esp = map_tribut_aliq.get(ncm)
                if not esp: return "NCM não encontrado na base interna"
            else:
                esp = map_inter.get(uf_d)
                if not esp: return "Destino não encontrado na base interestadual"
            
            esp_val = float(str(esp).replace(',', '.'))
            return "Correto" if abs(aliq_xml - esp_val) < 0.1 else f"Destacado: {aliq_xml} | Esperado: {esp_val}"

        # D. Complemento ICMS Próprio (Cálculo Financeiro)
        def f_complemento(row):
            analise = str(row['Analise Aliq ICMS'])
            if "Destacado" in analise:
                try:
                    # Extrai os valores da string de erro usando regex
                    dest = float(re.search(r'Destacado: ([\d.]+)', analise).group(1))
                    esp = float(re.search(r'Esperado: ([\d.]+)', analise).group(1))
                    if dest < esp:
                        return (esp - dest) * (row['BC ICMS'] / 100)
                except: return 0.0
            return 0.0

        # Aplicar Funções
        df_icms['Análise CST ICMS'] = df_icms.apply(f_analise_cst, axis=1)
        df_icms['CST x BC'] = df_icms.apply(f_cst_bc, axis=1)
        df_icms['Analise Aliq ICMS'] = df_icms.apply(f_aliq, axis=1)
        df_icms['Complemento ICMS Próprio'] = df_icms.apply(f_complemento, axis=1)

    # --- EXPORTAR ---
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        if not df_e.empty: df_e.to_excel(writer, index=False, sheet_name='Entradas')
        if not df_s.empty: df_s.to_excel(writer, index=False, sheet_name='Saídas')
        if not df_s.empty: df_icms.to_excel(writer, index=False, sheet_name='ICMS')

    st.success("✅ Auditoria Concluída!")
    st.download_button("📥 Baixar Planilha Sentinela", buffer.getvalue(), "Sentinela_Auditada_Final.xlsx")
