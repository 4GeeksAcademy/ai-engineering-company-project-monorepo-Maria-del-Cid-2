# Aprendiendo: pipeline de reporting de negocio en Nexova

Esta guía registra el diagnóstico del pipeline y el estado de implementación.
La fase previa de **Programmes dentro de Inventory está implementada y
validada localmente** (ver sección 6). La Fase 2 implementó outbox y worker; la
Fase 3 actual agrega fixtures de demo y eventos de negocio al mismo flujo. No
se implementan aquí el pipeline de reporting ni las fases posteriores.

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
- `docs/telemetry/event-schemas.json` mantiene `programme_id` opcional para
  movimientos históricos y permite `unit_cost` nulo en inbound. Los contratos
  de umbral y variación incluyen dimensiones requeridas; el worker valida su
  presencia y consistencia sin reinterpretar el histórico.

## 3. Dependencias imprescindibles y plan propuesto

1. **Fase previa propuesta, programas:** crear programas formativos y asociar
  cada movimiento de inventario a uno de ellos. El producto no pertenece a un
  programa; conserva su oficina y su moneda. Ver sección 6.
2. **Fase 2, fuente y entrega:** outbox transaccional y worker independiente,
   con leases, reintentos, dead-letter y deduplicación del destino.
3. **Fase 3, fixtures de inventario:** seed demo explícito y protegido,
   idempotencia de movimientos/preparaciones, valoración ponderada, escenarios
   de umbral y eventos de variancia de kit. Se preservan los registros
   históricos; ver el progreso detallado en `memory-bank/progress.md`.
4. **Fases 4 y 5, cálculo:** añadir migraciones PostgreSQL para
   `reporting.weekly_office_program_performance` y `reporting.pipeline_runs`;
   instalar Prefect 3 en el entorno acordado; implementar
   `data/pipelines/pipeline.py` y transformaciones en `data/process/` con las
   tasks y el flow nombrados en el diseño. Extracción siempre fresca, caché de
   transformación ligada al contenido y semana, upsert transaccional, registro
   independiente de ejecución fallida y task opcional con `return_state=True`.
   Guardar snapshots opcionales en `data/eval/` sin convertirlos en fuente KPI.
5. **Fase 6, acceso:** exponer CLI desde la raíz y adaptador de disparo en
   `data/pipelines/`; implementar los tres endpoints bajo `/api/reporting` en
   `services/api/app/reporting/` y registrar su router en
  `services/api/app/main.py`. Los servicios consultarán los resultados o
  solicitarán el flow, sin replicar cálculos. Prefect 3 será self-hosted,
  sin Prefect Cloud; configurar credenciales y permisos fuera del repositorio.
6. **Fase 7, verificación:** validar con datos controlados los cuatro KPI,
   rechazos, semanas UTC, deduplicación, upsert, fallos y reintentos, caché,
   CLI y endpoints. Contrastar la API y el informe técnico existentes. Anotar
   aquí los comandos ejecutados, resultados reales y limitaciones.

