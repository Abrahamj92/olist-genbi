from src.config import load_json, load_settings, make_athena, make_bedrock
from src.sql_generator import generate_sql
from src.sql_guard import validate_sql


def main():

    settings = load_settings()
    semantic = load_json(
        "config/semantic_layer.json"
    )

    bedrock = make_bedrock(settings)

    athena = make_athena(settings)

    question = input(
        "Business question: "
    ).strip()

    # -----------------------------------------
    # 1. Natural Language → SQL
    # -----------------------------------------

    result = generate_sql(
        bedrock,
        question,
        semantic,
    )


    if result.get("status") == "unavailable":
        print("\nInterpretation:", result["interpretation"])
        print("\nMETRIC NOT AVAILABLE:", result["message"])
        print("Alternatives:", ", ".join(result["alternatives"]))
        print("\nBedrock SQL generation and Athena were NOT called.")
        return

    if result.get("status") == "clarification":
        print("\nCLARIFICATION:", result.get("clarification_question"))
        return

    sql = result["sql"]

    print("\nInterpretation:")
    print(result["interpretation"])

    print("\nMetric:")
    print(result["metric_used"])

    print("\nGenerated SQL:")
    print(sql)

    # -----------------------------------------
    # 2. SQL Safety Gate
    # -----------------------------------------

    validate_sql(
        sql,
        settings["allowed_view"],
    )

    print("\nSQL Guard: PASSED")

    # -----------------------------------------
    # 3. Execute Athena
    # -----------------------------------------

    print("\nExecuting in Athena...")

    df, metadata = athena.run(sql)

    # -----------------------------------------
    # 4. Results
    # -----------------------------------------

    print("\n--- RESULT ---")
    print(df.to_string(index=False))

    print("\n--- ATHENA METADATA ---")

    print(
        "Query ID:",
        metadata["query_execution_id"],
    )

    print(
        "Execution time (ms):",
        metadata["total_execution_ms"],
    )

    scanned = metadata.get(
        "data_scanned_bytes"
    )

    if scanned is not None:
        scanned_mb = scanned / 1024 / 1024

        print(
            "Data scanned (MB):",
            round(scanned_mb, 4),
        )


if __name__ == "__main__":
    main()