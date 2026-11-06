\
import json
from pathlib import Path

from src.config import load_json, load_settings, make_athena, make_bedrock
from src.profiler import GenBIProfiler, save_profile


ROOT = Path(__file__).resolve().parents[1]


def main():
    settings = load_settings()
    context = load_json("config/business_context.json")

    athena = make_athena(settings)

    profiler = GenBIProfiler(
        athena_client=athena,
        database=settings["athena_database"],
        view_name=settings["allowed_view"],
    )

    profile = profiler.build_profile(
        business_context=context,
        sample_limit=8,
    )

    output = ROOT / "config/dataset_profile.json"
    save_profile(profile, output)
    print(f"Created: {output}")


if __name__ == "__main__":
    main()
