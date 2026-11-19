from src.sql_generator import _extra_kpi_columns, _keep_metric_column, generate_sql
import json

GQ10 = """SELECT COUNT(DISTINCT order_id) AS pedidos_insatisfechos,
100.0 * SUM(pedido_bajo) / NULLIF(SUM(tiene_resena), 0) AS porcentaje
FROM vw_olist_genbi_pedidos WHERE grupo_vendedores = '2 o mas'"""
KPI1 = "100.0 * SUM(pedido_bajo) / NULLIF(SUM(tiene_resena), 0)"


def test_detects_extra_column():
    assert len(_extra_kpi_columns(GQ10)) == 1


def test_group_by_allowed():
    sql = "SELECT region_cliente, SUM(precio) AS v FROM vw_olist_genbi_pedidos GROUP BY region_cliente"
    assert _extra_kpi_columns(sql) == []


def test_keep_metric_column():
    out = _keep_metric_column(GQ10, KPI1)
    assert "COUNT" not in out and "pedido_bajo" in out and "WHERE" in out


class FakeLLM:
    def __init__(self, answers):
        self.answers = list(answers); self.calls = 0
    def ask(self, **kw):
        self.calls += 1
        return self.answers.pop(0)


def test_generate_sql_regenerates():
    sem = json.load(open("config/semantic_layer.json", encoding="utf8"))
    good = f"SELECT {KPI1} AS kpi1 FROM vw_olist_genbi_pedidos WHERE grupo_vendedores = '2 o mas'"
    llm = FakeLLM([GQ10, good])
    r = generate_sql(llm, "¿Cuál es el porcentaje de pedidos insatisfechos con 2 o más vendedores?", sem)
    assert llm.calls == 2 and "COUNT" not in r["sql"] and "Single-KPI" in r["semantic_rule_applied"]
