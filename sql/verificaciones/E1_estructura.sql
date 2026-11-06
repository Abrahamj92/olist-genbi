-- ============================================================
-- OLIST GENBI - ETAPA 1: VERIFICACION DE ESTRUCTURA DEL DATAMART
-- Base: olist_master   (ejecutar en Athena, una consulta a la vez)
-- Objetivo: confirmar tablas, columnas, granos y relaciones
-- ANTES de calcular indicadores o construir la vista GenBI.
--
-- Orden: E1.1 -> E1.2 son obligatorias primero.
-- Las consultas E1.3 en adelante usan nombres de columnas tomados
-- de nuestros documentos previos (informe v4). Si E1.2 muestra
-- otros nombres, NO las ejecutes: comparteme E1.2 y las ajusto.
-- ============================================================


-- ------------------------------------------------------------
-- E1.1 Inventario de tablas y vistas de olist_master
-- Verifica: que existan las 7 tablas del modelo y la vista
-- v_resena_pedido, y si hay objetos adicionales (ej. dim_cliente).
-- ------------------------------------------------------------
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_schema = 'olist_master'
ORDER BY table_type, table_name;


-- ------------------------------------------------------------
-- E1.2 Diccionario de columnas (exportar a CSV)
-- Verifica: nombres y tipos reales de cada columna.
-- Es la base para escribir la vista GenBI sin suponer nombres.
-- ------------------------------------------------------------
SELECT table_name, ordinal_position, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'olist_master'
ORDER BY table_name, ordinal_position;


-- ------------------------------------------------------------
-- E1.3 Identificadores de cliente en MASTER y en RAW
-- Verifica: en que capa existe customer_id / customer_unique_id.
-- Resuelve la decision A/B/C sobre "compradores".
-- ------------------------------------------------------------
SELECT table_schema, table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema IN ('olist_master', 'olist_raw')
  AND (column_name LIKE '%customer%' OR column_name LIKE '%cliente%')
ORDER BY table_schema, table_name, column_name;


-- ------------------------------------------------------------
-- E1.4 Filas por tabla
-- Verifica: volumen actual de cada tabla. Se compara con lo
-- registrado (Q7): fact_resenas 455 721; fact_lineas_pedido 597 354;
-- dim_fecha 3 676; dim_geografia 14 995; dim_producto 32 951;
-- dim_vendedor 3 095; dim_estado_pedido 8.
-- ------------------------------------------------------------
SELECT 'fact_resenas' AS tabla, COUNT(*) AS filas FROM olist_master.fact_resenas
UNION ALL SELECT 'fact_lineas_pedido', COUNT(*) FROM olist_master.fact_lineas_pedido
UNION ALL SELECT 'dim_fecha',          COUNT(*) FROM olist_master.dim_fecha
UNION ALL SELECT 'dim_geografia',      COUNT(*) FROM olist_master.dim_geografia
UNION ALL SELECT 'dim_producto',       COUNT(*) FROM olist_master.dim_producto
UNION ALL SELECT 'dim_vendedor',       COUNT(*) FROM olist_master.dim_vendedor
UNION ALL SELECT 'dim_estado_pedido',  COUNT(*) FROM olist_master.dim_estado_pedido
UNION ALL SELECT 'v_resena_pedido',    COUNT(*) FROM olist_master.v_resena_pedido;


-- ------------------------------------------------------------
-- E1.5 Grano de fact_resenas: (review_id, order_id)
-- Verifica: que no haya filas duplicadas en el grano, cuantos
-- pedidos distintos tiene y cuantos review_id se repiten.
-- Esperado: duplicados_grano = 0.
-- ------------------------------------------------------------
SELECT COUNT(*)                                                AS filas,
       COUNT(DISTINCT order_id)                                AS pedidos_distintos,
       COUNT(DISTINCT review_id)                               AS review_id_distintos,
       COUNT(*) - COUNT(DISTINCT review_id || '|' || order_id) AS duplicados_grano,
       COUNT_IF(order_id IS NULL OR review_id IS NULL)         AS llaves_nulas
FROM olist_master.fact_resenas;


