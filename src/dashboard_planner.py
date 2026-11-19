"""Bedrock proposes dashboard structure; the application validates and executes it.

Adaptado del repositorio docente (NEXA) al Data Mart de Olist."""
import json

from src.dashboard_validator import DashboardValidationError, available_dimensions, validate_dashboard


PLANNER_SYSTEM_PROMPT = """
Eres un diseñador de dashboards de Business Intelligence para Olist
(marketplace brasileño; Data Mart de insatisfacción del cliente, 1 fila = 1 pedido).
Devuelve ÚNICAMENTE un objeto JSON (sin código, SQL, cifras ni explicaciones):
{
 "title": "título de negocio",
 "components": [
   {"id": "identificador_unico", "type": "kpi|bar|line|table",
    "metric": "métrica aprobada", "dimension": null,
    "title": "título claro", "limit": 20}
 ]
}
REGLAS:
- Solo utiliza identificadores exactos del catálogo. Nunca inventes métricas, fórmulas, dimensiones ni cifras.
- No generes SQL, Python, filtros de fecha ni explicaciones de negocio.
- Entre 1 y 8 componentes; cada identificador debe ser único y usar minúsculas y guiones bajos.
- Los KPI deben tener dimension: null. Los gráficos y tablas necesitan una dimensión aprobada.
- Una dimensión NUNCA es una métrica: cumplimiento_plazo, rango_flete, region_cliente o categoria_unica van en "dimension".
- Para EVOLUCIÓN ANUAL usa dimension: "anio" y type: "line"; para EVOLUCIÓN MENSUAL usa dimension: "mes" y type: "line".
- Para insatisfacción o pedidos insatisfechos elige kpi1_pct_pedidos_bajos; para reseñas bajas, kpi2_pct_resenas_bajas;
  para calificación promedio, kpi3_calificacion_promedio; para entrega tardía, kpi5_tasa_entrega_tardia;
  para flete sobre precio, kpi8_flete_sobre_precio; para ventas, ventas_productos; para pedidos, pedidos.
- "Insatisfacción según X" o "por X" es type: "bar" con metric kpi1_pct_pedidos_bajos y dimension X.
- El Data Mart NO tiene clientes, compradores, recompra, EBITDA, margen ni proyecciones: omítelos;
  nunca sustituyas una métrica ausente por otra incongruente ni la rotules con un nombre que no le corresponde.
- Diseña el dashboard para responder específicamente a la petición del usuario.
- No dupliques la MISMA métrica y dimensión en dos gráficos.
- Si hay espacio, prioriza diversidad de dimensiones cuando se soliciten.
"""


def catalog_for_planner(semantic):
    """Expose approved business identifiers and labels, but not SQL expressions."""
    dimensions = available_dimensions(semantic)
    return {
        "dataset": semantic.get("dataset", "Business Intelligence"),
        "unavailable_metrics": sorted(semantic.get("unavailable_metrics", {})),
        "grain": semantic.get("grain", ""),
        "metrics": {
            key: {
                "label": value.get("label", key),
                "synonyms": value.get("synonyms", [])[:8],
            }
            for key, value in semantic.get("measures", {}).items()
            if isinstance(value, dict) and value.get("sql")
        },
        "dimensions": {
            key: {"label": value.get("label", key)}
            for key, value in dimensions.items()
            if isinstance(value, dict) and value.get("column")
        },
    }


def remove_redundant_components(spec):
    """Keep one visualization per metric+dimension, preferring time lines and charts.

    This runs AFTER strict schema/semantic validation; unapproved or unsafe
    components can never be silently repaired.
    """
    preference = {"line": 3, "bar": 2, "table": 1, "kpi": 1}
    selected = {}
    for index, component in enumerate(spec["components"]):
        identity = (component["metric"], component["dimension"])
        old = selected.get(identity)
        if old is None or preference[component["type"]] > preference[old[1]["type"]]:
            selected[identity] = (index, component)
    output = dict(spec)
    output["components"] = [item[1] for item in sorted(selected.values(), key=lambda item: item[0])]
    return output


def plan_dashboard(bedrock_client, user_request, semantic):
    if not isinstance(user_request, str) or not 5 <= len(user_request.strip()) <= 1500:
        raise ValueError("Escribe una petición de negocio de 5 a 1500 caracteres.")
    catalog = catalog_for_planner(semantic)
    if not catalog["metrics"]:
        raise ValueError("No hay métricas aprobadas disponibles.")
    request = (
        "CATÁLOGO SEMÁNTICO APROBADO (identificadores obligatorios):\n"
        + json.dumps(catalog, ensure_ascii=False, indent=2)
        + "\n\nPETICIÓN DE NEGOCIO:\n"
        + user_request.strip()
        + "\n\nGenera el Dashboard Specification JSON."
    )
    # One validation-guided retry: never execute or silently fix invalid plans.
    # Bedrock must generate a new fully valid specification.
    for attempt in range(2):
        proposed = bedrock_client.ask_json(
            system_prompt=PLANNER_SYSTEM_PROMPT,
            user_prompt=request,
            max_tokens=2800,
        )
        try:
            validated = validate_dashboard(proposed, semantic, max_components=8)
            return remove_redundant_components(validated)
        except DashboardValidationError as exc:
            if attempt == 1:
                raise
            request += (
                "\n\nTU PROPUESTA ANTERIOR FUE RECHAZADA: " + str(exc)
                + "\nGenera un NUEVO JSON completo y válido. "
                + "Para KPI usa dimension:null; los desgloses por región, plazo, "
                + "rango de flete o categoría deben ser type:bar o type:table "
                + "con esa dimensión (nunca como metric); las líneas usan anio o mes. "
                + "Mantén todas las métricas y dimensiones dentro del catálogo."
            )
