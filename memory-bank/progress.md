# Progress â€” Nexova

### Reporting semanal de negocio â€” validaciÃ³n operacional pendiente

- Prefect local en Compose, pool process y deployment
  `weekly_office_program_performance/weekly-office-program-performance`
  estÃ¡n activos; cron `15 0 * * 1` en `UTC`. PostgreSQL 16 de reporting es
  dedicado, healthy y tiene `reporting.pipeline_runs` y
  `reporting.weekly_office_program_performance`.
- Backend reconstruido con Prefect en `requirements.txt`. Se corrigiÃ³ en
  `services/api/app/reporting/trigger.py` el slug del flow del default, que
  discrepaba con el deployment registrado.
- Conectividad de solo lectura desde el worker a `public.telemetry_events`
  verificada para la semana UTC 2026-11-02. La fuente contiene 14 eventos de
  los tipos procesados: 12 inbound, 1 outbound y 1 stock threshold; los 14
  carecen de `programme_id` y solo 6 contienen `office`. La transformaciÃ³n
  real en memoria confirmÃ³ 14 procesados, 14 rechazados y cero filas KPI.
- No se disparÃ³ una corrida Prefect manual: la transformaciÃ³n conocida no
  producirÃ­a mÃ©tricas y registrarÃ­a datos rechazados; no se usÃ³ seed, no se
  cambiÃ³ la fuente y no se escribiÃ³ a reporting. Hace falta corregir/emitir
  eventos de telemetrÃ­a con dimensiones vÃ¡lidas mediante el flujo autorizado
  de inventario antes de validar persistencia end-to-end.
- No se observÃ³ aÃºn una ejecuciÃ³n natural del cron. La prÃ³xima ocurrencia es
  lunes 2026-11-16 00:15 UTC; cron activo no equivale a ejecuciÃ³n verificada.
- RevisiÃ³n repetida el 2026-11-10: `reporting-db` healthy y Prefect Server,
  reporting-worker y backend en ejecuciÃ³n. La API de Prefect confirma que el
  deployment no estÃ¡ pausado y que su schedule estÃ¡ activo con cron
  `15 0 * * 1`, timezone `UTC`. Esto confirma configuraciÃ³n, no que el worker
  haya procesado una ocurrencia natural.
- Pruebas focalizadas de reporting: `uv run --project services/api python -m
  pytest services/api/tests/test_weekly_reporting_pipeline.py
  services/api/tests/test_reporting_api.py -q` â†’ **22 passed** (una warning de
  deprecaciÃ³n de Starlette/httpx). Estas pruebas no ejecutan el flow desplegado
  ni verifican escritura en las bases operativas.
- La corrida manual permanece sin ejecutar. La conectividad a la fuente no se
  reintentÃ³ en esta comprobaciÃ³n porque la credencial de telemetrÃ­a quedÃ³
  expuesta accidentalmente en una salida anterior: rotarla y actualizar el
  secreto local antes de cualquier nuevo acceso. DespuÃ©s, volver a validar
  dimensiones con consultas agregadas; solo solicitar el run si hay eventos
  vÃ¡lidos, y comprobar el run y resultados persistidos.
- Fase 6 iniciada (2026-11-10): suite focalizada ampliada a API reporting,
  transformaciÃ³n/flow, router/repositorio/analÃ­tica tÃ©cnica de telemetrÃ­a â†’
  **53 passed, 1 warning, 4 subtests passed**. Se aÃ±adiÃ³ prueba HTTP mockeada
  para `GET /api/telemetry/report`; `services/api/app/telemetry/analysis.py`
  conserva hash idÃ©ntico a `HEAD`. `git diff --check` pasÃ³.
- La Fase 6 sigue **parcial y no cerrada**: no se ejecutÃ³ CLI ni flow real,
  migraciÃ³n o upsert en PostgreSQL desechable, prueba E2E de moneda/reintentos,
  ni run natural. Los tests usan mocks/unit tests para DB y Prefect; la
  separaciÃ³n `SELECT public.telemetry_events` / escrituras `reporting.*` se
  confirmÃ³ por inspecciÃ³n estÃ¡tica. No hay evidencia de que nuevos eventos
  hayan llegado a telemetrÃ­a. Ver matriz y brechas en
  `docs/aprendiendo/aprendiendo-pipeline-negocio.md`, secciÃ³n 7.
- Sigue pendiente evaluar UI de seguimiento en el backoffice. El POST manual
  ya estÃ¡ protegido para administradores; no se modificÃ³ UI.
- No hubo commit ni push. La ejecuciÃ³n integral y documentaciÃ³n de esta fase
  deben cerrarse cuando exista una semana con eventos de negocio completos.

### Inventory reporting pipeline â€” Phase 3 demo/events (in progress)

- Additional validation: disposable PostgreSQL 16 containers successfully ran schema creation and two reruns of both inventory migrations. A synthetic inbound event was delivered by `deliver_batch` to a separate disposable PostgreSQL telemetry database; a subsequent worker iteration claimed no duplicate, destination row count remained one, and source outbox status was `delivered`. Both containers were stopped/removed; no volumes were mounted.
- Added SQLite legacy-schema migration regression test for nullable idempotency keys, unique indexes, historical-row preservation, and reruns. Added a successful demo-mode test proving no `programme_id` is required when the `--demo` branch is selected.
- Focused validation now passes: `uv run pytest tests/test_inventory_seed.py tests/test_inventory_seed_migration.py tests/test_inventory_phase2_events.py -q` â†’ 25 passed, 13 subtests passed. Editor diagnostics and `git diff --check` were clean at the previous checkpoint; rerun final review after this update.
- Full API suite remains non-conclusive: prior run had 257 passed and one unrelated-looking concurrent TinyDB password-reset JSONDecodeError before KeyboardInterrupt. Do not claim a clean full-suite run.

La Fase 3 amplÃ­a exclusivamente Inventory y el flujo outbox/worker existente;
no incluye reporting/Prefect ni instrumentaciÃ³n frontend. Los datos histÃ³ricos
quedan intactos y los seeds demo son explÃ­citos, aditivos y protegidos para
destinos `development`/`test`. No se realizaron commits, push ni PR.

- Implementados campos `seed_key` en entradas/salidas y `idempotency_key` en
  preparaciones de kit, con migraciÃ³n aditiva y protecciÃ³n de repeticiÃ³n.
- El seed demo crea 16 variantes de activos, 12 entradas, 10 salidas regulares
  y una preparaciÃ³n de kit que registra 3 consumos; dos escenarios usan el
  threshold aprobado. Movimientos pasan por operaciones de dominio para crear
  ledger, valoraciÃ³n y outbox; el seed histÃ³rico conserva sus 6 activos y no
  incorpora el catÃ¡logo demo.
- Regla de cruce: `before_stock >= threshold` y `after_stock < threshold`; sin
  repeticiÃ³n mientras stock siga bajo, y rearme al reponer hasta el lÃ­mite.
- Reparados imports de migraciÃ³n, separaciÃ³n del seed histÃ³rico y test de
  threshold. Focalizados: `uv run pytest tests/test_inventory_phase2_events.py
  tests/test_inventory_seed.py -q` â†’ **21 passed, 13 subtests passed**.
- El CLI permite omitir `--programme-id` con `--demo`; modo histÃ³rico continÃºa
  exigiÃ©ndolo en `main`. AÃºn pendiente test de CLI dedicado.
- DocumentaciÃ³n actualizada en API, worker y contrato de esquema, ademÃ¡s de
  esta guÃ­a y Memory Bank.
- Pendiente: pruebas demo de conteos/idempotencia y payload distinto para
  `seed_key`; validar migraciÃ³n PostgreSQL y flujo outboxâ†’workerâ†’PostgreSQL con
  bases desechables; revisar el stock del manual tras preparaciÃ³n del kit; el
  checklist final/diff tambiÃ©n sigue pendiente.

Detenerse para revisiÃ³n del usuario al completar pruebas seguras y sin commit.

### Inventory reporting pipeline â€” Phase 2 implementation

**Status:** ImplementaciÃ³n de persistencia transaccional y worker terminada; validaciÃ³n integral y decisiones de reglas de negocio documentadas abajo. No iniciar Phase 3 de este pipeline sin aprobaciÃ³n explÃ­cita.

