# Modo respaldo (sin Amazon Bedrock)

## Por qué existe

- **Plan gratuito:** la cuenta 341936017120 tenía todas las cuotas de Bedrock en 0. AWS rechazó el aumento (caso 179397137900209): *"el acceso al modelo puede depender de la disponibilidad regional, el historial de la cuenta y los patrones de uso"*.
- **Plan de pago:** la cuenta se actualizó el 2026-11-06 y se volvió a pedir el aumento (caso 179398855200550, pendiente).

## Qué hace

`"llm_mode": "offline"` reemplaza solo las dos piezas que dependen del LLM:

1. **SQL.** Se arma con la métrica que resuelve la capa semántica (resolver), la dimensión pedida ("por región", "peor categoría", "por mes"), los filtros reconocidos (años 2016–2025, UF en mayúsculas, región, 2 o más vendedores, plazo, datos reales o simulados) y el orden del ranking (en KPI-1, KPI-2 y KPI-5, "peor" ordena de mayor a menor).
2. **Insight.** Es una plantilla con el valor mayor, el menor y la diferencia, tomados del resultado de Athena. No inventa cifras.

## Qué sigue siendo real

- Resolver y métrica no disponible
- SQL Guard (parser)
- Ejecución en Athena
- Golden queries
- Visualización
- Streamlit

## Limitaciones (declarar en la exposición)

- No interpreta preguntas libres como un LLM: solo entiende términos de la capa semántica.
- El draft semántico (script 02) y la validación humana del draft requieren Bedrock.
- Las golden queries en este modo validan las reglas, no la interpretación de la IA.

## Cómo volver a Bedrock

1. AWS aprueba la cuota y "Hola" responde en el Playground.
2. En `config/settings.json`, poner `"llm_mode": "bedrock"`.
3. Ejecutar los scripts 02 → 06 y volver a correr las golden queries.
