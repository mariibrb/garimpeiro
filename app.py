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
        .stApp { 
            background: radial-gradient(circle at top right, #E0F7FA 0%, #F8F9FA 100%) !important; 
        }

        [data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
            border-right: 1px solid #E0F7FA !important;
            min-width: 400px !important;
            max-width: 400px !important;
        }

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
            box-shadow: 0 10px 20px rgba(0,188,212,0.2) !important;
            border-color: #00BCD4 !important;
            color: #00BCD4 !important;
        }

        [data-testid="stFileUploader"] { 
            border: 2px dashed #00BCD4 !important; 
            border-radius: 20px !important;
            background: #FFFFFF !important;
            padding: 20px !important;
        }

        div.stDownloadButton > button {
            background-color: #00BCD4 !important; 
            color: white !important; 
            border: 2px solid #FFFFFF !important;
            font-weight: 700 !important;
            border-radius: 15px !important;
            box-shadow: 0 0 15px rgba(0, 188, 212, 0.3) !important;
            text-transform: uppercase;
            width: 100% !important;
        }

        h1, h2, h3 {
            font-family: 'Montserrat', sans-serif;
            font-weight: 800;
            color: #00BCD4 !important;
            text-align: center;
        }

        .instrucoes-card {
            background-color: rgba(255, 255, 255, 0.7);
            border-radius: 15px;
            padding: 20px;
            border-left: 5px solid #00BCD4;
            margin-bottom: 20px;
            min-height: 200px;
        }
        </style>
    """, unsafe_allow_html=True)

aplicar_estilo_premium()

# --- VARIÁVEIS DE SISTEMA DE ARQUIVOS ---
TEMP_EXTRACT_DIR = "temp_extrator_zips"
TEMP_UPLOADS_DIR = "temp_extrator_uploads"
MAX_XML_PER_ZIP = 10000  # Trava para evitar queda de memória no download (Gera ZIPs de ~25MB)

# --- MOTOR DE LEITURA RÁPIDA (FOCA APENAS EM CNPJ E DATA) ---
def get_xml_minimal_info(content_bytes, client_cnpj_clean):
    try:
        content_str = content_bytes[:10000].decode('utf-8', errors='ignore').lower()
        if '<inf' not in content_str and '<inut' not in content_str: 
            return "OUTROS"
        
        # 1. Pega CNPJ Emitente
        cnpj_emit = ""
        cnpj_emit_match = re.search(r'<emit>.*?<cnpj>(\d+)</cnpj>', content_str, re.S)
        if cnpj_emit_match:
            cnpj_emit = cnpj_emit_match.group(1)
        else:
            # Tenta pegar pela chave
            chave_match = re.search(r'id=["\'](?:nfe|cte|mdfe)?(\d{44})["\']', content_str)
            if not chave_match:
                chave_match = re.search(r'<(?:chnfe|chcte|chmdfe)>(\d{44})</', content_str)
            if chave_match:
                cnpj_emit = chave_match.group(1)[6:20]

        # 2. Pega Ano e Mês
        ano, mes = "0000", "00"
        data_match = re.search(r'<(?:dhemi|demi|dhregevento|dhrecbto)>(\d{4})-(\d{2})-(\d{2})', content_str)
        if data_match:
            ano, mes = data_match.group(1), data_match.group(2)
        else:
            # Tenta pegar pela chave se não tiver tag de data clara
            chave_match = re.search(r'id=["\'](?:nfe|cte|mdfe)?(\d{44})["\']', content_str)
            if not chave_match:
                chave_match = re.search(r'<(?:chnfe|chcte|chmdfe)>(\d{44})</', content_str)
            if chave_match:
                ano = "20" + chave_match.group(1)[2:4]
                mes = chave_match.group(1)[4:6]

        if mes == "00": mes = "01"
        if ano == "0000": ano = "2000"

        # 3. Define a Pasta
        if cnpj_emit == client_cnpj_clean:
            return f"EMISSAO_PROPRIA/{ano}/{mes}"
        else:
            return f"TERCEIROS/{ano}/{mes}"
            
    except Exception:
        return "OUTROS"

# --- FUNÇÃO RECURSIVA OTIMIZADA PARA DISCO ---
def extrair_recursivo(conteudo_ou_file, nome_arquivo):
    if not os.path.exists(TEMP_EXTRACT_DIR): 
        os.makedirs(TEMP_EXTRACT_DIR)
        
    if nome_arquivo.lower().endswith('.zip'):
        try:
            file_obj = conteudo_ou_file if hasattr(conteudo_ou_file, 'read') else io.BytesIO(conteudo_ou_file)
            with zipfile.ZipFile(file_obj) as z:
                for sub_nome in z.namelist():
                    if sub_nome.startswith('__MACOSX') or os.path.basename(sub_nome).startswith('.'): 
                        continue
                        
                    if sub_nome.lower().endswith('.zip'):
                        temp_path = z.extract(sub_nome, path=TEMP_EXTRACT_DIR)
                        with open(temp_path, 'rb') as f_temp:
                            yield from extrair_recursivo(f_temp, sub_nome)
                        try: os.remove(temp_path)
                        except: pass
                    elif sub_nome.lower().endswith('.xml'):
                        yield (os.path.basename(sub_nome), z.read(sub_nome))
        except: 
            pass
    elif nome_arquivo.lower().endswith('.xml'):
        if hasattr(conteudo_ou_file, 'read'): 
            yield (os.path.basename(nome_arquivo), conteudo_ou_file.read())
        else: 
            yield (os.path.basename(nome_arquivo), conteudo_ou_file)

# --- LIMPEZA DE PASTAS TEMPORÁRIAS ---
def limpar_arquivos_temp():
    try:
        for f in os.listdir('.'):
            if f.endswith('.zip') and f.startswith('extracao_turbo'):
                try: os.remove(f)
                except: pass
            
        if os.path.exists(TEMP_EXTRACT_DIR): 
            shutil.rmtree(TEMP_EXTRACT_DIR, ignore_errors=True)
        if os.path.exists(TEMP_UPLOADS_DIR): 
            shutil.rmtree(TEMP_UPLOADS_DIR, ignore_errors=True)
    except: 
        pass

# --- DIVISOR DE LOTES HTML ---
def chunk_list(lst, n):
    for i in range(0, len(lst), n): 
        yield lst[i:i + n]

# --- INTERFACE PRINCIPAL ---
st.markdown("<h1>⚡ EXTRATOR TURBO XML</h1>", unsafe_allow_html=True)

with st.container():
    st.markdown("""
    <div class="instrucoes-card">
        <h3>🚀 Separação Brutal e Rápida</h3>
        <p>Este sistema não gera Excel, não audita falhas e não checa Sefaz. Ele apenas descompacta tudo, separa por Origem e Mês, e empacota de volta para você.</p>
        <ul>
            <li><b>1.</b> Digite o CNPJ do Cliente (para o robô saber o que é "Própria" e o que é "Terceiros").</li>
            <li><b>2.</b> Arraste as pastas/zips gigantes de notas.</li>
            <li><b>3.</b> Ele cria as pastas: <code>EMISSAO_PROPRIA/Ano/Mes</code> e <code>TERCEIROS/Ano/Mes</code>.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Controle de sessão
