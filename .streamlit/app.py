import streamlit as st
import zipfile
import io
import os
import xml.etree.ElementTree as ET
import re

def get_xml_key(root, content_str):
    """Extrai a chave de acesso (44 dígitos) do XML."""
    ch_tag = root.find(".//chNFe") or root.find(".//chCTe") or root.find(".//chMDFe")
    if ch_tag is not None and ch_tag.text:
        return ch_tag.text
    inf_tags = [".//infNFe", ".//infCTe", ".//infMDFe", ".//infProc"]
    for tag in inf_tags:
        element = root.find(tag)
        if element is not None and 'Id' in element.attrib:
            key = re.sub(r'\D', '', element.attrib['Id'])
            if len(key) == 44: return key
    found = re.findall(r'\d{44}', content_str)
    if found: return found[0]
    return None

def identify_xml_info(content_bytes, client_cnpj):
    client_cnpj = "".join(filter(str.isdigit, client_cnpj))
    try:
        content_str = content_bytes.decode('utf-8', errors='ignore')
        clean_content = content_str
        for ns in ["nfe", "cte", "mdfe"]:
            clean_content = clean_content.replace(f'xmlns="http://www.portalfiscal.inf.br/{ns}"', '')
        root = ET.fromstring(clean_content)
        
        doc_type = "Outros"
        tag_lower = content_str.lower()
        if '<infnfe' in tag_lower:
            doc_type = "NFC-e" if '<mod>65</mod>' in tag_lower else "NF-e"
        elif '<infcte' in tag_lower: doc_type = "CT-e"
        elif '<infmdfe' in tag_lower: doc_type = "MDF-e"
        elif '<evento' in tag_lower or '<infresevento' in tag_lower: doc_type = "Eventos"

        emit_cnpj = ""
        serie = "0"
        emit = root.find(".//emit/CNPJ")
        if emit is not None:
            emit_cnpj = "".join(filter(str.isdigit, emit.text))
        serie_tag = root.find(".//ide/serie")
        if serie_tag is not None:
            serie = serie_tag.text

        chave = get_xml_key(root, content_str)
        if client_cnpj and emit_cnpj == client_cnpj:
            pasta_final = f"EMITIDOS_CLIENTE/{doc_type}/Serie_{serie}"
        else:
            pasta_final = f"RECEBIDOS_TERCEIROS/{doc_type}"
        return pasta_final, chave
    except:
        return "NAO_IDENTIFICADOS", None

def add_to_dict(filepath, content, xml_files_dict, client_cnpj, processed_keys):
    simple_name = os.path.basename(filepath)
    if not simple_name or not simple_name.lower().endswith('.xml'): return
    subfolder, chave = identify_xml_info(content, client_cnpj)
    if chave:
        if chave in processed_keys: return
        processed_keys.add(chave)
        simple_name = f"{chave}.xml"
    full_path_in_zip = f"{subfolder}/{simple_name}"
    name_to_save = full_path_in_zip
    counter = 1
    while name_to_save in xml_files_dict:
        name_part, ext_part = os.path.splitext(simple_name)
        name_to_save = f"{subfolder}/{name_part}_{counter}{ext_part}"
        counter += 1
    xml_files_dict[name_to_save] = content

def process_recursively(file_name, file_bytes, xml_files_dict, client_cnpj, processed_keys):
    if file_name.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                for info in z.infolist():
                    if info.is_dir(): continue
                    content = z.read(info.filename)
                    process_recursively(info.filename, content, xml_files_dict, client_cnpj, processed_keys)
        except: pass
    elif file_name.lower().endswith('.xml'):
        add_to_dict(file_name, file_bytes, xml_files_dict, client_cnpj, processed_keys)

# --- INTERFACE ---

st.set_page_config(page_title="Garimpeiro de XML v2.6", page_icon="⛏️", layout="wide")

st.title("⛏️ Garimpeiro de XML 💎")

with st.sidebar:
    st.header("⚙️ Configurações")
    cnpj_input = st.text_input("CNPJ do Cliente (apenas números)", placeholder="Ex: 12345678000199")
    st.divider()
    st.info("🛡️ Anti-Duplicidade Ativa")
    st.info("📊 Separação por Série Ativa")

# --- ÁREA DE CARREGAMENTO E STATUS ---
st.markdown("### 📥 Passo 1: Carregar os arquivos")
uploaded_files = st.file_uploader(
    "Arraste sua pasta ou arquivos aqui", 
    accept_multiple_files=True
)

if uploaded_files:
    total_files = len(uploaded_files)
    st.info(f"📁 {total_files} itens prontos na fila. Clique no botão abaixo para iniciar o processamento.")
    
    if st.button("🚀 INICIAR EXTRAÇÃO E VER PROGRESSO TOTAL", use_container_width=True):
        all_xml_data = {}
        processed_keys = set()
        
        # Criando o painel de progresso fixo que vai aparecer LOGO ACIMA do resultado
        with st.container(border=True):
            st.markdown("## 📈 PROGRESSO TOTAL DO GARIMPO")
            barra_total = st.progress(0)
            col1, col2, col3 = st.columns(3)
            p_metric = col1.empty()
            c_metric = col2.empty()
            u_metric = col3.empty()
            txt_atual = st.empty()

        # Loop de processamento real
        for i, file in enumerate(uploaded_files):
            # Lógica de progresso
            progresso_atual = (i + 1) / total_files
            
            # Atualiza visualmente a BARRA GERAL
            barra_total.progress(progresso_atual)
            p_metric.metric("Concluído", f"{int(progresso_atual * 100)}%")
            c_metric.metric("Arquivos Lidos", f"{i+1} de {total_files}")
            u_metric.metric("XMLs Únicos", len(all_xml_data))
            txt_atual.caption(f"⛏️ Minerando: {file.name}")
            
            # Lê o conteúdo e processa
            process_recursively(file.name, file.read(), all_xml_data, cnpj_input, processed_keys)

        # Finalização
        txt_atual.empty()
        st.balloons()
        st.success(f"✨ Garimpo Finalizado! {len(all_xml_data)} XMLs organizados.")
        
        # Gerar ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for path, data in all_xml_data.items():
                zf.writestr(path, data)
        
        # Resumo
        resumo = {}
        for path in all_xml_data.keys():
            partes = path.split('/')
            cat = " - ".join([p.replace('_', ' ') for p in partes[:-1]])
            resumo[cat] = resumo.get(cat, 0) + 1
        
        st.write("### 💎 Resumo do Tesouro:")
        st.table(resumo)

        st.download_button(
            label="📥 BAIXAR ZIP FINAL",
            data=zip_buffer.getvalue(),
            file_name="garimpo_xml_final.zip",
            mime="application/zip",
            use_container_width=True
        )

st.divider()
st.caption("FoxHelper: Sistema com Barra de Progresso Unificada v2.6")