La ejecución cada lunes a las 00:15 UTC está **aprobada**. No se instalaron
dependencias de reporting ni se modificó el pipeline técnico.

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
  base de datos. El outbox acordado se entrega antes del cálculo/reporting.
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
  programme_id`; nunca crea una fila semanal con ID nulo ni reparte importes
  entre programas. No se toca el informe técnico ni se implementa todavía
  el pipeline de reporting.

### Datos, reglas y estado de Fase 2

**Verificación local de esta fase previa:** backend `test_inventory*.py` —
**48 tests OK, 1 skip** (prueba opcional de concurrencia PostgreSQL); frontend
— **87 tests OK** en la última ejecución, `npx tsc --noEmit`, ESLint
focalizado y `npm run build` OK. `git diff --check` OK. La suite frontend
produce warnings ruidosos al intentar enviar telemetría a la URL relativa
`/api/telemetry/events` desde Node, aunque las pruebas pasan. El lint global
señala errores preexistentes fuera de los archivos modificados. No se migró
ninguna base real ni se creó commit/push.

El seed de inventario contiene productos y movimientos, pero no programas,
precios unitarios, costes esperados ni composición de kits. La implementación
no infiere esos datos: un administrador configura umbrales por producto/oficina
y composición/coste esperado del kit. Una alerta se genera solo al cruzar de
stock igual o superior al umbral a stock inferior; su atribución de programa
procede del movimiento que cruza el umbral, aunque el stock físico sea
compartido. Para kits, la variación se calcula por kit y solo se emite cuando
todo el coste de componentes es conocido y la variación positiva supera
estrictamente el porcentaje configurado. Coste esperado cero o coste incompleto
no generan evento. El KPI de salidas mantiene su fórmula aprobada y no se
redefine aquí.

Se añadieron tablas aditivas para valuación, ledger, regularizaciones
auditables, umbrales, configuración/composición y snapshots de preparación.
Las entradas actualizan coste medio ponderado; las salidas consumen primero
stock sin coste conocido. La migración marca stock previo como no valuado; no
reescribe movimientos históricos ni inventa costes o programas. Una
regularización explícita requiere ADMIN y motivo. Los cambios de movimiento y
sus eventos outbox comparten transacción. La moneda se deriva en backend
(Valencia/EUR, Miami/USD).

Existen endpoints autenticados para umbrales, configuración/preparación de
kits y regularización; configuración y regularización están restringidas a
ADMIN. No se añadió UI para estas operaciones: el alcance implementado es API
y debe integrarse con una interfaz si se requiere su uso desde backoffice. Se
retiró del flujo frontend el emisor best-effort duplicado de alertas.

La migración CLI protegida por `--environment development|test` se ejecutó
contra dos instancias PostgreSQL 16 desechables, locales y aisladas, sin
volúmenes persistentes y distintas de los destinos configurados para la
aplicación. Se creó allí un esquema histórico sintético, identificado
explícitamente como fixture de prueba (un producto, una entrada sin coste y una
salida). La migración creó las tablas aditivas y la valoración inicial
`valued=0`, `unvalued=3`, `average_cost=0`; conservó los IDs/cantidades de
movimientos y el coste histórico nulo. Se ejecutó repetidamente, incluyendo
después de modificar el estado de valoración, y no lo sobrescribió. Los modelos
SQLModel pudieron leer las tablas migradas. No se migraron filas reales ni se
conectó con Supabase o producción.

En PostgreSQL 16 desechable se probaron carreras con sesiones independientes:
dos salidas simultáneas que cruzaban un umbral acabaron con stock 6, valoración
6 y exactamente un evento de cruce; dos preparaciones de kit con stock
suficiente consumieron dos unidades cada una y conservaron sus snapshots y
eventos; con una sola unidad disponible, solo una de dos preparaciones pudo
confirmar y la otra falló por stock insuficiente, sin efectos parciales. Una
falla inyectada al insertar en outbox revirtió en conjunto la entrada, el
ledger, la valoración y el evento. Estas son comprobaciones concurrentes
concretas, no una prueba exhaustiva de todos los órdenes posibles.

**Verificación previa conservada:** toda la suite backend de inventario
(`test_inventory*.py`): **63 passed, 1 skipped, 28 subtests passed**,
incluyendo cruce de umbral, migración temporal/idempotente, costes de kits,
supresión por coste desconocido, rollback, regularización, autorización y
validación de worker. El skip es una prueba opcional dependiente de PostgreSQL.
El archivo
`docs/telemetry/event-schemas.json` se validó como JSON y contiene los dos
contratos nuevos. La suite Node pasó: **87 tests**. El build de producción
Next.js también pasó, incluyendo TypeScript; emitió una advertencia por
múltiples lockfiles. ESLint global no pasa por errores existentes en otros
archivos, incluidos hooks de telemetría/formularios no modificados. No se
ejecutó la suite backend completa del proyecto.

**Validación final de persistencia y entrega:** el worker y repositorio reales
entregaron ambos tipos de evento a `public.telemetry_events` en el PostgreSQL
de telemetría desechable. Ambos outbox quedaron `delivered`. Se reabrieron los
mismos IDs para simular una respuesta incierta y repetir el envío: el destino
conservó exactamente una fila por `event_id` y el outbox volvió a `delivered`.
La tabla de telemetría de prueba se creó con `event_id` como clave primaria,
igual que el contrato de destino requerido para `ON CONFLICT`.

El ESLint local instalado se ejecutó directamente sobre los tres archivos
frontend Fase 2 modificados (`InboundFormPanel.tsx`, `OutboundFormPanel.tsx` y
`telemetry-constants.ts`): terminó sin errores ni salida. No se descargó ni
instaló ningún paquete. La ejecución global previa del lint había reportado
problemas en `app/global-error.tsx`, `hooks/useFormLifecycleTracking.ts`,
`hooks/useRecord.ts` y `hooks/useRecords.ts`, ajenos a los archivos modificados
de esta fase; no se hizo limpieza global.

### Fiabilidad de eventos: captura y entrega

En este entorno `DATABASE_URL` es SQLite para inventario y
`TELEMETRY_DATABASE_URL` es PostgreSQL: no hay transacción compartida. Un
`emit_event()` directo tampoco garantiza entrega, porque captura fallos. El
transactional outbox **en la misma base que los movimientos** guarda el
movimiento y evento en una sola transacción. Un worker independiente entrega
eventos a `public.telemetry_events` mediante el adaptador existente. La
unicidad de `event_id` permite reenvíos idempotentes; la entrega es
at-least-once y no hay atomicidad distribuida entre las bases. No escribir KPI
en telemetría.

**Estado actual:** cada movimiento inbound/outbound y su evento pendiente se
guardan en una transacción de `DATABASE_URL`, con UUID estable, payload de
dominio y referencia al movimiento. Las nuevas entradas requieren
`unit_cost >= 0`; el coste es nullable para conservar históricos desconocidos.
El worker usa leases, reintentos con backoff y dead-letter, y marca entregado
tras confirmación del destino. La retención/limpieza no debe confundirse con
atomicidad distribuida. Los eventos `stock_threshold_triggered` y
`kit_cost_variance_detected` están incluidos en el contrato y allowlist y se
validan antes del envío.

La validación final con PostgreSQL desechable confirmó generación → outbox →
worker → `telemetry_events` para `stock_threshold_triggered` y
`kit_cost_variance_detected`, así como la repetición idempotente por `event_id`.
Esto no elimina la limitación de ausencia de transacción distribuida: la
garantía se apoya en outbox at-least-once y unicidad en destino.