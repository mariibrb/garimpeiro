import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io

st.set_page_config(page_title="Sentinela - Extração Base_XML", layout="wide")
st.title("📑 Extração Bruta de XML (Padrão Power Query)")

def extrair_tags_query(xml_content):
    ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
    try:
        root = ET.fromstring(xml_content)
    except Exception:
        return []

    # Identificação da Nota
    infNFe = root.find('.//nfe:infNFe', ns)
    chave = infNFe.attrib['Id'][3:] if infNFe is not None else ""
    ide = root.find('.//nfe:ide', ns)
    emit = root.find('.//nfe:emit', ns)
    dest = root.find('.//nfe:dest', ns)
    total = root.find('.//nfe:total/nfe:ICMSTot', ns)

    itens = []
    # O Power Query processa cada tag <det> como uma linha na tabela
    for det in root.findall('.//nfe:det', ns):
        prod = det.find('nfe:prod', ns)
        imposto = det.find('nfe:imposto', ns)
        
        # Mapeamento de Colunas igual à sua Base_XML
        registro = {
            "Chave de Acesso": chave,
            "Número NF": ide.find('nfe:nNF', ns).text if ide is not None else "",
            "Série": ide.find('nfe:serie', ns).text if ide is not None else "",
            "Data Emissão": ide.find('nfe:dhEmi', ns).text[:10] if ide is not None else "",
            "Natureza da Operação": ide.find('nfe:natOp', ns).text if ide is not None else "",
            "Modelo": ide.find('nfe:mod', ns).text if ide is not None else "",
            
            # Dados do Emitente
            "CNPJ Emitente": emit.find('nfe:CNPJ', ns).text if emit is not None else "",
            "Nome Emitente": emit.find('nfe:xNome', ns).text if emit is not None else "",
            "UF Emitente": emit.find('.//nfe:UF', ns).text if emit is not None else "",
            
            # Dados do Destinatário
            "CNPJ/CPF Destinatário": (dest.find('nfe:CNPJ', ns).text if dest.find('nfe:CNPJ', ns) is not None else dest.find('nfe:CPF', ns).text) if dest is not None else "",
            "Nome Destinatário": dest.find('nfe:xNome', ns).text if dest is not None else "",
            "UF Destinatário": dest.find('.//nfe:UF', ns).text if dest is not None else "",
            
            # Dados do Item (Produto)
            "Item": det.attrib['nItem'],
            "Código Produto": prod.find('nfe:cProd', ns).text if prod is not None else "",
            "Descrição": prod.find('nfe:xProd', ns).text if prod is not None else "",
            "NCM": prod.find('nfe:NCM', ns).text if prod is not None else "",
            "CFOP": prod.find('nfe:CFOP', ns).text if prod is not None else "",
            "Unidade": prod.find('nfe:uCom', ns).text if prod is not None else "",
            "Quantidade": float(prod.find('nfe:qCom', ns).text) if prod is not None else 0.0,
            "Valor Unitário": float(prod.find('nfe:vUnCom', ns).text) if prod is not None else 0.
