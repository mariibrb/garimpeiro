import streamlit as st
import zipfile
import io
import os
import xml.etree.ElementTree as ET
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
                        if is_p and resumo["Número"] > 0 and "EMITIDOS" in resumo["Pasta"]:
                            if resumo["Tipo"] in ["NF-e", "NFC-e", "CT-e", "MDF-e"]:
                                s_key = (resumo["Tipo"], resumo["Série"])
                                if s_key not in sequencias: sequencias[s_key] = set()
                                sequencias[s_key].add(resumo["Número"])
    except: pass

def format_cnpj(cnpj):
    cnpj = "".join(filter(str.isdigit, cnpj))
    if len(cnpj) > 14: cnpj = cnpj[:14]
    if len(cnpj) <= 2: return cnpj
    if len(cnpj) <= 5: return f"{cnpj[:2]}.{cnpj[2:]}"
    if len(cnpj) <= 8: return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:]}"
    if len(cnpj) <= 12: return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:]}"
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

# --- DESIGN PREMIUM REFINADO ---
st.set_page_config(page_title="O Garimpeiro", layout="wide", page_icon="⛏️")

st.markdown("""
    <style>
    .stApp { background-color: #f7f3f0; }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #EADBC8 0%, #D2B48C 100%) !important;
        border-right: 3px solid #b8860b;
    }
    [data-testid="stSidebar"] * { color: #2b1e16 !important; font-weight: 800 !important; }
    [data-testid="stSidebar"] div.stButton > button {
        background: linear-gradient(180deg, #fcf6ba 0%, #d4af37 100%) !important;
        color: #2b1e16 !important; border: 2px solid #8a6d3b !important; font-weight: 900 !important;
    }
    h1, h2, h3, h4, p, label, .stMetric label { color: #2b1e16 !important; font-family: 'Playfair Display', serif; font-weight: 800 !important; }
    h1 { font-size: 3.5rem !important; text-shadow: 2px 2px 0px #fff; }
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #ffffff 0%, #fff9e6 100%);
        border: 2px solid #d4af37; border-radius: 20px; padding: 25px; box-shadow: 8px 8px 20px rgba(0,0,0,0.12);
    }
    [data-testid="stMetricValue"] { color: #a67c00 !important; font-weight: 900 !important; font-size: 2.5rem !important; }
    div.stButton > button:first-child {
        background: linear-gradient(180deg, #fcf6ba 0%, #d4af37 40%, #aa771c 100%);
        color: #2b1e16 !important; border: 2px solid #8a6d3b; padding: 20px 40px;
        font-size: 22px; font-weight: 900 !important; border-radius: 50px; box-shadow: 0 6px 20px rgba(0,0,0,0.25);
        width: 100%; text-transform: uppercase;
    }
    .gold-item { position: fixed; top: -50px; z-index: 9999; pointer-events: none; animation: drop 3.5s linear forwards; }
    @keyframes drop { 0% { transform: translateY(0) rotate(0deg); opacity: 1; } 100% { transform: translateY(110vh) rotate(720deg); opacity: 0; } }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>⛏️ O GARIMPEIRO</h1>", unsafe_allow_html=True)

if 'garimpo_ok' not in st.session_state: st.session_state['garimpo_ok'] = False
if 'confirmado' not in st.session_state: st.session_state['confirmado'] = False

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
    st.markdown(f"### 📦 ARQUIVOS: {format_cnpj(raw_cnpj)}")
    uploaded_files = st.file_uploader("Arraste seus XMLs ou ZIPs aqui:", accept_multiple_files=True)

    if uploaded_files:
        if st.button("🚀 INICIAR GARIMPO"):
            processed_keys, sequencias, relatorio_lista = set(), {}, []
            zip_buffer = io.BytesIO()
            
            with st.status("⛏️ Minerando...", expanded=True) as status:
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf_final:
                    for i, file in enumerate(uploaded_files):
                        f_bytes = file.read()
                        if file.name.lower().endswith('.zip'):
                            process_zip_recursively(f_bytes, zf_final, processed_keys, sequencias, relatorio_lista, cnpj_limpo)
                        elif file.name.lower().endswith('.xml'):
                            resumo, is_p = identify_xml_info(f_bytes, cnpj_limpo, file.name)
                            ident = resumo["Chave"] if len(resumo["Chave"]) == 44 else file.name
                            if ident not in processed_keys:
                                processed_keys.add(ident)
                                zf_final.writestr(f"{resumo['Pasta']}/{file.name}", f_bytes)
                                relatorio_lista.append(resumo)
                                if is_p and resumo["Número"] > 0 and "EMITIDOS" in resumo["Pasta"]:
                                    if resumo["Tipo"] in ["NF-e", "NFC-e", "CT-e", "MDF-e"]:
                                        s_key = (resumo["Tipo"], resumo["Série"])
                                        if s_key not in sequencias: sequencias[s_key] = set()
                                        sequencias[s_key].add(resumo["Número"])
                
                faltantes_data = []
                for (tipo, serie), numeros in sequencias.items():
                    if len(numeros) > 1:
                        ideal = set(range(min(numeros), max(numeros) + 1))
                        buracos = sorted(list(ideal - numeros))
                        for b in buracos:
                            faltantes_data.append({"Documento": tipo, "Série": serie, "Nº Faltante": b})
                
                st.session_state['df_faltantes'] = pd.DataFrame(faltantes_data) if faltantes_data else pd.DataFrame()
                status.update(label="💰 Garimpo Concluído!", state="complete")

            if relatorio_lista:
                st.session_state.update({'relatorio': relatorio_lista, 'zip_completo': zip_buffer.getvalue(), 'garimpo_ok': True})
                icons = ["💰", "🪙", "💎", "🥇", "✨"]
                rain_html = "".join([f'<div class="gold-item" style="left:{random.randint(0,95)}%; animation-delay:{random.uniform(0,2.5)}s; font-size:{random.randint(25,45)}px;">{random.choice(icons)}</div>' for i in range(70)])
                st.markdown(rain_html, unsafe_allow_html=True)

# --- RESULTADOS E BUSCA ---
if st.session_state.get('garimpo_ok'):
    st.divider()
    df_res = pd.DataFrame(st.session_state['relatorio'])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📦 VOLUME MINERADO", f"{len(df_res)}")
    emitidas = len(df_res[df_res['Pasta'].str.contains("EMITIDOS")])
    col2.metric("✨ NOTAS DO CLIENTE", f"{emitidas}")
    df_f = st.session_state.get('df_faltantes')
    col3.metric("⚠️ BURACOS NA MINA", f"{len(df_f) if df_f is not None else 0}")

    st.markdown("### 🔍 Peneira de Notas (Busca Individual)")
    busca = st.text_input("Digite o Número da Nota ou a Chave para baixar:", placeholder="Ex: 1234")
    
    if busca:
        filtro = df_res[df_res['Número'].astype(str).str.contains(busca) | df_res['Chave'].str.contains(busca)]
        if not filtro.empty:
            for _, row in filtro.iterrows():
                st.download_button(f"📥 Baixar XML: {row['Tipo']} - Nº {row['Número']}", row['Conteúdo'], file_name=row['Arquivo'])
        else:
            st.warning("Nenhuma pepita encontrada com esse número.")

    st.markdown("---")
    st.markdown("### ⚠️ RELATÓRIO DE NOTAS FALTANTES")
    if df_f is not None and not df_f.empty:
        st.dataframe(df_f, use_container_width=True, hide_index=True)
    else:
        st.success("Mina íntegra! Sequência completa.")

    st.divider()
    st.download_button("📥 BAIXAR TESOURO COMPLETO (.ZIP)", st.session_state['zip_completo'], "garimpo_final.zip", use_container_width=True)
