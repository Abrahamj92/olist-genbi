"""
SQL Safety Gate - Olist version.

Pedagogical guardrail, not a production SQL firewall.
Production should also rely on IAM / Lake Formation / Athena
workgroup controls.

Olist changes vs the original regex guard:
- Relations are extracted with a real SQL parser (sqlglot), so a
  comma join such as "FROM vw_olist_genbi_pedidos, olist_raw.customers"
  is detected and blocked (the regex only saw the first table).
- EXTRACT(year FROM fecha) is no longer mistaken for a table.
- COUNT(*) is allowed; SELECT * is still blocked.
"""

import re

import sqlglot
from sqlglot import exp


FORBIDDEN = {
    "insert", "update", "delete", "drop", "alter", "create",
    "truncate", "merge", "grant", "revoke", "unload", "call",
}

FORBIDDEN_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create,
    exp.Alter, exp.Merge, exp.Command, exp.TruncateTable,
)


class SQLValidationError(ValueError):
    pass


def _has_select_star(tree):
    for select in tree.find_all(exp.Select):
        for projection in select.expressions:
            if isinstance(projection, exp.Star):
                return True
            if isinstance(projection, exp.Column) and isinstance(
                projection.this, exp.Star
            ):
                return True
    return False


def validate_sql(sql, allowed_view):
    if not sql or not isinstance(sql, str):
        raise SQLValidationError("SQL is empty.")

    normalized = " ".join(sql.strip().lower().split())
    normalized = normalized.rstrip(";").strip()

    if ";" in normalized:
        raise SQLValidationError("Multiple SQL statements are not allowed.")

    if "--" in normalized or "/*" in normalized or "*/" in normalized:
        raise SQLValidationError("SQL comments are not allowed.")

    if not normalized.startswith("select"):
        raise SQLValidationError("Only SELECT statements are allowed.")

    for word in FORBIDDEN:
        if re.search(rf"\b{word}\b", normalized):
            raise SQLValidationError(f"Forbidden SQL operation: {word}")

    try:
        statements = sqlglot.parse(sql.strip().rstrip(";"), read="trino")
    except sqlglot.errors.ParseError as exc:
        raise SQLValidationError(f"SQL could not be parsed: {exc}") from exc

    statements = [s for s in statements if s is not None]

    if len(statements) != 1:
        raise SQLValidationError("Exactly one SQL statement is required.")

    tree = statements[0]

    if not isinstance(tree, (exp.Select, exp.Union)):
        raise SQLValidationError("Only SELECT statements are allowed.")

    if any(tree.find_all(*FORBIDDEN_NODES)):
        raise SQLValidationError("Forbidden SQL operation detected.")

    if _has_select_star(tree):
        raise SQLValidationError("SELECT * is not allowed.")

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    tables = [t for t in tree.find_all(exp.Table) if t.name]

    if not tables:
        raise SQLValidationError("No FROM relation was detected.")

    expected = allowed_view.lower()

    for table in tables:
        name = table.name.lower()
        if name in cte_names:
            continue
        if name != expected:
            full = ".".join(
                p for p in (table.catalog, table.db, table.name) if p
            )
            raise SQLValidationError(
                f"Unauthorized relation '{full}'. Allowed: {allowed_view}"
            )

    return True
