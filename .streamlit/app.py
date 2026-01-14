import streamlit as st
import zipfile
import io
import os
import xml.etree.ElementTree as ET
import re
import pandas as pd
import gc

# --- MOTOR DE EXTRAÇÃO DE DADOS ---
def identify_xml_info(content_bytes, client_cnpj, file_name):
    client_cnpj_clean = "".join(filter(str.isdigit, str(client_cnpj))) if client_cnpj else ""
    
    resumo_nota = {
        "Arquivo": file_name,
        "Chave": "",
        "Tipo": "Outros",
        "Série": "0",
        "Número": 0,
        "Data": "",
        "Valor": 0.0,
        "CNPJ_Emit": "",
        "Pasta": "RECEBIDOS_TERCEIROS/OUTROS",
        "Conteúdo": content_bytes # Mantemos o conteúdo para download individual
    }

    try:
        content_str = content_bytes.decode('utf-8', errors='ignore')
        match_ch = re.search(r'\d{44}', content_str)
        resumo_nota["Chave"] = match_ch.group(0) if match_ch else ""
        
        tag_lower = content_str.lower()
        if '<mod>65</mod>' in tag_lower: resumo_nota["Tipo"] = "NFC-e"
        elif '<infcte' in tag_lower: resumo_nota["Tipo"] = "CT-e"
        elif '<infmdfe' in tag_lower: resumo_nota["Tipo"] = "MDF-e"
        elif '<infnfe' in tag_lower: resumo_nota["Tipo"] = "NF-e"

        s_match = re.search(r'<serie>(\d+)</serie>', content_str)
        resumo_nota["Série"] = s_match.group(1) if s_match else "0"
        
        n_match = re.search(r'<(?:nNF|nCT|nMDF)>(\d+)</(?:nNF|nCT|nMDF)>', content_str)
        resumo_nota["Número"] = int(n_match.group(1)) if n_match else 0
        
        v_match = re.search(r'<(?:vNF|vTPrest|vTPT)>([\d.]+)</(?:vNF|vTPrest|vTPT)>', content_str)
        resumo_nota["Valor"] = float(v_match.group(1)) if v_match else 0.0

        emit_match = re.search(r'<emit>.*?<CNPJ>(\d+)</CNPJ>', content_str, re.DOTALL)
        resumo_nota["CNPJ_Emit"] = emit_match.group(1) if emit_match else ""

        is_p = (client_cnpj_clean != "" and resumo_nota["CNPJ_Emit"] == client_cnpj_clean)
        if not is_p and resumo_nota["Chave"]:
            is_p = (client_cnpj_clean in resumo_nota["Chave"][6:20])

        if is_p:
            resumo_nota["Pasta"] = f"EMITIDOS_CLIENTE/{resumo_nota['Tipo']}/Serie_{resumo_nota['Série']}"
        else:
            resumo_nota["Pasta"] = f"RECEBIDOS_TERCEIROS/{resumo_nota['Tipo']}"
            
        return resumo_nota, is_p
    except:
        return resumo_nota, False

def process_zip_recursively(file_bytes, zf_output, processed_keys, sequencias, relatorio_lista, client_cnpj):
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            for info in z.infolist():
                if info.is_dir(): continue
                content = z.read(info.filename)
                if info.filename.lower().endswith('.zip'):
                    process_zip_recursively(content, zf_output, processed_keys, sequencias, relatorio_lista, client_cnpj)
                elif info.filename.lower().endswith('.xml'):
                    resumo, is_p = identify_xml_info(content, client_cnpj, info.filename)
                    ident = resumo["Chave"] if resumo["Chave"] else info.filename
                    
                    if ident not in processed_keys:
                        processed_keys.add(ident)
                        zf_output.writestr(f"{resumo['Pasta']}/{ident}.xml", content)
                        relatorio_lista.append(resumo)
                        if is_p and resumo["Número"]:
                            s_key = (resumo["Tipo"], resumo["Série"])
                            if s_key not in sequencias: sequencias[s_key] = set()
                            sequencias[s_key].add(resumo["Número"])
    except: pass

# --- INTERFACE ---
st.set_page_config(page_title="Garimpeiro v5.4", layout="wide")
st.title("⛏️ Garimpeiro v5.4 - Com Busca Individual")

