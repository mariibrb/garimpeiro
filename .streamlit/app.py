import streamlit as st
import zipfile
import io
import os
import re
import pandas as pd

# --- MOTOR DE IDENTIFICAÇÃO ---
def identify_xml_info(content_bytes, client_cnpj, file_name):
    client_cnpj_clean = "".join(filter(str.isdigit, str(client_cnpj))) if client_cnpj else ""
    nome_puro = os.path.basename(file_name)
    
    # Filtro contra arquivos ocultos ou temporários do Excel
    if nome_puro.startswith('.') or nome_puro.startswith('~') or not nome_puro.lower().endswith('.xml'):
        return None, False

    resumo = {
        "Arquivo": nome_puro, "Chave": "", "Tipo": "Outros", "Série": "0",
        "Número": 0, "Status": "NORMAIS", "Pasta": "RECEBIDOS_TERCEIROS/OUTROS",
        "Valor": 0.0
    }
    try:
        content_str = content_bytes[:15000].decode('utf-8', errors='ignore')
        if '<?xml' not in content_str and '<inf' not in content_str:
            return None, False

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
        resumo["Status"] = status
        resumo["Série"] = re.search(r'<(?:serie)>(\d+)</', tag_l).group(1) if re.search(r'<(?:serie)>(\d+)</', tag_l) else "0"
        
        n_match = re.search(r'<(?:nnf|nct|nmdf|nnfini)>(\d+)</', tag_l)
        resumo["Número"] = int(n_match.group(1)) if n_match else 0
        
        # Captura financeira apenas para notas normais
        if status == "NORMAIS":
            v_match = re.search(r'<(?:vnf|vtprest)>([\d.]+)</', tag_l)
            resumo["Valor"] = float(v_match.group(1)) if v_match else 0.0

        cnpj_emit = re.search(r'<cnpj>(\d+)</cnpj>', tag_l).group(1) if re.search(r'<cnpj>(\d+)</cnpj>', tag_l) else ""
        is_p = (cnpj_emit == client_cnpj_clean) or (resumo["Chave"] and client_cnpj_clean in resumo["Chave"][6:20])
        resumo["Pasta"] = f"EMITIDOS_CLIENTE/{tipo}/{status}/Serie_{resumo['Série']}" if is_p else f"RECEBIDOS_TERCEIROS/{tipo}"
        return resumo, is_p
    except:
        return None, False

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
        uploaded_files = st.file_uploader("Suba seus arquivos (ZIP ou XML):", accept_multiple_files=True)
        if uploaded_files and st.button("🚀 INICIAR GRANDE GARIMPO"):
            keys, rel, seq, status_counts = set(), [], {}, {"CANCELADOS": 0, "INUTILIZADOS": 0}
            buf_org, buf_todos = io.BytesIO(), io.BytesIO()
            
            with st.status("⛏️ Minerando jazida profunda...", expanded=True) as status:
                with zipfile.ZipFile(buf_org, "w", zipfile.ZIP_STORED) as z_org, \
                     zipfile.ZipFile(buf_todos, "w", zipfile.ZIP_STORED) as z_todos:
                    
                    for f in uploaded_files:
                        f_bytes = f.read()
                        temp_list = []
                        if f.name.lower().endswith('.zip'):
                            with zipfile.ZipFile(io.BytesIO(f_bytes)) as z_in:
                                for name in z_in.namelist():
                                    b_name = os.path.basename(name)
                                    if b_name.lower().endswith('.xml') and not b_name.startswith(('.', '~')):
                                        temp_list.append((b_name, z_in.read(name)))
                        else:
                            temp_list.append((os.path.basename(f.name), f_bytes))

                        for name, xml_data in temp_list:
                            res, is_p = identify_xml_info(xml_data, cnpj_limpo, name)
                            if res:
                                k = res["Chave"] if res["Chave"] else name
                                if k not in keys:
                                    keys.add(k)
                                    z_org.writestr(f"{res['Pasta']}/{name}", xml_data)
                                    z_todos.writestr(name, xml_data)
                                    rel.append(res)
                                    if is_p:
                                        if res["Status"] in status_counts: status_counts[res["Status"]] += 1
                                        sk = (res["Tipo"], res["Série"])
                                        if sk not in seq: seq[sk] = {"nums": set(), "valor": 0.0}
                                        seq[sk]["nums"].add(res["Número"])
                                        seq[sk]["valor"] += res["Valor"]
                        del temp_list

            resumo_series, faltantes = [], []
            for (tipo_doc, serie_doc), dados in seq.items():
                nums = dados["nums"]
                min_n, max_n = min(nums), max(nums)
                resumo_series.append({
                    "Documento": tipo_doc, "Série": serie_doc, "Início": min_n, "Fim": max_n, 
                    "Qtd": len(nums), "Valor Total (R$)": round(dados["valor"], 2)
                })
                if len(nums) > 1:
                    for b in sorted(list(set(range(min_n, max_n + 1)) - nums)):
                        faltantes.append({"Documento": tipo_doc, "Série": serie_doc, "Nº Faltante": b})

            st.session_state.update({
                'zip_org': buf_org.getvalue(), 'zip_todos': buf_todos.getvalue(), 'relatorio': rel,
                'df_resumo': pd.DataFrame(resumo_series), 'df_faltantes': pd.DataFrame(faltantes),
                'status_counts': status_counts, 'garimpo_ok': True
            })
            st.rerun()
    else:
        st.success(f"⛏️ Garimpo Concluído!")
        sc = st.session_state.get('status_counts', {})
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 VOLUME ÚNICO", len(st.session_state.get('relatorio', [])))
        c2.metric("❌ CANCELADAS", sc.get("CANCELADOS", 0))
        c3.metric("🚫 INUTILIZADAS", sc.get("INUTILIZADOS", 0))

        st.markdown("### 📊 RESUMO POR SÉRIE (VALORES E SEQUÊNCIA)")
        st.dataframe(st.session_state.get('df_resumo', pd.DataFrame()), use_container_width=True, hide_index=True)

        st.markdown("### ⚠️ AUDITORIA DE SEQUÊNCIA (BURACOS)")
        st.dataframe(st.session_state.get('df_faltantes', pd.DataFrame()), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### 📥 ESCOLHA SUA EXTRAÇÃO")
        col1, col2 = st.columns(2)
        with col1: st.download_button("📂 BAIXAR ORGANIZADO (POR PASTAS)", st.session_state['zip_org'], "garimpo_pastas.zip", use_container_width=True)
        with col2: st.download_button("📦 BAIXAR TODOS (SÓ XML SOLTO)", st.session_state['zip_todos'], "todos_xml.zip", use_container_width=True)

        if st.button("⛏️ NOVO GARIMPO"):
            st.session_state.clear()
            st.rerun()
