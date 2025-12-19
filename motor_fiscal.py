import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
import re
import io
import streamlit as st

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
                prod = det.find('prod')
                imp = det.find('imposto')
                ncm_limpo = re.sub(r'\D', '', buscar('NCM', prod)).zfill(8)
                
                linha = {
                    "CHAVE_ACESSO": chave_acesso, "NUM_NF": buscar('nNF'),
                    "DATA_EMISSAO": pd.to_datetime(buscar('dhEmi')).replace(tzinfo=None) if buscar('dhEmi') else None,
                    "UF_EMIT": buscar('UF', root.find('.//emit')), "UF_DEST": buscar('UF', root.find('.//dest')),
                    "AC": int(det.attrib.get('nItem', '0')), "CFOP": buscar('CFOP', prod), "NCM": ncm_limpo,
                    "COD_PROD": buscar('cProd', prod), "DESCR": buscar('xProd', prod),
                    "VPROD": float(buscar('vProd', prod)) if buscar('vProd', prod) else 0.0,
                    "CST-ICMS": "", "BC-ICMS": 0.0, "VLR-ICMS": 0.0, "ALQ-ICMS": 0.0, "ICMS-ST": 0.0,
                    "CST-PIS": "", "ALQ-PIS": 0.0, "VAL-PIS": 0.0, 
                    "CST-COF": "", "ALQ-COF": 0.0, "VAL-COF": 0.0,
                    "BC-FED": 0.0, "VBC-IPI": 0.0, "VAL-IPI": 0.0, "VAL-DIFAL": 0.0
                }

                if imp is not None:
                    # ICMS
                    icms_nodo = imp.find('.//ICMS')
                    if icms_nodo is not None:
                        for nodo in icms_nodo:
                            cst = nodo.find('CST') if nodo.find('CST') is not None else nodo.find('CSOSN')
                            if cst is not None: linha["CST-ICMS"] = cst.text.zfill(2)
                            if nodo.find('vBC') is not None: linha["BC-ICMS"] = float(nodo.find('vBC').text)
                            if nodo.find('vICMS') is not None: linha["VLR-ICMS"] = float(nodo.find('vICMS').text)
                            if nodo.find('pICMS') is not None: linha["ALQ-ICMS"] = float(nodo.find('pICMS').text)
                            if nodo.find('vICMSST') is not None: linha["ICMS-ST"] = float(nodo.find('vICMSST').text)
                    
                    # PIS
                    pis = imp.find('.//PIS')
                    if pis is not None:
                        for p in pis:
                            if p.find('CST') is not None: linha["CST-PIS"] = p.find('CST').text.zfill(2)
                            if p.find('vBC') is not None: linha["BC-FED"] = float(p.find('vBC').text)
                            if p.find('pPIS') is not None: linha["ALQ-PIS"] = float(p.find('pPIS').text)
                            if p.find('vPIS') is not None: linha["VAL-PIS"] = float(p.find('vPIS').text)
                    
                    # COFINS
                    cof = imp.find('.//COFINS')
                    if cof is not None:
                        for c in cof:
                            if c.find('pCOFINS') is not None: linha["ALQ-COF"] = float(c.find('pCOFINS').text)
                            if c.find('vCOFINS') is not None: linha["VAL-COF"] = float(c.find('vCOFINS').text)

                dados_lista.append(linha)
        except: continue
    return pd.DataFrame(dados_lista)

