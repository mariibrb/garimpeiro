import streamlit as st
import zipfile
import io
import os
import re

def identify_xml_type(content_bytes):
    """
    Analisa o conteúdo do XML para identificar o tipo de documento.
    """
    try:
        content = content_bytes.decode('utf-8', errors='ignore').lower()
        
        if '<infnfe' in content:
            # Diferenciar entre NF-e e NFC-e pelo modelo (mod 55 ou 65)
            if '<mod>65</mod>' in content:
                return "NFC-e"
            return "NF-e"
        elif '<infcte' in content:
            return "CT-e"
        elif '<infresevento' in content or '<evento' in content:
            return "Eventos"
        elif '<procnfe' in content:
            return "NF-e"
        elif '<proccte' in content:
            return "CT-e"
        else:
            return "Outros_XMLs"
    except:
        return "Nao_Identificados"

def add_to_dict(filepath, content, xml_files_dict):
    """
    Identifica o tipo e adiciona ao dicionário com o caminho da subpasta.
    """
    simple_name = os.path.basename(filepath)
    if not simple_name:
        return

    # Descobre o tipo de XML (NF-e, CT-e, etc)
    doc_type = identify_xml_type(content)
    
    # Define o caminho dentro do ZIP (Pasta/Arquivo.xml)
    full_path_in_zip = f"{doc_type}/{simple_name}"
    
    # Se o nome já existir na mesma categoria, renomeia
    name_to_save = full_path_in_zip
    counter = 1
    while name_to_save in xml_files_dict:
        name_part, ext_part = os.path.splitext(simple_name)
        name_to_save = f"{doc_type}/{name_part}_{counter}{ext_part}"
        counter += 1
    
    xml_files_dict[name_to_save] = content

def process_recursively(file_name, file_bytes, xml_files_dict):
    """
    Mergulha em ZIPs e captura XMLs.
    """
    if file_name.lower().endswith('.xml'):
        add_to_dict(file_name, file_bytes, xml_files_dict)
    
    elif file_name.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                for internal_file in z.infolist():
                    if internal_file.is_dir():
                        continue
                    internal_content = z.read(internal_file.filename)
                    process_recursively(internal_file.filename, internal_content, xml_files_dict)
        except zipfile.BadZipFile:
            pass

# --- INTERFACE STREAMLIT ---

st.set_page_config(page_title="Organizador Fiscal XML", page_icon="📑", layout="centered")

st.title("📑 Organizador Fiscal de XML")
st.markdown("""
Arraste tudo o que tiver. O sistema vai separar automaticamente em pastas:
- **NF-e** (Notas Fiscais Eletrônicas)
- **NFC-e** (Notas de Consumidor)
- **CT-e** (Conhecimentos de Transporte)
- **Eventos** (Cancelamentos, Cartas de Correção)
""")

uploaded_files = st.file_uploader(
    "Arraste pastas, ZIPs e arquivos aqui", 
    accept_multiple_files=True
)

if uploaded_files:
    if st.button("🚀 Processar e Organizar"):
        all_xmls = {} # { "Tipo/Nome.xml": bytes }
        
        with st.spinner("Lendo e classificando XMLs..."):
            for uploaded_file in uploaded_files:
                file_bytes = uploaded_file.read()
                process_recursively(uploaded_file.name, file_bytes, all_xmls)
        
        if all_xmls:
            st.success(f"✅ Concluído! {len(all_xmls)} XMLs organizados.")
            
            # Criar o ZIP final mantendo a estrutura de pastas
            zip_output = io.BytesIO()
            with zipfile.ZipFile(zip_output, "w", zipfile.ZIP_DEFLATED) as new_zip:
                for path_in_zip, content in all_xmls.items():
                    new_zip.writestr(path_in_zip, content)
            
            st.download_button(
                label="📥 Baixar XMLs Separados por Pasta",
                data=zip_output.getvalue(),
                file_name="xmls_organizados.zip",
                mime="application/zip"
            )
            
            # Mostrar resumo do que foi encontrado
            resumo = {}
            for path in all_xmls.keys():
                categoria = path.split('/')[0]
                resumo[categoria] = resumo.get(categoria, 0) + 1
            
            st.write("### Resumo da extração:")
            st.table(resumo)
        else:
            st.error("❌ Nenhum XML reconhecido foi encontrado.")

st.divider()
st.caption("Organização inteligente baseada nas tags oficiais da SEFAZ.")
