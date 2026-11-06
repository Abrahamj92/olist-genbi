# Resultados de las Golden Queries

> **Estado: PENDIENTE de ejecución** (requiere cuota de Bedrock).
> `scripts/05_validate_reference.py` genera `docs/golden_results.json` automáticamente.

| ID | Nivel | Pregunta | Métrica esperada | Valor de referencia | Resultado GenBI | ¿Pasa? |
|---|---|---|---|---|---|---|
| GQ01 | pedido | ¿Cuántos pedidos con reseña hay? | pedidos_con_resena | 441 600 (verificado) | | |
| GQ02 | pedido | ¿Cuál es el porcentaje de pedidos insatisfechos? | KPI-1 | 15,21 % (verificado) | | |
| GQ03 | pedido | ¿Cuál es la calificación promedio? | KPI-3 | 3,72 (verificado) | | |
| GQ04 | reseña | ¿Qué porcentaje de reseñas bajas tenemos? | KPI-2 | 15,25 % (verificado) | | |
| GQ05 | reseña | ¿Cuántas reseñas hay en total? | resenas | 455 721 (verificado) | | |
| GQ06 | pedido + año | % de pedidos insatisfechos en 2017 | KPI-1 | 14,41 % (verificado) | | |
| GQ07 | pedido + año | Tasa de entrega tardía en 2025 | KPI-5 | 9,24 % (verificado) | | |
| GQ08 | línea | ¿Cuánto vendimos en total? | ventas_productos | R$ 86 437 222,10 (verificado) | | |
| GQ09 | línea | Proporción de flete sobre precio | KPI-8 | 18,63 % (verificado) | | |
| GQ10 | pedido + composición | % de pedidos insatisfechos con 2 o más vendedores | KPI-1 | 15,77 % (verificado) | | |
| GQ11 | comprador (gobierno) | ¿Cuántos clientes únicos tenemos? | no disponible | rechazo | | |

**Validación del resolver sin AWS.** `tests/test_semantic_resolver.py` comprueba que las 11 preguntas se resuelven a la métrica declarada (pasa 11/11 localmente).
