"""
Gerador do relatorio (camada visual) do .pbix — "report as code".

O .pbix e um zip. Desde o formato PBIR, a camada de relatorio vive em
`Report/definition/**` como JSON versionavel: uma pasta por pagina, um arquivo
por visual. Este script REESCREVE essa camada inteira a partir da especificacao
declarativa abaixo, preservando o modelo de dados (`DataModel`) intacto.

Por que gerar em vez de arrastar visual no Desktop:
  - o layout vira grid calculado (margens, calhas e alturas sempre coerentes);
  - a formatacao e definida uma vez e aplicada a todos os visuais;
  - a revisao do relatorio vira diff de codigo.

Uso:
    python tools/build_report.py [origem.pbix] [destino.pbix]

O tema (`theme/fibernet_dark.json`) e embutido no arquivo como tema customizado.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

# Chaves em PBIR_SKIP desligam recursos do gerador. Existe para isolar, em uma
# rodada so, qual construcao o Power BI Desktop recusa ao abrir o arquivo.
SKIP = {s.strip() for s in os.environ.get("PBIR_SKIP", "").split(",") if s.strip()}


def on(feature: str) -> bool:
    return feature not in SKIP

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PBIX = ROOT / "telecom_reclamacoes_anatel.pbix"
THEME_FILE = ROOT / "theme" / "fibernet_dark.json"

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

BG_OUT = "#07080B"     # area fora do canvas
BG_PAGE = "#0B0D11"    # canvas
BG_CARD = "#12151B"    # superficie dos paineis
BORDER = "#242A36"     # contorno dos paineis (unica separacao, entao um tom acima)
GRID = "#191D25"       # linhas de grade
BG_ALT = "#12161D"     # faixa alternada das tabelas (sutil sobre o fundo)
CHICLET_OFF = "#171C24"  # bloco nao selecionado
CHICLET_ON = "#1F4E5A"   # bloco selecionado

TXT = "#E9EDF3"        # texto primario
TXT_MUT = "#96A0B2"    # texto secundario
TXT_DIM = "#687284"    # texto terciario

CYAN = "#5AD8F0"
INDIGO = "#8B93F5"
AMBER = "#E0A33A"
GREEN = "#3FBF87"
RED = "#E05A52"
SLATE = "#4A5568"

# Paleta categorica: mesma ordem da paleta do tema.
SERIES = [CYAN, INDIGO, AMBER, GREEN, RED, "#9D7BF0", "#4FB8E8", "#D4A95C"]

# Cor fixa por marca e por status. Amarrar a cor ao valor (e nao a ordem em que
# ele aparece no visual) e o que faz CLARO ser sempre ciano em todas as paginas.
BRAND = {
    "CLARO": CYAN,
    "VIVO": INDIGO,
    "TIM": AMBER,
    "OI": GREEN,
    "SERCOMTEL": RED,
    "NÃO IDENTIFICADA": SLATE,
}
STATUS = {
    "Respondida": GREEN,
    "Em Análise": AMBER,
    "Pendente": RED,
}

FONT = "Segoe UI"
FONT_SEMI = "Segoe UI Semibold"

# Grid da pagina (1920x1080)
PAGE_W, PAGE_H = 1920, 1080
MARGIN = 32
GUTTER = 16
CONTENT_W = PAGE_W - 2 * MARGIN          # 1856
HEADER_Y, HEADER_H = 20, 78   # 78: titulo 22px + subtitulo 11px cabem sem corte
FILTER_Y, FILTER_H = 106, 80              # 80px: cabecalho + uma linha de blocos
BODY_Y = 204                              # inicio da area de conteudo
BODY_H = PAGE_H - BODY_Y - 36             # 840

ENTITY_M = "_Medidas"


def cols(n: int, gutter: int = GUTTER, x0: int = MARGIN, total: int = CONTENT_W):
    """Divide a largura util em n colunas iguais. Devolve [(x, w), ...]."""
    w = (total - gutter * (n - 1)) / n
    return [(x0 + i * (w + gutter), w) for i in range(n)]


def rows(n: int, gutter: int = GUTTER, y0: int = BODY_Y, total: int = BODY_H):
    """Divide a altura util em n faixas iguais. Devolve [(y, h), ...]."""
    h = (total - gutter * (n - 1)) / n
    return [(y0 + i * (h + gutter), h) for i in range(n)]


def split(*weights: float, gutter: int = GUTTER, y0: int = BODY_Y, total: int = BODY_H):
    """Faixas com alturas proporcionais. split(2, 1) = faixa de cima com o dobro."""
    free = total - gutter * (len(weights) - 1)
    unit = free / sum(weights)
    out, y = [], y0
    for w in weights:
        h = unit * w
        out.append((y, h))
        y += h + gutter
    return out


# ---------------------------------------------------------------------------
# Helpers de expressao (formato PBIR)
# ---------------------------------------------------------------------------

def lit(value) -> dict:
    """Literal PBIR. str -> 'texto', bool -> true/false, num -> 12D."""
    if isinstance(value, bool):
        v = "true" if value else "false"
    elif isinstance(value, str):
        v = "'" + value.replace("'", "''") + "'"
    else:
        v = f"{value}D"
    return {"expr": {"Literal": {"Value": v}}}


def solid(color: str) -> dict:
    """Cor fixa."""
    return {"solid": {"color": lit(color)}}


def solid_by_measure(measure: str, fallback: str = CYAN) -> dict:
    """Cor por valor de campo (formatacao condicional apontando para uma medida)."""
    if not on("cfcolor"):
        return solid(fallback)
    return {
        "solid": {
            "color": {
                "expr": {
                    "Measure": {
                        "Expression": {"SourceRef": {"Entity": ENTITY_M}},
                        "Property": measure,
                    }
                }
            }
        }
    }


def obj(**props) -> list:
    """Um bloco de propriedades de objeto de visual."""
    return [{"properties": props}]


def category_colors(entity: str, prop: str, mapping: dict[str, str]) -> list:
    """Cor fixa por valor de categoria.

    Cor por medida (`solid_by_measure`) funciona em cartao, onde a medida e
    avaliada uma vez, mas num grafico de barras o Power BI avalia a expressao
    fora do contexto do ponto e pinta tudo da mesma cor. Amarrar a cor ao valor
    da categoria via seletor resolve isso de forma deterministica.
    """
    return [
        {
            "properties": {"fill": solid(color)},
            "selector": {
                "data": [{
                    "scopeId": {
                        "Comparison": {
                            "ComparisonKind": 0,
                            "Left": {"Column": {
                                "Expression": {"SourceRef": {"Entity": entity}},
                                "Property": prop,
                            }},
                            "Right": {"Literal": {"Value": "'" + value.replace("'", "''") + "'"}},
                        }
                    }
                }]
            },
        }
        for value, color in mapping.items()
    ]


def measure_field(name: str, entity: str = ENTITY_M) -> dict:
    return {
        "field": {
            "Measure": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": name,
            }
        },
        "queryRef": f"{entity}.{name}",
        "nativeQueryRef": name,
    }


def column_field(entity: str, prop: str, active: bool = True) -> dict:
    d = {
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": prop,
            }
        },
        "queryRef": f"{entity}.{prop}",
        "nativeQueryRef": prop,
    }
    if active:
        d["active"] = True
    return d


def sort_by_measure(name: str, direction: str = "Descending", entity: str = ENTITY_M) -> dict:
    return {
        "sort": [
            {
                "field": {
                    "Measure": {
                        "Expression": {"SourceRef": {"Entity": entity}},
                        "Property": name,
                    }
                },
                "direction": direction,
            }
        ],
        "isDefaultSort": True,
    }


def sort_by_column(entity: str, prop: str, direction: str = "Ascending") -> dict:
    return {
        "sort": [
            {
                "field": {
                    "Column": {
                        "Expression": {"SourceRef": {"Entity": entity}},
                        "Property": prop,
                    }
                },
                "direction": direction,
            }
        ],
        "isDefaultSort": True,
    }


# ---------------------------------------------------------------------------
# Chrome padrao dos paineis
# ---------------------------------------------------------------------------

def panel(title: str | None = None, subtitle: str | None = None, framed: bool = True,
          centro: bool = False) -> dict:
    """Moldura padrao: fundo, borda, titulo e subtitulo com a mesma tipografia."""
    # Painel sem preenchimento: o relatorio inteiro fica sobre uma superficie
    # continua e a unica separacao e o fio do contorno. Fundo de painel numa cor
    # levemente diferente da pagina criava blocos flutuando sobre outro bloco.
    c: dict = {
        "background": obj(show=lit(False)),
        "border": obj(show=lit(framed), color=solid(BORDER), radius=lit(16)),
        "dropShadow": obj(show=lit(False)),
        "visualHeader": obj(show=lit(False)),
    }
    if title:
        c["title"] = obj(
            show=lit(True),
            text=lit(title),
            fontColor=solid(TXT),
            background=solid(BG_PAGE),
            fontFamily=lit(FONT_SEMI),
            fontSize=lit(14),
            alignment=lit("center" if centro else "left"),
            titleWrap=lit(False),
        )
        if on("subtitle"):
            c["subTitle"] = obj(
                show=lit(bool(subtitle)),
                text=lit(subtitle or ""),
                fontColor=solid(TXT_DIM),
                fontFamily=lit(FONT),
                fontSize=lit(11),
                alignment=lit("center" if centro else "left"),
                titleWrap=lit(False),
            )
    else:
        c["title"] = obj(show=lit(False))
    return c


def axis_cat(show_title: bool = False, font: int = 11) -> list:
    return obj(
        show=lit(True),
        labelColor=solid(TXT_MUT),
        fontFamily=lit(FONT),
        fontSize=lit(font),
        showAxisTitle=lit(show_title),
        gridlineShow=lit(False),
        concatenateLabels=lit(False),
    )


def axis_val(show: bool = True, font: int = 11, start: float | None = None) -> list:
    props = {
        "show": lit(show),
        "labelColor": solid(TXT_MUT),
        "fontFamily": lit(FONT),
        "fontSize": lit(font),
        "showAxisTitle": lit(False),
        "gridlineShow": lit(True),
        "gridlineColor": solid(GRID),
        "gridlineThickness": lit(1),
        "gridlineStyle": lit("solid"),
    }
    if start is not None:
        # Serie de volume truncada no zero exagera a variacao entre os meses.
        props["start"] = lit(start)
    return [{"properties": props}]


def legend(position: str = "TopLeft", show: bool = True) -> list:
    return obj(
        show=lit(show),
        labelColor=solid(TXT_MUT),
        fontFamily=lit(FONT),
        fontSize=lit(11),
        showTitle=lit(False),
        position=lit(position),
    )


def data_labels(show: bool = True, color: str = TXT_MUT, font: int = 11, unit: str | None = None) -> list:
    props = {
        "show": lit(show),
        "color": solid(color),
        "fontFamily": lit(FONT),
        "fontSize": lit(font),
    }
    if unit is not None:
        props["labelDisplayUnits"] = lit(unit)
    return [{"properties": props}]


def table_style(total: bool = False, font: int = 12) -> dict:
    """Formatacao comum de tabela/matriz: cabecalho discreto, grade horizontal fina."""
    return {
        "columnHeaders": obj(
            fontColor=solid(TXT_MUT),
            backColor=solid(BG_PAGE),
            fontFamily=lit(FONT_SEMI),
            fontSize=lit(11),
            outline=lit("BottomOnly"),
            wordWrap=lit(False),
            alignment=lit("left"),
        ),
        # Faixa alternada: em tabela de 10+ linhas o olho perde a linha no meio
        # do caminho. As duas cores sao proximas de proposito — a faixa serve
        # para guiar, nao para chamar atencao.
        "values": obj(
            fontColorPrimary=solid(TXT),
            backColorPrimary=solid(BG_PAGE),
            fontColorSecondary=solid(TXT),
            backColorSecondary=solid(BG_ALT),
            fontFamily=lit(FONT),
            fontSize=lit(font),
            outline=lit("None"),
            urlIcon=lit(False),
        ),
        "grid": obj(
            gridVertical=lit(False),
            gridHorizontal=lit(True),
            gridHorizontalColor=solid(GRID),
            gridHorizontalWeight=lit(1),
            outlineColor=solid(BORDER),
            outlineWeight=lit(1),
            rowPadding=lit(8),
            textSize=lit(font),
        ),
        "total": obj(
            totals=lit(total),
            fontColor=solid(TXT_MUT),
            backColor=solid(BG_CARD),
            fontFamily=lit(FONT_SEMI),
            fontSize=lit(font),
        ),
    }


# ---------------------------------------------------------------------------
# Construtores de visual
# ---------------------------------------------------------------------------

_seq = {"n": 0}


def vid(page: str, key: str, n: int) -> str:
    """Id estavel e unico por visual (o PBIR usa 20 caracteres hex)."""
    return hashlib.md5(f"{page}:{key}:{n}".encode()).hexdigest()[:20]


def visual(page: str, key: str, vtype: str, box, *,
           query: dict | None = None,
           objects: dict | None = None,
           container: dict | None = None,
           z: int | None = None) -> dict:
    x, y, w, h = box
    _seq["n"] += 1
    n = _seq["n"]
    z = n * 1000 if z is None else z
    v: dict = {"visualType": vtype}
    if query:
        v["query"] = query
    if objects:
        v["objects"] = objects
    v["visualContainerObjects"] = container or panel()
    v["drillFilterOtherVisuals"] = True
    name = vid(page, key, n)
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.11.0/schema.json",
        "name": name,
        "position": {
            "x": round(x, 2), "y": round(y, 2),
            "z": z, "height": round(h, 2), "width": round(w, 2),
            "tabOrder": z,
        },
        "visual": v,
    }


def q(state: dict, sort: dict | None = None) -> dict:
    d = {"queryState": {k: {"projections": v} for k, v in state.items()}}
    if sort and on("sort"):
        d["sortDefinition"] = sort
    return d


def textbox(page: str, key: str, box, runs: list, align: str = "left") -> dict:
    return visual(
        page, key, "textbox", box,
        objects={
            "general": obj(paragraphs=[{
                "textRuns": runs,
                "horizontalTextAlignment": align,
            }])
        },
        container={
            "background": obj(show=lit(False)),
            "border": obj(show=lit(False)),
            "dropShadow": obj(show=lit(False)),
            "visualHeader": obj(show=lit(False)),
            "title": obj(show=lit(False)),
        },
    )


def run(text: str, size: int, color: str, bold: bool = False, font: str = FONT) -> dict:
    style = {"fontSize": f"{size}px", "color": color, "fontFamily": font}
    if bold:
        style["fontWeight"] = "bold"
    return {"value": text, "textStyle": style}


def kpi(page: str, key: str, box, label: str, measure: str, color: str,
        note: str | None = None, color_measure: str | None = None) -> dict:
    """Cartao de KPI: rotulo no topo (titulo), numero grande, nota opcional."""
    value_color = solid_by_measure(color_measure) if color_measure else solid(color)
    return visual(
        page, key, "card", box,
        query=q({"Values": [measure_field(measure)]}),
        objects={
            "labels": obj(
                color=value_color,
                fontFamily=lit(FONT_SEMI),
                fontSize=lit(30),
                labelDisplayUnits=lit(0),
            ),
            "categoryLabels": obj(show=lit(False)),
            "wordWrap": obj(show=lit(False)),
        },
        container=panel(label, note, centro=True),
    )


def bar(page: str, key: str, box, title: str, subtitle: str,
        cat_entity: str, cat_prop: str, measure: str, *,
        vtype: str = "barChart", color: str | None = None,
        points: list | None = None, labels: bool = True,
        legend_pos: str | None = None, series: tuple | None = None,
        sort_measure: str | None = None, sort: dict | None = None) -> dict:
    state = {
        "Category": [column_field(cat_entity, cat_prop)],
        "Y": [measure_field(measure)],
    }
    if series:
        state["Series"] = [column_field(series[0], series[1])]
    objects = {
        "categoryAxis": axis_cat(),
        "valueAxis": axis_val(show=not labels),
        "legend": legend(legend_pos or "TopLeft", show=bool(series or legend_pos)),
        "labels": data_labels(labels),
    }
    if points:
        objects["dataPoint"] = points
    elif color:
        objects["dataPoint"] = obj(fill=solid(color))
    return visual(
        page, key, vtype, box,
        query=q(state, sort or sort_by_measure(sort_measure or measure)),
        objects=objects,
        container=panel(title, subtitle),
    )


def line(page: str, key: str, box, title: str, subtitle: str,
         cat_entity: str, cat_prop: str, measures: list[str],
         colors: list[str] | None = None, sort_col: tuple | None = None,
         start: float | None = 0) -> dict:
    colors = colors or SERIES
    points = []
    for m, c in zip(measures, colors):
        points.append({
            "properties": {"fill": solid(c)},
            "selector": {"metadata": f"{ENTITY_M}.{m}"},
        })
    return visual(
        page, key, "lineChart", box,
        query=q(
            {
                "Category": [column_field(cat_entity, cat_prop)],
                "Y": [measure_field(m) for m in measures],
            },
            sort_by_column(*(sort_col or (cat_entity, cat_prop))),
        ),
        objects={
            "categoryAxis": axis_cat(),
            "valueAxis": axis_val(start=start),
            "legend": legend("TopLeft", show=len(measures) > 1),
            "labels": data_labels(False),
            "lineStyles": obj(strokeWidth=lit(2), lineStyle=lit("solid"), showMarker=lit(False)),
            "dataPoint": points,
        },
        container=panel(title, subtitle),
    )


def table(page: str, key: str, box, title: str, subtitle: str,
          fields: list, *, totals: bool = False, sort: dict | None = None) -> dict:
    """`fields`: lista de tuplas ('col', entity, prop) ou ('mea', nome)."""
    projections = []
    for f in fields:
        projections.append(column_field(f[1], f[2], active=False) if f[0] == "col" else measure_field(f[1]))
    objects = table_style(total=totals)
    return visual(
        page, key, "tableEx", box,
        query=q({"Values": projections}, sort),
        objects=objects,
        container=panel(title, subtitle),
    )


def matrix(page: str, key: str, box, title: str, subtitle: str,
           rows_fields: list, cols_fields: list, values_fields: list) -> dict:
    objects = table_style(total=False)
    objects["rowHeaders"] = obj(
        fontColor=solid(TXT),
        backColor=solid(BG_PAGE),
        fontFamily=lit(FONT),
        fontSize=lit(12),
        steppedLayout=lit(True),
        outline=lit("None"),
    )
    objects["columnHeaders"] = obj(
        fontColor=solid(TXT_DIM),
        backColor=solid(BG_CARD),
        fontFamily=lit(FONT_SEMI),
        fontSize=lit(11),
        outline=lit("BottomOnly"),
        autoSizeColumnWidth=lit(True),
    )
    objects["subTotals"] = obj(rowSubtotals=lit(False), columnSubtotals=lit(False))
    return visual(
        page, key, "pivotTable", box,
        query=q({
            "Rows": [column_field(e, p, active=False) for e, p in rows_fields],
            "Columns": [column_field(e, p, active=False) for e, p in cols_fields],
            "Values": [measure_field(m) for m in values_fields],
        }),
        objects=objects,
        container=panel(title, subtitle),
    )


def donut(page: str, key: str, box, title: str, subtitle: str,
          cat_entity: str, cat_prop: str, measure: str,
          points: list | None = None) -> dict:
    objects = {
        "legend": legend("Right"),
        "labels": data_labels(False),
        "slices": obj(innerRadiusRatio=lit(68)),
    }
    if points:
        objects["dataPoint"] = points
    return visual(
        page, key, "donutChart", box,
        query=q({
            "Category": [column_field(cat_entity, cat_prop)],
            "Y": [measure_field(measure)],
        }, sort_by_measure(measure)),
        objects=objects,
        container=panel(title, subtitle),
    )


def scatter(page: str, key: str, box, title: str, subtitle: str,
            cat_entity: str, cat_prop: str, x: str, y: str, size: str,
            points: list | None = None) -> dict:
    objects = {
        "categoryAxis": axis_val(),
        "valueAxis": axis_val(),
        "legend": legend(show=False),
        "categoryLabels": obj(
            show=lit(True), color=solid(TXT_MUT),
            fontFamily=lit(FONT), fontSize=lit(9),
        ),
        "fillPoint": obj(show=lit(True)),
    }
    if points:
        objects["dataPoint"] = points
    return visual(
        page, key, "scatterChart", box,
        query=q({
            "Category": [column_field(cat_entity, cat_prop)],
            "X": [measure_field(x)],
            "Y": [measure_field(y)],
            "Size": [measure_field(size)],
        }),
        objects=objects,
        container=panel(title, subtitle),
    )


def chiclet(page: str, key: str, box, label: str, entity: str, prop: str,
            colunas: int) -> dict:
    """Chiclet Slicer — cada valor vira um bloco clicavel.

    O visual nativo nao expoe cor de estado: selecionado, sob o cursor e nao
    selecionado saem todos iguais, e o filtro ativo so aparecia por uma borda
    fina. O Chiclet expoe os tres, que e o que da acabamento a faixa de filtros.

    `colunas` = quantos blocos por linha. Definido pelo numero de valores do
    campo, para a faixa caber numa linha so.
    """
    return visual(
        page, key, "ChicletSlicer1448559807354", box,
        query=q({"Category": [column_field(entity, prop)]}),
        objects={
            "general": obj(
                orientation=lit("Horizontal"),
                columns=lit(colunas),
                rows=lit(0),
                multiselect=lit(True),
                showDisabled=lit("Inplace"),
                forcedSelection=lit(False),
            ),
            "header": obj(
                show=lit(True), title=lit(label),
                fontColor=solid(TXT_DIM), background=solid(BG_PAGE),
                textSize=lit(10), outline=lit("None"),
            ),
            "rows": obj(
                fontColor=solid(TXT), textSize=lit(10),
                selectedColor=solid(CHICLET_ON),
                hoverColor=solid("#2A3242"),
                unselectedColor=solid(CHICLET_OFF),
                disabledColor=solid(BG_PAGE),
                background=solid(BG_PAGE),
                transparency=lit(0),
                outlineColor=solid(BORDER), outlineWeight=lit(1),
                borderStyle=lit("Rounded"),
                padding=lit(4), height=lit(34),
            ),
        },
        container={
            "background": obj(show=lit(False)),
            "border": obj(show=lit(False)),
            "dropShadow": obj(show=lit(False)),
            "visualHeader": obj(show=lit(False)),
            "title": obj(show=lit(False)),
        },
    )


def slicer(page: str, key: str, box, label: str, entity: str, prop: str) -> dict:
    # Blocos, nao lista suspensa: e o acabamento do Chiclet Slicer feito com o
    # visual nativo (mode Basic + orientacao horizontal renderiza cada valor como
    # botao). Evita depender de visual de marketplace, que obrigaria quem abrisse
    # o arquivo a instalar o pacote antes de conseguir filtrar.
    objects: dict = {}
    if on("slicerobj"):
        objects = {
            "data": obj(mode=lit("Basic")),
            "general": obj(orientation=lit(1), outlineColor=solid(BORDER), outlineWeight=lit(1)),
            "selection": obj(singleSelect=lit(False), strictSingleSelect=lit(False),
                             selectAllCheckboxEnabled=lit(False)),
        }
    return visual(
        page, key, "slicer", box,
        query=q({"Values": [column_field(entity, prop)]}),
        objects={
            **objects,
            "header": obj(
                show=lit(True), text=lit(label), fontColor=solid(TXT_MUT),
                background=solid(BG_CARD), fontFamily=lit(FONT_SEMI),
                fontSize=lit(11), outline=lit("BottomOnly"),
            ),
            "items": obj(
                fontColor=solid(TXT), background=solid(BG_ALT),
                fontFamily=lit(FONT_SEMI), fontSize=lit(10),
                outline=lit("Frame"), outlineColor=solid("#2A3140"), outlineWeight=lit(1),
                padding=lit(6),
            ),
        },
        container={
            "background": obj(show=lit(True), color=solid(BG_CARD), transparency=lit(0)),
            "border": obj(show=lit(True), color=solid(BORDER), radius=lit(14)),
            "dropShadow": obj(show=lit(False)),
            "visualHeader": obj(show=lit(False)),
            "title": obj(show=lit(False)),
        },
    )


def navigator(page: str, box) -> dict:
    return visual(
        page, "nav", "pageNavigator", box,
        objects={
            "shape": obj(roundedCornerRadius=lit(8)),
            "text": [
                {"properties": {"fontColor": solid(TXT_MUT), "fontFamily": lit(FONT),
                                "fontSize": lit(10)},
                 "selector": {"id": "default"}},
                {"properties": {"fontColor": solid(BG_PAGE), "fontFamily": lit(FONT_SEMI),
                                "fontSize": lit(10)},
                 "selector": {"id": "selected"}},
            ],
            "fill": [
                {"properties": {"show": lit(True), "fillColor": solid(BG_CARD),
                                "transparency": lit(0)},
                 "selector": {"id": "default"}},
                {"properties": {"show": lit(True), "fillColor": solid(CYAN),
                                "transparency": lit(0)},
                 "selector": {"id": "selected"}},
            ],
            "outline": [
                {"properties": {"show": lit(True), "lineColor": solid(BORDER),
                                "weight": lit(1)},
                 "selector": {"id": "default"}},
            ],
        },
        container={
            "background": obj(show=lit(False)),
            "border": obj(show=lit(False)),
            "dropShadow": obj(show=lit(False)),
            "visualHeader": obj(show=lit(False)),
            "title": obj(show=lit(False)),
        },
    )


# ---------------------------------------------------------------------------
# Cabecalho comum a todas as paginas
# ---------------------------------------------------------------------------

def chrome(page: str, title: str, subtitle: str, filters: bool = True) -> list:
    v = [
        textbox(page, "titulo", (MARGIN, HEADER_Y, 820, HEADER_H), [
            run(title, 26, TXT, bold=True),
            run("\n" + subtitle, 13, TXT_DIM),
        ]),
    ]
    if on("nav"):
        v.append(navigator(page, (960, HEADER_Y + 4, PAGE_W - MARGIN - 960, 42)))
    if filters:
        # Largura proporcional a quantidade de valores: em bloco cada valor ocupa
        # espaco. Operadora tem 6, Regiao 5, Ano e Servico 2 cada.
        # "NAO IDENTIFICADA" e o rotulo mais longo: Operadora precisa de folga
        # para os 6 blocos caberem sem truncar o texto.
        widths = [(MARGIN, 168), (MARGIN + 184, 772), (MARGIN + 972, 468), (MARGIN + 1456, 160)]
        specs = [
            ("Ano", "dim_calendario", "Ano", 2),
            ("Operadora", "dim_operadora", "Operadora", 6),
            ("Região", "dim_uf", "Região", 5),
            ("Serviço", "fato_reclamacoes", "Serviço", 2),
        ]
        for (x, w), (label, ent, prop, cols) in zip(widths, specs):
            v.append(chiclet(page, f"slicer_{prop}", (x, FILTER_Y, w, FILTER_H),
                             label, ent, prop, cols))
        # Sem nota de fonte por pagina: a origem e a natureza do dado estao
    # declaradas na lede da primeira pagina e na pagina de metodologia. Repetir
    # em toda pagina so disputava espaco com os filtros.
    return v


# ---------------------------------------------------------------------------
# Paginas
# ---------------------------------------------------------------------------

def page_panorama() -> tuple[str, list]:
    p = "panorama"
    v = chrome(p, "Panorama Executivo",
               "8.000 reclamações, 71,9% respondidas e um mercado altamente concentrado — as três maiores operadoras respondem por 87% das queixas. Clique em qualquer elemento para filtrar a página.")

    # Faixa de KPIs
    kpi_y, kpi_h = BODY_Y, 112
    for (x, w), (key, label, measure, color, note, cm) in zip(cols(5), [
        ("k1", "TOTAL DE RECLAMAÇÕES", "Total Reclamações", CYAN, "no período filtrado", None),
        ("k2", "TAXA DE RESOLUÇÃO", "% Taxa Resolução", GREEN, "respondidas / total", None),
        ("k3", "EM ABERTO", "Em Aberto", AMBER, "sem resposta final", None),
        ("k4", "VARIAÇÃO MENSAL", "Var MoM %", CYAN, "vs. mês anterior", "Cor Var MoM"),
        ("k5", "CONCENTRAÇÃO (HHI)", "HHI", INDIGO, "índice Herfindahl-Hirschman", None),
    ]):
        v.append(kpi(p, key, (x, kpi_y, w, kpi_h), label, measure, color, note, cm))

    # Faixa de leitura automatica. Altura folgada porque o cartao divide o
    # espaco com o titulo e o subtitulo do painel.
    ins_y = kpi_y + kpi_h + GUTTER
    ins_h = 96
    v.append(visual(
        p, "insight", "card", (MARGIN, ins_y, CONTENT_W, ins_h),
        query=q({"Values": [measure_field("Insight Executivo")]}),
        objects={
            "labels": obj(color=solid(TXT), fontFamily=lit(FONT), fontSize=lit(14)),
            "categoryLabels": obj(show=lit(False)),
            "wordWrap": obj(show=lit(True)),
        },
        container=panel("LEITURA DO PERÍODO", "texto gerado por medida DAX, reage aos filtros"),
    ))

    top = ins_y + ins_h + GUTTER
    livre = PAGE_H - 36 - top - GUTTER
    h_topo = livre * 0.46
    h_base = livre * 0.54
    (xa, wa), (xb, wb) = cols(2)

    v.append(line(p, "serie", (MARGIN, top, 1218, h_topo),
                  "Evolução mensal do volume",
                  "reclamações abertas por mês e média móvel de 3 meses",
                  "dim_calendario", "Mês",
                  ["Total Reclamações", "Média Móvel 3M"],
                  [CYAN, INDIGO],
                  sort_col=("dim_calendario", "ano_mes_num"),
                  # Escala automatica: a serie oscila entre ~280 e ~390 e
                  # ancorar em zero achata a variacao ate ela sumir.
                  start=None))

    v.append(donut(p, "status", (MARGIN + 1218 + GUTTER, top, CONTENT_W - 1218 - GUTTER, h_topo),
                   "Composição por status",
                   "situação atual das reclamações do período",
                   "fato_reclamacoes", "Status", "Total Reclamações",
                   points=category_colors("fato_reclamacoes", "Status", STATUS)))

    v.append(bar(p, "operadoras", (xa, top + h_topo + GUTTER, wa, h_base),
                 "Volume por operadora",
                 "cor fixa por marca em todas as páginas",
                 "dim_operadora", "Operadora", "Total Reclamações",
                 points=category_colors("dim_operadora", "Operadora", BRAND)))

    v.append(bar(p, "motivos", (xb, top + h_topo + GUTTER, wb, h_base),
                 "Principais motivos",
                 "categoria da reclamação registrada na ANATEL",
                 "dim_tipo_reclamacao", "Categoria", "Total Reclamações",
                 color=INDIGO))

    return "Panorama Executivo", v


def page_operadoras() -> tuple[str, list]:
    p = "operadoras"
    v = chrome(p, "Operadoras",
               "SERCOMTEL é a menor operadora em volume e a que mais gera reclamação por assinante: 41,5 a cada 100 mil, contra 9,6 da CLARO. Ranking bruto mede tamanho de base, não qualidade de serviço.")

    # A tabela tem 6 linhas: dar metade da pagina a ela deixaria um vazio grande.
    r = split(3, 2.1)
    (xa, wa), (xb, wb) = cols(2)

    v.append(scatter(p, "disp", (xa, r[0][0], wa, r[0][1]),
                     "Volume × taxa de resolução",
                     "eixo X: reclamações · eixo Y: % resolvida · tamanho: reclamações por 100k assinantes",
                     "dim_operadora", "Operadora",
                     "Total Reclamações", "% Taxa Resolução", "Reclamações por 100k Assinantes",
                     points=category_colors("dim_operadora", "Operadora", BRAND)))

    v.append(bar(p, "por100k", (xb, r[0][0], wb, r[0][1]),
                 "Reclamações por 100k assinantes",
                 "comparação justa entre operadoras de portes diferentes",
                 "dim_operadora", "Operadora", "Reclamações por 100k Assinantes",
                 points=category_colors("dim_operadora", "Operadora", BRAND)))

    v.append(table(p, "painel", (MARGIN, r[1][0], CONTENT_W, r[1][1]),
                   "Painel por operadora",
                   "clique em uma linha para filtrar os demais visuais",
                   [
                       ("col", "dim_operadora", "Operadora"),
                       ("col", "dim_operadora", "Grupo econômico"),
                       ("mea", "Total Reclamações"),
                       ("mea", "Market Share Operadora %"),
                       ("mea", "% Taxa Resolução"),
                       ("mea", "Em Aberto"),
                       ("mea", "Reclamações por 100k Assinantes"),
                       ("mea", "Score Risco Operadora"),
                       ("mea", "Rating Risco"),
                   ],
                   sort=sort_by_measure("Total Reclamações")))
    return "Operadoras", v


def page_motivos() -> tuple[str, list]:
    p = "motivos"
    v = chrome(p, "Motivos",
               "Cobrança e velocidade concentram 44% de tudo. O mix muda pouco de uma marca para outra, o que aponta para causa estrutural do setor e não para falha isolada de uma operadora.")

    r = split(1, 1)
    (xa, wa), (xb, wb) = cols(2)

    v.append(bar(p, "cat", (xa, r[0][0], wa, r[0][1]),
                 "Reclamações por categoria",
                 "categoria registrada no protocolo ANATEL",
                 "dim_tipo_reclamacao", "Categoria", "Total Reclamações",
                 color=INDIGO))

    v.append(bar(p, "mix", (xb, r[0][0], wb, r[0][1]),
                 "Mix de motivos por operadora",
                 "participação de cada categoria dentro da operadora (100%)",
                 "dim_operadora", "Operadora", "Total Reclamações",
                 vtype="hundredPercentStackedBarChart",
                 series=("dim_tipo_reclamacao", "Categoria"),
                 labels=False, legend_pos="Bottom"))

    v.append(matrix(p, "heat", (MARGIN, r[1][0], CONTENT_W, r[1][1]),
                    "Categoria × operadora",
                    "expanda a categoria para ver a subcategoria",
                    [("dim_tipo_reclamacao", "Categoria"), ("dim_tipo_reclamacao", "Subcategoria")],
                    [("dim_operadora", "Operadora")],
                    ["Total Reclamações"]))
    return "Motivos", v


def page_regioes() -> tuple[str, list]:
    p = "regioes"
    v = chrome(p, "Regiões",
               "O Sudeste responde por 44% das reclamações — proporcional ao seu tamanho. Sem denominador populacional, ranking de UF mede população tanto quanto qualidade de serviço.")

    r = rows(2)
    v.append(bar(p, "regiao", (MARGIN, r[0][0], 608, r[0][1]),
                 "Por região",
                 "volume absoluto de reclamações",
                 "dim_uf", "Região", "Total Reclamações",
                 color=CYAN))

    v.append(bar(p, "uf", (MARGIN + 608 + GUTTER, r[0][0], CONTENT_W - 608 - GUTTER, r[0][1]),
                 "Por unidade federativa",
                 "todas as UFs com registro no período, ordenadas por volume",
                 "dim_uf", "UF", "Total Reclamações",
                 vtype="clusteredColumnChart", color=CYAN, labels=False))

    (xa, wa), (xb, wb) = cols(2)
    v.append(bar(p, "statusreg", (xa, r[1][0], wa, r[1][1]),
                 "Situação por região",
                 "participação de cada status dentro da região (100%)",
                 "dim_uf", "Região", "Total Reclamações",
                 vtype="hundredPercentStackedBarChart",
                 series=("fato_reclamacoes", "Status"),
                 points=category_colors("fato_reclamacoes", "Status", STATUS),
                 labels=False, legend_pos="Bottom"))

    v.append(table(p, "detalheuf", (xb, r[1][0], wb, r[1][1]),
                   "Detalhe por UF",
                   "participação e qualidade de atendimento por estado",
                   [
                       ("col", "dim_uf", "UF"),
                       ("col", "dim_uf", "Região"),
                       ("mea", "Total Reclamações"),
                       ("mea", "Share UF %"),
                       ("mea", "% Taxa Resolução"),
                   ],
                   sort=sort_by_measure("Total Reclamações")))
    return "Regiões", v


def page_risco() -> tuple[str, list]:
    p = "risco"
    v = chrome(p, "Risco Regulatório",
               "CLARO concentra o maior risco: lidera o volume, fica na média em resolução e tem a tendência mensal mais inclinada para cima. Score é composição ponderada, não previsão.")

    r = split(2, 3)
    left_w = 1218
    right_x = MARGIN + left_w + GUTTER
    right_w = CONTENT_W - left_w - GUTTER

    v.append(table(p, "risco", (MARGIN, r[0][0], left_w, r[0][1]),
                   "Índice de risco por operadora",
                   "score = 40% volume + 35% (1 − taxa de resolução) + 25% volume normalizado",
                   [
                       ("col", "dim_operadora", "Operadora"),
                       ("mea", "Total Reclamações"),
                       ("mea", "% Taxa Resolução"),
                       ("mea", "Reclamações por 100k Assinantes"),
                       ("mea", "Score Risco Operadora"),
                       ("mea", "Rating Risco"),
                   ],
                   sort=sort_by_measure("Score Risco Operadora")))

    kh = (r[0][1] - 2 * 12) / 3
    for i, (key, label, measure, color, note) in enumerate([
        ("hhi", "HHI DO MERCADO", "HHI", INDIGO, "soma dos quadrados dos market shares"),
        ("top3", "CONCENTRAÇÃO TOP 3", "Concentração Top 3 %", AMBER, "share das 3 maiores"),
        ("cob", "COBERTURA DE IDENTIFICAÇÃO", "Cobertura de Identificação", GREEN, "registros com operadora identificada"),
    ]):
        v.append(kpi(p, key, (right_x, r[0][0] + i * (kh + 12), right_w, kh),
                     label, measure, color, note))

    # Volume e z-score em ordens de grandeza incompativeis (~350 x ~2): num
    # unico eixo a segunda serie vira uma reta colada no zero. Como a serie de
    # volume ja esta no Panorama, aqui fica so o desvio, que e o assunto da
    # pagina — barra acima de zero e mes acima da media.
    v.append(bar(p, "anomalia", (MARGIN, r[1][0], left_w, r[1][1]),
                 "Desvio do volume mensal",
                 "z-score de cada mês contra a média do período · acima de +2 ou abaixo de −2 é anomalia",
                 "dim_calendario", "Mês", "Z-Score Volume Mensal",
                 vtype="clusteredColumnChart", color=AMBER, labels=False,
                 sort=sort_by_column("dim_calendario", "ano_mes_num")))

    v.append(bar(p, "tend", (right_x, r[1][0], right_w, r[1][1]),
                 "Tendência estrutural",
                 "inclinação da reta de regressão mensal · positivo = piorando",
                 "dim_operadora", "Operadora", "Tendência Linear Mensal",
                 points=category_colors("dim_operadora", "Operadora", BRAND), labels=True))
    return "Risco Regulatório", v


def page_metodologia() -> tuple[str, list]:
    p = "metodo"
    v = chrome(p, "Metodologia & Modelo",
               "O que é observado, o que é sintético e onde este painel não deve ser usado como fato de mercado.",
               filters=False)

    # Alturas medidas pelo conteudo, nao pela divisao da pagina: com split(3,4)
    # sobrava quase metade de cada painel vazia. O que resta de folga vira
    # margem simetrica em cima e embaixo, para o bloco ficar centrado.
    H_KPI = 132
    r = split(3, 2)
    c3 = cols(3)

    blocos = [
        ("Fonte e escopo", [
            ("Origem", "ANATEL — Reclamações e denúncias de consumidores (dados abertos), "
                       "serviços SCM (banda larga fixa) e SMP (telefonia móvel)."),
            ("Período", "Janeiro/2022 a dezembro/2023 · 8.000 registros · 730 dias de calendário."),
            ("Natureza", "Base sintética gerada a partir das proporções reais publicadas pela "
                         "ANATEL. Serve para demonstrar modelagem e análise, não para citar "
                         "números como fato de mercado."),
            ("Reprodutibilidade", "data_prep/prepare_data.py reconstrói o star schema a partir "
                                  "de data/raw. O caminho dos CSVs é o parâmetro PastaDados."),
        ]),
        ("Modelagem", [
            ("Esquema", "Star schema: 1 fato (fato_reclamacoes) e 4 dimensões "
                        "(operadora, UF, tipo de reclamação, calendário)."),
            ("Grão", "Uma linha por reclamação registrada. A coluna qtd = 1 mantém o fato "
                     "aditivo e permite trocar a agregação sem reescrever medidas."),
            ("Relações", "Um-para-muitos, filtro simples, da dimensão para o fato. Sem "
                         "bidirecional: ambiguidade de filtro é evitada por desenho."),
            ("Calendário", "dim_calendario é contínua e marcada como tabela de datas, "
                           "requisito das funções de inteligência temporal."),
        ]),
        ("Camada de medidas", [
            ("Organização", "Todas as medidas vivem na tabela _Medidas, agrupadas em pastas "
                            "numeradas por domínio (volume, resolução, temporal, mercado, risco)."),
            ("Normalização", "Reclamações por 100k assinantes corrige o viés de porte: "
                             "comparar CLARO e SERCOMTEL por volume bruto não diz nada."),
            ("Concentração", "HHI = soma dos quadrados dos market shares. Faixas: < 1.500 "
                             "competitivo, até 2.500 concentrado, acima disso altamente concentrado."),
            ("Score de risco", "Composição ponderada de volume (40%), falha de resolução (35%) "
                               "e volume normalizado (25%), reescalada de 0 a 1."),
        ]),
    ]

    for (x, w), (titulo, itens) in zip(c3, blocos):
        runs = []
        for i, (rot, txt) in enumerate(itens):
            if i:
                runs.append(run("\n\n", 11, TXT_DIM))
            runs.append(run(rot + "\n", 11, CYAN, bold=True))
            runs.append(run(txt, 11, TXT_MUT))
        v.append(visual(
            p, f"bloco_{titulo}", "textbox", (x, r[0][0], w, r[0][1]),
            objects={"general": obj(paragraphs=[{"textRuns": runs, "horizontalTextAlignment": "left"}])},
            container=panel(titulo.upper(), None),
        ))

    # Qualidade do dado — numeros reais, nao texto
    kw = cols(4)
    for (x, w), (key, label, measure, color, note) in zip(kw, [
        ("q1", "REGISTROS NO FATO", "Total Reclamações Geral", CYAN, "linhas carregadas"),
        ("q2", "COBERTURA DE IDENTIFICAÇÃO", "Cobertura de Identificação", GREEN, "com operadora reconhecida"),
        ("q3", "SEM OPERADORA", "Reclamações Não Identificadas", AMBER, "mantidos no fato, fora da comparação"),
        ("q4", "% SEM OPERADORA", "% Não Identificado", AMBER, "impacto no total"),
    ]):
        v.append(kpi(p, key, (x, r[1][0], w, H_KPI), label, measure, color, note))

    limites = [
        ("Por que os registros sem operadora ficam na base",
         "Descartá-los deixaria o total divergente da origem. Eles entram no volume "
         "consolidado e ficam com base de assinantes em branco, o que anula a taxa por "
         "100k em vez de produzir um número falso."),
        ("O que este relatório não responde",
         "Não há dado de causa raiz técnica, de custo de atendimento nem de tempo de "
         "resolução por protocolo. Taxa de resolução aqui é o percentual com status "
         "Respondida, não uma medida de satisfação do consumidor."),
        ("Stack",
         "Python (pandas) para preparação · Power BI Desktop com modelo tabular e DAX · "
         "tema e camada visual versionados em JSON (theme/ e tools/build_report.py)."),
    ]
    runs = []
    for i, (rot, txt) in enumerate(limites):
        if i:
            runs.append(run("\n\n", 11, TXT_DIM))
        runs.append(run(rot + "\n", 11, AMBER, bold=True))
        runs.append(run(txt, 11, TXT_MUT))
    v.append(visual(
        p, "limites", "textbox",
        (MARGIN, r[1][0] + H_KPI + GUTTER, CONTENT_W, r[1][1] - H_KPI - GUTTER),
        objects={"general": obj(paragraphs=[{"textRuns": runs, "horizontalTextAlignment": "left"}])},
        container=panel("LEITURA CRÍTICA E LIMITES", None),
    ))
    return "Metodologia & Modelo", v


PAGES = [page_panorama, page_operadoras, page_motivos, page_regioes, page_risco, page_metodologia]


# ---------------------------------------------------------------------------
# Tema
# ---------------------------------------------------------------------------

def build_theme() -> dict:
    return {
        "name": "FiberNet Dark",
        "dataColors": SERIES + ["#5AC79A", "#DD7A72", "#7FA8C9", "#C2C9D6"],
        "foreground": TXT,
        "foregroundNeutralSecondary": TXT_MUT,
        "foregroundNeutralTertiary": TXT_DIM,
        "background": BG_PAGE,
        "backgroundLight": BG_CARD,
        "backgroundNeutral": BORDER,
        "tableAccent": CYAN,
        "good": GREEN,
        "neutral": AMBER,
        "bad": RED,
        "maximum": CYAN,
        "center": "#2F5F72",
        "minimum": BG_CARD,
        "null": SLATE,
        "hyperlink": CYAN,
        "textClasses": {
            "title": {"fontFace": FONT_SEMI, "fontSize": 11, "color": TXT},
            "header": {"fontFace": FONT_SEMI, "fontSize": 10, "color": TXT_MUT},
            "label": {"fontFace": FONT, "fontSize": 10, "color": TXT_MUT},
            "callout": {"fontFace": FONT_SEMI, "fontSize": 30, "color": TXT},
        },
        "visualStyles": {
            "*": {
                "*": {
                    "background": [{"show": True, "color": {"solid": {"color": BG_CARD}}, "transparency": 0}],
                    "border": [{"show": True, "color": {"solid": {"color": BORDER}}, "radius": 12}],
                    "dropShadow": [{"show": False}],
                    "visualHeader": [{"show": False}],
                    "title": [{
                        "show": True,
                        "fontColor": {"solid": {"color": TXT}},
                        "background": {"solid": {"color": BG_CARD}},
                        "fontFamily": FONT_SEMI,
                        "fontSize": 11,
                        "alignment": "left",
                    }],
                    "labels": [{"color": {"solid": {"color": TXT_MUT}}, "fontSize": 9, "fontFamily": FONT}],
                    "categoryAxis": [{
                        "show": True,
                        "labelColor": {"solid": {"color": TXT_MUT}},
                        "fontSize": 9,
                        "showAxisTitle": False,
                        "gridlineShow": False,
                    }],
                    "valueAxis": [{
                        "show": True,
                        "labelColor": {"solid": {"color": TXT_MUT}},
                        "fontSize": 9,
                        "showAxisTitle": False,
                        "gridlineColor": {"solid": {"color": GRID}},
                        "gridlineThickness": 1,
                        "gridlineStyle": "solid",
                    }],
                    "legend": [{
                        "show": True,
                        "labelColor": {"solid": {"color": TXT_MUT}},
                        "fontSize": 9,
                        "showTitle": False,
                        "position": "TopLeft",
                    }],
                    "outline": [{"show": False}],
                }
            },
            "page": {
                "*": {
                    "background": [{"color": {"solid": {"color": BG_PAGE}}, "transparency": 0}],
                    "outspace": [{"color": {"solid": {"color": BG_OUT}}, "transparency": 0}],
                }
            },
            "card": {
                "*": {
                    "labels": [{"color": {"solid": {"color": TXT}}, "fontSize": 30, "fontFamily": FONT_SEMI}],
                    "categoryLabels": [{"show": False}],
                }
            },
            "slicer": {
                "*": {
                    "header": [{"show": True, "fontColor": {"solid": {"color": TXT_DIM}},
                                "background": {"solid": {"color": BG_CARD}}, "fontSize": 9,
                                "fontFamily": FONT_SEMI, "outline": "None"}],
                    "items": [{"fontColor": {"solid": {"color": TXT}},
                               "background": {"solid": {"color": BG_CARD}}, "fontSize": 10,
                               "outline": "None"}],
                }
            },
            "tableEx": {
                "*": {
                    "grid": [{"gridVertical": False, "gridHorizontal": True,
                              "gridHorizontalColor": {"solid": {"color": GRID}},
                              "outlineColor": {"solid": {"color": BORDER}}, "rowPadding": 6}],
                    "columnHeaders": [{"fontColor": {"solid": {"color": TXT_DIM}},
                                       "backColor": {"solid": {"color": BG_CARD}},
                                       "fontSize": 9, "fontFamily": FONT_SEMI}],
                    "values": [{"fontColorPrimary": {"solid": {"color": TXT}},
                                "backColorPrimary": {"solid": {"color": BG_CARD}},
                                "fontColorSecondary": {"solid": {"color": TXT}},
                                "backColorSecondary": {"solid": {"color": BG_CARD}},
                                "fontSize": 10}],
                }
            },
            "pivotTable": {
                "*": {
                    "grid": [{"gridVertical": False, "gridHorizontal": True,
                              "gridHorizontalColor": {"solid": {"color": GRID}},
                              "outlineColor": {"solid": {"color": BORDER}}, "rowPadding": 6}],
                    "columnHeaders": [{"fontColor": {"solid": {"color": TXT_DIM}},
                                       "backColor": {"solid": {"color": BG_CARD}},
                                       "fontSize": 9, "fontFamily": FONT_SEMI}],
                }
            },
        },
    }


# ---------------------------------------------------------------------------
# Montagem do pacote
# ---------------------------------------------------------------------------

def page_json(name: str, display: str) -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
        "name": name,
        "displayName": display,
        "displayOption": "FitToPage",
        "height": PAGE_H,
        "width": PAGE_W,
        "objects": {
            "background": obj(color=solid(BG_PAGE), transparency=lit(0)),
            "outspace": obj(color=solid(BG_OUT), transparency=lit(0)),
            "displayArea": obj(verticalAlignment=lit("Top")),
        },
    }


def report_json() -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {
                "name": "CY26SU04",
                "reportVersionAtImport": {"visual": "2.8.0", "report": "3.2.0", "page": "2.3.1"},
                "type": "SharedResources",
            },
            "customTheme": {
                "name": "fibernet_dark",
                "reportVersionAtImport": {"visual": "2.11.0", "report": "3.4.0", "page": "2.3.1"},
                "type": "RegisteredResources",
            },
        },
        "objects": {
            "section": obj(verticalAlignment=lit("Top")),
            "outspacePane": obj(expanded=lit(False)),
        },
        # Sem esta declaracao o Power BI ignora o pacote e o visual nao carrega.
        "publicCustomVisuals": ["ChicletSlicer1448559807354"],
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY26SU04", "path": "BaseThemes/CY26SU04.json", "type": "BaseTheme"}]},
            # `path` e o nome do arquivo dentro de RegisteredResources, com
            # extensao. Sem o `.json` o Desktop nao resolve o recurso e cai
            # silenciosamente no tema base — foi o que fez a paleta customizada
            # nao valer para donut e barras empilhadas.
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "fibernet_dark", "path": "fibernet_dark.json", "type": "BaseTheme"}]},
        ],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "AllowSummarized",
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
            "useDefaultAggregateDisplayName": True,
        },
    }


def build(src: Path, dst: Path) -> None:
    theme = build_theme()
    THEME_FILE.parent.mkdir(parents=True, exist_ok=True)
    THEME_FILE.write_text(json.dumps(theme, indent=2, ensure_ascii=False), encoding="utf-8")

    built = []
    for i, fn in enumerate(PAGES):
        display, visuals = fn()
        pname = hashlib.md5(f"page{i}:{display}".encode()).hexdigest()[:20]
        built.append((pname, display, visuals))

    files: dict[str, str] = {
        "Report/definition/version.json": json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        }, ensure_ascii=False),
        "Report/definition/report.json": json.dumps(report_json(), ensure_ascii=False),
        "Report/definition/pages/pages.json": json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
            "pageOrder": [p[0] for p in built],
            "activePageName": built[0][0],
        }, ensure_ascii=False),
        "Report/StaticResources/RegisteredResources/fibernet_dark.json":
            json.dumps(theme, ensure_ascii=False),
    }
    for pname, display, visuals in built:
        files[f"Report/definition/pages/{pname}/page.json"] = json.dumps(
            page_json(pname, display), ensure_ascii=False)
        for vis in visuals:
            files[f"Report/definition/pages/{pname}/visuals/{vis['name']}/visual.json"] = \
                json.dumps(vis, ensure_ascii=False)

    # Tudo que e camada de relatorio some; modelo e metadados sao preservados.
    #
    # SecurityBindings tambem sai: e um blob DPAPI que assina as partes do
    # pacote. Reescrever Report/definition invalida a assinatura e o Desktop
    # recusa o arquivo inteiro com "esse arquivo esta corrompido". Sem a parte,
    # ele abre normalmente e regrava a assinatura no primeiro save.
    # BuiltInThemes tambem sai: ao salvar, o Desktop despeja o catalogo de temas
    # embutidos dele no arquivo (Bloom.json sozinho tem 3 MB). Nada no relatorio
    # aponta para eles e o Desktop os recria sozinho quando precisa.
    # Report/CustomVisuals NAO entra na lista: o pacote do Chiclet Slicer vive
    # ali e precisa continuar no arquivo, senao o visual some do relatorio.
    drop_prefixes = ("Report/definition/",
                     "Report/StaticResources/RegisteredResources/",
                     "Report/StaticResources/SharedResources/BuiltInThemes/")
    drop_exact = {"Report/Layout", "SecurityBindings"}

    with zipfile.ZipFile(src) as zin:
        keep = [i for i in zin.infolist()
                if not i.filename.startswith(drop_prefixes) and i.filename not in drop_exact]
        payload = {i.filename: zin.read(i.filename) for i in keep}

    content_types = payload.pop("[Content_Types].xml", None)
    if content_types:
        # A parte foi removida acima; deixar o Override orfao quebra o pacote.
        xml = content_types.decode("utf-8-sig")
        xml = xml.replace('<Override PartName="/SecurityBindings" ContentType="" />', "")
        content_types = "﻿".encode() + xml.encode("utf-8")

    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
        for fname, data in payload.items():
            zout.writestr(fname, data)
        for fname, text in files.items():
            zout.writestr(fname, text.encode("utf-8"))
        zout.writestr("[Content_Types].xml", content_types or _content_types())

    n_vis = sum(len(p[2]) for p in built)
    print(f"OK  {dst.name}  ·  {len(built)} páginas  ·  {n_vis} visuais")
    for pname, display, visuals in built:
        print(f"    {display:<26} {len(visuals):>2} visuais")


def _content_types() -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="json" ContentType="" />'
        '<Default Extension="xml" ContentType="" />'
        '<Override PartName="/Version" ContentType="" />'
        '<Override PartName="/Report/Layout" ContentType="" />'
        '<Override PartName="/Settings" ContentType="" />'
        '<Override PartName="/Metadata" ContentType="" />'
        '<Override PartName="/DataModel" ContentType="" />'
        '<Override PartName="/DiagramLayout" ContentType="" />'
        "</Types>"
    ).encode("utf-8")


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PBIX
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else source
    if target == source:
        backup = source.with_suffix(".prebuild.pbix")
        shutil.copy2(source, backup)
        print(f"backup: {backup.name}")
    build(source, target)
