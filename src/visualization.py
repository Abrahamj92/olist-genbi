\
import pandas as pd
import plotly.express as px


def coerce_numeric(df):
    result = df.copy()
    for column in result.columns:
        try:
            converted = pd.to_numeric(result[column])
            # Keep conversion only when it is meaningfully numeric.
            if converted.notna().sum() > 0:
                result[column] = converted
        except (TypeError, ValueError):
            pass
    return result


def choose_chart(df):
    """
    Deterministic, intentionally simple BI visualization logic.
    Bedrock does NOT generate executable Python.
    """
    df = coerce_numeric(df)

    if df.empty:
        return None, "No data"

    if len(df.columns) < 2 or len(df) == 1:
        return None, "KPI/table"

    numeric = list(df.select_dtypes(include="number").columns)
    non_numeric = [c for c in df.columns if c not in numeric]

    if not numeric:
        return None, "Table"

    # Basic time-series heuristic
    date_candidates = [
        c for c in df.columns
        if any(k in c.lower() for k in (
            "date", "month", "year", "anio", "fecha", "trimestre"
        )) or c.lower() == "mes"
    ]
    # Olist: the measure is the last numeric column that is not a time column
    # (anio / mes are numeric and must not be used as Y).
    measures = [c for c in numeric if c not in date_candidates]
    if not measures:
        return None, "Table"
    y = measures[-1]
    non_numeric = [c for c in df.columns if c != y and c not in date_candidates]

    if date_candidates:
        x = date_candidates[0]
        return px.line(df, x=x, y=y, markers=True), "Line"

    if non_numeric:
        x = non_numeric[0]
        df[x] = df[x].astype(str)
        return px.bar(df, x=x, y=y), "Bar"

    return None, "Table"
