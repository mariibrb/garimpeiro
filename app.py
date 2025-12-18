import pandas as pd
import os

# Define o caminho da pasta oculta
pasta_destino = ".streamlit"

# Garante que a pasta existe
if not os.path.exists(pasta_destino):
    os.makedirs(pasta_destino)

# Cria os dados de exemplo (Gabarito)
dados = {
    'NCM': [
        '00000000', # Exemplo genérico
        '12345678', # Exemplo 2
        '87654321'  # Exemplo 3
    ],
    'CST': [
        '00', # Tributado Integralmente
        '60', # Cobrado anteriormente por ST
        '40'  # Isento
    ],
    'ALIQ': [
        18.0, # Alíquota padrão SP (exemplo)
        0.0,  # Sem alíquota na operação
        0.0   # Isento
    ]
}

# Cria o DataFrame
df = pd.DataFrame(dados)

# Caminho completo do arquivo
caminho_arquivo = os.path.join(pasta_destino, "base_icms.xlsx")

# Salva em Excel
df.to_excel(caminho_arquivo, index=False)

print(f"✅ Sucesso! O arquivo '{caminho_arquivo}' foi criado.")
print("Agora o Sentinela vai parar de reclamar que falta a base de ICMS.")