- Entradas y salidas guardan su evento `inbound_order_created` / `outbound_order_created` en `telemetry_outbox` dentro de la misma transacciÃ³n que el movimiento. Los eventos llevan ID estable y dimensiones actuales, incluido programa, coste de entrada y moneda.
- Worker independiente con claims/leases recuperables, fencing token, entrega at-least-once, idempotencia de destino, reintentos acotados, dead-letter, cierre SIGTERM/SIGINT y retenciÃ³n de eventos terminales. Compose expone `inventory-outbox-worker` sin puertos.
- Se agregaron pruebas SQLite aisladas de ciclo de vida del worker; **7 pasan** en `uv run pytest tests/test_inventory_outbox_worker.py -q`. Estas no verifican concurrencia PostgreSQL/`SKIP LOCKED`.
- ValidaciÃ³n backend focalizada: **56 passed, 1 skipped y 28 subtests passed** en la suite de inventario/worker. Frontend: tests de contrato de inventario **12 passed**; `npx tsc --noEmit` finalizÃ³ sin errores. `git diff --check` pasÃ³. La suite frontend completa no se pudo validar porque los intentos no entregaron un resumen/estado concluyente y mostraron ruido `ERR_INVALID_URL` del endpoint de telemetrÃ­a.
- ValidaciÃ³n adicional de las tareas pendientes: suite frontend completa **87/87 passed** (`npm test`); se ajustÃ³ el test de TelemetryService para simular `fetch`, ya que Node no resuelve el endpoint same-origin relativo `/api/telemetry/events` fuera del navegador. `docker compose config --quiet` y `docker compose build` pasaron para los tres servicios. Worker en contenedor: arranque correcto (`Inventory outbox worker started`) contra PostgreSQL desechable. MigraciÃ³n aplicada dos veces en PostgreSQL 16 desechable: tablas/columnas/Ã­ndice de claim correctos, idempotente y preserva la fila legacy con `unit_cost=NULL`. Concurrencia: dos threads/workers reclamaron 20 eventos sin intersecciÃ³n; se probÃ³ expiraciÃ³n/recuperaciÃ³n del lease, token nuevo y rechazo de ack obsoleto. Los contenedores desechables se eliminaron al terminar.
- El esquema de eventos fue corregido para reflejar la implementaciÃ³n real, sin afirmar que el catÃ¡logo entero estÃ© instrumentado. `stock_threshold_triggered` y `kit_cost_variance_detected` no se emiten: falta aprobar umbrales, composiciÃ³n/coste esperado y reglas de variancia; no inferirlos desde las visuales existentes.
- IntegraciÃ³n E2E adicional completada en dos PostgreSQL 16 desechables: se migrÃ³ Inventory/outbox, se preparÃ³ un movimiento/evento inbound de prueba, y el worker Compose lo entregÃ³ al PostgreSQL de telemetrÃ­a (`claimed=1, delivered=1, retried=0, dead=0`). El outbox quedÃ³ `delivered`, el destino tuvo exactamente una fila con tags filtrados correctos, y repetir el mismo `event_id` no duplicÃ³ el evento. Se eliminaron worker y ambas bases temporales. Supabase y bases persistentes de usuario no se usaron.
- Pendiente: despliegue operacional con configuraciÃ³n/datos reales y pruebas de entrega bajo fallos de red/destino. La prueba E2E fue controlada y desechable; no se usÃ³ Supabase ni una base persistente de usuario.

### Telemetry Instrumentation â€” Phase 3: Backoffice Event Instrumentation

**Status:** âœ… **COMPLETE (14/14 events)**

Fase 3 de telemetrÃ­a ha implementado la instrumentaciÃ³n de los 14 eventos frontales aprobados en el backoffice talent-pipeline-tracker, utilizando exclusivamente el servicio centralizado `TelemetryService.track()`.

**Eventos Instrumentados:**
1. âœ… login_succeeded â€” AuthForm despuÃ©s de signIn()
2. âœ… login_failed â€” AuthForm en catch block
3. âœ… account_created â€” AuthForm despuÃ©s de registerUser()
4. âœ… session_expired â€” AuthForm cuando expired prop detectado
5. âœ… inbound_order_created â€” InboundFormPanel despuÃ©s de createInbound()
6. âœ… outbound_order_created â€” OutboundFormPanel despuÃ©s de createOutbound()
7. âœ… incident_status_changed â€” IncidentManagerPanel despuÃ©s de updateIncidentStatus()
8. âœ… supplier_rate_updated â€” SupplierDirectoryPanel despuÃ©s de updateSupplierRate()
9. âœ… frontend_page_loaded â€” LayoutTelemetryProvider en AuthShell
10. âœ… section_viewed â€” useSectionTracking hook con route mapping
11. âœ… frontend_render_error â€” app/error.tsx Error Boundary
12. âœ… form_validation_failed â€” AuthForm en handleSubmit despuÃ©s de validaciÃ³n
13. âœ… form_opened â€” useFormLifecycleTracking hook en mount
14. âœ… form_abandoned â€” useFormLifecycleTracking hook en inactividad/tab hidden

**Infraestructura Nueva Creada:**
- `hooks/useSectionTracking.ts` (140 lÃ­neas) â€” Tracking de page load y section views
- `components/auth/LayoutTelemetryProvider.tsx` (65 lÃ­neas) â€” InicializaciÃ³n global de telemetrÃ­a
- `hooks/useFormLifecycleTracking.ts` (140 lÃ­neas) â€” Tracking de ciclo de vida de formularios

**Componentes Modificados:** 9 (AuthForm, InboundFormPanel, OutboundFormPanel, IncidentManagerPanel, SupplierDirectoryPanel, AuthShell, error.tsx, LayoutTelemetryProvider, useSectionTracking)

**ValidaciÃ³n:**
- âœ… TypeScript compilation: PASS (no type errors en componentes instrumentados)
- âœ… CloudEvents 1.0 compliant
- âœ… Sin PII en payloads
- âœ… Todos los eventos emiten DESPUÃ‰S de confirmaciÃ³n de Ã©xito
- âœ… Integration con TelemetryService centralizado

**DocumentaciÃ³n:**
- `docs/telemetry/implementation/phase-3/PHASE3_COMPLETION_REPORT.md` â€” Reporte detallado de todos los eventos, ubicaciones, payloads y cambios
- `docs/telemetry/telemetry-plan.md` â€” Plan original de eventos (aprobado por usuario)

**PrÃ³ximos Pasos:**
Phase 4 requerirÃ¡ autorizaciÃ³n del usuario para implementar persistencia backend de eventos en PostgreSQL/Supabase.

---

### GestiÃ³n de inventario â€” cierre de `feature/inventory-orm-dual-database`

Estado final documentado de la funcionalidad de inventario ORM con doble base
de datos. `services/api/app/inventory/seed.py` es un comando manual, no forma
parte del startup. Requiere `--environment development|test`, un `DATABASE_URL`
que pase el guard del entorno/destino y `NEXOVA_INVENTORY_SEED_USER_EMAIL` que
resuelva una cuenta Ãºnica y activa con `user_uuid` vÃ¡lido ya persistido en la
TinyDB elegida por `AUTH_DB_PATH` o su ruta por defecto. La resoluciÃ³n abre
TinyDB en solo lectura mediante `app.auth.database.get_database_path()`; no
genera UUID, no usa el ID de documento y no imprime PII ni URL.

La persistencia se mantiene separada: TinyDB contiene auth y otros dominios
existentes; PostgreSQL/Supabase es el almacÃ©n de inventario. Los modelos
SQLModel son `Asset`, `AssetEntry`, `AssetExit`; el stock se calcula como suma
de entradas menos salidas y no se persiste. El seed carga 6 activos, 4 entradas
y 3 salidas. La comprobaciÃ³n final fue reportada por el usuario: el seed se
ejecutÃ³ correctamente en Supabase y `GET /api/inventory/products` devolviÃ³ los
seis productos con `current_stock`. No se repitiÃ³ la carga en este cierre.

El guard solo permite Supabase para el destino de desarrollo explÃ­citamente
autorizado por cÃ³digo; contempla el nombre estÃ¡ndar `postgres` y rechaza
Supabase para tests. Otros destinos PostgreSQL/SQLite deben identificar el
entorno mediante sufijo y SQLite en memoria se limita a `test`. El seed solo
inserta, aborta ante conflicto/stock negativo, deduplica por identidad natural
incluido el UUID y usa advisory transaction lock en PostgreSQL. Mantener estas
barreras; nunca usar Supabase como DB de pruebas.

