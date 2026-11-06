import unittest

from src.sql_guard import SQLValidationError, validate_sql


class SQLGuardTests(unittest.TestCase):
    VIEW = "vw_olist_genbi_pedidos"

    def test_valid_select(self):
        sql = """
        SELECT region_cliente,
               100.0 * SUM(pedido_bajo) / NULLIF(SUM(tiene_resena), 0) AS kpi1
        FROM vw_olist_genbi_pedidos
        GROUP BY region_cliente
        """
        self.assertTrue(validate_sql(sql, self.VIEW))

    def test_valid_qualified_view(self):
        self.assertTrue(validate_sql(
            "SELECT COUNT(DISTINCT order_id) FROM olist_master.vw_olist_genbi_pedidos",
            self.VIEW,
        ))

    def test_count_star_allowed(self):
        self.assertTrue(validate_sql(
            "SELECT COUNT(*) AS n FROM vw_olist_genbi_pedidos", self.VIEW
        ))

    def test_extract_from_is_not_a_table(self):
        # The original regex guard blocked this valid query.
        self.assertTrue(validate_sql(
            "SELECT EXTRACT(year FROM fecha_compra) AS y, COUNT(*) AS n "
            "FROM vw_olist_genbi_pedidos GROUP BY 1",
            self.VIEW,
        ))

    def test_blocks_other_table(self):
        with self.assertRaises(SQLValidationError):
            validate_sql("SELECT order_id FROM fact_resenas", self.VIEW)

    def test_blocks_comma_join(self):
        # The original regex guard only captured the first table.
        with self.assertRaises(SQLValidationError):
            validate_sql(
                "SELECT v.order_id, c.customer_unique_id "
                "FROM vw_olist_genbi_pedidos v, olist_raw.customers c",
                self.VIEW,
            )

    def test_blocks_join_to_raw(self):
        with self.assertRaises(SQLValidationError):
            validate_sql(
                "SELECT v.order_id FROM vw_olist_genbi_pedidos v "
                "JOIN olist_raw.orders o ON v.order_id = o.order_id",
                self.VIEW,
            )

    def test_blocks_subquery_other_table(self):
        with self.assertRaises(SQLValidationError):
            validate_sql(
                "SELECT order_id FROM vw_olist_genbi_pedidos WHERE order_id IN "
                "(SELECT order_id FROM olist_master.fact_resenas)",
                self.VIEW,
            )

    def test_blocks_select_star(self):
        with self.assertRaises(SQLValidationError):
            validate_sql("SELECT * FROM vw_olist_genbi_pedidos", self.VIEW)

    def test_blocks_delete(self):
        with self.assertRaises(SQLValidationError):
            validate_sql("DELETE FROM vw_olist_genbi_pedidos", self.VIEW)

    def test_blocks_multiple_statements(self):
        with self.assertRaises(SQLValidationError):
            validate_sql(
                "SELECT 1 FROM vw_olist_genbi_pedidos; DROP VIEW x", self.VIEW
            )

    def test_blocks_comments(self):
        with self.assertRaises(SQLValidationError):
            validate_sql(
                "SELECT order_id FROM vw_olist_genbi_pedidos -- x", self.VIEW
            )


if __name__ == "__main__":
    unittest.main()
