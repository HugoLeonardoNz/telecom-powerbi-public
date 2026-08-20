# Medidas DAX — Reclamações ANATEL

53 medidas na tabela `_Medidas`, agrupadas em pastas numeradas por domínio. **O modelo é
a fonte da verdade**; este documento é o espelho dele. Se os dois divergirem, o modelo
está certo e o documento está velho.

```
[01] Volume     [02] Resolução   [03] Temporal    [04] Ranking
[05] Mercado    [06] Risco       [07] Categoria & Geografia
[08] Narrativa  [09] Auxiliares  [11] Qualidade do Dado
```

### Convenções

- Toda divisão usa `DIVIDE`, nunca `/` — evita erro de divisão por zero.
- Percentual guarda a fração (0–1); o formato cuida da exibição. Nada de `* 100` na fórmula.
- Medida sem sentido no contexto devolve `BLANK()`, nunca zero: um zero mente, um vazio
  admite que não sabe. É por isso que `Reclamações por 100k Assinantes` não existe para
  "NÃO IDENTIFICADA" — não há base de assinantes para dividir.
- Formato definido na medida, não no visual — o número sai igual em qualquer lugar.

### Modelo

Star schema, um fato e quatro dimensões. Relações um-para-muitos, filtro simples, da
dimensão para o fato; nenhuma bidirecional.

```
fato_reclamacoes[id_data]      → dim_calendario[id_data]
fato_reclamacoes[id_operadora] → dim_operadora[id_operadora]
fato_reclamacoes[id_uf]        → dim_uf[id_uf]
fato_reclamacoes[id_tipo]      → dim_tipo_reclamacao[id_tipo]
```

`dim_calendario` é contínua e está marcada como tabela de datas. A **data/hora automática
do Power BI está desligada**: com uma dimensão de calendário própria, o recurso só
acrescenta uma tabela de datas oculta por coluna de data — duas hierarquias concorrentes
para a mesma pergunta, e modelo maior sem nada em troca.

Duas colunas calculadas que o relatório usa e que não vêm do CSV:

```dax
-- Chave de ordenação do eixo mensal. Sem ela, "abr/22" vem antes de "jan/22".
ano_mes_num = dim_calendario[Ano] * 100 + dim_calendario[mes]

Mês = FORMAT(dim_calendario[data], "MMM/yy")   -- ordenada por ano_mes_num

-- Base de assinantes (ANATEL, dez/2023) para normalizar volume. BLANK para prestadora
-- não identificada, para a taxa por 100k não produzir número falso.
assinantes_estimados =
SWITCH(dim_operadora[Operadora],
    "CLARO", 35200000, "VIVO", 33100000, "TIM", 24800000,
    "OI", 12600000, "SERCOMTEL", 400000, BLANK())
```

---

## [01] Volume

```dax
-- O fato tem uma linha por reclamação e uma coluna qtd = 1. Somar qtd (em vez de contar
-- linhas) mantém o fato aditivo: se um dia o grão mudar para "reclamações por dia",
-- nenhuma medida precisa ser reescrita.
Total Reclamações = SUM(fato_reclamacoes[qtd])

Total Reclamações Geral = CALCULATE(COUNTROWS(fato_reclamacoes), ALL(fato_reclamacoes))

% do Total = DIVIDE([Total Reclamações], [Total Reclamações Geral], 0)

Reclamações SCM = CALCULATE(SUM(fato_reclamacoes[qtd]), fato_reclamacoes[Serviço] = "SCM")
Reclamações SMP = CALCULATE(SUM(fato_reclamacoes[qtd]), fato_reclamacoes[Serviço] = "SMP")

-- Média por MÊS, não por dia: itera a granularidade ano+mês.
Média Mensal Reclamações =
VAR _months = SUMMARIZE(dim_calendario, dim_calendario[Ano], dim_calendario[mes])
RETURN AVERAGEX(_months, [Total Reclamações])
```

---

## [02] Resolução

Os recortes de status são distintos e o nome diz qual é qual: `Em Aberto` é o
guarda-chuva (tudo que não foi respondido), `Qtd Pendentes` é só o status `Pendente`.