VerificaciÃ³n final desde `services/api`: `uv run pytest` â†’ **374 passed, 0
failed, 1 skipped**. El skip corresponde a la prueba opcional de concurrencia
PostgreSQL; SQLite no prueba `FOR UPDATE`, advisory locks o aislamiento real de
PostgreSQL. No se modificÃ³ cÃ³digo durante la validaciÃ³n final.

**Advertencia a futuros agentes:** antes de cambiar TinyDB o ejecutar cualquier
seed, consultar `memory-bank/techContext.md`, `memory-bank/progress.md` y la
documentaciÃ³n especÃ­fica; comprobar las rutas efectivas y variables reales del
proceso, y preservar datos existentes. No crear endpoints temporales, editar
registros directamente ni desactivar las protecciones si existe un flujo
normal, autorizado y seguro. No leer, copiar o registrar secretos, UUID reales
ni emails personales en documentaciÃ³n.

DocumentaciÃ³n de aprendizaje: `docs/aprendiendo-gestion-inventario-orm-doble-bbdd.md`.
Hechos verificados en cÃ³digo y tests se distinguen allÃ­ de la carga remota y la
comprobaciÃ³n API confirmadas por el usuario. Quedan pendientes la prueba real
de concurrencia PostgreSQL en una DB desechable, las migraciones/aprovisionamiento
formal y decisiones funcionales sobre stock por oficina/filtros/paginaciÃ³n y
un eventual backfill aprobado para usuarios histÃ³ricos sin UUID.

### GestiÃ³n de inventario â€” Fase 6: integraciÃ³n y regresiÃ³n

Revisada la integraciÃ³n del router `/api/inventory` con `main.py`, sesiones
SQLModel, auth TinyDB/JWT, UUID legacy, schemas, modelos, consultas y escrituras.
Confirmados los seis endpoints (listado/detalle de productos, orders
discriminadas `entry | exit`, creaciÃ³n de producto, inbound y outbound), el
stock derivado y respuestas de error esperadas. La suite completa de backend
se ejecutÃ³ desde `services/api` con `uv` y bases TinyDB temporales:
`uv run pytest tests -q --tb=short` â†’ **358 passed, 1 skipped, 49 subtests
passed**. El skip es el test de concurrencia PostgreSQL; no se configurÃ³ ni
usÃ³ una base PostgreSQL. No se encontraron regresiones en esta ejecuciÃ³n.

SQLite verificÃ³ flujo HTTP, autenticaciÃ³n, validaciÃ³n, stock y rollback; no
certifica `FOR UPDATE`, `READ COMMITTED` ni concurrencia PostgreSQL. El usuario
antiguo sin UUID conserva JWT/lecturas y recibe 428 para escrituras de
movimientos, sin mutaciÃ³n. `git diff --check` pasÃ³. No se leyÃ³ `.env`, no se
accediÃ³ a Supabase/BD real ni se ejecutaron seeds o migraciones.

### GestiÃ³n de inventario â€” Fase 5: escrituras y operaciones

Implementados `POST /api/inventory/products`, `/orders/inbound` y
`/orders/outbound`, con schemas estrictos, responses HTTP tipadas, controles de
integridad y transacciones SQLModel. El stock sigue derivado de movimientos.
Las salidas rechazan stock insuficiente con 400. En PostgreSQL se bloquea la
fila del activo con `SELECT FOR UPDATE` antes de calcular disponibilidad, para
serializar salidas del mismo activo sin mantener un contador redundante.

Los movimientos se atribuyen al `user_uuid` del contexto JWT; nunca se acepta
del payload. Usuarios histÃ³ricos sin UUID pueden leer y crear productos, pero
reciben 428 al intentar escribir movimientos. No hay backfill implÃ­cito. La
prueba PostgreSQL concurrente estÃ¡ implementada pero opcional; SQLite no
certifica `FOR UPDATE`.

VerificaciÃ³n desde `services/api`: `uv run pytest tests/test_inventory_api.py
tests/test_inventory_models.py tests/test_inventory_database.py -q --tb=short`:
**24 passed, 1 skipped, 16 subtests passed**. El Ãºnico skip es la prueba real de
concurrencia, por no haber URL a una base PostgreSQL de test. Se documentan los
detalles y lÃ­mites en `docs/aprendiendo-gestion-inventario-orm-doble-bbdd.md`.
No se accediÃ³ a Supabase ni a `.env`; no se ejecutaron migraciones, commits o
pushes.

### GestiÃ³n de inventario â€” Fase 4: consultas y endpoints de lectura

Implementados `GET /api/inventory/products`, `GET
/api/inventory/products/{asset_id}` y `GET /api/inventory/orders`, todos
protegidos por `get_current_user` sin nuevos roles. El stock se calcula como
entradas menos salidas: las sumas se agrupan por activo antes del join para
evitar multiplicar cantidades cuando hay varios movimientos de ambos tipos.
Orders combina movimientos en respuesta discriminada `type: entry|exit` y
conserva `supplier` o `exit_type`/`assigned_to` segÃºn corresponda.

Las pruebas HTTP usan SQLite temporal y sustituyen tanto la sesiÃ³n como el
usuario; cubren stock con varios movimientos, cero sin movimientos, lista y
detalle, 404, discriminadores y 401. VerificaciÃ³n conjunta con modelos e
infraestructura: `uv run pytest tests/test_inventory_api.py
tests/test_inventory_models.py tests/test_inventory_database.py -q --tb=short`
desde `services/api`: **15 passed, 8 subtests passed**. Filtros y paginaciÃ³n no se implementaron
porque siguen sin contrato. El stock se agrega globalmente por activo, sin
desglose por oficina; confirmar si se necesita stock por oficina. No se conectÃ³
a PostgreSQL/Supabase, no se leyÃ³ `.env` y no se instalaron dependencias.

### GestiÃ³n de inventario â€” Fase 3: modelos y esquemas

AÃ±adidos los modelos SQLModel `Asset`, `AssetEntry` y `AssetExit`, con SKU
Ãºnico, FK y relaciones, timestamps UTC, UUID obligatorio en movimientos,
cantidades positivas y reglas de tipo de salida/asignaciÃ³n. Los schemas HTTP
separan creaciÃ³n y respuesta; `current_stock` estÃ¡ Ãºnicamente en una respuesta
que recibirÃ¡ el valor calculado en una fase posterior. No se aÃ±adieron rutas,
repositorios, lÃ³gica operativa de stock, seeds ni migraciones.

VerificaciÃ³n: tests de modelos y de infraestructura **11 passed, 5 subtests
passed**, usando SQLite temporal. No se conectÃ³ a PostgreSQL/Supabase, no se
leyÃ³ `.env` ni se alteraron datos reales. El enunciado disponible no resuelve
si `quantity` debe ser entero o decimal; se dejÃ³ como `float` provisional y la
duda quedÃ³ documentada en `docs/aprendiendo-gestion-inventario-orm-doble-bbdd.md`.

### Gestor centralizado de incidencias â€” carga histÃ³rica desde CSV

Corregido `scripts/seed_incidents.py` para validar los conteos de calidad sobre
las filas importables del CSV, sin exigir que el total global de TinyDB sea 96.
El resultado distingue `total` de registros vÃ¡lidos del CSV y
`database_total` de registros persistidos, por lo que las incidencias manuales
no se consideran errores.

La base efectiva compartida por API y seed es `services/data/incidents.json`.
La carga real preservÃ³ la incidencia manual ID 1, importÃ³ 96 registros vÃ¡lidos
y creÃ³ 96 claves en `incident_seed_keys`, dejando 97 incidencias en total. Una
segunda ejecuciÃ³n insertÃ³ 0 registros y mantuvo el total en 97. `GET
/api/incidents` devolviÃ³ 97 registros incluyendo la incidencia manual y los
ejemplos histÃ³ricos.

VerificaciÃ³n: tests focalizados de seed y gestor API **12/12 correctos**; CSV
con 100 filas, 96 vÃ¡lidas, cuatro descartadas y conteos esperados por estado y
categorÃ­a. No se eliminÃ³ ni reiniciÃ³ la base, no se instalaron dependencias y
no se creÃ³ commit.

### ActualizaciÃ³n posterior â€” rate limit de password reset

