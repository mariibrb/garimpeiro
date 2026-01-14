import streamlit as st
import zipfile
import io
import os
import xml.etree.ElementTree as ET
import re
import pandas as pd
import gc

# --- MOTOR DE IDENTIFICAÇÃO (VERSÃO ASPIRADOR) ---
def get_xml_key(content_str):
    match = re.search(r'\d{44}', content_str)
    return match.group(0) if match else None

def identify_xml_info(content_bytes, client_cnpj, file_name):
    client_cnpj_clean = "".join(filter(str.isdigit, str(client_cnpj))) if client_cnpj else ""
    
    # Valores padrão para não perder o arquivo nunca
    pasta = "RECEBIDOS_TERCEIROS/Outros_ou_Eventos"
    chave = get_xml_key(content_bytes.decode('utf-8', errors='ignore')) or file_name.replace('.xml', '').replace('.XML', '')
    is_p = False
    serie = "0"
    num = None
    d_type = "XML_Geral"

    try:
        try:
            content_str = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            content_str = content_bytes.decode('latin-1', errors='ignore')

        # Identificação de Tipo
        tag_lower = content_str.lower()
        if '<mod>65</mod>' in tag_lower: d_type = "NFC-e"
        elif '<infcte' in tag_lower: d_type = "CT-e"
        elif '<infmdfe' in tag_lower: d_type = "MDF-e"
        elif '<infnfe' in tag_lower: d_type = "NF-e"
        elif '<evento' in tag_lower: d_type = "Eventos"

        # Parser XML
        clean_content = re.sub(r'\sxmlns="[^"]+"', '', content_str, count=1)
        root = ET.fromstring(clean_content)
        
        # Identifica Emitente
        emit_cnpj = ""
        emit_tag = root.find(".//emit/CNPJ")
        if emit_tag is not None and emit_tag.text:
            emit_cnpj = "".join(filter(str.isdigit, emit_tag.text))
        
        # Série e Número
        s_tag = root.find(".//ide/serie")
        if s_tag is not None: serie = s_tag.text
        
        n_tag = root.find(".//ide/nNF") or root.find(".//ide/nCT") or root.find(".//ide/nMDF")
        if n_tag is not None: num = int(n_tag.text)

        # SEPARAÇÃO EMITIDA VS RECEBIDA
        if client_cnpj_clean and (emit_cnpj == client_cnpj_clean or (chave and client_cnpj_clean in chave[6:20])):
            is_p = True
            pasta = f"EMITIDOS_CLIENTE/{d_type}/Serie_{serie}"
        else:
            is_p = False
            pasta = f"RECEBIDOS_TERCEIROS/{d_type}"
            
        return pasta, chave, is_p, serie, num, d_type
    except:
        # Se der erro no parser, ainda assim mantemos o arquivo nos Recebidos
        return "RECEBIDOS_TERCEIROS/Nao_Categorizados", chave, False, "0", None, "XML_Geral"

def process_zip_recursively(file_bytes, zf_output, processed_keys, sequencias, resumo, client_cnpj):
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            for info in z.infolist():
                if info.is_dir(): continue
                content = z.read(info.filename)
                fname_lower = info.filename.lower()
                
                if fname_lower.endswith('.zip'):
                    process_zip_recursively(content, zf_output, processed_keys, sequencias, resumo, client_cnpj)
                
                elif fname_lower.endswith('.xml'):
                    pasta, chave, is_p, serie, num, d_type = identify_xml_info(content, client_cnpj, info.filename)
                    
                    # Usamos o nome do arquivo + chave para garantir unicidade
                    identificador_unico = chave if chave else info.filename
                    
                    if identificador_unico not in processed_keys:
                        processed_keys.add(identificador_unico)
                        zf_output.writestr(f"{pasta}/{identificador_unico}.xml", content)
                        
                        cat = pasta.replace('/', ' - ')
                        resumo[cat] = resumo.get(cat, 0) + 1
                        
                        if is_p and num:
                            chave_seq = (d_type, serie)
                            if chave_seq not in sequencias: sequencias[chave_seq] = set()
                            sequencias[chave_seq].add(num)
    except: pass

# --- INTERFACE ---
st.set_page_config(page_title="Garimpeiro v5.0", layout="wide", page_icon="⛏️")
st.title("⛏️ Garimpeiro v5.0 - Coleta Total (Sem Perdas)")

with st.sidebar:
    st.header("⚙️ Configurações")
    cnpj_input = st.text_input("CNPJ do Cliente", placeholder="Ex: 12.345.678/0001-99")
    if st.button("🗑️ Resetar Tudo"):
        st.cache_data.clear()
        st.rerun()
    st.info("💡 v5.0: Agora captura até XMLs com erros ou sem chave definida.")

uploaded_files = st.file_uploader("Suba seus XMLs ou ZIPs", accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 INICIAR GARIMPO", use_container_width=True):
        processed_keys = set()
        sequencias = {} 
        resumo = {}
        zip_buffer = io.BytesIO()
        total = len(uploaded_files)
        bar = st.progress(0)

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf_final:
            for i, file in enumerate(uploaded_files):
                file_bytes = file.read()
                fname_lower = file.name.lower()
                
                if fname_lower.endswith('.zip'):
                    process_zip_recursively(file_bytes, zf_final, processed_keys, sequencias, resumo, cnpj_input)
                elif fname_lower.endswith('.xml'):
                    pasta, chave, is_p, serie, num, d_type = identify_xml_info(file_bytes, cnpj_input, file.name)
                    
                    identificador = chave if chave else file.name
                    if identificador not in processed_keys:
                        processed_keys.add(identificador)
                        zf_final.writestr(f"{pasta}/{identificador}.xml", file_bytes)
                        cat = pasta.replace('/', ' - ')
                        resumo[cat] = resumo.get(cat, 0) + 1
                        if is_p and num:
                            chave_seq = (d_type, serie)
                            if chave_seq not in sequencias: sequencias[chave_seq] = set()
                            sequencias[chave_seq].add(num)
                
                bar.progress((i + 1) / total)
                gc.collect()

        if processed_keys:
            st.success(f"✅ Concluído! {len(processed_keys)} arquivos minerados.")
            
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

            st.download_button("📥 BAIXAR GARIMPO COMPLETO", zip_buffer.getvalue(), "garimpo_v5.zip", use_container_width=True)
        zip_buffer.close()
        gc.collect()
