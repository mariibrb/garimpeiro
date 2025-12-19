# --- SIDEBAR (BARRA LATERAL) ---
with st.sidebar:
    # Mostra sua logo se o arquivo existir
    if os.path.exists(".streamlit/nascel sem fundo.png"):
        st.image(".streamlit/nascel sem fundo.png", use_container_width=True)
    
    st.markdown("---")
    st.subheader("📥 Baixar Modelos")
    
    # Criando os modelos para download na hora
    df_modelo = pd.DataFrame(columns=['NCM', 'REFERENCIA', 'DADOS'])
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_modelo.to_excel(writer, index=False)
    
    # Botão para o modelo de ICMS
    st.download_button(
        label="📂 Modelo ICMS",
        data=buffer.getvalue(),
        file_name="modelo_icms.xlsx",
        use_container_width=True
    )
    
    # Botão para o modelo de PIS e COFINS
    st.download_button(
        label="📂 Modelo PIS e COFINS",
        data=buffer.getvalue(),
        file_name="modelo_pis_cofins.xlsx",
        use_container_width=True
    )

    st.markdown("---")
    st.subheader("📤 Atualizar Bases")
    
    # Campos para você subir suas planilhas oficiais
    up_i = st.file_uploader("Atualizar Base ICMS", type=['xlsx'], key='up_i_side')
    if up_i:
        with open(".streamlit/Base_ICMS.xlsx", "wb") as f:
            f.write(up_i.getbuffer())
        st.success("Base ICMS atualizada!")

    up_p = st.file_uploader("Atualizar Base PIS/COF", type=['xlsx'], key='up_p_side')
    if up_p:
        with open(".streamlit/Base_CST_Pis_Cofins.xlsx", "wb") as f:
            f.write(up_p.getbuffer())
        st.success("Base PIS/COF atualizada!")
