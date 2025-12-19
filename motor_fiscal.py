import pandas as pd
import xml.etree.ElementTree as ET
import re
import io
import streamlit as st

def extrair_dados_xml(files, fluxo):
    """
    Leitura binária ultra-resistente.
    """
    dados_lista = []
    if not files: 
        return pd.DataFrame()

    container_status = st.empty()
    progresso = st.progress(0)
    total_arquivos = len(files)
    
    for i, f in enumerate(files):
        try:
            f.seek(0)
            conteudo_bruto = f.read()
            texto_xml = conteudo_bruto.decode('utf-8', errors='replace')
            
            texto_xml = re.sub(r'<\?xml[^?]*\?>', '', texto_xml)
            texto_xml = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', texto_xml)
            
            root = ET.fromstring(texto_xml)
            
            def buscar(caminho, raiz=root):
                alvo = raiz.find(f'.//{caminho}')
                return alvo.text if alvo is not None and alvo.text is not None else ""

            num_nf = buscar('nNF')
            data_emi = buscar('dhEmi')
            vlr_nf = buscar('vNF')
            
            bloco_parceiro = 'emit' if fluxo == "Entrada" else 'dest'
            parceiro = root.find(f'.//{bloco_parceiro}')
            cnpj = buscar('CNPJ', parceiro) if parceiro is not None else ""
            uf = buscar('UF', parceiro) if parceiro is not None else ""

            itens = root.findall('.//det')
            for det in itens:
                prod = det.find('prod')
                imp = det.find('imposto')
                n_item = det.attrib.get('nItem', '0')
                
                linha = {
                    "NUM_NF": num_nf,
                    "DATA_EMISSAO": pd.to_datetime(data_emi).replace(tzinfo=None) if data_emi else None,
                    "CNPJ": cnpj, "UF": uf, 
                    "VLR_NF": float(vlr_nf) if vlr_nf else 0.0, 
                    "AC": int(n_item),
                    "CFOP": buscar('CFOP', prod),
                    "COD_PROD": buscar('cProd', prod),
                    "DESCR": buscar('xProd', prod),
                    "NCM": buscar('NCM', prod),
                    "UNID": buscar('uCom', prod),
                    "VUNIT": float(buscar('vUnCom', prod)) if buscar('vUnCom', prod) else 0.0,
                    "QTDE": float(buscar('qCom', prod)) if buscar('qCom', prod) else 0.0,
                    "VPROD": float(buscar('vProd', prod)) if buscar('vProd', prod) else 0.0,
                    "DESC": float(buscar('vDesc', prod)) if buscar('vDesc', prod) else 0.0,
                    "FRETE": float(buscar('vFrete', prod)) if buscar('vFrete', prod) else 0.0,
                    "SEG": float(buscar('vSeg', prod)) if buscar('vSeg', prod) else 0.0,
                    "DESP": float(buscar('vOutro', prod)) if buscar('vOutro', prod) else 0.0,
                    "VC": 0.0, "CST-ICMS": "", "BC-ICMS": 0.0, "VLR-ICMS": 0.0, 
                    "BC-ICMS-ST": 0.0, "ICMS-ST": 0.0, "VLR_IPI": 0.0, 
                    "CST_PIS": "", "BC_PIS": 0.0, "VLR_PIS": 0.0, 
                    "CST_COF": "", "BC_COF": 0.0, "VLR_COF": 0.0,
                    "FCP": 0.0, "ICMS UF Dest": 0.0, "STATUS": "", 
                    "Análise CST ICMS": "", "CST x BC": "", "Analise Aliq ICMS": ""
                }

                if imp is not None:
                    # ICMS
                    icms_data = imp.find('.//ICMS')
                    if icms_data is not None:
                        for nodo in icms_data:
                            cst = nodo.find('CST') if nodo.find('CST') is not None else nodo.find('CSOSN')
                            if cst is not None: linha["CST-ICMS"] = cst.text
                            if nodo.find('vBC') is not None: linha["BC-ICMS"] = float(nodo.find('vBC').text)
                            if nodo.find('vICMS') is not None: linha["VLR-ICMS"] = float(nodo.find('vICMS').text)
                            if nodo.find('vBCST') is not None: linha["BC-ICMS-ST"] = float(nodo.find('vBCST').text)
                            if nodo.find('vICMSST') is not None: linha["ICMS-ST"] = float(nodo.find('vICMSST').text)

                    # PIS/COFINS/IPI
                    vipi = imp.find('.//vIPI')
                    if vipi is not None: linha["VLR_IPI"] = float(vipi.text)
                    vpis = imp.find('.//vPIS')
                    if vpis is not None: linha["VLR_PIS"] = float(vpis.text)
                    vcof = imp.find('.//vCOFINS')
                    if vcof is not None: linha["VLR_COF"] = float(vcof.text)
                    
                    # DIFAL / FCP
                    fcp = imp.find('.//vFCP')
                    if fcp is not None: linha["FCP"] = float(fcp.text)
                    uf_dest = imp.find('.//vICMSUFDest')
                    if uf_dest is not None: linha["ICMS UF Dest"] = float(uf_dest.text)

                linha["VC"] = linha["VPROD"] + linha["ICMS-ST"] + linha["VLR_IPI"] + linha["DESP"] - linha["DESC"]
                dados_lista.append(linha)
            
            container_status.text(f"📊 Processando {i+1} de {total_arquivos}...")
            progresso.progress((i + 1) / total_arquivos)

        except: continue
    
    container_status.empty()
    progresso.empty()
    return pd.DataFrame(dados_lista)

def gerar_excel_final(df_ent, df_sai):
    """
    Replicação INTEGRAL das Saídas para as abas de tributos.
    """
    memoria = io.BytesIO()
    with pd.ExcelWriter(memoria, engine='xlsxwriter') as escritor:
        # Aba Entradas
        if not df_ent.empty: 
            df_ent.to_excel(escritor, sheet_name='ENTRADAS', index=False)
        
        # Aba Saídas (Base para todas as outras)
        if not df_sai.empty: 
            df_sai.to_excel(escritor, sheet_name='SAIDAS', index=False)
            
            # REPLICAÇÃO TOTAL (Sem filtros)
            # Levamos exatamente o mesmo conteúdo para cada aba técnica
            df_sai.to_excel(escritor, sheet_name='ICMS', index=False)
            df_sai.to_excel(escritor, sheet_name='IPI', index=False)
            df_sai.to_excel(escritor, sheet_name='PIS_COFINS', index=False)
            df_sai.to_excel(escritor, sheet_name
