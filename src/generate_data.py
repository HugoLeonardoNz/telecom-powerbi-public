"""
generate_data.py
Gera dados sintéticos no formato ANATEL (SCM e SMP) para demonstração completa
do pipeline: limpeza → star schema → Power BI.

Os dados incluem os padrões de sujeira reais do ANATEL:
  - Encoding latin-1, separador ;
  - Datas como string DD/MM/AAAA
  - Capitalização inconsistente nos nomes de operadoras
  - Nulos implícitos: "-", "N/A", "NÃO INFORMADO"
  - Duplicatas (~2%) por re-uploads incrementais

Uso:
    python src/generate_data.py

Saída:
    data/raw/reclamacoes_scm.csv  (~5 100 linhas)
    data/raw/reclamacoes_smp.csv  (~3 060 linhas)
"""

import random
import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# ── Configuração ──────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

N_SCM = 5_000
N_SMP = 3_000
START = datetime.date(2022, 1, 1)
END   = datetime.date(2023, 12, 31)

# ── Tabelas de referência ─────────────────────────────────────────────────────

# Nome → (porte, grupo econômico, peso de mercado)
OPERADORAS = {
    "CLARO S.A.":                           ("Grande",   "Claro",      0.28),
    "CLARO S/A":                            ("Grande",   "Claro",      0.04),  # alias antigo
    "NET SERVIÇOS DE COMUNICAÇÃO S.A.":     ("Grande",   "Claro",      0.06),
    "TELEFONICA BRASIL S.A.":               ("Grande",   "Vivo",       0.26),
    "TIM S.A.":                             ("Grande",   "TIM",        0.20),
    "OI S.A.":                              ("Grande",   "Oi",         0.10),
    "SERCOMTEL S.A. - TELECOMUNICAÇÕES":    ("Pequeno",  "Sercomtel",  0.02),
    "EMBRATEL S.A.":                        ("Grande",   "Claro",      0.04),
}

UF_WEIGHTS = {
    "SP": 0.22, "RJ": 0.12, "MG": 0.10, "BA": 0.07, "RS": 0.06,
    "PR": 0.06, "PE": 0.05, "CE": 0.04, "PA": 0.04, "GO": 0.03,
    "MA": 0.03, "AM": 0.02, "ES": 0.02, "MT": 0.02, "MS": 0.02,
    "PB": 0.02, "RN": 0.02, "AL": 0.01, "PI": 0.01, "SE": 0.01,
    "TO": 0.01, "RO": 0.01, "AC": 0.005, "AP": 0.005, "RR": 0.005,
    "DF": 0.02, "SC": 0.03,
}

MUNICIPIOS = {
    "SP": ["SÃO PAULO", "CAMPINAS", "SANTOS", "GUARULHOS", "SOROCABA"],
    "RJ": ["RIO DE JANEIRO", "NITERÓI", "DUQUE DE CAXIAS", "NOVA IGUAÇU"],
    "MG": ["BELO HORIZONTE", "UBERLÂNDIA", "CONTAGEM", "JUIZ DE FORA"],
    "BA": ["SALVADOR", "FEIRA DE SANTANA", "VITÓRIA DA CONQUISTA"],
    "RS": ["PORTO ALEGRE", "CAXIAS DO SUL", "PELOTAS", "CANOAS"],
    "PR": ["CURITIBA", "LONDRINA", "MARINGÁ", "PONTA GROSSA"],
    "PE": ["RECIFE", "CARUARU", "PETROLINA", "OLINDA"],
    "CE": ["FORTALEZA", "CAUCAIA", "JUAZEIRO DO NORTE", "SOBRAL"],
    "PA": ["BELÉM", "ANANINDEUA", "SANTARÉM", "MARABÁ"],
    "GO": ["GOIÂNIA", "APARECIDA DE GOIÂNIA", "ANÁPOLIS"],
    "MA": ["SÃO LUÍS", "IMPERATRIZ", "TIMON"],
    "AM": ["MANAUS", "PARINTINS", "ITACOATIARA"],
    "ES": ["VITÓRIA", "VILA VELHA", "CARIACICA"],
    "MT": ["CUIABÁ", "VÁRZEA GRANDE", "SINOP"],
    "MS": ["CAMPO GRANDE", "DOURADOS", "TRÊS LAGOAS"],
    "DF": ["BRASÍLIA", "CEILÂNDIA", "TAGUATINGA"],
}

MOTIVOS_SCM = [
    ("Velocidade",   "Velocidade abaixo do contratado",    0.34),
    ("Cobrança",     "Cobrança indevida",                  0.22),
    ("Falha",        "Falha/Interrupção do serviço",        0.18),
    ("Atendimento",  "Atendimento inadequado",              0.10),
    ("Contrato",     "Cancelamento não realizado",          0.08),
    ("Instalação",   "Prazo de instalação excedido",        0.05),
    ("Outros",       "Outros",                              0.03),
]

