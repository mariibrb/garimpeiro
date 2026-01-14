import streamlit as st
import zipfile
import io
import os
import xml.etree.ElementTree as ET
import re
import pandas as pd
import gc

# --- FUNÇÕES DE IDENTIFICAÇÃO ---
def get_xml_key(content_str):
    match = re.search(r'\d{44}', content_str)
    return match.group(0) if match else None

def identify_xml_info(content_bytes, client_cnpj):
    # LIMPEZA ABSOLUTA DO CNPJ (Garante que só fiquem números para comparar)
    client_cnpj_clean = "".join(filter(str.isdigit, str(client_cnpj))) if client_cnpj else ""
    
    # Valores padrão para garantir o retorno de 6 itens sempre
    pasta = "NAO_IDENTIFICADOS"
    chave = None
    is_p = False
    serie = "0"
    num = None
    d_type = "Outros"

    try:
        content_str = content_bytes.decode('utf-8', errors='ignore')
        chave = get_xml_key(content_str)
        
        # Identifica tipo de documento
        if '<mod>65</mod>' in content_str: d_type = "NFC-e"
        elif '<infCTe' in content_str: d_type = "CT-e"
        elif '<infMDFe' in content_str: d_type = "MDF-e"
        elif '<infNFe' in content_str: d_type = "NF-e"
        elif '<evento' in content_str: d_type = "Eventos"

        # Parser XML
        clean_content = re.sub(r'\sxmlns="[^"]+"', '', content_str, count=1)
        root = ET.fromstring(clean_content)
        
        # Busca CNPJ do Emitente (quem enviou a nota)
        emit_cnpj = ""
        emit = root.find(".//emit/CNPJ")
        if emit is not None and emit.text: 
            emit_cnpj = "".join(filter(str.isdigit, emit.text))
        
        # Busca Série e Número
        s_tag = root.find(".//ide/serie")
        if s_tag is not None: serie = s_tag.text
        
        n_tag = root.find(".//ide/nNF") or root.find(".//ide/nCT") or root.find(".//ide/nMDF")
        if n_tag is not None: num = int(n_tag.text)

        # COMPARAÇÃO CRÍTICA: Se o CNPJ do XML for igual ao que você digitou
        if client_cnpj_clean and emit_cnpj == client_cnpj_clean:
            is_p = True
            pasta = f"EMITIDOS_CLIENTE/{d_type}/Serie_{serie}"
        else:
            is_p = False
            pasta = f"RECEBIDOS_TERCEIROS/{d_type}"
            
        return pasta, chave, is_p, serie, num, d_type
    except:
        # Se o arquivo estiver corrompido, ele retorna o erro sem quebrar o app
        return "ERRO_ARQUIVO", chave, False, "0", None, "ERRO"

# --- INTERFACE ---
st.set_page_config(page_title="Garimpeiro v4.5", layout="wide")
st.title("⛏️ Garimpeiro v4.5 - Restauração de Funções")

with st.sidebar:
    st.header("⚙️ Configurações")
    cnpj_input = st.text_input("CNPJ do Cliente", placeholder="00.000.000/0000-00")
    if st.button("🗑️ Resetar Tudo"):
        st.cache_data.clear()
        st.rerun()
    st.info("✅ Correção: Separação de Emitidas por Série restaurada.")

uploaded_files = st.file_uploader("Suba seus XMLs", accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 INICIAR GARIMPO", use_container_width=True):
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
                # Chamada da função garantindo os 6 retornos
                pasta, chave, is_p, serie, num, d_type = identify_xml_info(content, cnpj_input)
                
                if chave and chave not in processed_keys:
                    processed_keys.add(chave)
                    zf.writestr(f"{pasta}/{chave}.xml", content)
                    
                    # Contabiliza para o resumo visual
                    cat = pasta.replace('/', ' - ')
                    resumo[cat] = resumo.get(cat, 0) + 1
                    
                    # Lógica de Faltantes (Apenas para notas do próprio cliente)
                    if is_p and num:
                        chave_seq = (d_type, serie)
                        if chave_seq not in sequencias: sequencias[chave_seq] = set()
                        sequencias[chave_seq].add(num)
                
                # Atualização de progresso
                if i % 20 == 0 or i + 1 == total:
                    val = (i + 1) / total
                    bar.progress(val)
                    status.caption(f"Processando: {i+1} de {total}")
                    gc.collect()

        if processed_keys:
            st.success(f"✅ Concluído! {len(processed_keys)} notas organizadas.")
            
            # Relatório de Faltantes
            faltantes_data = []
            for (d_type, serie), nums in sequencias.items():
                if nums:
                    ideal = set(range(min(nums), max(nums) + 1))
                    buracos = sorted(list(ideal - nums))
                    for b in buracos:
                        faltantes_data.append({"Tipo": d_type, "Série": serie, "Nº Faltante": b})

            col1, col2 = st.columns([1, 1])
            with col1:
                st.write("### 📊 Inventário Final")
                st.table(pd.DataFrame(list(resumo.items()), columns=['Pasta / Caminho', 'Qtd']))
            
            with col2:
                st.write("### ⚠️ Relatório de Faltantes")
                if faltantes_data:
                    st.dataframe(pd.DataFrame(faltantes_data), use_container_width=True)
                else:
                    st.info("Nenhum buraco na sequência encontrado!")

            st.divider()
            st.download_button(
                "📥 BAIXAR GARIMPO COMPLETO (.ZIP)",
                data=zip_buffer.getvalue(),
                file_name="garimpo_v4_5.zip",
                use_container_width=True
            )
        
        zip_buffer.close()
        gc.collect()
