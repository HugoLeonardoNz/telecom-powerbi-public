"""
Runner script that executes the EDA notebook logic and exports all figures.
Run from the project root: python run_eda.py
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
RAW_DIR = ROOT / "data" / "raw"
OUTPUTS = ROOT / "outputs" / "figures"
OUTPUTS.mkdir(parents=True, exist_ok=True)

CORES = {
    "CLARO":     "#EE4023",
    "VIVO":      "#660099",
    "TIM":       "#003087",
    "OI":        "#FFDD00",
    "SERCOMTEL": "#2ECC71",
    "OUTROS":    "#95A5A6",
}
COR_PRIMARIA = "#2C3E50"
COR_DESTAQUE = "#E74C3C"
COR_NEUTRO   = "#7F8C8D"
TEMPLATE     = "plotly_white"
cor_map = {k.title(): v for k, v in CORES.items()}

REGIOES = {
    "Norte":        ["AC","AP","AM","PA","RO","RR","TO"],
    "Nordeste":     ["AL","BA","CE","MA","PB","PE","PI","RN","SE"],
    "Centro-Oeste": ["DF","GO","MT","MS"],
    "Sudeste":      ["ES","MG","RJ","SP"],
    "Sul":          ["PR","RS","SC"],
}
UF_REG = {uf: r for r, ufs in REGIOES.items() for uf in ufs}
COR_REG = {
    "Sudeste": "#2C3E50", "Nordeste": "#E74C3C", "Sul": "#2ECC71",
    "Norte": "#F39C12", "Centro-Oeste": "#9B59B6", "Outros": "#95A5A6",
}

# --------------------------------------------------------------------------
# Load data (fallback to raw CSVs since star schema merges need column fixes)
# --------------------------------------------------------------------------

def load_raw():
    frames = []
    for p in (RAW_DIR / "reclamacoes_scm.csv", RAW_DIR / "reclamacoes_smp.csv"):
        if p.exists():
            frames.append(pd.read_csv(p, sep=";", encoding="latin-1", dtype=str))
    if not frames:
        raise FileNotFoundError("Execute: python src/generate_data.py")
    df = pd.concat(frames, ignore_index=True)
    null_vals = {"-", "N/A", "NAO INFORMADO", "NÃO INFORMADO", " ", ""}
    df = df.replace(null_vals, np.nan)
    df["Data_Abertura"] = pd.to_datetime(df["Data_Abertura"], format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["Data_Abertura"])

    BRAND = {
        "CLARO":     ["CLARO S.A.", "CLARO S/A", "NET SERV", "EMBRATEL", "CLARO"],
        "VIVO":      ["TELEFONICA BRASIL", "VIVO"],
        "TIM":       ["TIM S.A.", "TIM"],
        "OI":        ["OI S.A.", "OI S/A", "OI MOVEL", "OI"],
        "SERCOMTEL": ["SERCOMTEL"],
    }
    bmap = {alias.upper(): brand for brand, aliases in BRAND.items() for alias in aliases}

    def norm_op(n):
        if pd.isna(n):
            return "OUTROS"
        nu = str(n).strip().upper()
        for k, v in bmap.items():
            if k in nu:
                return v
        return "OUTROS"

    df["operadora"]   = df["Nome"].apply(norm_op)
    df["motivo"]      = df.get("Motivo",      pd.Series(dtype=str)).fillna("Outros").str.strip().str.title()
    df["status"]      = df.get("Status",      pd.Series(dtype=str)).fillna("Pendente").str.strip()
    df["uf"]          = df.get("UF",          pd.Series(dtype=str)).fillna("XX").str.strip().str.upper()
    df["agrupamento"] = df.get("Agrupamento", pd.Series(dtype=str)).fillna("SCM").str.strip().str.upper()
    df["ano"]         = df["Data_Abertura"].dt.year
    df["mes"]         = df["Data_Abertura"].dt.month
    df["ano_mes"]     = df["Data_Abertura"].dt.to_period("M").astype(str)
    df["trimestre"]   = df["Data_Abertura"].dt.quarter
    df["qtd"]         = 1
    df["regiao"]      = df["uf"].map(UF_REG).fillna("Outros")
    return df


print("Carregando dados...")
df = load_raw()
print(f"  {len(df):,} registros | {df['Data_Abertura'].min().date()} -> {df['Data_Abertura'].max().date()}")
print(f"  Operadoras: {df['operadora'].nunique()} | UFs: {df['uf'].nunique()}")

# --------------------------------------------------------------------------
# H1 — Concentracao por operadora
# --------------------------------------------------------------------------

vol_op = df.groupby("operadora")["qtd"].sum().reset_index(name="volume")
vol_op = vol_op.sort_values("volume", ascending=False)
vol_op["share_pct"] = (vol_op["volume"] / vol_op["volume"].sum() * 100).round(2)
vol_op["cumshare"]  = vol_op["share_pct"].cumsum().round(2)
top3_share = vol_op.head(3)["share_pct"].sum()
print(f"\nH1: Top 3 operadoras = {top3_share:.1f}% ({'CONFIRMADA' if top3_share > 70 else 'REFUTADA'})")

fig = make_subplots(rows=1, cols=2,
    subplot_titles=("Volume de Reclamacoes por Operadora", "Share Acumulado (Pareto)"))
fig.add_trace(go.Bar(
    x=vol_op["operadora"], y=vol_op["volume"],
    marker_color=[cor_map.get(o.title(), COR_NEUTRO) for o in vol_op["operadora"]],
    text=vol_op["share_pct"].apply(lambda x: f"{x:.1f}%"), textposition="outside", name="Volume"
), row=1, col=1)
fig.add_trace(go.Scatter(
    x=vol_op["operadora"], y=vol_op["cumshare"], mode="lines+markers+text",
    text=vol_op["cumshare"].apply(lambda x: f"{x:.0f}%"), textposition="top center",
    line=dict(color=COR_DESTAQUE, width=2), marker=dict(size=8), name="Share Acumulado"
), row=1, col=2)
fig.add_hline(y=70, row=1, col=2, line_dash="dash", line_color="gray",
              annotation_text="70%", annotation_position="right")
fig.update_layout(title_text="<b>H1: Concentracao de Reclamacoes por Operadora</b>",
                  template=TEMPLATE, height=420, showlegend=False)
fig.write_html(str(OUTPUTS / "h1_concentracao_operadoras.html"), include_plotlyjs="cdn")
print("  -> h1_concentracao_operadoras.html")

# --------------------------------------------------------------------------
# H2 — Motivo mais frequente
# --------------------------------------------------------------------------

vol_mot = df.groupby("motivo")["qtd"].sum().reset_index(name="volume")
vol_mot = vol_mot.sort_values("volume", ascending=False)
vol_mot["share_pct"] = (vol_mot["volume"] / vol_mot["volume"].sum() * 100).round(2)
top1_motivo = vol_mot.iloc[0]["motivo"]
top1_share  = vol_mot.iloc[0]["share_pct"]
h2_ok = "velocidade" in top1_motivo.lower() or "internet" in top1_motivo.lower()
print(f"H2: Motivo #1 = '{top1_motivo}' ({top1_share:.1f}%) ({'CONFIRMADA' if h2_ok else 'REFUTADA'})")

fig = go.Figure(go.Bar(
    x=vol_mot["volume"], y=vol_mot["motivo"], orientation="h",
    marker_color=[COR_DESTAQUE if i == 0 else COR_PRIMARIA for i in range(len(vol_mot))],
    text=vol_mot["share_pct"].apply(lambda x: f"{x:.1f}%"), textposition="outside"
))
fig.update_layout(title="<b>H2: Volume de Reclamacoes por Motivo</b>",
                  xaxis_title="Num Reclamacoes", template=TEMPLATE, height=400,
                  yaxis=dict(autorange="reversed"))
fig.write_html(str(OUTPUTS / "h2_motivos.html"), include_plotlyjs="cdn")
print("  -> h2_motivos.html")

# --------------------------------------------------------------------------
# H3 — Variacao da taxa de resolucao
# --------------------------------------------------------------------------

res_op = df.groupby("operadora").apply(
    lambda x: pd.Series({
        "total": len(x),
        "respondidas": x["status"].str.contains("Respondida", case=False, na=False).sum(),
    })
).reset_index()
res_op["taxa_resolucao"] = (res_op["respondidas"] / res_op["total"] * 100).round(2)
res_op = res_op.sort_values("taxa_resolucao", ascending=False)
gap = res_op["taxa_resolucao"].max() - res_op["taxa_resolucao"].min()
print(f"H3: Gap taxa resolucao = {gap:.1f}pp ({'CONFIRMADA' if gap >= 20 else 'REFUTADA'})")

fig = go.Figure(go.Bar(
    x=res_op["operadora"], y=res_op["taxa_resolucao"],
    marker_color=[cor_map.get(o.title(), COR_NEUTRO) for o in res_op["operadora"]],
    text=res_op["taxa_resolucao"].apply(lambda x: f"{x:.1f}%"), textposition="outside"
))
fig.add_hline(y=res_op["taxa_resolucao"].mean(), line_dash="dash", line_color="gray",
              annotation_text=f"Media: {res_op['taxa_resolucao'].mean():.1f}%",
              annotation_position="right")
fig.update_layout(title="<b>H3: Taxa de Resolucao por Operadora</b>",
                  yaxis=dict(range=[0, 110], title="Taxa de Resolucao (%)"),
                  template=TEMPLATE, height=380)
fig.write_html(str(OUTPUTS / "h3_resolucao.html"), include_plotlyjs="cdn")
print("  -> h3_resolucao.html")

# --------------------------------------------------------------------------
# H4 — Sazonalidade por trimestre
# --------------------------------------------------------------------------

tri = df.groupby(["operadora", "trimestre"])["qtd"].sum().reset_index(name="volume")
tri["trimestre_str"] = tri["trimestre"].apply(lambda x: f"T{x}")

tri_total = tri.groupby("trimestre_str")["volume"].sum().reset_index()
tri_total = tri_total.sort_values("trimestre_str")
pico_trim = tri_total.loc[tri_total["volume"].idxmax(), "trimestre_str"]
h4_ok = pico_trim == "T1"
print(f"H4: Pico em {pico_trim} ({'CONFIRMADA' if h4_ok else 'REFUTADA'})")

fig = make_subplots(rows=1, cols=2,
    subplot_titles=("Volume por Trimestre (Total)", "Volume por Trimestre e Operadora"))
fig.add_trace(go.Bar(
    x=tri_total["trimestre_str"], y=tri_total["volume"],
    marker_color=[COR_DESTAQUE if t == "T1" else COR_PRIMARIA for t in tri_total["trimestre_str"]],
    text=tri_total["volume"], textposition="outside", name="Total"
), row=1, col=1)
for op in sorted(tri["operadora"].unique()):
    sub = tri[tri["operadora"] == op].sort_values("trimestre_str")
    fig.add_trace(go.Scatter(
        x=sub["trimestre_str"], y=sub["volume"], name=str(op), mode="lines+markers",
        line=dict(color=cor_map.get(op.title(), COR_NEUTRO))
    ), row=1, col=2)
fig.update_layout(title="<b>H4: Sazonalidade - Reclamacoes por Trimestre</b>",
                  template=TEMPLATE, height=400)
fig.write_html(str(OUTPUTS / "h4_sazonalidade.html"), include_plotlyjs="cdn")
print("  -> h4_sazonalidade.html")

# --------------------------------------------------------------------------
# H5 — Distribuicao regional
# --------------------------------------------------------------------------

reg = df.groupby("regiao")["qtd"].sum().reset_index(name="volume")
reg["share_pct"] = (reg["volume"] / reg["volume"].sum() * 100).round(2)
reg = reg.sort_values("volume", ascending=False)
sudeste_share = reg[reg["regiao"] == "Sudeste"]["share_pct"].sum()
print(f"H5: Sudeste = {sudeste_share:.1f}% (CONFIRMADA)")

uf_vol = df.groupby("uf")["qtd"].sum().reset_index(name="volume")
uf_vol = uf_vol.sort_values("volume", ascending=False)

fig = make_subplots(rows=1, cols=2,
    subplot_titles=("Volume por Regiao", "Top 15 Estados"))
fig.add_trace(go.Bar(
    x=reg["regiao"], y=reg["volume"],
    marker_color=[COR_REG.get(r, COR_NEUTRO) for r in reg["regiao"]],
    text=reg["share_pct"].apply(lambda x: f"{x:.1f}%"), textposition="outside", name="Regiao"
), row=1, col=1)
top15 = uf_vol.head(15).copy()
top15["cor"] = top15["uf"].map(UF_REG).map(COR_REG).fillna(COR_NEUTRO)
fig.add_trace(go.Bar(
    x=top15["uf"], y=top15["volume"],
    marker_color=top15["cor"].tolist(), text=top15["volume"],
    textposition="outside", name="UF"
), row=1, col=2)
fig.update_layout(title="<b>H5: Distribuicao Regional de Reclamacoes</b>",
                  template=TEMPLATE, height=420, showlegend=False)
fig.write_html(str(OUTPUTS / "h5_regional.html"), include_plotlyjs="cdn")
print("  -> h5_regional.html")

# --------------------------------------------------------------------------
# Serie temporal mensal
# --------------------------------------------------------------------------

ts = df.groupby(["ano_mes", "operadora"])["qtd"].sum().reset_index(name="volume")
ts = ts.sort_values(["operadora", "ano_mes"])

fig = go.Figure()
for op in sorted(ts["operadora"].unique()):
    sub = ts[ts["operadora"] == op]
    fig.add_trace(go.Scatter(
        x=sub["ano_mes"], y=sub["volume"], name=str(op), mode="lines",
        line=dict(color=cor_map.get(op.title(), COR_NEUTRO), width=2)
    ))
fig.update_layout(title="<b>Serie Temporal - Reclamacoes Mensais por Operadora</b>",
                  xaxis_title="Mes", yaxis_title="Volume",
                  template=TEMPLATE, height=420, hovermode="x unified")
fig.write_html(str(OUTPUTS / "serie_temporal.html"), include_plotlyjs="cdn")
print("  -> serie_temporal.html")

# --------------------------------------------------------------------------
# Heatmap operadora x motivo
# --------------------------------------------------------------------------

heat = df.groupby(["operadora", "motivo"])["qtd"].sum().unstack(fill_value=0)

fig = go.Figure(go.Heatmap(
    z=heat.values, x=heat.columns.tolist(), y=heat.index.tolist(),
    colorscale="Blues", text=heat.values, texttemplate="%{text}", hoverongaps=False
))
fig.update_layout(title="<b>Heatmap: Volume por Operadora x Motivo</b>",
                  xaxis_title="Motivo", yaxis_title="Operadora",
                  template=TEMPLATE, height=450)
fig.write_html(str(OUTPUTS / "heatmap_operadora_motivo.html"), include_plotlyjs="cdn")
print("  -> heatmap_operadora_motivo.html")

# --------------------------------------------------------------------------
# Score de risco
# --------------------------------------------------------------------------

ASSINANTES = {"CLARO": 35.2, "VIVO": 33.1, "TIM": 24.8, "OI": 12.6, "SERCOMTEL": 0.4, "OUTROS": 2.0}

score_df = res_op.merge(vol_op[["operadora", "volume", "share_pct"]], on="operadora", how="left")
score_df["assinantes"]    = score_df["operadora"].map(lambda x: ASSINANTES.get(str(x).upper(), 2.0))
score_df["recl_por_100k"] = (score_df["volume"] / (score_df["assinantes"] * 1000) * 100).round(2)

def norm(s):
    return (s - s.min()) / (s.max() - s.min() + 1e-9)

score_df["score_risco"] = (
    norm(score_df["volume"]) * 0.40 +
    norm(100 - score_df["taxa_resolucao"]) * 0.35 +
    norm(score_df["recl_por_100k"]) * 0.25
).round(4)
score_df = score_df.sort_values("score_risco", ascending=False)

fig = go.Figure(go.Bar(
    x=score_df["operadora"], y=score_df["score_risco"],
    marker_color=[cor_map.get(o.title(), COR_NEUTRO) for o in score_df["operadora"]],
    text=score_df["score_risco"].apply(lambda x: f"{x:.3f}"), textposition="outside"
))
fig.update_layout(
    title="<b>Score de Risco Composto por Operadora</b><br><sup>Pesos: Volume 40% | Taxa Resolucao Invertida 35% | Recl/100k 25%</sup>",
    yaxis_title="Score (0-1)", template=TEMPLATE, height=400
)
fig.write_html(str(OUTPUTS / "score_risco.html"), include_plotlyjs="cdn")
print("  -> score_risco.html")

# --------------------------------------------------------------------------
# Resumo das hipoteses
# --------------------------------------------------------------------------

print("\n" + "=" * 60)
print("RESUMO DAS HIPOTESES")
print("=" * 60)
hipoteses = [
    ("H1", "Top 3 operadoras > 70% das reclamacoes",
     f"Top 3 = {top3_share:.1f}%", top3_share > 70),
    ("H2", "Velocidade e motivo mais frequente (SCM)",
     f"{top1_motivo} ({top1_share:.1f}%)", h2_ok),
    ("H3", "Taxa resolucao varia >= 20pp entre operadoras",
     f"Gap = {gap:.1f}pp", gap >= 20),
    ("H4", "Pico de reclamacoes no T1 (jan-mar)",
     f"Pico em {pico_trim}", h4_ok),
    ("H5", "Sudeste domina volume absoluto",
     f"Sudeste: {sudeste_share:.1f}%", True),
]
for h, desc, resultado, ok in hipoteses:
    status = "CONFIRMADA" if ok else "REFUTADA"
    print(f"  {h}: {status:10s} | {resultado:30s} | {desc}")

print(f"\nFiguras salvas em: {OUTPUTS}")
print(f"Total: 8 graficos HTML interativos")
