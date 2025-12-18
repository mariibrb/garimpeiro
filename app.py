import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import re

st.set_page_config(page_title="Sentinela - Auditoria AP", layout="wide")
st.title("🛡️ Sentinela: Extração + Auditoria AP (Posição A e F)")

# --- 1. FUNÇÃO DE EXTRAÇÃO ---
def extrair_tags_estilo_query(xml_content):
    ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
    try:
        root = ET.fromstring(xml_content)
    except Exception:
        return []

    infNFe = root.find('.//nfe:infNFe', ns)
    chave = infNFe.attrib['Id'][3:] if infNFe is not None else ""
    ide = root.find('.//nfe:ide', ns)
    emit = root.find('.//nfe:emit', ns)
    dest = root.find('.//nfe:dest', ns)

    itens_extraidos = []
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
            "dest.CPF": dest.find('nfe:CPF', ns).text if dest is not None and dest.find('nfe:CPF', ns) is not None else "",
            "dest.CNPJ": dest.find('nfe:CNPJ', ns).text if dest is not None and dest.find('nfe:CNPJ', ns) is not None else "",
            "dest.IE": dest.find('nfe:IE', ns).text if dest is not None and dest.find('nfe:IE', ns) is not None else "",
            "nItem": det.attrib['nItem'],
            "Cód Prod": prod.find('nfe:cProd', ns).text if prod is not None else "",
            "Desc Prod": prod.find('nfe:xProd', ns).text if prod is not None else "",
            "NCM": prod.find('nfe:NCM', ns).text if prod is not None else "",
            "CEST": prod.find('nfe:CEST', ns).text if prod is not None and prod.find('nfe:CEST', ns) is not None else "",
            "CFOP": prod.find('nfe:CFOP', ns).text if prod is not None else "",
            "vProd": float(prod.find('nfe:vProd', ns).text) if prod is not None else 0.0,
            "vDesc": float(prod.find('nfe:vDesc', ns).text) if prod is not None and prod.find('nfe:vDesc', ns) is not None else 0.0,
            "Origem": imposto.find('.//nfe:orig', ns).text if imposto.find('.//nfe:orig', ns) is not None else "",
            "CST ICMS": imposto.find('.//nfe:CST', ns).text if imposto.find('.//nfe:CST', ns) is not None else "",
            "BC ICMS": float(imposto.find('.//nfe:vBC', ns).text) if imposto.find('.//nfe:vBC', ns) is not None else 0.0,
            "Alq ICMS": float(imposto.find('.//nfe:pICMS', ns).text) if imposto.find('.//nfe:pICMS', ns) is not None else 0.0,
            "ICMS": float(imposto.find('.//nfe:vICMS', ns).text) if imposto.find('.//nfe:vICMS', ns) is not None else 0.0,
            "pRedBC ICMS": float(imposto.find('.//nfe:pRedBC', ns).text) if imposto.find('.//nfe:pRedBC', ns) is not None else 0.0,
            "BC ICMS-ST": float(imposto.find('.//nfe:vBCST', ns).text) if imposto.find('.//nfe:vBCST', ns) is not None else 0.0,
            "ICMS-ST": float(imposto.find('.//nfe:vICMSST', ns).text) if imposto.find('.//nfe:vICMSST', ns) is not None else 0.0,
            "FCPST": float(imposto.find('.//nfe:vFCPST', ns).text) if imposto.find('.//nfe:vFCPST', ns) is not None else 0.0,
            "CST IPI": imposto.find('.//nfe:IPI//nfe:CST', ns).text if imposto.find('.//nfe:IPI//nfe:CST', ns) is not None else "",
            "BC IPI": float(imposto.find('.//nfe:IPI//nfe:vBC', ns).text) if imposto.find('.//nfe:IPI//nfe:vBC', ns) is not None else 0.0,
            "Aliq IPI": float(imposto.find('.//nfe:IPI//nfe:pIPI', ns).text) if imposto.find('.//nfe:IPI//nfe:pIPI', ns) is not None else 0.0,
            "IPI": float(imposto.find('.//nfe:IPI//nfe:vIPI', ns).text) if imposto.find('.//nfe:IPI//nfe:vIPI', ns) is not None else 0.0,
            "CST PIS": imposto.find('.//nfe:PIS//nfe:CST', ns).text if imposto.find('.//nfe:PIS//nfe:CST', ns) is not None else "",
            "BC PIS": float(imposto.find('.//nfe:PIS//nfe:vBC', ns).text) if imposto.find('.//nfe:PIS//nfe:vBC', ns) is not None else 0.0,
            "Aliq PIS": float(imposto.find('.//nfe:PIS//nfe:pPIS', ns).text) if imposto.find('.//nfe:PIS//nfe:pPIS', ns) is not None else 0.0,
            "PIS": float(imposto.find('.//nfe:PIS//nfe:vPIS', ns).text) if imposto.find('.//nfe:PIS//nfe:vPIS', ns) is not None else 0.0,
            "CST COFINS": imposto.find('.//nfe:COFINS//nfe:CST', ns).text if imposto.find('.//nfe:COFINS//nfe:CST', ns) is not None else "",
            "BC COFINS": float(imposto.find('.//nfe:COFINS//nfe:vBC', ns).text) if imposto.find('.//nfe:COFINS//nfe:vBC', ns) is not None else 0.0,
            "Aliq COFINS": float(imposto.find('.//nfe:COFINS//nfe:pCOFINS', ns).text) if imposto.find('.//nfe:COFINS//nfe:pCOFINS', ns) is not None else 0.0,
            "COFINS": float(imposto.find('.//nfe:COFINS//nfe:vCOFINS', ns).text) if imposto.find('.//nfe:COFINS//nfe:vCOFINS', ns) is not None else 0.0,
            "FCP": float(imposto.find('.//nfe:vFCP', ns).text) if imposto.find('.//nfe:vFCP', ns) is not None else 0.0,
            "ICMS UF Dest": float(imposto.find('.//nfe:vICMSUFDest', ns).text) if imposto.find('.//nfe:vICMSUFDest', ns) is not None else 0.0,
            "Chave de Acesso": chave
        }
        itens_extraidos.append(registro)
    return itens_extraidos

