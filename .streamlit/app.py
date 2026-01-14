import streamlit as st
import zipfile
import io
import os
import xml.etree.ElementTree as ET
import re
import pandas as pd
import gc

# --- FUNÇÕES DE IDENTIFICAÇÃO (EXTREMA VELOCIDADE) ---
def get_xml_key(content_str):
    """Busca chave de 44 dígitos via Regex (mais leve que XML parser)."""
    match = re.search(r'\d{44}', content_str)
    return match.group(0) if match else None

def identify_xml_minimal(content_bytes, client_cnpj):
    """Extrai apenas o essencial para a pasta e relatório."""
    try:
        content_str = content_bytes.decode('utf-8', errors='ignore')
        chave = get_xml_key(content_str)
        if not chave: return None, None, False, "0", None

        # Identifica tipo por tags simples
        doc_type = "NF-e"
        if '<mod>65</mod>' in content_str: doc_type = "NFC-e"
        elif '<infCTe' in content_str: doc_type = "CT-e"
        elif '<infMDFe' in content_str: doc_type = "MDF-e"
        elif '<evento' in content_str: doc_type = "Eventos"

        # Parser rápido apenas para CNPJ, Série e Número
        clean_content = re.sub(r'\sxmlns="[^"]+"', '', content_str, count=1)
        root = ET.fromstring(clean_content)
        
        emit_cnpj = ""
        emit = root.find(".//emit/CNPJ")
        if emit is not None: emit_cnpj = "".join(filter(str.isdigit, emit.text))
        
        serie = "0"
        s_tag = root.find(".//ide/serie")
        if s_tag is not None: serie = s_tag.text
        
        num = None
        n_tag = root.find(".//ide/nNF") or root.find(".//ide/nCT") or root.find(".//ide/nMDF")
        if n_tag is not None: num = int(n_tag.text)

        is_p = (client_cnpj and emit_cnpj == client_cnpj)
        pasta = f"EMITIDOS_CLIENTE/{doc_type}/Serie_{serie}" if is_p else f"RECEBIDOS_TERCEIROS/{doc_type}"
        
        return pasta, chave, is_p, serie, num
    except:
        return None, None, False, "0", None

# --- INTERFACE ---
st.set_page_config(page_title="Garimpeiro v4.2", layout="wide")
st.title("⛏️ Garimpeiro v4.2 - Ultra Leve")

with st.sidebar:
    st.header("⚙️ Configurações")
    cnpj_input = st.text_input("CNPJ do Cliente (Só números)")
    if st.button("🗑️ Forçar Reboot de Memória"):
        st.cache_data.clear()
        st.rerun()
    st.info("💡 Se tiver +2000 arquivos, suba em um arquivo .ZIP")

uploaded_files = st.file_uploader("Suba seus XMLs", accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 INICIAR GARIMPO DE ALTO VOLUME", use_container_width=True):
        processed_keys = set()
        sequencias = {}
        resumo = {}
        
        # Criamos o ZIP direto em um buffer de bytes
        zip_buffer = io.BytesIO()
        
        total = len(uploaded_files)
        bar = st.progress(0)
        status = st.empty()

        # Abrimos o ZIP para escrita imediata
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, file in enumerate(uploaded_files):
                content = file.read()
                pasta, chave, is_p, serie, num = identify_xml_minimal(content, cnpj_input)
                
                if chave and chave not in processed_keys:
                    processed_keys.add(chave)
                    
                    # Escreve no ZIP e remove o conteúdo da memória na hora
                    zf.writestr(f"{pasta}/{chave}.xml", content)
                    
                    # Alimenta o resumo
                    cat = pasta.replace('/', ' - ')
                    resumo[cat] = resumo.get(cat, 0) + 1
                    
                    # Alimenta sequencial
                    if is_p and num:
                        if serie not in sequencias: sequencias[serie] = set()
                        sequencias[serie].add(num)
                
                # Atualização de progresso
                if i % 20 == 0:
                    bar.progress((i + 1) / total)
                    status.caption(f"Processando: {i+1} de {total}")
                    gc.collect()

        if processed_keys:
            st.success(f"✅ {len(processed_keys)} Notas processadas com sucesso!")
            
            # Relatório de Faltantes
            faltantes = []
            for s, nums in sequencias.items():
                if nums:
                    ideal = set(range(min(nums), max(nums) + 1))
                    for f in sorted(list(ideal - nums)):
                        faltantes.append({"Série": s, "Faltante": f})
            
            c1, c2 = st.columns(2)
            with c1:
                st.write("### 📊 Inventário")
                st.table(pd.DataFrame(list(resumo.items()), columns=['Pasta', 'Qtd']))
            
            with c2:
                st.write("### ⚠️ Faltantes")
                if faltantes:
                    df_f = pd.DataFrame(faltantes)
                    st.dataframe(df_f, use_container_width=True)
                else:
                    st.info("Sequência OK!")

            # Botão de Download
            st.divider()
            st.download_button(
                "📥 BAIXAR GARIMPO COMPLETO (.ZIP)",
                data=zip_buffer.getvalue(),
                file_name="garimpo_v4_2.zip",
                use_container_width=True
            )
        
        # Limpeza final agressiva
        zip_buffer.close()
        gc.collect()

st.caption("v4.2 - Arquitetura de escrita direta em disco/buffer.")
