import streamlit as st
import zipfile
import io
import os
import xml.etree.ElementTree as ET
import re
import pandas as pd
import gc

# --- MOTOR DE IDENTIFICAÇÃO ---
def get_xml_key(content_str):
    match = re.search(r'\d{44}', content_str)
    return match.group(0) if match else None

def identify_xml_info(content_bytes, client_cnpj):
    client_cnpj_clean = "".join(filter(str.isdigit, str(client_cnpj))) if client_cnpj else ""
    
    pasta = "NAO_IDENTIFICADOS"
    chave = None
    is_p = False
    serie = "0"
    num = None
    d_type = "Outros"

    try:
        try:
            content_str = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            content_str = content_bytes.decode('latin-1', errors='ignore')

        chave = get_xml_key(content_str)
        
        tag_lower = content_str.lower()
        if '<mod>65</mod>' in tag_lower: d_type = "NFC-e"
        elif '<infcte' in tag_lower: d_type = "CT-e"
        elif '<infmdfe' in tag_lower: d_type = "MDF-e"
        elif '<infnfe' in tag_lower: d_type = "NF-e"
        elif '<evento' in tag_lower: d_type = "Eventos"

        clean_content = re.sub(r'\sxmlns="[^"]+"', '', content_str, count=1)
        root = ET.fromstring(clean_content)
        
        emit_cnpj = ""
        emit_tag = root.find(".//emit/CNPJ")
        if emit_tag is not None and emit_tag.text:
            emit_cnpj = "".join(filter(str.isdigit, emit_tag.text))
        
        s_tag = root.find(".//ide/serie")
        if s_tag is not None: serie = s_tag.text
        
        n_tag = root.find(".//ide/nNF") or root.find(".//ide/nCT") or root.find(".//ide/nMDF")
        if n_tag is not None: num = int(n_tag.text)

        if client_cnpj_clean and emit_cnpj == client_cnpj_clean:
            is_p = True
            pasta = f"EMITIDOS_CLIENTE/{d_type}/Serie_{serie}"
        else:
            if chave and client_cnpj_clean and client_cnpj_clean in chave[6:20]:
                is_p = True
                pasta = f"EMITIDOS_CLIENTE/{d_type}/Serie_{serie}"
            else:
                is_p = False
                pasta = f"RECEBIDOS_TERCEIROS/{d_type}"
            
        return pasta, chave, is_p, serie, num, d_type
    except:
        return "ERRO_PROCESSAMENTO", None, False, "0", None, "ERRO"

# --- FUNÇÃO RECURSIVA PARA ZIP DENTRO DE ZIP ---
def process_zip_recursively(file_bytes, zf_output, processed_keys, sequencias, resumo, client_cnpj):
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            for info in z.infolist():
                if info.is_dir(): continue
                content = z.read(info.filename)
                
                # Se for outro ZIP dentro, chama a função de novo (Recursividade)
                if info.filename.lower().endswith('.zip'):
                    process_zip_recursively(content, zf_output, processed_keys, sequencias, resumo, client_cnpj)
                
                # Se for XML, processa
                elif info.filename.lower().endswith('.xml'):
                    pasta, chave, is_p, serie, num, d_type = identify_xml_info(content, client_cnpj)
                    
                    if pasta != "ERRO_PROCESSAMENTO" and chave and chave not in processed_keys:
                        processed_keys.add(chave)
                        zf_output.writestr(f"{pasta}/{chave}.xml", content)
                        
                        cat = pasta.replace('/', ' - ')
                        resumo[cat] = resumo.get(cat, 0) + 1
                        
                        if is_p and num:
                            chave_seq = (d_type, serie)
                            if chave_seq not in sequencias: sequencias[chave_seq] = set()
                            sequencias[chave_seq].add(num)
    except:
        pass

# --- INTERFACE ---
st.set_page_config(page_title="Garimpeiro v4.9", layout="wide", page_icon="⛏️")
st.title("⛏️ Garimpeiro v4.9 - Visão Raio-X (ZIP em ZIP)")

with st.sidebar:
    st.header("⚙️ Configurações")
    cnpj_input = st.text_input("CNPJ do Cliente", placeholder="Ex: 12.345.678/0001-99")
    if st.button("🗑️ Resetar Tudo"):
        st.cache_data.clear()
        st.rerun()

uploaded_files = st.file_uploader("Suba seus XMLs ou ZIPs", accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 INICIAR GARIMPO RECURSIVO", use_container_width=True):
        processed_keys = set()
        sequencias = {} 
        resumo = {}
        
        zip_buffer = io.BytesIO()
        total = len(uploaded_files)
        bar = st.progress(0)

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf_final:
            for i, file in enumerate(uploaded_files):
                file_bytes = file.read()
                
                if file.name.lower().endswith('.zip'):
                    process_zip_recursively(file_bytes, zf_final, processed_keys, sequencias, resumo, cnpj_input)
                elif file.name.lower().endswith('.xml'):
                    pasta, chave, is_p, serie, num, d_type = identify_xml_info(file_bytes, cnpj_input)
                    if pasta != "ERRO_PROCESSAMENTO" and chave and chave not in processed_keys:
                        processed_keys.add(chave)
                        zf_final.writestr(f"{pasta}/{chave}.xml", file_bytes)
                        cat = pasta.replace('/', ' - ')
                        resumo[cat] = resumo.get(cat, 0) + 1
                        if is_p and num:
                            chave_seq = (d_type, serie)
                            if chave_seq not in sequencias: sequencias[chave_seq] = set()
                            sequencias[chave_seq].add(num)
                
                bar.progress((i + 1) / total)
                gc.collect()

        if processed_keys:
            st.success(f"✅ Concluído! {len(processed_keys)} notas mineradas em todas as camadas.")
            
            # Relatório de Faltantes
            faltantes_data = []
            for (d_type, serie), nums in sequencias.items():
                if nums:
                    ideal = set(range(min(nums), max(nums) + 1))
                    buracos = sorted(list(ideal - nums))
                    for b in buracos:
                        faltantes_data.append({"Tipo": d_type, "Série": serie, "Nº Faltante": b})

            c_a, c_b = st.columns(2)
            with c_a:
                st.write("### 📊 Inventário Final")
                st.table(pd.DataFrame(list(resumo.items()), columns=['Caminho', 'Qtd']))
            with c_b:
                st.write("### ⚠️ Notas Faltantes")
                if faltantes_data:
                    st.dataframe(pd.DataFrame(faltantes_data), use_container_width=True)
                else:
                    st.info("Sequência completa!")

            st.download_button("📥 BAIXAR GARIMPO (.ZIP)", zip_buffer.getvalue(), "garimpo_recursivo.zip", use_container_width=True)
        
        zip_buffer.close()
        gc.collect()
