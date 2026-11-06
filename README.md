# Olist — Build Your Own Generative BI

Proyecto del curso **Business Intelligence — USMP, 2026-II** (Docente: MSc. Jean Carlo Vallejos Pongo).
Adaptación del repositorio `build-your-own-generative-bi-aws` (caso NEXA) al datamart de **Olist**, enfocado en la **insatisfacción del cliente por pedido**.

**Integrantes:** Tafur Trujillo, Víctor · Palomino Zarate, Pedro · Huamán Carlos, Abraham · Quezada Pichihua, Nicolás.

> **Bedrock interpreta. La Semantic Layer gobierna. Athena calcula.**

---

## 1. Arquitectura

```text
Plano de datos:   S3 (olist-retail-2026) → Glue Data Catalog → Athena (olist_master)
                          2 facts + 5 dimensiones (constelación)
                                     ↓
Contrato:         vw_olist_genbi_pedidos   (1 fila = 1 pedido, Quality Gate aprobado)
                                     ↓
Plano GenBI:      Profiling → Draft Bedrock → Validación humana → Semantic Layer
                  Pregunta → Resolver semántico → Bedrock NL-to-SQL → SQL Guard
                  → Athena → Insight (Bedrock) + Visualización (Plotly) → Streamlit
```

No se usan LangChain, RAG, agentes, Lambda ni Knowledge Bases, igual que en el laboratorio del profesor.

## 2. Estructura

```text
olist_genbi/
├── app.py                         Streamlit (Olist)
├── requirements.txt               + sqlglot, pytest
├── config/
│   ├── settings.example.json      copiar a settings.json
│   ├── business_context.json      grano y notas de negocio (entrada del profiling)
│   ├── dataset_profile.json       GENERADO por scripts/01
│   ├── semantic_layer_draft.json  GENERADO por scripts/02 (evidencia, no editar)
│   ├── semantic_layer.json        capa semántica aprobada
│   ├── semantic_layer.example.json
│   └── reference_queries.json     10 Golden Queries + 1 prueba de gobierno
├── sql/
│   ├── 01_create_genbi_view.sql   vista vw_olist_genbi_pedidos
│   ├── 02_quality_gate.sql        QG1–QG7
│   └── verificaciones/            E1 estructura · E2 indicadores · E3 sin cliente · E4 PPT = AWS
├── src/                           módulos del profesor (ver sección 7)
├── scripts/01…06                  mismo flujo del profesor
├── tests/                         test_sql_guard.py · test_semantic_resolver.py
└── docs/                          evidencias (verificación, quality gate, decisiones,
                                   validación humana, golden results, capturas/)
```

## 3. Datamart y vista GenBI

- **Base:** `olist_master`, en `us-east-1`.
- **Facts:**
  - `fact_resenas`: grano (review_id, order_id), 455 721 filas.
  - `fact_lineas_pedido`: grano (order_id, order_item_id), 597 354 filas.
- **Dimensiones:**
  - `dim_fecha`, con 4 roles;
  - `dim_geografia`;
  - `dim_estado_pedido`;
  - `dim_producto`;
  - `dim_vendedor`.
- **Vista base existente:** `v_resena_pedido` (reseñas por pedido).
- **Vista GenBI:** `vw_olist_genbi_pedidos`. Cada fact se resume por `order_id` **antes** de unirse, así que no hay duplicación. Tiene 449 422 pedidos y 32 columnas. Quality Gate aprobado: ver `docs/quality_gate.md`.
- **No se usan** `v_lineas_2016_2025` ni `v_resenas_2016_2025`, porque duplican 2019–2025. Ver `docs/verificacion_athena.md`.

## 4. KPI oficiales (informe v4)

| KPI | Definición | Valor verificado |
|---|---|---|
| KPI-1 | % de pedidos con promedio de reseñas ≤ 2 (sobre pedidos con reseña) | 15,21 % |
| KPI-2 | % de reseñas con review_score ≤ 2 | 15,25 % |
| KPI-3 | Calificación promedio por pedido | 3,72 |
| KPI-4/5 | Entrega tardía / tasa de entrega tardía | 11,96 % |
| KPI-6 | Artículos por pedido | — |
| KPI-7 | Vendedores por pedido | — |
| KPI-8 | Flete / precio (SUM/SUM) | — |

## 5. Capa semántica (`config/semantic_layer.json`)

Cumple el mínimo del profesor (5 dimensiones, 4 métricas, 5 sinónimos, 5 reglas, 3 ambigüedades):

- **11 dimensiones, 12 métricas, más de 60 sinónimos y 12 reglas de negocio.**
- **6 ambigüedades gobernadas:**

| Término | Interpretación aprobada |
|---|---|
| insatisfacción | KPI-1 |
| calificación | KPI-3 |
| calificación baja | KPI-1 |
| ventas | sin flete |
| peor / mejor | KPI-1 |
| retraso | KPI-5 |

- **Métrica no disponible:** compradores únicos / clientes (sección 6).

## 6. Decisión: compradores únicos = métrica no disponible (opción C)

`customer_unique_id` existe en la fuente y en `olist_raw.customers`, pero **no en `olist_master`**. Lo verificamos con `sql/verificaciones/E3_sin_identificador_cliente.sql`, que devuelve 0 filas.

Para no depender de RAW y no confundir `customer_id` (uno por pedido) con `customer_unique_id` (la persona):

