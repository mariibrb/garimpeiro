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
                        # SÓ ENTRA NA SEQUÊNCIA SE FOR EMITIDO PELO CLIENTE E NÃO FOR INUTILIZAÇÃO/EVENTO
                        if is_p and resumo["Número"] > 0 and "EMITIDOS" in resumo["Pasta"] and "Serie_" in resumo["Pasta"]:
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

# --- DESIGN PREMIUM REFINADO (ESTILO IMAGEM) ---
st.set_page_config(page_title="O Garimpeiro", layout="wide", page_icon="⛏️")

st.markdown("""
    <style>
    /* Background Champagne Suave */
    .stApp { background: linear-gradient(180deg, #FFFFFF 0%, #E2D1C3 100%); }
    
    /* Sidebar Dourada Integrada */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #FFFFFF 0%, #D2B48C 100%);
        border-right: 1px solid #C4A484;
    }
    
    /* Textos Marrom Café (Onyx) */
    h1, h2, h3, h4, p, label, .stMetric label, [data-testid="stMetricValue"] {
        color: #3D2B1F !important;
        font-family: 'Playfair Display', serif;
    }

    /* Cards de Métricas Arredondados */
    [data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.5);
        border: 1px solid #D4AF37;
        border-radius: 20px;
        padding: 15px;
    }

    /* Botão Dourado Elegante */
    div.stButton > button {
        background: linear-gradient(180deg, #F9D976 0%, #D4AF37 100%);
        color: #3D2B1F !important;
        border: 1px solid #B8860B;
        padding: 12px 40px;
        font-size: 18px;
        font-weight: bold;
        border-radius: 35px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        width: 100%;
    }
    
    /* Chuva de Ouro Aleatória */
    .gold-particle {
        position: fixed; top: -50px; z-index: 9999;
        pointer-events: none; animation: fall linear forwards;
    }
    @keyframes fall {
        0% { transform: translateY(0) rotate(0deg); opacity: 1; }
        100% { transform: translateY(110vh) rotate(720deg); opacity: 0; }
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1>⛏️ O GARIMPEIRO</h1>", unsafe_allow_html=True)

if 'confirmado' not in st.session_state: st.session_state['confirmado'] = False
if 'garimpo_ok' not in st.session_state: st.session_state['garimpo_ok'] = False
if 'df_faltantes' not in st.session_state: st.session_state['df_faltantes'] = None

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### ⭐ Identificação")
    raw_cnpj = st.text_input("CNPJ do Cliente", placeholder="00.000.000/0001-00")
    cnpj_limpo = "".join(filter(str.isdigit, raw_cnpj))
    
    if len(cnpj_limpo) == 14:
        st.markdown(f"**Cliente:** {format_cnpj(raw_cnpj)}")
        if st.button("✅ CONFIRMAR CLIENTE"):
            st.session_state['confirmado'] = True
            st.rerun()
    
    st.divider()
    if st.button("🗑️ Resetar Jazida"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

# --- TRABALHO ---
if not st.session_state['confirmado']:
    st.info("👋 Por favor, informe o CNPJ completo no menu lateral e clique em **Confirmar**.")
else:
    st.markdown(f"### 📦 Depósito de Brutos: {format_cnpj(raw_cnpj)}")
    uploaded_files = st.file_uploader("Suba seus arquivos XML ou ZIP:", accept_multiple_files=True)

    if uploaded_files:
        if st.button("🌟 INICIAR GARIMPO"):
            processed_keys, sequencias, relatorio_lista = set(), {}, []
            zip_buffer = io.BytesIO()
            
            with st.status("💎 Minerando...", expanded=True) as status:
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf_final:
                    for file in uploaded_files:
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
                                    s_key = (resumo["Tipo"], resumo["Série"])
                                    if s_key not in sequencias: sequencias[s_key] = set()
                                    sequencias[s_key].add(resumo["Número"])
                
                # CORREÇÃO DO RELATÓRIO DE BURACOS
                faltantes_data = []
                for (tipo, serie), numeros in sequencias.items():
                    if numeros:
                        ideal = set(range(min(numeros), max(numeros) + 1))
                        buracos = sorted(list(ideal - numeros))
                        for b in buracos:
                            faltantes_data.append({"Documento": tipo, "Série": serie, "Nº Faltante": b})
                
                st.session_state['df_faltantes'] = pd.DataFrame(faltantes_data) if faltantes_data else pd.DataFrame()
                status.update(label="✅ Garimpo finalizado!", state="complete")

            if relatorio_lista:
                st.session_state.update({'relatorio': relatorio_lista, 'zip_completo': zip_buffer.getvalue(), 'garimpo_ok': True})
                
                # CHUVA DE OURO ESPAÇADA
                rain_html = ""
                for i in range(70):
                    left, delay, icon = random.randint(0, 98), random.uniform(0, 2), random.choice(["💰","💎","✨","🪙"])
                    rain_html += f'<div class="gold-particle" style="left:{left}%; top:-50px; font-size:{random.randint(15,30)}px; animation-delay:{delay}s; animation-duration:{random.uniform(2,4)}s;">{icon}</div>'
                st.markdown(rain_html, unsafe_allow_html=True)

# --- RESULTADOS ---
if st.session_state.get('garimpo_ok'):
    st.divider()
    df_res = pd.DataFrame(st.session_state['relatorio'])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("📦 Volume Minerado", f"{len(df_res)}")
    emitidas = len(df_res[df_res['Pasta'].str.contains("EMITIDOS")])
    c2.metric("💎 Notas do Cliente", f"{emitidas}")
    
    df_f = st.session_state.get('df_faltantes')
    buracos_qtd = len(df_f) if df_f is not None and not df_f.empty else 0
    c3.metric("⚠️ Buracos Encontrados", f"{buracos_qtd}")

    col_v1, col_v2 = st.columns(2)
    with col_v1:
        st.markdown("#### 📂 Estrutura de Pastas")
        st.dataframe(df_res['Pasta'].value_counts().reset_index().rename(columns={'Pasta': 'Caminho', 'count': 'Qtd'}), use_container_width=True, hide_index=True)
    with col_v2:
        st.markdown("#### ⚠️ Relatório de Faltantes")
        if df_f is not None and not df_f.empty:
            st.dataframe(df_f, use_container_width=True, hide_index=True)
        else:
            st.success("Sequência de notas 100% completa!")

    st.divider()
    st.download_button("📥 BAIXAR RESULTADO COMPLETO (.ZIP)", st.session_state['zip_completo'], "garimpeiro_final.zip", use_container_width=True)
