import streamlit as st
import zipfile
import io
import os

def add_to_dict(filepath, content, xml_files_dict):
    """
    Adiciona o conteúdo XML ao dicionário com um nome único para evitar sobrescrita.
    """
    simple_name = os.path.basename(filepath)
    if not simple_name:
        return

    name_to_save = simple_name
    counter = 1
    
    # Se o nome já existir (mesmo nome em pastas diferentes), renomeia com sufixo
    while name_to_save in xml_files_dict:
        name_part, ext_part = os.path.splitext(simple_name)
        name_to_save = f"{name_part}_{counter}{ext_part}"
        counter += 1
    
    xml_files_dict[name_to_save] = content

def process_recursively(file_name, file_bytes, xml_files_dict):
    """
    Analisa o arquivo: se for XML, guarda. Se for ZIP, explode e analisa o que tem dentro.
    """
    # 1. Se for um arquivo XML direto
    if file_name.lower().endswith('.xml'):
        add_to_dict(file_name, file_bytes, xml_files_dict)
    
    # 2. Se for um arquivo ZIP, abre e varre o conteúdo
    elif file_name.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                for internal_file in z.infolist():
                    if internal_file.is_dir():
                        continue
                    
                    internal_content = z.read(internal_file.filename)
                    # Chama a função novamente para o conteúdo interno (caso haja ZIP dentro de ZIP)
                    process_recursively(internal_file.filename, internal_content, xml_files_dict)
        except zipfile.BadZipFile:
            pass # Ignora arquivos corrompidos ou falsos .zip

# --- CONFIGURAÇÃO DA INTERFACE STREAMLIT ---

st.set_page_config(page_title="Extrator Universal XML", page_icon="🎯", layout="centered")

st.title("🎯 Extrator Universal de XML")
st.markdown("""
### Como funciona:
Arraste **pastas inteiras**, arquivos **ZIP** (com ou sem subpastas) ou **arquivos soltos**. 
O sistema vai:
1. Abrir cada pasta e subpasta.
2. Descompactar cada ZIP (e ZIPs dentro de ZIPs).
3. Identificar apenas os arquivos `.xml`.
4. Gerar um único arquivo ZIP para você baixar com tudo limpo.
""")

# Componente de Upload que aceita múltiplos arquivos (e pastas arrastadas)
uploaded_files = st.file_uploader(
    "Arraste sua bagunça de arquivos e pastas aqui", 
    accept_multiple_files=True
)

if uploaded_files:
    if st.button("🚀 Iniciar Garimpo de XML"):
        all_xmls = {} # Dicionário para armazenar {nome_unico: bytes}
        
        with st.spinner("Analisando arquivos... isso pode levar um tempo dependendo do volume."):
            for uploaded_file in uploaded_files:
                # Lê os bytes do arquivo enviado
                file_bytes = uploaded_file.read()
                file_name = uploaded_file.name
                
                # Processa cada arquivo individualmente
                process_recursively(file_name, file_bytes, all_xmls)
        
        if all_xmls:
            st.success(f"✨ Pronto! Encontramos {len(all_xmls)} arquivos XML no total.")
            
            # Criar o arquivo ZIP de saída em memória
            zip_output = io.BytesIO()
            with zipfile.ZipFile(zip_output, "w", zipfile.ZIP_DEFLATED) as new_zip:
                for name, content in all_xmls.items():
                    new_zip.writestr(name, content)
            
            # Botão de Download
            st.download_button(
                label="📥 Baixar todos os XMLs encontrados",
                data=zip_output.getvalue(),
                file_name="xmls_extraidos_total.zip",
                mime="application/zip"
            )
        else:
            st.error("❌ Nenhum arquivo XML foi localizado nos arquivos/pastas enviados.")

st.divider()
st.info("💡 **Dica:** Para subir pastas no Streamlit, basta selecioná-la no seu computador e arrastar para dentro da caixa de upload acima.")
