import unittest

from src.config import load_json
from src.sql_generator import generate_sql, resolve_semantic_metric


SEMANTIC = load_json("config/semantic_layer.json")


class FailingBedrock:
    """If the resolver refuses the metric, Bedrock must never be called."""

    def ask(self, *args, **kwargs):
        raise AssertionError("Bedrock should not be called")


class SemanticResolverTests(unittest.TestCase):

    def resolve(self, question):
        return resolve_semantic_metric(question, SEMANTIC)

    # ---- Unavailable metric: compradores / clientes -------------------

    def test_clientes_unavailable(self):
        r = self.resolve("¿Cuántos clientes tenemos?")
        self.assertEqual(r["source"], "unavailable")

    def test_clientes_never_become_pedidos(self):
        r = self.resolve("¿Cuántos clientes y pedidos hubo en 2017?")
        self.assertEqual(r["source"], "unavailable")

    def test_clientes_insatisfechos_unavailable(self):
        r = self.resolve("¿Qué región tiene más clientes insatisfechos?")
        self.assertEqual(r["source"], "unavailable")

    def test_compradores_unicos_unavailable(self):
        r = self.resolve("Número de compradores únicos por año")
        self.assertEqual(r["source"], "unavailable")

    def test_generate_sql_does_not_call_bedrock(self):
        out = generate_sql(FailingBedrock(), "¿Cuántos clientes únicos tenemos?", SEMANTIC)
        self.assertEqual(out["status"], "unavailable")
        self.assertIsNone(out["sql"])
        self.assertTrue(out["alternatives"])

    # ---- Governed metrics ---------------------------------------------

    def test_kpi1_synonym(self):
        r = self.resolve("¿Cuál es el porcentaje de pedidos insatisfechos?")
        self.assertEqual(r["metric_name"], "kpi1_pct_pedidos_bajos")

    def test_longest_phrase_wins(self):
        r = self.resolve("¿Cuántos pedidos con reseña hay?")
        self.assertEqual(r["metric_name"], "pedidos_con_resena")

    def test_kpi2_by_review(self):
        r = self.resolve("¿Qué porcentaje de reseñas bajas tenemos?")
        self.assertEqual(r["metric_name"], "kpi2_pct_resenas_bajas")

    def test_ambiguity_insatisfaccion_defaults_to_kpi1(self):
        r = self.resolve("¿Dónde hay más insatisfacción?")
        self.assertEqual(r["source"], "approved_default")
        self.assertEqual(r["metric_name"], "kpi1_pct_pedidos_bajos")

    def test_ambiguity_ventas_without_freight(self):
        r = self.resolve("¿Cuánto vendimos en total?")
        self.assertEqual(r["metric_name"], "ventas_productos")

    def test_ambiguity_peor(self):
        r = self.resolve("¿Cuál es la peor región?")
        self.assertEqual(r["metric_name"], "kpi1_pct_pedidos_bajos")

    def test_calificacion_promedio_over_ambiguity(self):
        r = self.resolve("¿Cuál es la calificación promedio?")
        self.assertEqual(r["source"], "synonym")
        self.assertEqual(r["metric_name"], "kpi3_calificacion_promedio")

    def test_whole_word_matching(self):
        # 'nota' must not match inside 'notable'
        self.assertIsNone(self.resolve("¿Hubo un cambio notable?"))

    def test_flete_sobre_precio(self):
        r = self.resolve("¿Cuál es la proporción de flete sobre precio?")
        self.assertEqual(r["metric_name"], "kpi8_flete_sobre_precio")


class GoldenQueriesResolverTests(unittest.TestCase):
    """Every Golden Query must resolve to its declared metric."""

    def test_golden_metrics(self):
        golden = load_json("config/reference_queries.json")
        for gq in golden:
            with self.subTest(gq=gq["id"]):
                r = resolve_semantic_metric(gq["question"], SEMANTIC)
                self.assertIsNotNone(r)
                self.assertEqual(r["metric_name"], gq["metric"])


if __name__ == "__main__":
    unittest.main()
