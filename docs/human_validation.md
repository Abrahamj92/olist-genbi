# Validación humana del borrador de Bedrock

> **Estado: PENDIENTE.** Se completa después de ejecutar `scripts/02_build_semantic_draft.py`.
> El archivo `config/semantic_layer_draft.json` se guarda **sin editar**: es la evidencia.
> Solo se registra aquí lo que Bedrock propuso realmente. No se inventan propuestas.

## Cómo llenar esta tabla

Por cada dimensión, medida, sinónimo o ambigüedad del draft:

| Elemento | Propuesta de Bedrock (cita textual del draft) | Decisión | Regla de BI que lo justifica | Evidencia (Athena) |
|---|---|---|---|---|
| | | Aceptado / Corregido / Rechazado | | |

## Puntos que hay que revisar con atención

Estos riesgos se conocen por el modelo; hay que verificar si el draft los cometió:

- Si cuenta pedidos con `COUNT(order_id)` en vez de `COUNT(DISTINCT order_id)`.
- Si promedia `score_prom` o `review_score` sin respetar el grano, o si suma calificaciones.
- Si calcula el KPI-1 sobre todos los pedidos en lugar de solo los que tienen reseña (`tiene_resena`).
- Si propone una métrica de clientes a partir de algún identificador (no existe en la vista).
- Si incluye el flete dentro de "ventas".
- Si atribuye la insatisfacción a una categoría en pedidos de varias categorías.
- Si promedia porcentajes en lugar de usar SUM/SUM (KPI-8).

## Evidencia obligatoria del profesor

Al menos un caso en que la IA propuso algo y una regla de BI lo corrigió o rechazó.

- **Si el draft contiene un error real:** se documenta aquí con la cita, la corrección y el valor antes y después en Athena.
- **Si el draft no contiene errores:** se usa la demo de ambigüedad. Se ejecuta "¿Cuál es la peor región?" con la regla `peor o mejor` eliminada del JSON y luego restaurada. Se guardan ambas salidas y las capturas en `docs/capturas/`.