-- ------------------------------------------------------------
-- E1.6 Grano de fact_lineas_pedido: (order_id, order_item_id)
-- Verifica: unicidad del grano y pedidos distintos con lineas.
-- Esperado: duplicados_grano = 0.
-- ------------------------------------------------------------
SELECT COUNT(*)                                                       AS filas,
       COUNT(DISTINCT order_id)                                       AS pedidos_distintos,
       COUNT(*) - COUNT(DISTINCT order_id || '|' || CAST(order_item_id AS varchar)) AS duplicados_grano,
       COUNT_IF(order_id IS NULL OR order_item_id IS NULL)            AS llaves_nulas,
       MAX(order_item_id)                                             AS max_item
FROM olist_master.fact_lineas_pedido;


-- ------------------------------------------------------------
-- E1.7 Grano de v_resena_pedido: 1 fila por pedido
-- Verifica: que la vista no duplique pedidos y que tenga los
-- mismos pedidos que fact_resenas (comparar con E1.5).
-- Esperado: filas = pedidos_distintos.
-- ------------------------------------------------------------
SELECT COUNT(*)                 AS filas,
       COUNT(DISTINCT order_id) AS pedidos_distintos,
       SUM(n_resenas)           AS resenas_sumadas
FROM olist_master.v_resena_pedido;


-- ------------------------------------------------------------
-- E1.8 Universo de pedidos entre las dos facts
-- Verifica: cuantos pedidos tienen solo resena, solo lineas o
-- ambas. Define que cubre la vista GenBI (FULL OUTER JOIN).
-- ------------------------------------------------------------
SELECT COUNT(*)                                         AS pedidos_master,
       COUNT_IF(r.order_id IS NOT NULL AND l.order_id IS NOT NULL) AS con_resena_y_lineas,
       COUNT_IF(r.order_id IS NOT NULL AND l.order_id IS NULL)     AS solo_resena,
       COUNT_IF(r.order_id IS NULL AND l.order_id IS NOT NULL)     AS solo_lineas
FROM (SELECT DISTINCT order_id FROM olist_master.fact_resenas) r
FULL OUTER JOIN (SELECT DISTINCT order_id FROM olist_master.fact_lineas_pedido) l
  ON r.order_id = l.order_id;


-- ------------------------------------------------------------
-- E1.9 Unicidad de llaves en dimensiones
-- Verifica: que cada surrogate key sea unica (si no, los JOIN
-- duplican filas). Esperado: todas las diferencias = 0.
-- ------------------------------------------------------------
SELECT 'dim_fecha' AS dim, COUNT(*) - COUNT(DISTINCT fecha_key) AS llaves_repetidas FROM olist_master.dim_fecha
UNION ALL SELECT 'dim_geografia',     COUNT(*) - COUNT(DISTINCT geografia_key)     FROM olist_master.dim_geografia
UNION ALL SELECT 'dim_producto',      COUNT(*) - COUNT(DISTINCT producto_key)      FROM olist_master.dim_producto
UNION ALL SELECT 'dim_vendedor',      COUNT(*) - COUNT(DISTINCT vendedor_key)      FROM olist_master.dim_vendedor
UNION ALL SELECT 'dim_estado_pedido', COUNT(*) - COUNT(DISTINCT estado_pedido_key) FROM olist_master.dim_estado_pedido;


-- ------------------------------------------------------------
-- E1.10 Integridad referencial de fact_resenas
-- Verifica: llaves de la fact sin fila en su dimension.
-- Esperado: 0 en todas (el -1 "No disponible" debe existir en la dim).
-- ------------------------------------------------------------
SELECT
  COUNT_IF(e.estado_pedido_key IS NULL) AS sin_estado,
  COUNT_IF(g.geografia_key     IS NULL) AS sin_geografia,
  COUNT_IF(fc.fecha_key        IS NULL) AS sin_fecha_compra,
  COUNT_IF(fe.fecha_key        IS NULL) AS sin_fecha_entrega,
  COUNT_IF(fs.fecha_key        IS NULL) AS sin_fecha_estimada
FROM olist_master.fact_resenas f
LEFT JOIN olist_master.dim_estado_pedido e ON f.estado_pedido_key          = e.estado_pedido_key
LEFT JOIN olist_master.dim_geografia     g ON f.geografia_cliente_key      = g.geografia_key
LEFT JOIN olist_master.dim_fecha        fc ON f.fecha_compra_key           = fc.fecha_key
LEFT JOIN olist_master.dim_fecha        fe ON f.fecha_entrega_cliente_key  = fe.fecha_key
LEFT JOIN olist_master.dim_fecha        fs ON f.fecha_entrega_estimada_key = fs.fecha_key;


