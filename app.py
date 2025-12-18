import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io

st.set_page_config(page_title="Sentinela - Power Query Python", layout="wide")
st.title("📑 Extração Bruta para Base_XML (Padrão Power Query)")

def extrair_tags_estilo_query(xml_content):
    ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
    try:
        root = ET.fromstring(xml_content)
    except Exception:
        return []

    # Dados do Cabeçalho (Repetem-se para cada item)
    infNFe = root.find('.//nfe:infNFe', ns)
    chave = infNFe.attrib['Id'][3:] if infNFe is not None else ""
    ide = root.find('.//nfe:ide', ns)
    emit = root.find('.//nfe:emit', ns)
    dest = root.find('.//nfe:dest', ns)

    itens_extraidos = []
    
    # O "Coração" do Query: Iterar sobre cada item <det>
    for det in root.findall('.//nfe:det', ns):
        prod = det.find('nfe:prod', ns)
        imposto = det.find('nfe:imposto', ns)
        
        # Mapeamento de Colunas Idêntico ao seu Modelo
        registro = {
            "Natureza Operação": ide.find('nfe:natOp', ns).text if ide is not None else "",
            "Número NF": ide.find('nfe:nNF', ns).text if ide is not None else "",
            "Finalidade": ide.find('nfe:finNFe', ns).text if ide is not None else "",
            "UF Emit": emit.find('nfe:enderEmit/nfe:UF', ns).text if emit is not None else "",
            "CNPJ Emit": emit.find('nfe:CNPJ', ns).text if emit is not None else "",
            "UF Dest": dest.find('nfe:enderDest/nfe:UF
