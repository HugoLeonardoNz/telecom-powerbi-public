"""
generate_insight.py
Gera um resumo executivo em linguagem natural a partir dos KPIs já calculados
por `src/kpis.py`, usando um modelo de IA generativa (Gemini, free tier).

Por que isto é diferente da medida DAX `Insight Executivo` (dax/measures.md):
a medida DAX reage a filtro em tempo real dentro do relatório — isso é papel
do modelo, não deste script. Este script complementa: lê o período completo já
agregado em outputs/*.csv e produz uma leitura mais livre e narrativa,
pensada para colar num e-mail/Slack de fechamento de mês, sem abrir o Power BI.

Uso:
    python tools/generate_insight.py

Requer:
    pip install -r requirements-ai.txt
    GEMINI_API_KEY no .env (chave grátis em https://aistudio.google.com/apikey)

Saída:
    outputs/insight_ia_<AAAA-MM-DD>.md
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")


def _load_env_file() -> None:
    """Carrega .env se existir, sem exigir python-dotenv como dependência dura."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass


def _build_context() -> str:
    """Monta um resumo textual compacto dos KPIs para servir de contexto ao prompt."""
    consolidado = pd.read_csv(OUTPUTS / "kpis_consolidado.csv", encoding="utf-8-sig")
    por_op = pd.read_csv(OUTPUTS / "kpis_por_operadora.csv", encoding="utf-8-sig")
    regionais = pd.read_csv(OUTPUTS / "kpis_regionais.csv", encoding="utf-8-sig")
    motivos = pd.read_csv(OUTPUTS / "kpis_motivos.csv", encoding="utf-8-sig")
    temporais = pd.read_csv(OUTPUTS / "kpis_temporais.csv", encoding="utf-8-sig")

    linhas = ["## KPIs Consolidados"]
    for _, row in consolidado.iterrows():
        linhas.append(f"- {row['metrica']}: {row['valor']} {row['unidade']}")

    linhas.append("\n## Por Operadora (ordenado por volume)")
    for _, row in por_op.sort_values("ranking_volume").iterrows():
        linhas.append(
            f"- {row['operadora']}: {row['volume']} reclamações "
            f"({row['share_pct']}% do total), resolução {row['taxa_resolucao_pct']}%, "
            f"{row['recl_por_100k']} por 100k assinantes, score de risco {row['score_risco']}"
        )

    linhas.append("\n## Top 5 estados por volume")
    for _, row in regionais.sort_values("ranking").head(5).iterrows():
        linhas.append(f"- {row['uf']}: {row['volume']} reclamações ({row['share_pct']}%)")

    linhas.append("\n## Motivo mais frequente por operadora")
    top_motivo = motivos.sort_values("ranking").groupby("operadora").first().reset_index()
    for _, row in top_motivo.iterrows():
        linhas.append(f"- {row['operadora']}: {row['motivo']} ({row['share_pct']}%)")

    ultimo_mes = temporais["ano_mes"].max()
    variacoes = temporais[temporais["ano_mes"] == ultimo_mes]
    linhas.append(f"\n## Variação no último mês registrado ({ultimo_mes})")
    for _, row in variacoes.iterrows():
        mom = row["var_mom_pct"]
        mom_txt = f"{mom:+.1f}%" if pd.notna(mom) else "sem base de comparação"
        linhas.append(f"- {row['operadora']}: MoM {mom_txt}")

    return "\n".join(linhas)


PROMPT_TEMPLATE = """\
Você é um analista de dados sênior escrevendo o resumo executivo mensal de
reclamações ANATEL (telecom) para a diretoria comercial. O público não é técnico:
nada de jargão de dado, vá direto ao ponto de negócio.

Dados do período (já agregados, não invente números fora daqui):

{contexto}

Escreva um resumo executivo em português, em até 180 palavras, com:
1. Um parágrafo de abertura com o fato mais importante do período.
2. Um parágrafo sobre risco/atenção (quem está pior e por quê).
3. Uma recomendação de ação concreta e priorizada.

Não use bullet points. Tom direto, como se fosse para o comitê de diretoria.
"""


def _call_gemini(prompt: str) -> str:
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "Dependência de IA não instalada. Rode:\n"
            "  pip install -r requirements-ai.txt"
        ) from exc

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY não encontrada. Crie uma chave grátis em "
            "https://aistudio.google.com/apikey e coloque em um arquivo .env "
            "na raiz do projeto (veja .env.example)."
        )

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    return response.text.strip()


def main() -> None:
    print("=" * 60)
    print("  Insight Executivo via IA Generativa — Telecom ANATEL")
    print("=" * 60)

    _load_env_file()

    for req in ["kpis_consolidado.csv", "kpis_por_operadora.csv", "kpis_regionais.csv",
                "kpis_motivos.csv", "kpis_temporais.csv"]:
        if not (OUTPUTS / req).exists():
            raise FileNotFoundError(
                f"{req} não encontrado em outputs/. Rode antes: python src/kpis.py"
            )

    print("\nMontando contexto a partir dos KPIs já calculados...")
    contexto = _build_context()

    prompt = PROMPT_TEMPLATE.format(contexto=contexto)

    print(f"Chamando {MODEL_NAME}...")
    texto = _call_gemini(prompt)

    hoje = date.today().isoformat()
    destino = OUTPUTS / f"insight_ia_{hoje}.md"
    destino.write_text(
        f"# Insight Executivo — gerado por IA ({MODEL_NAME}) em {hoje}\n\n"
        f"{texto}\n\n"
        "---\n\n"
        "<details><summary>Prompt e contexto usados (transparência/auditoria)</summary>\n\n"
        f"```\n{prompt}\n```\n\n</details>\n",
        encoding="utf-8",
    )

    print(f"\n{'-' * 60}\n{texto}\n{'-' * 60}")
    print(f"\nSalvo em {destino.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
