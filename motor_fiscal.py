import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
import re
import io

def extrair_dados_xml(files, fluxo="Saída"):
    """
    Extração profunda de XMLs NFe com foco em Auditoria Fiscal.
    Captura tags de ICMS, PIS, COFINS, IPI e DIFAL.
    """
    dados_lista = []
    if not files:
        return pd.DataFrame()

    for f in files:
        try:
            f.seek(0)
            conteudo_bruto = f.read()
            texto_xml = conteudo_bruto.decode('utf-8', errors='replace')
            
            # Limpeza de namespaces para facilitar a busca
            texto_xml = re.sub(r'<\?xml[^?]*\?>', '', texto_xml)
            texto_xml = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', texto_xml)
            root = ET.fromstring(texto_xml)
            
            def buscar(caminho, raiz=root):
                alvo = raiz.find(f'.//{caminho}')
                return alvo.text if alvo is not None and alvo.text is not None else ""

            inf_nfe = root.find('.//infNFe')
            chave_acesso = inf_nfe.attrib.get('Id', '')[3:] if inf_nfe is not None else ""
            
            # Dados do Emitente e Destinatário
            emit = root.find('.//emit')
            dest = root.find('.//dest')
            uf_emit = buscar('UF', emit)
            uf_dest = buscar('UF', dest)
            cnpj_emit = buscar('CNPJ', emit)
            cnpj_dest = buscar('CNPJ', dest)

            # Detalhamento de Itens
            for det in root.findall('.//det'):
                prod = det.find('prod')
                imp = det.find('imposto')
                nitem = det.attrib.get('nItem', '0')
                ncm_limpo = re.sub(r'\D', '', buscar('NCM', prod)).zfill(8)
                
                linha = {
                    "CHAVE_ACESSO": chave_acesso,
                    "NUM_NF": buscar('nNF'),
                    "DATA_EMISSAO": buscar('dhEmi')[:10] if buscar('dhEmi') else "",
                    "CNPJ_EMIT": cnpj_emit,
                    "UF_EMIT": uf_emit,
                    "CNPJ_DEST": cnpj_dest,
                    "UF_DEST": uf_dest,
                    "ITEM": nitem,
                    "CFOP": buscar('CFOP', prod),
                    "NCM": ncm_limpo,
                    "COD_PROD": buscar('cProd', prod),
                    "DESCR": buscar('xProd', prod),
                    "UNID": buscar('uCom', prod),
                    "QTDE": float(buscar('qCom', prod) or 0),
                    "VUNIT": float(buscar('vUnCom', prod) or 0),
                    "VPROD": float(buscar('vProd', prod) or 0),
                    "VFRETE": float(buscar('vFrete', prod) or 0),
                    "VSEG": float(buscar('vSeg', prod) or 0),
                    "VDESC": float(buscar('vDesc', prod) or 0),
                    "VOUTRAS": float(buscar('vOutro', prod) or 0),
                    # Impostos - Inicialização
                    "CST-ICMS": "", "BC-ICMS": 0.0, "ALQ-ICMS": 0.0, "VLR-ICMS": 0.0,
                    "BC-ICMSST": 0.0, "VLR-ICMSST": 0.0,
                    "CST-PIS": "", "BC-PIS": 0.0, "ALQ-PIS": 0.0, "VLR-PIS": 0.0,
                    "CST-COF": "", "BC-COF": 0.0, "ALQ-COF": 0.0, "VLR-COF": 0.0,
                    "CST-IPI": "", "BC-IPI": 0.0, "ALQ-IPI": 0.0, "VLR-IPI": 0.0,
                    "VLR-DIFAL-DEST": 0.0, "VLR-FCP-DEST": 0.0
                }

                if imp is not None:
                    # Lógica ICMS (Normal e Simples Nacional)
                    icms_node = imp.find('.//ICMS')
                    if icms_node is not None:
                        for n in icms_node:
                            cst = n.find('CST') if n.find('CST') is not None else n.find('CSOSN')
                            if cst is not None: linha["CST-ICMS"] = cst.text.zfill(2)
                            if n.find('vBC') is not None: linha["BC-ICMS"] = float(n.find('vBC').text)
                            if n.find('pICMS') is not None: linha["ALQ-ICMS"] = float(n.find('pICMS').text)
                            if n.find('vICMS') is not None: linha["VLR-ICMS"] = float(n.find('vICMS').text)
                            if n.find('vBCST') is not None: linha["BC-ICMSST"] = float(n.find('vBCST').text)
                            if n.find('vICMSST') is not None: linha["VLR-ICMSST"] = float(n.find('vICMSST').text)

                    # Lógica PIS
                    pis_node = imp.find('.//PIS')
                    if pis_node is not None:
                        for p in pis_node:
                            if p.find('CST') is not None: linha["CST-PIS"] = p.find('CST').text.zfill(2)
                            if p.find('vBC') is not None: linha["BC-PIS"] = float(p.find('vBC').text)
                            if p.find('pPIS') is not None: linha["ALQ-PIS"] = float(p.find('pPIS').text)
                            if p.find('vPIS') is not None: linha["VLR-PIS"] = float(p.find('vPIS').text)

                    # Lógica COFINS
                    cof_node = imp.find('.//COFINS')
                    if cof_node is not None:
                        for c in cof_node:
                            if c.find('CST') is not None: linha["CST-COF"] = c.find('CST').text.zfill(2)
                            if c.find('vBC') is not None: linha["BC-COF"] = float(c.find('vBC').text)
                            if c.find('pCOFINS') is not None: linha["ALQ-COF"] = float(c.find('pCOFINS').text)
                            if c.find('vCOFINS') is not None: linha["VLR-COF"] = float(c.find('vCOFINS').text)

                    # Lógica IPI
                    ipi_node = imp.find('.//IPI')
                    if ipi_node is not None:
                        cst_ipi = ipi_node.find('.//CST')
                        if cst_ipi is not None: linha["CST-IPI"] = cst_ipi.text.zfill(2)
                        if ipi_node.find('.//vBC') is not None: linha["BC-IPI"] = float(ipi_node.find('.//vBC').text)
                        if ipi_node.find('.//pIPI') is not None: linha["ALQ-IPI"] = float(ipi_node.find('.//pIPI').text)
                        if ipi_node.find('.//vIPI') is not None: linha["VLR-IPI"] = float(ipi_node.find('.//vIPI').text)

                    # Lógica DIFAL
                    difal_node = imp.find('.//ICMSUFDest')
                    if difal_node is not None:
                        if difal_node.find('vICMSUFDest') is not None: linha["VLR-DIFAL-DEST"] = float(difal_node.find('vICMSUFDest').text)
                        if difal_node.find('vFCPUFDest') is not None: linha["VLR-FCP-DEST"] = float(difal_node.find('vFCPUFDest').text)

                dados_lista.append(linha)
        except Exception as e:
            continue

    return pd.DataFrame(dados_lista)

