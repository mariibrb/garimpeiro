import pandas as pd
import xml.etree.ElementTree as ET
import re
import io
import os

def extrair_dados_xml(files, fluxo):
    dados_lista = []
    if not files: return pd.DataFrame()

    for f in files:
        try:
            f.seek(0)
            xml_utf8 = f.read().decode('utf-8', errors='ignore')
            xml_limpo = re.sub(r' xmlns="[^"]+"', '', xml_utf8)
            root = ET.fromstring(xml_limpo)
            
            ide = root.find('.//ide')
            emit = root.find('.//emit')
            dest = root.find('.//dest')
            
            num_nf = int(ide.find('nNF').text) if ide.find('nNF') is not None else 0
            data_emissao = ide.find('dhEmi').text if ide.find('dhEmi') is not None else None
            vlr_nf = float(root.find('.//vNF').text) if root.find('.//vNF') is not None else 0.0

            if fluxo == "Entrada":
                cnpj = emit.find('CNPJ').text if emit.find('CNPJ') is not None else ""
                uf = emit.find('UF').text if emit.find('UF') is not None else ""
            else:
                cnpj = dest.find('CNPJ').text if dest is not None and dest.find('CNPJ') is not None else ""
                uf = dest.find('UF').text if dest is not None and dest.find('UF') is not None else ""

            for det in root.findall('.//det'):
                n_item = det.attrib.get('nItem')
                prod = det.find('prod')
                imp = det.find('imposto')
                
                item = {
                    "NUM_NF": num_nf, "DATA_EMISSAO": pd.to_datetime(data_emissao).replace(tzinfo=None) if data_emissao else None,
                    "CNPJ": cnpj, "UF": uf, "VLR_NF": vlr_nf, "AC": int(n_item) if n_item else 0,
                    "CFOP": int(prod.find('CFOP').text) if prod.find('CFOP') is not None else 0,
                    "COD_PROD": prod.find('cProd').text if prod.find('cProd') is not None else "",
                    "DESCR": prod.find('xProd').text if prod.find('xProd') is not None else "",
                    "NCM": prod.find('NCM').text if prod.find('NCM') is not None else "",
                    "UNID": prod.find('uCom').text if prod.find('uCom') is not None else "",
                    "VUNIT": float(prod.find('vUnCom').text) if prod.find('vUnCom') is not None else 0.0,
                    "QTDE": float(prod.find('qCom').text) if prod.find('qCom') is not None else 0.0,
                    "VPROD": float(prod.find('vProd').text) if prod.find('vProd') is not None else 0.0,
                    "DESC": float(prod.find('vDesc').text) if prod.find('vDesc') is not None else 0.0,
                    "FRETE": float(prod.find('vFrete').text) if prod.find('vFrete') is not None else 0.0,
                    "SEG": float(prod.find('vSeg').text) if prod.find('vSeg') is not None else 0.0,
                    "DESP": float(prod.find('vOutro').text) if prod.find('vOutro') is not None else 0.0,
                    "VC": 0.0, "CST-ICMS": "", "BC-ICMS": 0.0, "VLR-ICMS": 0.0, "BC-ICMS-ST": 0.0, "ICMS-ST": 0.0,
                    "VLR_IPI": 0.0, "CST_PIS": "", "BC_PIS": 0.0, "VLR_PIS": 0.0, "CST_COF": "", "BC_COF": 0.0, "VLR_COF": 0.0,
                    "FCP": 0.0, "ICMS UF Dest": 0.0,
                    "STATUS": "", "Análise CST ICMS": "", "CST x BC": "", "Analise Aliq ICMS": ""
                }

                icms_node = imp.find('.//ICMS')
                if icms_node is not None:
                    for tag in icms_node:
                        cst = tag.find('CST') if tag.find('CST') is not None else tag.find('CSOSN')
                        item["CST-ICMS"] = cst.text if cst is not None else ""
                        item["BC-ICMS"] = float(tag.find('vBC').text) if tag.find('vBC') is not None else 0.0
                        item["VLR-ICMS"] = float(tag.find('vICMS').text) if tag.find('vICMS') is not None else 0.0
                
                item["VC"] = item["VPROD"] + item["ICMS-ST"] + item["VLR_IPI"] + item["DESP"] - item["DESC"]
                dados_lista.append(item)
        except: continue
    return pd.DataFrame(dados_lista)

def gerar_excel_final(df_ent, df_sai):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        if not df_ent.empty: df_ent.to_excel(writer, sheet_name='ENTRADAS', index=False)
        if not df_sai.empty: df_sai.to_excel(writer, sheet_name='SAIDAS', index=False)
        # Criação das abas vazias de auditoria (para você preencher na AO depois)
        pd.DataFrame().to_excel(writer, sheet_name='ICMS', index=False)
        pd.DataFrame().to_excel(writer, sheet_name='IPI', index=False)
        pd.DataFrame().to_excel(writer, sheet_name='PIS_COFINS', index=False)
        pd.DataFrame().to_excel(writer, sheet_name='DIFAL', index=False)
    return output.getvalue()
