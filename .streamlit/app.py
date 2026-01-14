import streamlit as st
import zipfile
import io
import re

# --- MOTOR DE IDENTIFICAÇÃO LEVE ---
def identify_xml_info(content_bytes, client_cnpj, file_name):
    client_cnpj_clean = "".join(filter(str.isdigit, str(client_cnpj))) if client_cnpj else ""
    resumo = {"Pasta": "RECEBIDOS_TERCEIROS/OUTROS", "Chave": ""}
    try:
        content_str = content_bytes.decode('utf-8', errors='ignore')
        match_ch = re.search(r'\d{44}', content_str)
        resumo["Chave"] = match_ch.group(0) if match_ch else ""
        tag_lower = content_str.lower()
        
        d_type = "NF-e"
        if '<mod>65</mod>' in tag_lower: d_type = "NFC-e"
        elif '<infcte' in tag_lower: d_type = "CT-e"
        elif '<infmdfe' in tag_lower: d_type = "MDF-e"
        
        status = "NORMAIS"
        if '110111' in tag_lower: status = "CANCELADOS"
        elif '<inutnfe' in tag_lower: status = "INUTILIZADOS"
        
        emit_match = re.search(r'<(?:emit|infInut|detEvento)>.*?<CNPJ>(\d+)</CNPJ>', content_str, re.DOTALL)
        cnpj_emit = emit_match.group(1) if emit_match else ""
        
        if client_cnpj_clean and (cnpj_emit == client_cnpj_clean or client_cnpj_clean in resumo["Chave"][6:20]):
            resumo["Pasta"] = f"EMITIDOS_CLIENTE/{d_type}/{status}"
        else:
            resumo["Pasta"] = f"RECEBIDOS_TERCEIROS/{d_type}"
        return resumo
    except:
        return resumo

# --- INTERFACE LIMPA ---
st.set_page_config(page_title="O Garimpeiro", page_icon="⛏️")

# Blindagem Visual
st.markdown("<style>#MainMenu, footer, header {visibility: hidden;}</style>", unsafe_allow_html=True)

st.title("⛏️ O GARIMPEIRO")

cnpj_cliente = st.sidebar.text_input("CNPJ DO CLIENTE (Só números)")

uploaded_files = st.file_uploader("Arraste seus XMLs ou ZIPs aqui", accept_multiple_files=True)

if uploaded_files and st.button("🚀 INICIAR GARIMPO"):
    processed_keys = set()
    output_zip = io.BytesIO()
    
    with st.spinner("Minerando..."):
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in uploaded_files:
                f_bytes = f.read()
                
                # Tratar ZIPs dentro do upload
                if f.name.lower().endswith('.zip'):
                    with zipfile.ZipFile(io.BytesIO(f_bytes)) as z_in:
                        for name in z_in.namelist():
                            if name.lower().endswith('.xml'):
                                xml_data = z_in.read(name)
                                info = identify_xml_info(xml_data, cnpj_cliente, name)
                                if info["Chave"] not in processed_keys:
                                    processed_keys.add(info["Chave"])
                                    zf.writestr(f"{info['Pasta']}/{name}", xml_data)
                
                # Tratar XMLs avulsos
                elif f.name.lower().endswith('.xml'):
                    info = identify_xml_info(f_bytes, cnpj_cliente, f.name)
                    if info["Chave"] not in processed_keys:
                        processed_keys.add(info["Chave"])
                        zf.writestr(f"{info['Pasta']}/{f.name}", f_bytes)
    
    st.success("✅ Garimpo concluído!")
    st.download_button(
        label="📥 BAIXAR GARIMPO FINAL",
        data=output_zip.getvalue(),
        file_name="garimpo_final.zip",
        mime="application/zip"
    )
