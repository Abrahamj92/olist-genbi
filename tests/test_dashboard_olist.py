"""Prompt-to-Dashboard (patrón del repositorio docente) adaptado a Olist.

Usa la Semantic Layer aprobada de Olist; Bedrock y Athena se simulan.
"""
import json
import unittest
from pathlib import Path

import pandas as pd

from src.dashboard_insights import curate_insights, evidence_from_results
from src.dashboard_planner import catalog_for_planner, plan_dashboard, remove_redundant_components
from src.dashboard_renderer import olist_amount
from src.dashboard_runtime import execute_dashboard
from src.dashboard_sql_builder import build_component_sql
from src.dashboard_validator import DashboardValidationError, validate_dashboard
from src.sql_guard import validate_sql

ROOT = Path(__file__).resolve().parents[1]
SEM = json.loads((ROOT / "config/semantic_layer.json").read_text(encoding="utf-8"))
EXEC = json.loads((ROOT / "config/dashboard_executive.json").read_text(encoding="utf-8"))
LOGI = json.loads((ROOT / "config/dashboard_examples.json").read_text(encoding="utf-8"))
SCEN = json.loads((ROOT / "config/dashboard_scenarios.json").read_text(encoding="utf-8"))["scenarios"]


class FakeBedrock:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def ask_json(self, system_prompt, user_prompt, max_tokens):
        self.calls.append(user_prompt)
        return self.responses.pop(0)


class FakeAthena:
    def run(self, sql):
        if "GROUP BY" in sql:
            return pd.DataFrame({"dimension_value": ["Tarde", "A tiempo"], "metric_value": ["57.85", "8.96"]}), {"query_execution_id": "q"}
        return pd.DataFrame({"metric_value": ["15.21"]}), {"query_execution_id": "q"}


class ValidatorAndBuilder(unittest.TestCase):
    def test_examples_compile_and_pass_guard(self):
        for spec in (EXEC, LOGI):
            plan = validate_dashboard(spec, SEM)
            for c in plan["components"]:
                sql = build_component_sql(c, SEM)
                validate_sql(sql, SEM["allowed_view"])
                self.assertIn(SEM["measures"][c["metric"]]["sql"], sql)

    def test_kpi1_formula_and_grouping(self):
        c = validate_dashboard(EXEC, SEM)["components"][6]
        sql = build_component_sql(c, SEM)
        self.assertIn("100.0 * SUM(pedido_bajo) / NULLIF(SUM(tiene_resena), 0)", sql)
        self.assertIn("region_cliente AS dimension_value", sql)
        self.assertIn("ORDER BY metric_value DESC", sql)

    def test_monthly_line_covers_all_months(self):
        c = validate_dashboard({"title": "t", "components": [
            {"type": "line", "metric": "ventas_productos", "dimension": "mes"}]}, SEM)["components"][0]
        sql = build_component_sql(c, SEM)
        self.assertIn("anio_mes AS dimension_value", sql)
        self.assertIn("ORDER BY dimension_value ASC LIMIT 120", sql)

    def test_governance_matrix(self):
        bad = [
            {"type": "kpi", "metric": "ebitda"},                                   # métrica no aprobada
            {"type": "kpi", "metric": "compradores_unicos"},                       # no disponible en Olist
            {"type": "kpi", "metric": "pedidos", "sql": "DROP TABLE x"},           # SQL inyectado
            {"type": "bar", "metric": "pedidos", "dimension": "unknown"},          # dimensión inexistente
            {"type": "bar", "metric": "cumplimiento_plazo", "dimension": "cumplimiento_plazo"},  # dimensión como métrica
            {"type": "line", "metric": "pedidos", "dimension": "region_cliente"},  # línea sin tiempo
            {"type": "kpi", "metric": "pedidos", "dimension": "anio"},             # KPI con dimensión
            {"type": "pie", "metric": "pedidos", "dimension": "anio"},             # tipo no soportado
        ]
        for comp in bad:
            with self.assertRaises(DashboardValidationError, msg=str(comp)):
                validate_dashboard({"title": "X", "components": [comp]}, SEM)

    def test_rejects_top_level_filters(self):
        with self.assertRaises(DashboardValidationError):
            validate_dashboard({"title": "X", "filters": [{"anio": 2025}],
                                "components": [{"type": "kpi", "metric": "pedidos"}]}, SEM)


