import streamlit as st
import zipfile
import io
import os
import re
import pandas as pd
import random

# --- CONFIGURAÇÃO E ESTILO (CLONE ABSOLUTO DO DIAMOND TAX) ---
st.set_page_config(page_title="DIAMOND TAX | O Garimpeiro", layout="wide", page_icon="⛏️")

def aplicar_estilo_diamond_tax_real():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;800&family=Plus+Jakarta+Sans:wght@400;700&display=swap');

        /* 1. FUNDAÇÃO E CABEÇALHO */
        header, [data-testid="stHeader"] { display: none !important; }
        .stApp { 
            background: radial-gradient(circle at top right, #FFDEEF 0%, #F8F9FA 100%) !important; 
        }

        /* 2. BOTÕES ESTILO DIAMOND (BRANCO GORDINHO) */
        div.stButton > button {
            color: #6C757D !important; 
            background-color: #FFFFFF !important; 
            border: 1px solid #DEE2E6 !important;
            border-radius: 15px !important;
            font-family: 'Montserrat', sans-serif !important;
            font-weight: 800 !important;
            height: 60px !important;
            text-transform: uppercase;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
            width: 100% !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
        }

        div.stButton > button:hover {
            transform: translateY(-5px) !important;
            opacity: 1 !important;
            box-shadow: 0 10px 20px rgba(255,105,180,0.2) !important;
            border-color: #FF69B4 !important;
            color: #FF69B4 !important;
        }

        /* 3. UPLOADER E DOWNLOAD ESTILIZADOS */
        [data-testid="stFileUploader"] { 
            border: 2px dashed #FF69B4 !important; 
            border-radius: 20px !important;
            background: #FFFFFF !important;
            padding: 20px !important;
        }

        [data-testid="stFileUploader"] section button, 
        div.stDownloadButton > button {
            background-color: #FF69B4 !important; 
            color: white !important; 
            border: 2px solid #FFFFFF !important;
            font-weight: 700 !important;
            border-radius: 15px !important;
            box-shadow: 0 0 15px rgba(255, 105, 180, 0.3) !important;
            text-transform: uppercase;
        }

        /* 4. TEXTOS E TÍTULOS */
        h1, h2, h3 {
            font-family: 'Montserrat', sans-serif;
            font-weight: 800;
            color: #FF69B4 !important;
            text-align: center;
        }

        /* 5. SIDEBAR CLONE 1:1 (LARGURA E ESPAÇAMENTO DO TAX) */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
            border-right: 1px solid #FFDEEF !important;
        }
        
        /* Força a largura do conteúdo da sidebar para ser igual ao Tax */
        [data-testid="stSidebar"] > div:first-child {
            width: 350px !important;
        }

        /* Estilo destacado para o campo de CNPJ (Moldura Rosa do Tax) */
        .stTextInput>div>div>input {
            border: 2px solid #FFDEEF !important;
            border-radius: 10px !important;
            padding: 10px !important;
            background-color: white !important;
            color: #6C757D !important;
        }
        
        .stTextInput>label {
            color: #FF69B4 !important;
            font-weight: 800 !important;
            font-family: 'Montserrat', sans-serif !important;
        }
        </style>
    """, unsafe_allow_html=True)

aplicar_estilo_diamond_tax_real()

# --- MOTOR DE IDENTIFICAÇÃO (LÓGICA ORIGINAL MANTIDA) ---
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
        if '<?xml' not in content_str and '<inf' not in content_str: return None, False
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
        resumo["Tipo"], resumo["Status"] = tipo, status
        resumo["Série"] = re.search(r'<(?:serie)>(\d+)</', tag_l).group(1) if re.search(r'<(?:serie)>(\d+)</', tag_l) else "0"
        n_match = re.search(r'<(?:nnf|nct|nmdf|nnfini)>(\d+)</', tag_l)
        resumo["Número"] = int(n_match.group(1)) if n_match else 0
        if status == "NORMAIS":
            v_match = re.search(r'<(?:vnf|vtprest)>([\d.]+)</', tag_l)
            resumo["Valor"] = float(v_match.group(1)) if v_match else 0.0
        cnpj_emit = re.search(r'<cnpj>(\d+)</cnpj>', tag_l).group(1) if re.search(r'<cnpj>(\d+)</cnpj>', tag_l) else ""
        is_p = (cnpj_emit == client_cnpj_clean) or (resumo["Chave"] and client_cnpj_clean in resumo["Chave"][6:20])
        resumo["Pasta"] = f"EMITIDOS_CLIENTE/{tipo}/{status}/Serie_{resumo['Série']}" if is_p else f"RECEBIDOS_TERCEIROS/{tipo}"
        return resumo, is_p
    except: return None, False

# --- INTERFACE ---
st.markdown("<h1>💎 DIAMOND TAX</h1>", unsafe_allow_html=True)

if 'confirmado' not in st.session_state: st.session_state['confirmado'] = False

with st.sidebar:
    st.markdown("### 🔍 Configuração")
    
    # Campo idêntico ao Diamond Tax (Placeholders e Cores)
    cnpj_input = st.text_input(
        "CNPJ DO CLIENTE", 
        placeholder="00.000.000/0001-00",
        help="Digite o CNPJ da empresa que está sendo auditada. Pode conter pontos, barras ou apenas números."
    )
    cnpj_limpo = "".join(filter(str.isdigit, cnpj_input))
    
    if cnpj_input and len(cnpj_limpo) != 14:
        st.error("⚠️ O CNPJ deve ter 14 números.")
    
    if len(cnpj_limpo) == 14:
        if st.button("✅ LIBERAR OPERAÇÃO"):
            st.session_state['confirmado'] = True
            st.rerun()
            
    st.divider()
    if st.button("🗑️ RESETAR SISTEMA"):
        st.session_state.clear()
        st.rerun()

if st.session_state['confirmado']:
    st.info(f"🏢 Operação liberada para o CNPJ: {cnpj_limpo}")
    
    if 'garimpo_ok' not in st.session_state or not st.session_state['garimpo_ok']:
        uploaded_files = st.file_uploader("Arraste seus arquivos XML ou ZIP aqui:", accept_multiple_files=True)
        if uploaded_files and st.button("🚀 INICIAR GRANDE GARIMPO"):
            p_keys, buf_org, buf_todos = set(), io.BytesIO(), io.BytesIO()
            with st.status("⛏️ Garimpando dados...", expanded=True):
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
                        else: items.append((os.path.basename(f.name), f_bytes))
                        for name, xml_data in items:
                            res, is_p = identify_xml_info(xml_data, cnpj_limpo, name)
                            if res:
                                key = res["Chave"] if res["Chave"] else name
                                if key not in p_keys:
                                    p_keys.add(key)
                                    z_org.writestr(f"{res['Pasta']}/{name}", xml_data); z_todos.writestr(name, xml_data)
            
            st.session_state.update({'z_org': buf_org.getvalue(), 'z_todos': buf_todos.getvalue(), 'garimpo_ok': True})
            st.rerun()
    else:
        st.success("💎 Garimpo Concluído!")
        st.divider()
        col1, col2 = st.columns(2)
        with col1: st.download_button("📂 BAIXAR ORGANIZADO", st.session_state['z_org'], "garimpo_pastas.zip", use_container_width=True)
        with col2: st.download_button("📦 BAIXAR TODOS", st.session_state['z_todos'], "todos_xml.zip", use_container_width=True)
        if st.button("⛏️ NOVO GARIMPO"):
            st.session_state.clear(); st.rerun()
else:
    st.warning("👈 Insira o CNPJ na barra lateral para começar.")
