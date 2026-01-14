import streamlit as st
import zipfile
import io
import os
import xml.etree.ElementTree as ET
import re
import pandas as pd
import gc

# --- MOTOR DE IDENTIFICAÇÃO (PRECISÃO TOTAL) ---
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
                        if is_p and resumo["Número"] > 0 and resumo["Tipo"] != "Inutilizacoes":
                            doc_base = "NFC-e" if "NFC-e" in resumo["Pasta"] else ("NF-e" if "NF-e" in resumo["Pasta"] else resumo["Tipo"])
                            s_key = (doc_base, resumo["Série"])
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

# --- DESIGN ROYAL GOLD (MARROM & DOURADO) ---
st.set_page_config(page_title="O Garimpeiro v8.5", layout="wide", page_icon="💎")

st.markdown("""
    <style>
    /* Degradê de fundo champagne e Sidebar Dourada */
    .stApp, [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #FFFFFF 0%, #D2B48C 100%);
    }
    
    /* Textos em Marrom Escuro (Café/Onyx) */
    h1, h2, h3, h4, p, label, [data-testid="stMetricValue"], [data-testid="stMarkdownContainer"] p {
        color: #3D2B1F !important;
        font-family: 'Playfair Display', serif;
    }

    /* Botão Dourado Premium */
    div.stButton > button:first-child {
        background: linear-gradient(180deg, #E6BE8A 0%, #B8860B 100%);
        color: #3D2B1F !important;
        border: 1px solid #5D4037;
        padding: 12px 30px;
        font-size: 18px;
        font-weight: bold;
        border-radius: 30px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        width: 100%;
    }
    
    /* Chuva de Ouro (Pepitas) Espaçadas */
    .gold-particle {
        position: fixed;
        background: radial-gradient(circle, #FFD700 0%, #B8860B 100%);
        border-radius: 50% 20% 50% 20%;
        box-shadow: 0 0 12px #FFD700;
        z-index: 9999;
        pointer-events: none;
        animation: fall linear forwards;
    }
    @keyframes fall {
        0% { transform: translateY(-100px) rotate(0deg); opacity: 1; }
        100% { transform: translateY(110vh) rotate(720deg); opacity: 0; }
    }
    </style>
    """, unsafe_allow_html=True)

# --- CABEÇALHO ---
st.markdown("<h1>⛏️ O GARIMPEIRO</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #5D4037; font-size: 1.1rem;'><b>Extraindo diamantes dos seus arquivos fiscais.</b></p>", unsafe_allow_html=True)

if 'garimpo_ok' not in st.session_state: st.session_state['garimpo_ok'] = False
if 'cnpj_confirmado' not in st.session_state: st.session_state['cnpj_confirmado'] = False

# --- SIDEBAR DOURADA ---
with st.sidebar:
    st.markdown("### 🏺 Identificação da Mina")
    raw_cnpj = st.text_input("CNPJ do Cliente", placeholder="00.000.000/0001-00")
    cnpj_limpo = "".join(filter(str.isdigit, raw_cnpj))
    
    if len(cnpj_limpo) == 14:
        st.markdown(f"**Formatado:** `{format_cnpj(raw_cnpj)}`")
        if st.button("✅ CONFIRMAR CLIENTE"):
            st.session_state['cnpj_confirmado'] = True
            st.rerun()
    
    st.divider()
    if st.button("🗑️ Resetar Sistema"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

# --- ÁREA DE TRABALHO ---
if not st.session_state['cnpj_confirmado']:
    st.info("👋 Por favor, informe o CNPJ completo no menu lateral e confirme para começar.")
else:
    st.markdown(f"### 📥 Depósito de Arquivos: {format_cnpj(raw_cnpj)}")
    uploaded_files = st.file_uploader("Suba seus XMLs ou arquivos ZIP aqui:", accept_multiple_files=True)

    if uploaded_files:
        if st.button("🚀 INICIAR GARIMPO"):
            processed_keys, sequencias, relatorio_lista = set(), {}, []
            zip_buffer = io.BytesIO()
            
            with st.status("💎 Analisando camadas de dados...", expanded=True) as status:
                total = len(uploaded_files)
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
                                if is_p and resumo["Número"] > 0 and resumo["Tipo"] != "Inutilizacoes":
                                    doc_base = "NFC-e" if "NFC-e" in resumo["Pasta"] else ("NF-e" if "NF-e" in resumo["Pasta"] else resumo["Tipo"])
                                    s_key = (doc_base, resumo["Série"])
                                    if s_key not in sequencias: sequencias[s_key] = set()
                                    sequencias[s_key].add(resumo["Número"])
                
                # Relatório de Faltantes
                faltantes_lista = []
                for (t, s), nums in sequencias.items():
                    if nums:
                        ideal = set(range(min(nums), max(nums) + 1))
                        for b in sorted(list(ideal - nums)):
                            faltantes_lista.append({"Tipo": t, "Série": s, "Nº Faltante": b})
                st.session_state['df_faltantes'] = pd.DataFrame(faltantes_lista) if faltantes_lista else None
                status.update(label="✨ Tesouro lapidado e organizado!", state="complete")

            if relatorio_lista:
                st.session_state.update({'relatorio': relatorio_lista, 'zip_completo': zip_buffer.getvalue(), 'garimpo_ok': True})
                
                # --- CHUVA DE OURO ESPAÇADA (PÓS-GARIMPO) ---
                import random
                pepita_html = ""
                for i in range(60):
                    left = random.randint(0, 95)
                    delay = random.uniform(0, 2)
                    duration = random.uniform(2, 4)
                    size = random.randint(10, 22)
                    pepita_html += f'<div class="gold-particle" style="left:{left}%; animation-delay:{delay}s; animation-duration:{duration}s; width:{size}px; height:{size}px;"></div>'
                st.markdown(pepita_html, unsafe_allow_html=True)

if st.session_state.get('garimpo_ok'):
    st.divider()
    df_res = pd.DataFrame(st.session_state['relatorio'])
    c1, c2, c3 = st.columns(3)
    c1.metric("📦 Volume Total", f"{len(df_res)} itens")
    c2.metric("💎 Notas do Cliente", f"{len(df_res[df_res['Pasta'].str.contains('EMITIDOS')])}")
    c3.metric("⚠️ Buracos", f"{len(st.session_state['df_faltantes']) if st.session_state['df_faltantes'] is not None else 0}")
    
    st.download_button("📥 RECOLHER JAZIDA COMPLETA (.ZIP)", st.session_state['zip_completo'], "garimpeiro_v8_5.zip", use_container_width=True)
