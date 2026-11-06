"""Tests del MODO RESPALDO (sin Bedrock ni AWS)."""

import unittest

import pandas as pd

from src.config import load_json, make_bedrock
from src.insight import generate_insight
from src.offline_generator import OfflineLLM
from src.semantic_builder import generate_semantic_draft
from src.sql_generator import generate_sql
from src.sql_guard import validate_sql
from src.visualization import choose_chart

SEMANTIC = load_json("config/semantic_layer.json")
VIEW = SEMANTIC["allowed_view"]


def sql_for(question):
    return generate_sql(OfflineLLM(), question, SEMANTIC)


class OfflineModeTests(unittest.TestCase):

    def test_settings_switch(self):
        client = make_bedrock({"aws_region": "us-east-1", "bedrock_model_id": "x",
                               "llm_mode": "offline"})
        self.assertTrue(getattr(client, "offline", False))

    def test_all_golden_queries_pass_guard(self):
        for gq in load_json("config/reference_queries.json"):
            with self.subTest(gq=gq["id"]):
                out = sql_for(gq["question"])
                if gq.get("expect_unavailable"):
                    self.assertEqual(out["status"], "unavailable")
                else:
                    self.assertEqual(out["status"], "ok")
                    self.assertIn(SEMANTIC["measures"][gq["metric"]]["sql"], out["sql"])
                    self.assertTrue(validate_sql(out["sql"], VIEW))

    def test_year_filter(self):
        self.assertIn("anio = 2017",
                      sql_for("¿Cuál fue el porcentaje de pedidos insatisfechos en 2017?")["sql"])

    def test_group_by_region_desc(self):
        sql = sql_for("¿Cuál es la peor región?")["sql"]
        self.assertIn("GROUP BY region_cliente", sql)
        self.assertIn("ORDER BY 2 DESC", sql)

    def test_best_category_asc_for_kpi1(self):
        sql = sql_for("¿Cuál es la mejor categoría?")["sql"]
        self.assertIn("GROUP BY categoria_unica", sql)
        self.assertIn("ORDER BY 2 ASC", sql)

    def test_time_series_ordered_by_time(self):
        sql = sql_for("porcentaje de pedidos insatisfechos por mes en 2025")["sql"]
        self.assertIn("GROUP BY anio_mes", sql)
        self.assertIn("ORDER BY anio_mes ASC", sql)

    def test_uf_and_range_filters(self):
        sql = sql_for("¿Cuál es la calificación promedio en SP entre 2019 y 2021?")["sql"]
        self.assertIn("estado_cliente = 'SP'", sql)
        self.assertIn("anio BETWEEN 2019 AND 2021", sql)

    def test_unknown_question_asks_clarification(self):
        self.assertEqual(sql_for("hola que tal")["status"], "clarification")

    def test_draft_requires_bedrock(self):
        with self.assertRaises(RuntimeError):
            generate_semantic_draft(OfflineLLM(), {})

    def test_template_insight_uses_only_result(self):
        df = pd.DataFrame({"region_cliente": ["Sur", "Norte"],
                           "kpi1_pct_pedidos_bajos": [12.5, 20.25]})
        out = generate_insight(OfflineLLM(), "q", df, SEMANTIC)
        self.assertIn("Norte", out["insight"])
        self.assertIn("20,25 %", out["insight"])
        self.assertIn("MODO RESPALDO", out["caveat"])

    def test_chart_uses_metric_not_year(self):
        df = pd.DataFrame({"anio": [2017, 2018], "kpi1_pct_pedidos_bajos": [14.4, 15.0]})
        fig, kind = choose_chart(df)
        self.assertEqual(kind, "Line")
        self.assertEqual(fig.data[0].y.tolist(), [14.4, 15.0])


if __name__ == "__main__":
    unittest.main()
