import pandas as pd
import xml.etree.ElementTree as ET
import re
import io
import streamlit as st

def extrair_dados_xml(files, fluxo, df_autenticidade=None):
    dados_lista = []
    if not files: return pd.DataFrame()

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

            inf_nfe = root.find('.//infNFe')
            chave_acesso = inf_nfe.attrib.get('Id', '')[3:] if inf_nfe is not None else ""
            num_nf = buscar('nNF')
            data_emi = buscar('dhEmi')
            total_nf = root.find('.//total/ICMSTot')
            vlr_nf = total_nf.find('vNF').text if total_nf is not None and total_nf.find('vNF') is not None else "0.0"
            
            bloco_parceiro = 'emit' if fluxo == "Entrada" else 'dest'
            parceiro = root.find(f'.//{bloco_parceiro}')
            cnpj = buscar('CNPJ', parceiro) if parceiro is not None else ""
            uf = buscar('UF', parceiro) if parceiro is not None else ""

            for det in root.findall('.//det'):
                prod = det.find('prod')
                imp = det.find('imposto')
                n_item = det.attrib.get('nItem', '0')
                
                linha = {
                    "CHAVE_ACESSO": chave_acesso, "NUM_NF": num_nf,
                    "DATA_EMISSAO": pd.to_datetime(data_emi).replace(tzinfo=None) if data_emi else None,
                    "CNPJ": cnpj, "UF": uf, "VLR_NF": float(vlr_nf) if vlr_nf else 0.0, 
                    "AC": int(n_item), "CFOP": buscar('CFOP', prod), "COD_PROD": buscar('cProd', prod),
                    "DESCR": buscar('xProd', prod), "NCM": buscar('NCM', prod), "UNID": buscar('uCom', prod),
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
                    "FCP": 0.0, "ICMS UF Dest": 0.0, "STATUS": "Não Encontrado"
                }

                if imp is not None:
                    icms_data = imp.find('.//ICMS')
                    if icms_data is not None:
                        for nodo in icms_data:
                            cst = nodo.find('CST') if nodo.find('CST') is not None else nodo.find('CSOSN')
                            if cst is not None: linha["CST-ICMS"] = cst.text
                            if nodo.find('vBC') is not None: linha["BC-ICMS"] = float(nodo.find('vBC').text)
                            if nodo.find('vICMS') is not None: linha["VLR-ICMS"] = float(nodo.find('vICMS').text)
                            if nodo.find('vBCST') is not None: linha["BC-ICMS-ST"] = float(nodo.find('vBCST').text)
                            if nodo.find('vICMSST') is not None: linha["ICMS-ST"] = float(nodo.find('vICMSST').text)

                linha["VC"] = linha["VPROD"] + linha["ICMS-ST"] + linha["VLR_IPI"] + linha["DESP"] - linha["DESC"]
                dados_lista.append(linha)
            
            container_status.text(f"📊 Processando {i+1} de {total_arquivos}...")
            progresso.progress((i + 1) / total_arquivos)
        except: continue
    
    df_res = pd.DataFrame(dados_lista)
    
    if not df_res.empty and df_autenticidade is not None:
        df_res['CHAVE_ACESSO'] = df_res['CHAVE_ACESSO'].astype(str).str.strip()
        mapeamento = dict(zip(df_autenticidade.iloc[:, 0].astype(str).str.strip(), df_autenticidade.iloc[:, 5]))
        df_res['STATUS'] = df_res['CHAVE_ACESSO'].map(mapeamento).fillna("Chave não encontrada")

    if not df_res.empty:
        df_res.drop_duplicates(subset=['CHAVE_ACESSO', 'AC'], keep='first', inplace=True)

    container_status.empty()
    progresso.empty()
    return df_res

def gerar_excel_final(df_ent, df_sai):
    ncms_com_st = []
    if not df_ent.empty:
        ncms_com_st = df_ent[df_ent['ICMS-ST'] > 0]['NCM'].unique().tolist()

    df_icms_audit = df_sai.copy() if not df_sai.empty else pd.DataFrame()

    if not df_icms_audit.empty:
        # Formatação de Moeda
        def format_brl(val): return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        def auditoria_detalhada(row):
            diagnostico = "✅ Nota emitida corretamente"
            correcao = "Nenhuma ação necessária"
            v_cobrado = row['VLR-ICMS']
            
            # 1. Alíquota Esperada (Estimativa baseada no preenchido)
            aliq_esp = (row['VLR-ICMS'] / row['BC-ICMS'] * 100) if row['BC-ICMS'] > 0 else 0.0
            
            # 2. Análise de Bitributação (NCM que já pagou ST na entrada)
            if row['NCM'] in ncms_com_st and row['VLR-ICMS'] > 0:
                diagnostico = f"❌ ERRO: Este produto (NCM {row['NCM']}) já teve o imposto pago na compra (Substituição Tributária)."
                correcao = "Para corrigir: Você deve zerar o ICMS desta saída e usar o código CST 060, pois o imposto já foi pago anteriormente."
                aliq_esp = 0.0

            # 3. Análise de Isenção
            elif row['CST-ICMS'] in ['40', '41', '50'] and row['VLR-ICMS'] > 0:
                diagnostico = "❌ ERRO: A nota está marcada como Isenta ou Não Tributada, mas existe valor de imposto cobrado."
                correcao = "Para corrigir: Se a operação é isenta, o valor do ICMS deve ser R$ 0,00. Verifique o cadastro do produto."
                aliq_esp = 0.0

            # 4. Análise de Itens Acessórios (Frete/Seguro)
            base_esperada = row['VPROD'] + row['FRETE'] + row['SEG'] + row['DESP'] - row['DESC']
            if row['BC-ICMS'] > 0 and abs(row['BC-ICMS'] - base_esperada) > 0.50:
                diagnostico = "⚠️ ATENÇÃO: A base de cálculo do imposto não inclui o Frete ou outras despesas da nota."
                correcao = "Para corrigir: O ICMS deve incidir sobre o (Produto + Frete + Seguro + Despesas - Desconto). Revise o cálculo do seu sistema."

            dif = v_cobrado - (row['BC-ICMS'] * (aliq_esp/100))
            
            return pd.Series([
                f"{aliq_esp:.2f}%", 
                format_brl(v_cobrado), 
                format_brl(row['BC-ICMS'] * (aliq_esp/100)),
                diagnostico, 
                correcao
            ])

        df_icms_audit[['Alíquota Esperada', 'Valor Cobrado (XML)', 'Valor que Deveria Ser', 'O que está errado?', 'Como corrigir?']] = df_icms_audit.apply(auditoria_detalhada, axis=1)

    mem = io.BytesIO()
    with pd.ExcelWriter(mem, engine='xlsxwriter') as wr:
        if not df_ent.empty: df_ent.to_excel(wr, sheet_name='ENTRADAS', index=False)
        if not df_sai.empty:
            df_sai.to_excel(wr, sheet_name='SAIDAS', index=False)
            df_icms_audit.to_excel(wr, sheet_name='ICMS', index=False) 
            df_sai.to_excel(wr, sheet_name='IPI', index=False)
            df_sai.to_excel(wr, sheet_name='PIS_COFINS', index=False)
            df_sai.to_excel(wr, sheet_name='DIFAL', index=False)
    return mem.getvalue()
