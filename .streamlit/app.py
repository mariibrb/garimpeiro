import streamlit as st
import zipfile
import io
import os
import xml.etree.ElementTree as ET
import re

def get_xml_key(root, content_str):
    """
    Tenta extrair a chave de acesso (44 dígitos) do XML.
    """
    # 1. Tenta pela tag <chNFe> ou <chCTe>
    ch_tag = root.find(".//chNFe") or root.find(".//chCTe") or root.find(".//chMDFe")
    if ch_tag is not None and ch_tag.text:
        return ch_tag.text

    # 2. Tenta pelo atributo Id da tag infNFe, infCTe, etc (remove o prefixo 'NFe', 'CTe')
    inf_tags = [".//infNFe", ".//infCTe", ".//infMDFe", ".//infProc"]
    for tag in inf_tags:
        element = root.find(tag)
        if element is not None and 'Id' in element.attrib:
            key = re.sub(r'\D', '', element.attrib['Id'])
            if len(key) == 44:
                return key
    
    # 3. Regex como última alternativa no texto bruto
    found = re.findall(r'\d{44}', content_str)
    if found:
        return found[0]
        
    return None

def identify_xml_info(content_bytes, client_cnpj):
    client_cnpj = "".join(filter(str.isdigit, client_cnpj))
    
    try:
        content_str = content_bytes.decode('utf-8', errors='ignore')
        # Limpeza de namespaces para facilitar a leitura
        clean_content = content_str
        for ns in ["nfe", "cte", "mdfe"]:
            clean_content = clean_content.replace(f'xmlns="http://www.portalfiscal.inf.br/{ns}"', '')
        
        root = ET.fromstring(clean_content)
        
        # Identificar Tipo
        doc_type = "Outros"
        tag_lower = content_str.lower()
        if '<infnfe' in tag_lower:
            doc_type = "NFC-e" if '<mod>65</mod>' in tag_lower else "NF-e"
        elif '<infcte' in tag_lower: doc_type = "CT-e"
        elif '<infmdfe' in tag_lower: doc_type = "MDF-e"
        elif '<evento' in tag_lower or '<infresevento' in tag_lower: doc_type = "Eventos"

        # Identificar Fluxo e Chave
        emit_cnpj = ""
        emit = root.find(".//emit/CNPJ")
        if emit is not None:
            emit_cnpj = "".join(filter(str.isdigit, emit.text))

        fluxo = "RECEBIDOS_TERCEIROS"
        if client_cnpj and emit_cnpj == client_cnpj:
            fluxo = "EMITIDOS_CLIENTE"
            
        chave = get_xml_key(root, content_str)
            
        return f"{fluxo}/{doc_type}", chave
    except:
        return "NAO_IDENTIFICADOS", None

def add_to_dict(filepath, content, xml_files_dict, client_cnpj, processed_keys):
    simple_name = os.path.basename(filepath)
    if not simple_name or not simple_name.lower().endswith('.xml'):
        return

    subfolder, chave = identify_xml_info(content, client_cnpj)
    
    # --- FILTRO DE DUPLICIDADE ---
    if chave:
        if chave in processed_keys:
            return # Já processamos esta nota, pula para a próxima
        processed_keys.add(chave)
        # Opcional: usar a chave como nome do arquivo para ficar mais organizado
        simple_name = f"{chave}.xml"

    full_path_in_zip = f"{subfolder}/{simple_name}"
    
    # Garantia contra nomes de arquivos idênticos sem chave
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
        except:
            pass
    elif file_name.lower().endswith('.xml'):
        add_to_dict(file_name, file_bytes, xml_files_dict, client_cnpj, processed_keys)

# --- INTERFACE ---

st.set_page_config(page_title="Extrator Fiscal Pro", page_icon="🛡️", layout="wide")

st.title("🛡️ Extrator Fiscal Pro (Anti-Duplicidade)")

with st.sidebar:
    st.header("⚙️ Configuração")
    cnpj_input = st.text_input("CNPJ do Cliente (apenas números)", placeholder="00000000000000")
    st.divider()
    st.write("✅ **Filtro de Chave Única Ativo:** Notas repetidas serão eliminadas automaticamente.")

uploaded_files = st.file_uploader("Arraste seus arquivos ou pastas aqui", accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 PROCESSAR SEM DUPLICADOS", use_container_width=True):
        all_xml_data = {}
        processed_keys = set() # Conjunto para guardar as chaves já vistas
        
        progress = st.progress(0)
        for i, file in enumerate(uploaded_files):
            process_recursively(file.name, file.read(), all_xml_data, cnpj_input, processed_keys)
            progress.progress((i + 1) / len(uploaded_files))

        if all_xml_data:
            st.success(f"✅ Finalizado! {len(all_xml_data)} XMLs únicos encontrados (Duplicados foram removidos).")
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for path, data in all_xml_data.items():
                    zf.writestr(path, data)
            
            resumo = {}
            for path in all_xml_data.keys():
                partes = path.split('/')
                categoria = f"{partes[0].replace('_', ' ')} - {partes[1]}"
                resumo[categoria] = resumo.get(categoria, 0) + 1
            
            st.table(resumo)
            st.download_button(
                label="📥 BAIXAR ZIP LIMPO",
                data=zip_buffer.getvalue(),
                file_name="xmls_limpos_e_organizados.zip",
                mime="application/zip",
                use_container_width=True
            )

st.divider()
st.caption("Filtro baseado na chave de acesso de 44 dígitos contida no XML.")
