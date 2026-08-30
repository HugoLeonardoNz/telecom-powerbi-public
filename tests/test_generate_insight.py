"""
tools/generate_insight.py — contexto e chamada de API isolados

POR QUE ESTE ARQUIVO EXISTE
----------------------------
generate_insight.py chama uma API paga por token (Gemini). Rodar a suíte de
testes não pode depender de rede nem de chave de API válida — então aqui a
chamada é mockada e o que se testa é: (1) o contexto montado a partir dos
KPIs tem as seções esperadas, (2) sem GEMINI_API_KEY o erro é claro em vez de
uma exceção genérica do SDK.
"""

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import generate_insight as gi  # noqa: E402


@pytest.fixture
def outputs_prontos():
    faltando = [
        f for f in ["kpis_consolidado.csv", "kpis_por_operadora.csv",
                     "kpis_regionais.csv", "kpis_motivos.csv", "kpis_temporais.csv"]
        if not (gi.OUTPUTS / f).exists()
    ]
    if faltando:
        pytest.skip(f"outputs/ incompleto, rode 'python src/kpis.py' antes: faltam {faltando}")


def test_contexto_tem_todas_as_secoes(outputs_prontos):
    contexto = gi._build_context()
    for secao in ["KPIs Consolidados", "Por Operadora", "Top 5 estados",
                  "Motivo mais frequente", "Variação no último mês"]:
        assert secao in contexto


def test_sem_chave_api_da_erro_claro(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    fake_genai = types.ModuleType("genai")
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        gi._call_gemini("prompt de teste")


def test_com_chave_chama_o_modelo_e_devolve_texto(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "chave-falsa-de-teste")

    class _FakeResponse:
        text = "  resumo executivo gerado  "

    class _FakeModels:
        def generate_content(self, model, contents):
            assert model == gi.MODEL_NAME
            assert "prompt de teste" in contents
            return _FakeResponse()

    class _FakeClient:
        def __init__(self, api_key):
            assert api_key == "chave-falsa-de-teste"
            self.models = _FakeModels()

    fake_genai = types.ModuleType("genai")
    fake_genai.Client = _FakeClient
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    assert gi._call_gemini("prompt de teste") == "resumo executivo gerado"
