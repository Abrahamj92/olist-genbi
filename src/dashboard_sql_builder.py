"""Deterministic SQL compiler: formulas come only from approved local semantics."""
import re

from src.dashboard_validator import DashboardValidationError, TIME_DIMENSIONS, available_dimensions

SAFE_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
FORBIDDEN = re.compile(
    r";|--|/\*|\*/|\b(?:FROM|JOIN|UNION|SELECT|INSERT|DROP|DELETE|UPDATE|ALTER)\b",
    re.I,
)


def build_component_sql(component, semantic):
    """No SQL fragment comes from the Bedrock-generated dashboard JSON."""
    metric_sql = semantic["measures"][component["metric"]]["sql"].strip()
    if FORBIDDEN.search(metric_sql):
        raise DashboardValidationError("Unsafe semantic SQL expression.")
    if not re.fullmatch(r"[a-zA-Z0-9_(),.\s+*/-]+", metric_sql):
        raise DashboardValidationError("Unexpected characters in approved metric expression.")
    view = semantic["allowed_view"]
    if not SAFE_NAME.fullmatch(view):
        raise DashboardValidationError("Invalid approved view name.")
    dimension = component["dimension"]
    if dimension is None:
        return f"SELECT {metric_sql} AS metric_value FROM {view}"
    column = available_dimensions(semantic)[dimension].get("column")
    if not isinstance(column, str) or not SAFE_NAME.fullmatch(column):
        raise DashboardValidationError("Invalid approved dimension column.")
    ordering = "dimension_value ASC" if dimension in TIME_DIMENSIONS and component["type"] == "line" \
        else "metric_value DESC"
    return (
        f"SELECT {column} AS dimension_value, {metric_sql} AS metric_value "
        f"FROM {view} GROUP BY 1 ORDER BY {ordering} LIMIT {component['limit']}"
    )
