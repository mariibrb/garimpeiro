# Garimpeiro local — convenções de nomes (entrada e saída)

Documento de referência para o escritório: o que colocar nas pastas, como nomear ficheiros e o que esperar na saída da versão **local** (CLI / PowerShell), alinhado ao comportamento da app Streamlit atual.

---

## 1. Pastas e papéis

| Pasta | Função |
|--------|--------|
| **Pasta de entrada (lote)** | Raiz onde o utilizador aponta o cliente: XML, ZIP, SPED, planilhas opcionais. O motor **vasculha em profundidade** (subpastas e ZIP dentro de ZIP), como na app. |
| **Pasta de saída** | Onde gravar relatórios Excel, pacote contabilidade (pastas abertas + ZIPs), ficheiros SPED auxiliares e exports opcionais (canceladas, inutilizadas, autenticidade). |

Recomenda-se **uma subpasta por trabalho** dentro da saída (ex.: `ClienteX_2025-04`) para não misturar lotes.

---

## 2. Entrada — ficheiros que o lote pode conter

### 2.1 Documentos fiscais (XML / ZIP)

| Tipo | Padrão | Notas |
|------|--------|--------|
| XML de NF-e / eventos / etc. | `*.xml` em qualquer subpasta | Incluídos na leitura recursiva. |
| Arquivos compactados | `*.zip` em qualquer subpasta | Tratamento em **matriosca** (ZIP dentro de ZIP), alinhado a `extrair_recursivo` na app. |
| Ficheiros a ignorar (típico) | `__MACOSX/**`, `Thumbs.db`, `.DS_Store` | Apenas ruído de sistema; lista pode ser fixa no CLI. |

Não é obrigatório que XML/ZIP estejam na **raiz** — podem estar espalhados.

### 2.2 SPED (EFD) — modo “com SPED”

| Padrão canónico | Exemplo | Descrição |
|-----------------|---------|-----------|
| `SPED_<codigo_empresa_escritorio>.txt` | `SPED_578.txt` | **Codigo** = identificador interno do cliente/empresa no escritório. Facilita automação e vários trabalhos em paralelo. |

**Regras sugeridas para o CLI:**

- Aceitar **caminho absoluto** para o SPED **ou**
- Procurar na pasta de entrada um ficheiro cujo nome corresponda a `SPED_<codigo>.txt` (extensão típica do EFD; se no escritório usarem sempre `.txt`, manter isso fixo no contrato).

Se existirem **vários** `SPED_*` na mesma pasta, o utilizador deve passar **qual código** usar (parâmetro obrigatório) ou caminho explícito — evita ambiguidade.

### 2.3 Planilhas opcionais (quando a versão local suportar)

| Uso | Nome canónico sugerido | Conteúdo |
|-----|-------------------------|----------|
| Relatório Sefaz para **autenticidade** | `autenticidade.xlsx` **ou** `autenticidade1.xlsx`, `autenticidade2.xlsx`, … | Mesma lógica da app: **vários** Excel/CSV são agregados. Partir por volume (`autenticidade2`, …) evita ficheiros gigantes e mantém nomes estáveis. |
| Notas **canceladas** declaradas sem XML (manual) | `canceladas.xlsx` (ou `.csv`) | Alinhado à ideia de nome “real” e legível. |
| Notas **inutilizadas** declaradas sem XML (manual) | `inutilizadas.xlsx` (ou `.csv`) | Idem. |

Modelos de referência na app (nomes distintos, só para modelo):  
`MODELO_canceladas_sem_XML_garimpeiro.xlsx`, `MODELO_inutilizadas_sem_XML_garimpeiro.xlsx`.

---

## 3. Modos de análise (regra de negócio)

| Modo | SPED | Relatório / pacote contabilidade | Comparação SPED × lote |
|------|------|----------------------------------|-------------------------|
| **A — Pasta completa (sem filtro SPED)** | Não usado (ou ignorado) | Reflete **tudo** o que foi lido no lote. | Não aplica cruzamento C100/D100 × XML. |
| **B — Alinhado ao SPED** | Obrigatório (`SPED_<codigo>.txt`) | Pastas/ZIPs e fatias de relatório **coerentes com as chaves presentes no SPED** (quando extraíveis). | Gera também o auxiliar de **chaves no SPED sem XML no lote** (ver saída). |

Comportamento de filtro alinhado ao docstring de `_garimpo_df_e_filtro_espelho_so_sped_se_anexado` em `app.py`: com SPED válido, o espelho de export tende a **espelhar só** documentos cuja chave de 44 dígitos está no SPED; sem SPED mantém o conjunto completo lido.

---

## 4. Saída — artefactos principais (alinhados à app)

### 4.1 Relatório Excel completo (várias abas)

Na app, o pacote contabilidade usa como base de nome em raiz (entre outros):

| Ficheiro | Referência no código |
|----------|----------------------|
| `relatorio_garimpeiro_completo.xlsx` | Constante `_PACOTE_CONTAB_NOME_EXCEL_RAIZ` |

Dentro de cada ZIP de grupo, os Excels seguem o padrão `relatorio_garimpeiro_<grupo ou sufixo>.xlsx` (nome único por grupo para não sobrescrever ao extrair vários ZIPs para a mesma pasta).

**Versão local:** replicar estes padrões para o mesmo tipo de entrega.

