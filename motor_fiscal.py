import pandas as pd
import xml.etree.ElementTree as ET
import re
import io
import streamlit as st

def extrair_dados_xml(files, fluxo):
    """
    Processa tanto XML de Entrada quanto de Saída com proteção contra tags faltantes.
    """
    dados_lista = []
    if not files: 
        return pd.DataFrame()

    # Barra de progresso para acompanhar o processamento
    progresso = st.progress(0)
    total = len(files)
    
    for i, f in enumerate(files):
        try:
            f.seek(0)
            xml_utf8 = f.read().decode('utf-8', errors='replace')
            # Limpeza de namespaces para evitar erros de localização de tags
            xml_limpo = re.sub(r'\sxmlns="[^"]+"', '', xml_utf8)
            xml_limpo = re.sub(r'\sxmlns:[\w]+="[^"]+"', '', xml_limpo)
            root = ET.fromstring(xml_limpo)
            
            ide = root.find('.//ide')
            emit = root.find('.//emit')
            dest = root.find('.//dest')
            total_nf = root.find('.//total/ICMSTot')
            
            # Dados principais da nota (com proteção se a tag não existir)
            num_nf = int(ide.find('nNF').text) if ide is not None and ide.find('nNF') is not None else 0
            data_emissao = ide.find('dhEmi').text if ide is not None and ide.find('dhEmi') is not None else None
            vlr_nf = float(total_nf.find('vNF').text) if total_nf is not None and total_nf.find('vNF') is not None else 0.0

            # Lógica Automática de Fluxo:
            # Se for Entrada, pega o CNPJ de quem emitiu. Se for Saída, de quem recebeu.
            if fluxo == "Entrada":
                cnpj = emit.find('CNPJ').text if emit is not None and emit.find('CNPJ') is not None else ""
                uf = emit.find('UF').text if emit is not None and emit.find('UF') is not None else ""
            else:
                cnpj = dest.find('CNPJ').text if dest is not None and dest.find('CNPJ') is not None else ""
                uf = dest.find('UF').text if dest is not None and dest.find('UF') is not None else ""

            # Varre os itens da nota (Tag <det>)
            for det in root.findall('.//det'):
                prod = det.find('prod')
                imp = det.find('imposto')
                n_item = det.attrib.get('nItem', '0')
                
                # Criamos o dicionário com valores padrão (Vazio ou 0.0)
                # Se o XML não tiver a tag, ele preenche com o valor abaixo em vez de dar erro
                item = {
                    "NUM_NF": num_nf,
                    "DATA_EMISSAO": pd.to_datetime(data_emissao).replace(tzinfo=None) if data_emissao else None,
                    "CNPJ": cnpj, "UF": uf, "VLR_NF": vlr_nf, "AC": int(n_item),
                    "CFOP": int(prod.find('CFOP').text) if prod is not None and prod.find('CFOP') is not None else 0,
                    "COD_PROD": prod.find('cProd').text if prod is not None and prod.find('cProd') is not None else "",
                    "DESCR": prod.find('xProd').text if prod is not None and prod.find('xProd') is not None else "",
                    "NCM": prod.find('NCM').text if prod is not None and prod.find('NCM') is not None else "",
                    "UNID": prod.find('uCom').text if prod is not None and prod.find('uCom') is not None else "",
                    "VUNIT": float(prod.find('vUnCom').text) if prod is not None and prod.find('vUnCom') is not None else 0.0,
                    "QTDE": float(prod.find('qCom').text) if prod is not None and prod.find('qCom') is not None else 0.0,
                    "VPROD": float(prod.find('vProd').text) if prod is not None and prod.find('vProd') is not None else 0.0,
                    "DESC": float(prod.find('vDesc').text) if prod is not None and prod.find('vDesc') is not None else 0.0,
                    "FRETE": float(prod.find('vFrete').text) if prod is not None and prod.find('vFrete') is not None else 0.0,
                    "SEG": float(prod.find('vSeg').text) if prod is not None and prod.find('vSeg') is not None else 0.0,
                    "DESP": float(prod.find('vOutro').text) if prod is not None and prod.find('vOutro') is not None else 0.0,
                    "VC": 0.0, "CST-ICMS": "", "BC-ICMS": 0.0, "VLR-ICMS": 0.0, "BC-ICMS-ST": 0.0, "ICMS-ST": 0.0,
                    "VLR_IPI": 0.0, "CST_PIS": "", "BC_PIS": 0.0, "VLR_PIS": 0.0, "CST_COF": "", "BC_COF": 0.0, "VLR_COF": 0.0,
                    "FCP": 0.0, "ICMS UF Dest": 0.0, "STATUS": "", "Análise CST ICMS": "", "CST x BC": "", "Analise Aliq ICMS": ""
                }

                # Tenta ler tributos; se não existir a tag, o valor do item continua 0.0
                if imp is not None:
                    # Leitura de ICMS
                    icms_tree = imp.find('.//ICMS')
                    if icms_tree is not None:
                        for nodo in icms_tree:
                            cst = nodo.find('CST') if nodo.find('CST') is not None else nodo.find('CSOSN')
                            if cst is not None: item["CST-ICMS"] = cst.text
                            if nodo.find('vBC') is not None: item["BC-ICMS"] = float(nodo.find('vBC').text)
                            if nodo.find('vICMS') is not None: item["VLR-ICMS"] = float(nodo.find('vICMS').text)
                            if nodo.find('vBCST') is not None: item["BC-ICMS-ST"] = float(nodo.find('vBCST').text)
                            if nodo.find('vICMSST') is not None: item["ICMS-ST"] = float(nodo.find('vICMSST').text)

                    # Leitura de IPI
                    ipi_vlr = imp.find('.//IPI/IPITrib/vIPI')
                    if ipi_vlr is not None: item["VLR_IPI"] = float(ipi_vlr.text)

                    # Leitura de PIS e COFINS
                    pis_v = imp.find('.//PIS//vPIS')
                    if pis_v is not None: item["VLR_PIS"] = float(pis_v.text)
                    cof_v = imp.find('.//COFINS//vCOFINS')
                    if cof_v is not None: item["VLR_COF"] = float(cof_v.text)

                # Cálculo do Valor Contábil (seguindo sua regra anterior)
                item["VC"] = item["VPROD"] + item["ICMS-ST"] + item["VLR_IPI"] + item["DESP"] - item["DESC"]
                dados_lista.append(item)
            
            # Atualiza o progresso visual no Streamlit
            progresso.progress((i + 1) / total)

        except:
            # Se o arquivo estiver muito corrompido, ele pula, mas com errors='replace' isso é raro
            continue
    
    return pd.DataFrame(dados_lista)

def gerar_excel_final(df_ent, df_sai):
    """
    Consolida tudo em um arquivo Excel com abas separadas.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        if not df_ent.empty: 
            df_ent.to_excel(writer, sheet_name='ENTRADAS', index=False)
        if not df_sai.empty: 
            df_sai.to_excel(writer, sheet_name='SAIDAS', index=False)
        
        # Abas extras de auditoria conforme seu modelo
        for aba in ['ICMS', 'IPI', 'PIS_COFINS', 'DIFAL']:
            # Pega as colunas da entrada para manter o padrão, ou cria vazio
            cols = df_ent.columns if not df_ent.empty else []
            pd.DataFrame(columns=cols).to_excel(writer, sheet_name=aba, index=False)
            
    return output.getvalue()
