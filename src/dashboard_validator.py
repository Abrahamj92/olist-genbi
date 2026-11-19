"""Validate dashboard plans against the human-approved semantic layer.

Adaptado del repositorio docente (NEXA) al Data Mart de Olist.
Olist: las dimensiones de tiempo aprobadas son `anio` y `mes` (columna anio_mes,
formato YYYY-MM); no hace falta derivar sale_month.
"""
import re

ALLOWED_TYPES = {"kpi", "bar", "line", "table"}
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
TIME_DIMENSIONS = {"anio", "mes"}
# Olist: 2016-09 a 2025-12 son ~112 meses; el límite docente de 100 cortaría 2025.
MAX_LIMIT = 120


class DashboardValidationError(ValueError):
    pass


def available_dimensions(semantic):
    """Approved dimensions only (Olist ya expone anio y mes como columnas)."""
    return dict(semantic.get("dimensions", {}))


def validate_dashboard(spec, semantic, max_components=12):
    """Fail closed for unknown keys, metrics, dimensions and chart combinations."""
    if not isinstance(spec, dict):
        raise DashboardValidationError("Dashboard must be a JSON object.")
    if set(spec) - {"title", "components", "version"}:
        raise DashboardValidationError("Unknown dashboard fields.")
    if not isinstance(spec.get("title"), str) or not 1 <= len(spec["title"]) <= 120:
        raise DashboardValidationError("Title must contain 1-120 characters.")
    components = spec.get("components")
    if not isinstance(components, list) or not 1 <= len(components) <= max_components:
        raise DashboardValidationError(f"Dashboard requires 1-{max_components} components.")
    measures = semantic.get("measures", {})
    dimensions = available_dimensions(semantic)
    validated = []
    ids = set()
    for i, c in enumerate(components):
        if not isinstance(c, dict) or set(c) - {"id", "type", "metric", "dimension", "limit", "title"}:
            raise DashboardValidationError(f"Invalid fields in component {i}.")
        key = c.get("id", f"component_{i}")
        if not isinstance(key, str) or not IDENTIFIER.fullmatch(key) or key in ids:
            raise DashboardValidationError(f"Invalid/duplicate component id: {key!r}")
        ids.add(key)
        kind = c.get("type")
        metric = c.get("metric")
        dimension = c.get("dimension")
        if kind not in ALLOWED_TYPES:
            raise DashboardValidationError(f"Unsupported component type: {kind}")
        if metric not in measures or not isinstance(measures[metric], dict) or not measures[metric].get("sql"):
            raise DashboardValidationError(f"Unapproved metric: {metric}")
        if kind == "kpi" and dimension is not None:
            raise DashboardValidationError("KPI cannot have a grouping dimension.")
        if kind != "kpi" and (dimension not in dimensions or not isinstance(dimensions[dimension], dict)):
            raise DashboardValidationError(f"Unapproved dimension: {dimension}")
        if kind == "line" and dimension not in TIME_DIMENSIONS:
            raise DashboardValidationError("Line charts require an approved time dimension.")
        limit = c.get("limit", MAX_LIMIT if kind == "line" else 20)
        if type(limit) is not int or not 1 <= limit <= MAX_LIMIT:
            raise DashboardValidationError(f"Component limit must be an integer between 1 and {MAX_LIMIT}.")
        label = c.get("title", metric)
        if not isinstance(label, str) or not 1 <= len(label) <= 120:
            raise DashboardValidationError("Invalid component title.")
        validated.append({
            "id": key, "type": kind, "metric": metric, "dimension": dimension,
            "limit": limit, "title": label,
        })
    return {"version": "1.0", "title": spec["title"], "components": validated}
