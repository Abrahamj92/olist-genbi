import json
import math
from pathlib import Path

from src.config import load_json, load_settings, make_athena, make_bedrock
from src.sql_generator import generate_sql
from src.sql_guard import validate_sql


def to_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compare_scalar_results(
    generated_df,
    reference_df,
    tolerance=0.01,
):
    """
    Compare one-row / one-value BI results.

    Column aliases do not need to match.
    We compare the actual business value.
    """

    if generated_df.shape != (1, 1):
        return False, (
            f"Generated result shape is "
            f"{generated_df.shape}, expected (1, 1)"
        )

    if reference_df.shape != (1, 1):
        return False, (
            f"Reference result shape is "
            f"{reference_df.shape}, expected (1, 1)"
        )

    generated_value = generated_df.iloc[0, 0]
    reference_value = reference_df.iloc[0, 0]

    generated_number = to_number(
        generated_value
    )

    reference_number = to_number(
        reference_value
    )

    # Numeric comparison
    if (
        generated_number is not None
        and reference_number is not None
    ):
        passed = math.isclose(
            generated_number,
            reference_number,
            rel_tol=1e-9,
            abs_tol=tolerance,
        )

        return passed, {
            "generated": generated_number,
            "reference": reference_number,
            "difference": abs(
                generated_number
                - reference_number
            ),
        }

    # Text fallback
    passed = (
        str(generated_value).strip()
        == str(reference_value).strip()
    )

    return passed, {
        "generated": generated_value,
        "reference": reference_value,
    }



def compare_table_results(generated_df, reference_df, tolerance=0.01):
    """
    OPTIONAL Olist improvement: compare small multi-row results
    (rankings / breakdowns). Column names are ignored; rows are
    compared after sorting, numbers with tolerance.
    """
    if generated_df.shape != reference_df.shape:
        return False, (
            f"Shape mismatch: generated {generated_df.shape}, "
            f"reference {reference_df.shape}"
        )

    def rows(df):
        out = []
        for record in df.itertuples(index=False):
            out.append(tuple(
                round(n, 2) if (n := to_number(v)) is not None else str(v).strip()
                for v in record
            ))
        return sorted(out, key=str)

    g_rows, r_rows = rows(generated_df), rows(reference_df)

    for g, r in zip(g_rows, r_rows):
        for gv, rv in zip(g, r):
            if isinstance(gv, float) and isinstance(rv, float):
                if not math.isclose(gv, rv, abs_tol=tolerance):
                    return False, {"generated_row": g, "reference_row": r}
            elif gv != rv:
                return False, {"generated_row": g, "reference_row": r}

    return True, {"rows_compared": len(g_rows)}


def compare_results(generated_df, reference_df, tolerance=0.01):
    if generated_df.shape == (1, 1) and reference_df.shape == (1, 1):
        return compare_scalar_results(generated_df, reference_df, tolerance)
    return compare_table_results(generated_df, reference_df, tolerance)


def main():

    settings = load_settings()
    semantic = load_json("config/semantic_layer.json")
    golden = load_json("config/reference_queries.json")
    golden_queries = golden["queries"] if isinstance(golden, dict) else golden

    bedrock = make_bedrock(settings)
    athena = make_athena(settings)

    total = len(golden_queries)
    passed_count = 0
    report = []

    print("\n==============================")
    print(" OLIST GENBI - GOLDEN QUERIES")
    print("==============================")

    for test in golden_queries:

        print("\n" + "=" * 60)
        print(f'{test["id"]} | {test["level"]} | {test["question"]}')
        print("=" * 60)

        row = {"id": test["id"], "question": test["question"]}

        try:
            generated = generate_sql(bedrock, test["question"], semantic)
            print("\nSemantic interpretation:")
            print(generated["interpretation"])
            row["interpretation"] = generated["interpretation"]

            # Governance test: the metric must be refused
            if test.get("expect_unavailable"):
                passed = generated.get("status") == "unavailable"
                row.update(
                    generated_sql=None,
                    result=generated.get("message"),
                    passed=passed,
                )
                print("\nExpected: metric NOT available")
                print("Got status:", generated.get("status"))
            else:
                generated_sql = generated["sql"]
                print("\nGenerated SQL:")
                print(generated_sql)

                validate_sql(generated_sql, settings["allowed_view"])
                print("\nSQL Guard: PASSED")

                generated_df, _ = athena.run(generated_sql)
                reference_df, _ = athena.run(test["reference_sql"])

                passed, details = compare_results(generated_df, reference_df)

                print("\nGenerated result:")
                print(generated_df.to_string(index=False))
                print("\nReference result:")
                print(reference_df.to_string(index=False))
                print("\nComparison:")
                print(details)

                row.update(
                    generated_sql=generated_sql,
                    generated=generated_df.to_dict(orient="records"),
                    reference=reference_df.to_dict(orient="records"),
                    details=details,
                    passed=passed,
                )

        except Exception as exc:  # keep running the battery
            passed = False
            row.update(passed=False, error=str(exc))
            print("\nERROR:", exc)

        if passed:
            passed_count += 1
            print("\nVALIDATION: ✅ PASS")
        else:
            print("\nVALIDATION: ❌ FAIL")

        report.append(row)

    print("\n==============================")
    print(" VALIDATION SUMMARY")
    print("==============================")
    print(f"Passed: {passed_count}/{total}")
    score = passed_count / total * 100 if total else 0
    print(f"Accuracy: {score:.1f}%")

    output = Path(__file__).resolve().parents[1] / "docs/golden_results.json"
    with output.open("w", encoding="utf-8") as f:
        json.dump(
            {"passed": passed_count, "total": total, "results": report},
            f, indent=2, ensure_ascii=False, default=str,
        )
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
