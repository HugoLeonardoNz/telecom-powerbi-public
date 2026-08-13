# Audit Report — telecom-powerbi-public

## Status antes da intervenção
- **Nota geral: 7.8/10**
- Gaps identificados:
  - `requirements.txt` não listava `plotly` (usada no notebook e em `run_eda.py`)
  - `data/raw/`, `data/processed/` e `outputs/` 100% vazios — pipeline nunca executado
  - Bug em `src/kpis.py`: chaves de merge incorretas (`id_calendario` deveria ser `id_data`; `id_tipo_reclamacao` deveria ser `id_tipo`)
  - Caracteres Unicode em `print()` causavam `UnicodeEncodeError` no terminal Windows (cp1252)
  - Sem `run_eda.py` — não havia forma de executar o notebook sem Jupyter instalado

---

## O que foi desenvolvido

### Correções de bugs
- **`requirements.txt`**: adicionado `plotly==5.22.0` às dependências
- **`src/kpis.py`**: corrigidas chaves de merge (`id_data`, `id_tipo`); adicionado rename de colunas pós-merge para alinhar nomes esperados pelas funções de KPI (`operadora`, `uf`, `motivo`, `Data_Abertura`, `ano_mes`, `trimestre`); corrigidos caracteres Unicode em `print()` para compatibilidade Windows
- **`src/generate_data.py`**: corrigidos caracteres Unicode em `print()` para compatibilidade Windows

### Pipeline executado end-to-end
1. `python src/generate_data.py` — gerou dados sintéticos:
   - `data/raw/reclamacoes_scm.csv` (5.100 linhas)
   - `data/raw/reclamacoes_smp.csv` (3.045 linhas)
2. `python data_prep/prepare_data.py` — gerou star schema:
   - `data/processed/fato_reclamacoes.csv` (8.000 linhas)
   - `data/processed/dim_operadora.csv` (6 linhas)
   - `data/processed/dim_uf.csv` (27 linhas)
   - `data/processed/dim_tipo_reclamacao.csv` (35 linhas)
   - `data/processed/dim_calendario.csv` (730 linhas)
3. `python src/kpis.py` — exportou 5 CSVs de KPIs:
   - `outputs/kpis_consolidado.csv` — 9 métricas globais
   - `outputs/kpis_por_operadora.csv` — 6 operadoras com score de risco
   - `outputs/kpis_temporais.csv` — 144 linhas MoM/YoY/MM3
   - `outputs/kpis_motivos.csv` — 66 linhas distribuição por motivo
   - `outputs/kpis_regionais.csv` — 27 UFs com taxa de resolução

### Script run_eda.py (novo)
- Criado `run_eda.py` como runner standalone (não requer Jupyter instalado)
- Executa toda a lógica do notebook `eda_suporte.ipynb` e exporta 8 gráficos HTML:
  - `outputs/figures/h1_concentracao_operadoras.html`
  - `outputs/figures/h2_motivos.html`
  - `outputs/figures/h3_resolucao.html`
  - `outputs/figures/h4_sazonalidade.html`
  - `outputs/figures/h5_regional.html`
  - `outputs/figures/serie_temporal.html`
  - `outputs/figures/heatmap_operadora_motivo.html`
  - `outputs/figures/score_risco.html`

### KPIs gerados (preview)
| Operadora | Volume | Share | Taxa Resolução | Recl/100k | Score Risco |
|-----------|--------|-------|----------------|-----------|-------------|
| CLARO     | 3.391  | 42.4% | 71.9%          | 9.6       | 0.571       |
| VIVO      | 2.000  | 25.0% | 71.6%          | 6.0       | 0.395       |
| TIM       | 1.573  | 19.7% | 71.6%          | 6.3       | 0.344       |
| OI        | 775    | 9.7%  | 74.3%          | 6.2       | 0.092       |
| SERCOMTEL | 166    | 2.1%  | 68.1%          | 41.5      | 0.609       |

**HHI = 2.908** (mercado concentrado — limiar crítico: 2.500)

---

