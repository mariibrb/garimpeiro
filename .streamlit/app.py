import streamlit as st
import zipfile
import io
import os

def extract_xml_recursive(data, xml_files_dict):
    """
    Lê bytes de um arquivo. Se for um ZIP, abre e olha dentro de forma recursiva.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for file_info in z.infolist():
                if file_info.is_dir():
                    continue
                
                filename = file_info.filename
                
                # Se encontrar um ZIP dentro do ZIP, mergulha de novo
                if filename.lower().endswith('.zip'):
                    try:
                        nested_zip_bytes = z.read(filename)
                        extract_xml_recursive(nested_zip_bytes, xml_files_dict)
                    except Exception:
                        continue
                
                # Se encontrar um XML dentro do ZIP
                elif filename.lower().endswith('.xml'):
                    content = z.read(filename)
                    add_to_dict(filename, content, xml_files_dict)
    except zipfile.BadZipFile:
        pass

def add_to_dict(filepath, content, xml_files_dict):
    """
    Adiciona o XML ao dicionário garantindo que o nome seja único.
    """
    simple_name = os.path.basename(filepath)
    if not simple_name:
        return

    name_to_save = simple_name
    counter = 1
    
    # Se o nome já existir (ex: nota.xml de pastas diferentes), renomeia
    while name_to_save in xml_files_dict:
        name_part, ext_part = os.path.splitext(simple_name)
        name_to_save = f"{name_part}_{counter}{ext_part}"
        counter += 1
    
    xml_files_dict[name_to_save] = content

# --- INTERFACE STREAMLIT ---

st.set_page_config(page_title="Garimpeiro de XML", page_icon="🔍", layout="centered")

st.title("🔍 Garimpeiro de XML")
st.subheader("Extraia XMLs de Pastas, ZIPs e Subpastas")

st.markdown("""
**Como usar:**
1. Selecione ou arraste **Pastas**, **Arquivos ZIP** ou **XMLs soltos**.
2. O sistema vai ignorar a bagunça de pastas e encontrar todos os arquivos `.xml`.
3. No final, você baixa um único arquivo ZIP com tudo organizado.
""")

# O accept_multiple_files permite que você selecione vários arquivos ou arraste uma pasta
uploaded_files = st.file_uploader(
    "Arraste tudo aqui (Pastas, ZIPs, XMLs)", 
    accept_multiple_files=True
)

if uploaded_files:
    if st.button("🚀 Iniciar Varredura Total"):
        all_xmls = {} # Dicionário: {nome_unico.xml: bytes}
        
        with st.spinner("Vasculhando arquivos... aguarde."):
            for uploaded_file in uploaded_files:
                file_bytes = uploaded_file.read()
                file_name = uploaded_file.name.lower()
                
                # Se for um ZIP que você subiu ou que estava na pasta
                if file_name.endswith('.zip'):
                    extract_xml_recursive(file_bytes, all_xmls)
                
                # Se for um XML que estava solto na pasta ou subpasta
                elif file_name.endswith('.xml'):
                    add_to_dict(uploaded_file.name, file_bytes, all_xmls)
        
        if all_xmls:
            st.success(f"✅ Sucesso! Localizamos {len(all_xmls)} arquivos XML.")
            
            # Criar o ZIP de saída
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as new_zip:
                for name, content in all_xmls.items():
                    new_zip.writestr(name, content)
            
            st.download_button(
                label="📥 Baixar Pack de XMLs",
                data=zip_buffer.getvalue(),
                file_name="xmls_consolidados.zip",
                mime="application/zip"
            )
        else:
            st.error("⚠️ Nenhum arquivo XML foi encontrado nos itens enviados.")

st.divider()
st.caption("Dica: Você pode selecionar múltiplos arquivos e pastas de uma vez usando o Ctrl (ou Cmd) + A.")
