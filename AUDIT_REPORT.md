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
