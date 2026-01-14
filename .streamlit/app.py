import streamlit as st
import zipfile
import io
import os
import xml.etree.ElementTree as ET
import re
import pandas as pd
import gc

# --- MOTOR DE IDENTIFICAÇÃO CORRIGIDO ---
def get_xml_key(content_str):
    match = re.search(r'\d{44}', content_str)
    return match.group(0) if match else None

def identify_xml_info(content_bytes, client_cnpj):
    # LIMPEZA DO CNPJ DO CLIENTE (Garante que só fiquem números)
    client_cnpj_clean = "".join(filter(str.isdigit, client_cnpj)) if client_cnpj else ""
    
    # Valores padrão para evitar erro de desempacotamento
    d_type = "Outros"
    chave = None
    is_p = False
    serie = "0"
    num = None
    pasta = "NAO_IDENTIFICADOS"

    try:
        content_str = content_bytes.decode('utf-8', errors='ignore')
        chave = get_xml_key(content_str)
        
        # Identifica tipo simplificado
        if '<mod>65</mod>' in content_str: d_type = "NFC-e"
        elif '<infCTe' in content_str: d_type = "CT-e"
        elif '<infMDFe' in content_str: d_type = "MDF-e"
        elif '<infNFe' in content_str: d_type = "NF-e"
        elif '<evento' in content_str: d_type = "Eventos"

        # Parser XML rápido
        clean_content = re.sub(r'\sxmlns="[^"]+"', '', content_str, count=1)
        root = ET.fromstring(clean_content)
        
        # Busca CNPJ do Emitente
        emit_cnpj = ""
        emit = root.find(".//emit/CNPJ")
        if emit is not None: 
            emit_cnpj = "".join(filter(str.isdigit, emit.text))
        
        # Série e Número
        s_tag = root.find(".//ide/serie")
        if s_tag is not None: serie = s_tag.text
        
        n_tag = root.find(".//ide/nNF") or root.find(".//ide/nCT") or root.find(".//ide/nMDF")
        if n_tag is not None: num = int(n_tag.text)

        # COMPARAÇÃO DE CNPJ
        is_p = (client_cnpj_clean != "" and emit_cnpj == client_cnpj_clean)
        
        if is_p:
            pasta = f"EMITIDOS_CLIENTE/{d_type}/Serie_{serie}"
        else:
            pasta = f"RECEBIDOS_TERCEIROS/{d_type}"
            
        return pasta, chave, is_p, serie, num, d_type
    except:
        return "ERRO_LEITURA", chave, False, "0", None, "ERRO"

# --- INTERFACE ---
st.set_page_config(page_title="Garimpeiro v4.4", layout="wide")
st.title("⛏️ Garimpeiro v4.4 - Versão de Estabilidade")

with st.sidebar:
    st.header("⚙️ Configurações")
    cnpj_input = st.text_input("CNPJ do Cliente", placeholder="00.000.000/0000-00")
    if st.button("🗑️ Resetar Sistema"):
        st.cache_data.clear()
        st.rerun()
    st.info("💡 Corrigido erro de desempacotamento e identificação de CNPJ.")

uploaded_files = st.file_uploader("Suba seus XMLs", accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 INICIAR PROCESSAMENTO", use_container_width=True):
        processed_keys = set()
        sequencias = {} 
        resumo = {}
        
        zip_buffer = io.BytesIO()
        total = len(uploaded_files)
        bar = st.progress(0)
        status = st.empty()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, file in enumerate(uploaded_files):
                content = file.read()
                # Agora SEMPRE retorna 6 valores
                pasta, chave, is_p, serie, num, d_type = identify_xml_info(content, cnpj_input)
                
                if chave and chave not in processed_keys:
                    processed_keys.add(chave)
                    zf.writestr(f"{pasta}/{chave}.xml", content)
                    
                    cat = pasta.replace('/', ' - ')
                    resumo[cat] = resumo.get(cat, 0) + 1
                    
                    if is_p and num:
                        chave_seq = (d_type, serie)
                        if chave_seq not in sequencias: sequencias[chave_seq] = set()
                        sequencias[chave_seq].add(num)
                
                if i % 20 == 0:
                    prog_val = (i + 1) / total
                    bar.progress(prog_val)
                    status.caption(f"Processando: {i+1} de {total}")
                    gc.collect()

        if processed_keys:
            st.success(f"✅ Processamento Concluído! {len(processed_keys)} notas únicas.")
            
            # Relatório de Faltantes
            faltantes_data = []
            for (d_type, serie), nums in sequencias.items():
                if nums:
                    min_n, max_n = min(nums), max(nums)
                    sequencia_completa = set(range(min_n, max_n + 1))
                    numeros_faltantes = sorted(list(sequencia_completa - nums))
                    for n in numeros_faltantes:
                        faltantes_data.append({"Documento": d_type, "Série": serie, "Número Faltante": n})

            col_res1, col_res2 = st.columns([1, 1])
            with col_res1:
                st.write("### 📊 Inventário de Pastas")
                df_res = pd.DataFrame(list(resumo.items()), columns=['Caminho', 'Quantidade'])
                st.table(df_res)
            
            with col_res2:
                st.write("### ⚠️ Notas Faltantes")
                if faltantes_data:
                    df_faltantes = pd.DataFrame(faltantes_data)
                    st.dataframe(df_faltantes, use_container_width=True)
                else:
                    st.info("Nenhuma falha de sequência nas notas emitidas.")

            st.divider()
            st.download_button(
                "📥 BAIXAR TUDO (.ZIP)",
                data=zip_buffer.getvalue(),
                file_name="garimpo_v4_4.zip",
                use_container_width=True
            )
        
        zip_buffer.close()
        gc.collect()
