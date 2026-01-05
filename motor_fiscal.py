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
            emit = root.find('.//emit')
            dest = root.find('.//dest')
            
            for det in root.findall('.//det'):
                prod = det.find('prod')
                imp = det.find('imposto')
                
                linha = {
                    "CHAVE_ACESSO": chave,
                    "NUM_NF": buscar('nNF'),
                    "DATA_EMISSAO": buscar('dhEmi')[:10] if buscar('dhEmi') else "",
                    "CNPJ_EMIT": buscar('CNPJ', emit),
                    "UF_EMIT": buscar('UF', emit),
                    "CNPJ_DEST": buscar('CNPJ', dest),
                    "UF_DEST": buscar('UF', dest),
                    "ITEM": det.attrib.get('nItem', '0'),
                    "CFOP": buscar('CFOP', prod),
                    "NCM": re.sub(r'\D', '', buscar('NCM', prod)).zfill(8),
                    "COD_PROD": buscar('cProd', prod),
                    "DESCR": buscar('xProd', prod),
                    "VPROD": float(buscar('vProd', prod) or 0),
                    "CST-ICMS": "", "BC-ICMS": 0.0, "ALQ-ICMS": 0.0, "VLR-ICMS": 0.0,
                    "CST-PIS": "", "BC-PIS": 0.0, "ALQ-PIS": 0.0, "VLR-PIS": 0.0,
                    "CST-COFINS": "", "BC-COFINS": 0.0, "ALQ-COFINS": 0.0, "VLR-COFINS": 0.0
                }

                if imp is not None:
                    # ICMS
                    icms = imp.find('.//ICMS')
                    if icms is not None:
                        for n in icms:
                            cst = n.find('CST') or n.find('CSOSN')
                            if cst is not None: linha["CST-ICMS"] = cst.text.zfill(2)
                            if n.find('vBC') is not None: linha["BC-ICMS"] = float(n.find('vBC').text)
                            if n.find('vICMS') is not None: linha["VLR-ICMS"] = float(n.find('vICMS').text)
                            if n.find('pICMS') is not None: linha["ALQ-ICMS"] = float(n.find('pICMS').text)
                    
                    # PIS
                    pis = imp.find('.//PIS')
                    if pis is not None:
                        for p in pis:
                            if p.find('CST') is not None: linha["CST-PIS"] = p.find('CST').text.zfill(2)
                            if p.find('vBC') is not None: linha["BC-PIS"] = float(p.find('vBC').text)
                            if p.find('pPIS') is not None: linha["ALQ-PIS"] = float(p.find('pPIS').text)
                            if p.find('vPIS') is not None: linha["VLR-PIS"] = float(p.find('vPIS').text)
                            
                    # COFINS
                    cof = imp.find('.//COFINS')
                    if cof is not None:
                        for c in cof:
                            if c.find('CST') is not None: linha["CST-COFINS"] = c.find('CST').text.zfill(2)
                            if c.find('vBC') is not None: linha["BC-COFINS"] = float(c.find('vBC').text)
                            if c.find('pCOFINS') is not None: linha["ALQ-COFINS"] = float(c.find('pCOFINS').text)
                            if c.find('vCOFINS') is not None: linha["VLR-COFINS"] = float(c.find('vCOFINS').text)

                dados_lista.append(linha)
        except: continue
    return pd.DataFrame(dados_lista)

def gerar_excel_final(df_xe, df_xs, ge_file=None, gs_file=None, ae_file=None, as_file=None):
    def load_csv(f, cols):
        if not f: return pd.DataFrame()
        try:
            f.seek(0); raw = f.read().decode('utf-8-sig'); sep = ';' if raw.count(';') > raw.count(',') else ','
            df = pd.read_csv(io.StringIO(raw), sep=sep, header=None, engine='python', dtype={0: str})
            if not str(df.iloc[0, 0]).strip().isdigit(): df = df.iloc[1:]
            df = df.iloc[:, :len(cols)]; df.columns = cols
            return df
        except: return pd.DataFrame()

    c_e = ['NF','DATA','CNPJ','UF','VLR_NF','AC','CFOP','COD','DESC','NCM','UNID','VUNIT','QTDE','VPROD','DESC_P','FRETE','SEG','DESP','VC','CST_ICMS','COL2','BC_ICMS','V_ICMS','BC_ST','V_ST','V_IPI','CST_PIS','BC_PIS','V_PIS','CST_COF','BC_COF','V_COF']
    c_s = ['NF','DATA','CNPJ','UF','VC','AC','CFOP','COD','VUNIT','QTDE','VITEM','DESC','FRETE','SEG','OUTRO','VC_I','CST','COL2','COL3','BC_ICMS','ALQ_ICMS','V_ICMS','BC_ST','V_ST','V_IPI','CST_PIS','BC_PIS','V_PIS','CST_COF','BC_COF','V_COF']

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # 1. XMLs Brutos
        if not df_xe.empty: df_xe.to_excel(writer, sheet_name='XML_ENTRADAS', index=False)
        if not df_xs.empty: df_xs.to_excel(writer, sheet_name='XML_SAIDAS', index=False)
        
        # 2. Gerenciais
        df_ge = load_csv(ge_file, c_e)
        df_gs = load_csv(gs_file, c_s)
        if not df_ge.empty: df_ge.to_excel(writer, sheet_name='GERENCIAL_ENT', index=False)
        if not df_gs.empty: df_gs.to_excel(writer, sheet_name='GERENCIAL_SAI', index=False)
        
        # 3. ABA DE ANÁLISE (Onde as conferências acontecem)
        if not df_xs.empty and not df_gs.empty:
            # Exemplo de Análise: Cruzamento XML vs Gerencial
            df_comp = pd.merge(df_xs[['NUM_NF', 'VPROD', 'VLR-ICMS']], 
                             df_gs[['NF', 'VITEM', 'V_ICMS']], 
                             left_on='NUM_NF', right_on='NF', how='left')
            df_comp.to_excel(writer, sheet_name='CONFERENCIA_VALORES', index=False)
            
    return output.getvalue()