def gerar_excel_final(df_ent, df_sai):
    def limpar_txt(v): return str(v).replace('.0', '').strip()
    
    # Bases
    try:
        base_icms = pd.read_excel(".streamlit/Base_ICMS.xlsx")
        base_icms['NCM_KEY'] = base_icms.iloc[:, 0].apply(limpar_txt).str.replace(r'\D', '', regex=True).str.zfill(8)
    except: base_icms = pd.DataFrame()

    try:
        base_pis = pd.read_excel(".streamlit/Base_CST_Pis_Cofins.xlsx")
        base_pis['NCM_KEY'] = base_pis.iloc[:, 0].apply(limpar_txt).str.replace(r'\D', '', regex=True).str.zfill(8)
        base_pis.columns = [c.upper() for c in base_pis.columns] # Normaliza nomes das colunas
    except: base_pis = pd.DataFrame()

    if df_sai is None or df_sai.empty: df_sai = pd.DataFrame([{"AVISO": "Sem dados"}])
    def format_brl(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # --- AUDITORIA ICMS ---
    df_icms = df_sai.copy()
    ncms_st = df_ent[(df_ent['CST-ICMS']=="60") | (df_ent['ICMS-ST'] > 0)]['NCM'].unique().tolist() if df_ent is not None and not df_ent.empty else []

    def audit_icms(row):
        ncm = str(row['NCM']).zfill(8)
        info = base_icms[base_icms['NCM_KEY'] == ncm] if not base_icms.empty else pd.DataFrame()
        st_ent = "✅ ST Localizado" if ncm in ncms_st else "❌ Sem ST na Entrada"
        if info.empty: return pd.Series([st_ent, "NCM Ausente na Base", format_brl(row['VLR-ICMS']), "R$ 0,00", "Cadastrar NCM"])
        aliq_esp = float(info.iloc[0, 3]) if row['UF_EMIT'] == row['UF_DEST'] else 12.0
        return pd.Series([st_ent, "✅ Correto" if abs(row['ALQ-ICMS'] - aliq_esp) < 0.1 else "Aliq. Divergente", format_brl(row['VLR-ICMS']), format_brl(row['BC-ICMS']*aliq_esp/100), "Ajustar Alíquota" if abs(row['ALQ-ICMS'] - aliq_esp) > 0.1 else "✅ Correto"])

    df_icms[['ST na Entrada', 'Diagnóstico', 'ICMS XML', 'ICMS Esperado', 'Ação']] = df_icms.apply(audit_icms, axis=1)

    # --- AUDITORIA PIS/COFINS (CORREÇÃO DO INDEXERROR) ---
    df_pc = df_sai.copy()
    def audit_pc(row):
        ncm = str(row['NCM']).zfill(8)
        info = base_pis[base_pis['NCM_KEY'] == ncm] if not base_pis.empty else pd.DataFrame()
        
        if info.empty: 
            return pd.Series(["NCM não mapeado", format_brl(row['VAL-PIS']+row['VAL-COF']), "R$ 0,00", "Verificar NCM"])
        
        # Tenta pegar alíquota por nome de coluna ou posição segura
        try:
            aliq_p_esp = float(info.iloc[0]['ALQ_PIS']) if 'ALQ_PIS' in info.columns else 1.65
            aliq_c_esp = float(info.iloc[0]['ALQ_COFINS']) if 'ALQ_COFINS' in info.columns else 7.6
        except:
            aliq_p_esp, aliq_c_esp = 1.65, 7.6

        diag_pc, acao_pc = [], []
        if abs(row['ALQ-PIS'] - aliq_p_esp) > 0.01: diag_pc.append("PIS Divergente"); acao_pc.append("Ajustar PIS")
        if abs(row['ALQ-COF'] - aliq_c_esp) > 0.01: diag_pc.append("COF Divergente"); acao_pc.append("Ajustar COF")
        
        esp_total = (row['BC-FED'] * (aliq_p_esp + aliq_c_esp) / 100)
        return pd.Series(["; ".join(diag_pc) if diag_pc else "✅ Correto", format_brl(row['VAL-PIS']+row['VAL-COF']), format_brl(esp_total), " + ".join(acao_pc) if acao_pc else "✅ Correto"])

    df_pc[['Diagnóstico', 'Total PIS/COF XML', 'Esperado Total', 'Ação']] = df_pc.apply(audit_pc, axis=1)

    # --- OUTRAS ABAS ---
    df_ipi = df_sai.copy(); df_ipi['ANALISE'] = ""
    df_difal = df_sai.copy()
    df_difal['Análise DIFAL'] = np.where((df_difal['UF_EMIT'] != df_difal['UF_DEST']) & (df_difal['VAL-DIFAL'] == 0), "❌ Erro", "✅ OK")

    mem = io.BytesIO()
    with pd.ExcelWriter(mem, engine='xlsxwriter') as wr:
        if df_ent is not None and not df_ent.empty: df_ent.to_excel(wr, sheet_name='ENTRADAS', index=False)
        df_sai.to_excel(wr, sheet_name='SAIDAS', index=False)
        df_icms.to_excel(wr, sheet_name='ICMS', index=False)
        df_pc.to_excel(wr, sheet_name='PIS_COFINS', index=False)
        df_ipi.to_excel(wr, sheet_name='IPI', index=False)
        df_difal.to_excel(wr, sheet_name='DIFAL', index=False)
    return mem.getvalue()
