# Verificación del datamart en Athena

Resultados ejecutados manualmente en la consola de Amazon Athena (`us-east-1`, workgroup `primary`) por el grupo. Las consultas están en `sql/verificaciones/`.

## Etapa 1: estructura (`E1_estructura.sql`)

| Consulta | Resultado real | Estado |
|---|---|---|
| E1.1 Inventario | 7 tablas + 3 vistas (`v_resena_pedido`, `v_lineas_2016_2025`, `v_resenas_2016_2025`) | OK |
| E1.2 Diccionario | Columnas idénticas al modelo de la PPT (diapositiva 12) | OK |
| E1.3 Identificadores de cliente | En `olist_master` no hay `customer_id` ni `customer_unique_id`; solo en `olist_raw.customers` | Decisión C |
| E1.4 Filas | fact_resenas 455 721 · fact_lineas_pedido 597 354 · dim_fecha 3 676 · dim_geografia 14 995 · dim_producto 32 951 · dim_vendedor 3 095 · dim_estado_pedido 8 · v_resena_pedido 441 600 | OK |
| E1.5 Grano fact_resenas | 455 721 filas · 441 600 pedidos · 454 907 review_id · 0 duplicados · 0 nulos | OK |
| E1.6 Grano fact_lineas_pedido | 597 354 filas · 448 666 pedidos · 0 duplicados · 0 nulos · máx. 21 ítems | OK |
| E1.7 v_resena_pedido | 441 600 filas = 441 600 pedidos · SUM(n_resenas) = 455 721 | OK |
| E1.8 Universo | 449 422 pedidos: 440 844 con reseña y líneas · 756 solo reseña · 7 822 solo líneas | OK |
| E1.9 Llaves de dimensiones | 0 repetidas | OK |
| E1.10 / E1.11 Integridad referencial | 0 huérfanos | OK |
| E1.12 Miembro -1 | Solo fecha_entrega_cliente: 2 865 reseñas | OK |
| E1.13 Atributos por pedido | 0 inconsistencias | OK |
| E1.14 Años | 2016–2025 presentes (2016: 324 pedidos con reseña) | OK |
| E1.15 Categorías | 341 303 pedidos de una categoría · 107 363 de varias | OK |
| E1.16 Definición de vistas | `v_resena_pedido` = definición del informe | OK |
| E1.17 origen_datos | `historico_real` 597 354 (2016–2025) + `simulado` 484 704 (2019–2025) | Ver nota |
| E1.18 Atributos entre facts | 0 diferencias en 440 844 pedidos comunes | OK |
| E1.19 Categoría especial | 610 productos con valor `sin_categoria` | OK |

**Nota sobre `v_lineas_2016_2025` y `v_resenas_2016_2025`:** duplican 2019–2025. `SELECT COUNT(*) FROM olist_master.v_lineas_2016_2025` = 1 082 058 líneas, cuando en realidad hay 597 354. Quedan fuera del modelo oficial y el proyecto no las usa.

## Conciliación RAW vs. MASTER

- RAW `orders`: 449 441 pedidos. MASTER: 449 422. Hay 19 pedidos que no entraron a ninguna fact.
- "7 841 pedidos sin reseña" (registro anterior) = 7 822 solo con líneas + 19.
- "775 pedidos sin productos" = 756 solo con reseña + 19.
- 2016–2018 suman 98 673 pedidos con reseña, igual que el informe original.
