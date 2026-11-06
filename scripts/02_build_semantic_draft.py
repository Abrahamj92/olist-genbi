\
import json
from pathlib import Path

from src.config import load_json, load_settings, make_athena, make_bedrock
from src.semantic_builder import generate_semantic_draft


ROOT = Path(__file__).resolve().parents[1]


def main():
    settings = load_settings()
    profile = load_json("config/dataset_profile.json")

    bedrock = make_bedrock(settings)

    draft = generate_semantic_draft(bedrock, profile)

    output = ROOT / "config/semantic_layer_draft.json"
    with output.open("w", encoding="utf-8") as f:
        json.dump(draft, f, indent=2, ensure_ascii=False)

    print(f"Created: {output}")
    print()
    print("NEXT STEP: Human validation.")
    print("Do NOT use the draft as the approved semantic layer without review.")


if __name__ == "__main__":
    main()