```dax
Total Respondidas = CALCULATE(SUM(fato_reclamacoes[qtd]), fato_reclamacoes[Status] = "Respondida")

% Taxa Resolução = DIVIDE([Total Respondidas], [Total Reclamações], 0)

Em Aberto      = CALCULATE(SUM(fato_reclamacoes[qtd]), fato_reclamacoes[Status] <> "Respondida")
Qtd Pendentes  = CALCULATE(SUM(fato_reclamacoes[qtd]), fato_reclamacoes[Status] = "Pendente")
Qtd Em Análise = CALCULATE(SUM(fato_reclamacoes[qtd]), fato_reclamacoes[Status] = "Em Análise")

Gap vs Meta 60% = [% Taxa Resolução] - 0.60

Taxa de Resolução Texto =
VAR _taxa = [% Taxa Resolução]
RETURN IF(ISBLANK(_taxa), "--",
    FORMAT(_taxa, "0.0%") & IF(_taxa >= 0.8, " OK", IF(_taxa >= 0.6, " Atenção", " Crítico")))

Status vs Meta =
VAR _gap = [Gap vs Meta 60%]
RETURN SWITCH(TRUE(),
    ISBLANK(_gap), "--", _gap >= 0.10, "Superou", _gap >= 0, "Atingiu",
    _gap >= -0.10, "Abaixo", "Critico")
```

---

## [03] Temporal

```dax
Reclamações Mês Anterior = CALCULATE([Total Reclamações], DATEADD(dim_calendario[data], -1, MONTH))
Reclamações Ano Anterior = CALCULATE([Total Reclamações], SAMEPERIODLASTYEAR(dim_calendario[data]))
Reclamações YTD          = TOTALYTD([Total Reclamações], dim_calendario[data])

-- BLANK quando não há base de comparação: sem mês anterior, "variação" é invenção.
Var MoM % =
VAR atual = [Total Reclamações]
VAR anterior = [Reclamações Mês Anterior]
RETURN IF(NOT ISBLANK(anterior) && anterior <> 0, DIVIDE(atual - anterior, anterior), BLANK())

Var YoY % =   -- mesma estrutura, contra o ano anterior

-- Média móvel sobre o total MENSAL. A versão original iterava DIAS (AVERAGEX sobre
-- DATESINPERIOD de datas) e devolvia média diária (~11) onde o gráfico pedia média
-- mensal (~350): a linha ficava colada no eixo e ninguém questionava o número.
Média Móvel 3M =
VAR _fim = MAX(dim_calendario[data])
VAR _meses =
    CALCULATETABLE(
        SUMMARIZE(dim_calendario, dim_calendario[Ano], dim_calendario[mes]),
        REMOVEFILTERS(dim_calendario),
        DATESINPERIOD(dim_calendario[data], _fim, -3, MONTH))
RETURN
    AVERAGEX(_meses,
        VAR _a = dim_calendario[Ano]
        VAR _m = dim_calendario[mes]
        RETURN CALCULATE([Total Reclamações], REMOVEFILTERS(dim_calendario),
                         dim_calendario[Ano] = _a, dim_calendario[mes] = _m))

-- Inclinação da reta de mínimos quadrados sobre a série mensal: reclamações ganhas ou
-- perdidas por mês. Positivo = piorando. Não é previsão — é a direção do período.
Tendência Linear Mensal =
VAR _serie =
    ADDCOLUMNS(
        SUMMARIZE(ALLSELECTED(dim_calendario), dim_calendario[Ano], dim_calendario[mes]),
        "@x", dim_calendario[Ano] * 12 + dim_calendario[mes],
        "@y", VAR _a = dim_calendario[Ano] VAR _m = dim_calendario[mes]
              RETURN CALCULATE([Total Reclamações], REMOVEFILTERS(dim_calendario),
                               dim_calendario[Ano] = _a, dim_calendario[mes] = _m))
VAR _n = COUNTROWS(_serie)
VAR _sx = SUMX(_serie, [@x])   VAR _sy  = SUMX(_serie, [@y])
VAR _sxy = SUMX(_serie, [@x] * [@y])   VAR _sxx = SUMX(_serie, [@x] * [@x])
RETURN DIVIDE(_n * _sxy - _sx * _sy, _n * _sxx - _sx * _sx)

Último Mês com Dados = FORMAT(MAXX(ALL(dim_calendario), dim_calendario[data]), "MMMM/YYYY")
Variação YoY Texto   = -- formatação de [Var YoY %] com sinal explícito
```

---

## [04] Ranking

```dax
Ranking Operadora Volume = RANKX(ALL(dim_operadora[Operadora]), [Total Reclamações], , DESC, DENSE)

-- Correção do viés de porte: comparar CLARO (35,2 mi de assinantes) com SERCOMTEL
-- (400 mil) por volume bruto não diz nada sobre qualidade de serviço.
Reclamações por 100k Assinantes =
VAR assinantes = SELECTEDVALUE(dim_operadora[assinantes_estimados])
RETURN DIVIDE([Total Reclamações], assinantes / 100000, BLANK())

Ranking Normalizado = RANKX(ALL(dim_operadora[Operadora]), [Reclamações por 100k Assinantes], , DESC, DENSE)
```

