import streamlit as st
import zipfile
import io
import os
import re
import pandas as pd
import random

# --- MOTOR DE IDENTIFICAÇÃO (MANTENDO HIERARQUIA FISCAL ORIGINAL) ---
def identify_xml_info(content_bytes, client_cnpj, file_name):
    client_cnpj_clean = "".join(filter(str.isdigit, str(client_cnpj))) if client_cnpj else ""
    nome_puro = os.path.basename(file_name)
    
    if nome_puro.startswith('.') or nome_puro.startswith('~') or not nome_puro.lower().endswith('.xml'):
        return None, False

    resumo = {
        "Arquivo": nome_puro, "Chave": "", "Tipo": "Outros", "Série": "0",
        "Número": 0, "Status": "NORMAIS", "Pasta": "RECEBIDOS_TERCEIROS/OUTROS",
        "Valor": 0.0, "Conteúdo": content_bytes
    }
    try:
        content_str = content_bytes[:20000].decode('utf-8', errors='ignore')
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
        
        # Captura de número
        n_match = re.search(r'<(?:nnf|nct|nmdf|nnfini)>(\d+)</', tag_l)
        resumo["Número"] = int(n_match.group(1)) if n_match else 0
        
        if status == "NORMAIS":
            v_match = re.search(r'<(?:vnf|vtprest)>([\d.]+)</', tag_l)
            resumo["Valor"] = float(v_match.group(1)) if v_match else 0.0

        cnpj_emit = re.search(r'<cnpj>(\d+)</cnpj>', tag_l).group(1) if re.search(r'<cnpj>(\d+)</cnpj>', tag_l) else ""
        is_p = (cnpj_emit == client_cnpj_clean) or (resumo["Chave"] and client_cnpj_clean in resumo["Chave"][6:20])
        resumo["Pasta"] = f"EMITIDOS_CLIENTE/{tipo}/{status}/Serie_{resumo['Série']}" if is_p else f"RECEBIDOS_TERCEIROS/{tipo}"
        return resumo, is_p
    except:
        return None, False

