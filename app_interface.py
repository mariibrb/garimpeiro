import pandas as pd
import numpy as np
from datetime import datetime

class AnalisadorFiscalConsolidado:
    def __init__(self, caminho_planilha=None):
        """
        Inicializa o motor de análise. Aceita um caminho de arquivo ou 
        pode ser alimentado por DataFrames (para testes/CI-CD).
        """
        self.data_processamento = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        if caminho_planilha:
            # Carregamento real das abas da planilha
            self.df_icms = pd.read_excel(caminho_planilha, sheet_name='ICMS')
            self.df_pis = pd.read_excel(caminho_planilha, sheet_name='PIS')
            self.df_cofins = pd.read_excel(caminho_planilha, sheet_name='COFINS')
            self.df_ipi = pd.read_excel(caminho_planilha, sheet_name='IPI')
            self.df_final = self.df_icms.copy()
        else:
            # Inicialização vazia para instanciamento manual (Mock)
            self.df_icms = pd.DataFrame()
            self.df_pis = pd.DataFrame()
            self.df_cofins = pd.DataFrame()
            self.df_ipi = pd.DataFrame()
            self.df_final = pd.DataFrame()

    def analisar_aba_pis(self):
        """Analisa a consistência do PIS: Calculado vs Declarado"""
        self.df_pis['valor_pis_calculado'] = self.df_pis['base_calculo'] * (self.df_pis['aliquota_pis'] / 100)
        self.df_pis['status_pis'] = np.where(
            abs(self.df_pis['valor_pis_calculado'] - self.df_pis['valor_pis_declarado']) < 0.01, 
            'OK', 'Divergente'
        )
        return self

    def analisar_aba_cofins(self):
        """Analisa a consistência do COFINS: Calculado vs Declarado"""
        self.df_cofins['valor_cofins_calculado'] = self.df_cofins['base_calculo'] * (self.df_cofins['aliquota_cofins'] / 100)
        self.df_cofins['status_cofins'] = np.where(
            abs(self.df_cofins['valor_cofins_calculado'] - self.df_cofins['valor_cofins_declarado']) < 0.01, 
            'OK', 'Divergente'
        )
        return self

    def analisar_aba_ipi(self):
        """Analisa a incidência de IPI na aba específica"""
        self.df_ipi['valor_ipi_calculado'] = self.df_ipi['base_calculo'] * (self.df_ipi['aliquota_ipi'] / 100)
        # Regra de negócio: IPI acima de 20% exige flag de revisão manual
        self.df_ipi['status_ipi'] = np.where(
            self.df_ipi['aliquota_ipi'] > 20, 'Alíquota Alta - Revisar', 'OK'
        )
        return self

    def integrar_e_consolidar(self):
        """
        Realiza o merge de todas as abas analisadas na base principal (ICMS).
        """
        # Integração PIS
        self.df_final = self.df_final.merge(
            self.df_pis[['id_item', 'valor_pis_calculado', 'status_pis']], on='id_item', how='left'
        )
        # Integração COFINS
        self.df_final = self.df_final.merge(
            self.df_cofins[['id_item', 'valor_cofins_calculado', 'status_cofins']], on='id_item', how='left'
        )
        # Integração IPI
        self.df_final = self.df_final.merge(
            self.df_ipi[['id_item', 'valor_ipi_calculado', 'status_ipi']], on='id_item', how='left'
        )

        # Cálculo da Carga Tributária Total Consolidada
        self.df_final['total_tributos_federais'] = (
            self.df_final['valor_pis_calculado'].fillna(0) + 
            self.df_final['valor_cofins_calculado'].fillna(0) + 
            self.df_final['valor_ipi_calculado'].fillna(0)
        )
        
        self.df_final['carga_total_geral'] = (
            self.df_final['total_tributos_federais'] + self.df_final['valor_icms']
        )
        
        return self

    def aplicar_aprovacao_nivel_1(self):
        """
        Aprovação 1: Validação de integridade entre todas as abas.
        Status 'Aprovado 1' somente se PIS, COFINS e IPI estiverem 'OK'.
        """
        condicoes = [
            (self.df_final['status_pis'] == 'OK') & 
            (self.df_final['status_cofins'] == 'OK') & 
            (self.df_final['status_ipi'] == 'OK'),
            (self.df_final['valor_item'] <= 0)
        ]
        escolhas = ['Aprovado 1', 'Erro: Valor Negativo']
        
        self.df_final['status_aprovacao'] = np.select(condicoes, escolhas, default='Revisão Fiscal Necessária')
        self.df_final['data_analise'] = self.data_processamento
        
        return self

    def gerar_output_github(self):
