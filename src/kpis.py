"""
kpis.py
Calcula e exporta os principais KPIs de reclamações de telecomunicações
a partir do star schema gerado por data_prep/prepare_data.py.

KPIs produzidos:
  - Volume total e por operadora
  - Taxa de resolução (%)
  - Tempo médio de resolução (dias) — estimado por status
  - Reclamações por 100k assinantes (normalizado)
  - Variação MoM (mês anterior) e YoY (ano anterior)
  - Média móvel 3 meses
  - Top 5 motivos por operadora
  - Índice de Concentração Herfindahl-Hirschman (HHI)
  - Score de risco por operadora (composição ponderada)

Uso:
    python src/kpis.py

Saída:
    outputs/kpis_consolidado.csv
    outputs/kpis_por_operadora.csv
    outputs/kpis_motivos.csv
    outputs/kpis_regionais.csv
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Configuração ──────────────────────────────────────────────────────────────
ROOT         = Path(__file__).resolve().parent.parent
PROCESSED    = ROOT / "data" / "processed"
RAW_DIR      = ROOT / "data" / "raw"
OUTPUTS      = ROOT / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)

# Base de assinantes por operadora (estimativa 2023, em milhões — fonte ANATEL)
ASSINANTES = {
    "CLARO":      35.2,
    "VIVO":       33.1,
    "TIM":        24.8,
    "OI":         12.6,
    "SERCOMTEL":   0.4,
    "OUTROS":      2.0,
}

# ── Carregamento ──────────────────────────────────────────────────────────────

def _load_fato() -> pd.DataFrame:
    """Carrega fato_reclamacoes ou fallback para raw."""
    fato_path = PROCESSED / "fato_reclamacoes.csv"
    if fato_path.exists():
        df = pd.read_csv(fato_path, encoding="utf-8-sig")
        dim_op  = pd.read_csv(PROCESSED / "dim_operadora.csv",       encoding="utf-8-sig")
        dim_cal = pd.read_csv(PROCESSED / "dim_calendario.csv",      encoding="utf-8-sig")
        dim_tip = pd.read_csv(PROCESSED / "dim_tipo_reclamacao.csv", encoding="utf-8-sig")
        dim_uf  = pd.read_csv(PROCESSED / "dim_uf.csv",              encoding="utf-8-sig")

        # Rename before merge to avoid column name conflicts
        dim_op  = dim_op.rename(columns={"nome": "operadora"})
        dim_uf  = dim_uf.rename(columns={"sigla": "uf", "nome": "uf_nome"})
        dim_tip = dim_tip.rename(columns={"categoria": "motivo", "subcategoria": "detalhe_motivo"})

        df = (df
              .merge(dim_op,  on="id_operadora", how="left")
              .merge(dim_cal, on="id_data",       how="left")
              .merge(dim_tip, on="id_tipo",       how="left")
              .merge(dim_uf,  on="id_uf",         how="left"))

        # Derive time columns expected by KPI functions
        df["Data_Abertura"] = pd.to_datetime(df["data"], errors="coerce")
        df["ano"]       = df["Data_Abertura"].dt.year
        df["mes"]       = df["Data_Abertura"].dt.month
        df["ano_mes"]   = df["Data_Abertura"].dt.to_period("M").astype(str)
        df["trimestre"] = df["Data_Abertura"].dt.quarter
        df["qtd"]       = df.get("qtd", pd.Series(1, index=df.index))
        return df

    # Fallback: lê direto dos CSVs brutos
    scm = RAW_DIR / "reclamacoes_scm.csv"
    smp = RAW_DIR / "reclamacoes_smp.csv"
    frames = []
    for path in [scm, smp]:
        if path.exists():
            frames.append(pd.read_csv(path, sep=";", encoding="latin-1", dtype=str))
    if not frames:
        raise FileNotFoundError(
            "Nenhum dado encontrado. Execute:\n"
            "  1. python src/generate_data.py\n"
            "  2. python data_prep/prepare_data.py"
        )
    df = pd.concat(frames, ignore_index=True)

    # Limpeza mínima para os KPIs
    null_vals = {"-", "N/A", "NÃO INFORMADO", "NAO INFORMADO", " ", ""}
    df = df.replace(null_vals, np.nan)
    df.columns = [c.strip() for c in df.columns]

    # Data
    df["Data_Abertura"] = pd.to_datetime(
        df["Data_Abertura"], format="%d/%m/%Y", errors="coerce"
    )
    df = df.dropna(subset=["Data_Abertura"])

    # Normaliza operadora
    BRAND = {
        "CLARO":    ["CLARO S.A.", "CLARO S/A", "NET SERVIÇOS", "EMBRATEL", "CLARO"],
        "VIVO":     ["TELEFONICA BRASIL", "TELEFÔNICA BRASIL", "VIVO"],
        "TIM":      ["TIM S.A.", "TIM"],
        "OI":       ["OI S.A.", "OI S/A", "OI MÓVEL", "OI"],
        "SERCOMTEL": ["SERCOMTEL"],
    }
    brand_map = {}
    for brand, aliases in BRAND.items():
        for alias in aliases:
            brand_map[alias.upper()] = brand

    def _norm(nome):
        if pd.isna(nome):
            return "OUTROS"
        nome_up = str(nome).strip().upper()
        for key, val in brand_map.items():
            if key in nome_up:
                return val
        return "OUTROS"

    df["operadora"] = df["Nome"].apply(_norm)
    df["motivo"]    = df.get("Motivo", pd.Series(dtype=str)).fillna("Outros").str.strip().str.title()
    df["status"]    = df.get("Status", pd.Series(dtype=str)).fillna("Pendente").str.strip()
    df["uf"]        = df.get("UF", pd.Series(dtype=str)).fillna("XX").str.strip().str.upper()
    df["ano"]       = df["Data_Abertura"].dt.year
    df["mes"]       = df["Data_Abertura"].dt.month
    df["ano_mes"]   = df["Data_Abertura"].dt.to_period("M").astype(str)
    df["trimestre"] = df["Data_Abertura"].dt.quarter
    df["qtd"]       = 1

    return df


# ── KPIs consolidados ─────────────────────────────────────────────────────────

def kpis_consolidado(df: pd.DataFrame) -> pd.DataFrame:
    total = len(df)
    resolvidas = df["status"].str.contains("Respondida", case=False, na=False).sum()
    taxa_res = resolvidas / total * 100 if total else 0

    # HHI — Índice de Concentração
    shares = df.groupby("operadora")["qtd"].sum() / total
    hhi = (shares**2).sum() * 10_000

    periodo_min = df["Data_Abertura"].min()
    periodo_max = df["Data_Abertura"].max()

    resumo = pd.DataFrame([{
        "metrica":              "Total Reclamações",
        "valor":                total,
        "unidade":              "reclamações",
    }, {
        "metrica":              "Taxa de Resolução",
        "valor":                round(taxa_res, 2),
        "unidade":              "%",
    }, {
        "metrica":              "Pendentes",
        "valor":                total - resolvidas,
        "unidade":              "reclamações",
    }, {
        "metrica":              "Operadoras Monitoradas",
        "valor":                df["operadora"].nunique(),
        "unidade":              "operadoras",
    }, {
        "metrica":              "Estados Cobertos",
        "valor":                df["uf"].nunique(),
        "unidade":              "UFs",
    }, {
        "metrica":              "Motivos Distintos",
        "valor":                df["motivo"].nunique(),
        "unidade":              "motivos",
    }, {
        "metrica":              "HHI Concentração",
        "valor":                round(hhi, 0),
        "unidade":              "pontos (max 10.000)",
    }, {
        "metrica":              "Período Início",
        "valor":                periodo_min.strftime("%d/%m/%Y") if pd.notna(periodo_min) else "-",
        "unidade":              "data",
    }, {
        "metrica":              "Período Fim",
        "valor":                periodo_max.strftime("%d/%m/%Y") if pd.notna(periodo_max) else "-",
        "unidade":              "data",
    }])
    return resumo


# ── KPIs por operadora ────────────────────────────────────────────────────────

def kpis_por_operadora(df: pd.DataFrame) -> pd.DataFrame:
    total = len(df)
    grp = df.groupby("operadora")

    vol = grp["qtd"].sum().rename("volume")
    res = grp.apply(
        lambda x: x["status"].str.contains("Respondida", case=False, na=False).mean() * 100
    ).rename("taxa_resolucao_pct")

    por_op = pd.concat([vol, res], axis=1).reset_index()
    por_op["share_pct"]       = (por_op["volume"] / total * 100).round(2)
    por_op["assinantes_mi"]   = por_op["operadora"].map(ASSINANTES).fillna(2.0)
    por_op["recl_por_100k"]   = (
        por_op["volume"] / (por_op["assinantes_mi"] * 1_000) * 100
    ).round(2)
    por_op["ranking_volume"]  = por_op["volume"].rank(ascending=False, method="min").astype(int)
    por_op["ranking_100k"]    = por_op["recl_por_100k"].rank(ascending=False, method="min").astype(int)

    # Score de risco ponderado (volume 40%, taxa resolução invertida 35%, recl_100k 25%)
    def _normalize(s):
        mn, mx = s.min(), s.max()
        return (s - mn) / (mx - mn + 1e-9)

    por_op["score_risco"] = (
        _normalize(por_op["volume"])               * 0.40 +
        _normalize(100 - por_op["taxa_resolucao_pct"]) * 0.35 +
        _normalize(por_op["recl_por_100k"])        * 0.25
    ).round(4)

    por_op["taxa_resolucao_pct"] = por_op["taxa_resolucao_pct"].round(2)
    return por_op.sort_values("ranking_volume")


# ── KPIs temporais (MoM, YoY, MM3) ───────────────────────────────────────────

def kpis_temporais(df: pd.DataFrame) -> pd.DataFrame:
    mensal = (
        df.groupby(["ano_mes", "operadora"])["qtd"]
        .sum()
        .reset_index()
        .rename(columns={"qtd": "volume"})
    )
    mensal["ano_mes_dt"] = pd.to_datetime(mensal["ano_mes"], format="%Y-%m")
    mensal = mensal.sort_values(["operadora", "ano_mes_dt"])

    mensal["volume_mes_anterior"] = mensal.groupby("operadora")["volume"].shift(1)
    mensal["var_mom_pct"] = (
        (mensal["volume"] - mensal["volume_mes_anterior"])
        / mensal["volume_mes_anterior"].replace(0, np.nan)
        * 100
    ).round(2)

    mensal["volume_ano_anterior"] = mensal.groupby("operadora")["volume"].shift(12)
    mensal["var_yoy_pct"] = (
        (mensal["volume"] - mensal["volume_ano_anterior"])
        / mensal["volume_ano_anterior"].replace(0, np.nan)
        * 100
    ).round(2)

    mensal["media_movel_3m"] = (
        mensal.groupby("operadora")["volume"]
        .transform(lambda x: x.rolling(3, min_periods=1).mean())
        .round(1)
    )

    return mensal.drop(columns=["ano_mes_dt"])


# ── KPIs por motivo ───────────────────────────────────────────────────────────

def kpis_motivos(df: pd.DataFrame) -> pd.DataFrame:
    total = len(df)
    motivos = (
        df.groupby(["operadora", "motivo"])["qtd"]
        .sum()
        .reset_index()
        .rename(columns={"qtd": "volume"})
    )
    motivos["share_pct"] = (motivos["volume"] / total * 100).round(2)
    motivos["ranking"]   = (
        motivos.groupby("operadora")["volume"]
        .rank(ascending=False, method="min")
        .astype(int)
    )
    return motivos.sort_values(["operadora", "ranking"])


# ── KPIs regionais ────────────────────────────────────────────────────────────

def kpis_regionais(df: pd.DataFrame) -> pd.DataFrame:
    total = len(df)
    reg = (
        df.groupby("uf")
        .agg(
            volume=("qtd", "sum"),
            taxa_resolucao=("status", lambda x: (
                x.str.contains("Respondida", case=False, na=False).mean() * 100
            )),
        )
        .reset_index()
    )
    reg["share_pct"]      = (reg["volume"] / total * 100).round(2)
    reg["taxa_resolucao"] = reg["taxa_resolucao"].round(2)
    reg["ranking"]        = reg["volume"].rank(ascending=False, method="min").astype(int)
    return reg.sort_values("ranking")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  KPI Calculator — Telecom Reclamações ANATEL")
    print("=" * 60)

    print("\nCarregando dados...")
    df = _load_fato()
    print(f"  {len(df):,} registros carregados.")

    targets = [
        ("kpis_consolidado.csv",    kpis_consolidado,    "KPIs Consolidados"),
        ("kpis_por_operadora.csv",  kpis_por_operadora,  "KPIs por Operadora"),
        ("kpis_temporais.csv",      kpis_temporais,      "Série Temporal MoM/YoY/MM3"),
        ("kpis_motivos.csv",        kpis_motivos,        "KPIs por Motivo"),
        ("kpis_regionais.csv",      kpis_regionais,      "KPIs Regionais por UF"),
    ]

    print("\nCalculando KPIs...")
    for fname, fn, label in targets:
        result = fn(df)
        out = OUTPUTS / fname
        result.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"  OK  {label:35s} -> {out.name} ({len(result)} linhas)")

    # Preview: Top operadoras
    por_op = kpis_por_operadora(df)
    print("\nTop Operadoras por Volume:")
    print(por_op[["operadora", "volume", "share_pct", "taxa_resolucao_pct",
                   "recl_por_100k", "score_risco"]].to_string(index=False))

    print("\nKPIs Consolidados:")
    resumo = kpis_consolidado(df)
    print(resumo.to_string(index=False))

    print("\n" + "=" * 60)
    print("  Arquivos exportados em outputs/")
    print("  Prontos para importacao no Power BI.")
    print("=" * 60)


if __name__ == "__main__":
    main()
