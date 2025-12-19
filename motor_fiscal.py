import pandas as pd
import numpy as np
import io

def extrair_dados_xml(xml_files, tipo, df_autenticidade=None):
    """
    Sua lógica original de extração permanece aqui.
    Retorna o DataFrame base processado dos XMLs.
    """
    # ... (Mantenha sua lógica de extração de tags XML aqui)
    return pd.DataFrame() 

def gerar_excel_final(df_e, df_s):
    """
    Gera o Excel final mantendo sua estrutura, acrescentando a coluna de análise 
    apenas nas abas IPI e PISCOFINS.
    """
    output = io.BytesIO()
    
    # Criando as cópias para as abas específicas
    # Aba PISCOFINS
    df_piscofins = pd.concat([df_e, df_s], ignore_index=True).copy()
    if not df_piscofins.empty:
        # Cálculo esperado para análise
        valor_esperado = df_piscofins['base_calculo'] * ((df_piscofins['aliquota_pis'] + df_piscofins['aliquota_cofins']) / 100)
        valor_xml = df_piscofins['valor_pis_xml'] + df_piscofins['valor_cofins_xml']
        
        df_piscofins['ANALISE_PIS_COFINS'] = np.where(
            abs(valor_esperado - valor_xml) < 0.01, "CORRETO", "DIVERGENTE"
        )

    # Aba IPI
    df_ipi = pd.concat([df_e, df_s], ignore_index=True).copy()
    if not df_ipi.empty:
        ipi_esperado = df_ipi['base_calculo'] * (df_ipi['aliquota_ipi'] / 100)
        df_ipi['ANALISE_IPI'] = np.where(
            abs(ipi_esperado - df_ipi['valor_ipi_xml']) < 0.01, "CORRETO", "DIVERGENTE"
        )

    # Gravando no Excel mantendo as abas originais do seu projeto
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_e.to_excel(writer, sheet_name='Entradas', index=False)
        df_s.to_excel(writer, sheet_name='Saídas', index=False)
        df_piscofins.to_excel(writer, sheet_name='PISCOFINS', index=False)
        df_ipi.to_excel(writer, sheet_name='IPI', index=False)
        
    return output.getvalue()
