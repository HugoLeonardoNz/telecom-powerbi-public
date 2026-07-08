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

```dax
-- Reclamações com status "Respondida"
Total Respondidas =
CALCULATE(
    COUNTROWS(fato_reclamacoes),
    fato_reclamacoes[status] = "Respondida"
)

-- Taxa de resolução
% Taxa Resolução =
DIVIDE([Total Respondidas], [Total Reclamações], 0)

-- Reclamações pendentes (não respondidas)
Pendentes =
CALCULATE(
    COUNTROWS(fato_reclamacoes),
    fato_reclamacoes[status] <> "Respondida"
)

-- SLA médio de resolução (dias)
Dias Médios Resolução =
AVERAGEX(
    FILTER(fato_reclamacoes, NOT ISBLANK(fato_reclamacoes[dias_resolucao])),
    fato_reclamacoes[dias_resolucao]
)
```

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
    ALL(dim_operadora[nome]),
    [Total Reclamações],
    ,
    DESC,
    DENSE
)

-- Ranking normalizado por assinantes estimados
-- (requer coluna dim_operadora[assinantes_estimados] preenchida manualmente)
Reclamações por 100k Assinantes =
DIVIDE(
    [Total Reclamações],
    RELATED(dim_operadora[assinantes_estimados]) / 100000,
    BLANK()
)

Ranking Normalizado =
RANKX(
    ALL(dim_operadora[nome]),
    [Reclamações por 100k Assinantes],
    ,
    DESC,
    DENSE
)

-- Top N operadoras (usar em visual de tabela com filtro dinâmico)
É Top N Operadoras =
VAR n = SELECTEDVALUE(slicer_top_n[valor], 5)
RETURN IF([Ranking Operadora Volume] <= n, 1, 0)
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

-- Operadora pior estado (para card de destaque)
Pior Estado Operadora =
CALCULATE(
    SELECTEDVALUE(dim_uf[nome], "Múltiplos"),
    TOPN(1, ALL(dim_uf), [Total Reclamações], DESC)
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
Sumarização Operadora =
"Operadora: " & SELECTEDVALUE(dim_operadora[nome]) &
" | Reclamações: " & FORMAT([Total Reclamações], "#,##0") &
" | Resolução: " & FORMAT([% Taxa Resolução], "0.0%")
```

---

## Como Usar no Power BI

1. Abrir Power BI Desktop → aba **Modelagem** → **Nova Medida**
2. Colar o código DAX acima
3. Organizar medidas em uma tabela dedicada: **Medidas** (tabela calculada vazia)
4. Para medidas com `RELATED()`: garantir que os relacionamentos estão ativos no modelo

### Tabela de Medidas (prática recomendada)

Criar uma tabela vazia chamada `_Medidas`:
```dax
_Medidas = ROW("dummy", 1)
```
Mover todas as medidas para essa tabela para organização.
