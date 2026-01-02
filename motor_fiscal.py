import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
import re
import io

def extrair_dados_xml(files, fluxo, df_autenticidade=None):
    dados_lista = []
    if not files: return pd.DataFrame()
    for f in files:
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

            inf_nfe = root.find('.//infNFe')
            chave_acesso = inf_nfe.attrib.get('Id', '')[3:] if inf_nfe is not None else ""
            
            for det in root.findall('.//det'):
                prod = det.find('prod'); imp = det.find('imposto')
                ncm_limpo = re.sub(r'\D', '', buscar('NCM', prod)).zfill(8)
                linha = {
                    "CHAVE_ACESSO": chave_acesso, "NUM_NF": buscar('nNF'),
                    "DATA_EMISSAO": pd.to_datetime(buscar('dhEmi')).replace(tzinfo=None) if buscar('dhEmi') else None,
                    "UF_EMIT": buscar('UF', root.find('.//emit')), "UF_DEST": buscar('UF', root.find('.//dest')),
                    "AC": int(det.attrib.get('nItem', '0')), "CFOP": buscar('CFOP', prod), "NCM": ncm_limpo,
                    "COD_PROD": buscar('cProd', prod), "DESCR": buscar('xProd', prod),
                    "VPROD": float(buscar('vProd', prod)) if buscar('vProd', prod) else 0.0,
                    "CST-ICMS": "", "BC-ICMS": 0.0, "VLR-ICMS": 0.0, "ALQ-ICMS": 0.0, "ICMS-ST": 0.0,
                    "CST-PIS": "", "CST-COF": "", "VAL-PIS": 0.0, "VAL-COF": 0.0, "BC-FED": 0.0,
                    "CST-IPI": "", "VAL-IPI": 0.0, "BC-IPI": 0.0, "ALQ-IPI": 0.0, "VAL-DIFAL": 0.0
                }
                if imp is not None:
                    ic = imp.find('.//ICMS')
                    if ic is not None:
                        for n in ic:
                            cst = n.find('CST') if n.find('CST') is not None else n.find('CSOSN')
                            if cst is not None: linha["CST-ICMS"] = cst.text.zfill(2)
                            if n.find('vBC') is not None: linha["BC-ICMS"] = float(n.find('vBC').text)
                            if n.find('vICMS') is not None: linha["VLR-ICMS"] = float(n.find('vICMS').text)
                dados_lista.append(linha)
        except: continue
    return pd.DataFrame(dados_lista)

def gerar_excel_final(df_ent, df_sai, file_ger_ent=None, file_ger_sai=None):
    def load_ger(f, target_cols):
        if not f: return pd.DataFrame()
        try:
            f.seek(0); raw = f.read().decode('utf-8-sig', errors='replace'); sep = ';' if raw.count(';') > raw.count(',') else ','
            df = pd.read_csv(io.StringIO(raw), sep=sep, header=None, engine='python', dtype={0: str})
            if df.shape[0] > 0 and not str(df.iloc[0, 0]).strip().isdigit(): df = df.iloc[1:]
            df = df.iloc[:, :len(target_cols)]; df.columns = target_cols
            return df
        except: return pd.DataFrame()

    c_sai = ['NF','DATA_EMISSAO','CNPJ','Ufp','VC','AC','CFOP','COD_ITEM','VUNIT','QTDE','VITEM','DESC','FRETE','SEG','OUTRAS','VC_ITEM','CST','Coluna2','Coluna3','BC_ICMS','ALIQ_ICMS','ICMS','BC_ICMSST','ICMSST','IPI','CST_PIS','BC_PIS','PIS','CST_COF','BC_COF','COF']
    c_ent = ['NUM_NF','DATA_EMISSAO','CNPJ','UF','VLR_NF','AC','CFOP','COD_PROD','DESCR','NCM','UNID','VUNIT','QTDE','VPROD','DESC','FRETE','SEG','DESP','VC','CST-ICMS','Coluna2','BC-ICMS','VLR-ICMS','BC-ICMS-ST','ICMS-ST','VLR_IPI','CST_PIS','BC_PIS','VLR_PIS','CST_COF','BC_COF','VLR_COF']
    
    df_ge = load_ger(file_ger_ent, c_ent); df_gs = load_ger(file_ger_sai, c_sai)

    mem = io.BytesIO()
    with pd.ExcelWriter(mem, engine='xlsxwriter') as wr:
        if not df_ent.empty: df_ent.to_excel(wr, sheet_name='ENTRADAS_XML', index=False)
        if not df_sai.empty: df_sai.to_excel(wr, sheet_name='SAIDAS_XML', index=False)
        if not df_ge.empty: df_ge.to_excel(wr, sheet_name='Gerencial Entradas', index=False)
        if not df_gs.empty: df_gs.to_excel(wr, sheet_name='Gerencial Saídas', index=False)
        for s in wr.sheets: wr.sheets[s].set_column('A:A', 20, wr.book.add_format({'num_format': '@'}))
    return mem.getvalue()
