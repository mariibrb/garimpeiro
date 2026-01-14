import streamlit as st
import zipfile
import io
import os

def identify_xml_type(content_bytes):
    """Analisa o conteúdo do XML para identificar o tipo de documento fiscal."""
    try:
        content = content_bytes.decode('utf-8', errors='ignore').lower()
        if '<infnfe' in content:
            return "NFC-e" if '<mod>65</mod>' in content else "NF-e"
        elif '<infcte' in content: return "CT-e"
        elif '<infmdfe' in content: return "MDF-e"
        elif '<infresevento' in content or '<evento' in content: return "Eventos"
        elif '<procnfe' in content: return "NF-e"
        elif '<proccte' in content: return "CT-e"
        else: return "Outros_XMLs"
    except:
        return "Nao_Identificados"

def add_to_dict(filepath, content, xml_files_dict):
    """Organiza o arquivo na pasta correta e evita nomes duplicados."""
    simple_name = os.path.basename(filepath)
    if not simple_name or not simple_name.lower().endswith('.xml'):
        return

    doc_type = identify_xml_type(content)
    full_path_in_zip = f"{doc_type}/{simple_name}"
    
    name_to_save = full_path_in_zip
    counter = 1
    while name_to_save in xml_files_dict:
        name_part, ext_part = os.path.splitext(simple_name)
        name_to_save = f"{doc_type}/{name_part}_{counter}{ext_part}"
        counter += 1
    
    xml_files_dict[name_to_save] = content

def process_recursively(file_name, file_bytes, xml_files_dict):
    """Mergulha em ZIPs e processa arquivos XML soltos (de pastas abertas)."""
    if file_name.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                for internal_info in z.infolist():
                    if