- **"Clientes" no se interpreta como pedidos.**
- **El resolver de Python** (`src/sql_generator.py`) detecta los términos de `unavailable_metrics` y devuelve `status = "unavailable"`, **sin llamar a Bedrock ni a Athena**. La app muestra el mensaje y propone alternativas.
- **Pruebas:** `tests/test_semantic_resolver.py` y la golden query GQ11.
- **Mejora futura** (fuera de esta entrega): incorporar una `dim_cliente` con `customer_unique_id` mediante el pipeline incremental.

## 7. Cambios respecto del repositorio del profesor

| Archivo | Cambio | Tipo |
|---|---|---|
| `src/sql_guard.py` | Usa un parser SQL (`sqlglot`): bloquea *comma joins* y subconsultas a otras tablas, no confunde `EXTRACT(... FROM ...)` con una tabla y permite `COUNT(*)` | Necesaria |
| `src/sql_generator.py` | Busca términos por **palabra completa** (antes, subcadenas); da prioridad a la frase más larga; agrega `unavailable_metrics`; envía la capa semántica como JSON | Necesaria |
| `scripts/05_validate_reference.py` | Agrega pruebas de gobierno (`expect_unavailable`), continúa aunque falle un caso y guarda `docs/golden_results.json`; compara tablas pequeñas | Mejora opcional (la comparación escalar original se mantiene) |
| `src/bedrock.py`, `src/athena.py`, `src/config.py` | Perfil de AWS opcional (`aws_profile`, `bedrock_aws_profile`) | Opcional (plan B de cuota) |
| `app.py`, scripts 03, 04 y 06 | Textos de Olist y manejo de métricas no disponibles | Necesaria |
| `.gitignore` | Se quitó la línea `config`, que ocultaba toda la carpeta | Necesaria |
| `profiler.py`, `semantic_builder.py`, `insight.py`, `visualization.py` | Sin cambios | — |

## 8. Instalación (Visual Studio Code)

```bash
git clone <url-del-repo> olist_genbi
cd olist_genbi
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Credenciales de AWS:**

```bash
aws configure            # región: us-east-1
aws sts get-caller-identity
```

**Configuración:** copiar `config/settings.example.json` a `config/settings.json`. Ese archivo no se sube a git.

## 9. Orden de ejecución (siempre desde la raíz del proyecto)

| Paso | Comando | Usa | Criterio para avanzar |
|---|---|---|---|
| 0 | `python -m pytest -q tests` | local | Todos los tests pasan |
| 1 | Athena: `sql/01_create_genbi_view.sql` y `sql/02_quality_gate.sql` | Athena | QG1–QG7 pasan (**hecho**) |
| 2 | `PYTHONPATH=. python scripts/01_profile.py` | Athena | Se crea `config/dataset_profile.json` |
| 3 | `PYTHONPATH=. python scripts/02_build_semantic_draft.py` | Bedrock | Se crea el draft; **no editarlo** |
| 4 | Validación humana → `docs/human_validation.md` → ajustar `semantic_layer.json` | — | Aceptado / corregido / rechazado documentado |
| 5 | `PYTHONPATH=. python scripts/03_test_nl2sql.py` | Bedrock | Se aplica la métrica gobernada y el SQL Guard da PASSED |
| 6 | `PYTHONPATH=. python scripts/04_execute_genbi_query.py` | Bedrock + Athena | Athena devuelve resultado |
| 7 | `PYTHONPATH=. python scripts/05_validate_reference.py` | Bedrock + Athena | 10/10 + GQ11 |
| 8 | `PYTHONPATH=. python scripts/06_genbi_result.py` | Bedrock + Athena | Insight en R$, sin cifras inventadas |
| 9 | `streamlit run app.py` | Bedrock + Athena | Demo en http://localhost:8501 |

En Windows PowerShell, `PYTHONPATH=.` se reemplaza por `$env:PYTHONPATH="."` en una línea aparte.

## 10. Estado de Bedrock

La cuenta tiene **cuota 0** para Amazon Nova Micro en `us-east-1` (Service Quotas). Se solicitó un aumento.

Si hace falta, el plan B es usar Bedrock desde otra cuenta. Para eso se configura un perfil (`aws configure --profile bedrock`) y se pone `"bedrock_aws_profile": "bedrock"` en `settings.json`. Athena sigue en la cuenta del datamart.

## 11. Modo respaldo (sin Bedrock)

AWS rechazó el acceso a Bedrock en la cuenta (casos 179397137900209 y 179398855200550). Mientras se resuelve, el proyecto corre con `"llm_mode": "offline"` en `config/settings.json`.

| Componente | Modo `bedrock` | Modo `offline` |
|---|---|---|
| Resolver semántico y métrica no disponible | Igual | Igual |
| Generación de SQL | Amazon Bedrock (Nova Micro) | Reglas sobre la capa semántica (`src/offline_generator.py`) |
| SQL Guard, Athena, golden queries, gráfico, Streamlit | Reales | Reales |
| Insight | Redactado por Bedrock | Plantilla con cifras del resultado |
| Draft semántico (script 02) | Bedrock | No disponible |

Para volver a Bedrock basta con poner `"llm_mode": "bedrock"`. En modo `offline`, las golden queries validan las **reglas semánticas**, no al LLM; hay que volver a ejecutarlas con Bedrock cuando AWS habilite la cuota.

## 12. Limitaciones

- La reseña califica el **pedido completo**: no se atribuye la insatisfacción a un producto.
- Solo existe el **último estado** del pedido, sin historial.
- **2019–2025 son datos simulados.**
- Los resultados son **asociaciones, no causas**.
- El SQL Guard es pedagógico: en producción se complementa con IAM, Lake Formation y los controles del workgroup.