El contrato se fijÃ³ en **3 solicitudes por direcciÃ³n de email durante una hora**.
La implementaciÃ³n y los dos tests del rate limit quedaron alineados con ese
contrato, manteniendo el contador independiente por email y la expiraciÃ³n de la
ventana.

La suite backend completa pasa **279/279 tests**. La validaciÃ³n visual/E2E y la
comprobaciÃ³n contra servicios desplegados reales siguen pendientes; no se han
declarado como realizadas.

## 1. Estado general

El proyecto Nexova se encuentra en una fase de construcciÃ³n progresiva de su ecosistema digital y de AI Engineering.

Ya existe una base de aplicaciones y documentaciÃ³n, y se estÃ¡ incorporando una estructura persistente para que los agentes de desarrollo puedan trabajar de forma consistente sobre el monorepo.

---

## 2. Completado

### Serialization-audit â€” Fases 0-3 (rama `serialization-audit`)

AuditorÃ­a de serializaciÃ³n del backend FastAPI (`services/api`): inventario de
31 rutas de negocio + infraestructura, clasificaciÃ³n A/B/C, dos cambios de
contrato (Clase B) y pruebas de contrato. Inventario completo y estado final en
`docs/serialization-audit.md`.

- **Fase 1 â€” Suppliers, OpciÃ³n A.** `SupplierCreate` separado de
  `SupplierFields`: el cliente ya no envÃ­a `status` en `POST /api/suppliers`;
  el servidor fija `active` (`Supplier.from_create`, parÃ¡metro interno
  `status` para el seed). El seed conserva los 2 proveedores semilla
  `suspended` intencionales. Frontend (`types/supplier.ts`,
  `SupplierDirectoryPanel.tsx`) sin campo/selector de status en creaciÃ³n;
  `PATCH /status` sigue funcionando. Tests adaptados y nuevos en
  `test_supplier_models.py`, `test_supplier_api.py`, `test_supplier_seed.py`,
  `test_auth_unit5.py` (payloads sin status).
- **Fase 2 â€” Incident analysis.** Creado
  `services/api/app/incidents/schemas.py` con `IncidentAnalysisResponse`
  (exactamente los 8 campos agregados de `_serialize_result`). AÃ±adido
  `response_model=IncidentAnalysisResponse` a `POST /api/incidents/analyze`
  en `app/main.py`. Payload de salida sin cambios (el frontend
  `IncidentAnalysisResult` no se tocÃ³).
- **Fase 3 â€” Pruebas de contrato y documentaciÃ³n.** AÃ±adidos a `test_api.py`:
  `test_analyze_response_has_exactly_aggregate_keys` (bloquea campos
  extra/faltantes) y `test_openapi_declares_incident_analysis_response_schema`
  (verifica el `response_model` documentado en OpenAPI sin campos crudos).
  DocumentaciÃ³n finalizada en `docs/serialization-audit.md` (Â§7) con los
  resultados reales.

VerificaciÃ³n (bases TinyDB aisladas en rutas temporales + `env -u CORS_ORIGINS`):
- Suppliers tras Fase 1: **24 passed, 8 subtests** (models/seed/api).
- Suite completa tras Fase 1: **379 passed, 1 skipped, 63 subtests** (tras
  corregir 3 payloads con `status` en `test_auth_unit5.py`).
- Suite completa tras Fase 2: **379 passed, 1 skipped, 63 subtests**.
- Suite completa tras Fase 3: **381 passed, 1 skipped, 63 subtests**.
- Frontend backoffice: `npx tsc --noEmit` y `eslint` en los archivos
  modificados sin errores.
- `git diff --check` sin errores.

DecisiÃ³n documentada: los errores se documentan por familia (no se unifican),
los listados no aÃ±aden paginaciÃ³n/proyecciÃ³n y la exportaciÃ³n CSV se conserva.
La ruta `/__test/unexpected-error` es exclusiva de tests. Sin commits ni PR
(no solicitados). Las advertencias sobre `.env`, rutas reales de TinyDB y
preservaciÃ³n de datos se mantienen: nunca leer el `.env` real ni usar
Supabase/BD real como base de pruebas.

### Error-handling-audit â€” Fase 1 backend

Reforzada la gestiÃ³n de errores y el diagnÃ³stico seguro en autenticaciÃ³n:

- El adaptador Resend usa `logging` con dominio del destinatario, tipo de fallo
  y estado HTTP, sin emails completos, tokens ni cuerpos de respuesta.
- La creaciÃ³n de perfiles usa `ProfilePersistenceError`; el registro de usuario
  conserva la compensaciÃ³n y registra de forma segura los fallos del rollback.
- Las respuestas de error mantienen los cÃ³digos y contratos existentes.

VerificaciÃ³n: 46 tests de email/repositorios y 66 tests HTTP de usuarios,
perfiles y autenticaciÃ³n focalizada pasan. La suite ampliada de auth ejecuta
193 tests: 191 pasan y 2 fallan en el rate limit de password reset, un fallo
preexistente y ajeno a estos archivos. No se modificaron scripts Python ni el
frontend.

### Error-handling-audit â€” Fase 2 scripts y CSV

Implementado el tratamiento controlado de errores en el lector CSV y el seed de
incidencias. El parser usa modo estricto y convierte `csv.Error` en
`CsvReadError` con nÃºmero de fila; los estados desconocidos generan
`INVALID_STATUS` sin `ValueError` inesperado. El seed prepara todas las filas
antes de abrir la base y devuelve cÃ³digo no cero por `stderr` ante errores
esperables, sin afirmar rollback transaccional de TinyDB.

VerificaciÃ³n: slice de lector, validaciÃ³n, anÃ¡lisis, exportaciÃ³n, CLI, API y
seed con 41 tests correctos; validaciÃ³n compartida con 2 tests correctos; seed
aislado con 96 inserciones en la primera ejecuciÃ³n y 0 en la segunda. La suite
backend completa ejecuta 266 tests: 264 correctos y 2 fallan en los tests
preexistentes de rate limit de password reset. `analyze.py`, exportaciÃ³n,
frontend, autenticaciÃ³n y rate limiting no se modificaron.

### Error-handling-audit â€” Fase 3 clientes API del frontend

Reforzados los clientes API de `uis/backoffice/talent-pipeline-tracker` sin
modificar componentes visuales. Se aÃ±adiÃ³ `lib/api-errors.ts` para clasificar
errores HTTP, red, timeout, parseo y cancelaciÃ³n, interpretar formatos de error
conocidos y redactar emails, tokens, URLs y rutas internas.

`lib/api.ts`, `lib/nexova-api.ts` y `lib/incident-analysis-api.ts` ahora
gestionan cuerpos JSON, texto plano, respuestas vacÃ­as, JSON invÃ¡lido, timeout
configurable y cancelaciÃ³n externa. La exportaciÃ³n conserva el tipo `Blob` y
los clientes existentes mantienen sus firmas de Ã©xito.

VerificaciÃ³n: tests nuevos de Tracker e Incident Analysis **9/9**, tests de
Nexova **24/24**, suite frontend completa **56/56**, TypeScript correcto y build
correcto. El lint mantiene 3 errores y 5 warnings preexistentes en archivos del
Tracker no relacionados con esta fase. Los componentes visuales y los clientes
de negocio que delegan en Nexova no se modificaron; la traducciÃ³n uniforme de
mensajes en esos consumidores queda pendiente para la siguiente fase.

### Error-handling-audit â€” Fase 4 consumidores frontend y validaciÃ³n integrada

AÃ±adido `lib/api-error-messages.ts` para centralizar mensajes seguros en los
consumidores genÃ©ricos. Los hooks de candidaturas y notas, perfil, Supplier
Directory e Incident Analysis ya no propagan directamente `error.message`.
Mantienen sus fallbacks contextuales y dejan intactas las traducciones
especÃ­ficas de autenticaciÃ³n, password reset e Incident Manager.

Las cancelaciones esperadas devuelven `null` y no generan mensajes visibles;
red, timeout y errores HTTP siguen distinguiÃ©ndose internamente. Se aÃ±adieron
2 pruebas focalizadas para el traductor comÃºn.

La Fase 4 queda verificada con la suite frontend
completa **58/58**, TypeScript
y build correctos, y `git diff --check` correcto. El lint mantiene 3 errores y
5 warnings preexistentes. No se modificaron backend, rate limiting, CSV,
seeders ni se creÃ³ commit.

### Error-handling-audit â€” Fase 5 validaciÃ³n integrada y cierre