-- ------------------------------------------------------------
-- E1.11 Integridad referencial de fact_lineas_pedido
-- Verifica: lineas sin producto, vendedor o geografia.
-- Esperado: 0 en todas.
-- ------------------------------------------------------------
SELECT
  COUNT_IF(p.producto_key  IS NULL) AS sin_producto,
  COUNT_IF(v.vendedor_key  IS NULL) AS sin_vendedor,
  COUNT_IF(g.geografia_key IS NULL) AS sin_geografia
FROM olist_master.fact_lineas_pedido f
LEFT JOIN olist_master.dim_producto  p ON f.producto_key          = p.producto_key
LEFT JOIN olist_master.dim_vendedor  v ON f.vendedor_key          = v.vendedor_key
LEFT JOIN olist_master.dim_geografia g ON f.geografia_cliente_key = g.geografia_key;


-- ------------------------------------------------------------
-- E1.12 Uso del miembro "No disponible" (-1) en las facts
-- Verifica: cuantas filas caen en -1 por cada llave. Define que
-- pedidos quedaran como "No disponible" en la vista GenBI.
-- ------------------------------------------------------------
SELECT
  COUNT_IF(geografia_cliente_key      = -1) AS geo_no_disp,
  COUNT_IF(estado_pedido_key          = -1) AS estado_no_disp,
  COUNT_IF(fecha_compra_key           = -1) AS compra_no_disp,
  COUNT_IF(fecha_entrega_cliente_key  = -1) AS entrega_no_disp,
  COUNT_IF(fecha_entrega_estimada_key = -1) AS estimada_no_disp,
  COUNT(*)                                  AS filas
FROM olist_master.fact_resenas;


-- ------------------------------------------------------------
-- E1.13 Consistencia de atributos del pedido dentro de fact_resenas
-- Verifica: que todas las resenas de un mismo pedido tengan el
-- mismo estado, geografia y fechas (justifica arbitrary() en
-- v_resena_pedido). Esperado: 0 en todas.
-- ------------------------------------------------------------
SELECT
  COUNT_IF(n_estado > 1) AS pedidos_estado_inconsistente,
  COUNT_IF(n_geo    > 1) AS pedidos_geo_inconsistente,
  COUNT_IF(n_compra > 1) AS pedidos_fecha_compra_inconsistente
FROM (
  SELECT order_id,
         COUNT(DISTINCT estado_pedido_key)     AS n_estado,
         COUNT(DISTINCT geografia_cliente_key) AS n_geo,
         COUNT(DISTINCT fecha_compra_key)      AS n_compra
  FROM olist_master.fact_resenas
  GROUP BY order_id
) t;


-- ------------------------------------------------------------
-- E1.14 Anos existentes segun fecha de compra
-- Verifica: periodos reales disponibles (para las Golden Queries)
-- y cuantos pedidos hay por ano. NO calcula indicadores.
-- ------------------------------------------------------------
SELECT d.anio,
       COUNT(DISTINCT f.order_id) AS pedidos_con_resena,
       COUNT(*)                   AS resenas
FROM olist_master.fact_resenas f
JOIN olist_master.dim_fecha d ON f.fecha_compra_key = d.fecha_key
GROUP BY d.anio
ORDER BY d.anio;


-- ------------------------------------------------------------
-- E1.15 Pedidos con varias categorias
-- Verifica: que proporcion de pedidos mezcla categorias.
-- Decide si la dimension "categoria_unica" es util.
-- (Si E1.2 muestra otro nombre de columna, reemplazar "categoria".)
-- ------------------------------------------------------------
SELECT COUNT(*)                     AS pedidos_con_lineas,
       COUNT_IF(n_categorias = 1)   AS una_categoria,
       COUNT_IF(n_categorias > 1)   AS varias_categorias,
       COUNT_IF(n_categorias = 0)   AS sin_categoria
FROM (
  SELECT f.order_id, COUNT(DISTINCT p.categoria) AS n_categorias
  FROM olist_master.fact_lineas_pedido f
  LEFT JOIN olist_master.dim_producto p ON f.producto_key = p.producto_key
  GROUP BY f.order_id
) t;
