import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
import re
import io

def extrair_dados_xml(files):
    dados_lista = []
    if not files: return pd.DataFrame()
    for f in files:
        try:
            f.seek(0)
            conteudo = f.read().decode('utf-8', errors='replace')
            root = ET.fromstring(re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', conteudo))
            
            def buscar(caminho, raiz=root):
                alvo = raiz.find(f'.//{caminho}')
                return alvo.text if alvo is not None and alvo.text is not None else ""

            inf_nfe = root.find('.//infNFe')
            chave = inf_nfe.attrib.get('Id', '')[3:] if inf_nfe is not None else ""
            
            for det in root.findall('.//det'):
                prod = det.find('prod')
                imp = det.find('imposto')
                linha = {
                    "CHAVE_ACESSO": chave, "NUM_NF": buscar('nNF'),
                    "DATA_EMISSAO": buscar('dhEmi')[:10] if buscar('dhEmi') else "",
                    "UF_EMIT": buscar('UF', root.find('.//emit')), "UF_DEST": buscar('UF', root.find('.//dest')),
                    "AC": int(det.attrib.get('nItem', '0')), "CFOP": buscar('CFOP', prod),
                    "NCM": re.sub(r'\D', '', buscar('NCM', prod)).zfill(8),
                    "COD_PROD": buscar('cProd', prod), "DESCR": buscar('xProd', prod),
                    "VPROD": float(buscar('vProd', prod) or 0),
                    "CST-ICMS": "", "BC-ICMS": 0.0, "VLR-ICMS": 0.0,
                    "CST-PIS": "", "VAL-PIS": 0.0, "CST-COF": "", "VAL-COF": 0.0
                }
                if imp is not None:
                    ic = imp.find('.//ICMS')
                    if ic is not None:
                        for n in ic:
                            cst = n.find('CST') or n.find('CSOSN')
                            if cst is not None: linha["CST-ICMS"] = cst.text.zfill(2)
                            if n.find('vBC') is not None: linha["BC-ICMS"] = float(n.find('vBC').text)
                            if n.find('vICMS') is not None: linha["VLR-ICMS"] = float(n.find('vICMS').text)
                dados_lista.append(linha)
        except: continue
    return pd.DataFrame(dados_lista)

def gerar_excel_final(df_xe, df_xs, ge=None, gs=None, ae=None, as_f=None):
    def load_csv(f, cols):
        if not f: return pd.DataFrame()
        try:
            f.seek(0); raw = f.read().decode('utf-8-sig'); sep = ';' if raw.count(';') > raw.count(',') else ','
            df = pd.read_csv(io.StringIO(raw), sep=sep, header=None, engine='python', dtype={0: str})
            if not str(df.iloc[0,0]).isdigit(): df = df.iloc[1:]
            df = df.iloc[:, :len(cols)]; df.columns = cols
            return df
        except: return pd.DataFrame()
    
    c_e = ['NF','DATA','CNPJ','UF','VLR_NF','AC','CFOP','COD','DESC','NCM','UNID','VUNIT','QTDE','VPROD','DESC_P','FRETE','SEG','DESP','VC','CST_ICMS','COL2','BC_ICMS','V_ICMS','BC_ST','V_ST','V_IPI','CST_PIS','BC_PIS','V_PIS','CST_COF','BC_COF','V_COF']
    c_s = ['NF','DATA','CNPJ','UF','VC','AC','CFOP','COD','VUNIT','QTDE','VITEM','DESC','FRETE','SEG','OUTRO','VC_I','CST','COL2','COL3','BC_ICMS','ALQ_ICMS','V_ICMS','BC_ST','V_ST','V_IPI','CST_PIS','BC_PIS','V_PIS','CST_COF','BC_COF','V_COF']
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as wr:
        if not df_xe.empty: df_xe.to_excel(wr, sheet_name='XML_ENTRADAS', index=False)
        if not df_xs.empty: df_xs.to_excel(wr, sheet_name='XML_SAIDAS', index=False)
        load_csv(ge, c_e).to_excel(wr, sheet_name='GER_ENT', index=False)
        load_csv(gs, c_s).to_excel(wr, sheet_name='GER_SAI', index=False)
    return output.getvalue()