# --- 2. INTERFACE ---
xml_files = st.file_uploader("1. Selecione os ficheiros XML", accept_multiple_files=True, type='xml')
report_file = st.file_uploader("2. Selecione o Relatório (Chave na A, Status na F)", type=['xlsx', 'csv'])

# --- 3. PROCESSAMENTO ---
if xml_files and report_file:
    try:
        # Carrega o relatório
        if report_file.name.endswith('.csv'):
            df_status = pd.read_csv(report_file, dtype=str)
        else:
            df_status = pd.read_excel(report_file, dtype=str)
        
        # Define posições fixas: Coluna A (0) e Coluna F (5)
        # Usamos .iloc para garantir a posição independente do nome
        chaves_relatorio = df_status.iloc[:, 0].astype(str).apply(lambda x: re.sub(r'\D', '', x)).str.strip()
        status_relatorio = df_status.iloc[:, 5].astype(str).str.strip()
        
        # Cria dicionário de busca rápida {Chave: Status}
        status_dict = dict(zip(chaves_relatorio, status_relatorio))
        
        # Extrai XMLs
        lista_consolidada = []
        for f in xml_files:
            lista_consolidada.extend(extrair_tags_estilo_query(f.read()))
        
        if lista_consolidada:
            df_base = pd.DataFrame(lista_consolidada)
            
            # Limpa chaves do XML para bater com o relatório
            df_base['Chave de Acesso'] = df_base['Chave de Acesso'].apply(lambda x: re.sub(r'\D', '', str(x))).str.strip()

            # --- CRIA A COLUNA AP ---
            df_base['AP'] = df_base['Chave de Acesso'].map(status_dict).fillna("Não Encontrada no Relatório")
            
            st.success("Auditoria da Coluna AP finalizada!")
            st.dataframe(df_base[['Chave de Acesso', 'Número NF', 'AP']].head(15))
            
            # Download
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_base.to_excel(writer, index=False, sheet_name='Base_XML')
            st.download_button("📥 Baixar Base_XML com Auditoria", buffer.getvalue(), "Base_XML_Auditada.xlsx")

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
