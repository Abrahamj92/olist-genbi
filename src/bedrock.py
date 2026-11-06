import json
import re

import boto3
from botocore.config import Config


class BedrockClient:
    def __init__(self, region, model_id, profile_name=None):
        # Olist: optional AWS profile, so Bedrock can use a different
        # account/profile than Athena (plan B while quotas are 0).
        self.model_id = model_id
        session = boto3.Session(profile_name=profile_name)

        self.client = session.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(
                connect_timeout=60,
                read_timeout=3600,
                retries={"max_attempts": 2},
            ),
        )

    def ask(
        self,
        system_prompt,
        user_prompt,
        max_tokens=1600,
        temperature=0,
    ):
        response = self.client.converse(
            modelId=self.model_id,
            system=[
                {
                    "text": system_prompt
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": user_prompt
                        }
                    ],
                }
            ],
            inferenceConfig={
                "maxTokens": max_tokens,
                "temperature": temperature,
                "topP": 0.9,
            },
        )

        return response["output"]["message"]["content"][0]["text"]

    def ask_json(
        self,
        system_prompt,
        user_prompt,
        max_tokens=2200,
    ):
        text = self.ask(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=0,
        )

        try:
            return extract_json(text)

        except Exception as first_error:
            print("\n--- BEDROCK RAW RESPONSE ---")
            print(repr(text))
            print("--- END RAW RESPONSE ---\n")

            repair_prompt = f"""
The following response was expected to be valid JSON but it was not.

ORIGINAL RESPONSE:
{text}

Return ONLY the corrected JSON object.

Rules:
- Return valid JSON.
- Do not use markdown.
- Do not use code fences.
- Do not explain anything.
- Preserve the original meaning.
"""

            repaired = self.ask(
                system_prompt=(
                    "You are a JSON formatter. "
                    "Return valid JSON only."
                ),
                user_prompt=repair_prompt,
                max_tokens=max_tokens,
                temperature=0,
            )

            try:
                return extract_json(repaired)

            except Exception as repair_error:
                print("\n--- BEDROCK REPAIRED RESPONSE ---")
                print(repr(repaired))
                print("--- END REPAIRED RESPONSE ---\n")

                raise ValueError(
                    "Bedrock returned invalid JSON and "
                    "the repair attempt also failed."
                ) from repair_error


def extract_json(text):
    """
    Extract a JSON object from a Bedrock response.

    Supports:
    - Pure JSON
    - JSON wrapped in Markdown fences
    - Additional text before or after the JSON object
    """

    if text is None:
        raise ValueError("Bedrock returned None instead of text.")

    cleaned = text.strip()

    if not cleaned:
        raise ValueError("Bedrock returned an empty response.")

    # Remove Markdown code fences if present.
    if cleaned.startswith("```"):
        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned,
        )

        cleaned = cleaned.strip()

    # First try: response is already valid JSON.
    try:
        return json.loads(cleaned)

    except json.JSONDecodeError:
        pass

    # Second try: find the first complete-looking JSON object.
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            f"No JSON object found in Bedrock response: {cleaned!r}"
        )

    json_candidate = cleaned[start : end + 1]

    try:
        return json.loads(json_candidate)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON returned by Bedrock: {json_candidate!r}"
        ) from exc