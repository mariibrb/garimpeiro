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
    nome_puro = os.path.basename(file_name)
    resumo = {
        "Arquivo": nome_puro, "Chave": "", "Tipo": "Outros", "Série": "0",
        "Número": 0, "Pasta": "RECEBIDOS_TERCEIROS/OUTROS"
    }
    try:
        content_str = content_bytes[:8192].decode('utf-8', errors='ignore')
        match_ch = re.search(r'\d{44}', content_str)
        resumo["Chave"] = match_ch.group(0) if match_ch else ""
        tag_l = content_str.lower()
        
        tipo = "NF-e"
        if '<mod>65</mod>' in tag_l: tipo = "NFC-e"
        elif '<infcte' in tag_l: tipo = "CT-e"
        elif '<infmdfe' in tag_l: tipo = "MDF-e"
        
        status = "NORMAIS"
        if '110111' in tag_l: status = "CANCELADOS"
        elif '110110' in tag_l: status = "CARTA_CORRECAO"
        elif '<inutnfe' in tag_l or '<procinut' in tag_l:
            status = "INUTILIZADOS"
            tipo = "Inutilizacoes"
            
        resumo["Tipo"] = tipo
        s_match = re.search(r'<(?:serie)>(\d+)</', tag_l)
        resumo["Série"] = s_match.group(1) if s_match else "0"
        n_match = re.search(r'<(?:nnf|nct|nmdf|nnfini)>(\d+)</', tag_l)
        resumo["Número"] = int(n_match.group(1)) if n_match else 0
        
        cnpj_emit = re.search(r'<cnpj>(\d+)</cnpj>', tag_l).group(1) if re.search(r'<cnpj>(\d+)</cnpj>', tag_l) else ""
        is_p = (cnpj_emit == client_cnpj_clean) or (resumo["Chave"] and client_cnpj_clean in resumo["Chave"][6:20])
        resumo["Pasta"] = f"EMITIDOS_CLIENTE/{tipo}/{status}/Serie_{resumo['Série']}" if is_p else f"RECEBIDOS_TERCEIROS/{tipo}"
        return resumo, is_p
    except:
        return resumo, False

