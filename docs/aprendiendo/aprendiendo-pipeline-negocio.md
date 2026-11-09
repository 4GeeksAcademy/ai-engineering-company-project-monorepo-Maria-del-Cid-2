# Aprendiendo: pipeline de reporting de negocio en Nexova

Esta guía registra el diagnóstico del pipeline y el estado de implementación.
La fase previa de **Programmes dentro de Inventory está implementada y
validada localmente** (ver sección 6). La Fase 2 original del pipeline y sus
fases posteriores siguen pendientes y no se han iniciado.

## 1. Objetivo y contrato aprobado

El diseño de referencia es `data/pipelines/PIPELINE_DESIGN.md`. El informe
consolidará semanas ISO UTC (lunes 00:00 incluido, lunes siguiente excluido)
por `(office, programme_id, week_start)` desde `public.telemetry_events` hacia
`reporting.weekly_office_program_performance`. No sustituirá el informe técnico
de `GET /api/telemetry/report` ni escribirá resultados de negocio en la fuente.

| KPI | Regla aprobada |
|---|---|
| `total_material_cost` | Suma de `Decimal(quantity) * Decimal(unit_cost)` de eventos `inbound_order_created` válidos. |
| `kits_delivered_count` | Uno por evento `outbound_order_created` único y válido; no suma `quantity` ni filtra por `product_category`. |
| `shortage_events_count` | Uno por evento `stock_threshold_triggered` único, válido y atribuido a oficina/programa. |
| `cost_variance_events_count` | Uno por evento `kit_cost_variance_detected` único, válido y atribuido a oficina/programa. |

Solo se admiten las oficinas canónicas `Valencia` (EUR) y `Miami` (USD). Los
eventos incompletos, duplicados por `event_id`, con cantidad no positiva, coste
inválido o moneda incoherente se rechazan. El cálculo no convierte divisas.
Una reejecución leerá toda la semana y reemplazará sus agregados mediante
upsert; la política de correcciones de negocio con otro UUID no está definida.

## 2. Qué se comprobó en la Fase 1

- La rama `feature/business-reporting-pipeline-implementation` se creó desde
  `origin/main` en `2448038`, después de un fast-forward local. El diseño ya
  formaba parte de `main`; el árbol de trabajo estaba limpio antes del cambio.
- Los modelos `Asset`, `AssetEntry` y `AssetExit` no tienen `programme_id`;
  las entradas tampoco tienen `unit_cost` ni `currency`. Las salidas admiten
  `allocation` y `consumption`, pero no identifican una entrega de kit.
- Los formularios frontend emiten inbound y outbound tras una respuesta HTTP
  satisfactoria sin `programme_id`; inbound no incluye `unit_cost`. El helper de
  alerta calcula umbrales visuales tras volver a consultar el stock y no envía
  `programme_id`. No se encontró un emisor de variación de coste de kits.
- La ingesta valida el envelope CloudEvents y filtra tags según su allowlist,
  pero no valida los campos obligatorios de cada evento. `programme_id` está
  permitido en inbound/outbound y se descarta en alertas y variaciones. El
  repositorio persiste en `public.telemetry_events` con unicidad de `event_id`.
- Una consulta PostgreSQL de **solo lectura** confirmó `SELECT` sobre la tabla
  de telemetría y conteos agregados existentes: inbound 10, outbound 1,
  alertas 1, variaciones de coste 0. Ninguno de los 12 tiene `programme_id`;
  ninguno de los 10 inbound tiene `unit_cost` (3 incluyen `currency`). No se
  inspeccionaron payloads personales. Estos eventos históricos no permiten
  calcular los KPI aprobados por programa ni el coste de material.
- En esa base no existe el esquema `reporting` ni las dos tablas previstas;
  la cuenta consultada tiene privilegio `CREATE` sobre la base. Los permisos
  finales de lectura y escritura para el rol de ejecución siguen sin probarse.
- Prefect no está instalado en el intérprete Python consultado. La API declara
  `psycopg[binary]` y usa `TELEMETRY_DATABASE_URL`; el entorno de ejecución,
  el deployment y los Blocks de Prefect aún no están configurados.
- `docs/telemetry/event-schemas.json` permite `programme_id` opcional en
  inbound/outbound y `unit_cost` nulo en inbound; no declara `programme_id`
  para alerta ni variación. El diseño del pipeline exige dimensiones completas
  en los cuatro casos. Se necesitará una extensión aditiva de contratos y
  emisores en Fase 2, sin reinterpretar el histórico.