with st.sidebar:
    cnpj_input = st.text_input("CNPJ do Cliente (Só números)", placeholder="Ex: 12345678000199")
    st.divider()
    if st.button("🗑️ Limpar Memória"):
        st.cache_data.clear()
        st.rerun()

uploaded_files = st.file_uploader("Suba seus arquivos (XML ou ZIP)", accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 INICIAR GARIMPO COMPLETO", use_container_width=True):
        processed_keys = set()
        sequencias = {} 
        relatorio_lista = []
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf_final:
            for file in uploaded_files:
                f_bytes = file.read()
                if file.name.lower().endswith('.zip'):
                    process_zip_recursively(f_bytes, zf_final, processed_keys, sequencias, relatorio_lista, cnpj_input)
                elif file.name.lower().endswith('.xml'):
                    resumo, is_p = identify_xml_info(f_bytes, cnpj_input, file.name)
                    ident = resumo["Chave"] if resumo["Chave"] else file.name
                    if ident not in processed_keys:
                        processed_keys.add(ident)
                        zf_final.writestr(f"{resumo['Pasta']}/{ident}.xml", f_bytes)
                        relatorio_lista.append(resumo)
                        if is_p and resumo["Número"]:
                            s_key = (resumo["Tipo"], resumo["Série"])
                            if s_key not in sequencias: sequencias[s_key] = set()
                            sequencias[s_key].add(resumo["Número"])
                gc.collect()

        if relatorio_lista:
            st.session_state['relatorio'] = relatorio_lista # Salva na sessão para a busca
            st.session_state['zip_completo'] = zip_buffer.getvalue()
            st.session_state['sequencias'] = sequencias
            st.success(f"✅ {len(processed_keys)} notas mineradas!")

if 'relatorio' in st.session_state:
    df_geral = pd.DataFrame(st.session_state['relatorio'])

    # --- NOVO: BUSCA INDIVIDUAL ---
    st.divider()
    st.write("### 🔍 Localizador Rápido de XML")
    busca = st.text_input("Digite o Número da Nota ou Chave de Acesso para baixar o arquivo avulso:", placeholder="Ex: 12345")
    
    if busca:
        # Busca por número (convertido para string) ou por chave
        resultado = df_geral[
            (df_geral['Número'].astype(str) == busca) | 
            (df_geral['Chave'].str.contains(busca))
        ]
        
        if not resultado.empty:
            st.write(f"✅ Encontrado: {len(resultado)} nota(s)")
            for idx, row in resultado.iterrows():
                with st.container(border=True):
                    st.write(f"**Tipo:** {row['Tipo']} | **Série:** {row['Série']} | **Número:** {row['Número']}")
                    st.caption(f"Chave: {row['Chave']}")
                    st.download_button(
                        label=f"📥 Baixar XML {row['Número']}",
                        data=row['Conteúdo'],
                        file_name=f"{row['Chave'] if row['Chave'] else row['Número']}.xml",
                        key=f"dl_{idx}"
                    )
        else:
            st.error("Nenhuma nota encontrada com esse termo.")

    # --- RELATÓRIO DE FALTANTES ---
    st.divider()
    faltantes_data = []
    for (t, s), nums in st.session_state['sequencias'].items():
        ideal = set(range(min(nums), max(nums) + 1))
        buracos = sorted(list(ideal - nums))
        for b in buracos: faltantes_data.append({"Tipo": t, "Série": s, "Nº Faltante": b})

    col1, col2 = st.columns(2)
    with col1:
        st.write("### 📊 Inventário Final")
        resumo_pastas = df_geral['Pasta'].value_counts().reset_index()
        resumo_pastas.columns = ['Caminho', 'Qtd']
        st.table(resumo_pastas)
    
    with col2:
        st.write("### ⚠️ Notas Faltantes")
        if faltantes_data:
            st.dataframe(pd.DataFrame(faltantes_data), use_container_width=True)
        else:
            st.info("Sequência completa!")

    # DOWNLOAD GERAL
    st.divider()
    st.download_button(
        "📥 BAIXAR ZIP COMPLETO ORGANIZADO",
        st.session_state['zip_completo'],
        "garimpo_v5_4.zip",
        use_container_width=True
    )
