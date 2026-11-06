# Quality Gate de `vw_olist_genbi_pedidos`

La vista se creó con `sql/01_create_genbi_view.sql` y se validó con `sql/02_quality_gate.sql`. Los resultados son reales, ejecutados en Athena.

| QG | Verificación | Resultado | Estado |
|---|---|---|---|
| QG1 | Grano y universo | 449 422 filas = 449 422 pedidos · 441 600 con reseña · 448 666 con líneas | PASA |
| QG2 | Conservación de medidas | Diferencia 0 en reseñas, líneas, reseñas bajas, precio y flete | PASA |
| QG3 | KPI oficiales desde la vista | KPI-1 = 15,21 % · KPI-2 = 15,25 % · KPI-3 = 3,72 | PASA (= valores registrados) |
| QG4 | Dimensiones vacías | 0 | PASA |
| QG5 | Cumplimiento del plazo | A tiempo 386 291 (KPI-1 8,96 %) · Tarde 52 466 (57,85 %) · No evaluable 2 843 (77,70 %) · Sin reseña 7 822 | PASA (suma 449 422) |
| QG6 | Categoría | Una 341 303 · Varias 107 363 · Sin líneas 756 | PASA |
| QG7 | Esquema | 32 columnas | PASA |

## Indicadores derivados (de QG5)

- **KPI-5, tasa de entrega tardía:** 52 466 / (386 291 + 52 466) = 11,96 %.
- **KPI-1 según el plazo:** 8,96 % a tiempo frente a 57,85 % con entrega tarde. Es una asociación, no una causa.

## Decisiones de diseño

- **Grano pedido.** Las dos facts se resumen por `order_id` antes de unirse, así que no se duplican reseñas.
- **Conteos incluidos.** La vista trae `n_resenas` y `n_resenas_bajas`, de modo que el KPI-2 se calcula sin error de grano.
- **Fechas de entrega.** Solo existen en `fact_resenas`, así que la entrega tardía solo es evaluable en pedidos con reseña.
- **Categoría.** Solo se atribuye a pedidos de una categoría (23,9 % de los pedidos tiene varias).
- **Origen de los datos.** `periodo_datos` sale del año, no de las vistas `_2016_2025`.
- **Datamart intacto.** No se modificó; solo se agregó una vista de consumo.