# --- DESIGN ---
st.set_page_config(page_title="O Garimpeiro", layout="wide", page_icon="⛏️")
st.markdown("""
    <style>
    #MainMenu, footer, header, .stAppDeployButton {visibility: hidden !important;}
    .stApp { background-color: #f7f3f0; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #EADBC8 0%, #D2B48C 100%) !important; border-right: 3px solid #b8860b; }
    h1, h2, h3, h4, p, label, .stMetric label { color: #2b1e16 !important; font-family: 'Playfair Display', serif; font-weight: 900 !important;}
    [data-testid="stMetric"] { background: linear-gradient(135deg, #ffffff 0%, #fff9e6 100%); border: 2px solid #d4af37; border-radius: 20px; padding: 20px; }
    div.stButton > button { background: linear-gradient(180deg, #fcf6ba 0%, #d4af37 40%, #aa771c 100%) !important; color: #2b1e16 !important; border: 2px solid #8a6d3b; padding: 20px !important; border-radius: 50px !important; width: 100% !important; text-transform: uppercase !important; font-weight: 900 !important;}
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>⛏️ O GARIMPEIRO</h1>", unsafe_allow_html=True)

# INICIALIZAÇÃO SEGURA
keys_to_init = ['garimpo_ok', 'confirmado', 'z_org', 'z_todos', 'relatorio', 'df_resumo', 'df_faltantes', 'st_counts']
for k in keys_to_init:
    if k not in st.session_state:
        if 'df' in k: st.session_state[k] = pd.DataFrame()
        elif 'z_' in k: st.session_state[k] = None
        elif k == 'relatorio': st.session_state[k] = []
        elif k == 'st_counts': st.session_state[k] = {"CANCELADOS": 0, "INUTILIZADOS": 0}
        else: st.session_state[k] = False

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
        uploaded_files = st.file_uploader("Suba seus arquivos:", accept_multiple_files=True)
        if uploaded_files and st.button("🚀 INICIAR GRANDE GARIMPO"):
            p_keys, rel_list, seq_map, st_counts = set(), [], {}, {"CANCELADOS": 0, "INUTILIZADOS": 0}
            buf_org, buf_todos = io.BytesIO(), io.BytesIO()
            
            with st.status("⛏️ Processando...", expanded=True):
                with zipfile.ZipFile(buf_org, "w", zipfile.ZIP_STORED) as z_org, \
                     zipfile.ZipFile(buf_todos, "w", zipfile.ZIP_STORED) as z_todos:
                    
                    for f in uploaded_files:
                        f_bytes = f.read()
                        items = []
                        if f.name.lower().endswith('.zip'):
                            with zipfile.ZipFile(io.BytesIO(f_bytes)) as z_in:
                                for n in z_in.namelist():
                                    b_name = os.path.basename(n)
                                    if b_name.lower().endswith('.xml') and not b_name.startswith(('.', '~')):
                                        items.append((b_name, z_in.read(n)))
                        else:
                            items.append((os.path.basename(f.name), f_bytes))

                        for name, xml_data in items:
                            res, is_p = identify_xml_info(xml_data, cnpj_limpo, name)
                            if res:
                                key = res["Chave"] if res["Chave"] else name
                                if key not in p_keys:
                                    p_keys.add(key)
                                    z_org.writestr(f"{res['Pasta']}/{name}", xml_data)
                                    z_todos.writestr(name, xml_data)
                                    rel_list.append(res)
                                    
                                    if is_p:
                                        if res["Status"] in st_counts: st_counts[res["Status"]] += 1
                                        
                                        # SEQ_MAP para Resumo e Buracos
                                        sk = (res["Tipo"], res["Série"])
                                        if sk not in seq_map: seq_map[sk] = {"nums": set(), "valor": 0.0}
                                        seq_map[sk]["nums"].add(res["Número"])
                                        seq_map[sk]["valor"] += res["Valor"]

            # Montagem dos relatórios
            res_final = []
            nums_encontrados_por_serie = {} # Para unificar notas + inutilizações na auditoria de buraco

            for (t, s), dados in seq_map.items():
                ns = dados["nums"]
                res_final.append({
                    "Documento": t, "Série": s, "Início": min(ns), "Fim": max(ns),
                    "Quantidade": len(ns), "Valor Contábil (R$)": round(dados["valor"], 2)
                })
                # Agrupa números por série para checar buraco real (ignora se é nota ou inutilização)
                if s not in nums_encontrados_por_serie: nums_encontrados_por_serie[s] = set()
                nums_encontrados_por_serie[s].update(ns)

            fal_final = []
            for s, todos_nums in nums_encontrados_por_serie.items():
                if len(todos_nums) > 1:
                    ideal = set(range(min(todos_nums), max(todos_nums) + 1))
                    buracos = sorted(list(ideal - todos_nums))
                    for b in buracos:
                        fal_final.append({"Série": s, "Nº Faltante": b})

            st.session_state.update({
                'z_org': buf_org.getvalue(), 'z_todos': buf_todos.getvalue(),
                'relatorio': rel_list, 'df_resumo': pd.DataFrame(res_final),
                'df_faltantes': pd.DataFrame(fal_final), 'st_counts': st_counts, 'garimpo_ok': True
            })
            st.rerun()
    else:
        st.success(f"⛏️ Garimpo Concluído!")
        sc = st.session_state['st_counts']
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 VOLUME", len(st.session_state['relatorio']))
        c2.metric("❌ CANCELADAS", sc.get("CANCELADOS", 0))
        c3.metric("🚫 INUTILIZADAS", sc.get("INUTILIZADOS", 0))

        st.markdown("### 📊 RESUMO POR SÉRIE E VALOR CONTÁBIL")
        st.dataframe(st.session_state['df_resumo'], use_container_width=True, hide_index=True)

        st.markdown("### ⚠️ AUDITORIA DE SEQUÊNCIA (BURACOS REAIS)")
        st.dataframe(st.session_state['df_faltantes'], use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### 🔍 PENEIRA INDIVIDUAL (BUSCA)")
        busca = st.text_input("Número ou Chave:")
        if busca:
            df_full = pd.DataFrame(st.session_state['relatorio'])
            filtro = df_full[df_full['Número'].astype(str).contains(busca) | df_full['Chave'].contains(busca)]
            for _, row in filtro.iterrows():
                st.download_button(f"📥 XML Nº {row['Número']} ({row['Status']})", row['Conteúdo'], row['Arquivo'], key=f"dl_{row['Chave']}_{random.random()}")

        st.divider()
        st.markdown("### 📥 EXTRAÇÃO FINAL")
        col1, col2 = st.columns(2)
        with col1:
            if st.session_state['z_org']:
                st.download_button("📂 BAIXAR ORGANIZADO", st.session_state['z_org'], "garimpo_pastas.zip", use_container_width=True)
        with col2:
            if st.session_state['z_todos']:
                st.download_button("📦 BAIXAR TODOS (SÓ XML)", st.session_state['z_todos'], "todos_xml.zip", use_container_width=True)

        if st.button("⛏️ NOVO GARIMPO"):
            st.session_state.clear()
            st.rerun()
