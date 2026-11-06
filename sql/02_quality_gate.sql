-- ============================================================
-- OLIST GENBI - QUALITY GATE DE LA VISTA vw_olist_genbi_pedidos
-- Regla: si alguna verificacion falla, NO se continua con el
-- profiling (scripts/01_profile.py) hasta corregir la vista.
-- Valores esperados: los verificados en las Etapas 1 y 2 en Athena.
-- ============================================================


-- ------------------------------------------------------------
-- QG1 Grano y universo
-- Esperado: filas = pedidos_distintos = 449 422 (E1.8)
--           con_resena = 441 600 (E1.7) ; con_lineas = 448 666 (E1.6)
-- ------------------------------------------------------------
SELECT COUNT(*)                  AS filas,
       COUNT(DISTINCT order_id)  AS pedidos_distintos,
       SUM(tiene_resena)         AS con_resena,
       SUM(tiene_lineas)         AS con_lineas
FROM olist_master.vw_olist_genbi_pedidos;


-- ------------------------------------------------------------
-- QG2 Conservacion de medidas (vista vs facts)
-- Esperado: diferencias = 0 (precio y flete con tolerancia 0,01)
-- ------------------------------------------------------------
SELECT v.resenas  - f.resenas                     AS dif_resenas,
       v.items    - l.items                       AS dif_lineas,
       ROUND(v.precio - l.precio, 2)              AS dif_precio,
       ROUND(v.flete  - l.flete, 2)               AS dif_flete,
       v.resenas_bajas - f.resenas_bajas          AS dif_resenas_bajas
FROM (SELECT SUM(n_resenas) AS resenas, SUM(n_resenas_bajas) AS resenas_bajas,
             SUM(n_items) AS items, SUM(precio) AS precio, SUM(flete) AS flete
      FROM olist_master.vw_olist_genbi_pedidos) v
CROSS JOIN (SELECT COUNT(*) AS resenas, COUNT_IF(review_score <= 2) AS resenas_bajas
            FROM olist_master.fact_resenas) f
CROSS JOIN (SELECT COUNT(*) AS items, SUM(price) AS precio, SUM(freight_value) AS flete
            FROM olist_master.fact_lineas_pedido) l;


-- ------------------------------------------------------------
-- QG3 KPI oficiales desde la vista vs desde el datamart
-- Esperado: cada par igual (comparar con E2.1 y E2.2)
-- ------------------------------------------------------------
SELECT ROUND(100.0 * SUM(pedido_bajo) / NULLIF(SUM(tiene_resena), 0), 2)    AS kpi1_vista,
       ROUND(100.0 * SUM(n_resenas_bajas) / NULLIF(SUM(n_resenas), 0), 2)   AS kpi2_vista,
       ROUND(AVG(score_prom), 2)                                            AS kpi3_vista
FROM olist_master.vw_olist_genbi_pedidos;


-- ------------------------------------------------------------
-- QG4 Dimensiones sin valor (no deberian existir: E1.10 / E1.11)
-- Esperado: 0 en todas
-- ------------------------------------------------------------
SELECT COUNT_IF(anio IS NULL)            AS sin_anio,
       COUNT_IF(estado_pedido IS NULL)   AS sin_estado_pedido,
       COUNT_IF(estado_cliente IS NULL)  AS sin_estado_cliente,
       COUNT_IF(region_cliente IS NULL)  AS sin_region,
       COUNT_IF(categoria_unica IS NULL) AS sin_categoria_unica
FROM olist_master.vw_olist_genbi_pedidos;


-- ------------------------------------------------------------
-- QG5 Entrega tardia: vista vs calculo directo (comparar con E2.7)
-- ------------------------------------------------------------
SELECT cumplimiento_plazo,
       COUNT(*)                                                        AS pedidos,
       ROUND(100.0 * SUM(pedido_bajo) / NULLIF(SUM(tiene_resena), 0), 2) AS kpi1_pct
FROM olist_master.vw_olist_genbi_pedidos
GROUP BY cumplimiento_plazo
ORDER BY pedidos DESC;


-- ------------------------------------------------------------
-- QG6 Categoria: vista vs E1.15 / E2.10
-- Esperado: Una categoria + Varias categorias = 448 666 ;
--           Varias categorias = 107 363
-- ------------------------------------------------------------
SELECT tipo_pedido_categoria, COUNT(*) AS pedidos
FROM olist_master.vw_olist_genbi_pedidos
GROUP BY tipo_pedido_categoria;


-- ------------------------------------------------------------
-- QG7 Esquema final de la vista (para dataset_profile y la capa semantica)
-- ------------------------------------------------------------
SELECT ordinal_position, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'olist_master'
  AND table_name   = 'vw_olist_genbi_pedidos'
ORDER BY ordinal_position;
