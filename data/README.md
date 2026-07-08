# Dados — ANATEL Reclamações de Consumidores

## Download

1. Acesse **dados.anatel.gov.br** → Reclamações e Denúncias de Consumidores
2. Baixe os CSVs para os serviços:
   - **SCM** (internet banda larga)
   - **SMP** (celular)  
   - **STFC** (telefonia fixa) — opcional
3. Salve na pasta `data/raw/`:
   - `data/raw/reclamacoes_scm.csv`
   - `data/raw/reclamacoes_smp.csv`

## Processamento

Após download, execute:
```bash
python data_prep/prepare_data.py
```

O script gera os CSVs limpos em `data/processed/` prontos para importação no Power BI.

## Saída Esperada em `data/processed/`

| Arquivo | Linhas aprox. | Descrição |
|---------|--------------|-----------|
| `fato_reclamacoes.csv` | ~500k | Tabela fato principal |
| `dim_operadora.csv` | ~50 | Dimensão operadora |
| `dim_uf.csv` | 27 | Dimensão estados |
| `dim_tipo_reclamacao.csv` | ~80 | Dimensão tipo/motivo |
| `dim_calendario.csv` | ~1.095 | Dimensão datas (3 anos) |
