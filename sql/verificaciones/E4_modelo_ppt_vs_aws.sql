-- ============================================================
-- E4 El modelo dimensional de la PPT (diapositiva 12) = AWS
-- Esperado: 0 filas
-- ============================================================
WITH ppt (table_name, column_name) AS (
  VALUES
  ('fact_resenas','resena_key'),('fact_resenas','review_id'),('fact_resenas','order_id'),
  ('fact_resenas','geografia_cliente_key'),('fact_resenas','estado_pedido_key'),
  ('fact_resenas','fecha_compra_key'),('fact_resenas','fecha_entrega_cliente_key'),
  ('fact_resenas','fecha_entrega_estimada_key'),('fact_resenas','fecha_creacion_resena_key'),
  ('fact_resenas','review_score'),
  ('fact_lineas_pedido','linea_key'),('fact_lineas_pedido','order_id'),('fact_lineas_pedido','order_item_id'),
  ('fact_lineas_pedido','producto_key'),('fact_lineas_pedido','vendedor_key'),
  ('fact_lineas_pedido','geografia_cliente_key'),('fact_lineas_pedido','estado_pedido_key'),
  ('fact_lineas_pedido','fecha_compra_key'),('fact_lineas_pedido','price'),('fact_lineas_pedido','freight_value'),
  ('dim_fecha','fecha_key'),('dim_fecha','fecha'),('dim_fecha','dia'),('dim_fecha','mes'),
  ('dim_fecha','nombre_mes'),('dim_fecha','trimestre'),('dim_fecha','anio'),
  ('dim_fecha','dia_semana'),('dim_fecha','nombre_dia'),
  ('dim_geografia','geografia_key'),('dim_geografia','zip_code_prefix'),('dim_geografia','ciudad'),
  ('dim_geografia','estado'),('dim_geografia','region'),
  ('dim_estado_pedido','estado_pedido_key'),('dim_estado_pedido','codigo_estado'),
  ('dim_estado_pedido','estado'),('dim_estado_pedido','grupo_estado'),
  ('dim_producto','producto_key'),('dim_producto','product_id'),('dim_producto','categoria'),
  ('dim_producto','categoria_en'),
  ('dim_vendedor','vendedor_key'),('dim_vendedor','seller_id')
),
aws AS (
  SELECT table_name, column_name
  FROM information_schema.columns
  WHERE table_schema = 'olist_master'
    AND table_name IN ('fact_resenas','fact_lineas_pedido','dim_fecha','dim_geografia',
                       'dim_estado_pedido','dim_producto','dim_vendedor')
)
SELECT COALESCE(p.table_name, a.table_name)   AS tabla,
       COALESCE(p.column_name, a.column_name) AS columna,
       CASE WHEN a.column_name IS NULL THEN 'Esta en la PPT, falta en AWS'
            ELSE 'Esta en AWS, falta en la PPT' END AS diferencia
FROM ppt p
FULL OUTER JOIN aws a
  ON p.table_name = a.table_name AND p.column_name = a.column_name
WHERE p.column_name IS NULL OR a.column_name IS NULL;
