import streamlit as st
import zipfile
import io
import os

def extract_xml_recursive(zip_bytes, xml_files_dict):
    """
    Função recursiva que entra em ZIPs dentro de ZIPs em busca de XMLs.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for file_info in z.infolist():
            # Se for um arquivo XML, salva no dicionário (evita duplicados pelo nome)
            if file_info.filename.lower().endswith('.xml'):
                # Pegamos apenas o nome do arquivo, ignorando o caminho da pasta interna
                filename = os.path.basename(file_info.filename)
                if filename:
                    xml_files_dict[filename] = z.read(file_info.filename)
            
            # Se encontrar outro arquivo ZIP dentro, chama a função novamente
            elif file_info.filename.lower().endswith('.zip'):
                nested_zip_bytes = z.read(file_info.filename)
                extract_xml_recursive(nested_zip_bytes, xml_files_dict)

# Configuração da Página
st.set_page_config(page_title="Extrator Recursivo de XML", page_icon="📦")

st.title("📦 Extrator de XML (ZIP Recursivo)")
st.markdown("""
Esta ferramenta vasculha arquivos ZIP, inclusive aqueles que possuem **outros ZIPs dentro**, 
localiza todos os arquivos `.xml` e gera um único arquivo para download.
""")

# Upload de múltiplos arquivos ZIP
uploaded_files = st.file_uploader("Escolha seus arquivos ZIP", type="zip", accept_multiple_files=True)

if uploaded_files:
    if st.button("Processar e Extrair XMLs"):
        all_xmls = {} # Dicionário para armazenar {nome_arquivo: conteudo_bytes}
        
        with st.spinner("Mergulhando nos arquivos..."):
            for uploaded_file in uploaded_files:
                file_bytes = uploaded_file.read()
                extract_xml_recursive(file_bytes, all_xmls)
        
        if all_xmls:
            st.success(f"Sucesso! Encontramos {len(all_xmls)} arquivos XML.")
            
            # Criar o novo ZIP em memória
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as new_zip:
                for name, content in all_xmls.items():
                    new_zip.writestr(name, content)
            
            # Botão de Download
            st.download_button(
                label="📥 Baixar ZIP Único com XMLs",
                data=zip_buffer.getvalue(),
                file_name="todos_os_xmls.zip",
                mime="application/zip"
            )
        else:
            st.warning("Nenhum arquivo XML foi encontrado nos ZIPs enviados.")

st.divider()
st.caption("Desenvolvido para simplificar extrações complexas de arquivos fiscais ou de dados.")
