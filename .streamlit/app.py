import streamlit as st
import zipfile
import io
import os
import xml.etree.ElementTree as ET

def identify_xml_info(content_bytes, client_cnpj):
    """
    Analisa o XML para identificar o tipo (NF-e, CT-e, etc) 
    e se é EMITIDA (Saída) ou RECEBIDA (Entrada).
    """
    # Limpa o CNPJ do cliente (remove pontos e traços)
    client_cnpj = "".join(filter(str.isdigit, client_cnpj))
    
    try:
        content_str = content_bytes.decode('utf-8', errors='ignore')
        # Remove o namespace para facilitar a busca de tags
        content_str = content_str.replace('xmlns="http://www.portalfiscal.inf.br/nfe"', '')
        content_str = content_str.replace('xmlns="http://www.portalfiscal.inf.br/cte"', '')
        
        root = ET.fromstring(content_str)
        
        # 1. Identificar Tipo de Documento
        doc_type = "Outros"
        tag_str = content_str.lower()
        
        if '<infnfe' in tag_str:
            doc_type = "NFC-e" if '<mod>65</mod>' in tag_str else "NF-e"
        elif '<infcte' in tag_str:
            doc_type = "CT-e"
        elif '<infmdfe' in tag_str:
            doc_type = "MDF-e"
        elif '<evento' in tag_str or '<infresevento' in tag_str:
            doc_type = "Eventos"

        # 2. Identificar Fluxo (Emitida vs Recebida)
        # Procuramos o CNPJ do Emitente
        emit_cnpj = ""
        # Tenta encontrar a tag de emitente (funciona para NFe e CTe)
        emit = root.find(".//emit/CNPJ")
        if emit is not None:
            emit_cnpj = "".join(filter(str.isdigit, emit.text))

        fluxo = "RECEBIDOS_TERCEIROS"
        if client_cnpj and emit_cnpj == client_cnpj:
            fluxo = "EMITIDOS_CLIENTE"
            
        return f"{fluxo}/{doc_type}"
    except:
        return "NAO_IDENTIFICADOS"

def add_to_dict(filepath, content, xml_files_dict, client_cnpj):
    simple_name = os.path.basename(filepath)
    if not simple_name or not simple_name.lower().endswith('.xml'):
        return

    # Obtém a pasta (Ex: EMITIDOS_CLIENTE/NF-e)
    subfolder = identify_xml_info(content, client_cnpj)
    full_path_in_zip = f"{subfolder}/{simple_name}"
    
    # Evita duplicados
    name_to_save = full_path_in_zip
    counter = 1
    while name_to_save in xml_files_dict:
        name_part, ext_part = os.path.splitext(simple_name)
        name_to_save = f"{subfolder}/{name_part}_{counter}{ext_part}"
        counter += 1
    
    xml_files_dict[name_to_save] = content

def process_recursively(file_name, file_bytes, xml_files_dict, client_cnpj):
    if file_name.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                for info in z.infolist():
                    if info.is_dir(): continue
                    content = z.read(info.filename)
                    process_recursively(info.filename, content, xml_files_dict, client_cnpj)
        except:
            pass
    elif file_name.lower().endswith('.xml'):
        add_to_dict(file_name, file_bytes, xml_files_dict, client_cnpj)

# --- INTERFACE ---

st.set_page_config(page_title="Extrator Fiscal Inteligente", page_icon="🏦", layout="wide")

st.title("🏦 Extrator Fiscal: Emitidos vs Recebidos")

# Novo campo para o CNPJ do Cliente
with st.sidebar:
    st.header("Configuração")
    cnpj_cliente = st.text_input("CNPJ do seu Cliente", placeholder="00.000.000/0000-00")
    st.info("Se você digitar o CNPJ, vou separar o que ele emitiu do que ele recebeu.")

st.markdown("""
### 🚀 Como usar:
1. Digite o **CNPJ do Cliente** na barra lateral (opcional).
2. Selecione todos os arquivos da pasta (**Ctrl + A**) e arraste para baixo.
3. O sistema vai separar em pastas: **EMITIDOS** e **RECEBIDOS**, e dentro delas por tipo de nota.
""")

uploaded_files = st.file_uploader(
    "Arraste seus arquivos e pastas aqui", 
    accept_multiple_files=True
)

if uploaded_files:
    if st.button("📥 INICIAR SEPARAÇÃO INTELIGENTE"):
        all_xml_data = {}
        progress = st.progress(0)
        
        for i, file in enumerate(uploaded_files):
            process_recursively(file.name, file.read(), all_xml_data, cnpj_cliente)
            progress.progress((i + 1) / len(uploaded_files))

        if all_xml_data:
            st.success(f"✅ Concluído! {len(all_xml_data)} XMLs processados.")
            
            # Criar ZIP final
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for path, data in all_xml_data.items():
                    zf.writestr(path, data)
            
            # Resumo visual (agora por fluxo)
            resumo = {}
            for path in all_xml_data.keys():
                partes = path.split('/')
                fluxo_tipo = f"{partes[0]} - {partes[1]}"
                resumo[fluxo_tipo] = resumo.get(fluxo_tipo, 0) + 1
            
            st.write("### 📊 Resumo da Organização:")
            st.table(resumo)

            st.download_button(
                label="📦 BAIXAR ZIP ORGANIZADO (CLIENTE vs TERCEIROS)",
                data=zip_buffer.getvalue(),
                file_name="contabilidade_organizada.zip",
                mime="application/zip",
                use_container_width=True
            )
        else:
            st.error("Nenhum XML encontrado.")
