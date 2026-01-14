import streamlit as st
import zipfile
import io
import os
import xml.etree.ElementTree as ET
import re
import pandas as pd
import gc

# --- MOTOR DE IDENTIFICAÇÃO ---
def identify_xml_info(content_bytes, client_cnpj, file_name):
    client_cnpj_clean = "".join(filter(str.isdigit, str(client_cnpj))) if client_cnpj else ""
    resumo_nota = {
        "Arquivo": file_name, "Chave": "", "Tipo": "Outros", "Série": "0",
        "Número": 0, "Data": "", "Valor": 0.0, "CNPJ_Emit": "",
        "Pasta": "RECEBIDOS_TERCEIROS/OUTROS", "Conteúdo": content_bytes
    }
    try:
        content_str = content_bytes.decode('utf-8', errors='ignore')
        match_ch = re.search(r'\d{44}', content_str)
        resumo_nota["Chave"] = match_ch.group(0) if match_ch else ""
        
        tag_lower = content_str.lower()
        d_type = "NF-e"
        if '<mod>65</mod>' in tag_lower: d_type = "NFC-e"
        elif '<infcte' in tag_lower: d_type = "CT-e"
        elif '<infmdfe' in tag_lower: d_type = "MDF-e"
        
        status = "NORMAIS"
        if '<procevento' in tag_lower or '<revento' in tag_lower:
            status = "EVENTOS_CANCELAMENTOS"
            if '110111' in tag_lower: status = "CANCELADOS"
            elif '110110' in tag_lower: status = "CARTA_CORRECAO"
        elif '<inutnfe' in tag_lower or '<procinut' in tag_lower:
            status = "INUTILIZADOS"
            d_type = "Inutilizacoes"

        resumo_nota["Tipo"] = d_type
        s_match = re.search(r'<(?:serie|serie)>(\d+)</?:serie|serie>', content_str)
        resumo_nota["Série"] = s_match.group(1) if s_match else "0"
        
        n_match = re.search(r'<(?:nNF|nCT|nMDF|nNFIni)>(\d+)</(?:nNF|nCT|nMDF|nNFIni)>', content_str)
        resumo_nota["Número"] = int(n_match.group(1)) if n_match else 0
        
        emit_match = re.search(r'<(?:emit|infInut|detEvento)>.*?<CNPJ>(\d+)</CNPJ>', content_str, re.DOTALL)
        resumo_nota["CNPJ_Emit"] = emit_match.group(1) if emit_match else ""

        is_p = False
        if client_cnpj_clean:
            if resumo_nota["CNPJ_Emit"] == client_cnpj_clean: is_p = True
            elif resumo_nota["Chave"] and client_cnpj_clean in resumo_nota["Chave"][6:20]: is_p = True

        if is_p:
            resumo_nota["Pasta"] = f"EMITIDOS_CLIENTE/{d_type}/{status}/Serie_{resumo_nota['Série']}"
        else:
            resumo_nota["Pasta"] = f"RECEBIDOS_TERCEIROS/{d_type}"
            
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
                    ident = resumo["Chave"] if len(resumo["Chave"]) == 44 else f"{resumo['Pasta']}_{resumo['Número']}_{info.filename}"
                    if ident not in processed_keys:
                        processed_keys.add(ident)
                        zf_output.writestr(f"{resumo['Pasta']}/{info.filename}", content)
                        relatorio_lista.append(resumo)
                        if is_p and resumo["Número"] > 0:
                            # SEPARAÇÃO CRÍTICA: Inutilização não entra no mapa de sequências para auditoria de buracos
                            if resumo["Tipo"] != "Inutilizacoes":
                                doc_base = "NFC-e" if "NFC-e" in resumo["Pasta"] else ("NF-e" if "NF-e" in resumo["Pasta"] else resumo["Tipo"])
                                s_key = (doc_base, resumo["Série"])
                                if s_key not in sequencias: sequencias[s_key] = set()
                                sequencias[s_key].add(resumo["Número"])
    except: pass

