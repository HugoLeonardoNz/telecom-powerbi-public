# DAX Measures — Telecom Operadoras Dashboard

## Configuração de Tabelas

Antes de adicionar as medidas, configure os relacionamentos no Power BI:

```
fato_reclamacoes[id_data]        → dim_calendario[id_data]      (Many-to-One)
fato_reclamacoes[id_operadora]   → dim_operadora[id_operadora]  (Many-to-One)
fato_reclamacoes[id_uf]          → dim_uf[id_uf]                (Many-to-One)
fato_reclamacoes[id_tipo]        → dim_tipo_reclamacao[id_tipo]  (Many-to-One)
```

---

## Medidas Base

```dax
-- Total de reclamações no contexto atual
Total Reclamações =
COUNTROWS(fato_reclamacoes)

-- Total sem filtros (para % do total)
Total Reclamações Geral =
CALCULATE(COUNTROWS(fato_reclamacoes), ALL(fato_reclamacoes))

-- % do total (participação da seleção atual)
% do Total =
DIVIDE([Total Reclamações], [Total Reclamações Geral], 0)
```

---

## Medidas de Resolução

Os três recortes de status são distintos e os nomes dizem qual é qual — `Em Aberto` é o
guarda-chuva (tudo que não foi respondido), `Qtd Pendentes` é só o status `Pendente`.

```dax
-- Reclamações com status "Respondida"
Total Respondidas =
CALCULATE(SUM(fato_reclamacoes[qtd]), fato_reclamacoes[Status] = "Respondida")

-- Taxa de resolução
% Taxa Resolução =
DIVIDE([Total Respondidas], [Total Reclamações], 0)

-- Sem resposta final: inclui Pendente E Em Análise
Em Aberto =
CALCULATE(SUM(fato_reclamacoes[qtd]), fato_reclamacoes[Status] <> "Respondida")

-- Apenas o status "Pendente"
Qtd Pendentes =
CALCULATE(SUM(fato_reclamacoes[qtd]), fato_reclamacoes[Status] = "Pendente")

-- Apenas o status "Em Análise"
Qtd Em Análise =
CALCULATE(SUM(fato_reclamacoes[qtd]), fato_reclamacoes[Status] = "Em Análise")
```

> Taxa de resolução mede se houve resposta ao protocolo, **não** satisfação do consumidor.
> A base não tem desfecho nem tempo de resolução.

---

## Medidas Temporais

```dax
-- Reclamações no mês anterior (para variação MoM)
Reclamações Mês Anterior =
CALCULATE(
    [Total Reclamações],
    DATEADD(dim_calendario[data], -1, MONTH)
)

-- Variação mês a mês (%)
Var MoM % =
VAR atual    = [Total Reclamações]
VAR anterior = [Reclamações Mês Anterior]
RETURN
    IF(
        NOT ISBLANK(anterior) && anterior <> 0,
        DIVIDE(atual - anterior, anterior),
        BLANK()
    )

-- Reclamações no mesmo período do ano anterior
Reclamações Ano Anterior =
CALCULATE(
    [Total Reclamações],
    SAMEPERIODLASTYEAR(dim_calendario[data])
)

-- Variação ano a ano (%)
Var YoY % =
VAR atual    = [Total Reclamações]
VAR anterior = [Reclamações Ano Anterior]
RETURN
    IF(
        NOT ISBLANK(anterior) && anterior <> 0,
        DIVIDE(atual - anterior, anterior),
        BLANK()
    )

-- Acumulado no ano (YTD)
Reclamações YTD =
TOTALYTD([Total Reclamações], dim_calendario[data])

-- Média móvel 3 meses
Média Móvel 3M =
AVERAGEX(
    DATESINPERIOD(dim_calendario[data], LASTDATE(dim_calendario[data]), -3, MONTH),
    [Total Reclamações]
)
```

---

## Medidas de Ranking

