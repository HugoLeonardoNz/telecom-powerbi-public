# Guia de leitura do dashboard

Como navegar as 6 páginas e, mais importante, o que cada número quer dizer.

---

## Como o relatório se comporta

**Filtros.** Cada página (menos Metodologia) tem a mesma barra: **Ano**, **Operadora**,
**Região** e **Serviço**. Os filtros valem para a página em que estão — mudar de página
não carrega a seleção junto.

**Cruzamento.** Clicar em qualquer barra, fatia ou linha de tabela filtra os outros
visuais da página. Clicar de novo desfaz. `Ctrl` + clique acumula seleção.

**Navegação.** A barra de botões no topo direito troca de página; as abas na base do
Power BI fazem o mesmo.

**Drill.** Na matriz *Categoria × operadora* (página Motivos), o `+` ao lado da categoria
abre a subcategoria.

**Cor.** Cada operadora tem cor fixa em todas as páginas — CLARO ciano, VIVO índigo, TIM
âmbar, OI verde, SERCOMTEL vermelho, NÃO IDENTIFICADA cinza. Status também: verde
respondida, âmbar em análise, vermelho pendente. E cada uma das 11 categorias de
reclamação: uma família só, de azul a rosa, com "Outros" e "Não Informado" em cinza —
são ausência de informação, não mais um assunto.

Quando a cor não carrega informação nenhuma, ela também não varia: no gráfico de
subcategorias, todas as barras são ciano, porque ali o comprimento já diz tudo.

---

## Página 1 — Panorama Executivo

A leitura de 30 segundos.

| Elemento | O que mostra | Como ler |
|----------|--------------|----------|
| Total de reclamações | Volume no filtro atual | Base de comparação de tudo na página |
| Taxa de resolução | Respondidas ÷ total | Só mede se houve resposta, não se o cliente ficou satisfeito |
| Em aberto | Sem resposta final (pendente + em análise) | Passivo acumulado de atendimento |
| Variação mensal | Último mês vs. anterior | **Vermelho é alta de reclamação** — aqui subir é ruim |
| Concentração (HHI) | Soma dos quadrados dos market shares | < 1.500 competitivo · até 2.500 concentrado · acima, altamente concentrado |
| Leitura do período | Texto gerado por medida DAX | Reage aos filtros; some com o que está selecionado |
| Evolução mensal | Volume por mês + média móvel 3M | A média móvel mostra a tendência sem o ruído do mês |
| Composição por status | Distribuição do atendimento | O anel vermelho é o que ainda não foi respondido |
| Volume por operadora | Ranking bruto | Mede tamanho de base tanto quanto qualidade — ver página Operadoras |
| Principais motivos | Categoria do protocolo | Onde atacar primeiro |

> O eixo do gráfico de evolução **não começa em zero**. É proposital: a série oscila numa
> faixa estreita e ancorar em zero achataria a variação até ela sumir.

---

## Página 2 — Operadoras

A comparação competitiva, e a correção do viés de porte.

**Volume × taxa de resolução** — dispersão com as duas dimensões que importam. Eixo X é
volume, eixo Y é o percentual resolvido, e o **tamanho da bolha é reclamação por 100k
assinantes**. Canto inferior direito é o pior lugar do gráfico: muito volume, pouca
resolução.

**Reclamações por 100k assinantes** — a comparação justa. SERCOMTEL aparece em último no
volume bruto e em **primeiro** aqui: proporcionalmente à sua base, é a operadora que mais
gera reclamação. É o inverso da leitura ingênua do ranking.

**Painel por operadora** — tudo consolidado. Clicar numa linha filtra os dois gráficos
acima.

> NÃO IDENTIFICADA aparece sem valor por 100k. Não é falha do relatório: não existe base
> de assinantes para um registro sem prestadora, e a medida prefere ficar vazia a inventar.

---

## Página 3 — Motivos

**Reclamações por categoria** — o ranking de causas.

**Mix de motivos por operadora** — barras 100%. Aqui o tamanho da operadora some e sobra
só a *composição*: se uma marca tem proporcionalmente muito mais "Cobrança" que as
outras, o problema é de processo dela, não de escala.

**Categoria × operadora** — matriz com drill. Expandir a categoria mostra a subcategoria,
que é onde a causa raiz costuma aparecer.

**Subcategorias mais frequentes** — o mesmo detalhe da matriz, mas somado e ordenado:
serve para achar a queixa isolada mais comum sem ter que expandir 11 categorias uma a uma.

---

## Página 4 — Regiões

**Por região** e **por unidade federativa** — volume absoluto. Sem população como
denominador, o ranking acompanha o tamanho do estado; SP no topo é esperado, não é
descoberta.

**Situação por região** — barras 100% de status. Diferença de taxa de resolução entre
regiões indica capacidade de atendimento desigual.

**Detalhe por UF** — share e taxa de resolução por estado.

---

## Página 5 — Risco Regulatório

**Índice de risco por operadora** — o score composto:

```
score = 0,40 × volume normalizado
      + 0,35 × (1 − taxa de resolução)
      + 0,25 × reclamações por 100k normalizadas
```

Cada componente é reescalado pelo maior valor do conjunto, então o score fica entre 0 e 1.
Os pesos são uma escolha de modelagem — volume pesa mais porque é o que atrai atenção do
regulador, mas falha de resolução pesa quase igual porque é o que ele cobra.

**HHI, Top 3 e cobertura** — a estrutura do mercado e a confiabilidade da base.

**Desvio do volume mensal** — z-score de cada mês contra a média do período. Barra acima
de +2 ou abaixo de −2 é mês fora da curva e merece investigação; o resto é oscilação
normal.

**Tendência estrutural** — inclinação da reta de regressão sobre a série mensal, por
operadora. Positivo significa piora consistente ao longo do período, não um mês ruim.

---

## Página 6 — Metodologia & Modelo

Origem, grão, relações, camada de medidas, qualidade do dado e limites. Vale ler antes de
tirar conclusão de qualquer número das outras páginas — principalmente a parte de
**o que este relatório não responde**.

---

## Armadilhas conhecidas

- **Taxa de resolução ≠ satisfação.** Mede status `Respondida`, não desfecho.
- **Volume bruto ≠ qualidade.** Sempre cruzar com a métrica por 100k assinantes.
- **Os dados são sintéticos.** As proporções imitam a realidade publicada pela ANATEL,
  mas nenhum número aqui deve ser citado como fato de mercado.
- **Sem denominador populacional na análise regional.** O ranking de UF mede tamanho do
  estado tanto quanto qualidade do serviço.