Se ejecutaron primero los slices focalizados sobre bases TinyDB temporales:
auth/email/perfiles/password reset **127 tests, 125 correctos y 2 fallos** del
rate limit conocido; CSV/validaciÃ³n/anÃ¡lisis/exportaciÃ³n/CLI/seed **36/36**; API
HTTP/Incident Manager/Supplier/CORS **36/36**; y frontend **58/58**.

La suite backend completa ejecutÃ³ **267 tests: 265 correctos y 2 fallos**, los
mismos asserts del rate limit. La suite frontend completa quedÃ³ en **58/58**.
TypeScript, build de Next.js y `git diff --check` pasaron. Lint mantiene 3
errores y 5 warnings preexistentes. FastAPI emitiÃ³ Ãºnicamente el warning de
deprecaciÃ³n sobre `httpx`/`TestClient`.

El fixture `scripts/incidents-nexova.csv` estuvo presente durante la validaciÃ³n
y tenÃ­a 101 lÃ­neas. No se ejecutaron seeders contra datos reales, no se
instalaron dependencias y no se creÃ³ commit. No existen Error Boundaries
globales en el Tracker y no hay navegador/runner E2E disponible, por lo que la
validaciÃ³n visual queda pendiente.

Los riesgos residuales son el contrato no resuelto del rate limit, la falta de
atomicidad multioperaciÃ³n de TinyDB, la ausencia de Error Boundary global y la
falta de verificaciÃ³n contra servicios desplegados reales. La matriz completa
de hallazgos y recomendaciones estÃ¡ en `docs/aprendiendo-gestion-errores.md`.

### Error Boundaries globales de Next.js â€” correcciÃ³n posterior a la Fase 5

Implementados `app/error.tsx` y `app/global-error.tsx` en
`uis/backoffice/talent-pipeline-tracker`. Ambos son Client Components
compatibles con Next.js 16.3.3 y App Router. Muestran mensajes genÃ©ricos en
espaÃ±ol, permiten reintentar mediante `reset()` y ofrecen navegaciÃ³n a `/` sin
exponer mensajes de error, trazas ni datos internos. El registro tÃ©cnico se
limita al identificador `error.digest` cuando estÃ¡ disponible.

No se modificaron `AuthProvider`, `AuthShell`, autenticaciÃ³n, logout, clientes
API, backend ni dependencias. La suite frontend ejecuta **58/58 tests
correctos**, TypeScript y el build de Next.js pasan, y `git diff --check` es
correcto. No se realizÃ³ validaciÃ³n visual en navegador; esa comprobaciÃ³n queda
pendiente.

### Password reset â€” Fase 1 backend

Implementado el flujo backend de recuperaciÃ³n y cambio de contraseÃ±a bajo el
dominio de auth existente:

  expiraciÃ³n y uso Ãºnico en una tabla TinyDB separada.
  real ni se han enviado emails.

### Contexto y documentaciÃ³n

  - `memory-bank/projectbrief.md`
  - `memory-bank/techContext.md`
  - `memory-bank/progress.md`

### Web corporativa

La web pÃºblica de Nexova estÃ¡ desarrollada e incluye:


### Talent Pipeline Tracker

La aplicaciÃ³n estÃ¡ ubicada actualmente en:

`uis/talent-pipeline-tracker/`

Funcionalidades implementadas y verificadas:


### Arquitectura tÃ©cnica verificada

Se ha revisado y confirmado la existencia y funcionamiento previsto de:


### AutenticaciÃ³n del backoffice â€” AUTH-02, fase 2

Implementada la infraestructura frontend de cliente Nexova y sesiÃ³n JWT en
`uis/backoffice/talent-pipeline-tracker`:

  de sesiÃ³n mediante `/auth/me`, cierre local e invalidaciÃ³n ante `401`;
  inyectados para tests y evitando invocarlo con receptor incorrecto;
  permanecen separados;

Esta fase no aÃ±ade pantallas de autenticaciÃ³n ni protecciÃ³n global de rutas.
VerificaciÃ³n: 12 tests, TypeScript, lint focalizado y build pasan. El lint global
sigue reportando errores React preexistentes en `app/page.tsx`,
`hooks/useRecord.ts` y `hooks/useRecords.ts`.

### AutenticaciÃ³n del backoffice â€” AUTH-02, fase 3

Implementadas las rutas `/login` y `/register` con un formulario compartido,
validaciÃ³n en espaÃ±ol, estados de envÃ­o, prevenciÃ³n de peticiones duplicadas y
controles accesibles. El login envÃ­a el formulario OAuth2 esperado, guarda el
JWT mediante el cliente compartido, valida `/auth/me` y redirige a `/`; el
registro envÃ­a Ãºnicamente email y contraseÃ±a, y ofrece continuar al login sin
crear sesiÃ³n. No se aÃ±adieron guards ni se protegieron rutas existentes.

VerificaciÃ³n: 21 tests frontend, 64 tests backend de auth, TypeScript, lint
focalizado, build y comprobaciÃ³n HTTP SSR completados. El lint global sigue
fallando solo por los tres errores React preexistentes indicados en fase 2.

### AutenticaciÃ³n del backoffice â€” fases 4 y 5

La fase 4 se considera verificada por el usuario: registro, login, perfil,
Supplier Directory, Incident Analysis, menÃº `My Profile` y logout funcional.

En fase 5 se revisaron el proveedor, almacenamiento/token, cliente, logout,
layout, rutas y requisitos backend. Ya existÃ­a `AuthShell`: protege
`/suppliers` y `/account/profile` y sus subrutas; login/registro son pÃºblicos.
Tracker e Incident Analysis mantienen sus clientes separados y acceso pÃºblico.
Se reutilizÃ³ este guard, sin crear middleware ni otro `PrivateRoute`.

Se reprodujo y corrigiÃ³ una carrera: una respuesta pendiente de `/auth/me`
podÃ­a restaurar `authenticated` despuÃ©s del logout. El cliente ahora descarta
resultados obsoletos y evita que un `401` anterior invalide una sesiÃ³n nueva.
Se mantiene la expiraciÃ³n existente por `401` y el reintento ante errores de
red/servidor, que bloquean contenido sin eliminar el token.

VerificaciÃ³n: 34 tests frontend, TypeScript, lint focalizado, build de Next y
`git diff --check` pasan. Persiste el aviso de mÃºltiples lockfiles. Chromium
completÃ³ 18 escenarios en escritorio (1440px) y mÃ³vil (390px), con API simulada
y peticiones externas bloqueadas: acceso privado sin sesiÃ³n, login/registro,
acceso autenticado a perfil/proveedores, logout y reentrada denegada, token
rechazado por `401` y validaciÃ³n fallida por red/503. Se revisaron capturas.
No equivale a un nuevo E2E contra la API real. Las herramientas de navegador
se instalaron temporalmente fuera del repo; no se aÃ±adieron dependencias.
No se modificÃ³ backend ni `services/data/`, ni se ejecutaron seeders,
commits o push.

### Password reset â€” Fase 2 frontend

Implementadas las pantallas `/forgot-password`, `/reset-password` y
`/account/change-password` en `uis/backoffice/talent-pipeline-tracker`.
El token de recuperaciÃ³n se lee desde `searchParams` y no se guarda en
localStorage ni en `AuthProvider`. Las peticiones pÃºblicas no envÃ­an Bearer;
el cambio de contraseÃ±a reutiliza el cliente autenticado y cierra la sesiÃ³n
local tras completarse, porque el backend invalida el JWT.

Se aÃ±adiÃ³ `PasswordResetForm` con validaciÃ³n, mensajes genÃ©ricos, estados de
Ã©xito/error y prevenciÃ³n de envÃ­os concurrentes. `/account/change-password`
queda protegido por el `AuthShell` existente y el login incluye el enlace de
recuperaciÃ³n.

VerificaciÃ³n realizada: 41 tests frontend, `npx tsc --noEmit`. Pendientes de
ejecutar en esta fase: lint y build. No se modificÃ³ backend, `services/data/`,
`uis/website`, ni se creÃ³ commit o push.

### Password reset â€” Fase 3 seguridad

