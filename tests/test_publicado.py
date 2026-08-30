"""
Os números publicados, como asserção — Telecom Operadoras (Power BI)

Execute com: pytest tests/ -v

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Este era o único repositório do portfólio sem nenhum teste, e o único cujo
número publicado ninguém conferia. Não é detalhe: o README estampa uma tabela
com seis operadoras, taxa de resolução e reclamações por 100 mil assinantes, e
a página "Operadoras" do relatório se apoia inteira num deles — SERCOMTEL
reclama 4x mais por assinante que a CLARO. Se o gerador mudar uma proporção,
o texto continua afirmando o número velho e nada avisa.

O que NÃO dá para testar aqui: o .pbix. O modelo é binário e as medidas vivem
dentro dele. O que dá para testar é a base sobre a qual o modelo roda — o star
schema em data/processed — e a coerência do que o repositório declara sobre si.
"""

import re
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"

# Base de assinantes por operadora (milhões). Espelha src/kpis.py — a
# normalização por 100 mil é o achado da página, então o denominador entra no
# teste em vez de ser importado: se alguém mexer no kpis.py sem querer, aqui
# quebra.
ASSINANTES = {"VIVO": 33.4, "CLARO": 35.2, "TIM": 25.0, "OI": 12.5, "SERCOMTEL": 0.4}


def _csv(nome):
    return pd.read_csv(PROC / f"{nome}.csv", encoding="utf-8-sig")


@pytest.fixture(scope="module")
def fato():
    return _csv("fato_reclamacoes")


@pytest.fixture(scope="module")
def por_operadora(fato):
    dim = _csv("dim_operadora")
    df = fato.merge(dim, on="id_operadora")
    g = df.groupby("nome").agg(volume=("qtd", "sum")).reset_index()
    g["share"] = g["volume"] / g["volume"].sum() * 100
    resp = df[df["status"] == "Respondida"].groupby("nome")["qtd"].sum()
    g["taxa_resolucao"] = g["nome"].map(resp).fillna(0) / g["volume"] * 100
    g["por_100k"] = g.apply(
        lambda r: r["volume"] / (ASSINANTES[r["nome"]] * 1000) * 100
        if r["nome"] in ASSINANTES else float("nan"),
        axis=1,
    )
    return g.set_index("nome")


# ── Integridade do star schema ────────────────────────────────────────────
# Um modelo dimensional quebra em silêncio: chave órfã não dá erro, vira
# categoria "em branco" no visual e some no meio de 8 mil linhas.

def test_fato_tem_o_volume_publicado(fato):
    assert fato["qtd"].sum() == 8000


def test_nenhuma_chave_orfa(fato):
    for coluna, dim in [
        ("id_data", "dim_calendario"), ("id_operadora", "dim_operadora"),
        ("id_uf", "dim_uf"), ("id_tipo", "dim_tipo_reclamacao"),
    ]:
        validas = set(_csv(dim)[coluna])
        orfas = set(fato[coluna]) - validas
        assert not orfas, f"{coluna}: {len(orfas)} chave(s) fora de {dim}"


def test_dimensoes_sem_chave_repetida():
    for dim, chave in [
        ("dim_calendario", "id_data"), ("dim_operadora", "id_operadora"),
        ("dim_uf", "id_uf"), ("dim_tipo_reclamacao", "id_tipo"),
    ]:
        d = _csv(dim)
        assert d[chave].is_unique, f"{dim}[{chave}] tem valor repetido"


def test_calendario_e_continuo():
    """Tabela de datas com buraco quebra time intelligence sem avisar."""
    cal = _csv("dim_calendario")
    datas = pd.to_datetime(cal["data"]).sort_values()
    assert (datas.diff().dropna() == pd.Timedelta(days=1)).all()
    assert datas.min().year == 2022 and datas.max().year == 2023


def test_as_27_ufs():
    assert len(_csv("dim_uf")) == 27


# ── Os números que o README publica ───────────────────────────────────────

@pytest.mark.parametrize("operadora,volume,share,taxa", [
    ("CLARO",     3391, 42.4, 71.9),
    ("VIVO",      2000, 25.0, 71.6),
    ("TIM",       1573, 19.7, 71.6),
    ("OI",         775,  9.7, 74.3),
    ("SERCOMTEL",  166,  2.1, 68.1),
])
def test_tabela_por_operadora(por_operadora, operadora, volume, share, taxa):
    linha = por_operadora.loc[operadora]
    assert linha["volume"] == volume
    assert round(linha["share"], 1) == share
    assert round(linha["taxa_resolucao"], 1) == taxa


