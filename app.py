import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import re
import os
import io

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Sentinela - Nascel",
    page_icon="🛡️",
    layout="wide"
)

# --- 2. CSS PERSONALIZADO (Identidade Nascel) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main-title { font-size: 2.5rem; font-weight: 700; color: #555555; margin-bottom: 0px; }
    .sub-title { font-size: 1rem; color: #FF8C00; font-weight: 600; margin-bottom: 30px; }
    .feature-card {
        background-color: white; padding: 20px; border-radius: 10px;
        border: 1px solid #E0E0E0; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: center; transition: all 0.3s ease; height: 100%;
    }
    .feature-card:hover { transform: translateY(-5px); border-color: #FF8C00; box-shadow: 0 10px 15px rgba(255, 140, 0, 0.15); }
    .card-icon { font-size: 2rem; margin-bottom: 10px; display: block; }
    .stButton button { width: 100%; border-radius: 8px; font-weight: 600; }
    [data-testid='stFileUploader'] section { background-color: #FFF8F0; border: 1px dashed #FF8C00; }
</style>
""", unsafe_allow_html=True)

# --- 3. FUNÇÕES DE LÓGICA (O CÉREBRO) ---

def extrair_tags_simples(arquivos_upload):
    """Extrai apenas dados básicos para conferência de autenticidade"""
    lista = []
    for arquivo in arquivos_upload:
        try:
            content = arquivo.read()
            arquivo.seek(0)
            try: xml_str = content.decode('utf-8')
            except: xml_str = content.decode('latin-1')
            
            # Limpeza
            xml_str = re.sub(r' xmlns="[^"]+"', '', xml_str)
            root = ET.fromstring(xml_str)
            
            infNFe = root.find('.//infNFe')
            ide = root.find('.//ide')
            
            if infNFe is not None and ide is not None:
                chave = infNFe.attrib.get('Id', '')[3:]
                numero = ide.find('nNF').text if ide.find('nNF') is not None else "0"
                lista.append({'Arquivo': arquivo.name, 'Chave': chave, 'Numero': int(numero)})
        except:
            pass
    return pd.DataFrame(lista)

def carregar_status_sefaz(file_status):
    """Lê o excel de status da sefaz"""
    if not file_status: return {}
    try:
        if file_status.name.endswith('.xlsx'): df = pd.read_excel(file_status, dtype=str)
        else: df = pd.read_csv(file_status, dtype=str)
        # Assume coluna 0 como Chave e coluna 5 como Status (ajuste conforme seu arquivo real)
        return dict(zip(df.iloc[:, 0].str.replace(r'\D', '', regex=True), df.iloc[:, 5]))
    except:
        return {}

# --- 4. CABEÇALHO ---
col_logo, col_text = st.columns([1, 5])
with col_logo:
    logo_path = "nascel sem fundo.png"
    if not os.path.exists(logo_path): logo_path = ".streamlit/nascel sem fundo.png"
    if os.path.exists(logo_path): st.image(logo_path, width=150)
    else: st.markdown("### NASCEL")

with col_text:
    st.markdown('<div class="main-title">Sentinela Fiscal</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Central de Auditoria e Compliance</div>', unsafe_allow_html=True)

st.divider()

# --- 5. UPLOADS ---
st.markdown("### 📂 1. Importação de Arquivos")
c1, c2, c3 = st.columns(3, gap="medium")

with c1:
    st.markdown('<div class="feature-card"><span class="card-icon">📥</span><b>Entradas XML</b></div>', unsafe_allow_html=True)
    xml_entradas = st.file_uploader("Upload Entradas", type=["xml"], accept_multiple_files=True, label_visibility="collapsed", key="in")

with c2:
    st.markdown('<div class="feature-card"><span class="card-icon">📤</span><b>Saídas XML</b></div>', unsafe_allow_html=True)
    xml_saidas = st.file_uploader("Upload Saídas", type=["xml"], accept_multiple_files=True, label_visibility="collapsed", key="out")

with c3:
    st.markdown('<div class="feature-card"><span class="card-icon">📋</span><b>Status Sefaz (Excel)</b></div>', unsafe_allow_html=True)
    file_status = st.file_uploader("Upload Status", type=["xlsx", "csv"], label_visibility="collapsed", key="stat")

st.markdown("<br>", unsafe_allow_html=True)

# --- 6. BOTÕES DE AUTENTICIDADE (AGORA FUNCIONAM!) ---
st.markdown("### 🛡️ 2. Validação de Autenticidade")
c_auth_ent, c_auth_sai = st.columns(2, gap="medium")

# --- LÓGICA AUTENTICIDADE ENTRADAS ---
with c_auth_ent:
    st.info("Valida status Sefaz das Notas de Compra.")
    if st.button("🔍 Verificar Entradas", type="primary", use_container_width=True):
        if not xml_entradas:
            st.error("⚠️ Falta XML de Entrada.")
        elif not file_status:
            st.error("⚠️ Falta arquivo de Status Sefaz.")
        else:
            df_ent = extrair_tags_simples(xml_entradas)
            dic_status = carregar_status_sefaz(file_status)
            
            if not df_ent.empty:
                df_ent['Status Sefaz'] = df_ent['Chave'].map(dic_status).fillna("Não Encontrado")
                
                # Resumo
                st.success("✅ Verificação Concluída!")
                st.write(df_ent['Status Sefaz'].value_counts())
                
                # Mostra tabela colorida
                def color_status(val):
                    color = '#d4edda' if 'Autorizada' in str(val) else '#f8d7da' if 'Cancelada' in str(val) else ''
                    return f'background-color: {color}'
                
                st.dataframe(df_ent.style.map(color_status, subset=['Status Sefaz']), use_container_width=True)
            else:
                st.warning("Não foi possível ler os XMLs.")

# --- LÓGICA AUTENTICIDADE SAÍDAS ---
with c_auth_sai:
    st.info("Valida sequência e status das Vendas.")
    if st.button("🔍 Verificar Saídas", type="primary", use_container_width=True):
        if not xml_saidas:
            st.error("⚠️ Falta XML de Saída.")
        elif not file_status:
            st.error("⚠️ Falta arquivo de Status Sefaz.")
        else:
            df_sai = extrair_tags_simples(xml_saidas)
            dic_status = carregar_status_sefaz(file_status)
            
            if not df_sai.empty:
                df_sai['Status Sefaz'] = df_sai['Chave'].map(dic_status).fillna("Não Encontrado")
                
                # Verifica Sequência Numérica (Pulos)
                df_sai = df_sai.sort_values('Numero')
                numeros = df_sai['Numero'].tolist()
                pulos = []
                if len(numeros) > 1:
                    for i in range(len(numeros)-1):
                        if numeros[i+1] != numeros[i] + 1:
                            pulos.append(f"{numeros[i]} -> {numeros[i+1]}")
                
                c_res1, c_res2 = st.columns(2)
                with c_res1:
                    st.metric("Total Notas", len(df_sai))
                with c_res2:
                    st.metric("Pulos de Numeração", len(pulos))
                
                if pulos:
                    st.warning(f"⚠️ Pulos detectados: {', '.join(pulos[:5])}...")
                
                st.dataframe(df_sai, use_container_width=True)
            else:
                st.warning("Não foi possível ler os XMLs.")

# --- 7. RELATÓRIOS GERENCIAIS (PLACEHOLDERS) ---
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("### 📊 3. Relatórios Gerenciais")
c_ger_ent, c_ger_sai = st.columns(2, gap="medium")

with c_ger_ent:
    if st.button("📈 Gerar Relatório Gerencial Entradas", use_container_width=True):
        st.info("Funcionalidade em desenvolvimento... (Implemente sua lógica de Dashboard aqui)")

with c_ger_sai:
    if st.button("📈 Gerar Relatório Gerencial Saídas", use_container_width=True):
        st.info("Funcionalidade em desenvolvimento... (Implemente sua lógica de Dashboard aqui)")
