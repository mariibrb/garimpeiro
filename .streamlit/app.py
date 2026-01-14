import streamlit as st
import zipfile
import io
import xml.etree.ElementTree as ET
import re
import pandas as pd
import gc

# Limpa o cache toda vez que a página inicia para evitar o "Oh no" infinito
st.cache_data.clear()
st.cache_resource.clear()

def identify_xml_info(content_bytes, client_cnpj):
    client_cnpj = "".join(filter(str.isdigit, client_cnpj)) if client_cnpj else ""
    try:
        content_str = content_bytes.decode('utf-8', errors='ignore')
        # Regex rápido para Chave e Tipo (Gasta quase zero de memória)
        chave = None
        match = re.search(r'\d{44}', content_str)
        if match: chave = match.group(0)
        
        doc_type = "NF-e"
        if '<mod>65</mod>' in content_str: doc_type = "NFC-e"
        elif '<infCTe' in content_str: doc_type = "CT-e"
        elif '<infMDFe' in content_str: doc_type = "MDF-e"
        
        # XML Parser simples apenas para o que é essencial
        root = ET.fromstring(re.sub(r'\sxmlns="[^"]+"', '', content_str, count=1))
        
        emit_cnpj = ""
        emit = root.find(".//emit/CNPJ")
        if emit is not None: emit_cnpj = "".join(filter(str.isdigit, emit.text))
        
        serie = "0"
        s_tag = root.find(".//ide/serie")
        if s_tag is not None: serie = s_tag.text
        
        num = None
        n_tag = root.find(".//ide/nNF") or root.find(".//ide/nCT") or root.find(".//ide/nMDF")
        if n_tag is not None: num = int(n_tag.text)

        is_propria = (client_cnpj != "" and emit_cnpj == client_cnpj)
        pasta = f"EMITIDOS/Serie_{serie}" if is_propria else f"RECEBIDOS/{doc_type}"
        
        return pasta, chave, is_propria, serie, num
    except:
        return "ERRO", None, False, "0", None

st.set_page_config(page_title="Garimpeiro v4.0", layout="centered")
st.title("⛏️ Garimpeiro v4.0")

cnpj_input = st.text_input("CNPJ do Cliente (Só números)", key="cnpj_val")

# accept_multiple_files consome muita RAM. Tente subir um ZIP se for muita coisa.
uploaded_files = st.file_uploader("Suba seus XMLs", accept_multiple_files=True)

if uploaded_files and st.button("🚀 INICIAR"):
    all_data = {}
    sequencias = {}
    
    prog = st.progress(0)
    for i, file in enumerate(uploaded_files):
        bytes_data = file.read()
        pasta, chave, is_p, serie, num = identify_xml_info(bytes_data, cnpj_input)
        
        if chave:
            all_data[f"{pasta}/{chave}.xml"] = bytes_data
            if is_p and num:
                if serie not in sequencias: sequencias[serie] = set()
                sequencias[serie].add(num)
        
        prog.progress((i + 1) / len(uploaded_files))
        if i % 100 == 0: gc.collect()

    if all_data:
        st.success("✅ Processado!")
        
        # Relatório de Faltantes
        faltantes = []
        for s, nums in sequencias.items():
            ideal = set(range(min(nums), max(nums) + 1))
            buracos = sorted(list(ideal - nums))
            for b in buracos:
                faltantes.append({"Série": s, "Faltante": b})
        
        if faltantes:
            st.write("### ⚠️ Notas Faltantes")
            st.dataframe(pd.DataFrame(faltantes))

        # ZIP
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            for p, d in all_data.items():
                zf.writestr(p, d)
        
        st.download_button("📥 BAIXAR ZIP", zip_buf.getvalue(), "garimpo.zip")
        
        # Limpeza total após o botão aparecer
        all_data.clear()
        gc.collect()
