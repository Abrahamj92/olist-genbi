\
from src.config import load_json, load_settings, make_athena, make_bedrock
from src.sql_generator import generate_sql
from src.sql_guard import validate_sql


def main():
    settings = load_settings()
    semantic = load_json("config/semantic_layer.json")

    bedrock = make_bedrock(settings)

    question = input("Business question: ").strip()
    result = generate_sql(bedrock, question, semantic)

    print("\nInterpretation:", result.get("interpretation"))

    if result.get("status") == "unavailable":
        print("METRIC NOT AVAILABLE:", result.get("message"))
        print("Alternatives:", ", ".join(result.get("alternatives", [])))
        print("Bedrock was NOT called.")
        return

    if result.get("status") != "ok":
        print("Clarification:", result.get("clarification_question"))
        return

    sql = result["sql"]
    print("\nGenerated SQL:\n", sql)

    validate_sql(sql, settings["allowed_view"])
    print("\nSQL Guard: PASSED")


if __name__ == "__main__":
    main()
