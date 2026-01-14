import streamlit as st
import zipfile
import io
import os

def identify_xml_type(content_bytes):
    """
    Identifica se é NF-e, CT-e, MDF-e, etc., lendo o XML.
    """
    try:
        content = content_bytes.decode('utf-8', errors='ignore').lower()
        if '<infnfe' in content:
            if '<mod>65</mod>' in content: return "NFC-e"
            return "NF-e"
        elif '<infcte' in content: return "CT-e"
        elif '<infmdfe' in content: return "MDF-e"
        elif '<infresevento' in content or '<evento' in content: return "Eventos"
        elif '<procnfe' in content: return "NF-e"
        elif '<proccte' in content: return "CT-e"
        else: return "Outros_XMLs"
    except:
        return "Nao_Identificados"

def add_to_dict(filepath, content, xml_files_dict):
    """
    Guarda o XML na pasta certa dentro do dicionário.
    """
    simple_name = os.path.basename(filepath)
    if not simple_name or not simple_name.lower().endswith('.xml'):
        return

    doc_type = identify_xml_type(content)
    full_path_in_zip = f"{doc_type}/{simple_name}"
    
    # Evita sobrescrever arquivos com mesmo nome
    name_to_save = full_path_in_zip
    counter = 1
    while name_to_save in xml_files_dict:
        name_part, ext_part = os.path.splitext(simple_name)
        name_to_save = f"{doc_type}/{name_part}_{counter}{ext_part}"
        counter += 1
    
    xml_files_dict[name_to_save] = content

def process_recursively(file_name, file_bytes, xml_files_dict):
    """
    Mergulha em ZIPs e processa XMLs soltos.
    """
    # Se o arquivo for um ZIP, abre e processa o que tem dentro
    if file_name.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                for internal_info in z.infolist():
                    if internal_info.is_dir(): continue
                    
                    internal_content = z.read(internal_info.filename)
                    internal_name = internal_info.filename
                    
                    # Recursividade: se tiver outro ZIP dentro do ZIP
                    process_recursively(internal_name, internal_content, xml_files_dict)
        except zipfile.BadZipFile:
            pass
            
    # Se for um XML
    elif file_name.lower().endswith('.xml'):
        add_to_dict(file_name, file_bytes, xml_files_dict)

# --- INTERFACE ---

st.set_page_config(page_title="Extrator de Pastas e ZIPs", page_icon="📂", layout="wide")

st.title("📂 Extrator de XML: Pastas e ZIPs")
st.info("💡 Como o Streamlit não abre o seletor de pastas, selecione todos os arquivos (Ctrl+A) e arraste para cá, ou selecione todos no botão abaixo.")

uploaded_files = st.file_uploader(
    "Arraste a PASTA aqui ou selecione os arquivos", 
    accept_multiple_files=True
)

if uploaded_files:
    if st.button("🚀 Processar Tudo agora"):
        all_xml_data = {}
        
        progress_bar = st.progress(0)
        
        for index, uploaded_file in enumerate(uploaded_files):
            # Processa cada item que veio na "sacola" (pastas arrastadas vêm como lista de arquivos)
            f_bytes = uploaded_file.read()
            f_name = uploaded_file.name
            process_recursively(f_name, f_bytes, all_xml_data)
            
            progress_bar.progress((index + 1) / len(uploaded_files))
            
        if all_xml_data:
            st.success(f"✅ Encontrados {len(all_xml_data)} XMLs!")
            
            # Gera o ZIP final organizado
            final_zip_buffer = io.BytesIO()
            with zipfile.ZipFile(final_zip_buffer, "w", zipfile.ZIP_DEFLATED) as z_final:
                for path_in_zip, data in all_xml_data.items():
                    z_final.writestr(path_in_zip, data)
            
            # Mostra o resultado por colunas
            resumo = {}
            for path in all_xml_data.keys():
                cat = path.split('/')[0]
                resumo[cat] = resumo.get(cat, 0) + 1
            
            cols = st.columns(len(resumo))
            for i, (cat, qtd) in enumerate(resumo.items()):
                cols[i].metric(cat, f"{qtd} un")
            
            st.download_button(
                label="📥 Baixar ZIP Organizado",
                data=final_zip_buffer.getvalue(),
                file_name="xmls_extraidos.zip",
                mime="application/zip",
                use_container_width=True
            )
        else:
            st.error("Nenhum XML localizado.")

st.divider()
st.caption("Nota: Se você arrastar uma pasta, o navegador enviará todos os arquivos dela individualmente.")
