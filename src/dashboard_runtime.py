"""Governed dashboard execution: semantic SQL -> SQL Guard -> Athena -> typed data."""
import pandas as pd

from src.dashboard_validator import validate_dashboard
from src.dashboard_sql_builder import build_component_sql
from src.sql_guard import validate_sql


def execute_dashboard(specification, semantic, athena):
    """Run validated components; preserve per-component failures for the UI."""
    spec = validate_dashboard(specification, semantic)
    results = []
    for component in spec["components"]:
        sql = build_component_sql(component, semantic)
        validate_sql(sql, semantic["allowed_view"])
        try:
            frame, metadata = athena.run(sql)
            frame = frame.copy()
            if "metric_value" in frame.columns:
                frame["metric_value"] = pd.to_numeric(frame["metric_value"], errors="coerce")
            results.append({
                "component": component, "sql": sql, "data": frame,
                "metadata": metadata, "error": None,
            })
        except Exception as exc:
            results.append({
                "component": component, "sql": sql, "data": pd.DataFrame(),
                "metadata": {}, "error": str(exc),
            })
    return spec, results
