import streamlit as st
import zipfile
import io
import os
import xml.etree.ElementTree as ET
import re
import pandas as pd
import gc

# --- MOTOR DE IDENTIFICAÇÃO (CORRIGIDO PARA EVENTOS PRÓPRIOS) ---
def identify_xml_info(content_bytes, client_cnpj, file_name):
    client_cnpj_clean = "".join(filter(str.isdigit, str(client_cnpj))) if client_cnpj else ""
    resumo_nota = {
        "Arquivo": file_name, "Chave": "", "Tipo": "Outros", "Série": "0",
        "Número": 0, "Data": "", "Valor": 0.0, "CNPJ_Emit": "",
        "Pasta": "RECEBIDOS_TERCEIROS/OUTROS", "Conteúdo": content_bytes
    }
    try:
        content_str = content_bytes.decode('utf-8', errors='ignore')
        
        # 1. Identifica a Chave de Acesso
        match_ch = re.search(r'\d{44}', content_str)
        resumo_nota["Chave"] = match_ch.group(0) if match_ch else ""
        
        # 2. Identifica o Tipo de Documento e Status
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

        # 3. Série e Número (Regex)
        s_match = re.search(r'<(?:serie|serie)>(\d+)</(?:serie|serie)>', content_str)
        resumo_nota["Série"] = s_match.group(1) if s_match else "0"
        
        n_match = re.search(r'<(?:nNF|nCT|nMDF|nNFIni|nNFIn)>(\d+)</(?:nNF|nCT|nMDF|nNFIni|nNFIn)>', content_str)
        resumo_nota["Número"] = int(n_match.group(1)) if n_match else 0
        
        # 4. Identifica o CNPJ do Emitente (quem enviou o arquivo)
        # Em inutilização e eventos, a tag CNPJ fica dentro de infInut ou detEvento
        emit_match = re.search(r'<(?:emit|infInut|detEvento)>.*?<CNPJ>(\d+)</CNPJ>', content_str, re.DOTALL)
        resumo_nota["CNPJ_Emit"] = emit_match.group(1) if emit_match else ""

        # 5. LÓGICA DE CLASSIFICAÇÃO (EMISSÃO PRÓPRIA VS TERCEIROS)
        is_p = False
        if client_cnpj_clean:
            # Se o CNPJ emitente bater OU se o CNPJ do cliente estiver na chave (posição 6 a 20)
            if resumo_nota["CNPJ_Emit"] == client_cnpj_clean:
                is_p = True
            elif resumo_nota["Chave"] and client_cnpj_clean in resumo_nota["Chave"][6:20]:
                is_p = True

        if is_p:
            # Se for do cliente, vai para EMITIDOS e separa por Status (Normal, Cancelado, Inutilizado)
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
                    # Para inutilização, a chave pode não ter 44 dígitos, usamos o nome do arquivo como backup
                    ident = resumo["Chave"] if len(resumo["Chave"]) == 44 else f"{resumo['Pasta']}_{resumo['Número']}_{info.filename}"
                    if ident not in processed_keys:
                        processed_keys.add(ident)
                        zf_output.writestr(f"{resumo['Pasta']}/{info.filename}", content)
                        relatorio_lista.append(resumo)
                        # Só entra no sequencial de faltantes se for emissão própria e não for inutilizada (ou entra para "preencher" o buraco)
                        if is_p and resumo["Número"] > 0:
                            s_key = (resumo["Tipo"], resumo["Série"])
                            if s_key not in sequencias: sequencias[s_key] = set()
                            sequencias[s_key].add(resumo["Número"])
    except: pass

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Garimpeiro v5.7", layout="wide")
st.title("⛏️ Garimpeiro v5.7 - Especialista em Emitidas")

if 'garimpo_ok' not in st.session_state: st.session_state['garimpo_ok'] = False

with st.sidebar:
    cnpj_input = st.text_input("CNPJ do Cliente (SÓ NÚMEROS)", placeholder="Ex: 12345678000199")
    if st.button("🗑️ Resetar Sistema"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

uploaded_files = st.file_uploader("Suba seus arquivos (XML ou ZIP)", accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 INICIAR GARIMPO E SEPARAR EVENTOS", use_container_width=True):
        processed_keys, sequencias, relatorio_lista = set(), {}, []
        zip_buffer = io.BytesIO()
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
                        if is_p and resumo["Número"] > 0:
                            s_key = (resumo["Tipo"], resumo["Série"])
                            if s_key not in sequencias: sequencias[s_key] = set()
                            sequencias[s_key].add(resumo["Número"])
                status_text.write(f"⛏️ Minerando... {len(processed_keys)} arquivos organizados.")
                gc.collect()

        if relatorio_lista:
            st.session_state.update({'relatorio': relatorio_lista, 'zip_completo': zip_buffer.getvalue(), 'sequencias': sequencias, 'garimpo_ok': True})
            st.success("✅ Organização concluída!")

if st.session_state.get('garimpo_ok'):
    df = pd.DataFrame(st.session_state['relatorio'])
    
    st.divider()
    st.write("### 📊 Inventário de Emissão Própria (Emitidas)")
    emitidas_df = df[df['Pasta'].str.contains("EMITIDOS_CLIENTE")]
    if not emitidas_df.empty:
        resumo_emit = emitidas_df['Pasta'].value_counts().reset_index()
        resumo_emit.columns = ['Pasta / Categoria', 'Quantidade']
        st.table(resumo_emit)
    else:
        st.warning("Nenhuma nota de emissão própria encontrada. Verifique o CNPJ digitado.")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.write("### 📂 Outras Pastas (Recebidas)")
        recebidas_df = df[df['Pasta'].str.contains("RECEBIDOS_TERCEIROS")]
        st.table(recebidas_df['Pasta'].value_counts().reset_index().rename(columns={'Pasta': 'Caminho', 'count': 'Qtd'}))
    
    with col2:
        st.write("### ⚠️ Buracos na Sequência (Faltantes)")
        faltantes = []
        for (t, s), nums in st.session_state['sequencias'].items():
            if nums:
                ideal = set(range(min(nums), max(nums) + 1))
                for b in sorted(list(ideal - nums)): faltantes.append({"Tipo": t, "Série": s, "Nº": b})
        if faltantes: st.dataframe(pd.DataFrame(faltantes), use_container_width=True)
        else: st.info("Sequência perfeita!")

    st.download_button("📥 BAIXAR TUDO SEPARADO (.ZIP)", st.session_state['zip_completo'], "garimpo_v5_7.zip", use_container_width=True)
