\
import json


SEMANTIC_SYSTEM_PROMPT = """
You are helping a Business Intelligence engineer build a semantic layer.

Your role is DISCOVERY, not final governance.

From the supplied dataset profile:
1. Identify candidate dimensions.
2. Identify candidate measures.
3. Suggest safe aggregations.
4. Suggest business-friendly labels and synonyms.
5. Identify IDs or fields that should not be summed.
6. Identify ambiguous business terms.
7. Flag any decision that requires human/business validation.

Important rules:
- Never invent columns.
- Respect the stated grain.
- Do not make uncertain business definitions look authoritative.
- If counting an identifier may duplicate entities because of the grain, flag it.
- Return JSON only.

Required top-level keys:
dataset, dimensions, candidate_measures, non_additive_fields,
suggested_synonyms, ambiguities, validation_questions
"""


def generate_semantic_draft(bedrock_client, dataset_profile):
    if getattr(bedrock_client, "offline", False):
        raise RuntimeError(
            "El draft semantico requiere Amazon Bedrock y no se genera en "
            "modo respaldo. Cambie llm_mode a 'bedrock' cuando la cuota "
            "este aprobada."
        )
    user_prompt = f"""
DATASET PROFILE

{json.dumps(dataset_profile, indent=2, ensure_ascii=False)}

Generate a semantic layer DRAFT for human review.
"""
    return bedrock_client.ask_json(
        SEMANTIC_SYSTEM_PROMPT,
        user_prompt,
        max_tokens=3000,
    )
