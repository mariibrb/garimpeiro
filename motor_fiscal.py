import pandas as pd
import xml.etree.ElementTree as ET
import re
import io
import streamlit as st

def extrair_dados_xml(files, fluxo):
    dados_lista = []
    if not files: 
        return pd.DataFrame()

    progresso = st.progress(0)
    total = len(files)
    
    for i, f in enumerate(files):
        try:
            f.seek(0)
            xml_utf8 = f.read().decode('utf-8', errors='replace')
            xml_limpo = re.sub(r'\sxmlns="[^"]+"', '', xml_utf8)
            xml_limpo = re.sub(r'\sxmlns:[\w]+="[^"]+"', '', xml_limpo)
            root = ET.fromstring(xml_limpo)
            
            # Localiza blocos (se não achar, o código não trava mais)
            ide = root.find('.//ide')
            emit = root.find('.//emit')
            dest = root.find('.//dest')
            total_nf = root.find('.//total/ICMSTot')
            
            # Pega dados básicos ou deixa vazio/zero
            num_nf = int(ide.find('nNF').text) if ide is not None and ide.find('nNF') is not None else 0
            data_emissao = ide.find('dhEmi').text if ide is not None and ide.find('dhEmi') is not None else None
            vlr_nf = float(total_nf.find('vNF').text) if total_nf is not None and total_nf.find('vNF') is not None else 0.0

            if fluxo == "Entrada":
                cnpj = emit.find('CNPJ').text if emit is not None and emit.find('CNPJ') is not None else ""
                uf = emit.find('UF').text if emit is not None and emit.find('UF') is not None else ""
            else:
                cnpj = dest.find('CNPJ').text if dest is not None and dest.find('CNPJ') is not None else ""
                uf = dest.find('UF').text if dest is not None and dest.find('UF') is not None else ""

            # LER ITENS - Aqui está a mágica: se não tiver a tag, ele preenche com padrão
            for det in root.findall('.//det'):
                prod = det.find('prod')
                imp = det.find('imposto')
                n_item = det.attrib.get('nItem', '0')
                
                # Criamos o dicionário com valores padrão (vazio ou 0.0)
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

                # Tenta ler tributos, se não existir a tag, o valor do dicionário continua o padrão
                if imp is not None:
                    # ICMS
                    icms_tree = imp.find('.//ICMS')
                    if icms_tree is not None:
                        for nodo in icms_tree:
                            cst = nodo.find('CST') if nodo.find('CST') is not None else nodo.find('CSOSN')
                            if cst is not None: item["CST-ICMS"] = cst.text
                            if nodo.find('vBC') is not None: item["BC-ICMS"] = float(nodo.find('vBC').text)
                            if nodo.find('vICMS') is not None: item["VLR-ICMS"] = float(nodo.find('vICMS').text)

                    # IPI
                    ipi_vlr = imp.find('.//IPI/IPITrib/vIPI')
                    if ipi_vlr is not None: item["VLR_IPI"] = float(ipi_vlr.text)

                    # PIS/COFINS (mesma lógica de segurança)
                    pis_v = imp.find('.//PIS//vPIS')
                    if pis_v is not None: item["VLR_PIS"] = float(pis_v.text)
                    cof_v = imp.find('.//COFINS//vCOFINS')
                    if cof_v is not None: item["VLR_COF"] = float(cof_v.text)

                # Cálculo do Valor Contábil
                item["VC"] = item["VPROD"] + item["ICMS-ST"] + item["VLR_IPI"] + item["DESP"] - item["DESC"]
                dados_lista.append(item)
            
            progresso.progress((i + 1) / total)

        except:
            continue
    
    return pd.DataFrame(dados_lista)

def gerar_excel_final(df_ent, df_sai):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        if not df_ent.empty: df_ent.to_excel(writer, sheet_name='ENTRADAS', index=False)
        if not df_sai.empty: df_sai.to_excel(writer, sheet_name='SAIDAS', index=False)
        # Cria as outras abas conforme o seu modelo
        for aba in ['ICMS', 'IPI', 'PIS_COFINS', 'DIFAL']:
            pd.DataFrame(columns=df_ent.columns if not df_ent.empty else []).to_excel(writer, sheet_name=aba, index=False)
    return output.getvalue()
