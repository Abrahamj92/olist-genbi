-- ============================================================
-- OLIST GENBI - ETAPA 2: CONCILIACION DE INDICADORES
-- Base: olist_master (ejecutar en Athena, una consulta a la vez)
-- Fuentes: solo facts de MASTER y v_resena_pedido.
-- NO usar v_lineas_2016_2025 ni v_resenas_2016_2025 (duplican 2019-2025).
-- Origen de datos: anio <= 2018 = real ; anio >= 2019 = simulado.
-- Definiciones oficiales: informe v4 / taller GenBI.
-- ============================================================


-- ------------------------------------------------------------
-- E2.1 KPI-1 y KPI-3 total (Q1 del informe)
-- KPI-1 = pedidos con promedio de resenas <= 2 / pedidos con resena x 100
-- KPI-3 = calificacion promedio por pedido
-- Registrado: 441 600 pedidos; KPI-1 = 15,21 %; KPI-3 = 3,72
-- ------------------------------------------------------------
SELECT COUNT(*)                                                AS pedidos_con_resena,
       COUNT_IF(score_prom <= 2)                               AS pedidos_bajos,
       ROUND(100.0 * COUNT_IF(score_prom <= 2) / COUNT(*), 2)  AS kpi1_pct,
       ROUND(AVG(score_prom), 2)                               AS kpi3_prom
FROM olist_master.v_resena_pedido;


-- ------------------------------------------------------------
-- E2.2 KPI-2 total (Q12 del informe)
-- KPI-2 = resenas con review_score <= 2 / total de resenas x 100
-- Registrado: 455 721 resenas; KPI-2 = 15,25 %
-- ------------------------------------------------------------
SELECT COUNT(*)                                                    AS resenas,
       COUNT_IF(review_score <= 2)                                 AS resenas_bajas,
       ROUND(100.0 * COUNT_IF(review_score <= 2) / COUNT(*), 2)    AS kpi2_pct
FROM olist_master.fact_resenas;


-- ------------------------------------------------------------
-- E2.3 KPI-1, KPI-2 y KPI-3 por ano y origen
-- Verifica: que los totales salgan de sumar los anos, y la
-- diferencia entre datos reales y simulados.
-- ------------------------------------------------------------
SELECT d.anio,
       CASE WHEN d.anio <= 2018 THEN 'Real' ELSE 'Simulado' END       AS origen,
       COUNT(*)                                                       AS pedidos_con_resena,
       ROUND(100.0 * COUNT_IF(p.score_prom <= 2) / COUNT(*), 2)       AS kpi1_pct,
       ROUND(AVG(p.score_prom), 2)                                    AS kpi3_prom,
       SUM(p.n_resenas)                                               AS resenas
FROM olist_master.v_resena_pedido p
JOIN olist_master.dim_fecha d ON p.fecha_compra_key = d.fecha_key
GROUP BY d.anio
ORDER BY d.anio;


-- ------------------------------------------------------------
-- E2.4 KPI-2 por ano (resenas)
-- ------------------------------------------------------------
SELECT d.anio,
       COUNT(*)                                                    AS resenas,
       ROUND(100.0 * COUNT_IF(r.review_score <= 2) / COUNT(*), 2)  AS kpi2_pct
FROM olist_master.fact_resenas r
JOIN olist_master.dim_fecha d ON r.fecha_compra_key = d.fecha_key
GROUP BY d.anio
ORDER BY d.anio;


-- ------------------------------------------------------------
-- E2.5 KPI-2 calculado A NIVEL PEDIDO (prueba para la vista GenBI)
-- Verifica: que SUM(resenas_bajas)/SUM(n_resenas) por pedido da
-- el mismo KPI-2 que E2.2. Si coincide, la vista de grano pedido
-- puede calcular KPI-2 sin duplicar.
-- ------------------------------------------------------------
SELECT SUM(n_resenas)                                               AS resenas,
       SUM(n_bajas)                                                 AS resenas_bajas,
       ROUND(100.0 * SUM(n_bajas) / SUM(n_resenas), 2)              AS kpi2_pct_desde_pedido
FROM (
  SELECT order_id, COUNT(*) AS n_resenas, COUNT_IF(review_score <= 2) AS n_bajas
  FROM olist_master.fact_resenas
  GROUP BY order_id
) t;


-- ------------------------------------------------------------
-- E2.6 Cobertura de fechas de entrega (base del KPI-4 / KPI-5)
-- Verifica: cuantos pedidos con resena tienen ambas fechas y por
-- estado del pedido. Define el denominador de la entrega tardia.
-- ------------------------------------------------------------
SELECT e.codigo_estado,
       COUNT(*)                                                            AS pedidos,
       COUNT_IF(p.fecha_entrega_cliente_key <> -1
                AND p.fecha_entrega_estimada_key <> -1)                    AS con_ambas_fechas
FROM olist_master.v_resena_pedido p
JOIN olist_master.dim_estado_pedido e ON p.estado_pedido_key = e.estado_pedido_key
GROUP BY e.codigo_estado
ORDER BY pedidos DESC;


-- ------------------------------------------------------------
-- E2.7 KPI-5 tasa de entrega tardia y KPI-1 por cumplimiento (Q15)
-- KPI-4: tarde si fecha de entrega al cliente > fecha estimada.
-- KPI-5 = pedidos tarde / pedidos con ambas fechas x 100
-- ------------------------------------------------------------
SELECT CASE WHEN fe.fecha > fs.fecha THEN 'Tarde' ELSE 'A tiempo' END   AS cumplimiento,
       COUNT(*)                                                         AS pedidos,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)               AS pct_del_total,
       ROUND(100.0 * COUNT_IF(p.score_prom <= 2) / COUNT(*), 2)         AS kpi1_pct,
       ROUND(AVG(p.score_prom), 2)                                      AS kpi3_prom
