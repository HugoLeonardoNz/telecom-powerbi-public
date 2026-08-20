# Dados — reclamações ANATEL (sintéticos)

> **Este diretório não contém dado real.** Os CSVs de `raw/` são **gerados** por
> `src/generate_data.py`. Antes este arquivo mandava baixar os CSVs do portal da
> ANATEL e prometia `fato_reclamacoes.csv` com ~500 mil linhas — instrução herdada
> de uma versão anterior do projeto, que contradizia o pipeline inteiro e era o
> primeiro arquivo que alguém abria para reproduzir.

## Por que sintético

O exercício aqui não é o volume, é a **sujeira**. O gerador reproduz os defeitos do
arquivo público real, e o pipeline tem de sobreviver a todos eles:

| Defeito | Efeito se ignorado |
|---|---|
| Encoding `latin-1` | Todo acento vira caractere corrompido lido como UTF-8 |
| Separador `;` | Com `sep=','` o arquivo vira uma coluna só |
| Data em texto `DD/MM/AAAA` | Bloqueia qualquer operação temporal |
| Capitalização mista | "CLARO", "Claro" e "claro " viram três operadoras |
| Nulos implícitos (`-`, `N/A`, `NÃO INFORMADO`) | `isna()` devolve zero e o inválido passa |
| ~2% de duplicatas | Infla a contagem de volume |

As proporções (participação por operadora, mix de motivos, sazonalidade) seguem a
ordem de grandeza do dado público. **Os números não devem ser citados como fato de
mercado** — servem para demonstrar o tratamento e a modelagem.

## Como gerar

```bash
python src/generate_data.py        # data/raw/  — 8.000 linhas sujas (SCM + SMP)
python data_prep/prepare_data.py   # data/processed/ — star schema limpo
```

| Arquivo gerado | Linhas | Papel |
|---|---:|---|
| `raw/reclamacoes_scm.csv` | ~5.100 | Bruto, banda larga (com duplicatas) |
| `raw/reclamacoes_smp.csv` | ~3.060 | Bruto, celular |
| `processed/fato_reclamacoes.csv` | 8.000 | Fato |
| `processed/dim_operadora.csv` | 6 | Dimensão |
| `processed/dim_uf.csv` | 27 | Dimensão |
| `processed/dim_tipo_reclamacao.csv` | 35 | Dimensão |
| `processed/dim_calendario.csv` | 730 | Dimensão de data (2022–2023) |

O `SEED = 42` está fixo em `generate_data.py`: rodar de novo dá exatamente os
mesmos 8.000 registros, e por isso os números do README e do `.pbix` conferem.

## Se você quiser rodar com o dado real

O portal é **dados.anatel.gov.br** → "Reclamações e Denúncias de Consumidores".
Baixe os CSVs de SCM e SMP, salve em `data/raw/` com os mesmos nomes e pule o
`generate_data.py`. O `prepare_data.py` foi escrito para o formato real e roda sem
alteração — é justamente o ponto do exercício. Os totais do painel vão mudar.