class Planner(unittest.TestCase):
    def test_catalog_has_no_sql(self):
        cat = catalog_for_planner(SEM)
        self.assertNotIn("sql", json.dumps(cat["metrics"]))
        self.assertIn("compradores_unicos", cat["unavailable_metrics"])

    def test_retry_with_feedback_then_valid(self):
        bad = {"title": "x", "components": [{"id": "a", "type": "bar", "metric": "cumplimiento_plazo",
                                             "dimension": "cumplimiento_plazo"}]}
        good = {"title": "x", "components": [{"id": "a", "type": "bar", "metric": "kpi1_pct_pedidos_bajos",
                                              "dimension": "cumplimiento_plazo"}]}
        fake = FakeBedrock(bad, good)
        plan = plan_dashboard(fake, SCEN[1]["prompt"], SEM)
        self.assertEqual(len(fake.calls), 2)
        self.assertIn("RECHAZADA", fake.calls[1])
        self.assertEqual(plan["components"][0]["metric"], "kpi1_pct_pedidos_bajos")

    def test_two_invalid_plans_fail_closed(self):
        bad = {"title": "x", "components": [{"id": "a", "type": "kpi", "metric": "ebitda"}]}
        with self.assertRaises(DashboardValidationError):
            plan_dashboard(FakeBedrock(bad, bad), "Muéstrame el EBITDA mensual", SEM)

    def test_more_than_8_components_rejected(self):
        many = {"title": "x", "components": [{"id": f"k{i}", "type": "kpi", "metric": "pedidos"} for i in range(9)]}
        with self.assertRaises(DashboardValidationError):
            plan_dashboard(FakeBedrock(many, many), "dashboard", SEM)

    def test_duplicates_removed_prefer_line(self):
        spec = validate_dashboard({"title": "x", "components": [
            {"id": "t", "type": "table", "metric": "pedidos", "dimension": "anio"},
            {"id": "l", "type": "line", "metric": "pedidos", "dimension": "anio"}]}, SEM)
        self.assertEqual([c["id"] for c in remove_redundant_components(spec)["components"]], ["l"])

    def test_scenarios_fit_and_have_focus(self):
        self.assertEqual(len(SCEN), 4)
        for s in SCEN:
            self.assertLessEqual(len(s["prompt"]), 1500)
            self.assertTrue(set(s["focus_metrics"]) <= set(SEM["measures"]))
            self.assertTrue(set(s["focus_dimensions"]) <= set(SEM["dimensions"]))


class RuntimeAndInsights(unittest.TestCase):
    def test_runtime_and_evidence(self):
        spec, results = execute_dashboard(EXEC, SEM, FakeAthena())
        self.assertEqual(len(results), 7)
        evidence = evidence_from_results(results, SEM)
        self.assertTrue(any(e["fact"].startswith("Lidera") for e in evidence))
        self.assertIn("15.21 %", evidence[0]["fact"])

    def test_invented_evidence_id_rejected(self):
        evidence = [{"id": "kpi1_total", "title": "x", "fact": "x", "source": "x"}]
        with self.assertRaises(ValueError):
            curate_insights(FakeBedrock({"selected_ids": ["inventado"]}), "p", evidence)

    def test_formats(self):
        self.assertEqual(olist_amount(15.207, "kpi1_pct_pedidos_bajos", SEM), "15.21 %")
        self.assertEqual(olist_amount(86437222.1, "ventas_productos", SEM), "R$ 86,437,222.10")
        self.assertEqual(olist_amount(449422, "pedidos", SEM), "449,422")


if __name__ == "__main__":
    unittest.main()
