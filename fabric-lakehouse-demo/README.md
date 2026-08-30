# Fabric Lakehouse Demo — mesmo dataset, arquitetura de nuvem

O `.pbix` na raiz deste repositório importa dados de CSV local. Esta pasta demonstra o
mesmo dataset (reclamações ANATEL) processado como **Lakehouse no Microsoft Fabric**,
com arquitetura medallion (Bronze → Silver → Gold) em PySpark e um relatório Power BI em
modo **DirectLake** — o cenário de quem já trabalha com Data Lake/Fabric em produção, não
só com Power BI Desktop isolado.

> Trial gratuito de capacidade Fabric, sem custo de infraestrutura fixa. Workspace e
> screenshots abaixo assim que a etapa de portal (manual, ver checklist) for concluída.

## Por que isto existe

O `telecom-powerbi-public` já prova modelagem dimensional, DAX e Power Query. O que ele
não prova é a parte que aparece em vagas mais avançadas de BI: conectar a fontes mais
complexas, trabalhar com Data Lake/Dataflows e operar dentro do ecossistema Fabric/Azure.
Em vez de inventar um projeto novo do zero, esta pasta reaproveita o dataset e a regra de
negócio já validados no projeto principal — só muda onde e como o dado é processado.

## Arquitetura

Ver [`docs/architecture.md`](docs/architecture.md) para o diagrama completo. Resumo:

```
Files/raw/*.csv  →  Bronze (ingestão 1:1)  →  Silver (limpeza + normalização)  →  Gold (KPIs agregados)  →  Power BI (DirectLake)
```

O notebook completo está em [`notebooks/bronze_to_gold.ipynb`](notebooks/bronze_to_gold.ipynb)
— pronto para colar num notebook do Fabric.

## Checklist de execução (portal Fabric — manual, precisa de login)

1. **Workspace**: criar/usar um workspace com capacidade Fabric trial ativa.
2. **Lakehouse**: `Novo item → Lakehouse`, nome sugerido `lh_telecom_anatel`.
3. **Upload**: em `Files`, criar pasta `raw/` e subir `data/raw/reclamacoes_scm.csv` e
   `data/raw/reclamacoes_smp.csv` (deste repositório).
4. **Notebook**: `Novo item → Notebook`, anexar o Lakehouse criado no passo 2 como
   *default lakehouse*, colar o conteúdo de `notebooks/bronze_to_gold.ipynb` (ou importar
   o arquivo direto) e rodar todas as células.
5. **Conferir**: no Lakehouse, a aba `Tables` deve mostrar `bronze_reclamacoes_scm`,
   `bronze_reclamacoes_smp`, `silver_reclamacoes`, `gold_kpis_operadora`,
   `gold_kpis_regional`, `gold_kpis_temporal`.
6. **Relatório DirectLake**: no Lakehouse, `Novo relatório` → escolher as tabelas
   `gold_kpis_*` → confirmar que abre em modo DirectLake (não Import).
7. **Paridade**: comparar `gold_kpis_operadora` com `outputs/kpis_por_operadora.csv` do
   projeto principal — mesmos números, fontes diferentes.
8. **Screenshots**: workspace, Lakehouse com as tabelas, notebook rodado, relatório
   DirectLake → salvar em `docs/img/` e linkar aqui.

## Stack

`Microsoft Fabric` · `Lakehouse` · `PySpark` · `Delta Lake` · `Power BI (DirectLake)`
