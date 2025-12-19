import pandas as pd
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
                    # ICMS
                    "CST-ICMS": "", "BC-ICMS": 0.0, "VLR-ICMS": 0.0, "ALQ-ICMS": 0.0, "ICMS-ST": 0.0,
                    # IPI
                    "CST-IPI": "", "BC-IPI": 0.0, "VLR-IPI": 0.0, "ALQ-IPI": 0.0
                }

                if imp is not None:
                    # Coleta ICMS
                    icms_nodo = imp.find('.//ICMS')
                    if icms_nodo is not None:
                        for nodo in icms_nodo:
                            cst = nodo.find('CST') if nodo.find('CST') is not None else nodo.find('CSOSN')
                            if cst is not None: linha["CST-ICMS"] = cst.text.zfill(2)
                            if nodo.find('vBC') is not None: linha["BC-ICMS"] = float(nodo.find('vBC').text)
                            if nodo.find('vICMS') is not None: linha["VLR-ICMS"] = float(nodo.find('vICMS').text)
                            if nodo.find('pICMS') is not None: linha["ALQ-ICMS"] = float(nodo.find('pICMS').text)
                    
                    # Coleta IPI
                    ipi_nodo = imp.find('.//IPI')
                    if ipi_nodo is not None:
                        cst_ipi = ipi_nodo.find('.//CST')
                        if cst_ipi is not None: linha["CST-IPI"] = cst_ipi.text.zfill(2)
                        if ipi_nodo.find('.//vBC') is not None: linha["BC-IPI"] = float(ipi_nodo.find('.//vBC').text)
                        if ipi_nodo.find('.//vIPI') is not None: linha["VLR-IPI"] = float(ipi_nodo.find('.//vIPI').text)
                        if ipi_nodo.find('.//pIPI') is not None: linha["ALQ-IPI"] = float(ipi_nodo.find('.//pIPI').text)
                
                dados_lista.append(linha)
        except: continue
    return pd.DataFrame(dados_lista)

