-- ============================================================
-- E3 Evidencia: olist_master NO contiene identificadores de cliente
-- Esperado: 0 filas (justifica la opcion C: compradores no disponible)
-- ============================================================
SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema = 'olist_master'
  AND (lower(column_name) LIKE '%customer%'
       OR lower(column_name) LIKE '%unique%'
       OR lower(column_name) IN ('cliente_id', 'cliente_key', 'comprador'));

-- Referencia: el identificador solo existe en RAW
SELECT table_schema, table_name, column_name
FROM information_schema.columns
WHERE table_schema = 'olist_raw'
  AND column_name IN ('customer_id', 'customer_unique_id');