### 4.2 Pacote contabilidade (pastas + ZIPs)

- Pastas abertas com XML organizados por grupo (critério atual do Garimpeiro).
- Ficheiros `.zip` correspondentes (incl. partes `pt1`, `pt2`, … quando o lote é grande).
- Estrutura espelhada na subpasta **`Garimpeiro_Local_Com_SPED`** ou **`Garimpeiro_Local_Sem_SPED`** (CLI: com SPED se `--modo sped`; app: conforme anexo SPED no 1.º passo), **dentro da pasta de saída** do trabalho.

### 4.3 SPED — o que foi lido / o que faltou

| Ficheiro | Quando |
|----------|--------|
| `SPED_chaves_sem_XML_no_lote.xlsx` | Modo **B**, quando há chaves C100/D100 no SPED **sem** XML correspondente no lote (comportamento já descrito em `app.py`). |

Isto cobre “falar o que foi lido e o que não foi lido” no eixo SPED × XML.

### 4.4 Descargas “por tipo” na app (defaults úteis para espelhar no disco)

Quando existir export único ou por lado, a app usa nomes como:

| Contexto | Nome default típico |
|----------|---------------------|
| Relatório completo (download) | `relatorio_completo.xlsx` |
| Emissão própria | `relatorio_emissao_propria.xlsx` |
| Terceiros | `relatorio_terceiros.xlsx` |

A versão local pode gravar o equivalente na pasta de saída **se** gerar esses cortes (nomes podem ser parametrizados, mas estes são os valores de referência).

### 4.5 Canceladas, inutilizadas, autenticidade (exports dedicados)

| Conteúdo | Nome canónico sugerido na saída |
|----------|----------------------------------|
| Lista de **canceladas** (vista dedicada) | `canceladas.xlsx` |
| Lista de **inutilizadas** | `inutilizadas.xlsx` |
| **Divergências de autenticidade** (Sefaz × lote) | `autenticidade.xlsx` **ou**, se partido por volume, `autenticidade_parte01.xlsx`, `autenticidade_parte02.xlsx` (equivalente a `autenticidade1`, `autenticidade2`). |

Regra: **prefixo fixo** + **sufixo sequencial** quando houver limite de linhas ou tamanho de ficheiro; manter sempre a mesma raiz (`autenticidade`) para ordenação e cópia de segurança.

---

## 5. Resumo executivo

1. **Entrada:** uma pasta raiz; **tudo** é varrido (subpastas + ZIP em matriosca).  
2. **SPED:** convencionar `SPED_<codigo_escritorio>.txt` e passar o código ou o caminho explícito.  
3. **Saída:** mesmos tipos de artefactos que a app (relatório completo com abas, pacote contabilidade em pastas e ZIPs, Excel SPED faltantes quando aplicável).  
4. **Canceladas / inutilizadas / autenticidade:** nomes legíveis nos Excel de saída; autenticidade pode partir em `autenticidade1`, `autenticidade2` ou `autenticidade_parteNN`.

Este ficheiro pode ser atualizado quando o CLI fixar parâmetros exatos (`--entrada`, `--saida`, `--sped`, `--modo`).

---

## 7. CLI implementado (`garimpeiro_cli.py`)

Variável de ambiente interna: `GARIMPEIRO_HEADLESS=1` (definida pelo script) para importar `app.py` **sem** executar a interface Streamlit.

| Parâmetro | Obrigatório | Descrição |
|-----------|-------------|-----------|
| `--entrada` | sim | Pasta raiz do lote (varredura recursiva de `.xml` e `.zip`). |
| `--saida` | sim | Pasta onde gravar `relatorio_garimpeiro_completo.xlsx`, `canceladas.xlsx` / `inutilizadas.xlsx` se houver dados, o Excel de SPED faltantes (modo SPED), e a árvore `Garimpeiro_Local_Com_SPED` ou `Garimpeiro_Local_Sem_SPED` + ZIPs na pasta de saída. |
| `--cnpj` | sim | CNPJ do emitente (14 dígitos). |
| `--modo` | não | `pasta` (omissão) ou `sped`. |
| `--codigo` | com `--modo sped` | Sufixo do ficheiro `SPED_<codigo>.txt` (ex.: `578`). |
| `--stem` | não | Nome base dos ZIPs do pacote contabilidade (omissão: `pacote_apuracao`). |

**Exemplos (PowerShell):**

```text
py -3 garimpeiro_cli.py --entrada "D:\Lote" --saida "D:\Export" --cnpj 12345678000199 --modo pasta
py -3 garimpeiro_cli.py --entrada "D:\Lote" --saida "D:\Export" --cnpj 12345678000199 --modo sped --codigo 578
```

Atalho: `.\Run-Garimpeiro-Local.ps1 -Entrada "..." -Saida "..." -Cnpj "..." [-Modo sped] [-Codigo 578]`.

**Planilhas opcionais na pasta de entrada:** `inutilizadas.xlsx` / `.csv` e `canceladas.xlsx` / `.csv` (primeiro ficheiro encontrado por nome, recursivo) — mesma lógica de buracos que na app.

**Requisito:** `GARIMPEIRO_ANALISE_SEM_DISCO_LOCAL` fica `0` por omissão no CLI (lote em disco sob `temp_garimpo_uploads`), adequado a lotes grandes.