# --- DESIGN PREMIUM ---
st.set_page_config(page_title="O Garimpeiro", layout="wide", page_icon="⛏️")
st.markdown("""
    <style>
    #MainMenu, footer, header, .stAppDeployButton {visibility: hidden !important; display: none !important;}
    .stApp { background-color: #f7f3f0; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #EADBC8 0%, #D2B48C 100%) !important; border-right: 3px solid #b8860b; }
    [data-testid="stSidebar"] * { color: #2b1e16 !important; font-weight: 900 !important; }
    h1, h2, h3, h4, p, label, .stMetric label { color: #2b1e16 !important; font-family: 'Playfair Display', serif; font-weight: 900 !important; }
    [data-testid="stMetric"] { background: linear-gradient(135deg, #ffffff 0%, #fff9e6 100%); border: 2px solid #d4af37; border-radius: 20px; padding: 20px; }
    div.stButton > button { background: linear-gradient(180deg, #fcf6ba 0%, #d4af37 40%, #aa771c 100%) !important; color: #2b1e16 !important; border: 2px solid #8a6d3b; padding: 20px !important; font-weight: 900 !important; border-radius: 50px !important; width: 100% !important; text-transform: uppercase !important; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>⛏️ O GARIMPEIRO</h1>", unsafe_allow_html=True)

if 'garimpo_ok' not in st.session_state: st.session_state['garimpo_ok'] = False
if 'confirmado' not in st.session_state: st.session_state['confirmado'] = False

with st.sidebar:
    st.markdown("### ⛏️ Painel de Extração")
    cnpj_input = st.text_input("CNPJ DO CLIENTE")
    cnpj_limpo = "".join(filter(str.isdigit, cnpj_input))
    if len(cnpj_limpo) == 14:
        if st.button("✅ LIBERAR OPERAÇÃO"):
            st.session_state['confirmado'] = True
            st.rerun()
    st.divider()
    if st.button("🗑️ RESETAR SISTEMA"):
        st.session_state.clear()
        st.rerun()

if st.session_state['confirmado']:
    if not st.session_state['garimpo_ok']:
        files = st.file_uploader("Suba seus arquivos (ZIP ou XML):", accept_multiple_files=True)
        if files and st.button("🚀 INICIAR GRANDE GARIMPO"):
            keys, rel_lista, seq = set(), [], {}
            buf_org = io.BytesIO()
            buf_todos = io.BytesIO()
            
            with st.status("⛏️ Processando jazidas separadas...", expanded=True) as status:
                with zipfile.ZipFile(buf_org, "w", zipfile.ZIP_STORED) as z_org, \
                     zipfile.ZipFile(buf_todos, "w", zipfile.ZIP_STORED) as z_todos:
                    
                    for f in files:
                        f_bytes = f.read()
                        temp_contents = []
                        if f.name.lower().endswith('.zip'):
                            with zipfile.ZipFile(io.BytesIO(f_bytes)) as z_in:
                                for name in z_in.namelist():
                                    if name.lower().endswith('.xml'):
                                        temp_contents.append((os.path.basename(name), z_in.read(name)))
                        else:
                            temp_contents.append((os.path.basename(f.name), f_bytes))

                        for name, xml_data in temp_contents:
                            res, is_p = identify_xml_info(xml_data, cnpj_limpo, name)
                            k = res["Chave"] if res["Chave"] else name
                            if k not in keys:
                                keys.add(k)
                                # Grava no ZIP de Pastas
                                z_org.writestr(f"{res['Pasta']}/{res['Arquivo']}", xml_data)
                                # Grava no ZIP TODOS (apenas arquivos soltos)
                                z_todos.writestr(res['Arquivo'], xml_data)
                                rel_lista.append(res)
                                if is_p and res["Número"] > 0:
                                    sk = (res["Tipo"], res["Série"])
                                    if sk not in seq: seq[sk] = set()
                                    seq[sk].add(res["Número"])
                        del temp_contents

            faltantes = []
            for (t, s), nums in seq.items():
                if len(nums) > 1:
                    ideal = set(range(min(nums), max(nums) + 1))
                    for b in sorted(list(ideal - nums)):
                        faltantes.append({"Documento": t, "Série": s, "Nº Faltante": b})

            st.session_state.update({
                'zip_org': buf_org.getvalue(),
                'zip_todos': buf_todos.getvalue(),
                'relatorio': rel_lista,
                'df_faltantes': pd.DataFrame(faltantes),
                'garimpo_ok': True
            })
            st.rerun()
    else:
        st.success(f"⛏️ Garimpo Concluído! {len(st.session_state.get('relatorio', []))} pepitas encontradas.")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 VOLUME", len(st.session_state.get('relatorio', [])))
        c2.metric("✨ CLIENTE", len([x for x in st.session_state.get('relatorio', []) if "EMITIDOS" in x['Pasta']]))
        c3.metric("⚠️ BURACOS", len(st.session_state.get('df_faltantes', [])))

        st.divider()
        st.markdown("### 📥 ESCOLHA SUA EXTRAÇÃO")
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            st.download_button(
                label="📂 BAIXAR ORGANIZADO (POR PASTAS)",
                data=st.session_state['zip_org'],
                file_name="garimpo_estruturado.zip",
                use_container_width=True
            )
            st.caption("Ideal para contabilidade (separado por série e tipo).")

        with col_btn2:
            st.download_button(
                label="📦 BAIXAR TODOS (ARQUIVOS SOLTOS)",
                data=st.session_state['zip_todos'],
                file_name="todos_xml_brutos.zip",
                use_container_width=True
            )
            st.caption("Ideal para importação em massa (sem subpastas).")

        st.divider()
        st.markdown("### 🔍 PENEIRA INDIVIDUAL")
        busca = st.text_input("Número ou Chave:")
        df_res = pd.DataFrame(st.session_state.get('relatorio', []))
        if busca and not df_res.empty:
            filtro = df_res[df_res['Número'].astype(str).contains(busca) | df_res['Chave'].contains(busca)]
            st.dataframe(filtro[["Arquivo", "Tipo", "Série", "Número"]], use_container_width=True, hide_index=True)

        st.markdown("### ⚠️ AUDITORIA DE SEQUÊNCIA")
        st.dataframe(st.session_state.get('df_faltantes', pd.DataFrame()), use_container_width=True, hide_index=True)

        if st.button("⛏️ NOVO GARIMPO"):
            st.session_state['garimpo_ok'] = False
            st.rerun()