Auditado y reforzado el flujo completo de password reset. `forgot-password`
mantiene respuestas homogÃ©neas para cuentas existentes, inexistentes e
inactivas. Los tokens usan fuente criptogrÃ¡ficamente segura, solo se persiste
su hash, tienen expiraciÃ³n, uso Ãºnico y rotaciÃ³n; la rotaciÃ³n y el consumo
quedan protegidos por locks de proceso. La actualizaciÃ³n de contraseÃ±a tambiÃ©n
serializa el incremento de `credentials_version`.

El frontend redirige a `/login?reset=1` tras un reset correcto, eliminando el
token de la URL mediante una ruta fija. No se introdujeron almacenamientos,
logs ni redirects controlados por el usuario. Resend sigue siendo backend-only,
CORS continÃºa usando origins explÃ­citos y bcrypt no se ha sustituido.

VerificaciÃ³n focalizada: 11 tests backend de password reset correctos. La
limitaciÃ³n de TinyDB multi-worker queda documentada: los locks solo coordinan
un proceso y no sustituyen una base de datos transaccional distribuida.

### Password reset â€” Fase 4 extensiones opcionales

Implementadas las tres extensiones no evaluables: plantilla HTML sencilla para
el email mediante `EmailSender`, rate limiting de 3 solicitudes por email en
una ventana de una hora y auditorÃ­a TinyDB de solicitudes/resultados con
timestamp, IP, email cuando procede y tipo de evento. No se guardan secretos,
contraseÃ±as, tokens ni JWT. Los tests usan `FakeEmailSender`; Resend no se ha
activado ni modificado operativamente.

### Fase 6 â€” AuditorÃ­a final previa a la entrega

La auditorÃ­a histÃ³rica ejecutÃ³ 222 tests backend, con 212 correctos; los fallos
restantes se atribuyeron entonces a un fixture ausente,
`scripts/incidents-nexova.csv`, que no estaba disponible en aquella ejecuciÃ³n.
En la validaciÃ³n integrada actual el fixture estÃ¡ presente y la suite backend
ejecuta 267 tests, con 265 correctos y solo los 2 fallos conocidos de rate
limit. Auth, perfiles, CORS, Supplier Directory, CSV, anÃ¡lisis y seed pasan en
los slices cubiertos.
La suite se ejecutÃ³ sobre una copia aislada en `/tmp` porque
`AuthSemanticTests`/`IncidentsPublicTests` abren la BD por defecto.

Frontend: 34 tests, TypeScript, build y los 18 escenarios de navegador pasan.
El lint global mantiene 3 errores y 5 avisos preexistentes de React en
`app/page.tsx`, `hooks/useRecord.ts`, `hooks/useRecords.ts` y dos componentes
del Tracker; ningÃºn archivo de autenticaciÃ³n aparece afectado.

Hallazgo de seguridad corregido: `services/data/` no estaba ignorado y
`git add -A` habrÃ­a subido `auth.json` (emails y hashes bcrypt) y
`suppliers.json`. Se aÃ±adiÃ³ al `.gitignore` raÃ­z junto a `.env.local.save`.
Los archivos no se leyeron ni modificaron.

Pendientes resueltos tras la auditorÃ­a: `httpx` se declara en el extra `test`
de `services/api/pyproject.toml` (y `uv.lock`); `ConfigTests`
(`test_auth_unit1`) carga una copia aislada de `config.py` y ya no depende del
orden de importaciÃ³n. En la validaciÃ³n integrada de Fase 5 el fixture CSV estÃ¡
presente y los tests de datos pasan; se mantiene la recomendaciÃ³n de verificar
su ubicaciÃ³n antes de ejecutar pruebas.


## 3. Estado actual del Talent Pipeline Tracker

## Fase 1 â€” Gestor de Incidencias Centralizado

Implementados el dominio persistente del gestor en TinyDB, sus endpoints
CRUD/summary y la validaciÃ³n de transiciones de estado. El modelo del gestor es
independiente del dominio existente de Incident Analysis. TambiÃ©n se aÃ±adiÃ³
`scripts/seed_incidents.py`, que transforma exclusivamente
`scripts/incidents-nexova.csv`, descarta las filas invÃ¡lidas y controla
duplicados sin almacenar `ticket_id` en `Incident`.

VerificaciÃ³n de seed en base temporal: 96 inserciones iniciales, 0 inserciones
en la segunda ejecuciÃ³n, 4 filas descartadas (`18`, `44`, `87`, `91`), estados
`open=27`, `resolved=56`, `discarded=13` y categorÃ­as
`technical_failure=49`, `process_error=35`, `client_complaint=12`. El API del
gestor tiene 4 tests focalizados correctos. La fase frontend queda pendiente de
confirmaciÃ³n explÃ­cita.
confirmaciÃ³n explÃ­cita.

## Fase 2 â€” Frontend del Gestor de Incidencias

Implementado el frontend del gestor en `/incidents/manager`, manteniendo
`/incidents` para Incident Analysis. Incluye creaciÃ³n de incidentes, filtros por
estado/origen/sede/categorÃ­a, resumen por estado, listado y transiciones de
estado vÃ¡lidas. La ruta del manager queda protegida por el `AuthShell` y se
aÃ±adiÃ³ al menÃº principal.

Se aÃ±adieron contratos TypeScript, cliente API autenticado y propagaciÃ³n de
errores estructurados con campo. La validaciÃ³n de navegaciÃ³n y del parser de
errores queda cubierta por la suite frontend.

VerificaciÃ³n: 46 tests frontend correctos, TypeScript y build de Next.js
correctos. El lint global sigue fallando Ãºnicamente por los tres errores React
preexistentes en `app/page.tsx`, `hooks/useRecord.ts` y `hooks/useRecords.ts`,
con cinco avisos preexistentes. No se modificÃ³ backend en esta fase.

## Fase 3 â€” IntegraciÃ³n, documentaciÃ³n y validaciÃ³n final

El backend del Incident Manager quedÃ³ protegido con JWT Bearer mediante la
dependencia comÃºn de autenticaciÃ³n. Se actualizaron los tests focalizados para
cubrir `401` sin credenciales y se documentaron API, configuraciÃ³n CORS,
`INCIDENTS_DB_PATH`, ubicaciÃ³n del CSV, seed idempotente, ejecuciÃ³n y pruebas en
los README del servicio y del frontend.

ValidaciÃ³n aislada del seed: 96 inserciones en la primera ejecuciÃ³n, 0 en la
segunda, con TinyDB temporal. La suite focalizada del manager pasa: 5 tests.
La suite backend completa ejecuta 253 tests: 251 pasan y 2 fallan Ãºnicamente en
los tests ajenos de rate-limit de password reset, debido al cambio existente en
`services/api/app/auth/password_reset.py` que no se modificÃ³.

Frontend: 46 tests, TypeScript y build pasan. El lint global conserva los tres
errores y cinco avisos preexistentes del Tracker. `git diff --check` pasa.

La API se reiniciÃ³ en `localhost:8000` con `CORS_ORIGINS` explÃ­cito para
localhost y `https://friendly-barnacle-qv5p44r9rxq2644j-3000.app.github.dev`,
ademÃ¡s de TinyDB temporales. Se comprobÃ³ el preflight HTTPS (`200`), el login
vÃ¡lido (`200` con CORS), el login invÃ¡lido (`401` con CORS) y el manager sin
token (`401`). El default de `app/main.py` tambiÃ©n deriva el origen exacto de
Codespaces desde `CODESPACE_NAME`, sin permitir wildcard. La navegaciÃ³n vuelve a
mostrar Login, registro y recuperaciÃ³n mientras no hay sesiÃ³n validada, y
mantiene perfil/cambio de contraseÃ±a para sesiones autenticadas.

La suite focalizada de CORS, auth y manager pasa: 75 tests. Frontend: 46 tests,
TypeScript y build pasan. Los dos fallos de password reset y los tres errores de
ESLint del Tracker siguen siendo preexistentes y ajenos; no se modificÃ³
`services/api/app/auth/password_reset.py`.

La validaciÃ³n visual interactiva en navegador no se realizÃ³ porque no hay una
herramienta de navegador automatizado disponible en este entorno. Para la
revisiÃ³n manual, abrir `http://localhost:3000/login`, iniciar sesiÃ³n con un
usuario vÃ¡lido y comprobar `/incidents/manager` en escritorio y mÃ³vil; verificar
tambiÃ©n que `/incidents` continÃºa mostrando Incident Analysis.

### Header responsive del backoffice