## 3. Dependencias imprescindibles y plan propuesto

1. **Fase previa propuesta, programas:** crear programas formativos y asociar
  cada movimiento de inventario a uno de ellos. El producto no pertenece a un
  programa; conserva su oficina y su moneda. Ver sección 6.
2. **Fase 2, fuente:** revisar el dominio para definir kits, costes reales,
  umbrales persistidos y regla de detección de variaciones, previa aprobación
  cuando falten datos de negocio. Completar los campos de los eventos desde
  operaciones de dominio, tras aprobar la garantía de entrega; ampliar los
  contratos en
   `services/api/app/telemetry/tags.py` y `docs/telemetry/event-schemas.json`
   para `programme_id` en alerta y variación. Verificar con los tests cercanos
   de inventario y telemetría. No usar valores supuestos para rellenar datos.
3. **Fases 3 y 4, cálculo:** añadir migraciones PostgreSQL para
   `reporting.weekly_office_program_performance` y `reporting.pipeline_runs`;
   instalar Prefect 3 en el entorno acordado; implementar
   `data/pipelines/pipeline.py` y transformaciones en `data/process/` con las
   tasks y el flow nombrados en el diseño. Extracción siempre fresca, caché de
   transformación ligada al contenido y semana, upsert transaccional, registro
   independiente de ejecución fallida y task opcional con `return_state=True`.
   Guardar snapshots opcionales en `data/eval/` sin convertirlos en fuente KPI.
4. **Fase 5, acceso:** exponer CLI desde la raíz y adaptador de disparo en
   `data/pipelines/`; implementar los tres endpoints bajo `/api/reporting` en
   `services/api/app/reporting/` y registrar su router en
  `services/api/app/main.py`. Los servicios consultarán los resultados o
  solicitarán el flow, sin replicar cálculos. Prefect 3 será self-hosted,
  sin Prefect Cloud; configurar credenciales y permisos fuera del repositorio.
5. **Fase 6, verificación:** validar con datos controlados los cuatro KPI,
   rechazos, semanas UTC, deduplicación, upsert, fallos y reintentos, caché,
   CLI y endpoints. Contrastar la API y el informe técnico existentes. Anotar
   aquí los comandos ejecutados, resultados reales y limitaciones.

La ejecución cada lunes a las 00:15 UTC está **aprobada**. En esta fase
preliminar no se instalaron dependencias de reporting ni se modificó el
pipeline técnico; sí se implementaron y validaron cambios locales de Inventory.

## 4. Decisiones y límites pendientes

- El KPI `kits_delivered_count` cuenta cada `outbound_order_created` único y
  válido como una entrega; no usa `quantity` ni `product_category`. Esta regla
  ha sido confirmada, aunque hoy las salidas también pueden ser consumos o
  asignaciones genéricos: el nombre del KPI no prueba que cada salida sea un kit.
- La integración HTTP irá en `services/api/app/reporting/` con prefijo público
  `/api/reporting`; el CLI seguirá siendo `python data/pipelines/pipeline.py`.
- No existe definición de kit, coste esperado ni regla de anomalía: estos datos
  y reglas deben ser facilitados o aprobados, no inferidos de ejemplos.
- Prefect 3 será self-hosted, pero quedan por decidir host/work pool y rol de
  base de datos. El outbox propuesto para entrega fiable necesita aprobación.
- Los eventos históricos sin dimensiones completas no pueden convertirse
  automáticamente en observaciones válidas del informe; no se ha acordado una
  política de backfill ni de corrección semántica.

## 5. Validaciones realizadas

Se comprobó Git (`status`, comparación de ramas y `fetch`), presencia de
Prefect mediante importación y acceso PostgreSQL en transacciones `READ ONLY`
(esquema, tablas, privilegio de lectura y conteos por tipo). No se ejecutaron
tests de código ni el pipeline, que todavía no existe. Las consultas de base
de datos no son una prueba integral del flujo de usuario.

## 6. Fase previa: Programmes dentro de Inventory

**Estado: implementada; lista para revisión del usuario.** Un
`Programme` identifica un curso o iniciativa de formación, no un producto.
Cada entrada/salida **nueva** debe llevar una referencia obligatoria a un
programa existente; un mismo producto podrá aparecer en movimientos de
programas distintos. Las filas históricas conservarán `programme_id = NULL`.
La elección se hará en el formulario de cada movimiento, no en la ficha del
producto. Habrá una sección Inventory > Programmes para listar, consultar y
crear programas. El seed explícito e idempotente para una base de desarrollo
o test aislada incluirá exactamente estos tres programas iniciales:

| Nombre | `programme_id` estable |
|---|---|
| Digital Skills & AI Foundations | `prog-digital-skills-001` |
| Technical Onboarding Programme | `prog-technical-onboarding-001` |
| Professional Development Programme | `prog-professional-development-001` |

Los tres identificadores son strings: encajan con el `programme_id` de tipo
`string` ya permitido en los contratos inbound/outbound y con una futura PK
textual del modelo `Programme`. Inventario actualmente no define una entidad
ni tipo de identificador de programa. No usar `Asset.id` (entero) como ID de
programa ni asignar estos tres IDs a filas preexistentes.

### Cambios técnicos implementados

- Backend: añadir `Programme` (PK textual `programme_id`, nombre obligatorio)
  en `services/api/app/inventory/models.py`, schemas en `schemas.py`,
  consultas/operaciones y rutas autenticadas `GET/POST /api/inventory/programmes`
  en el router de inventario. Validar `programme_id` como referencia real en
  `AssetEntry` y `AssetExit` al crear movimientos; incluirlo como `str` no
  nulo en schemas de creación y `str | None` en respuestas/listado. Conservar
  `office` y otros campos originales de movimientos. No añadir `programme_id`
  a `Asset`. Distinguir error de campo ausente (422) de ID inexistente (404 o
  422 según convención de inventario) y probar el contrato elegido.
- Persistencia: migración de inventario aditiva que crea `programmes` con PK
  textual y añade `programme_id` nullable con FK a `asset_entries` y
  `asset_exits`, sin modificar filas previas ni imponer `NOT NULL` global.
  Las FK nullable conservan `NULL` histórico pero por sí solas **no impiden**
  un nuevo INSERT SQL directo con `NULL`; los schemas y operaciones exigirán
  programa en todos los writes de la API. Si se requiere garantía también para
  escrituras externas, acordar controles DB adicionales, compatibles con
  SQLite y PostgreSQL. Revisar la migración real según el motor: SQLite puede
  requerir reconstruir tablas para añadir FK, mientras PostgreSQL permite
  restricciones aditivas. `SQLModel.metadata.create_all()` usado en tests no
  migra tablas existentes. Seed explícito idempotente mediante `app.inventory.seed`
  con las protecciones actuales de desarrollo/test; nunca asignar programas
  automáticamente a entradas/salidas históricas.
- Consultas: añadir `programme_id` a las dos selecciones de
  `list_inventory_orders` antes del `UNION ALL`, sin filtrar `NULL` ni alterar
  el cálculo de stock (que sigue sumando todos los movimientos del producto).
  Mostrar "Sin programa asignado (histórico)" solo como etiqueta de UI, no
  como `programme_id` persistido ni como cuarto programa del catálogo.
- UI: añadir vista accesible bajo `app/inventory/programmes/`, cliente y tipos
  junto a `lib/inventory.ts` y `types/inventory.ts`, un enlace en el menú
  Inventory existente en `components/auth/AuthShell.tsx` y
  selector obligatorio de programa en ambos formularios. Actualizar
  `components/inventory/OrdersHistoryPanel.tsx` para mostrar el nombre del
  programa o la etiqueta histórica. Gestionar loading, errores, lista vacía
  y creación. Las operaciones de backend deben validar oficina del movimiento
  igual a la del producto para impedir cruces.
- Moneda: la única regla permitida es `Valencia` -> `EUR`, `Miami` -> `USD`.
  Proponer una validación canónica en backend y persistir la moneda derivada
  de la oficina en productos y movimientos, sin aceptar una moneda arbitraria
  del cliente. La migración de filas existentes debe verificar oficinas antes
  de asignar moneda; si hay oficinas no canónicas, detenerla para revisión.
  No agregar ni comparar importes de oficinas distintas; los emisores de
  inbound y outbound deberán conservar la misma oficina/moneda. Esta fase no
  añade importes ni cambia las fórmulas KPI.

### Criterios de validación y resultados

1. API autenticada crea y lista programas con IDs textuales estables sin
  duplicados; el seed aislado aporta exactamente los tres programas aprobados
  y una segunda ejecución no crea nuevas filas. La UI permite crearlos,
  consultarlos y seleccionarlos. **Validado** con pruebas API/seed y build.
