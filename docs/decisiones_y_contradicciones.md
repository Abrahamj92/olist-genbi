# Decisiones y contradicciones resueltas

| # | Tema | Evidencia | Decisión |
|---|---|---|---|
| C1 | Numeración de los KPI | Un documento antiguo numeraba KPI 1 = % reseñas bajas. El informe v4 y el taller usan KPI-1 = % pedidos bajos y KPI-2 = % reseñas bajas | Se usa la numeración del informe v4 y del taller |
| C2 | `customer_unique_id` | Existe en la fuente y en `olist_raw.customers`. No existe en `olist_master` (E1.3) | **Opción C:** compradores únicos = métrica no disponible |
| C3 | Total de pedidos | RAW 449 441 · MASTER 449 422 · con reseña 441 600 | Universo GenBI = 449 422 (MASTER) |
| C4 | Líneas y reseñas | 484 704 / 356 497 = solo 2019–2025; 597 354 / 455 721 = 2016–2025 | Se usa MASTER 2016–2025 |
| C5 | Datos reales vs. simulados | 2016–2018 real; 2019–2025 simulado | Columna `periodo_datos` |
| C6 | Vistas `_2016_2025` | Duplican 2019–2025 (1 082 058 líneas) | No se usan; quedan fuera del modelo oficial |
| C7 | Categoría principal | Una reseña califica el pedido completo; el 23,9 % de los pedidos tiene varias categorías | `categoria_unica` solo para pedidos de una categoría |

## Opción C: compradores únicos no disponibles

- **Regla.** "Clientes" no se interpreta como pedidos.
- **Implementación en Python.** `src/sql_generator.py` (`unavailable_metrics`) devuelve `status = "unavailable"` y no llama a Bedrock ni a Athena.
- **Declaración en el JSON.** `config/semantic_layer.json → unavailable_metrics.compradores_unicos`.
- **Pruebas.** `tests/test_semantic_resolver.py` y la golden query GQ11.
- **Mejora futura (fuera de esta entrega).** Una `dim_cliente` con `customer_unique_id`, cargada por el pipeline incremental.
