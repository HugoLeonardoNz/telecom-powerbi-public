# Telecom Operadoras — Power BI Dashboard

<div align="center">

![Power BI](https://img.shields.io/badge/Power%20BI-Desktop-F2C811?style=for-the-badge&logo=powerbi&logoColor=black)
![DAX](https://img.shields.io/badge/DAX-49%20Medidas-F2C811?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-Data%20Prep-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Domain](https://img.shields.io/badge/Domain-Telecom%20%2F%20Regulatório-0ea5e9?style=for-the-badge)
![Data](https://img.shields.io/badge/Dados-ANATEL%20Sintéticos-10b981?style=for-the-badge)

**Dashboard comparativo de reclamações e qualidade de serviço das principais operadoras de telecomunicações do Brasil.**  
Dados ANATEL modelados em star schema e analisados com 49 medidas DAX organizadas em 7 domínios analíticos.

</div>

---

## O Que Este Dashboard Entrega

Painel executivo de 5 páginas para análise regulatória e competitiva do setor de telecomunicações, respondendo:

| Pergunta | Página |
|----------|--------|
| Qual operadora lidera em volume de reclamações? | Visão Executiva |
| Quais tipos de falha predominam por operadora? | Análise de Motivos |
| A qualidade está melhorando ou piorando? | Qualidade de Atendimento |
| Quais estados têm pior experiência de consumidor? | Análise Regional |
| Qual operadora representa maior risco regulatório? | Índice de Risco |

---

## Destaques do Modelo (Dados de Demonstração)

> Período analisado: 2022–2023 · 8.000 reclamações sintéticas baseadas nas proporções reais ANATEL

| KPI | Valor |
|-----|-------|
| Total de Reclamações | 8.000 |
| Reclamações SCM (Internet) | 5.000 (62,5%) |
| Reclamações SMP (Celular) | 3.000 (37,5%) |
| Taxa de Resolução Global | 71,9% |
| Pendentes + Em Análise | 2.247 |
| HHI (concentração) | 2.908 — Altamente Concentrado |
| Top 3 operadoras | 87,1% das reclamações |

**Ranking de Volume:**
| # | Operadora | Reclamações | Market Share | Score Risco |
|---|-----------|-------------|-------------|------------|
| 1 | CLARO | 3.391 | 42,4% | 0,557 — Risco Elevado |
| 2 | VIVO | 2.000 | 25,0% | 0,372 — Risco Moderado |
| 3 | TIM | 1.573 | 19,7% | 0,323 — Risco Moderado |
| 4 | OI | 775 | 9,7% | 0,218 — Baixo Risco |
| 5 | SERCOMTEL | 166 | 2,1% | 0,381 — Risco Moderado |

---

## Fonte de Dados

**ANATEL — Dados Abertos: Reclamações e Denúncias de Consumidores**

- Portal: [dados.anatel.gov.br](https://dados.anatel.gov.br)
- Serviços cobertos: **SCM** (Internet Banda Larga) e **SMP** (Telefonia Móvel)
- Formato original: CSV · Encoding: ISO-8859-1 · Separador: `;`
- Pipeline de preparação: [`data_prep/prepare_data.py`](data_prep/prepare_data.py)
- Geração de dados sintéticos: [`src/generate_data.py`](src/generate_data.py)

Para uso com dados reais, baixar os CSVs do portal ANATEL e executar `data_prep/prepare_data.py`.

---

## Estrutura do Projeto

```
telecom-powerbi-public/
├── README.md
├── requirements.txt
├── data_prep/
│   └── prepare_data.py          ← Pipeline ETL: limpeza, tipagem, star schema
├── src/
│   ├── generate_data.py         ← Gerador de dados sintéticos (demo)
│   └── kpis.py                  ← Cálculo e exportação de KPIs para outputs/
├── dax/
│   └── measures.md              ← Documentação de todas as medidas DAX
├── docs/
│   └── DASHBOARD_GUIDE.md       ← Guia de uso e interpretação do dashboard
├── data/
│   ├── README.md
│   └── processed/               ← CSVs prontos para importação no Power BI
│       ├── fato_reclamacoes.csv
│       ├── dim_operadora.csv
│       ├── dim_uf.csv
│       ├── dim_tipo_reclamacao.csv
│       └── dim_calendario.csv
└── outputs/                     ← KPIs exportados em JSON/CSV (via kpis.py)
```

---

## Modelo de Dados — Star Schema

```
                     ┌──────────────────────┐
                     │   fato_reclamacoes   │
                     │──────────────────────│
                     │ id_reclamacao (PK)   │
          ┌──────────┤ id_data              ├──────────┐
          │          │ id_operadora         │          │
          │          │ id_uf                │          │
          │          │ id_tipo              │          │
          │          │ status               │          │
          │          │ sigla_servico        │          │
          │          │ qtd (sempre 1)       │          │
          │          └──────────┬───────────┘          │
          │                     │                      │
   dim_operadora          dim_calendario            dim_uf
   ──────────────         ──────────────            ──────
   id_operadora           id_data (PK)              id_uf (PK)
   nome                   data                      sigla_uf
   porte                  ano                       nome_uf
   grupo_economico        trimestre                 regiao
   assinantes_estimados   mes
                          nome_mes
                          semana_ano          dim_tipo_reclamacao
                          dia_semana          ───────────────────
                          nome_dia            id_tipo (PK)
                          fim_semana          categoria
                                              subcategoria
```

**Relacionamentos:** Many-to-One (fato → dimensões), todos ativos, single cross-filter.

### Tabela Fato: `fato_reclamacoes`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id_reclamacao` | INT | Chave surrogate da reclamação |
| `id_data` | INT | FK → `dim_calendario[id_data]` |
| `id_operadora` | INT | FK → `dim_operadora[id_operadora]` |
| `id_uf` | INT | FK → `dim_uf[id_uf]` |
| `id_tipo` | INT | FK → `dim_tipo_reclamacao[id_tipo]` |
| `status` | TEXT | `Respondida` / `Em Análise` / `Pendente` |
| `sigla_servico` | TEXT | `SCM` (internet) ou `SMP` (celular) |
| `qtd` | INT | Sempre 1 — permite SUM como contagem |

### Coluna Calculada: `dim_operadora[assinantes_estimados]`

Estimativa de base de assinantes por operadora (fonte: `src/kpis.py`):

| Operadora | Assinantes Estimados |
|-----------|---------------------|
| CLARO | 35.200.000 |
| VIVO | 33.100.000 |
| TIM | 24.800.000 |
| OI | 12.600.000 |
| SERCOMTEL | 400.000 |

---

## Medidas DAX — Dicionário Completo

O modelo contém **49 medidas DAX** organizadas na tabela `_Medidas` em 7 domínios:

### [01] Volume

| Medida | Fórmula resumida | Uso |
|--------|-----------------|-----|
| `Total Reclamações` | `SUM(fato_reclamacoes[qtd])` | KPI base — todas as páginas |
| `Total Reclamações Geral` | `CALCULATE([Total Rec.], ALL(fato_reclamacoes))` | Denominador para % do total |
| `Reclamações SCM` | `CALCULATE(..., sigla_servico = "SCM")` | Filtro por internet |
| `Reclamações SMP` | `CALCULATE(..., sigla_servico = "SMP")` | Filtro por celular |
| `Média Mensal Reclamações` | `AVERAGEX(SUMMARIZE(ano, mes), ...)` | Benchmarking temporal |

### [02] Resolução

| Medida | Uso |
|--------|-----|
| `Total Respondidas` | Volume com status Respondida |
| `Pendentes` | Volume não resolvido (Em Análise + Pendente) |
| `Qtd Em Análise` | Reclamações com status "Em Análise" |
| `Qtd Não Resolvidas` | Reclamações com status "Pendente" |
| `% Taxa Resolução` | `DIVIDE([Total Respondidas], [Total Reclamações], 0)` |
| `Taxa de Resolução Texto` | Formatado com label OK / Atenção / Crítico |
| `Gap vs Meta 60%` | `[% Taxa Resolução] - 0.60` — desvio da meta mínima |
| `Status vs Meta` | Superou / Atingiu / Abaixo / Crítico |

### [03] Temporal

| Medida | Uso |
|--------|-----|
| `Reclamações Mês Anterior` | `DATEADD(..., -1, MONTH)` |
| `Var MoM %` | Variação percentual mês a mês |
| `Reclamações Ano Anterior` | `SAMEPERIODLASTYEAR(...)` |
| `Var YoY %` | Variação percentual ano a ano |
| `Variação YoY Texto` | Formatado com sinal `+`/`-` |
| `Reclamações YTD` | `TOTALYTD(...)` — acumulado no ano |
| `Média Móvel 3M` | Suavização de série temporal |
| `Último Mês com Dados` | `FORMAT(MAXX(ALL(...), data), "MMMM/YYYY")` |

### [04] Mercado

| Medida | Uso |
|--------|-----|
| `% do Total` | Share da seleção atual no total geral |
| `Market Share Operadora %` | Share de reclamações por operadora |
| `Market Share Texto` | Formatado como "XX.X%" |
| `HHI` | Índice Herfindahl-Hirschman de concentração |
| `Classificação HHI` | Competitivo / Concentrado / Altamente Concentrado |
| `Concentração Top 3 %` | Share acumulado das 3 maiores operadoras |
| `Ranking Operadora Volume` | `RANKX(ALL(dim_operadora), ...)` |
| `Reclamações por 100k Assinantes` | Volume normalizado por base de clientes |
| `Ranking Normalizado` | Ranking pela métrica por 100k |
| `É Top N Operadoras` | Flag 0/1 para filtro dinâmico de Top N |

### [05] Risco

| Medida | Uso |
|--------|-----|
| `HHI Concentracao` | HHI × 10.000 — componente do score |
| `Score Risco Operadora` | Índice 0–1: vol(40%) + resolução_inv(35%) + r100k(25%) |
| `Rating Risco` | Baixo / Moderado / Elevado / Alto Risco |
| `Cor Risco Numérico` | 1–4 para formatação condicional |
| `Flag Piora MoM` | Crítico / Atenção / Estável / Melhora |

### [06] Categoria

| Medida | Uso |
|--------|-----|
| `Rank Categoria` | Ranking de categorias por volume |
| `Share Categoria %` | % do total por categoria de motivo |

### [07] Geográfico

| Medida | Uso |
|--------|-----|
| `Share UF %` | % do total por estado |
| `Pior Estado Operadora` | Nome do estado com maior volume para a operadora selecionada |

### [HTML] Visuais

5 medidas que retornam HTML completo para o visual **HTML Viewer**:

| Medida | Conteúdo |
|--------|----------|
| `_HTML_Dashboard` | Layout principal: KPI cards + donut de market share + ranking em barras SVG |
| `_HTML_Motivos` | Grid de categorias por volume com barras gradiente |
| `_HTML_Ranking` | Tabela de ranking de operadoras com score de risco |
| `_HTML_Regional` | Top 10 estados por volume |
| `_HTML_Titulo` | Painel de título com data de última atualização |

---

## Páginas do Dashboard

### Página 1 — Visão Executiva
KPIs em destaque (Total, Taxa Resolução, Pendentes, Var MoM), gráfico de barras por operadora, série temporal mensal, rosca de market share.

### Página 2 — Análise de Motivos
Treemap de categorias, heatmap Operadora × Motivo, barras empilhadas por trimestre.

### Página 3 — Qualidade de Atendimento
Taxa de resolução por operadora (gauge vs meta), ranking de pendentes, flag de piora MoM.

### Página 4 — Análise Regional
Shape map do Brasil por UF (intensidade = volume), tabela UF × Operadora com ranking.

### Página 5 — Índice de Risco
Score composto de risco regulatório por operadora, HHI e classificação de concentração de mercado.

---

## Como Reproduzir

```bash
# 1. Clonar o repositório e instalar dependências
pip install -r requirements.txt

# 2a. Usar dados sintéticos (demo imediato)
python src/generate_data.py
python data_prep/prepare_data.py
python src/kpis.py

# 2b. Usar dados reais ANATEL
#     Baixar CSVs em dados.anatel.gov.br > Reclamações de Consumidores
#     Salvar em data/raw/ e executar prepare_data.py

# 3. No Power BI Desktop
#    Arquivo > Obter Dados > Texto/CSV
#    Importar todos os CSVs de data/processed/
#    Criar relacionamentos conforme o modelo acima
#    dim_calendario: marcar como Tabela de Datas (coluna: data)
#    Adicionar medidas DAX conforme dax/measures.md
```

---

## Decisões Técnicas

- **`SUM(qtd)` em vez de `COUNTROWS`** — permite futuras extensões onde qtd > 1 sem quebrar medidas dependentes
- **Star schema com chaves inteiras** — performance de relacionamento otimizada vs. chaves de texto
- **dim_calendario marcada como Date Table** — habilita funções de Time Intelligence nativas (DATEADD, SAMEPERIODLASTYEAR, TOTALYTD)
- **`assinantes_estimados` como coluna calculada** — substitui base real ANATEL para demonstração; trocar por dado real para produção
- **HTML Viewer para visuais customizados** — CSS Grid + glassmorphism para layout 1920×1080 sem dependência de visual marketplace pago
- **Score de risco normalizado 0–1** — comparação justa entre operadoras de portes distintos (SERCOMTEL vs CLARO)

---

## Stack

`Python 3.x` · `Pandas` · `NumPy` · `Power BI Desktop` · `DAX` · `Power Query (M)` · `HTML/CSS` (HTML Viewer)

---

## Autor

**Hugo Leonardo**  
Analista de Dados Pleno — SQL · Python · Power BI  
Speed Fibra · Santa Luzia, MG

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Hugo%20Leonardo-0077B5?style=flat&logo=linkedin)](https://www.linkedin.com/in/hugo-leonardo-data-analyst/)
[![GitHub](https://img.shields.io/badge/GitHub-HugoLeonardoNz-181717?style=flat&logo=github)](https://github.com/HugoLeonardoNz)
