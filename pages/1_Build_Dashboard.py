"""Olist — one-prompt governed dashboards, with an auditable manual mode (adaptado del repo docente)."""
import json

import streamlit as st

from src.config import load_json, load_settings, make_athena, make_bedrock
from src.dashboard_insights import curate_insights, evidence_from_results
from src.dashboard_planner import plan_dashboard
from src.dashboard_renderer import render_dashboard
from src.dashboard_runtime import execute_dashboard
from src.dashboard_validator import validate_dashboard

st.set_page_config(page_title="Olist | Prompt-to-Dashboard", page_icon="📊", layout="wide")
st.markdown(
    """
    <style>
      .block-container {padding-top: 1.6rem; max-width: 1500px;}
      div[data-testid="stMetric"] {border: 1px solid rgba(128,128,128,0.35);
        border-top: 3px solid #c82f42; border-radius: 12px; padding: 15px;}
      div[data-testid="stMetricLabel"] {font-weight: 600;}
      div[data-testid="stMetricValue"] {font-weight: 700;}
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("📊 Olist | Generative BI")
st.caption("Prompt-to-Dashboard · Amazon Bedrock · Semantic Layer · Amazon Athena · Streamlit/Plotly")

try:
    settings = load_settings()
    semantic = load_json("config/semantic_layer.json")
    commercial_example = load_json("config/dashboard_examples.json")
    executive_example = load_json("config/dashboard_executive.json")
except Exception as exc:
    st.error(f"Error de configuración: {exc}")
    st.stop()

if "dashboard_spec_text" not in st.session_state:
    st.session_state.dashboard_spec_text = json.dumps(executive_example, indent=2, ensure_ascii=False)
if "dashboard_output" not in st.session_state:
    st.session_state.dashboard_output = None

mode = st.radio("Modo", ["✨ Prompt-to-Dashboard", "🧩 Laboratorio JSON"], horizontal=True)
with st.expander("⚙️ Opciones y trazabilidad", expanded=False):
    details = st.checkbox("Mostrar SQL y metadatos Athena", value=False)
    include_insights = st.checkbox("Priorizar hallazgos con Bedrock", value=True)
    st.caption("El SQL procede solo de expresiones aprobadas; el modelo nunca genera código ejecutable.")

business_prompt = ""
execute_now = False
plan_only = False
if mode.startswith("✨"):
    scenarios = load_json("config/dashboard_scenarios.json")["scenarios"]
    if "business_prompt" not in st.session_state:
        st.session_state.business_prompt = scenarios[0]["prompt"]

    def _load_scenario():
        chosen = st.session_state.scenario_choice
        for item in scenarios:
            if item["title"] == chosen:
                st.session_state.business_prompt = item["prompt"]

    st.selectbox("Escenario de negocio", [x["title"] for x in scenarios],
                 key="scenario_choice", on_change=_load_scenario)
    business_prompt = st.text_area(
        "¿Qué dashboard necesita tu negocio?",
        height=110,
        max_chars=1500,
        key="business_prompt",
    )
    left, right = st.columns([2, 3])
    with left:
        execute_now = st.button(
            "✨ Generar dashboard completo",
            type="primary",
            use_container_width=True,
            disabled=not business_prompt.strip(),
        )
    with right:
        plan_only = st.button(
            "🔍 Solo planificar (sin consultar Athena)",
            use_container_width=True,
            disabled=not business_prompt.strip(),
        )
else:
    preset = st.selectbox(
        "Ejemplo preparado",
        ["Ejecutivo (7 componentes)", "Logístico (4 componentes)"],
    )
    if st.button("📋 Cargar ejemplo"):
        selected = executive_example if preset.startswith("Ejecutivo") else commercial_example
        st.session_state.dashboard_spec_text = json.dumps(selected, indent=2, ensure_ascii=False)
        st.session_state.dashboard_output = None
    st.caption("En este modo editas el JSON antes de ejecutar, sin usar Bedrock para planificar.")

with st.expander("🔧 Dashboard Specification JSON (auditoría)", expanded=mode.startswith("🧩")):
    if mode.startswith("🧩"):
        st.text_area(
            "Especificación declarativa editable",
            key="dashboard_spec_text",
            height=320,
        )
    else:
        st.code(st.session_state.dashboard_spec_text, language="json")

manual_run = False
if mode.startswith("🧩"):
    manual_run = st.button("🚀 Construir desde JSON", type="primary")

if execute_now or plan_only or manual_run:
    try:
        if execute_now or plan_only:
            with st.spinner("Bedrock está planificando el dashboard..."):
                bedrock = make_bedrock(settings)
                proposed = plan_dashboard(bedrock, business_prompt, semantic)
            # Save the fully validated, auditable plan for later JSON-mode edits.
            st.session_state.dashboard_spec_text = json.dumps(proposed, indent=2, ensure_ascii=False)
            plan = proposed
        else:
            plan = validate_dashboard(json.loads(st.session_state.dashboard_spec_text), semantic)

        if plan_only:
            st.session_state.dashboard_output = None
            st.success("Plan validado. Abre el JSON para inspeccionarlo; cambia al laboratorio para ejecutarlo.")
        else:
            athena = make_athena(settings)
            with st.spinner("Ejecutando consultas gobernadas en Athena..."):
                final_spec, results = execute_dashboard(plan, semantic, athena)

            evidence = evidence_from_results(results, semantic)
            selected = evidence[:4]
            warning = None
            if include_insights and evidence:
                try:
                    with st.spinner("Seleccionando hechos ejecutivos con Bedrock..."):
                        if not (execute_now or plan_only):
                            bedrock = make_bedrock(settings)
                        selected = curate_insights(
                            bedrock,
                            business_prompt if execute_now else final_spec["title"],
                            evidence,
                        )
                except Exception as exc:
                    warning = f"Selección con Bedrock no disponible; se usan hechos verificados: {exc}"
            st.session_state.dashboard_output = {
                "spec": final_spec,
                "results": results,
                "insights": selected,
                "warning": warning,
            }
    except Exception as exc:
        st.session_state.dashboard_output = None
        st.error(f"No se pudo generar un dashboard gobernado: {exc}")

output = st.session_state.dashboard_output
if output:
    st.divider()
    render_dashboard(output["spec"], output["results"], semantic, show_details=details)
    if output["insights"]:
        st.divider()
        st.subheader("💡 Executive Insights")
        st.caption("Hechos calculados en Athena y seleccionados por evidencia, no cifras generadas por IA.")
        if output["warning"]:
            st.warning(output["warning"])
        for item in output["insights"]:
            st.markdown(f"- **{item['title']}** — {item['fact']}")
        st.caption("No se infieren causas. La completitud temporal no se ha verificado.")
    if any(item["error"] for item in output["results"]):
        st.warning("Dashboard parcial: algunos componentes no pudieron ejecutarse.")