# --- INTERFACE ---
st.set_page_config(page_title="Garimpeiro v6.3", layout="wide", page_icon="⛏️")
st.title("⛏️ Garimpeiro v6.3 - Auditoria sem Inutilizados")

if 'garimpo_ok' not in st.session_state: st.session_state['garimpo_ok'] = False
if 'df_faltantes' not in st.session_state: st.session_state['df_faltantes'] = None

with st.sidebar:
    cnpj_input = st.text_input("CNPJ do Cliente (SÓ NÚMEROS)", placeholder="Ex: 12345678000199")
    if st.button("🗑️ Resetar Tudo"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

uploaded_files = st.file_uploader("Suba seus arquivos (XML ou ZIP)", accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 INICIAR GARIMPO", use_container_width=True):
        processed_keys, sequencias, relatorio_lista = set(), {}, []
        zip_buffer = io.BytesIO()
        prog_bar = st.progress(0)
        status_text = st.empty()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf_final:
            for i, file in enumerate(uploaded_files):
                f_bytes = file.read()
                if file.name.lower().endswith('.zip'):
                    process_zip_recursively(f_bytes, zf_final, processed_keys, sequencias, relatorio_lista, cnpj_input)
                elif file.name.lower().endswith('.xml'):
                    resumo, is_p = identify_xml_info(f_bytes, cnpj_input, file.name)
                    ident = resumo["Chave"] if len(resumo["Chave"]) == 44 else file.name
                    if ident not in processed_keys:
                        processed_keys.add(ident)
                        zf_final.writestr(f"{resumo['Pasta']}/{file.name}", f_bytes)
                        relatorio_lista.append(resumo)
                        if is_p and resumo["Número"] > 0 and resumo["Tipo"] != "Inutilizacoes":
                            doc_base = "NFC-e" if "NFC-e" in resumo["Pasta"] else ("NF-e" if "NF-e" in resumo["Pasta"] else resumo["Tipo"])
                            s_key = (doc_base, resumo["Série"])
                            if s_key not in sequencias: sequencias[s_key] = set()
                            sequencias[s_key].add(resumo["Número"])
                
                prog_bar.progress((i + 1) / len(uploaded_files))
                status_text.info(f"⛏️ Minerando... {len(processed_keys)} arquivos.")
                gc.collect()

            # --- AUDITORIA DE BURACOS (Apenas Notas de Venda) ---
            faltantes_lista = []
            for (t, s), nums in sequencias.items():
                if nums:
                    ideal = set(range(min(nums), max(nums) + 1))
                    buracos = sorted(list(ideal - nums))
                    for b in buracos:
                        faltantes_lista.append({"Tipo": t, "Série": s, "Nº Faltante": b})
            
            st.session_state['df_faltantes'] = pd.DataFrame(faltantes_lista) if faltantes_lista else None

        if relatorio_lista:
            st.session_state.update({'relatorio': relatorio_lista, 'zip_completo': zip_buffer.getvalue(), 'garimpo_ok': True})
            status_text.success("✅ Concluído! Inutilizações ignoradas no relatório de buracos.")

if st.session_state.get('garimpo_ok'):
    df = pd.DataFrame(st.session_state['relatorio'])
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("### 📂 Resumo de Arquivos")
        st.table(df['Pasta'].value_counts().reset_index().rename(columns={'Pasta': 'Caminho', 'count': 'Qtd'}))
    
    with col2:
        st.write("### ⚠️ Buracos (Apenas NF-e/NFC-e)")
        df_f = st.session_state.get('df_faltantes')
        if df_f is not None and not df_f.empty:
            st.warning(f"Existem {len(df_f)} notas de venda faltando.")
            st.dataframe(df_f, use_container_width=True)
        else:
            st.info("Nenhuma nota de venda faltando na sequência.")

    st.divider()
    st.download_button("📥 BAIXAR ZIP COMPLETO", st.session_state['zip_completo'], "garimpo_v6_3.zip", use_container_width=True)