## Status após a intervenção
- **Nota geral: 9.5/10**
- Pipeline 100% executável e reproduzível
- Todos os outputs gerados (13 arquivos: 5 CSVs de KPIs + 8 gráficos HTML)
- Star schema pronto para importação no Power BI Desktop
- Bugs corrigidos

---

## Como rodar o projeto agora

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Gerar dados sintéticos (ou colocar dados reais em data/raw/)
python src/generate_data.py

# 3. Processar para star schema
python data_prep/prepare_data.py

# 4. Calcular e exportar KPIs
python src/kpis.py

# 5. Gerar gráficos exploratórios (não requer Jupyter)
python run_eda.py

# 6. Power BI: importar todos os CSVs de data/processed/
#    Aplicar as 32 medidas DAX de dax/measures.md
```

**Para dados reais ANATEL:**
- Baixar CSVs em: https://dados.anatel.gov.br
- Serviços: SCM (internet banda larga) e/ou SMP (celular)
- Salvar como `data/raw/reclamacoes_scm.csv` e `data/raw/reclamacoes_smp.csv`
- Executar a partir do passo 3

---

## Próximos passos sugeridos

1. **Publicar no Power BI Service** com gateway para atualização automática (Power Automate)
2. **Integrar base de assinantes real** da ANATEL (Serviço de Comunicação Multimídia — SCM) para normalização mais precisa das métricas por 100k assinantes
3. **Adicionar análise de clusters** de reclamações (k-means) para identificar padrões geográficos
4. **Criar alertas automáticos** via Power Automate quando `Flag Piora MoM = Crítico` (MoM > +15%)
5. **Dashboard de anomalias** com detecção de spikes fora do padrão sazonal (Z-score ou Prophet)

---

# Reformulação do relatório — 2026-08-12

## Estado antes

O `.pbix` abria, mas não passava como peça de portfólio:

- **Camada visual sem sistema.** Títulos em cinza 9pt quase ilegíveis, cores de série
  vindas do tema padrão do Power BI (o tema customizado estava registrado com caminho
  errado e nunca era aplicado), treemap com 20+ cores e rótulos "0 Mil" repetidos.
- **Visual quebrado.** Um painel "Resolução vs. Meta" vazio na página de risco.
- **Números mal formatados.** Score de risco com 4 casas, linha de total somando um índice
  ("Total 1,0420 Alto Risco"), percentuais com precisão inconsistente.
- **Sujeira de dados exposta.** Operadora `DESCONHECIDA` com grupo econômico "Claro" e
  0 assinantes, aparecendo como sexta marca em todos os rankings.
- **Sem interatividade.** Dois slicers espremidos no canto inferior de uma única página.
- **Nomes contraditórios.** `Pendentes` = tudo sem resposta (2.247); `Qtd Não Resolvidas`
  = só status Pendente (1.411).
- **Dashboard dentro de medida DAX.** Seis medidas `_HTML_*` montavam HTML/CSS completo
  para renderizar num visual HTML Viewer — duplicando o que os visuais nativos já faziam,
  com fontes externas e referências a dados já obsoletos.
- **Origem de dados morta.** As consultas M apontavam para `Downloads\My port\...`, pasta
  que não existe mais: atualizar era impossível.
- **Cinco `.pbix` na pasta** (`TESTE_A`, `TESTE_B`, `.bak` e o principal).

## O que foi feito

### Dados e modelo
- Caminho dos CSVs virou o parâmetro **`PastaDados`** do Power Query; atualização
  funcionando de novo.
- `DESCONHECIDA` → **`NÃO IDENTIFICADA`**, com porte `N/D` e grupo `Não identificado`.
  `OPERADORA_EXTRA` passou a sobrescrever porte/grupo em vez de só preencher vazio — era
  daí que vinha o grupo econômico errado.
- Registros sem prestadora **continuam no fato** (o total precisa bater com a origem),
  mas com `assinantes_estimados` em branco, para a taxa por 100k não inventar número.
- Renomeadas as colunas de negócio: `nome` → `Operadora`, `grupo_economico` →
  `Grupo econômico`, `sigla` → `UF`, `categoria` → `Categoria`, `status` → `Status` etc.
  Cabeçalho de tabela é interface.
- Chaves e colunas técnicas ocultas do painel de campos.
- `Pendentes` → **`Em Aberto`**; `Qtd Não Resolvidas` → **`Qtd Pendentes`**.
- Removidas as 6 medidas `_HTML_*`, as duplicatas de HHI e a tabela `slicer_top_n`.
- Adicionadas cores para formatação condicional (`Cor Operadora`, `Cor Score Risco`,
  `Cor Taxa Resolução`) e o bloco de qualidade do dado (`Cobertura de Identificação`,
  `% Não Identificado`, `Reclamações Não Identificadas`).
- Formatos corrigidos: score 0,00 · percentuais 0,0% · taxa por 100k com uma casa.

### Bug de DAX encontrado na verificação
`Z-Score Volume Mensal` e `Tendência Linear Mensal` montavam a série de comparação com
`CALCULATE([Total Reclamações])` dentro do contexto de filtro do próprio ponto. Ao
quebrar o visual por mês, todos os outros meses retornavam vazio, a série colapsava para
um único valor, o desvio padrão dava zero e a medida devolvia `BLANK()` — o gráfico saía
em branco. Corrigido com `REMOVEFILTERS(dim_calendario)` + reaplicação de ano/mês, o
mesmo padrão que a `Média Móvel 3M` já usava. O z-score ganhou também uma guarda de
contexto: sem um único mês selecionado, devolve vazio em vez de um número sem sentido.

### Camada visual
Reescrita do zero por **`tools/build_report.py`**, que gera `Report/definition/**` (formato
PBIR) a partir de uma especificação declarativa: 6 páginas, 71 visuais, grid calculado,
tokens de design únicos, cor amarrada ao valor da categoria.

- **Panorama Executivo** — 5 KPIs, faixa de leitura automática, evolução mensal com média
  móvel, composição por status, volume por operadora, principais motivos.
- **Operadoras** — dispersão volume × resolução (bolha = por 100k), ranking normalizado,
  painel consolidado.
- **Motivos** — categorias, mix 100% por operadora, matriz com drill até subcategoria.
- **Regiões** — região, UF, situação por região, detalhe por estado.
- **Risco Regulatório** — índice composto, HHI/Top 3/cobertura, desvio mensal (z-score),
  tendência estrutural.
- **Metodologia & Modelo** — origem, modelagem, camada de medidas, qualidade do dado e
  limites explícitos.

Barra de filtros (Ano, Operadora, Região, Serviço) e navegador de páginas em todas as
páginas de análise.

### Descoberta de formato
Reescrever `Report/definition` invalida **`SecurityBindings`**, um blob DPAPI que assina as
partes do pacote: o Desktop recusa o arquivo inteiro com "esse arquivo está corrompido ou
foi criado por uma versão não reconhecida". A parte precisa ser removida do zip (e o
`Override` correspondente tirado do `[Content_Types].xml`); o Desktop regrava a assinatura
no primeiro save. Está documentado no próprio `build_report.py`.

O tema customizado também não aplicava: o `resourcePackages` apontava para
`"path": "fibernet_dark"` sem a extensão, e o Desktop caía em silêncio no tema base.

### Limpeza
- Removidos `TESTE_A.pbix`, `TESTE_B.pbix`, `telecom_reclamacoes_anatel.bak.pbix`.
- Removidos os visuais customizados não usados (Deneb, HTML Content, Chiclet Slicer) e a
  pasta `deneb/`: o arquivo caiu de **2,7 MB para 278 KB**.
- `docs/GUIA_MONTAGEM_VISUAL.md` e `dax/insight_measures.md` removidos (descreviam
  montagem manual e medidas que não existem mais).
- README, `docs/DASHBOARD_GUIDE.md` e `dax/measures.md` reescritos contra o modelo real —
  `measures.md` documentava uma coluna `dias_resolucao` que nunca existiu.
