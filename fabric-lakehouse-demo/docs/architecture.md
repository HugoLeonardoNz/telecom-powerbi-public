# Arquitetura — Fabric Lakehouse Demo

```mermaid
flowchart LR
    subgraph Origem
        A["CSV ANATEL<br/>reclamacoes_scm.csv<br/>reclamacoes_smp.csv"]
    end

    subgraph Lakehouse Fabric
        B["Bronze<br/>bronze_reclamacoes_scm<br/>bronze_reclamacoes_smp<br/>(ingestão 1:1)"]
        C["Silver<br/>silver_reclamacoes<br/>(união + limpeza + normalização de operadora)"]
        D["Gold<br/>gold_kpis_operadora<br/>gold_kpis_regional<br/>gold_kpis_temporal"]
    end

    subgraph Consumo
        E["Power BI<br/>DirectLake"]
    end

    A -->|upload manual em Files/raw| B
    B -->|PySpark| C
    C -->|PySpark| D
    D -->|sem import, sem duplicar dado| E
```

## Por que medallion e não uma tabela só

- **Bronze** existe para reprocessar a Silver sem depender do arquivo CSV original — e
  para auditar o dado exatamente como a fonte publicou, antes de qualquer regra de
  negócio ser aplicada.
- **Silver** aplica uma única vez a normalização de marca (mapear "Telefonica Brasil
  S.A." → `VIVO`) e a tipagem de data — a mesma regra usada em `src/kpis.py::_norm` do
  projeto principal, portada para PySpark, para as duas versões não divergirem por
  engano.
- **Gold** é o que o relatório consome: agregações prontas, sem lógica de negócio dentro
  do Power BI além do que já está pré-calculado.

## DirectLake vs. Import

O `.pbix` principal deste repositório usa modo **Import** — os dados são copiados para
dentro do arquivo. Aqui, o relatório lê o **Delta Lake diretamente** (DirectLake): não
duplica o dado, reflete a tabela Gold assim que ela é reescrita, e é o modo recomendado
pelo Fabric para relatórios sobre Lakehouse.
