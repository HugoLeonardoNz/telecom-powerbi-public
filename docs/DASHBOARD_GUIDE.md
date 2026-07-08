# Dashboard Guide — Telecom Reclamações ANATEL

> Guia completo para entender, usar e atualizar o dashboard Power BI de reclamações de telecomunicações.

---

## Visão Geral

O dashboard monitora o **volume, tipo e resolução de reclamações** de consumidores registradas na ANATEL para os serviços de internet banda larga (SCM) e celular (SMP) das principais operadoras do Brasil.

**Para quem serve:**
- Gestores de qualidade e atendimento de operadoras
- Analistas de regulação e compliance
- Executivos monitorando posicionamento competitivo

**Período coberto:** 2022–2023 (atualizável conforme disponibilidade ANATEL)

---

## Modelo de Dados (Star Schema)

```
                         ┌─────────────────┐
                         │  fato_reclamacoes│
                         │─────────────────│
                         │ id_reclamacao   │
              ┌──────────│ id_operadora    │──────────┐
              │          │ id_uf           │          │
              │          │ id_tipo         │          │
              │          │ id_calendario   │          │
              │          │ dias_resolucao  │          │
              │          │ status          │          │
              │          │ qtd (=1)        │          │
              │          └────────┬────────┘          │
              │                   │                   │
     dim_operadora         dim_calendario          dim_uf
    ─────────────         ──────────────          ──────
    id_operadora          id_calendario           id_uf
    nome_operadora        data_completa           sigla_uf
    porte                 ano                     nome_uf
    grupo_economico       trimestre               regiao
                          mes
                          nome_mes
                          fim_semana
                                      dim_tipo_reclamacao
                                      ───────────────────
                                      id_tipo_reclamacao
                                      categoria (motivo)
                                      subcategoria (detalhe)
```

**Relacionamento:** Many-to-One (fato → dimensões) via chave inteira `id_*`.

---

## Páginas do Dashboard

### Página 1 — Visão Executiva (`overview`)

**Propósito:** Painel de entrada com os KPIs mais críticos em cards de destaque.

| Card | Medida DAX | Interpretação |
|------|-----------|---------------|
| Total Reclamações | `[Total Reclamações]` | Volume bruto no período filtrado |
| Taxa de Resolução | `[% Taxa Resolução]` | % respondidas sobre total |
| Pendentes | `[Pendentes]` | Reclamações sem resposta final |
| Var. MoM | `[Var MoM %]` | Crescimento vs. mês anterior |
| Dias Médios | `[Dias Médios Resolução]` | Tempo médio para resposta |

**Visuais principais:**
- **Barras horizontais:** Volume por operadora + linha de % resolução (eixo duplo)
- **Gráfico de rosca:** Share por operadora (% do total)
- **Linha temporal:** Tendência mensal de reclamações (total e por operadora)

**Filtros de página:**
- Período (slicer de data)
- Operadora (multi-select)
- Tipo de serviço: SCM / SMP

---

### Página 2 — Análise de Motivos (`motivos`)

**Propósito:** Entender o que provoca as reclamações e onde cada operadora falha.

| Visual | Dados | Uso |
|--------|-------|-----|
| Treemap | Motivo × Volume | Ver hierarquia de problemas de um relance |
| Heatmap | Operadora × Motivo | Identificar padrões de falha por marca |
| Barras empilhadas | Motivo por trimestre | Detectar sazonalidade de tipos de problema |

**Interpretação do heatmap:**
- Células escuras = maior concentração de reclamações naquela combinação
- Identifica qual operadora tem problema específico (ex: Claro + Cobrança)

---

### Página 3 — Qualidade de Atendimento (`resolucao`)

**Propósito:** Avaliar o quão bem cada operadora resolve os problemas.

**KPIs exibidos:**
- `% Taxa Resolução` por operadora
- `Dias Médios Resolução` por operadora
- `Pendentes` e `Em análise` por operadora

**Visual de destaque:** Gráfico de bullet (gauge) comparando taxa de resolução de cada operadora vs. meta (ex: 80%).

