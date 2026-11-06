import json
import re
import unicodedata


SQL_SYSTEM_PROMPT = """
You are the NL-to-SQL component of a governed
Business Intelligence application.

The application may provide a FORCED SEMANTIC METRIC.

If a forced metric is provided:
- You MUST use exactly its approved SQL expression.
- You MUST NOT replace it with another metric.
- You MUST NOT reinterpret its business meaning.
- The metric name is a semantic concept, not a physical column.

General rules:
- Generate exactly one SELECT statement.
- Query ONLY the allowed view.
- Never use SELECT *.
- Never invent columns.
- Never modify data.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER,
  CREATE, TRUNCATE, MERGE, GRANT or REVOKE.
- Do not add dimensions unless required by the question.
- If the question asks for one KPI only, return one KPI only.
- Add GROUP BY only when the user requests a breakdown,
  comparison, ranking, trend or dimension.
- Prefer explicit aliases.
- Use LIMIT 100 for ranked or tabular results.
- Filter years and months only with the columns anio and anio_mes.
- Do not use EXTRACT, WITH, subqueries or joins: query the view directly.

Return SQL ONLY.

Do not return JSON.
Do not explain the SQL.
Markdown SQL fences are allowed.
"""


def normalize_text(text):
    """
    Normalize text for semantic matching.

    Example:
    'Facturación' -> 'facturacion'
    """
    text = text.lower().strip()

    text = unicodedata.normalize(
        "NFD",
        text,
    )

    text = "".join(
        char
        for char in text
        if unicodedata.category(char) != "Mn"
    )

    text = re.sub(
        r"[^a-z0-9_% ]+",
        " ",
        text,
    )

    return " ".join(text.split())


def _find_term(normalized_question, term):
    """
    Return the (start, end) span of a business term inside the
    normalized question, matching WHOLE WORDS only.

    Olist change: the original resolver used substring matching
    ('nota' matched inside 'notable').
    """
    normalized_term = normalize_text(term)

    if not normalized_term:
        return None

    match = re.search(
        rf"(?<![a-z0-9_]){re.escape(normalized_term)}(?![a-z0-9_])",
        normalized_question,
    )

    if not match:
        return None

    return match.span()


def _collect_matches(question, semantic_layer):
    """
    Collect every governed term found in the question:
    measure synonyms, approved ambiguities and unavailable metrics.
    """
    normalized_question = normalize_text(question)
    measures = semantic_layer.get("measures", {})
    matches = []

    # 1. Measure names, labels and synonyms
    for metric_name, metric in measures.items():
        candidates = [
            metric_name.replace("_", " "),
            metric.get("label", ""),
            *metric.get("synonyms", []),
        ]
        for candidate in candidates:
            span = _find_term(normalized_question, candidate)
            if span:
                matches.append({
                    "source": "synonym",
                    "metric_name": metric_name,
                    "metric": metric,
                    "matched_term": candidate,
                    "span": span,
                })

    # 2. Governed ambiguities (approved defaults)
    for key, rule in semantic_layer.get("ambiguities", {}).items():
        default_metric = rule.get("approved_default")
        if default_metric not in measures:
            continue
        for term in rule.get("terms", [key]):
            span = _find_term(normalized_question, term)
            if span:
                matches.append({
                    "source": "approved_default",
                    "metric_name": default_metric,
                    "metric": measures[default_metric],
                    "matched_term": term,
                    "ambiguity": key,
                    "reason": rule.get("reason"),
                    "span": span,
                })

    # 3. Metrics declared NOT available in the data mart
    for key, rule in semantic_layer.get("unavailable_metrics", {}).items():
        for term in rule.get("terms", [key]):
            span = _find_term(normalized_question, term)
            if span:
                matches.append({
                    "source": "unavailable",
                    "metric_name": key,
                    "metric": rule,
                    "matched_term": term,
                    "span": span,
                })

    return matches


def _drop_contained(matches):
    """
    Remove matches whose span is fully inside a longer match
    ('pedidos' inside 'pedidos con calificacion baja').
    """
    kept = []
    for m in matches:
        s, e = m["span"]
        contained = any(
            (o is not m)
            and o["span"][0] <= s
            and e <= o["span"][1]
            and (o["span"][1] - o["span"][0]) > (e - s)
            for o in matches
        )
        if not contained:
            kept.append(m)
    return kept


