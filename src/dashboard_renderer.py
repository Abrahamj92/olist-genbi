"""Deterministic Streamlit + Plotly dashboard renderer (adaptado a Olist)."""
import pandas as pd
import plotly.express as px
import streamlit as st


PCT_METRICS = {"kpi1_pct_pedidos_bajos", "kpi2_pct_resenas_bajas", "kpi5_tasa_entrega_tardia",
               "kpi8_flete_sobre_precio"}
MONEY_METRICS = {"ventas_productos", "flete_total"}
COUNT_METRICS = {"pedidos", "pedidos_con_resena", "resenas"}


def olist_amount(value, metric, semantic):
    """Olist: los KPI-1/2/5/8 ya vienen en escala 0-100 (100.0 * ...)."""
    symbol = semantic.get("business_context", {}).get("currency_symbol", "")
    value = float(value)
    if metric in PCT_METRICS:
        return f"{value:,.2f} %"
    if metric in MONEY_METRICS:
        return f"{symbol} {value:,.2f}"
    if metric in COUNT_METRICS:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _format_value(value, metric, semantic):
    if pd.isna(value):
        return "Sin datos"
    return olist_amount(value, metric, semantic)


def render_component(result, semantic, show_details=False):
    component = result["component"]
    if component["type"] != "kpi":
        st.markdown(f"**{component['title']}**")
    if result["error"]:
        st.error(f"No se pudo ejecutar: {result['error']}")
        return
    df = result["data"]
    if df.empty or "metric_value" not in df:
        st.info("No existen resultados para este componente.")
        return
    kind = component["type"]
    if kind == "kpi":
        value = df.iloc[0]["metric_value"]
        st.metric(component["title"], _format_value(value, component["metric"], semantic))
    elif kind == "table":
        st.dataframe(df.rename(columns={
            "dimension_value": component["dimension"],
            "metric_value": component["metric"],
        }), hide_index=True, use_container_width=True)
    elif kind == "bar":
        chart_df = df.dropna(subset=["metric_value"]).sort_values("metric_value", ascending=True)
        fig = px.bar(
            chart_df, x="metric_value", y="dimension_value", orientation="h",
            labels={"dimension_value": component["dimension"],
                    "metric_value": component["metric"]},
        )
        fig.update_traces(marker_color="#c92e43", hovertemplate="%{y}: %{x:,.2f}<extra></extra>")
        fig.update_layout(
            height=max(300, min(560, 55 * len(chart_df) + 100)),
            margin=dict(l=5, r=15, t=20, b=25),
            showlegend=False, yaxis_title=None, xaxis_title=component["metric"],
        )
        st.plotly_chart(fig, use_container_width=True, key=component["id"])
    elif kind == "line":
        chart_df = df.sort_values("dimension_value").copy()
        chart_df["dimension_value"] = chart_df["dimension_value"].astype(str)
        fig = px.line(
            chart_df, x="dimension_value", y="metric_value",
            markers=True, labels={"dimension_value": component["dimension"],
                                  "metric_value": component["metric"]},
        )
        fig.update_traces(line_color="#c92e43", marker_color="#c92e43")
        fig.update_layout(
            height=350, margin=dict(l=5, r=15, t=20, b=25),
            xaxis_title=None, yaxis_title=component["metric"],
        )
        st.plotly_chart(fig, use_container_width=True, key=component["id"])
    if show_details:
        with st.expander(f"SQL y metadatos: {component['id']}"):
            st.code(result["sql"], language="sql")
            st.json(result["metadata"])


def render_dashboard(spec, results, semantic, show_details=False):
    st.header(spec["title"])
    successful = sum(item["error"] is None for item in results)
    st.caption(f"Componentes ejecutados: {successful}/{len(results)} · "
               "Resultados procedentes de Amazon Athena")
    # Layout depends on JSON component order and count; no hardcoded KPI names.
    kpis = [item for item in results if item["component"]["type"] == "kpi"]
    others = [item for item in results if item["component"]["type"] != "kpi"]
    for offset in range(0, len(kpis), 4):
        group = kpis[offset: offset + 4]
        for col, result in zip(st.columns(len(group)), group):
            with col:
                render_component(result, semantic, show_details)
    for offset in range(0, len(others), 2):
        group = others[offset: offset + 2]
        for col, result in zip(st.columns(len(group)), group):
            with col:
                render_component(result, semantic, show_details)
