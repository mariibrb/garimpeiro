import streamlit as st
import zipfile
import io
import os
import re
import random
import gc
import shutil

# --- CONFIGURAÇÃO E ESTILO ---
st.set_page_config(page_title="EXTRATOR TURBO XML", layout="wide", page_icon="⚡")

def aplicar_estilo_premium():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;800&family=Plus+Jakarta+Sans:wght@400;700&display=swap');
        header, [data-testid="stHeader"] { display: none !important; }
        .stApp { background: radial-gradient(circle at top right, #E0F7FA 0%, #F8F9FA 100%) !important; }
        [data-testid="stSidebar"] { background-color: #FFFFFF !important; min-width: 350px !important; }
        div.stButton > button { border-radius: 15px !important; font-weight: 800 !important; width: 100% !important; }
        .instrucoes-card { background-color: rgba(255, 255, 255, 0.7); border-radius: 15px; padding: 20px; border-left: 5px solid #00BCD4; }
        </style>
    """, unsafe_allow_html=True)

aplicar_estilo_premium()

# --- VARIÁVEIS DE SISTEMA ---
TEMP_UPLOADS_DIR = "temp_uploads"
if 'dados_extraidos' not in st.session_state: st.session_state['dados_extraidos'] = {}
if 'processamento_concluido' not in st.session_state: st.session_state['processamento_concluido'] = False

def limpar_tudo():
    if os.path.exists(TEMP_UPLOADS_DIR): shutil.rmtree(TEMP_UPLOADS_DIR)
    st.session_state.clear()
    st.rerun()

# --- MOTOR DE BUSCA RECURSIVA ---
def get_xml_info(content_bytes, cnpj_cliente):
    content_str = content_bytes[:10000].decode('utf-8', errors='ignore').lower()
    if '<inf' not in content_str: return None
    
    # CNPJ
    cnpj_emit = ""
    match = re.search(r'<emit>.*?<cnpj>(\d+)</cnpj>', content_str, re.S)
    if match: cnpj_emit = match.group(1)
    else:
        match_chave = re.search(r'id=["\'](?:nfe|cte|mdfe)?(\d{44})["\']', content_str)
        if match_chave: cnpj_emit = match_chave.group(1)[6:20]
    
    # Data
    ano, mes = "0000", "00"
    match_data = re.search(r'<(?:dhemi|demi|dhregevento|dhrecbto)>(\d{4})-(\d{2})-(\d{2})', content_str)
    if match_data: ano, mes = match_data.group(1), match_data.group(2)
    
    origem = "EMISSAO_PROPRIA" if cnpj_emit == cnpj_cliente else "TERCEIROS"
    return f"{origem}/{ano}/{mes}"

def extrair_matrioska(conteudo_ou_file, nome_arquivo):
    if nome_arquivo.lower().endswith('.zip'):
        file_obj = conteudo_ou_file if hasattr(conteudo_ou_file, 'read') else io.BytesIO(conteudo_ou_file)
        try:
            with zipfile.ZipFile(file_obj) as z:
                for sub_nome in z.namelist():
                    if sub_nome.startswith('__MACOSX') or os.path.basename(sub_nome).startswith('.'): continue
                    if sub_nome.lower().endswith('.zip'):
                        yield from extrair_matrioska(z.read(sub_nome), sub_nome)
                    elif sub_nome.lower().endswith('.xml'):
                        yield (os.path.basename(sub_nome), z.read(sub_nome))
        except: pass
    elif nome_arquivo.lower().endswith('.xml'):
        data = conteudo_ou_file.read() if hasattr(conteudo_ou_file, 'read') else conteudo_ou_file
        yield (os.path.basename(nome_arquivo), data)

# --- INTERFACE ---
st.title("⚡ EXTRATOR TURBO COM FILTRO")

with st.sidebar:
    cnpj_input = st.text_input("CNPJ DO CLIENTE", placeholder="00000000000000")
    cnpj_limpo = "".join(filter(str.isdigit, cnpj_input))
    if st.button("🗑️ RESETAR TUDO"): limpar_tudo()

if len(cnpj_limpo) == 14:
    if not st.session_state['processamento_concluido']:
        files = st.file_uploader("Arraste as Matrioskas (ZIPs):", accept_multiple_files=True)
        if files and st.button("🚀 ESCANEAR ARQUIVOS"):
            dados = {}
            with st.status("Garimpando XMLs...", expanded=True):
                for f in files:
                    for nome, conteudo in extrair_matrioska(f, f.name):
                        rota = get_xml_info(conteudo, cnpj_limpo)
                        if rota:
                            if rota not in dados: dados[rota] = []
                            dados[rota].append((nome, conteudo))
            st.session_state['dados_extraidos'] = dados
            st.session_state['processamento_concluido'] = True
            st.rerun()

    if st.session_state['processamento_concluido']:
        st.success(f"Busca finalizada! Encontrei XMLs em {len(st.session_state['dados_extraidos'])} pastas diferentes.")
        
        # --- O FILTRO QUE VOCÊ QUERIA ---
        st.markdown("### 🎯 Selecione o que deseja baixar:")
        opcoes = sorted(list(st.session_state['dados_extraidos'].keys()))
        selecionados = st.multiselect("Escolha as pastas (Ex: PROPRIA/2024/01):", opcoes, default=opcoes)

        if selecionados:
            if st.button("📦 GERAR PACOTE PARA DOWNLOAD"):
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z_out:
                    for rota in selecionados:
                        for nome, conteudo in st.session_state['dados_extraidos'][rota]:
                            # Resolve nomes duplicados
                            z_out.writestr(f"{rota}/{nome}", conteudo)
                
                st.download_button(
                    label="📥 BAIXAR XMLS SELECIONADOS",
                    data=buffer.getvalue(),
                    file_name="extracao_filtrada.zip",
                    mime="application/zip"
                )
else:
    st.info("Aguardando CNPJ para liberar o sistema.")
