import json


INSIGHT_SYSTEM_PROMPT = """
You are a Business Intelligence analyst.

Use ONLY the supplied query result and the approved
business context.

Rules:

- Never invent facts.
- Never invent causes.
- Never invent trends.
- Never invent benchmarks.
- Never invent currency.
- Never assume USD.
- If a currency is provided, use only that currency.
- Never add business explanations that are not supported
  directly by the query result.
- Keep the insight concise and business-oriented.
- Respond in Spanish.

Return JSON only:

{
  "headline": "...",
  "insight": "...",
  "caveat": "..."
}
"""


def generate_insight(
    bedrock_client,
    question,
    dataframe,
    semantic_layer=None,
    max_rows=30,
):

    # Olist: MODO RESPALDO -> insight por plantilla (sin Bedrock)
    if getattr(bedrock_client, "offline", False):
        from src.offline_generator import generate_insight_offline

        metric_name = dataframe.columns[-1] if len(dataframe.columns) else None
        return generate_insight_offline(
            question, dataframe, semantic_layer, metric_name
        )

    payload = dataframe.head(
        max_rows
    ).to_dict(
        orient="records"
    )

    business_context = {}

    if semantic_layer:
        business_context = semantic_layer.get(
            "business_context",
            {}
        )

    prompt = f"""
PREGUNTA ORIGINAL

{question}


CONTEXTO DE NEGOCIO APROBADO

{json.dumps(
    business_context,
    indent=2,
    ensure_ascii=False
)}


RESULTADO DE ATHENA

{json.dumps(
    payload,
    indent=2,
    ensure_ascii=False,
    default=str
)}


Genera un insight de negocio breve.

Usa exclusivamente la evidencia proporcionada.
"""

    return bedrock_client.ask_json(
        INSIGHT_SYSTEM_PROMPT,
        prompt,
        max_tokens=700,
    )