**Alerta condicional (`Flag Piora MoM`):**
```
🔴 Crítico     → Var MoM > +15% (piora expressiva)
🟡 Atenção     → Var MoM entre +5% e +15%
🟢 Melhora     → Var MoM < -5% (queda nas reclamações)
⚪ Estável     → Var MoM entre -5% e +5%
```

---

### Página 4 — Análise Regional (`regional`)

**Propósito:** Identificar onde os problemas se concentram geograficamente.

**Visuais:**
- **Mapa coroplético (shape map):** Brasil por UF, intensidade = volume de reclamações
- **Barras horizontais:** Top 15 estados por volume
- **Tabela detalhada:** UF × Operadora × Motivo com ranking

**Nota para interpretação regional:**
- Volume absoluto favorece estados populosos (SP, RJ, MG)
- Use `[Reclamações por 100k Assinantes]` para comparação justa entre estados
- Norte e Nordeste tendem a ter índice relativo mais alto apesar de menor volume absoluto

---

### Página 5 — Índice de Risco (`risco`)

**Propósito:** Score composto para ranquear operadoras por nível de risco regulatório.

**Fórmula do Score de Risco:**
```
Score = Volume (40%) + Resolução Invertida (35%) + Recl/100k (25%)
```
- Cada componente normalizado de 0 a 1
- Score mais alto = maior risco / pior performance

**Índice de Concentração (HHI):**
```DAX
Índice Concentração = SUMX(ALL(dim_operadora[nome_operadora]),
    ([Total Reclamações] / [Total Reclamações Geral]) ^ 2
) * 10000
```
- HHI < 1.500: mercado competitivo
- HHI 1.500–2.500: concentrado
- HHI > 2.500: altamente concentrado

---

## Como Atualizar os Dados

### Atualização Manual (dados ANATEL)

1. Acesse [dados.anatel.gov.br](https://dados.anatel.gov.br) → Reclamações de Consumidores
2. Baixe os CSVs de SCM e SMP do período desejado
3. Salve em `data/raw/` substituindo os arquivos existentes
4. Execute o pipeline:
   ```bash
   python data_prep/prepare_data.py
   python src/kpis.py
   ```
5. No Power BI Desktop: **Página Inicial → Atualizar**

### Com dados sintéticos (demonstração)

```bash
python src/generate_data.py      # Gera CSVs sintéticos em data/raw/
python data_prep/prepare_data.py # Gera star schema em data/processed/
python src/kpis.py               # Exporta KPIs para outputs/
```

---

## Medidas DAX — Referência Rápida

| Medida | Propósito | Página |
|--------|-----------|--------|
| `Total Reclamações` | Soma simples de qtd | Todas |
| `% Taxa Resolução` | Respondidas / Total | Visão Executiva, Resolução |
| `Var MoM %` | Variação vs. mês anterior | Visão Executiva |
| `Var YoY %` | Variação vs. ano anterior | Visão Executiva |
| `Média Móvel 3M` | Suavização da série temporal | Visão Executiva |
| `Reclamações por 100k` | Normalizado por assinantes | Regional, Risco |
| `Índice Concentração` | HHI de market share de reclamações | Risco |
| `Flag Piora MoM` | Sinal de alerta (Crítico/Atenção/Melhora) | Todas |

> Implementação completa de todas as medidas: `dax/measures.md`

---

## Limitações e Caveats

1. **Sem dados de assinantes reais:** A métrica `Recl/100k` usa estimativas de market share — para produção, substituir pela base real ANATEL
2. **Dias de resolução:** O dataset ANATEL não contém data de resposta; o campo `dias_resolucao` é estimado
3. **SMP vs. SCM:** Reclamações de celular e internet têm perfis de motivos distintos — filtrar por serviço para análises comparativas precisas
4. **Dados sintéticos:** Este repositório usa dados gerados por `src/generate_data.py` para demonstração. Para uso real, baixar CSVs do portal ANATEL

---

## Próximos Passos Sugeridos

- [ ] Integrar base de assinantes real (ANATEL → Setor Regulado)
- [ ] Adicionar NPS proxy via scraping de reclameaqui.com.br
- [ ] Dashboard de acompanhamento de metas mensais
- [ ] Alertas automáticos via Power Automate quando variação > threshold
- [ ] Publicar no Power BI Service com refresh agendado