```dax
-- Ranking de operadoras por volume (1 = mais reclamações)
Ranking Operadora Volume =
RANKX(
    ALL(dim_operadora[Operadora]),
    [Total Reclamações],
    ,
    DESC,
    DENSE
)

-- A medida que torna a comparação honesta: sem ela, "quem tem mais reclamação"
-- é só "quem tem mais cliente". Devolve BLANK quando não há base conhecida,
-- em vez de fabricar um número.
Reclamações por 100k Assinantes =
VAR assinantes = SELECTEDVALUE(dim_operadora[assinantes_estimados])
RETURN DIVIDE([Total Reclamações], assinantes / 100000, BLANK())

Ranking Normalizado =
RANKX(
    ALL(dim_operadora[Operadora]),
    [Reclamações por 100k Assinantes],
    ,
    DESC,
    DENSE
)
```

---

## Medidas de Alerta

```dax
-- Flag de piora: operadoras com crescimento acima da média do setor
Flag Piora MoM =
VAR media_setor = AVERAGEX(ALL(dim_operadora), [Var MoM %])
RETURN
    SWITCH(
        TRUE(),
        [Var MoM %] > media_setor * 1.5, "🔴 Crítico",
        [Var MoM %] > media_setor,       "🟡 Atenção",
        [Var MoM %] <= 0,                "🟢 Melhora",
        "⚪ Estável"
    )

-- Concentração de reclamações (Herfindahl simplificado)
Índice Concentração =
SUMX(
    ALL(dim_operadora),
    POWER([% do Total], 2)
)

-- Estado com maior volume no contexto atual
Pior Estado Operadora =
CALCULATE(
    SELECTEDVALUE(dim_uf[Estado], "Múltiplos"),
    TOPN(1, ALL(dim_uf), [Total Reclamações], DESC)
)

-- Desvio padronizado do mês contra a média do período selecionado.
-- O IF de entrada é obrigatório: sem um único mês no contexto, "atual" seria
-- um acumulado comparado contra médias mensais e o resultado seria absurdo.
-- A comparação também precisa de REMOVEFILTERS + reaplicação de ano/mês —
-- sem isso a série de referência colapsa para um único ponto e a medida
-- devolve BLANK sempre que o visual quebra por mês.
Z-Score Volume Mensal =
IF(
    NOT (HASONEVALUE(dim_calendario[Ano]) && HASONEVALUE(dim_calendario[mes])),
    BLANK(),
    VAR _serie =
        ADDCOLUMNS(
            SUMMARIZE(ALLSELECTED(dim_calendario), dim_calendario[Ano], dim_calendario[mes]),
            "@v",
            VAR _a = dim_calendario[Ano]
            VAR _m = dim_calendario[mes]
            RETURN
                CALCULATE(
                    [Total Reclamações],
                    REMOVEFILTERS(dim_calendario),
                    dim_calendario[Ano] = _a,
                    dim_calendario[mes] = _m
                )
        )
    VAR _media = AVERAGEX(_serie, [@v])
    VAR _dp    = STDEVX.P(_serie, [@v])
    VAR _atual = [Total Reclamações]
    RETURN
        IF(_dp = 0 || ISBLANK(_atual), BLANK(), DIVIDE(_atual - _media, _dp))
)
```

---

## Medidas Auxiliares (Formatação)

