"""
Olist - MODO RESPALDO (offline) sin Amazon Bedrock.

Se usa solo cuando settings.json tiene "llm_mode": "offline"
(cuenta AWS con cuotas de Bedrock en 0; casos AWS 179397137900209
y 179398855200550).

Sustituye UNICAMENTE las dos piezas que dependen del LLM:
  1. Generacion de SQL  -> reglas deterministas sobre la capa semantica.
  2. Redaccion del insight -> plantilla con cifras del resultado de Athena.

Todo lo demas (resolver semantico, SQL Guard, Athena, golden queries,
visualizacion y Streamlit) es el codigo real del proyecto.

Alcance: entiende solo metricas, dimensiones y filtros declarados en la
capa semantica. No interpreta preguntas libres como lo haria un LLM.
"""

import re

from src.sql_generator import _drop_contained, _find_term, normalize_text


OFFLINE_NOTICE = (
    "MODO RESPALDO: SQL generado por reglas de la capa semantica "
    "(Amazon Bedrock no disponible en la cuenta)."
)


class OfflineLLM:
    """Placeholder que ocupa el lugar del cliente de Bedrock."""

    offline = True
    model_id = "offline-rule-based"

    def ask(self, *args, **kwargs):
        raise RuntimeError(OFFLINE_NOTICE + " Esta funcion requiere Bedrock.")

    def ask_json(self, *args, **kwargs):
        raise RuntimeError(OFFLINE_NOTICE + " Esta funcion requiere Bedrock.")


def is_offline(client):
    return bool(getattr(client, "offline", False))


# ------------------------------------------------------------------
# Deteccion de dimension (GROUP BY)
# ------------------------------------------------------------------

TIME_DIMENSIONS = {"anio", "anio_mes", "mes", "trimestre"}

EXTRA_DIMENSION_TERMS = {
    "anio": ["por ano", "por anio", "anual", "cada ano", "por year"],
    "mes": ["por mes", "mensual", "cada mes", "evolucion mensual", "mes a mes"],
}


def _detect_dimension(normalized_question, semantic_layer):
    """
    Devuelve la columna de la dimension pedida, o None.
    Solo agrupa si la dimension aparece tras 'por', 'segun', 'cada',
    'entre' o en un ranking ('que region', 'cual categoria').
    """
    candidates = []

    for key, dim in semantic_layer.get("dimensions", {}).items():
        column = dim["column"]
        terms = [*dim.get("synonyms", []), dim.get("label", "")]
        terms += EXTRA_DIMENSION_TERMS.get(key, [])

        for term in terms:
            t = normalize_text(term)
            if not t:
                continue

            explicit = t.startswith(("por ", "cada ")) or t in ("anual", "mensual")
            if explicit:
                span = _find_term(normalized_question, t)
            else:
                span = None
                for prefix in ("por ", "segun ", "cada ", "entre ", "que ", "cual ", "cuales ",
                               "peor ", "peores ", "mejor ", "mejores "):
                    span = _find_term(normalized_question, prefix + t)
                    if span:
                        break
                if not span and t.startswith("evolucion"):
                    span = _find_term(normalized_question, t)

            if span:
                candidates.append({"column": column, "span": span})

    if not candidates:
        return None

    candidates = _drop_contained(candidates)
    best = max(candidates, key=lambda c: c["span"][1] - c["span"][0])
    return best["column"]


# ------------------------------------------------------------------
# Deteccion de filtros (WHERE)
# ------------------------------------------------------------------

UF_CODES = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
}

REGIONES = {
    "norte": "Norte",
    "nordeste": "Nordeste",
    "centro oeste": "Centro-Oeste",
    "centro-oeste": "Centro-Oeste",
    "sudeste": "Sudeste",
    "sur": "Sur",
}

VALUE_FILTERS = [
    # (frase normalizada, columna, valor)
    ("2 o mas vendedores", "grupo_vendedores", "2 o mas"),
    ("dos o mas vendedores", "grupo_vendedores", "2 o mas"),
    ("varios vendedores", "grupo_vendedores", "2 o mas"),
    ("un vendedor", "grupo_vendedores", "1"),
    ("un solo vendedor", "grupo_vendedores", "1"),
    ("1 vendedor", "grupo_vendedores", "1"),
    ("entregados tarde", "cumplimiento_plazo", "Tarde"),
    ("con entrega tarde", "cumplimiento_plazo", "Tarde"),
    ("entregados a tiempo", "cumplimiento_plazo", "A tiempo"),
    ("con entrega a tiempo", "cumplimiento_plazo", "A tiempo"),
    ("datos reales", "periodo_datos", "Real 2016-2018"),
    ("datos simulados", "periodo_datos", "Simulado 2019-2025"),
    ("varias categorias", "tipo_pedido_categoria", "Varias categorias"),
    ("una categoria", "tipo_pedido_categoria", "Una categoria"),
]


