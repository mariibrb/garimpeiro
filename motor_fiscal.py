import pandas as pd
import numpy as np
import io
import xml.etree.ElementTree as ET
from datetime import datetime

def extrair_dados_xml(xml_files, tipo, df_autenticidade=None):
    """
    Extração que preserva sua lógica original de tags.
    O segredo para não vir vazio é o uso correto do namespace e do findtext.
    """
    registros = []
    
    if not xml_files:
        return pd.DataFrame()

    for xml_file in xml_files:
        try:
            # Garante a leitura do buffer do Streamlit
            conteudo = xml_file.read()
            if not conteudo:
                continue
            root = ET.fromstring(conteudo)
            
            # Namespace flexível para NF-e
            ns = ""
            if '}' in root.tag:
                ns = root.tag.split('}')[0] + '}'

            # Busca a Chave de Acesso
            infNFe = root.find(f".//{ns}infNFe")
            chave = infNFe.attrib['Id'][3:] if infNFe is not None else "N/A"
            
            # Detalhamento dos itens conforme sua estrutura de origem
            for det in root.findall(f".//{ns}det"):
                prod = det.find(f"{ns}prod")
                imposto = det.find(f"{ns}imposto")
                
                if prod is None or imposto is None:
                    continue

                item = {
                    'CHAVE': chave,
                    'TIPO': tipo,
                    'produto': prod.findtext(f"{ns}xProd") or "",
                    'ncm': prod.findtext(f"{ns}NCM") or "",
                    'valor_item': float(prod.findtext(f"{ns}vProd") or 0.0),
                    'base_calculo': 0.0,
                    'aliquota_pis': 0.0,
                    'valor_pis_xml': 0.0,
                    'aliquota_cofins': 0.0,
                    'valor_cofins_xml': 0.0,
                    'aliquota_ipi': 0.0,
                    'valor_ipi_xml': 0.0,
                    'valor_icms': 0.0
                }

                # Extração de ICMS
                icms = imposto.find(f".//{ns}ICMS")
                if icms is not None:
                    v_icms = icms.find(f".//{ns}vICMS")
                    if v_icms is not None:
                        item['valor_icms'] = float(v_icms.text or 0.0)

                # Extração de PIS
                pis = imposto.find(f".//{ns}PIS")
                if pis is not None:
                    item['base_calculo'] = float(pis.findtext(f".//{ns}vBC") or 0.0)
                    item['aliquota_pis'] = float(pis.findtext(f".//{ns}pPIS") or 0.0)
                    item['valor_pis_xml'] = float(pis.findtext(f".//{ns}vPIS") or 0.0)

                # Extração de COFINS
                cofins = imposto.find(f".//{ns}COFINS")
                if cofins is not None:
                    item['aliquota_cofins'] = float(cofins.findtext(f".//{ns}pCOFINS") or 0.0)
                    item['valor_cofins_xml'] = float(cofins.findtext(f".//{ns}vCOFINS") or 0.0)

                # Extração de IPI
                ipi = imposto.find(f".//{ns}IPI")
                if ipi is not None:
                    item['aliquota_ipi'] = float(ipi.findtext(f".//{ns}pIPI") or 0.0)
                    item['valor_ipi_xml'] = float(ipi.findtext(f".//{ns}vIPI") or 0.0)

                registros.append(item)
            
            # Resetar o ponteiro do arquivo para evitar que venha vazio na próxima leitura
            xml_file.seek(0)
            
        except Exception:
            continue

    df = pd.DataFrame(registros)
    
    # Cruzamento com Autenticidade (Proteção contra KeyError)
    if df_autenticidade is not None and not df.empty:
        df_autenticidade.columns = [c.upper() for c in df_autenticidade.columns]
        if 'CHAVE' in df_autenticidade.columns:
            df = df.merge(df_autenticidade, on='CHAVE', how='left')
            
    return df

def gerar_excel_final(df_e, df_s):
    """
    Gera o Excel mantendo suas abas e acrescentando apenas a coluna de ANALISE.
    """
    output = io.BytesIO()
    
    # Consolidação apenas para as abas de auditoria
    df_consolidado = pd.concat([df_e, df_s], ignore_index=True)

    # --- ABA PISCOFINS ---
    df_piscofins = df_consolidado.copy()
    if not df_piscofins.empty:
        v_destacado = df_piscofins['valor_pis_xml'] + df_piscofins['valor_cofins_xml']
        v_esperado = df_piscofins['base_calculo'] * ((df_piscofins['aliquota_pis'] + df_piscofins['aliquota_cofins']) / 100)
        df_piscofins['ANALISE'] = np.where(abs(v_destacado - v_esperado) < 0.01, "CORRETO", "ESPERADO DESTACADO")

    # --- ABA IPI ---
    df_ipi = df_consolidado.copy()
    if not df_ipi.empty:
        v_ipi_esp = df_ipi['base_calculo'] * (df_ipi['aliquota_ipi'] / 100)
        df_ipi['ANALISE'] = np.where(abs(df_ipi['valor_ipi_xml'] - v_ipi_esp) < 0.01, "CORRETO", "ESPERADO DESTACADO")

    # Escrita final mantendo a estrutura original
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        if not df_e.empty: df_e.to_excel(writer, sheet_name='Entradas', index=False)
        if not df_s.empty: df_s.to_excel(writer, sheet_name='Saídas', index=False)
        df_piscofins.to_excel(writer, sheet_name='PISCOFINS', index=False)
        df_ipi.to_excel(writer, sheet_name='IPI', index=False)
        
    return output.getvalue()
