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
        if not self.df_pis.empty:
            self.df_pis['valor_pis_calculado'] = self.df_pis['base_calculo'] * (self.df_pis['aliquota_pis'] / 100)
            self.df_pis['status_pis'] = np.where(
                abs(self.df_pis['valor_pis_calculado'] - self.df_pis['valor_pis_declarado']) < 0.01, 
                'OK', 'Divergente'
            )
        return self

    def analisar_aba_cofins(self):
        """Analisa a consistência do COFINS: Calculado vs Declarado"""
        if not self.df_cofins.empty:
            self.df_cofins['valor_cofins_calculado'] = self.df_cofins['base_calculo'] * (self.df_cofins['aliquota_cofins'] / 100)
            self.df_cofins['status_cofins'] = np.where(
                abs(self.df_cofins['valor_cofins_calculado'] - self.df_cofins['valor_cofins_declarado']) < 0.01, 
                'OK', 'Divergente'
            )
        return self

    def analisar_aba_ipi(self):
        """Analisa a incidência de IPI na aba específica"""
        if not self.df_ipi.empty:
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
        if not self.df_pis.empty:
            self.df_final = self.df_final.merge(
                self.df_pis[['id_item', 'valor_pis_calculado', 'status_pis']], on='id_item', how='left'
            )
        
        # Integração COFINS
        if not self.df_cofins.empty:
            self.df_final = self.df_final.merge(
                self.df_cofins[['id_item', 'valor_cofins_calculado', 'status_cofins']], on='id_item', how='left'
            )
            
        # Integração IPI
        if not self.df_ipi.empty:
            self.df_final = self.df_final.merge(
                self.df_ipi[['id_item', 'valor_ipi_calculado', 'status_ipi']], on='id_item', how='left'
            )

        # Cálculo da Carga Tributária Total Consolidada
        self.df_final['total_tributos_federais'] = (
            self.df_final.get('valor_pis_calculado', 0).fillna(0) + 
            self.df_final.get('valor_cofins_calculado', 0).fillna(0) + 
            self.df_final.get('valor_ipi_calculado', 0).fillna(0)
        )
        
        self.df_final['carga_total_geral'] = (
            self.df_final['total_tributos_federais'] + self.df_final.get('valor_icms', 0)
        )
        
        return self

    def aplicar_aprovacao_nivel_1(self):
        """
        Aprovação 1: Validação de integridade entre todas as abas.
        Status 'Aprovado 1' somente se PIS, COFINS e IPI estiverem 'OK'.
        """
        if self.df_final.empty:
            return self

        condicoes = [
            (self.df_final.get('status_pis') == 'OK') & 
            (self.df_final.get('status_cofins') == 'OK') & 
            (self.df_final.get('status_ipi') == 'OK'),
            (self.df_final['valor_item'] <= 0)
        ]
        escolhas = ['Aprovado 1', 'Erro: Valor Negativo']
        
        self.df_final['status_aprovacao'] = np.select(condicoes, escolhas, default='Revisão Fiscal Necessária')
        self.df_final['data_analise'] = self.data_processamento
        
        return self

    def gerar_output_github(self):
        """Exibe o resultado formatado para documentação de repositório"""
        if self.df_final.empty:
            print("Nenhum dado processado para gerar output.")
            return self

        print(f"\n# Auditoria Fiscal Consolidada - {self.data_processamento}")
        
        cols = [
            'produto', 'valor_item', 'valor_icms', 'valor_pis_calculado', 
            'valor_cofins_calculado', 'valor_ipi_calculado', 'carga_total_geral', 'status_aprovacao'
        ]
        
        # Filtra apenas as colunas que realmente existem no DataFrame
        cols_existentes = [c for c in cols if c in self.df_final.columns]
        
        print("\n### 1. Tabela de Integração (ICMS + PIS + COFINS + IPI)")
        print(self.df_final[cols_existentes].to_markdown(index=False, floatfmt=".2f"))
        
        # Resumo Estatístico
        total_geral = self.df_final['carga_total_geral'].sum()
        print(f"\n### 2. Resumo de Impacto")
        print(f"- **Total Impostos Analisados:** R$ {total_geral:,.2f}")
        
        if 'status_aprovacao' in self.df_final.columns:
            resumo_status = self.df_final['status_aprovacao'].value_counts().to_dict()
            print(f"- **Status Geral:** {resumo_status}")
        
        return self.df_final

# --- EXECUÇÃO COMPLETA DO PIPELINE ---

if __name__ == "__main__":
    try:
        # Mock de dados simulando as 4 abas da planilha mestre
        data_icms = {
            'id_item': [1, 2, 3],
            'produto': ['Servidor Proliant', 'Licença Cloud', 'Switch 24p'],
            'valor_item': [25000.0, 5000.0, 12000.0],
            'valor_icms': [4500.0, 900.0, 2160.0]
        }
        
        data_pis = {
            'id_item': [1, 2, 3],
            'base_calculo': [25000.0, 5000.0, 12000.0],
            'aliquota_pis': [1.65, 1.65, 1.65],
            'valor_pis_declarado': [412.50, 82.50, 198.00]
        }
        
        data_cofins = {
            'id_item': [1, 2, 3],
            'base_calculo': [25000.0, 5000.0, 12000.0],
            'aliquota_cofins': [7.6, 7.6, 7.6],
            'valor_cofins_declarado': [1900.00, 380.00, 912.00]
        }
        
        data_ipi = {
            'id_item': [1, 2, 3],
            'base_calculo': [25000.0, 5000.0, 12000.0],
            'aliquota_ipi': [15.0, 0.0, 10.0]
        }

        # Inicialização com os dados das abas
        analisador = AnalisadorFiscalConsolidado()
        analisador.df_icms = pd.DataFrame(data_icms)
        analisador.df_pis = pd.DataFrame(data_pis)
        analisador.df_cofins = pd.DataFrame(data_cofins)
        analisador.df_ipi = pd.DataFrame(data_ipi)
        analisador.df_final = analisador.df_icms.copy()

        # Fluxo de processamento unificado
        (analisador.analisar_aba_pis()
                   .analisar_aba_cofins()
                   .analisar_aba_ipi()
                   .integrar_e_consolidar()
                   .aplicar_aprovacao_nivel_1()
                   .gerar_output_github())

    except Exception as e:
        print(f"ERRO CRÍTICO NO PROCESSAMENTO: {str(e)}")