def gerar_excel_final(df_ent, df_sai):
    try:
        # Uso da Base de ICMS e Base de IPI conforme as fotos do GitHub
        base_icms = pd.read_excel(".streamlit/Base_ICMS.xlsx")
        base_ipi = pd.read_excel(".streamlit/Base_IPI.xlsx")
        
        def limpar_texto(val): return str(val).replace('.0', '').strip()
        
        # Padronização Base ICMS
        base_icms['NCM_KEY'] = base_icms.iloc[:, 0].apply(limpar_texto).str.replace(r'\D', '', regex=True).str.zfill(8)
        base_icms['CST_ESP'] = base_icms.iloc[:, 2].apply(limpar_texto).str.zfill(2)
        
        # Padronização Base IPI
        base_ipi['NCM_KEY'] = base_ipi.iloc[:, 0].apply(limpar_texto).str.replace(r'\D', '', regex=True).str.zfill(8)
        base_ipi['CST_ESP'] = base_ipi.iloc[:, 2].apply(limpar_texto).str.zfill(2)
        base_ipi['ALQ_ESP'] = base_ipi.iloc[:, 3].fillna(0).astype(float)
        
    except Exception as e:
        st.error(f"Erro ao carregar bases: {e}")
        return None

    df_icms_audit = df_sai.copy()
    df_ipi_audit = df_sai.copy()
    tem_entradas = df_ent is not None and not df_ent.empty
    ncms_ent_st = df_ent[(df_ent['CST-ICMS']=="60") | (df_ent['ICMS-ST'] > 0)]['NCM'].unique().tolist() if tem_entradas else []

    def format_brl(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # Auditoria IPI - Seguindo Aprovação 1
    def auditoria_ipi(row):
        ncm_atual = str(row['NCM']).strip().zfill(8)
        info_ncm = base_ipi[base_ipi['NCM_KEY'] == ncm_atual]
        
        if info_ncm.empty:
            return pd.Series([ncm_atual, f"NCM {ncm_atual} Ausente na Base IPI", format_brl(row['VLR-IPI']), "R$ 0,00", "Cadastrar NCM na Base IPI"])

        cst_esp = str(info_ncm.iloc[0]['CST_ESP'])
        aliq_esp = float(info_ncm.iloc[0]['ALQ_ESP'])
        cst_xml = str(row['CST-IPI']).strip().zfill(2)

        diag_list, acoes_list = [], []

        if cst_xml != cst_esp:
            diag_list.append(f"CST IPI: Destacado {cst_xml} | Esperado {cst_esp}")
            acoes_list.append(f"Cc-e (Corrigir CST IPI para {cst_esp})")

        if abs(row['ALQ-IPI'] - aliq_esp) > 0.01:
            diag_list.append(f"Aliq IPI: Destacada {row['ALQ-IPI']}% | Esperada {aliq_esp}%")
            acoes_list.append("Revisar Alíquota de IPI no ERP")

        res = "; ".join(diag_list) if diag_list else "✅ Correto"
        acao = " + ".join(list(dict.fromkeys(acoes_list))) if acoes_list else "✅ Correto"
        return pd.Series([ncm_atual, res, format_brl(row['VLR-IPI']), format_brl(row['BC-IPI'] * aliq_esp / 100), acao])

    # Auditoria ICMS - Mantendo Aprovação 1
    def auditoria_icms(row):
        ncm_atual = str(row['NCM']).strip().zfill(8)
        info_ncm = base_icms[base_icms['NCM_KEY'] == ncm_atual]
        st_entrada = ("✅ ST Localizado" if ncm_atual in ncms_ent_st else "❌ Sem ST na Entrada") if tem_entradas else "⚠️ Entrada não enviada"
        
        if info_ncm.empty:
            return pd.Series([st_entrada, f"NCM {ncm_atual} Ausente na Base ICMS", format_brl(row['VLR-ICMS']), "R$ 0,00", "Cadastrar NCM na Base ICMS", "R$ 0,00"])

        cst_esp = str(info_ncm.iloc[0]['CST_ESP'])
        aliq_esp = float(info_ncm.iloc[0, 3]) if row['UF_EMIT'] == row['UF_DEST'] else 12.0
        cst_xml = str(row['CST-ICMS']).strip().zfill(2)
        diag_list, acoes_list = [], []

        if cst_xml == "60":
            if row['VLR-ICMS'] > 0:
                diag_list.append(f"CST 60 com destaque: {format_brl(row['VLR-ICMS'])}")
                acoes_list.append("Estorno de ICMS")
            aliq_esp = 0.0
        else:
            if aliq_esp > 0 and row['VLR-ICMS'] == 0: acoes_list.append("Emitir NF Complementar de Imposto")
            if cst_xml != cst_esp: acoes_list.append(f"Cc-e (Corrigir CST para {cst_esp})")
            if abs(row['ALQ-ICMS'] - aliq_esp) > 0.01: acoes_list.append("Ajustar Alíquota no ERP")

        res = "; ".join(diag_list) if diag_list else "✅ Correto"
        acao = " + ".join(list(dict.fromkeys(acoes_list))) if acoes_list else "✅ Correto"
        return pd.Series([st_entrada, res, format_brl(row['VLR-ICMS']), format_brl(row['BC-ICMS'] * aliq_esp / 100), acao, format_brl(0.0)])

    df_icms_audit[['ST na Entrada', 'Diagnóstico', 'ICMS XML', 'ICMS Esperado', 'Ação', 'Complemento']] = df_icms_audit.apply(auditoria_icms, axis=1)
    df_ipi_audit[['NCM', 'Diagnóstico', 'IPI XML', 'IPI Esperado', 'Ação']] = df_ipi_audit.apply(auditoria_ipi, axis=1)

    mem = io.BytesIO()
    with pd.ExcelWriter(mem, engine='xlsxwriter') as wr:
        if tem_entradas: df_ent.to_excel(wr, sheet_name='ENTRADAS', index=False)
        df_sai.to_excel(wr, sheet_name='SAIDAS', index=False)
        df_icms_audit.to_excel(wr, sheet_name='ICMS', index=False)
        df_ipi_audit[['NUM_NF', 'NCM', 'Diagnóstico', 'IPI XML', 'IPI Esperado', 'Ação']].to_excel(wr, sheet_name='IPI', index=False)
        for aba in ['PIS_COFINS', 'DIFAL']: df_sai.to_excel(wr, sheet_name=aba, index=False)
    return mem.getvalue()
