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
                            if resumo["Tipo"] != "Inutilizacoes":
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

# --- DESIGN LÚDICO & SOFISTICADO ---
st.set_page_config(page_title="O Garimpeiro", layout="wide", page_icon="⛏️")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #fdfcfb 0%, #e2d1c3 100%); }
    h1 { color: #5d4037 !important; font-family: 'Playfair Display', serif; font-weight: 800; text-align: center; }
    div.stButton > button:first-child {
        background: linear-gradient(to right, #8e5e02, #d4af37);
        color: white; border: none; padding: 15px 40px; font-size: 18px; font-weight: bold; border-radius: 50px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); transition: all 0.3s ease;
    }
    div.stButton > button:first-child:hover { transform: scale(1.02); box-shadow: 0 6px 20px rgba(0,0,0,0.3); border: 1px solid white; }
    [data-testid="stMetric"] { background-color: rgba(255, 255, 255, 0.6); padding: 15px; border-radius: 15px; border: 1px solid rgba(212, 175, 55, 0.3); }

    /* CSS para o efeito de pepitas de ouro */
    @keyframes gold-sparkle {
        0% { transform: translateY(0) scale(0.5); opacity: 0; }
        50% { opacity: 1; }
        100% { transform: translateY(-100px) scale(1.5); opacity: 0; }
    }
    .gold-particle {
        position: fixed;
        background-color: #FFD700; /* Cor do ouro */
        border-radius: 50%;
        opacity: 0;
        animation: gold-sparkle 2s ease-out forwards;
        z-index: 9999;
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1>⛏️ O GARIMPEIRO</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #8d6e63; font-style: italic;'>Transformando montanhas de arquivos em ouro organizado.</p>", unsafe_allow_html=True)

if 'garimpo_ok' not in st.session_state: st.session_state['garimpo_ok'] = False

# --- SIDEBAR COM MÁSCARA ---
with st.sidebar:
    st.markdown("### ✨ Identificação")
    raw_cnpj = st.text_input("CNPJ do Cliente", placeholder="00.000.000/0001-00", help="Digite apenas os números")
    formatted_cnpj = format_cnpj(raw_cnpj)
    if raw_cnpj:
        st.markdown(f"**CNPJ Formatado:** `{formatted_cnpj}`")
    
    st.divider()
    if st.button("🗑️ Resetar Jazida"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
    st.caption("Versão 7.4 | Pepita de Ouro Edition")

# --- ÁREA DE TRABALHO TRAVADA ---
cnpj_limpo = "".join(filter(str.isdigit, raw_cnpj))

if len(cnpj_limpo) < 14:
    st.info("👋 Para começar, informe o **CNPJ completo (14 dígitos)** do seu cliente ali no menu lateral.")
else:
    with st.container():
        st.markdown(f"### 🏺 Depósito de Arquivos - Cliente: {formatted_cnpj}")
        uploaded_files = st.file_uploader("Arraste aqui seus arquivos XML ou ZIP:", accept_multiple_files=True)

    if uploaded_files:
        if st.button("🌟 INICIAR GARIMPO", use_container_width=True):
            processed_keys, sequencias, relatorio_lista = set(), {}, []
            zip_buffer = io.BytesIO()
            
            with st.status("💎 Minerando e organizando...", expanded=True) as status:
                prog_bar = st.progress(0)
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
                        prog_bar.progress((i + 1) / total)
                    
                    faltantes_lista = []
                    for (t, s), nums in sequencias.items():
                        if nums:
                            ideal = set(range(min(nums), max(nums) + 1))
                            for b in sorted(list(ideal - nums)):
                                faltantes_lista.append({"Tipo": t, "Série": s, "Nº Faltante": b})
                    st.session_state['df_faltantes'] = pd.DataFrame(faltantes_lista) if faltantes_lista else None
                
                status.update(label="✨ Garimpo finalizado!", state="complete", expanded=False)

            if relatorio_lista:
                st.session_state.update({'relatorio': relatorio_lista, 'zip_completo': zip_buffer.getvalue(), 'garimpo_ok': True})
                # Efeito de pepitas de ouro subindo
                st.markdown("""
                    <div class="gold-particle" style="left: 10%; top: 80%; width: 10px; height: 10px; animation-delay: 0s;"></div>
                    <div class="gold-particle" style="left: 20%; top: 90%; width: 8px; height: 8px; animation-delay: 0.2s;"></div>
                    <div class="gold-particle" style="left: 30%; top: 70%; width: 12px; height: 12px; animation-delay: 0.4s;"></div>
                    <div class="gold-particle" style="left: 40%; top: 85%; width: 9px; height: 9px; animation-delay: 0.6s;"></div>
                    <div class="gold-particle" style="left: 50%; top: 75%; width: 11px; height: 11px; animation-delay: 0.8s;"></div>
                    <div class="gold-particle" style="left: 60%; top: 82%; width: 7px; height: 7px; animation-delay: 1s;"></div>
                    <div class="gold-particle" style="left: 70%; top: 78%; width: 10px; height: 10px; animation-delay: 1.2s;"></div>
                    <div class="gold-particle" style="left: 80%; top: 88%; width: 8px; height: 8px; animation-delay: 1.4s;"></div>
                    <div class="gold-particle" style="left: 90%; top: 72%; width: 12px; height: 12px; animation-delay: 1.6s;"></div>
                """, unsafe_allow_html=True)


# --- RESULTADOS ---
if st.session_state.get('garimpo_ok'):
    st.divider()
    df_resumo = pd.DataFrame(st.session_state['relatorio'])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("📁 Total Minerado", f"{len(df_resumo)}")
    emitidas_count = len(df_resumo[df_resumo['Pasta'].str.contains("EMITIDOS")])
    c2.metric("💎 Notas do Cliente", f"{emitidas_count}")
    buracos_count = len(st.session_state['df_faltantes']) if st.session_state['df_faltantes'] is not None else 0
    c3.metric("⚠️ Buracos", f"{buracos_count}")

    st.markdown("---")
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        st.markdown("#### 📂 Estrutura de Pastas")
        st.dataframe(df_resumo['Pasta'].value_counts().reset_index().rename(columns={'Pasta': 'Caminho', 'count': 'Qtd'}), use_container_width=True, hide_index=True)
    with col_v2:
        st.markdown("#### ⚠️ Números Faltantes (Buracos)")
        df_f = st.session_state.get('df_faltantes')
        if df_f is not None and not df_f.empty:
            st.dataframe(df_f, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma falha de sequência detectada.")

    st.divider()
    st.download_button("📥 BAIXAR RESULTADO COMPLETO (.ZIP)", st.session_state['zip_completo'], "garimpo_v7_4.zip", use_container_width=True)
