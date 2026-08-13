"""
Data preparation pipeline for Telecom Operadoras Power BI Dashboard.

Reads raw ANATEL complaint CSVs (ISO-8859-1, semicolon-separated),
cleans them, and exports a star-schema set of CSVs ready for Power BI import.

Usage:
    python data_prep/prepare_data.py

Input:
    data/raw/reclamacoes_scm.csv   (ANATEL SCM complaints)
    data/raw/reclamacoes_smp.csv   (ANATEL SMP complaints) [optional]

Output (data/processed/):
    fato_reclamacoes.csv
    dim_operadora.csv
    dim_uf.csv
    dim_tipo_reclamacao.csv
    dim_calendario.csv
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
OUT_DIR = Path(__file__).parent.parent / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IMPLICIT_NULLS = {"-", "N/A", "NA", "NÃO INFORMADO", "NAO INFORMADO", " ", ""}

# Rótulo único para prestadora não identificada. Usado tanto na normalização
# quanto na dimensão, para não existirem dois nomes para o mesmo conceito.
NAO_IDENTIFICADA = "NÃO IDENTIFICADA"

COLUMN_RENAME = {
    "Data_Abertura":     "data_abertura",
    "Tipo":              "tipo",
    "Motivo":            "motivo",
    "Detalhe_Motivo":    "detalhe_motivo",
    "Status":            "status",
    "Agrupamento":       "agrupamento",
    "Nome":              "operadora_raw",
    "Porte":             "porte",
    "Grupo_Economico":   "grupo_economico",
    "UF":                "uf_sigla",
    "Municipio":         "municipio",
    "Sigla":             "sigla_servico",
}

OPERADORA_EXTRA = {
    "CLARO":      ("Grande", "América Móvil"),
    "VIVO":       ("Grande", "Telefónica"),
    "TIM":        ("Grande", "TIM Group"),
    "OI":         ("Grande", "Oi S.A."),
    "SERCOMTEL":  ("Médio",  "Sercomtel"),
    # Registros cuja prestadora não pôde ser identificada na base bruta.
    # Mantidos no fato (não são descartados) para que o volume total continue
    # batendo com a origem; ficam de fora das comparações competitivas.
    NAO_IDENTIFICADA: ("N/D", "Não identificado"),
}

UF_MAP = {
    "AC": ("Acre",                "Norte"),
    "AL": ("Alagoas",             "Nordeste"),
    "AP": ("Amapá",               "Norte"),
    "AM": ("Amazonas",            "Norte"),
    "BA": ("Bahia",               "Nordeste"),
    "CE": ("Ceará",               "Nordeste"),
    "DF": ("Distrito Federal",    "Centro-Oeste"),
    "ES": ("Espírito Santo",      "Sudeste"),
    "GO": ("Goiás",               "Centro-Oeste"),
    "MA": ("Maranhão",            "Nordeste"),
    "MT": ("Mato Grosso",         "Centro-Oeste"),
    "MS": ("Mato Grosso do Sul",  "Centro-Oeste"),
    "MG": ("Minas Gerais",        "Sudeste"),
    "PA": ("Pará",                "Norte"),
    "PB": ("Paraíba",             "Nordeste"),
    "PR": ("Paraná",              "Sul"),
    "PE": ("Pernambuco",          "Nordeste"),
    "PI": ("Piauí",               "Nordeste"),
    "RJ": ("Rio de Janeiro",      "Sudeste"),
    "RN": ("Rio Grande do Norte", "Nordeste"),
    "RS": ("Rio Grande do Sul",   "Sul"),
    "RO": ("Rondônia",            "Norte"),
    "RR": ("Roraima",             "Norte"),
    "SC": ("Santa Catarina",      "Sul"),
    "SP": ("São Paulo",           "Sudeste"),
    "SE": ("Sergipe",             "Nordeste"),
    "TO": ("Tocantins",           "Norte"),
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def load_raw(path: Path) -> pd.DataFrame:
    print(f"Loading {path.name}...")
    df = pd.read_csv(
        path,
        encoding="latin-1",
        sep=";",
        dtype=str,
        on_bad_lines="skip",
    )
    df.columns = df.columns.str.strip()
    df.replace(IMPLICIT_NULLS, pd.NA, inplace=True)
    df = df.rename(columns={k: v for k, v in COLUMN_RENAME.items() if k in df.columns})
    return df


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    df["data_abertura"] = pd.to_datetime(
        df["data_abertura"].str.strip(),
        format="%d/%m/%Y",
        errors="coerce",
    )
    return df.dropna(subset=["data_abertura"])


def normalize_operator(name: str | float) -> str:
    if pd.isna(name):
        return NAO_IDENTIFICADA
    name = str(name).strip().upper()
    mapping = {
        "CLARO S.A.": "CLARO",
        "CLARO S/A": "CLARO",
        "NET SERVIÇOS": "CLARO",
        "EMBRATEL": "CLARO",
        "VIVO":  "VIVO",
        "TELEFONICA BRASIL": "VIVO",
        "TELEFÔNICA BRASIL": "VIVO",
        "TIM CELULAR": "TIM",
        "TIM S.A.": "TIM",
        "OI S.A.": "OI",
        "OI MÓVEL": "OI",
        "SERCOMTEL": "SERCOMTEL",
    }
    for key, brand in mapping.items():
        if key in name:
            return brand
    return name.split()[0]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = parse_dates(df)
    df["operadora"] = df["operadora_raw"].apply(normalize_operator)
    df["status"] = df["status"].str.strip().str.title().fillna("Não Informado")
    df["motivo"] = df["motivo"].str.strip().str.title().fillna("Não Informado")
    df["detalhe_motivo"] = df["detalhe_motivo"].str.strip().str.title().fillna("Não Informado")
    df["uf_sigla"] = df["uf_sigla"].str.strip().str.upper().fillna("XX")
    df = df.drop_duplicates()
    return df


# ---------------------------------------------------------------------------
# Main ETL pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    # 1. Load and clean raw files
    frames = []
    for fname in ["reclamacoes_scm.csv", "reclamacoes_smp.csv"]:
        fpath = RAW_DIR / fname
        if fpath.exists():
            frames.append(clean(load_raw(fpath)))
        else:
            print(f"  [skip] {fname} not found — place file in data/raw/ to include it")

    if not frames:
        print("\nNo raw files found. Place ANATEL CSV files in data/raw/ and re-run.")
        raise SystemExit(1)

    df = pd.concat(frames, ignore_index=True)
    print(f"Total rows after cleaning: {len(df):,}")

    # 2. Dimension: Operadora
    dim_operadora = (
        df[["operadora", "porte", "grupo_economico"]]
        .drop_duplicates("operadora")
        .reset_index(drop=True)
        .rename(columns={"operadora": "nome"})
    )
    # OPERADORA_EXTRA é a fonte da verdade para porte/grupo: o valor que vem da
    # base bruta é o da primeira linha encontrada e não é confiável (foi assim
    # que "NÃO IDENTIFICADA" acabou herdando grupo econômico "Claro").
    for name, (porte, grupo) in OPERADORA_EXTRA.items():
        mask = dim_operadora["nome"] == name
        dim_operadora.loc[mask, "porte"] = porte
        dim_operadora.loc[mask, "grupo_economico"] = grupo
    dim_operadora.insert(0, "id_operadora", range(1, len(dim_operadora) + 1))
    print(f"dim_operadora: {len(dim_operadora)} rows")

    # 3. Dimension: UF
    dim_uf = pd.DataFrame(
        [{"sigla": k, "nome": v[0], "regiao": v[1]} for k, v in UF_MAP.items()]
    )
    dim_uf.insert(0, "id_uf", range(1, len(dim_uf) + 1))
    print(f"dim_uf: {len(dim_uf)} rows")

    # 4. Dimension: Tipo de Reclamação
    dim_tipo = (
        df[["motivo", "detalhe_motivo"]]
        .drop_duplicates()
        .sort_values(["motivo", "detalhe_motivo"])
        .reset_index(drop=True)
        .rename(columns={"motivo": "categoria", "detalhe_motivo": "subcategoria"})
    )
    dim_tipo.insert(0, "id_tipo", range(1, len(dim_tipo) + 1))
    print(f"dim_tipo_reclamacao: {len(dim_tipo)} rows")

    # 5. Dimension: Calendário
    min_date = df["data_abertura"].min().date()
    max_date = df["data_abertura"].max().date()
    dates = pd.date_range(min_date, max_date, freq="D")
    dim_calendario = pd.DataFrame({
        "data":        dates,
        "ano":         dates.year,
        "trimestre":   dates.quarter,
        "mes":         dates.month,
        "nome_mes":    dates.month.map(
            lambda m: ["Janeiro","Fevereiro","Marco","Abril","Maio","Junho",
                       "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"][m - 1]
        ),
        "semana_ano":  dates.isocalendar().week.astype(int),
        "dia_semana":  dates.day_of_week,
        "nome_dia":    dates.day_of_week.map(
            lambda d: ["Segunda","Terca","Quarta","Quinta","Sexta","Sabado","Domingo"][d]
        ),
        "fim_semana":  (dates.day_of_week >= 5).astype(int),
    })
    dim_calendario.insert(0, "id_data", range(1, len(dim_calendario) + 1))
    print(f"dim_calendario: {len(dim_calendario)} rows")

    # 6. Fact table: fato_reclamacoes
    op_lookup   = dim_operadora.set_index("nome")["id_operadora"]
    uf_lookup   = dim_uf.set_index("sigla")["id_uf"]
    tipo_lookup = dim_tipo.set_index(["categoria", "subcategoria"])["id_tipo"]
    cal_lookup  = dim_calendario.set_index("data")["id_data"]

    df["id_operadora"] = df["operadora"].map(op_lookup)
    df["id_uf"]        = df["uf_sigla"].map(uf_lookup)
    df["id_tipo"]      = df.set_index(["motivo", "detalhe_motivo"]).index.map(
        lambda x: tipo_lookup.get(x, pd.NA)
    )
    df["id_data"] = df["data_abertura"].dt.date.map(cal_lookup)

    fato = df[[
        "id_data", "id_operadora", "id_uf", "id_tipo",
        "status", "sigla_servico",
    ]].copy()
    fato["qtd"] = 1
    fato = fato.reset_index(drop=True)
    fato.insert(0, "id_reclamacao", range(1, len(fato) + 1))
    print(f"fato_reclamacoes: {len(fato):,} rows")

    # 7. Export
    exports = {
        "fato_reclamacoes.csv":     fato,
        "dim_operadora.csv":        dim_operadora,
        "dim_uf.csv":               dim_uf,
        "dim_tipo_reclamacao.csv":  dim_tipo,
        "dim_calendario.csv":       dim_calendario,
    }

    for fname, frame in exports.items():
        path = OUT_DIR / fname
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"  Exported {path.name} ({len(frame):,} rows)")

    print("\nDone. Import CSVs from data/processed/ into Power BI.")
    print("See dax/measures.md for all DAX measures.")


if __name__ == "__main__":
    main()
