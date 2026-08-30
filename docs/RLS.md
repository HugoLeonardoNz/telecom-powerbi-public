Três roles no modelo, dois padrões de filtro diferentes:

| Role | Tabela filtrada | Expressão DAX | Cenário |
|---|---|---|---|
| `Operadora - VIVO` | `dim_operadora` | `dim_operadora[Operadora] = "VIVO"` | Multi-tenant: a operadora só vê os próprios indicadores |
| `Operadora - CLARO` | `dim_operadora` | `dim_operadora[Operadora] = "CLARO"` | Mesmo padrão, segunda operadora — mostra que a regra replica |
| `Regional - Sul` | `dim_uf` | `dim_uf[Região] = "Sul"` | Analista regional só vê a própria região |

## Por que essas duas tabelas

O filtro entra pela dimensão, não pelo fato: `dim_operadora` e `dim_uf` se relacionam com
`fato_reclamacoes` por relação simples (um-para-muitos, filtro de dimensão → fato), então
a role restringe a dimensão e o Power BI propaga o filtro para o fato e para as 53
medidas automaticamente — nenhuma medida precisou ser reescrita para respeitar a RLS.

## Como validar

No Power BI Desktop: **Modelagem → Gerenciar funções → Exibir como** → selecionar a role.
Cada uma delas deve reduzir o relatório inteiro (KPIs, gráficos, `Insight Executivo`) para
o recorte da operadora ou região correspondente — sem editar nenhum visual.

## Como foi criada

Via `mcp__powerbi-modeling-mcp` (Tabular Object Model / XMLA), conectando ao Power BI
Desktop aberto localmente — não pelo formato PBIP (este projeto não usa PBIP; o modelo
semântico vive compactado dentro do `.pbix`, ver seção "Camada visual gerada por código"
no README principal). É por isso que as roles não aparecem como diff de texto: existem no
binário `DataModel`, e a evidência delas é este documento + a validação visual acima.