`AuthShell` ahora ofrece navegaciÃ³n horizontal con dropdowns accesibles para
Incidents y Account/Profile en escritorio, y un menÃº hamburguesa compacto en
mÃ³vil. Los menÃºs se cierran al seleccionar un enlace, pulsar Escape, hacer
click fuera o cerrar sesiÃ³n; se mantienen las rutas existentes, el guard de
autenticaciÃ³n y el logout compartido.

VerificaciÃ³n: 46 tests frontend, TypeScript y build pasan; `git diff --check`
tambiÃ©n pasa. El lint global mantiene los 3 errores y 5 avisos preexistentes
del Tracker. No se realizÃ³ validaciÃ³n visual automatizada en navegador.

El Talent Pipeline Tracker dispone actualmente de una estructura funcional completa para el caso de uso de gestiÃ³n de candidaturas.

La arquitectura conocida es:

`app â†’ components â†’ hooks â†’ lib â†’ API`

La aplicaciÃ³n utiliza la API de 4Geeks:

`https://playground.4geeks.com/tracker/api/v1`

El frontend estÃ¡ construido con:

- Next.js 16.3.3
- React 19.2.8
- TypeScript 5
- Tailwind CSS 4

La aplicaciÃ³n estÃ¡ ubicada actualmente en `uis/backoffice/talent-pipeline-tracker`, siguiendo la estructura definida para las aplicaciones internas de Nexova. La web pÃºblica existente estÃ¡ organizada en `uis/website`.

- ValidaciÃ³n final: `npm run build` ejecutado desde `uis/backoffice/talent-pipeline-tracker` correctamente. Next.js compilÃ³ TypeScript y generÃ³ todas las rutas sin errores. Se mantiene Ãºnicamente el warning sobre mÃºltiples `package-lock.json`.
- ValidaciÃ³n visual: comprobadas correctamente la website pÃºblica y el backoffice mediante las previsualizaciones de Codespaces.
---

## 4. Hallazgos y pendientes confirmados

- La ruta predeterminada de Supplier es `services/data/suppliers.json`; no se
  detectÃ³ override en el entorno inspeccionado y el archivo existe con 15
  entradas. Esto no demuestra quÃ© ruta usÃ³ un proceso histÃ³rico ni por quÃ© se
  observÃ³ `[]` anteriormente.
- Sin token, Supplier responde `401 Not authenticated`; con token invÃ¡lido,
  `401 Invalid credentials`. El registro no inicia sesiÃ³n automÃ¡ticamente.
- En la validaciÃ³n de Fase 5 `scripts/incidents-nexova.csv` estÃ¡ presente y
  contiene 101 lÃ­neas; el slice de CSV, anÃ¡lisis, exportaciÃ³n, CLI y seed pasa
  36/36. La ubicaciÃ³n efectiva debe seguir verificÃ¡ndose antes de ejecutar
  procesos en otros entornos.
- La causa exacta de los errores de hidrataciÃ³n observados no estÃ¡ confirmada.
  La soluciÃ³n actual evita renderizar el formulario antes de hidratar, pero se
  debe completar la validaciÃ³n de login/registro en Chrome.
- El README de `services/api` estaba desactualizado respecto a Supplier y se
  sincronizÃ³ con la implementaciÃ³n actual.

## 5. Siguiente trabajo

1. Validar manualmente login, registro, persistencia de sesiÃ³n y acceso a
   Supplier Directory en Chrome con API/base URL y CORS correctos.
2. Confirmar la disponibilidad y ubicaciÃ³n esperada del CSV de pruebas de
   Incident Analysis.
3. Si reaparece una respuesta vacÃ­a de Supplier, registrar URL/base efectiva,
   estado HTTP, presencia/validez del token (nunca su valor) y ruta DB del
   proceso antes de atribuir una causa.

No se ejecutaron tests, seeders ni scripts de anÃ¡lisis durante esta actualizaciÃ³n
documental para evitar efectos sobre datos locales.

---

## AuditorÃ­a inicial de almacenamiento de telemetrÃ­a

Se completÃ³ la primera etapa de anÃ¡lisis para almacenar telemetrÃ­a en
Supabase, sin cambios de runtime, frontend ni base de datos. El receptor vigente
es `POST /api/telemetry/events`; sigue siendo un stub que valida el lote entero
mediante `TelemetryBatch` y solo registra logs. La documentaciÃ³n inicial quedÃ³
en `docs/aprendiendo/aprendiendo-telemetry-storage.md`.

La discrepancia del esquema se resolviÃ³ mediante aprobaciÃ³n del usuario: ocho
columnas (`id`, `event_id`, `event_type`, `timestamp`, `source`, `session_id`,
`schema_version`, `tags`) e Ã­ndices por `timestamp`, `event_type` y GIN para
`tags`. La migraciÃ³n no aplicada estÃ¡ en
`services/api/scripts/migrations/001_create_telemetry_events.sql`. Se intentÃ³
aplicarla desde el contenedor `backend`, pero `DATABASE_URL` estÃ¡ configurada
para SQLite y `psycopg` rechazÃ³ esa URL antes de ejecutar DDL; no se alterÃ³
Supabase ni otra base. La migraciÃ³n requiere una URL PostgreSQL/Supabase
autorizada. Posteriormente se verificÃ³ mediante catÃ¡logo de solo lectura que la
tabla fue creada manualmente en Supabase, con sus tres Ã­ndices y trigger
inmutable, pero inicialmente no coincidÃ­a por completo con el contrato
aprobado. Tras comprobar que tenÃ­a cero filas, se aplicÃ³
`services/api/scripts/migrations/002_align_existing_telemetry_events.sql`:
solo usa `ALTER TABLE`/`ALTER INDEX`, no recrea la tabla ni modifica filas.
La comprobaciÃ³n posterior confirmÃ³ `id` con identidad `ALWAYS`, restricciones
`NOT NULL`, lÃ­mites de los `VARCHAR`, unicidad de `event_id`, el nombre previsto
para el Ã­ndice GIN y la permanencia del trigger. La Fase 1 de almacenamiento
queda terminada.

### Fase 2: endpoint real de almacenamiento de telemetrÃ­a

El stub de `POST /api/telemetry/events` fue sustituido sin cambiar su ruta ni el
envelope del frontend. El endpoint recibe el body de forma laxa, valida cada
elemento mediante `TelemetryEvent.model_validate`, conserva los vÃ¡lidos y
responde con `received`, `stored` y `rejected`. Los invÃ¡lidos no cancelan el
lote; los envelopes sin un array `events` responden 400.

La persistencia estÃ¡ aislada en `app/telemetry/repository.py`: usa Ãºnicamente
`TELEMETRY_DATABASE_URL`, exige PostgreSQL y no recurre a `DATABASE_URL`, que
puede seguir siendo SQLite para inventario. El adaptador ejecuta un solo
`INSERT ... VALUES ... ON CONFLICT DO NOTHING RETURNING` por lote y no contiene
operaciones UPDATE o DELETE. `tags` se filtra con los allowlists derivados del
catÃ¡logo documentado. Si falta la configuraciÃ³n o falla PostgreSQL, el endpoint
devuelve 503 sin revelar secretos.

Pruebas focalizadas ejecutadas: 29 correctas (modelos, configuraciÃ³n, allowlist
e integraciÃ³n HTTP con repositorio falso). Se aÃ±adiÃ³ `httpx2` solo al extra de
test porque Starlette lo requiere para `TestClient`; se actualizÃ³ `uv.lock`. No
se insertaron eventos de prueba en Supabase. Pendiente Fase 3: configurar
`TELEMETRY_DATABASE_URL` en el proceso FastAPI activo y verificar desde el
backoffice los eventos y filas reales en Supabase.

### Fase 3: verificaciÃ³n end-to-end completada

La suite focalizada de telemetrÃ­a volviÃ³ a pasar (29 pruebas). Se resolviÃ³ la
configuraciÃ³n privada de `TELEMETRY_DATABASE_URL` sin modificar `DATABASE_URL`:
la URI del pooler contenÃ­a inicialmente problemas de formato y autenticaciÃ³n.
La conexiÃ³n real del backend a Supabase quedÃ³ confirmada despuÃ©s de corregirla.

