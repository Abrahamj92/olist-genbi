\
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_settings(path="config/settings.json"):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path

    if not path.exists():
        example = ROOT / "config/settings.example.json"
        raise FileNotFoundError(
            f"Missing {path}. Copy {example} to {path} and configure your AWS values."
        )

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def make_athena(settings):
    """Olist: build the Athena client from settings (optional aws_profile)."""
    from src.athena import AthenaClient

    return AthenaClient(
        region=settings["aws_region"],
        database=settings["athena_database"],
        output_s3=settings["athena_output_s3"],
        workgroup=settings.get("athena_workgroup", "primary"),
        profile_name=settings.get("aws_profile"),
    )


def make_bedrock(settings):
    """
    Olist: build the Bedrock client. bedrock_aws_profile allows using
    another AWS profile/account for Bedrock only (plan B if the main
    account has Bedrock quotas in 0).
    """
    if settings.get("llm_mode", "bedrock") == "offline":
        from src.offline_generator import OfflineLLM

        return OfflineLLM()

    from src.bedrock import BedrockClient

    return BedrockClient(
        region=settings.get("bedrock_region", settings["aws_region"]),
        model_id=settings["bedrock_model_id"],
        profile_name=settings.get("bedrock_aws_profile")
        or settings.get("aws_profile"),
    )