2. Crear inbound y outbound sin ID o con uno inexistente falla antes de grabar
  movimientos. Las respuestas y consultas de órdenes conservan el ID; el
  mismo `asset_id` funciona con dos programas distintos sin cambiar producto.
3. Oficinas ajenas a Valencia/Miami y combinaciones producto/movimiento de
   oficinas diferentes se rechazan. Productos y movimientos exponen EUR o USD
  derivados exclusivamente de su oficina; no se aceptan discrepancias.
  **Validado** en pruebas de API/modelos.
4. Migraciones sobre copias aisladas de SQLite/PostgreSQL conservan IDs,
  cantidades, stock y demás campos de movimientos previos, con
  `programme_id = NULL` y FK para valores no nulos. El listado sigue mostrando
  todas las órdenes y etiqueta los históricos como "Sin programa asignado
  (histórico)"; el stock incluye también los movimientos históricos. **Validado**
  con un SQLite efímero creado con esquema previo: migración repetida, moneda
  EUR y `programme_id = NULL` preservado con FK añadida. No se migró ninguna
  base real ni se comprobó PostgreSQL.
5. El pipeline futuro descarta o contabiliza como inválidos los eventos sin
  `programme_id`; nunca crea una fila semanal con ID nulo ni reparte importes
  entre programas. No se toca el informe técnico ni se implementa todavía
  el pipeline o el outbox.

### Datos y reglas pendientes para la Fase 2

**Verificación local de esta fase previa:** backend `test_inventory*.py` —
**48 tests OK, 1 skip** (prueba opcional de concurrencia PostgreSQL); frontend
— **87 tests OK** en la última ejecución, `npx tsc --noEmit`, ESLint
focalizado y `npm run build` OK. `git diff --check` OK. La suite frontend
produce warnings ruidosos al intentar enviar telemetría a la URL relativa
`/api/telemetry/events` desde Node, aunque las pruebas pasan. El lint global
señala errores preexistentes fuera de los archivos modificados. No se migró
ninguna base real ni se creó commit/push.

El seed de inventario contiene productos y movimientos, pero no programas,
precios unitarios, costes esperados ni composición de kits. El frontend muestra
niveles visuales en 8 y 2 unidades; no hay umbrales persistidos por
producto/oficina/programa ni regla backend de cuándo emitir una alerta. Por
eso se propondrá y aprobará por separado el modelo y criterio de
`stock_threshold_triggered` y `kit_cost_variance_detected`, sin deducir
porcentajes ni precios de ejemplos. El KPI de salidas conserva exactamente la
fórmula confirmada, independientemente de `quantity` o categoría.
Como propuesta para aprobación futura: configurar un umbral explícito por
producto/oficina/programa y emitir una alerta cuando un movimiento haga que
el stock pase de igual o superior a inferior al umbral; hay que confirmar si
el stock compartido entre programas admite atribuir esa alerta a uno solo.
Para variaciones, mantener un coste esperado de kit aprobado y comparar su
coste real de componentes de la misma oficina y moneda en el momento de una
operación de kit; hay que definir qué operación es esa, qué componentes/costes
la alimentan y qué condición porcentual merece un evento. Ninguna de estas
reglas ni sus valores se implementa en la fase previa.
La URL de inventario puede apuntar a un archivo SQLite de contenedor que no
existe en este host: no se inspeccionó ese volumen ni las oficinas de
movimientos reales. Antes de migrar una base de trabajo habrá que consultar
sus filas de forma segura y acordar cómo conservar movimientos anteriores que
no tienen programa.

### Propuesta de fiabilidad de eventos para aprobación

En este entorno `DATABASE_URL` es SQLite para inventario y
`TELEMETRY_DATABASE_URL` es PostgreSQL: no hay transacción compartida. Un
`emit_event()` directo tampoco garantiza entrega, porque captura fallos. Se
propone un transactional outbox **en la misma base que los movimientos**:
guardar movimiento y evento pendiente en una sola transacción; después, un
worker independiente envía cada evento a `public.telemetry_events` mediante
el adaptador existente, con UUID estable, reintentos y monitorización de
pendientes. La unicidad de `event_id` en destino hace idempotente el reenvío;
marcar como entregado solo tras confirmación. Fallos prolongados dejan el
evento pendiente para reintento sin perder el movimiento. No escribir KPI en
telemetría ni atribuir atomicidad entre SQLite y PostgreSQL. Esto requiere
definir el despliegue y concurrencia del worker y la política de retención
antes de implementar la emisión de la Fase 2; no forma parte del alcance de
la fase previa propuesta.