```dax
-- Texto de variação com seta
Texto Var MoM =
VAR v = [Var MoM %]
RETURN
    IF(
        ISBLANK(v),
        "—",
        IF(v >= 0,
            "▲ " & FORMAT(ABS(v), "0.0%"),
            "▼ " & FORMAT(ABS(v), "0.0%")
        )
    )

-- Cor dinâmica para variação (usar em formatação condicional)
Cor Var MoM =
IF([Var MoM %] > 0, "#EF4444", "#10B981")  -- vermelho se piora, verde se melhora

-- Sumarização para tooltip
Sumarizacao Operadora =
"Operadora: " & SELECTEDVALUE(dim_operadora[Operadora]) &
" | Reclamações: " & FORMAT([Total Reclamações], "#,##0") &
" | Resolução: " & FORMAT([% Taxa Resolução], "0.0%")

-- Paleta fixa por marca. Serve para "cor por valor do campo" em cartão;
-- em gráfico de barras a cor é declarada por seletor de categoria
-- (ver tools/build_report.py), porque ali o Power BI avalia a medida fora
-- do contexto do ponto e pintaria tudo da mesma cor.
Cor Operadora =
SWITCH(
    SELECTEDVALUE(dim_operadora[Operadora]),
    "CLARO",            "#5AD8F0",
    "VIVO",             "#8B93F5",
    "TIM",              "#E0A33A",
    "OI",               "#3FBF87",
    "SERCOMTEL",        "#E0685F",
    "NÃO IDENTIFICADA", "#4A5568",
    "#5AD8F0"
)
```

---

## Qualidade do Dado

Registros cuja prestadora não foi identificada na base bruta **não são descartados** —
sumir com eles deixaria o total divergente da origem. Ficam no volume consolidado, com
base de assinantes em branco, e a cobertura vira KPI explícito.

```dax
Reclamações Não Identificadas =
CALCULATE(
    [Total Reclamações],
    KEEPFILTERS(dim_operadora[Operadora] = "NÃO IDENTIFICADA")
)

% Não Identificado =
DIVIDE([Reclamações Não Identificadas], [Total Reclamações Geral])

Cobertura de Identificação = 1 - [% Não Identificado]
```

---

## Narrativa

Texto que lê os próprios números e reage aos filtros. Usar em cartão ou no título
dinâmico do visual (**Título → fx → por campo**).

```dax
Título Dinâmico =
VAR _op  = IF(HASONEVALUE(dim_operadora[Operadora]), SELECTEDVALUE(dim_operadora[Operadora]), "Todas as operadoras")
VAR _uf  = IF(HASONEVALUE(dim_uf[Estado]), " · " & SELECTEDVALUE(dim_uf[Estado]), "")
VAR _ano = IF(HASONEVALUE(dim_calendario[Ano]), FORMAT(SELECTEDVALUE(dim_calendario[Ano]), "0"), "2022–2023")
RETURN "Reclamações ANATEL · " & _op & _uf & " · " & _ano
```

`Insight Executivo` segue a mesma ideia com mais fôlego: identifica a líder, o share dela,
a direção do mês, a taxa de resolução, a classificação de concentração e o estado mais
crítico, e devolve tudo como frase. É o texto da faixa **Leitura do Período**, na primeira
página. A fórmula completa está no modelo, pasta `[08] Narrativa`.

---

## Sobre este documento

As 53 medidas já estão no `.pbix` — este arquivo é o dicionário das que carregam decisão
analítica, não um roteiro de montagem. **O modelo é a fonte da verdade**; se divergirem,
o modelo está certo.

Todas vivem na tabela `_Medidas` (uma tabela calculada vazia, `ROW("dummy", 1)`),
organizadas em pastas numeradas por domínio para que o painel de campos seja navegável:

```
[01] Volume          [02] Resolução      [03] Temporal
[04] Ranking         [05] Mercado        [06] Risco & Alertas
[07] Categoria & Geografia               [08] Narrativa
[09] Auxiliares      [11] Qualidade do Dado
```

### Convenções

- Toda divisão usa `DIVIDE`, nunca `/` — evita erro de divisão por zero.
- Medida que não faz sentido no contexto devolve `BLANK()`, nunca zero: um zero mente,
  um vazio admite que não sabe.
- Percentual guarda a fração (0–1) e o formato cuida da exibição; nada de `* 100` na
  fórmula.
- Formato definido na medida, não no visual — o número sai igual em qualquer lugar.