def _sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def _detect_filters(question, normalized_question, group_column):
    filters = []

    # Anos 2016-2025 (columna anio)
    years = sorted({int(y) for y in re.findall(r"\b(201[6-9]|202[0-5])\b", question)})
    if len(years) == 1:
        filters.append(f"anio = {years[0]}")
    elif len(years) > 1:
        if re.search(r"\b(entre|desde)\b", normalized_question) and len(years) == 2:
            filters.append(f"anio BETWEEN {years[0]} AND {years[1]}")
        else:
            filters.append("anio IN (" + ", ".join(str(y) for y in years) + ")")

    # Estado (UF) en mayusculas: "en SP", "de RJ"
    ufs = sorted({u for u in re.findall(r"\b([A-Z]{2})\b", question) if u in UF_CODES})
    if ufs and group_column != "estado_cliente":
        if len(ufs) == 1:
            filters.append(f"estado_cliente = {_sql_literal(ufs[0])}")
        else:
            filters.append(
                "estado_cliente IN (" + ", ".join(_sql_literal(u) for u in ufs) + ")"
            )

    # Region: "region sudeste", "en el nordeste"
    if group_column != "region_cliente":
        for term, value in REGIONES.items():
            if _find_term(normalized_question, "region " + term) or _find_term(
                normalized_question, "en el " + term
            ):
                filters.append(f"region_cliente = {_sql_literal(value)}")
                break

    # Valores conocidos de dimensiones
    for phrase, column, value in VALUE_FILTERS:
        if column == group_column:
            continue
        if _find_term(normalized_question, phrase):
            clause = f"{column} = {_sql_literal(value)}"
            if not any(f.startswith(column + " ") for f in filters):
                filters.append(clause)

    return filters


# ------------------------------------------------------------------
# Orden (rankings)
# ------------------------------------------------------------------

DESC_WORDS = ["peor", "peores", "mas", "mayor", "mayores", "mas alto", "mas alta",
              "maximo", "top", "mas problematica", "mas problematico"]
ASC_WORDS = ["mejor", "mejores", "menos", "menor", "menores", "mas bajo",
             "mas baja", "minimo"]

# Metricas donde "mas alto = peor"
HIGHER_IS_WORSE = {"kpi1_pct_pedidos_bajos", "kpi2_pct_resenas_bajas",
                   "kpi5_tasa_entrega_tardia"}


def _detect_order(normalized_question, metric_name, group_column):
    if group_column in TIME_DIMENSIONS:
        return f"ORDER BY {group_column} ASC"

    has_desc = any(_find_term(normalized_question, w) for w in DESC_WORDS)
    has_asc = any(_find_term(normalized_question, w) for w in ASC_WORDS)

    asks_best = any(_find_term(normalized_question, w) for w in ("mejor", "mejores"))
    asks_worst = any(_find_term(normalized_question, w) for w in ("peor", "peores"))

    if metric_name in HIGHER_IS_WORSE:
        if asks_best:
            return "ORDER BY 2 ASC"
        if asks_worst:
            return "ORDER BY 2 DESC"
    else:
        if asks_best:
            return "ORDER BY 2 DESC"
        if asks_worst:
            return "ORDER BY 2 ASC"

    if has_asc and not has_desc:
        return "ORDER BY 2 ASC"
    return "ORDER BY 2 DESC"


# ------------------------------------------------------------------
# Generador principal
# ------------------------------------------------------------------

