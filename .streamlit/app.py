import streamlit as st
import zipfile
import io
import os
import xml.etree.ElementTree as ET
import re
import pandas as pd
import gc

# --- FUNÇÕES DE IDENTIFICAÇÃO (EXTREMA LEVEZA) ---
def get_xml_key(root, content_str):
    try:
        # Busca direta por regex na string costuma ser mais leve que percorrer o XML inteiro
        found = re.search(r'(?:chNFe|chCTe|chMDFe|infNFe Id="|infCTe Id="|infMDFe Id=")[^\d]*(\d{44})', content_str)
        if found: return found.group(1)
        
        # Backup caso o regex falhe
        ch_tag = root.find(".//chNFe") or root.find(".//chCTe") or root.find(".//chMDFe")
        if ch_tag is not None and ch_tag.text: return ch_tag.text
    except: pass
    return None

def identify_xml_info(content_bytes, client_cnpj):
    client_cnpj = "".join(filter(str.isdigit, client_cnpj))
    try:
        content_str = content_bytes.decode('utf-8', errors='ignore')
        # Remove espaços e namespaces para o parser não fritar a RAM
        clean_content = re.sub(r'\sxmlns="[^"]+"', '', content_str, count=1)
        root = ET.fromstring(clean_content)
        
        doc_type = "Outros"
        tag_lower = content_str.lower()
        if '<infnfe' in tag_lower: doc_type = "NFC-e" if '<mod>65</mod>' in tag_lower else "NF-e"
        elif '<infcte' in tag_lower: doc_type = "CT-e"
        elif '<infmdfe' in tag_lower: doc_type = "MDF-e"
        elif '<evento' in tag_lower: doc_type = "Eventos"
        
        emit_cnpj = ""; serie = "0"; numero = None
        emit = root.find(".//emit/CNPJ")
        if emit is not None: emit_cnpj = "".join(filter(str.isdigit, emit.text))
        
        serie_tag = root.find(".//ide/serie")
        if serie_tag is not None: serie = serie_tag.text
        
        n_tag = root.find(".//ide/nNF") or root.find(".//ide/nCT") or root.find(".//ide/nMDF")
        if n_tag is not None: numero = int(n_tag.text)

        chave = get_xml_key(root, content_str)
        is_propria = (client_cnpj and emit_cnpj == client_cnpj)
        
        pasta = f"EMITIDOS_CLIENTE/{doc_type}/Serie_{serie}" if is_propria else f"RECEBIDOS_TERCEIROS/{doc_type}"
        return pasta, chave, is_propria, serie, numero
    except:
        return "NAO_IDENTIFICADOS", None, False, "0", None

def process_recursively(file_name, file_bytes, xml_files_dict, client_cnpj, processed_keys, sequencias):
    if file_name.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                for info in z.infolist():
                    if info.is_dir(): continue
                    process_recursively(info.filename, z.read(info.filename), xml_files_dict, client_cnpj, processed_keys, sequencias)
        except: pass
    elif file_name.lower().endswith('.xml'):
        pasta, chave, is_propria, serie, numero = identify_xml_info(file_bytes, client_cnpj)
        if chave and chave not in processed_keys:
            processed_keys.add(chave)
            xml_files_dict[f"{pasta}/{chave}.xml"] = file_bytes
            if is_propria and numero:
                if serie not in sequencias: sequencias[serie] = set()
                sequencias[serie].add(numero)

# --- INTERFACE ---
st.set_page_config(page_title="Garimpeiro v3.8", page_icon="⛏️", layout="wide")
st.title("⛏️ Garimpeiro de XML 💎")

with st.sidebar:
    st.header("⚙️ Configurações")
    cnpj_input = st.text_input("CNPJ do Cliente (Só números)", placeholder="Ex: 12345678000199")
    if st.button("🗑️ Resetar Tudo"):
        st.cache_data.clear()
        st.rerun()

uploaded_files = st.file_uploader("Solte a pasta ou arquivos aqui", accept_multiple_files=True)

if uploaded_files:
    total = len(uploaded_files)
    if st.button("🚀 INICIAR GARIMPO TOTAL", use_container_width=True):
        all_xml_data = {}
        processed_keys = set()
        sequencias_proprias = {}

        # Barra de progresso simplificada
        prog_bar = st.progress(0)
        status = st.empty()

        for i, file in enumerate(uploaded_files):
            process_recursively(file.name, file.read(), all_xml_data, cnpj_input, processed_keys, sequencias_proprias)
            
            if i % 10 == 0: # Atualiza menos vezes para poupar processamento
                prog = (i + 1) / total
                prog_bar.progress(prog)
                status.write(f"⛏️ Processando: {i+1} de {total}")
                gc.collect() # Limpeza agressiva de RAM

        if all_xml_data:
            st.success("✨ Garimpo Concluído!")
            
            # INVENTÁRIO
            resumo = {}
            for path in all_xml_data.keys():
                cat = " - ".join(path.split('/')[:-1]).replace('_', ' ')
                resumo[cat] = resumo.get(cat, 0) + 1
            st.write("### 📊 Inventário")
            st.table(pd.DataFrame(list(resumo.items()), columns=['Categoria / Série', 'Quantidade']))

            # FALTANTES
            faltantes_list = []
            for serie, numeros in sequencias_proprias.items():
                if numeros:
                    seq_ideal = set(range(min(numeros), max(numeros) + 1))
                    for f in sorted(list(seq_ideal - numeros)):
                        faltantes_list.append({"Série": serie, "Número Faltante": f})
            
            if faltantes_list:
                st.write("### ⚠️ Notas Faltantes")
                df_f = pd.DataFrame(faltantes_list)
                st.dataframe(df_f, use_container_width=True)
            
            # ZIP FINAL (Usando compressão mínima para não travar a CPU)
            zip_out = io.BytesIO()
            with zipfile.ZipFile(zip_out, "w", zipfile.STORED) as zf:
                for path, data in all_xml_data.items():
                    zf.writestr(path, data)
                if faltantes_list:
                    zf.writestr("faltantes.csv", pd.DataFrame(faltantes_list).to_csv(index=False))
            
            st.download_button("📥 BAIXAR GARIMPO (.ZIP)", zip_out.getvalue(), "garimpo.zip", use_container_width=True)
            
            # Limpeza final total
            all_xml_data.clear()
            processed_keys.clear()
            gc.collect()

st.divider()
st.caption("v3.8 - Otimização de Fluxo de Dados")
