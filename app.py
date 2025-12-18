import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import os

st.set_page_config(page_title="Sentinela Fiscal", layout="wide")
st.title("🛡️ Auditoria Fiscal Sentinela")

# Função para carregar a base sem dar erro de nome
@st.cache_data
def carregar_regras():
    # Procura qualquer arquivo Excel na pasta
    arquivos_excel = [f for f in os.listdir('.') if f.endswith('.xlsx')]
    
    if not arquivos_excel:
        st.error("❌ Erro: Não encontrei nenhum arquivo Excel (.xlsx) no GitHub!")
        return None
    
    # Tenta abrir o primeiro que encontrar
    nome_arquivo = arquivos_excel[0]
    try:
        xls = pd.ExcelFile(nome_arquivo)
        
        # Procura pela aba 'Bases Tribut' (com espaço)
        # Se não achar, ele pega a primeira aba que existir no arquivo
        nome_aba = 'Bases Tribut' if 'Bases Tribut' in xls.sheet_names else xls.sheet_names[0]
        
        df = pd.read_excel(xls, sheet_name=nome_aba)
        st.success(f"✅ Base carregada: **{nome_arquivo}** | Aba: **{nome_aba}**")
        return df
    except Exception as e:
        st.error(f"Erro ao ler a planilha: {e}")
        return None

base_regras = carregar_regras()

if base_regras is not None:
    # Área de Upload de XMLs
    arquivos_xml = st.file_uploader("Arraste seus XMLs aqui", type="xml", accept_multiple_files=True)

    if arquivos_xml:
        resultados = []
        for arq in arquivos_xml:
            try:
                tree = ET.parse(arq)
                root = tree.getroot()
                ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
                
                nNF = root.find('.//nfe:ide/nfe:nNF', ns).text
                uf_emit = root.find('.//nfe:emit/nfe:enderEmit/nfe:UF', ns).text
                uf_dest = root.find('.//nfe:dest/nfe:enderDest/nfe:UF', ns).text
                cpf_dest = root.find('.//nfe:dest/nfe:CPF', ns)
                
                # Para cada item (produto) na nota
                for det in root.findall('.//nfe:det', ns):
                    ncm = det.find('.//nfe:prod/nfe:NCM', ns).text
                    cfop = det.find('.//nfe:prod/nfe:CFOP', ns).text
                    
                    # Valor do DIFAL (se existir no total da nota)
                    difal_tag = root.find('.//nfe:total/nfe:ICMSTot/nfe:vICMS