Un lote mixto enviado mediante el proxy del backoffice devolviÃ³ HTTP 200 con
`received: 2`, `stored: 1` y `rejected: 1`. La fila vÃ¡lida se verificÃ³ en
`public.telemetry_events`; sus tags permitidos fueron almacenados y una clave no
aprobada fue descartada. La validaciÃ³n manual del backoffice tambiÃ©n quedÃ³
confirmada contra filas reales: `inbound_order_created` y
`outbound_order_created` desde `/nexova/inventory`, y `login_failed` desde
`/nexova/auth`. Los tres incluyeron `session_id` y `schema_version: 1.0.0`;
los tags observados coincidieron con sus allowlists. El contrato histÃ³rico de
`login_failed` se alineÃ³ con el flujo seguro: `user_uuid` es opcional porque no
hay sesiÃ³n autenticada y no se deriva desde credenciales; `failure_reason` es
suficiente para el evento y la mÃ©trica A1. La Fase 3 queda terminada.

## 7. Criterio para actualizar este archivo

Este archivo debe actualizarse cuando cambie de forma relevante el estado del proyecto.

Registrar:

- nuevas funcionalidades completadas;
- nuevas aplicaciones;
- cambios importantes de arquitectura;
- decisiones tÃ©cnicas relevantes;
- tareas importantes pendientes;
- problemas relevantes encontrados y resueltos.

No registrar aquÃ­ cada pequeÃ±o cambio de cÃ³digo.

El objetivo es que un agente pueda leer este archivo y entender rÃ¡pidamente dÃ³nde estÃ¡ el proyecto y cuÃ¡l es el siguiente trabajo pendiente.

## 8. PrÃ¡ctica de contenerizaciÃ³n â€” rama `Containerization`

Completada la prÃ¡ctica de contenerizaciÃ³n local de Nexova en la rama
`Containerization`. El alcance no incluye despliegue en VPS; no se realizÃ³ ni es
necesario para dar por terminada esta parte.

### Resultado implementado

- `docker-compose.yml` coordina los servicios `interfaces` y `backend`.
- La web pÃºblica queda publicada en `http://localhost:3000` y el backoffice en
  `http://localhost:3001`.
- La API queda publicada en `http://localhost:8000`.
- Los dos servicios comparten la red Docker `nexova` y el backend es accesible
  internamente por el nombre `backend` y el puerto `8000`.
- El contenedor de interfaces arranca Next.js en modo desarrollo y un proxy
  Node que sirve la web pÃºblica, expone el backoffice y reenvÃ­a `/api/*` a
  `http://backend:8000`.
- El backend arranca Uvicorn con `--reload`.
- Los bind mounts permiten editar el cÃ³digo fuente desde el host y que los
  contenedores lo vean. `node_modules` y `.next` usan volÃºmenes Docker; el
  backend monta tambiÃ©n `services/data` para conservar la persistencia local.
- `.env.example` documenta los valores necesarios. En Docker las variables
  `NEXT_PUBLIC_NEXOVA_API_BASE` y
  `NEXT_PUBLIC_INCIDENT_ANALYSIS_API_BASE` deben ser `/api`.

### DecisiÃ³n de comunicaciÃ³n entre servicios

Los clientes frontend no deben usar `http://backend:8000` directamente, porque
el navegador del usuario no resuelve nombres internos de Docker. En su lugar,
usan `/api` en el mismo origen de la interfaz y el proxy interno comunica con
`backend:8000`. Esto evita `localhost` e IPs hardcodeadas para la comunicaciÃ³n
entre contenedores y mantiene los prefijos actuales de la API.

Los valores `http://localhost:8000/api` que permanecen como fallback en
`lib/nexova-api.ts` y `lib/incident-analysis-api.ts` son para ejecuciÃ³n local
fuera de Docker. Si faltan las variables pÃºblicas en un contenedor, ese
fallback no funcionarÃ¡ correctamente desde el navegador; por eso las variables
de Compose deben mantenerse configuradas como `/api`.

### VerificaciÃ³n documentada

La revisiÃ³n final comprobÃ³ `docker-compose.yml`, ambos Dockerfiles,
`uis/start.sh`, `uis/proxy-server.js`, los clientes de API y las variables
`NEXT_PUBLIC_*`. El usuario confirmÃ³ el funcionamiento de los tres puertos y
que las pruebas locales anteriores pasaron. No se modificaron archivos durante
esa revisiÃ³n ni se ejecutÃ³ un despliegue remoto.

El aprendizaje tÃ©cnico y las instrucciones para futuros desarrollos estÃ¡n
recogidos en `docs/aprendiendo-containerization-docker.md`.

## DiseÃ±o del pipeline de business reporting completado

Se completÃ³ el diseÃ±o documental en `data/pipelines/PIPELINE_DESIGN.md`, sin
implementar orquestaciÃ³n, migraciones, servicios HTTP ni cambios en telemetrÃ­a.
El diseÃ±o define una consolidaciÃ³n ISO semanal UTC por oficina/programa en
`reporting.weekly_office_program_performance`, el registro reutilizable
`reporting.pipeline_runs`, idempotencia por evento y resultado, recuperaciÃ³n,
el mapeo futuro a Prefect y los endpoints previstos bajo `/api/reporting`.

Antes de implementar el hito siguen pendientes: crear los modelos/dimensiones
de programa, coste, moneda, kit y umbral; emitir datos de negocio completos y
versionables; aprobar la hora de ejecuciÃ³n semanal; e instalar/configurar
Prefect, el mÃ³dulo `services/reporting/`, las migraciones y los permisos de
PostgreSQL.

## Business reporting: Fase previa a la Fase 2 â€” Programmes en Inventory

Se creÃ³ `feature/business-reporting-pipeline-implementation` desde el Ãºltimo
`origin/main` (`2448038`), preservando la rama de diseÃ±o. El diagnÃ³stico y plan
por fases estÃ¡n en `docs/aprendiendo/aprendiendo-pipeline-negocio.md`. La lectura
real de PostgreSQL confirmÃ³ 10 inbound, 1 outbound, 1 alerta y ninguna variaciÃ³n
de kits; ninguno de los 12 eventos tiene `programme_id` y ningÃºn inbound tiene
`unit_cost`. El esquema `reporting` todavÃ­a no existe y Prefect no estÃ¡ instalado
en el intÃ©rprete comprobado. No se ha implementado el ETL, modificado el informe
tÃ©cnico ni ejecutado migraciones. La Fase 2 requiere definir los datos reales
de programas, kits, costes, umbrales y garantÃ­a de entrega de eventos antes de
desarrollar los emisores y modelos necesarios.

El usuario aprobÃ³ implementar la fase previa: Programmes en Inventory y
asociaciÃ³n de cada movimiento nuevo a un programa, sin ligarlo al producto.
Quedaron confirmados el conteo de un outbound vÃ¡lido por entrega, la moneda
exclusiva por oficina (Valencia/EUR y Miami/USD), la integraciÃ³n HTTP futura en
`services/api/app/reporting/`, Prefect 3 self-hosted, la CLI original y el
horario semanal del lunes a las 00:15 UTC. El trabajo implementado y su
validaciÃ³n local estÃ¡n documentados en
`docs/aprendiendo/aprendiendo-pipeline-negocio.md`.

Se aprobaron los IDs de prueba `prog-digital-skills-001`,
`prog-technical-onboarding-001` y `prog-professional-development-001`.
Los movimientos anteriores conservarÃ¡n `programme_id = NULL` y se mostrarÃ¡n
como "Sin programa asignado (histÃ³rico)"; los nuevos requerirÃ¡n un programa
existente. El reporting por programa no atribuirÃ¡ esos histÃ³ricos a ninguno.
La fase previa estÃ¡ lista para revisiÃ³n del usuario. No se ha implementado el
outbox ni se han definido reglas de alertas o variaciones de costes; la Fase 2
original permanece detenida y fuera de este alcance.

VerificaciÃ³n final local: `test_inventory*.py` **48 OK, 1 skip** (concurrencia
PostgreSQL opcional); frontend **87 tests OK** en la Ãºltima ejecuciÃ³n,
`npx tsc --noEmit`, ESLint focalizado y `npm run build` OK. La suite frontend
registra warnings de telemetrÃ­a por su URL relativa en Node; el lint global
reporta errores preexistentes fuera de los archivos modificados. Se corrigiÃ³
la comparaciÃ³n de URL SQLite del test de infraestructura para que sea
independiente de la serializaciÃ³n de Windows. `git diff --check` OK. MigraciÃ³n
comprobada solo sobre SQLite efÃ­mero con esquema legado; no se tocÃ³ ninguna
base real. Sin commits ni push.