def resolve_semantic_metric(question, semantic_layer):
    """
    Resolve the business metric BEFORE calling the LLM.

    Priority (Olist version):
    1. Unavailable metrics: if the question asks for something the
       data mart cannot answer (e.g. clientes / compradores unicos),
       return source = 'unavailable'. This wins over any other match
       unless the term is part of a longer governed phrase.
    2. The longest remaining governed term (synonym or approved
       ambiguity). On equal length, explicit synonyms win.

    Returns None when no metric can be determined.
    """
    matches = _drop_contained(
        _collect_matches(question, semantic_layer)
    )

    if not matches:
        return None

    unavailable = [m for m in matches if m["source"] == "unavailable"]
    if unavailable:
        best = max(unavailable, key=lambda m: m["span"][1] - m["span"][0])
    else:
        best = max(
            matches,
            key=lambda m: (
                m["span"][1] - m["span"][0],
                1 if m["source"] == "synonym" else 0,
            ),
        )

    best = dict(best)
    best["match_length"] = best["span"][1] - best["span"][0]
    return best


def extract_sql(text):
    """
    Extract SQL from either plain text or a Markdown
    SQL code block.
    """

    if text is None:
        raise ValueError(
            "Bedrock returned no SQL."
        )

    cleaned = text.strip()

    if not cleaned:
        raise ValueError(
            "Bedrock returned empty SQL."
        )

    # Remove Markdown fence.
    cleaned = re.sub(
        r"^```(?:sql)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    )

    return cleaned.strip()


def generate_sql(
    bedrock_client,
    question,
    semantic_layer,
):
    """
    Resolve governed semantics first, then ask Bedrock
    to generate SQL using those semantics.
    """

    resolved = resolve_semantic_metric(
        question,
        semantic_layer,
    )

    allowed_view = semantic_layer[
        "allowed_view"
    ]

    # --------------------------------------------------
    # Olist: governed refusal for unavailable metrics.
    # Bedrock and Athena are NOT called.
    # --------------------------------------------------

    if resolved and resolved["source"] == "unavailable":

        rule = resolved["metric"]

        return {
            "status": "unavailable",
            "interpretation": (
                f'"{resolved["matched_term"]}" '
                f'→ {rule.get("label", resolved["metric_name"])} '
                "(no disponible)"
            ),
            "metric_used": None,
            "semantic_rule_applied": (
                "Unavailable metric: "
                f'{resolved["metric_name"]} - {rule.get("reason", "")}'
            ),
            "sql": None,
            "message": rule.get("message"),
            "alternatives": rule.get("alternatives", []),
            "clarification_question": None,
        }

    # --------------------------------------------------
    # Olist: MODO RESPALDO (llm_mode = "offline")
    # SQL por reglas de la capa semantica, sin Bedrock.
    # --------------------------------------------------

    if getattr(bedrock_client, "offline", False):
        from src.offline_generator import generate_sql_offline

        return generate_sql_offline(question, semantic_layer, resolved)

    # --------------------------------------------------
    # Semantic metric context
    # --------------------------------------------------

    if resolved:

        metric_name = resolved[
            "metric_name"
        ]

        metric = resolved["metric"]

        metric_sql = metric["sql"]

        semantic_context = f"""
FORCED SEMANTIC METRIC

Metric key:
{metric_name}

Business label:
{metric.get("label", metric_name)}

Approved SQL expression:
{metric_sql}

Matched business term:
{resolved["matched_term"]}

IMPORTANT:
You MUST use this exact SQL expression.

Do NOT substitute another metric.
Do NOT treat "{metric_name}" as a physical column.
"""

        interpretation = (
            f'"{resolved["matched_term"]}" '
            f'→ {metric.get("label", metric_name)}'
        )

        semantic_rule = (
            f"Semantic Layer resolved "
            f"{resolved['matched_term']} "
            f"to {metric_name} "
            f"({resolved['source']})"
        )

    else:

        metric_name = None

        semantic_context = """
NO FORCED METRIC WAS RESOLVED.

Use the approved semantic layer and business rules
to interpret the question.

Do not invent business definitions.
"""

        interpretation = (
            "No deterministic metric match; "
            "Bedrock interpretation required."
        )

        semantic_rule = (
            "No direct semantic synonym matched."
        )

    # --------------------------------------------------
    # Prompt
    # --------------------------------------------------

    user_prompt = f"""
ALLOWED VIEW

{allowed_view}


APPROVED SEMANTIC LAYER

{json.dumps(semantic_layer, indent=2, ensure_ascii=False)}


{semantic_context}


BUSINESS QUESTION

{question}


Generate the SQL query.
"""

    raw_sql = bedrock_client.ask(
        system_prompt=SQL_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=1000,
        temperature=0,
    )

    sql = extract_sql(raw_sql)

    return {
        "status": "ok",
        "interpretation": interpretation,
        "metric_used": metric_name,
        "semantic_rule_applied": semantic_rule,
        "sql": sql,
        "clarification_question": None,
    }