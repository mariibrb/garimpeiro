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

st.set_page_config(page_title="Garimpeiro de XML v2.4", page_icon="⛏️", layout="wide")

st.title("⛏️ Garimpeiro de XML 💎")

with st.sidebar:
    st.header("⚙️ Configurações")
    cnpj_input = st.text_input("CNPJ do Cliente (apenas números)", placeholder="Ex: 12345678000199")
    st.divider()
    st.info("🛡️ Anti-Duplicidade Ativa")
    st.info("📊 Separação por Série Ativa")

st.markdown("### 📥 1. Carregar Arquivos")
uploaded_files = st.file_uploader(
    "Arraste sua pasta ou arquivos (Ctrl+A)", 
    accept_multiple_files=True
)

if uploaded_files:
    total_files = len(uploaded_files)
    st.info(f"📂 **{total_files}** arquivos recebidos pelo navegador. Prontos para a mineração!")

    if st.button("⛏️ INICIAR GARIMPO (VER PROGRESSO)", use_container_width=True):
        all_xml_data = {}
        processed_keys = set()
        
        # --- CONTAINER DE PROGRESSO FIXO ---
        # Usamos esse container para garantir que a barra apareça ANTES de começar a pensar
        progress_container = st.container()
        
        with progress_container:
            st.markdown("### 📈 Progresso da Leitura")
            # A barra começa em 0%
            main_bar = st.progress(0)
            c1, c2, c3 = st.columns(3)
            p_text = c1.empty()
            c_text = c2.empty()
            u_text = c3.empty()
            current_f = st.empty()
            st.divider()

        # Execução do Garimpo
        for i, file in enumerate(uploaded_files):
            # Lógica de porcentagem
            perc = (i + 1) / total_files
            
            # Atualização IMEDIATA das métricas para o usuário ver
            main_bar.progress(perc)
            p_text.metric("Concluído", f"{int(perc * 100)}%")
            c_text.metric("Arquivos Processados", f"{i+1} de {total_files}")
            u_text.metric("XMLs Únicos", len(all_xml_data))
            current_f.caption(f"🔍 Analisando: {file.name}")
            
            # O processamento real acontece aqui
            process_recursively(file.name, file.read(), all_xml_data, cnpj_input, processed_keys)

        # Finalização
        current_f.empty()
        st.balloons()
        st.success(f"✨ Tesouro extraído com sucesso! {len(all_xml_data)} arquivos únicos.")
        
        # Criação do ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for path, data in all_xml_data.items():
                zf.writestr(path, data)
        
        # Tabela de Resumo
        resumo = {}
        for path in all_xml_data.keys():
            partes = path.split('/')
            cat = " - ".join([p.replace('_', ' ') for p in partes[:-1]])
            resumo[cat] = resumo.get(cat, 0) + 1
        
        st.write("### 💎 Inventário:")
        st.table(resumo)

        st.download_button(
            label="📥 BAIXAR ZIP ORGANIZADO",
            data=zip_buffer.getvalue(),
            file_name="garimpo_final.zip",
            mime="application/zip",
            use_container_width=True
        )

st.divider()
st.caption("🦊 Garimpeiro v2.4 - Foco em visibilidade de progresso.")
