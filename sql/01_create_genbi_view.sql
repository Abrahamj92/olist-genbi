-- ============================================================
-- OLIST GENBI - VISTA ANALITICA PARA GENBI
-- Grano: 1 fila = 1 pedido (order_id) presente en olist_master
--        (con resena, con lineas o con ambas).
-- Fuentes: v_resena_pedido, fact_resenas, fact_lineas_pedido y dimensiones.
-- NO usa v_lineas_2016_2025 ni v_resenas_2016_2025 (duplican 2019-2025).
-- No modifica el datamart: solo crea una vista de consumo.
--
-- Reglas de construccion:
--  * Cada fact se resume por order_id ANTES de unirse (no se duplica).
--  * Atributos del pedido: COALESCE resena / lineas (E1.18: 0 diferencias).
--  * Dimensiones con LEFT JOIN para no perder pedidos.
--  * Fechas de entrega solo existen en fact_resenas: la entrega tardia
--    solo es evaluable en pedidos con resena y ambas fechas <> -1.
--  * Categoria: solo se atribuye si el pedido tiene UNA categoria.
--  * Compradores (customer_unique_id): NO incluido; decision pendiente
--    (solo existe en olist_raw).
-- ============================================================

CREATE OR REPLACE VIEW olist_master.vw_olist_genbi_pedidos AS
SELECT
    -- Llave
    u.order_id

    -- Tiempo (fecha de compra)
  , fc.fecha                                               AS fecha_compra
  , fc.anio                                                AS anio
  , fc.mes                                                 AS mes
  , fc.nombre_mes                                          AS nombre_mes
  , fc.trimestre                                           AS trimestre
  , CAST(fc.anio AS varchar) || '-' || lpad(CAST(fc.mes AS varchar), 2, '0') AS anio_mes
  , CASE WHEN fc.anio <= 2018 THEN 'Real 2016-2018'
         ELSE 'Simulado 2019-2025' END                     AS periodo_datos

    -- Contexto del pedido y del cliente
  , e.codigo_estado                                        AS codigo_estado_pedido
  , e.estado                                               AS estado_pedido
  , e.grupo_estado                                         AS grupo_estado_pedido
  , g.estado                                               AS estado_cliente
  , g.ciudad                                               AS ciudad_cliente
  , g.region                                               AS region_cliente

    -- Resenas (grano pedido, con conteos para KPI-2)
  , CASE WHEN r.order_id IS NOT NULL THEN 1 ELSE 0 END     AS tiene_resena
  , COALESCE(r.n_resenas, 0)                               AS n_resenas
  , COALESCE(rb.n_resenas_bajas, 0)                        AS n_resenas_bajas
  , r.score_prom                                           AS score_prom
  , CASE WHEN r.score_prom <= 2 THEN 1 ELSE 0 END          AS pedido_bajo

    -- Entrega (solo pedidos con resena)
  , CASE WHEN r.order_id IS NOT NULL
          AND r.fecha_entrega_cliente_key  <> -1
          AND r.fecha_entrega_estimada_key <> -1
         THEN 1 ELSE 0 END                                 AS entrega_evaluable
  , CASE WHEN r.order_id IS NOT NULL
          AND r.fecha_entrega_cliente_key  <> -1
          AND r.fecha_entrega_estimada_key <> -1
          AND fe.fecha > fs.fecha
         THEN 1 ELSE 0 END                                 AS entrega_tarde
  , CASE WHEN r.order_id IS NULL THEN 'Sin resena'
         WHEN r.fecha_entrega_cliente_key = -1
           OR r.fecha_entrega_estimada_key = -1 THEN 'No evaluable'
         WHEN fe.fecha > fs.fecha THEN 'Tarde'
         ELSE 'A tiempo' END                               AS cumplimiento_plazo

    -- Lineas (composicion, ventas y flete)
  , CASE WHEN l.order_id IS NOT NULL THEN 1 ELSE 0 END     AS tiene_lineas
  , COALESCE(l.n_items, 0)                                 AS n_items
  , COALESCE(l.n_vendedores, 0)                            AS n_vendedores
  , CASE WHEN l.order_id IS NULL THEN 'Sin lineas'
         WHEN l.n_vendedores >= 2 THEN '2 o mas'
         ELSE '1' END                                      AS grupo_vendedores
  , COALESCE(l.precio, 0)                                  AS precio
  , COALESCE(l.flete, 0)                                   AS flete
  , CASE WHEN l.order_id IS NULL THEN 'Sin lineas'
         WHEN l.precio = 0 THEN 'Precio cero'
         WHEN l.flete / l.precio < 0.10 THEN '1. <10%'
         WHEN l.flete / l.precio < 0.25 THEN '2. 10-25%'
         WHEN l.flete / l.precio < 0.50 THEN '3. 25-50%'
         ELSE '4. >=50%' END                               AS rango_flete

    -- Categoria (solo atribuible si el pedido tiene una sola)
  , COALESCE(l.n_categorias, 0)                            AS n_categorias
  , CASE WHEN l.order_id IS NULL THEN 'Sin lineas'
         WHEN l.n_categorias = 1 THEN 'Una categoria'
         ELSE 'Varias categorias' END                      AS tipo_pedido_categoria
  , CASE WHEN l.order_id IS NULL THEN 'Sin lineas'
         WHEN l.n_categorias > 1 THEN 'Varias categorias'
         WHEN l.categoria_unica = 'sin_categoria' THEN 'Sin categoria'
         ELSE l.categoria_unica END                        AS categoria_unica

FROM (
      -- Universo: todos los pedidos de ambas facts
      SELECT order_id FROM olist_master.v_resena_pedido
      UNION
      SELECT DISTINCT order_id FROM olist_master.fact_lineas_pedido
     ) u

LEFT JOIN olist_master.v_resena_pedido r
       ON u.order_id = r.order_id

LEFT JOIN (
      SELECT order_id, COUNT_IF(review_score <= 2) AS n_resenas_bajas
      FROM olist_master.fact_resenas
      GROUP BY order_id
     ) rb
       ON u.order_id = rb.order_id

LEFT JOIN (
      SELECT f.order_id,
             COUNT(*)                         AS n_items,
             COUNT(DISTINCT f.vendedor_key)   AS n_vendedores,
             SUM(f.price)                     AS precio,
             SUM(f.freight_value)             AS flete,
             COUNT(DISTINCT p.categoria)      AS n_categorias,
             arbitrary(p.categoria)           AS categoria_unica,
             arbitrary(f.estado_pedido_key)     AS estado_pedido_key,
             arbitrary(f.geografia_cliente_key) AS geografia_cliente_key,
             arbitrary(f.fecha_compra_key)      AS fecha_compra_key
      FROM olist_master.fact_lineas_pedido f
      LEFT JOIN olist_master.dim_producto p ON f.producto_key = p.producto_key
      GROUP BY f.order_id
     ) l
       ON u.order_id = l.order_id

LEFT JOIN olist_master.dim_fecha fc
       ON COALESCE(r.fecha_compra_key, l.fecha_compra_key) = fc.fecha_key
LEFT JOIN olist_master.dim_estado_pedido e
       ON COALESCE(r.estado_pedido_key, l.estado_pedido_key) = e.estado_pedido_key
LEFT JOIN olist_master.dim_geografia g
       ON COALESCE(r.geografia_cliente_key, l.geografia_cliente_key) = g.geografia_key
LEFT JOIN olist_master.dim_fecha fe
       ON r.fecha_entrega_cliente_key = fe.fecha_key
LEFT JOIN olist_master.dim_fecha fs
       ON r.fecha_entrega_estimada_key = fs.fecha_key;