MOTIVOS_SMP = [
    ("Cobrança",          "Cobrança indevida / surpresa na fatura",   0.28),
    ("Qualidade",         "Queda de sinal / cobertura inadequada",    0.25),
    ("Internet",          "Velocidade de internet móvel abaixo",      0.20),
    ("Portabilidade",     "Portabilidade numérica não efetivada",     0.12),
    ("Atendimento",       "Atendimento ao cliente",                   0.10),
    ("Outros",            "Outros",                                   0.05),
]

STATUS_DIST = [("Respondida", 0.72), ("Pendente", 0.18), ("Em análise", 0.10)]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _rdate(start: datetime.date, end: datetime.date) -> str:
    delta = (end - start).days
    d = start + datetime.timedelta(days=random.randint(0, delta))
    return d.strftime("%d/%m/%Y")


def _rhora() -> str:
    return f"{random.randint(7, 22):02d}:{random.randint(0, 59):02d}"


def _wc(items, weights):
    return random.choices(items, weights=weights, k=1)[0]


def _noise(value: str, prob: float = 0.03) -> str:
    """Injeta nulo implícito com probabilidade prob."""
    if random.random() < prob:
        return random.choice(["-", "N/A", "NÃO INFORMADO", " "])
    return value


def _op_variants(name: str) -> str:
    """Cria variações de capitalização para simular dado bruto."""
    variants = [name, name.lower().title(), name.upper()]
    return random.choices(variants, weights=[0.90, 0.05, 0.05], k=1)[0]


# ── Geradores de linhas ────────────────────────────────────────────────────────

def _make_row(agrupamento: str, motivos: list) -> dict:
    op_names   = list(OPERADORAS.keys())
    op_weights = [v[2] for v in OPERADORAS.values()]
    op         = _wc(op_names, op_weights)
    uf         = _wc(list(UF_WEIGHTS.keys()), list(UF_WEIGHTS.values()))
    muni       = random.choice(MUNICIPIOS.get(uf, [f"{uf} - INTERIOR"]))
    mot        = _wc(motivos, [m[2] for m in motivos])
    status     = _wc([s[0] for s in STATUS_DIST], [s[1] for s in STATUS_DIST])
    porte, grupo, _ = OPERADORAS[op]

    return {
        "Data_Abertura":   _rdate(START, END),
        "Hora_Abertura":   _rhora(),
        "Tipo":            "Reclamação",
        "Motivo":          _noise(mot[0]),
        "Detalhe_Motivo":  _noise(mot[1]),
        "Status":          status,
        "Agrupamento":     agrupamento,
        "Nome":            _noise(_op_variants(op), prob=0.01),
        "Porte":           _noise(porte, prob=0.02),
        "Grupo_Economico": _noise(grupo, prob=0.02),
        "UF":              uf,
        "Municipio":       muni,
        "Sigla":           agrupamento,
    }


def generate_df(n: int, agrupamento: str, motivos: list, dup_rate: float = 0.02) -> pd.DataFrame:
    rows = [_make_row(agrupamento, motivos) for _ in range(n)]
    # duplicatas como em re-uploads ANATEL
    n_dup = int(n * dup_rate)
    rows += random.choices(rows, k=n_dup)
    random.shuffle(rows)
    return pd.DataFrame(rows)


def save_latin1(df: pd.DataFrame, path: Path) -> None:
    """Salva CSV com encoding latin-1 e separador ; (formato ANATEL)."""
    df.to_csv(path, sep=";", index=False, encoding="latin-1")
    print(f"  OK  {path.name:35s} {len(df):>6,} linhas -> {path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Gerando dados sintéticos no formato ANATEL")
    print("=" * 60)

    df_scm = generate_df(N_SCM, "SCM", MOTIVOS_SCM, dup_rate=0.02)
    save_latin1(df_scm, RAW_DIR / "reclamacoes_scm.csv")

    df_smp = generate_df(N_SMP, "SMP", MOTIVOS_SMP, dup_rate=0.015)
    save_latin1(df_smp, RAW_DIR / "reclamacoes_smp.csv")

    print()
    print("Próximos passos:")
    print("  1. python data_prep/prepare_data.py   -> gera star schema em data/processed/")
    print("  2. python src/kpis.py                 -> exporta KPIs consolidados")
    print("  3. jupyter notebook notebooks/eda_suporte.ipynb")
    print("=" * 60)


if __name__ == "__main__":
    main()