def generate_sql_offline(question, semantic_layer, resolved):
    allowed_view = semantic_layer["allowed_view"]
    normalized_question = normalize_text(question)

    if not resolved:
        return {
            "status": "clarification",
            "interpretation": "Modo respaldo: no se reconocio una metrica gobernada.",
            "metric_used": None,
            "semantic_rule_applied": OFFLINE_NOTICE,
            "sql": None,
            "clarification_question": (
                "En modo respaldo solo se entienden las metricas de la capa "
                "semantica. Prueba con: porcentaje de pedidos insatisfechos, "
                "porcentaje de resenas bajas, calificacion promedio, tasa de "
                "entrega tardia, flete sobre precio, ventas o pedidos."
            ),
        }

    metric_name = resolved["metric_name"]
    metric = resolved["metric"]
    metric_sql = metric["sql"]

    group_column = _detect_dimension(normalized_question, semantic_layer)
    filters = _detect_filters(question, normalized_question, group_column)

    lines = ["SELECT"]
    if group_column:
        lines.append(f"    {group_column},")
    lines.append(f"    {metric_sql} AS {metric_name}")
    lines.append(f"FROM {allowed_view}")

    if filters:
        lines.append("WHERE " + "\n  AND ".join(filters))

    if group_column:
        lines.append(f"GROUP BY {group_column}")
        lines.append(_detect_order(normalized_question, metric_name, group_column))
        lines.append("LIMIT 100")

    sql = "\n".join(lines)

    interpretation = f'"{resolved["matched_term"]}" → {metric.get("label", metric_name)}'
    if group_column:
        interpretation += f" | por {group_column}"
    if filters:
        interpretation += " | filtros: " + "; ".join(filters)

    return {
        "status": "ok",
        "interpretation": interpretation,
        "metric_used": metric_name,
        "semantic_rule_applied": (
            f"Semantic Layer resolved {resolved['matched_term']} to "
            f"{metric_name} ({resolved['source']}). {OFFLINE_NOTICE}"
        ),
        "sql": sql,
        "clarification_question": None,
        "mode": "offline",
    }


# ------------------------------------------------------------------
# Insight por plantilla (sin inventar cifras)
# ------------------------------------------------------------------

def _fmt(value, metric_name, semantic_layer):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    symbol = semantic_layer.get("business_context", {}).get("currency_symbol", "")
    text = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    if metric_name and (metric_name.startswith(("kpi1", "kpi2", "kpi5", "kpi8"))):
        return f"{text} %"
    if metric_name in ("ventas_productos", "flete_total"):
        return f"{symbol} {text}".strip()
    if metric_name in ("pedidos", "pedidos_con_resena", "resenas"):
        return f"{number:,.0f}".replace(",", ".")
    return text


def generate_insight_offline(question, dataframe, semantic_layer=None, metric_name=None):
    semantic_layer = semantic_layer or {}
    caveat = semantic_layer.get("business_context", {}).get(
        "causality_note", "Los resultados muestran asociaciones, no causas."
    )

    if dataframe is None or dataframe.empty:
        return {
            "headline": "Sin resultados",
            "insight": "La consulta no devolvio filas.",
            "caveat": OFFLINE_NOTICE,
        }

    df = dataframe.copy()
    value_col = df.columns[-1]
    label = semantic_layer.get("measures", {}).get(metric_name or value_col, {}).get(
        "label", value_col
    )

    if len(df.columns) == 1 or len(df) == 1 and len(df.columns) == 1:
        value = _fmt(df.iloc[0, -1], metric_name or value_col, semantic_layer)
        return {
            "headline": f"{label}: {value}",
            "insight": f"El valor de {label} para la consulta es {value}.",
            "caveat": f"{caveat} {OFFLINE_NOTICE}",
        }

    dim_col = df.columns[0]
    numeric = df[value_col].apply(lambda v: float(v) if str(v) not in ("", "None", "nan") else None)
    df = df.assign(_v=numeric).dropna(subset=["_v"])

    if df.empty:
        return {
            "headline": label,
            "insight": "No hay valores numericos para resumir.",
            "caveat": OFFLINE_NOTICE,
        }

    top = df.loc[df["_v"].idxmax()]
    low = df.loc[df["_v"].idxmin()]
    m = metric_name or value_col
    diff = top["_v"] - low["_v"]

    insight = (
        f"El mayor valor de {label} corresponde a {top[dim_col]} "
        f"({_fmt(top['_v'], m, semantic_layer)}) y el menor a {low[dim_col]} "
        f"({_fmt(low['_v'], m, semantic_layer)}), una diferencia de "
        f"{_fmt(diff, m, semantic_layer)}. Se compararon {len(df)} valores de {dim_col}."
    )

    return {
        "headline": f"{label} por {dim_col}",
        "insight": insight,
        "caveat": f"{caveat} {OFFLINE_NOTICE}",
    }