keys_to_init = ['confirmado', 'processamento_concluido', 'lotes_gerados', 'total_xmls']
for k in keys_to_init:
    if k not in st.session_state:
        if k == 'lotes_gerados': st.session_state[k] = []
        elif k == 'total_xmls': st.session_state[k] = 0
        else: st.session_state[k] = False

with st.sidebar:
    st.markdown("### 🔍 Identificação")
    cnpj_input = st.text_input("CNPJ DO CLIENTE", placeholder="00.000.000/0001-00")
    cnpj_limpo = "".join(filter(str.isdigit, cnpj_input))
    
    if cnpj_input and len(cnpj_limpo) != 14: 
        st.error("⚠️ CNPJ Inválido.")
        
    if len(cnpj_limpo) == 14:
        if st.button("✅ LIBERAR EXTRAÇÃO"): 
            st.session_state['confirmado'] = True
            
    st.divider()
    if st.button("🗑️ RESETAR SISTEMA"):
        limpar_arquivos_temp()
        st.session_state.clear()
        st.rerun()

if st.session_state['confirmado']:
    if not st.session_state['processamento_concluido']:
        uploaded_files = st.file_uploader("📂 ARRASTE AQUI SEUS ARQUIVOS (XML ou ZIP):", accept_multiple_files=True)
        
        if uploaded_files and st.button("⚡ INICIAR SEPARAÇÃO TURBO"):
            limpar_arquivos_temp() 
            os.makedirs(TEMP_UPLOADS_DIR, exist_ok=True)
            
            progresso_bar = st.progress(0)
            status_text = st.empty()
            
            with st.status("⚡ Turbo Ativado! Escaneando e separando...", expanded=True) as status_box:
                
                # 1. Salva uploads fisicamente
                for i, f in enumerate(uploaded_files):
                    caminho_salvo = os.path.join(TEMP_UPLOADS_DIR, f.name)
                    with open(caminho_salvo, "wb") as out_f:
                        out_f.write(f.read())
                
                lista_salvos = os.listdir(TEMP_UPLOADS_DIR)
                total_salvos = len(lista_salvos)
                
                nomes_unicos_vistos = set()
                lotes_parts = []
                current_count = 0
                curr_part = 1
                
                zip_name = f'extracao_turbo_pt{curr_part}.zip'
                z_out = zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED)
                lotes_parts.append(zip_name)
                
                total_xmls_extraidos = 0
                
                # 2. Leitura super rápida
                for i, f_name in enumerate(lista_salvos):
                    if i % 20 == 0: gc.collect()
                        
                    progresso_bar.progress((i + 1) / total_salvos)
                    status_text.text(f"⚡ Separando arquivo {i+1}/{total_salvos}: {f_name}")
                    
                    caminho_leitura = os.path.join(TEMP_UPLOADS_DIR, f_name)
                    try:
                        with open(caminho_leitura, "rb") as file_obj:
                            todos_xmls = extrair_recursivo(file_obj, f_name)
                            for name, xml_data in todos_xmls:
                                
                                # Proteção contra nomes duplicados
                                nome_final = name
                                if nome_final in nomes_unicos_vistos:
                                    name_parts = os.path.splitext(name)
                                    random_sufix = str(random.randint(1000, 9999))
                                    nome_final = f"{name_parts[0]}_{random_sufix}{name_parts[1]}"
                                    
                                nomes_unicos_vistos.add(nome_final)
                                
                                # A mágica da separação rápida
                                pasta_destino = get_xml_minimal_info(xml_data, cnpj_limpo)
                                
                                # Lógica Anti-Crash de Lotes
                                if current_count >= MAX_XML_PER_ZIP:
                                    z_out.close()
                                    curr_part += 1
                                    zip_name = f'extracao_turbo_pt{curr_part}.zip'
                                    z_out = zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED)
                                    lotes_parts.append(zip_name)
                                    current_count = 0
                                    
                                # Escreve o arquivo dentro da pasta certa no ZIP
                                z_out.writestr(f"{pasta_destino}/{nome_final}", xml_data)
                                current_count += 1
                                total_xmls_extraidos += 1
                                
                                del xml_data 
                    except Exception: 
                        continue
                
                if z_out: z_out.close()
                
                status_box.update(label=f"✅ Sucesso! {total_xmls_extraidos} XMLs separados.", state="complete", expanded=False)
                progresso_bar.empty(); status_text.empty()

            st.session_state['total_xmls'] = total_xmls_extraidos
            st.session_state['lotes_gerados'] = lotes_parts
            st.session_state['processamento_concluido'] = True
            st.rerun()

    else:
        # --- TELA DE RESULTADO (DOWNLOADS) ---
        st.success(f"🎉 Separação concluída! Foram organizados **{st.session_state['total_xmls']}** arquivos XML.")
        
        st.markdown("### 📥 DOWNLOADS DISPONÍVEIS")
        st.write("Os seus arquivos estão separados por pastas (`EMISSAO_PROPRIA/Mes` e `TERCEIROS/Mes`). Se o volume for gigante, ele foi dividido em lotes numéricos para não travar o seu download.")
        
        lista_lotes = st.session_state['lotes_gerados']
        
        for row in chunk_list(lista_lotes, 3):
            cols = st.columns(len(row))
            for idx, part_name in enumerate(row):
                if os.path.exists(part_name):
                    part_num = re.search(r'pt(\d+)', part_name).group(1)
                    tamanho_mb = os.path.getsize(part_name) / (1024 * 1024)
                    
                    label = f"📂 BAIXAR LOTE {part_num} ({tamanho_mb:.1f} MB)" if len(lista_lotes) > 1 else f"📂 BAIXAR ARQUIVOS SEPARADOS ({tamanho_mb:.1f} MB)"
                    with cols[idx]:
                        with open(part_name, 'rb') as f:
                            st.download_button(
                                label=label, 
                                data=f.read(), 
                                file_name=f"xml_separados_pt{part_num}.zip", 
                                mime="application/zip", 
                                use_container_width=True
                            )
                            
        st.divider()
        if st.button("⚡ FAZER NOVA EXTRAÇÃO"):
            limpar_arquivos_temp()
            st.session_state.clear()
            st.rerun()
else:
    st.warning("👈 Insira o CNPJ na barra lateral para começar a separação.")