---

## [05] Mercado

```dax
Market Share Operadora % =
DIVIDE([Total Reclamações], CALCULATE([Total Reclamações], ALL(dim_operadora)), 0)

-- Herfindahl-Hirschman: soma dos quadrados dos market shares, em base 10.000.
HHI =
ROUND(
    SUMX(ALL(dim_operadora[Operadora]),
        POWER(DIVIDE(CALCULATE([Total Reclamações]),
                     CALCULATE([Total Reclamações], ALL(dim_operadora))), 2)) * 10000, 0)

Concentração Top 3 % =
VAR _tot  = CALCULATE([Total Reclamações], ALL(dim_operadora))
VAR _top3 = TOPN(3, ALL(dim_operadora[Operadora]), CALCULATE([Total Reclamações]), DESC)
RETURN DIVIDE(SUMX(_top3, CALCULATE([Total Reclamações])), _tot, 0)

-- Faixas do critério antitruste clássico.
Classificação HHI =
VAR _hhi = [HHI]
RETURN SWITCH(TRUE(), _hhi < 1500, "Competitivo", _hhi <= 2500, "Concentrado",
              "Altamente Concentrado")

Market Share Texto = -- formatação de [Market Share Operadora %]
```

> **Leitura honesta do HHI aqui:** o índice mede concentração *das reclamações*, não do
> mercado. Um HHI de 2.908 diz que as queixas se concentram em poucas marcas — o que
> acompanha, mas não é, a concentração de assinantes.

---

## [06] Risco & Alertas

```dax
-- Composição ponderada, não previsão. Os pesos são escolha declarada, não resultado de
-- ajuste: quem discordar deles muda o número e o ranking muda junto.
Score Risco Operadora =
VAR vol_norm   = DIVIDE([Total Reclamações], MAXX(ALL(dim_operadora), [Total Reclamações]), 0)
VAR res_inv    = 1 - [% Taxa Resolução]
VAR r100k_norm = DIVIDE([Reclamações por 100k Assinantes],
                        MAXX(ALL(dim_operadora), [Reclamações por 100k Assinantes]), 0)
RETURN ROUND(vol_norm * 0.40 + res_inv * 0.35 + r100k_norm * 0.25, 4)

Rating Risco =
VAR _score = [Score Risco Operadora]
RETURN SWITCH(TRUE(), ISBLANK(_score), "--", _score >= 0.75, "Alto Risco",
    _score >= 0.50, "Risco Elevado", _score >= 0.25, "Risco Moderado", "Baixo Risco")

Cor Risco Numérico = -- 0 a 4, para formatação condicional por faixa

-- Desvio padronizado do mês contra a média do período selecionado.
-- A guarda de HASONEVALUE existe porque, fora do contexto de um único mês, o "atual"
-- seria um acumulado comparado contra médias mensais — número absurdo com cara de
-- estatística. A versão anterior somava dentro do contexto do próprio mês e devolvia
-- BLANK sempre que o visual quebrava por mês.
Z-Score Volume Mensal =
IF(NOT (HASONEVALUE(dim_calendario[Ano]) && HASONEVALUE(dim_calendario[mes])), BLANK(),
    VAR _serie =
        ADDCOLUMNS(
            SUMMARIZE(ALLSELECTED(dim_calendario), dim_calendario[Ano], dim_calendario[mes]),
            "@v", VAR _a = dim_calendario[Ano] VAR _m = dim_calendario[mes]
                  RETURN CALCULATE([Total Reclamações], REMOVEFILTERS(dim_calendario),
                                   dim_calendario[Ano] = _a, dim_calendario[mes] = _m))
    VAR _media = AVERAGEX(_serie, [@v])
    VAR _dp    = STDEVX.P(_serie, [@v])
    VAR _atual = [Total Reclamações]
    RETURN IF(_dp = 0 || ISBLANK(_atual), BLANK(), DIVIDE(_atual - _media, _dp)))

Flag Anomalia   = -- rótulo do z-score em faixas de sigma
Flag Piora MoM  = -- compara [Var MoM %] com a média do setor
Pior Estado Operadora =
CALCULATE(SELECTEDVALUE(dim_uf[Estado], "Múltiplos"), TOPN(1, ALL(dim_uf), [Total Reclamações], DESC))
```

---

## [07] Categoria & Geografia