def test_sercomtel_reclama_4x_mais_por_assinante(por_operadora):
    """O achado da pagina 'Operadoras'. Se cair abaixo de 4x, o texto mente."""
    sercomtel = por_operadora.loc["SERCOMTEL", "por_100k"]
    claro = por_operadora.loc["CLARO", "por_100k"]
    assert round(sercomtel, 1) == 41.5
    assert round(claro, 1) == 9.6
    assert sercomtel / claro >= 4.0


def test_ranking_bruto_e_o_normalizado_discordam(por_operadora):
    """A razao de existir das duas visoes lado a lado: se um dia a maior em
    volume for tambem a maior por assinante, a pagina perde o argumento."""
    maior_volume = por_operadora["volume"].idxmax()
    maior_por_100k = por_operadora["por_100k"].idxmax()
    assert maior_volume != maior_por_100k


def test_cobranca_e_velocidade_concentram_44_por_cento(fato):
    tipos = _csv("dim_tipo_reclamacao")
    df = fato.merge(tipos, on="id_tipo")
    total = df["qtd"].sum()
    duas = df[df["categoria"].isin(["Cobrança", "Velocidade"])]["qtd"].sum()
    # 44,5 e' o valor real. O README dizia "44%", que arredonda para baixo um
    # numero que esta exatamente em cima da fronteira — e "44" ou "45" viram
    # escolha de quem escreve, nao do dado.
    assert round(duas / total * 100, 1) == 44.5


# ── Coerencia do que o repositorio declara sobre si ───────────────────────

def _medidas_documentadas():
    """Conta as definicoes em dax/measures.md.

    Uma definicao e' uma linha na coluna 0, dentro de um bloco ```dax, no
    formato `Nome =`. VAR, RETURN e comentario tambem comecam na coluna 0 e
    fazem parte do CORPO da medida anterior — por isso a exclusao explicita.
    """
    texto = (RAIZ / "dax" / "measures.md").read_text(encoding="utf-8")
    corpo = texto[texto.index("## [01]"):]
    ignora = ("VAR ", "RETURN", "--", '"', "CALCULATE", "ADDCOLUMNS", "SUMMARIZE")
    nomes, dentro = [], False
    for ln in corpo.split("\n"):
        if ln.startswith("```dax"):
            dentro = True
            continue
        if ln.startswith("```"):
            dentro = False
            continue
        if dentro and ln and not ln[0].isspace() and not ln.startswith(ignora):
            # % conta como caractere inicial valido: "% Taxa Resolucao =" e
            # "% do Total =" sao nomes de medida reais no modelo, e o regex
            # anterior (so letra) as deixava de fora — 3 medidas documentadas
            # no arquivo nunca eram contadas.
            m = re.match(r"^([A-Za-zÀ-ÿ%][A-Za-zÀ-ÿ0-9 %ºª_/.\-]*?)\s*=(?!=)", ln)
            if m:
                nomes.append(m.group(1).strip())
    return nomes


def test_measures_md_documenta_o_que_diz_documentar():
    """O cabecalho de dax/measures.md afirmava 53 medidas e documentava 50.

    Numero de vitrine que ninguem confere e' exatamente o que este portfolio
    passou a semana removendo. Agora o documento tem de bater consigo mesmo.
    """
    texto = (RAIZ / "dax" / "measures.md").read_text(encoding="utf-8")
    declarado = int(re.search(r"^(\d+) medidas", texto, re.M).group(1))
    assert declarado == len(_medidas_documentadas())


def test_readme_cita_o_mesmo_numero_de_medidas():
    """O badge do README e o texto abaixo dele repetem o numero. Tres lugares
    para o mesmo fato e' onde a divergencia nasce."""
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    n = len(_medidas_documentadas())
    assert f"DAX-{n}%20medidas" in readme, "badge do README desatualizado"
    assert f"{n} medidas DAX" in readme, "texto do README desatualizado"


def test_nenhuma_medida_documentada_duas_vezes():
    nomes = _medidas_documentadas()
    repetidas = {n for n in nomes if nomes.count(n) > 1}
    assert not repetidas, f"medida duplicada em measures.md: {repetidas}"
