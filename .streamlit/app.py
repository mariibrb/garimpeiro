import streamlit as st
import zipfile
import io
import os
import xml.etree.ElementTree as ET
import re
import pandas as pd
import gc

# --- FUNÇÕES DE IDENTIFICAÇÃO (FISCAL) ---
def get_xml_key(root, content_str):
    try:
        ch_tag = root.find(".//chNFe") or root.find(".//chCTe") or root.find(".//chMDFe")
        if ch_tag is not None and ch_tag.text: return ch_tag.text
        inf_tags = [".//infNFe", ".//infCTe", ".//infMDFe", ".//infProc"]
        for tag in inf_tags:
            element = root.find(tag)
            if element is not None and 'Id' in element.attrib:
                key = re.sub(r'\D', '', element.attrib['Id'])
                if len(key) == 44: return key
        found = re.findall(r'\d{44}', content_str)
        if found: return found[0]
    except: pass
    return None

def identify_xml_info(content_bytes, client_cnpj):
    client_cnpj = "".join(filter(str.isdigit, client_cnpj))
    try:
        content_str = content_bytes.decode('utf-8', errors='ignore')
        # Limpeza agressiva para economizar RAM
        clean_content = content_str.replace('xmlns="http://www.portalfiscal.inf.br/nfe"', '')
        clean_content = clean_content.replace('xmlns="http://www.portalfiscal.inf.br/cte"', '')
        clean_content = clean_content.replace('xmlns="http://www.portalfiscal.inf.br/mdfe"', '')
        
        root = ET.fromstring(clean_content)
        
        doc_type = "Outros"
        tag_lower = content_str.lower()
        if '<infnfe' in tag_lower: doc_type = "NFC-e" if '<mod>65</mod>' in tag_lower else "NF-e"
        elif '<infcte' in tag_lower: doc_type = "CT-e"
        elif '<infmdfe' in tag_lower: doc_type = "MDF-e"
        elif '<evento' in tag_lower or '<infresevento' in tag_lower: doc_type = "Eventos"
        
        emit_cnpj = ""; serie = "0"; numero = None
        emit = root.find(".//emit/CNPJ")
        if emit is not None: emit_cnpj = "".join(filter(str.isdigit, emit.text))
        
        serie_tag = root.find(".//ide/serie")
        if serie_tag is not None: serie = serie_tag.text
        
        nNF_tag = root.find(".//ide/nNF") or root.find(".//ide/nCT") or root.find(".//ide/nMDF")
        if nNF_tag is not None: numero = int(nNF_tag.text)

        chave = get_xml_key(root, content_str)
        is_propria = (client_cnpj and emit_cnpj == client_cnpj)
        
        pasta_final = f"EMITIDOS_CLIENTE/{doc_type}/Serie_{serie}" if is_propria else f"RECEBIDOS_TERCEIROS/{doc_type}"
        return pasta_final, chave, is_propria, serie, numero
    except:
        return "NAO_IDENTIFICADOS", None, False, "0", None

def process_recursively(file_name, file_bytes, xml_files_dict, client_cnpj, processed_keys, sequencias_proprias):
    if file_name.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                for info in z.infolist():
                    if info.is_dir(): continue
                    process_recursively(info.filename, z.read(info.filename), xml_files_dict, client_cnpj, processed_keys, sequencias_proprias)
        except: pass
    elif file_name.lower().endswith('.xml'):
        subfolder, chave, is_propria, serie, numero = identify_xml_info(file_bytes, client_cnpj)
        if chave:
            if chave not in processed_keys:
                processed_keys.add(chave)
                xml_files_dict[f"{subfolder}/{chave}.xml"] = file_bytes
                if is_propria and numero:
                    if serie not in sequencias_proprias: sequencias_proprias[serie] = set()
                    sequencias_proprias[serie].add(numero)

# --- INTERFACE ---
st.set_page_config(page_title="Garimpeiro v3.6", page_icon="⛏️", layout="wide")
st.title("⛏️ Garimpeiro de XML 💎")

with st.sidebar:
    st.header("⚙️ Configurações")
    cnpj_input = st.text_input("CNPJ do Cliente", placeholder="00000000000000")
    if st.button("🗑️ Limpar Memória/Sessão"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.info("v3.6 - Estabilidade por Gerenciamento de Memória")

uploaded_files = st.file_uploader("Arraste sua pasta ou arquivos aqui", accept_multiple_files=True)

if uploaded_files:
    total = len(uploaded_files)
    if st.button("🚀 INICIAR GARIMPO TOTAL", use_container_width=True):
        all_xml_data = {}
        processed_keys = set()
        sequencias_proprias = {}

        progress_box = st.container(border=True)
        with progress_box:
            st.write("### 📈 Progresso do Garimpo")
            barra_geral = st.progress(0)
            c1, c2, c3 = st.columns(3)
            m_perc = c1.empty()
            m_qtd = c2.empty()
            m_rest = c3.empty()

        for i, file in enumerate(uploaded_files):
            process_recursively(file.name, file.read(), all_xml_data, cnpj_input, processed_keys, sequencias_proprias)
            
            prog = (i + 1) / total
            barra_geral.progress(prog)
            m_perc.metric("Status", f"{int(prog * 100)}%")
            m_qtd.metric("Processados", f"{i+1} de {total}")
            m_rest.metric("Faltam", total - (i+1))
            
            if i % 100 == 0: gc.collect() # Limpeza pesada a cada 100 arquivos

        if all_xml_data:
            st.success(f"✨ Concluído! {len(all_xml_data)} XMLs únicos.")
            
            # 1. INVENTÁRIO
            st.write("### 📊 Inventário do Tesouro")
            resumo = {}
            for path in all_xml_data.keys():
                cat = " - ".join(path.split('/')[:-1]).replace('_', ' ')
                resumo[cat] = resumo.get(cat, 0) + 1
            st.table(pd.DataFrame(list(resumo.items()), columns=['Categoria / Série', 'Quantidade']))

            # 2. FALTANTES
            st.divider()
            st.write("### ⚠️ Notas de Emissão Própria Faltantes")
            faltantes_list = []
            for serie, numeros in sequencias_proprias.items():
                if numeros:
                    seq_ideal = set(range(min(numeros), max(numeros) + 1))
                    for f in sorted(list(seq_ideal - numeros)):
                        faltantes_list.append({"Série": serie, "Número Faltante": f})
            
            if faltantes_list:
                df_f = pd.DataFrame(faltantes_list)
                st.dataframe(df_f, use_container_width=True)
                st.download_button("📥 Baixar Faltantes (CSV)", df_f.to_csv(index=False).encode('utf-8'), "faltantes.csv")
            else:
                st.info("✅ Sequência numérica completa!")

            # GERADOR DE ZIP
            zip_out = io.BytesIO()
            with zipfile.ZipFile(zip_out, "w", zipfile.ZIP_DEFLATED) as zf:
                for path, data in all_xml_data.items():
                    zf.writestr(path, data)
                if faltantes_list:
                    zf.writestr("RELATORIOS/faltantes.csv", pd.DataFrame(faltantes_list).to_csv(index=False))
            
            st.download_button("📥 BAIXAR TUDO (.ZIP)", zip_out.getvalue(), "garimpo_v3_6.zip", use_container_width=True)
            
            # Limpeza final de RAM
            all_xml_data.clear()
            processed_keys.clear()
            gc.collect()

st.divider()
st.caption("FoxHelper v3.6: Proteção contra estouro de memória ativada.")