FROM olist_master.v_resena_pedido p
JOIN olist_master.dim_fecha fe ON p.fecha_entrega_cliente_key  = fe.fecha_key
JOIN olist_master.dim_fecha fs ON p.fecha_entrega_estimada_key = fs.fecha_key
WHERE p.fecha_entrega_cliente_key <> -1
  AND p.fecha_entrega_estimada_key <> -1
GROUP BY 1;


-- ------------------------------------------------------------
-- E2.8 KPI-6, KPI-7 y KPI-8 (composicion y flete) - total
-- KPI-6 = articulos por pedido ; KPI-7 = vendedores por pedido
-- KPI-8 = flete / precio (global SUM/SUM y promedio de ratios)
-- ------------------------------------------------------------
SELECT COUNT(*)                                                AS pedidos_con_lineas,
       ROUND(AVG(n_items), 2)                                  AS kpi6_articulos_prom,
       COUNT_IF(n_vendedores >= 2)                             AS pedidos_2_o_mas_vendedores,
       ROUND(100.0 * COUNT_IF(n_vendedores >= 2) / COUNT(*), 2) AS pct_2_o_mas_vendedores,
       ROUND(SUM(precio), 2)                                   AS ventas_precio,
       ROUND(SUM(flete), 2)                                    AS flete_total,
       ROUND(100.0 * SUM(flete) / SUM(precio), 2)              AS kpi8_global_pct,
       ROUND(100.0 * AVG(flete / NULLIF(precio, 0)), 2)        AS kpi8_prom_ratios_pct,
       COUNT_IF(precio = 0)                                    AS pedidos_precio_cero
FROM (
  SELECT order_id,
         COUNT(*)                     AS n_items,
         COUNT(DISTINCT vendedor_key) AS n_vendedores,
         SUM(price)                   AS precio,
         SUM(freight_value)           AS flete
  FROM olist_master.fact_lineas_pedido
  GROUP BY order_id
) t;


-- ------------------------------------------------------------
-- E2.9 KPI-1 por grupo de vendedores y por rango de flete
-- Verifica: que el cruce de ambas facts AGREGADAS por pedido
-- funciona (patron que usara la vista GenBI).
-- ------------------------------------------------------------
SELECT CASE WHEN l.n_vendedores >= 2 THEN '2 o mas' ELSE '1' END       AS grupo_vendedores,
       CASE WHEN l.flete / NULLIF(l.precio, 0) < 0.10 THEN '1. <10%'
            WHEN l.flete / NULLIF(l.precio, 0) < 0.25 THEN '2. 10-25%'
            WHEN l.flete / NULLIF(l.precio, 0) < 0.50 THEN '3. 25-50%'
            ELSE '4. >=50%' END                                        AS rango_flete,
       COUNT(*)                                                        AS pedidos,
       ROUND(100.0 * COUNT_IF(r.score_prom <= 2) / COUNT(*), 2)        AS kpi1_pct
FROM olist_master.v_resena_pedido r
JOIN (
  SELECT order_id,
         COUNT(DISTINCT vendedor_key) AS n_vendedores,
         SUM(price)                   AS precio,
         SUM(freight_value)           AS flete
  FROM olist_master.fact_lineas_pedido
  GROUP BY order_id
) l ON r.order_id = l.order_id
GROUP BY 1, 2
ORDER BY 1, 2;


-- ------------------------------------------------------------
-- E2.10 Categoria unica vs varias (con 'sin_categoria' aparte)
-- Verifica: cuantos pedidos quedan con categoria atribuible y su
-- distribucion por origen real / simulado.
-- ------------------------------------------------------------
SELECT CASE WHEN d.anio <= 2018 THEN 'Real' ELSE 'Simulado' END  AS origen,
       COUNT(*)                                                  AS pedidos,
       COUNT_IF(t.n_cat = 1 AND t.solo_sin_cat = 0)              AS una_categoria_real,
       COUNT_IF(t.n_cat = 1 AND t.solo_sin_cat = 1)              AS solo_sin_categoria,
       COUNT_IF(t.n_cat > 1)                                     AS varias_categorias
FROM (
  SELECT f.order_id,
         arbitrary(f.fecha_compra_key)                           AS fecha_compra_key,
         COUNT(DISTINCT p.categoria)                             AS n_cat,
         MAX(CASE WHEN p.categoria = 'sin_categoria' THEN 1 ELSE 0 END)
           * MIN(CASE WHEN p.categoria = 'sin_categoria' THEN 1 ELSE 0 END) AS solo_sin_cat
  FROM olist_master.fact_lineas_pedido f
  JOIN olist_master.dim_producto p ON f.producto_key = p.producto_key
  GROUP BY f.order_id
) t
JOIN olist_master.dim_fecha d ON t.fecha_compra_key = d.fecha_key
GROUP BY 1;


-- ------------------------------------------------------------
-- E2.11 Region y estado del cliente: cobertura (objetivo geografico)
-- Verifica: valores de region y si existe "No disponible".
-- ------------------------------------------------------------
SELECT g.region,
       COUNT(*)                                                  AS pedidos_con_resena,
       ROUND(100.0 * COUNT_IF(p.score_prom <= 2) / COUNT(*), 2)  AS kpi1_pct
FROM olist_master.v_resena_pedido p
JOIN olist_master.dim_geografia g ON p.geografia_cliente_key = g.geografia_key
GROUP BY g.region
ORDER BY pedidos_con_resena DESC;
