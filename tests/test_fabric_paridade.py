"""
A paridade Fabric x pandas, como asserção — fabric-lakehouse-demo

Execute com: pytest tests/ -v

POR QUE ESTE ARQUIVO EXISTE
---------------------------
O README do fabric-lakehouse-demo publica uma tabela dizendo que a camada Gold
gerada no Microsoft Fabric bate número por número com outputs/kpis_por_operadora.csv.
Na primeira execução real ela NÃO batia: o data_prep/prepare_data.py deduplica e o
notebook PySpark não deduplicava. São 145 linhas repetidas no bruto da ANATEL —
8.145 contra 8.000, CLARO 3.460 contra 3.391. Nenhum dos dois pipelines deu erro.

Não dá para rodar Spark no CI, e o Lakehouse exige credencial. O que dá para
testar é o que causa a divergência:

  1. a tabela publicada no README bate com o CSV de referência do repositório;
  2. o notebook ainda contém os dois passos que fazem essa paridade existir
     (o dedupe e o rótulo único), com a mesma regra de marca;
  3. o dedupe aplicado ao dado bruto realmente produz o total publicado.

Se alguém remover o .dropDuplicates() do notebook "porque não parecia fazer nada",
este arquivo quebra antes de a divergência voltar a ser publicada.
"""

import json
import re
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
DEMO = RAIZ / "fabric-lakehouse-demo"
NOTEBOOK = DEMO / "notebooks" / "bronze_to_gold.ipynb"
README_DEMO = DEMO / "README.md"
REFERENCIA = RAIZ / "outputs" / "kpis_por_operadora.csv"
RAW = RAIZ / "data" / "raw"

# A Gold publicada. Espelha a tabela do README do demo de propósito: se alguém
# editar o README sem reexecutar o pipeline, a divergência aparece aqui.
GOLD_PUBLICADA = {
    "CLARO": 3391,
    "VIVO": 2000,
    "TIM": 1573,
    "OI": 775,
    "SERCOMTEL": 166,
    "NÃO IDENTIFICADA": 95,
}
TOTAL_PUBLICADO = 8000
LINHAS_DUPLICADAS = 145


@pytest.fixture(scope="module")
def codigo_notebook():
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    return "\n".join(
        "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"
    )


@pytest.fixture(scope="module")
def bruto():
    frames = []
    for nome in ["reclamacoes_scm.csv", "reclamacoes_smp.csv"]:
        d = pd.read_csv(
            RAW / nome, sep=";", encoding="latin-1", dtype=str, on_bad_lines="skip"
        )
        d.columns = d.columns.str.strip()
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


# --- 1. o que o README promete bate com o CSV de referência ------------------


def test_gold_publicada_bate_com_kpis_por_operadora():
    ref = pd.read_csv(REFERENCIA, encoding="utf-8-sig")
    do_csv = dict(zip(ref["operadora"], ref["volume"]))
    assert do_csv == GOLD_PUBLICADA, (
        "A tabela publicada no README do fabric-lakehouse-demo divergiu de "
        f"outputs/kpis_por_operadora.csv: {do_csv} != {GOLD_PUBLICADA}"
    )


def test_total_publicado_fecha():
    assert sum(GOLD_PUBLICADA.values()) == TOTAL_PUBLICADO


def test_readme_do_demo_cita_os_mesmos_numeros():
    texto = README_DEMO.read_text(encoding="utf-8")
    for operadora, volume in GOLD_PUBLICADA.items():
        formatado = f"{volume:,}".replace(",", ".")
        assert re.search(rf"\|\s*{re.escape(operadora)}\s*\|\s*{formatado}\s*\|", texto), (
            f"O README do demo não publica {operadora} = {formatado}"
        )


# --- 2. o notebook ainda contém o que faz a paridade existir ----------------


def test_notebook_deduplica_na_silver(codigo_notebook):
    assert "dropDuplicates()" in codigo_notebook, (
        "O notebook perdeu o .dropDuplicates(). Sem ele a Gold do Fabric fecha em "
        f"{TOTAL_PUBLICADO + LINHAS_DUPLICADAS} e diverge do pipeline pandas."
    )


def test_notebook_usa_o_rotulo_unico(codigo_notebook):
    assert '"NÃO IDENTIFICADA"' in codigo_notebook, (
        "O catch-all do notebook precisa usar o mesmo rótulo da dim_operadora."
    )
    assert '.otherwise("OUTROS")' not in codigo_notebook, (
        "Dois nomes para o mesmo conceito: OUTROS no Fabric, NÃO IDENTIFICADA no repo."
    )


@pytest.mark.parametrize(
    "marca", ["CLARO|NET SERVI|EMBRATEL", "TELEFONICA|TELEF.NICA|VIVO", "SERCOMTEL"]
)
def test_notebook_mantem_a_regra_de_marca(codigo_notebook, marca):
    assert marca in codigo_notebook


# --- 3. o dedupe sobre o dado bruto produz mesmo o total publicado ----------


def test_bruto_tem_as_linhas_duplicadas_esperadas(bruto):
    assert len(bruto) == TOTAL_PUBLICADO + LINHAS_DUPLICADAS
    assert len(bruto.drop_duplicates()) == TOTAL_PUBLICADO
    assert len(bruto) - len(bruto.drop_duplicates()) == LINHAS_DUPLICADAS


def test_regra_do_notebook_reproduz_a_gold_publicada(bruto):
    """A regra do notebook, reescrita em pandas, tem de dar a Gold publicada."""
    df = bruto.drop_duplicates().copy()
    df["dt"] = pd.to_datetime(
        df["Data_Abertura"].str.strip(), format="%d/%m/%Y", errors="coerce"
    )
    df = df.dropna(subset=["dt"])

    def marca(nome):
        u = "" if pd.isna(nome) else str(nome).strip().upper()
        if re.search(r"CLARO|NET SERVI|EMBRATEL", u):
            return "CLARO"
        if re.search(r"TELEFONICA|TELEF.NICA|VIVO", u):
            return "VIVO"
        if re.search(r"^TIM", u):
            return "TIM"
        if re.search(r"^OI ", u):
            return "OI"
        if re.search(r"SERCOMTEL", u):
            return "SERCOMTEL"
        return "NÃO IDENTIFICADA"

    obtido = df["Nome"].apply(marca).value_counts().to_dict()
    assert obtido == GOLD_PUBLICADA
