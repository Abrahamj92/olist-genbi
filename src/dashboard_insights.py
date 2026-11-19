"""Executive insights: deterministic facts from Athena plus optional Bedrock curation.

Bedrock never invents numbers or writes free-form claims: it selects evidence IDs.
"""
import json
import math

import pandas as pd


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _amount(value, metric, semantic):
    from src.dashboard_renderer import olist_amount
    return olist_amount(value, metric, semantic)


def evidence_from_results(results, semantic):
    """Only use actual queried DataFrames; skip failed, empty and null results."""
    evidence = []
    # A segment share is reported only when its complete group sum reconciles
    # with the corresponding unfiltered KPI in the same dashboard.
    totals = {}
    for item in results:
        if item.get("error"):
            continue
        frame = item.get("data")
        if frame is None or frame.empty or "metric_value" not in frame:
            continue
        component = item["component"]
        if component["type"] == "kpi":
            value = _number(frame.iloc[0]["metric_value"])
            if value is not None:
                totals[component["metric"]] = value
    for result in results:
        if result.get("error") or result.get("data") is None:
            continue
        frame = result["data"]
        if frame.empty or "metric_value" not in frame:
            continue
        component = result["component"]
        metric = component["metric"]
        kind = component["type"]
        if kind == "kpi":
            value = _number(frame.iloc[0]["metric_value"])
            if value is None:
                continue
            evidence.append({
                "id": component["id"], "title": component["title"],
                "fact": f"{component['title']}: {_amount(value, metric, semantic)}.",
                "source": component["id"],
            })
            continue
        if "dimension_value" not in frame or not frame["metric_value"].notna().any():
            continue
        valid = frame[["dimension_value", "metric_value"]].copy()
        valid["metric_value"] = pd.to_numeric(valid["metric_value"], errors="coerce")
        valid = valid.dropna(subset=["dimension_value", "metric_value"])
        if valid.empty:
            continue
        if component.get("dimension") in {"anio", "mes"}:
            valid = valid.sort_values("dimension_value")
            top = valid.loc[valid["metric_value"].idxmax()]
            label = str(top["dimension_value"])
            fact = (
                f"El mayor valor {'anual' if component.get('dimension') == 'anio' else 'mensual'} observado de {component['title'].lower()} "
                f"corresponde a {label}: {_amount(float(top['metric_value']), metric, semantic)}. "
                "2019-2025 son datos simulados y no se ha verificado la completitud del periodo."
            )
        else:
            top = valid.loc[valid["metric_value"].idxmax()]
            top_value = float(top["metric_value"])
            fact = (
                f"Lidera {component['title'].lower()}: {top['dimension_value']} "
                f"con {_amount(top_value, metric, semantic)}."
            )
            # Only show percent of whole if every observed group reconciles
            # with the KPI. A LIMIT or missing group can invalidate the share.
            total = totals.get(metric)
            group_sum = float(valid["metric_value"].sum())
            if (total is not None and total > 0
                    and math.isclose(group_sum, total, rel_tol=0.00001, abs_tol=0.02)):
                fact += f" Representa el {100 * top_value / total:.1f}% del total validado."
        evidence.append({
            "id": component["id"], "title": component["title"],
            "fact": fact, "source": component["id"],
        })
    return evidence


INSIGHTS_SYSTEM_PROMPT = """Eres analista de Business Intelligence.
Recibes hechos de Athena con identificadores y debes seleccionar hasta 4 hechos útiles
para un resumen ejecutivo. Devuelve SOLO JSON: {"selected_ids":["id1","id2"]}.
Elige exclusivamente IDs presentes, sin inventarlos ni escribir resultados, números,
comentarios adicionales, causas, predicciones o métricas.
Prioriza diversidad: al menos un desglose dimensional o temporal si existe. Evita seleccionar solamente KPIs que repitan las tarjetas visibles. No repitas IDs.
"""


def curate_insights(bedrock_client, business_request, evidence):
    """Model selects fact IDs only; displayed text is always calculated in Python."""
    if not evidence:
        return []
    if bedrock_client is None:
        return evidence[:4]
    response = bedrock_client.ask_json(
        system_prompt=INSIGHTS_SYSTEM_PROMPT,
        user_prompt=(
            "SOLICITUD ORIGINAL:\n" + str(business_request or "Resumen ejecutivo")[:1500]
            + "\nHECHOS VERIFICADOS:\n"
            + json.dumps(evidence, ensure_ascii=False, default=str)
        ),
        max_tokens=450,
    )
    selected = response.get("selected_ids") if isinstance(response, dict) else None
    if not isinstance(selected, list) or not selected or len(selected) > 4:
        raise ValueError("Bedrock did not return valid evidence identifiers.")
    indexed = {item["id"]: item for item in evidence}
    if any(not isinstance(key, str) or key not in indexed for key in selected):
        raise ValueError("Bedrock selected unverified evidence.")
    seen = set()
    final = []
    for key in selected:
        if key not in seen:
            final.append(indexed[key])
            seen.add(key)
    # A governed summary should not consist exclusively of KPI repeats when
    # valid categorical or temporal comparisons are available.
    breakdown = [item for item in evidence if item["fact"].startswith(("Lidera ", "El mayor valor"))]
    if breakdown and not any(item["id"] in {x["id"] for x in breakdown} for item in final):
        chosen = breakdown[0]
        if len(final) == 4:
            final[-1] = chosen
        else:
            final.append(chosen)
    return final