def gerar_excel_final(df_xe, df_xs, ge_file=None, gs_file=None, ae_file=None, as_file=None):
    """
    Consolida todas as fontes de dados em um único relatório Excel formatado.
    """
    def load_csv_blindado(f, col_names):
        if not f: return pd.DataFrame()
        try:
            f.seek(0)
            raw = f.read().decode('utf-8-sig', errors='replace')
            sep = ';' if raw.count(';') > raw.count(',') else ','
            df = pd.read_csv(io.StringIO(raw), sep=sep, header=None, engine='python', dtype={0: str})
            # Remove cabeçalho se houver texto na primeira célula numérica
            if not str(df.iloc[0, 0]).strip().isdigit():
                df = df.iloc[1:]
            df = df.iloc[:, :len(col_names)]
            df.columns = col_names
            return df
        except:
            return pd.DataFrame()

    # Definição de colunas conforme padrão do usuário
    c_ent = ['NF','DATA','CNPJ','UF','VLR_NF','AC','CFOP','COD','DESC','NCM','UNID','VUNIT','QTDE','VPROD','DESC_P','FRETE','SEG','DESP','VC','CST_ICMS','COL2','BC_ICMS','V_ICMS','BC_ST','V_ST','V_IPI','CST_PIS','BC_PIS','V_PIS','CST_COF','BC_COF','V_COF']
    c_sai = ['NF','DATA','CNPJ','UF','VC','AC','CFOP','COD','VUNIT','QTDE','VITEM','DESC','FRETE','SEG','OUTRO','VC_I','CST','COL2','COL3','BC_ICMS','ALQ_ICMS','V_ICMS','BC_ST','V_ST','V_IPI','CST_PIS','BC_PIS','V_PIS','CST_COF','BC_COF','V_COF']

    df_ge = load_csv_blindado(ge_file, c_ent)
    df_gs = load_csv_blindado(gs_file, c_sai)
    
    # Autenticidade
    df_ae = pd.read_excel(ae_file) if ae_file else pd.DataFrame()
    df_as = pd.read_excel(as_file) if as_file else pd.DataFrame()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        if not df_xe.empty: df_xe.to_excel(writer, sheet_name='XML_ENTRADAS', index=False)
        if not df_xs.empty: df_xs.to_excel(writer, sheet_name='XML_SAIDAS', index=False)
        if not df_ge.empty: df_ge.to_excel(writer, sheet_name='GERENCIAL_ENTRADAS', index=False)
        if not df_gs.empty: df_gs.to_excel(writer, sheet_name='GERENCIAL_SAIDAS', index=False)
        if not df_ae.empty: df_ae.to_excel(writer, sheet_name='AUTENTICIDADE_ENT', index=False)
        if not df_as.empty: df_as.to_excel(writer, sheet_name='AUTENTICIDADE_SAI', index=False)

        # Formatação básica das abas
        workbook = writer.book
        for sheetname in writer.sheets:
            worksheet = writer.sheets[sheetname]
            worksheet.set_column('A:AZ', 18)

    return output.getvalue()
