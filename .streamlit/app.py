import streamlit as st
import zipfile
import io
import os
import re
import pandas as pd
import random

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

def process_zip_recursively(file_bytes, zf_output, processed_keys, relatorio_lista, client_cnpj):
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            for info in z.infolist():
                if info.is_dir(): continue
                content = z.read(info.filename)
                if info.filename.lower().endswith('.zip'):
                    process_zip_recursively(content, zf_output, processed_keys, relatorio_lista, client_cnpj)
                elif info.filename.lower().endswith('.xml'):
                    resumo, is_p = identify_xml_info(content, client_cnpj, info.filename)
                    ident = resumo["Chave"] if len(resumo["Chave"]) == 44 else f"{resumo['Pasta']}_{resumo['Número']}_{info.filename}"
                    if ident not in processed_keys:
                        processed_keys.add(ident)
                        zf_output.writestr(f"{resumo['Pasta']}/{info.filename}", content)
                        relatorio_lista.append(resumo)
    except: pass

def format_cnpj(cnpj):
    cnpj = "".join(filter(str.isdigit, cnpj))
    if len(cnpj) <= 14:
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    return cnpj

# --- DESIGN E BLINDAGEM ---
st.set_page_config(page_title="O Garimpeiro", layout="wide", page_icon="⛏️")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    header {visibility: hidden !important;}
    .stApp { background-color: #f7f3f0; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #EADBC8 0%, #D2B48C 100%) !important; border-right: 3px solid #b8860b; }
    [data-testid="stSidebar"] * { color: #2b1e16 !important; font-weight: 800 !important; }
    h1, h2, h3, h4, p, label { color: #2b1e16 !important; font-family: 'Playfair Display', serif; font-weight: 800 !important; }
    
    .stDownloadButton > button {
        background: linear-gradient(180deg, #fcf6ba 0%, #d4af37 40%, #aa771c 100%) !important;
        color: #2b1e16 !important;
        border: 3px solid #8a6d3b !important;
        padding: 30px !important;
        font-weight: 900 !important;
        font-size: 22px !important;
        border-radius: 20px !important;
        width: 100% !important;
        text-transform: uppercase !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>⛏️ O GARIMPEIRO</h1>", unsafe_allow_html=True)

if 'confirmado' not in st.session_state: st.session_state['confirmado'] = False
if 'garimpo_ok' not in st.session_state: st.session_state['garimpo_ok'] = False

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### ⛏️ Painel de Extração")
    raw_cnpj = st.text_input("CNPJ DO CLIENTE", placeholder="Digite os números")
    cnpj_limpo = "".join(filter(str.isdigit, raw_cnpj))
    if len(cnpj_limpo) == 14:
        st.markdown(f"**CLIENTE ATIVO:**\n`{format_cnpj(raw_cnpj)}`")
        if st.button("✅ LIBERAR OPERAÇÃO"):
            st.session_state['confirmado'] = True
            st.rerun()
    st.divider()
    if st.button("🗑️ RESETAR SISTEMA"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

# --- ÁREA DE TRABALHO ---
if not st.session_state['confirmado']:
    st.info("💰 Para iniciar, identifique o CNPJ no menu lateral e clique em **LIBERAR OPERAÇÃO**.")
else:
    if not st.session_state['garimpo_ok']:
        st.markdown(f"### 📦 JAZIDA DE ARQUIVOS: {format_cnpj(raw_cnpj)}")
        uploaded_files = st.file_uploader("Arraste seus XMLs ou ZIPs aqui:", accept_multiple_files=True)

        if uploaded_files:
            if st.button("🚀 INICIAR GRANDE GARIMPO"):
                processed_keys, relatorio_lista = set(), []
                
                # 1. ZIP ORGANIZADO
                buf_org = io.BytesIO()
                with zipfile.ZipFile(buf_org, "w", zipfile.ZIP_DEFLATED) as zf:
                    for f in uploaded_files:
                        f_bytes = f.read()
                        if f.name.lower().endswith('.zip'):
                            process_zip_recursively(f_bytes, zf, processed_keys, relatorio_lista, cnpj_limpo)
                        elif f.name.lower().endswith('.xml'):
                            resumo, is_p = identify_xml_info(f_bytes, cnpj_limpo, f.name)
                            ident = resumo["Chave"] if len(resumo["Chave"]) == 44 else f.name
                            if ident not in processed_keys:
                                processed_keys.add(ident)
                                zf.writestr(f"{resumo['Pasta']}/{f.name}", f_bytes)
                                relatorio_lista.append(resumo)
                
                # 2. ZIP TODOS (COM PASTA TODOS INTERNA)
                buf_todos = io.BytesIO()
                with zipfile.ZipFile(buf_todos, "w", zipfile.ZIP_DEFLATED) as zf_t:
                    for item in relatorio_lista:
                        zf_t.writestr(f"TODOS/{item['Arquivo']}", item['Conteúdo'])

                # SALVAR TUDO
                st.session_state['zip_download_org'] = buf_org.getvalue()
                st.session_state['zip_download_todos'] = buf_todos.getvalue()
                st.session_state['garimpo_ok'] = True
                st.rerun()
    else:
        # --- EXIBIÇÃO FINAL (AQUI NÃO TEM ERRO) ---
        st.success("💰 MINERAÇÃO FINALIZADA!")
        
        st.markdown("## 📥 BAIXAR SEUS ARQUIVOS")
        
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                label="📦 BAIXAR TODOS (PASTA ÚNICA)",
                data=st.session_state['zip_download_todos'],
                file_name="TODOS.zip",
                mime="application/zip"
            )
            st.markdown("<p style='text-align:center;'>Pasta única 'TODOS' com tudo misturado.</p>", unsafe_allow_html=True)

        with c2:
            st.download_button(
                label="📂 BAIXAR GARIMPO FINAL (ORGANIZADO)",
                data=st.session_state['zip_download_org'],
                file_name="garimpo_final.zip",
                mime="application/zip"
            )
            st.markdown("<p style='text-align:center;'>Pastas separadas (Emitidas/Recebidas).</p>", unsafe_allow_html=True)

        st.divider()
        if st.button("⛏️ FAZER NOVO GARIMPO"):
            st.session_state['garimpo_ok'] = False
            st.rerun()