```dax
Rank Categoria    = RANKX(ALL(dim_tipo_reclamacao[Categoria]), [Total Reclamações], , DESC, DENSE)
Rank UF           = RANKX(ALL(dim_uf[Estado]), [Total Reclamações], , DESC, DENSE)
Share Categoria % = DIVIDE([Total Reclamações], CALCULATE([Total Reclamações], ALL(dim_tipo_reclamacao)), 0)
Share UF %        = DIVIDE([Total Reclamações], CALCULATE([Total Reclamações], ALL(dim_uf)), 0)
```

---

## [08] Narrativa

```dax
-- Frase montada por DAX que reage aos filtros. É o cartão "Leitura do período" da
-- primeira página: quem filtra por operadora recebe a leitura daquela operadora.
Insight Executivo =
VAR _topOp    = TOPN(1, ALL(dim_operadora[Operadora]), [Total Reclamações], DESC)
VAR _nomeTop  = MAXX(_topOp, dim_operadora[Operadora])
VAR _shareTop = DIVIDE(MAXX(_topOp, CALCULATE([Total Reclamações])),
                       CALCULATE([Total Reclamações], ALL(dim_operadora)))
VAR _mom = [Var MoM %]   VAR _res = [% Taxa Resolução]
VAR _estado = [Pior Estado Operadora]   VAR _hhiTxt = [Classificação HHI]
VAR _tend = SWITCH(TRUE(),
    ISBLANK(_mom), "sem base de comparação mensal",
    _mom > 0.05,  "com volume em ALTA de " & FORMAT(_mom, "0.0%") & " no mês (atenção)",
    _mom < -0.05, "com volume em QUEDA de " & FORMAT(ABS(_mom), "0.0%") & " no mês",
    "com volume estável no mês")
RETURN _nomeTop & " lidera as reclamações (" & FORMAT(_shareTop, "0.0%") & " do total), " &
       _tend & ". Taxa de resolução em " & FORMAT(_res, "0.0%") & " e mercado " &
       LOWER(_hhiTxt) & " (HHI " & FORMAT([HHI], "#,##0") & "). Maior concentração " &
       "geográfica: " & _estado & "."

Título Dinâmico       = -- "Reclamações ANATEL · <operadora> · <UF> · <ano>"
Sumarizacao Operadora = -- linha compacta com operadora, volume e taxa
```

---

## [09] Auxiliares

Medidas que devolvem **cor** (hex) ou **texto formatado**. Existem porque a formatação
condicional do Power BI aceita medida, e assim a regra de cor mora no modelo — um lugar
só — em vez de repetida em cada visual.

```dax
-- Paleta fixa por marca: CLARO é sempre o mesmo ciano, em qualquer página.
Cor Operadora =
SWITCH(SELECTEDVALUE(dim_operadora[Operadora]),
    "CLARO", "#5AD8F0", "VIVO", "#8B93F5", "TIM", "#E0A33A",
    "OI", "#3FBF87", "SERCOMTEL", "#E0685F", "NÃO IDENTIFICADA", "#4A5568", "#5AD8F0")

Cor Var MoM        = IF([Var MoM %] > 0, "#EF4444", "#10B981")
Cor Score Risco    = -- verde até 0,30 · âmbar até 0,45 · vermelho acima
Cor Taxa Resolução = -- compara com a média geral do período, ±2pp
Texto Var MoM      = -- variação com sinal explícito, "--" quando BLANK
```

> **Onde `Cor Operadora` NÃO é usada:** em gráfico de barras. O Power BI avalia a medida
> fora do contexto do ponto e pinta todas as barras da mesma cor — funciona em cartão,
> onde a medida é avaliada uma vez. Nas barras, a cor por marca é declarada por seletor
> de categoria na camada visual (`tools/build_report.py`, função `category_colors`).

---

## [11] Qualidade do Dado

```dax
Reclamações Não Identificadas =
CALCULATE([Total Reclamações], KEEPFILTERS(dim_operadora[Operadora] = "NÃO IDENTIFICADA"))

% Não Identificado        = DIVIDE([Reclamações Não Identificadas], [Total Reclamações Geral])
Cobertura de Identificação = 1 - [% Não Identificado]
```

Os registros sem prestadora identificada **ficam na base**: descartá-los deixaria o total
divergente da origem. Entram no volume consolidado e ficam sem base de assinantes, o que
anula a taxa por 100k em vez de produzir um número falso.

---

## Sobre este documento

A camada visual do relatório é gerada por `tools/build_report.py` e as medidas vivem no
modelo. Este arquivo existe para quem quer ler a lógica sem abrir o Power BI Desktop —
e para deixar registrado o **porquê** de cada decisão, que o modelo sozinho não conta.
