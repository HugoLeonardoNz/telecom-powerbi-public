# Medidas de Insight — camada de storytelling

> Medidas que transformam o dashboard de "painel de números" em "entrega de insights":
> títulos dinâmicos, narrativa automática e cores condicionais.
> Pré-requisito: medidas base de `measures.md` já criadas.

## Títulos dinâmicos (usar em Título do visual → fx)

```dax
Título Dinâmico =
VAR op = IF(HASONEVALUE(dim_operadora[nome_operadora]),
            SELECTEDVALUE(dim_operadora[nome_operadora]), "Todas as operadoras")
VAR per = IF(HASONEVALUE(dim_calendario[ano]),
             FORMAT(SELECTEDVALUE(dim_calendario[ano]), "0"), "2022–2023")
RETURN "Reclamações · " & op & " · " & per
```

## Narrativa automática (card de texto no topo da Visão Executiva)

```dax
Insight Automático =
VAR topOp =
    TOPN(1, ALL(dim_operadora[nome_operadora]), [Total Reclamações], DESC)
VAR nomeTop = MAXX(topOp, dim_operadora[nome_operadora])
VAR volTop  = MAXX(topOp, [Total Reclamações])
VAR share   = DIVIDE(volTop, CALCULATE([Total Reclamações], ALL(dim_operadora)))
VAR mom     = [Var MoM %]
VAR tendencia =
    SWITCH(TRUE(),
        ISBLANK(mom), "",
        mom > 0.05,  " Volume em alta (" & FORMAT(mom, "+0.0%") & " MoM) — atenção.",
        mom < -0.05, " Volume em queda (" & FORMAT(mom, "0.0%") & " MoM) — melhora.",
        " Volume estável no mês.")
RETURN
    nomeTop & " concentra " & FORMAT(share, "0.0%") &
    " das reclamações no período." & tendencia
```

## Cores condicionais (Formatação condicional → Cor de fundo/fonte → fx → por valor de campo)

```dax
Cor MoM =
SWITCH(TRUE(),
    ISBLANK([Var MoM %]), "#7F8C99",
    [Var MoM %] > 0.15,  "#C7534B",   -- crítico
    [Var MoM %] > 0.05,  "#D9B44A",   -- atenção
    [Var MoM %] < -0.05, "#2E8B57",   -- melhora
    "#7F8C99")                        -- estável

Cor Resolução =
SWITCH(TRUE(),
    ISBLANK([% Taxa Resolução]), "#7F8C99",
    [% Taxa Resolução] >= 0.80, "#2E8B57",
    [% Taxa Resolução] >= 0.70, "#D9B44A",
    "#C7534B")
```

## Deltas com seta (usar como rótulo secundário nos cards)

```dax
Seta MoM =
VAR v = [Var MoM %]
RETURN IF(ISBLANK(v), "—",
    IF(v >= 0, "▲ " & FORMAT(v, "+0.0%"), "▼ " & FORMAT(v, "0.0%")) & " vs mês ant.")
```

## Checklist de aplicação por página

| Página | Aplicar |
|---|---|
| Visão Executiva | `Título Dinâmico` no cabeçalho, card `Insight Automático`, `Seta MoM` sob o card de total, `Cor MoM` no fundo do card MoM |
| Motivos | `Cor MoM` como fonte na matriz operadora × motivo |
| Resolução | `Cor Resolução` no fundo da coluna de taxa por operadora |
| Regional | tooltip com `Seta MoM` + `% Taxa Resolução` |
| Risco | `Cor MoM` na tabela de score |

> Tema visual: importar `theme/fibernet_theme.json` (Exibição → Temas → Procurar temas).
