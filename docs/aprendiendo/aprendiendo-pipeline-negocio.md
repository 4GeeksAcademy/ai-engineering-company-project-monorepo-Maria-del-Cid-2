# Aprendiendo: pipeline de reporting de negocio en Nexova

Esta guía registra el diagnóstico del pipeline y el estado de implementación.
Las fases previas de Inventory, outbox y fixtures de demo están descritas en
`memory-bank/progress.md`. El pipeline de reporting y sus endpoints están
implementados; la Fase 6 de validación queda **parcialmente verificada** según
la matriz de evidencias de la sección 7. Las pruebas locales no equivalen a
una corrida Prefect real ni a validación E2E con eventos completos.

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

El plan siguiente refleja el diagnóstico inicial y no el estado actual de
implementación. Las fases 4–6 se implementaron posteriormente; la validación
Fase 6 se resume con evidencias y brechas en la sección 7.

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

## 5. Validaciones realizadas durante el diagnóstico inicial (histórico)

Se comprobó Git (`status`, comparación de ramas y `fetch`), presencia de
Prefect mediante importación y acceso PostgreSQL en transacciones `READ ONLY`
(esquema, tablas, privilegio de lectura y conteos por tipo). No se ejecutaron
tests de código ni el pipeline, que todavía no existe. Las consultas de base
de datos no son una prueba integral del flujo de usuario.

## 7. Fase 6 — validación integral: evidencias y límites

Validación inicial ejecutada el 2026-11-10 desde la raíz del monorepo:

```text
uv run --project services/api python -m pytest \
  services/api/tests/test_reporting_api.py \
  services/api/tests/test_weekly_reporting_pipeline.py \
  services/api/tests/test_telemetry_router.py \
  services/api/tests/test_telemetry_repository.py \
  services/api/tests/test_telemetry_report.py -q
53 passed, 1 warning, 4 subtests passed
```

La warning es deprecación de Starlette/httpx en `TestClient`; no hizo fallar
las pruebas. `git diff --check` pasó. Se añadió una prueba HTTP de
`GET /api/telemetry/report` que sustituye el generador de reporte y verifica
status, filtros y respuesta; no consulta una base de telemetría real. El
SHA-1 del archivo `services/api/app/telemetry/analysis.py` coincide con
`HEAD` (`d56c0984552ba1168757996193c136dddf5a9ef0`), por lo que dicho módulo
no tiene cambios frente a la revisión base.

| Criterio | Evidencia ejecutada | Estado |
|---|---|---|
| Extracción y límites ISO semana UTC `[lunes, lunes siguiente)` | Test de límites y revisión del query parametrizado; no se ejecutó extracción SQL contra fixtures. | Parcial: unit test/inspección, sin prueba DB. |
| KPI de coste, salidas, shortage y variancia; agregación por oficina/programa/semana | Test sintético de transformación comprueba coste decimal, conteos, deduplicación exacta y una fila agregada; código y contrato contrastados. | PASS en transformación unitaria. No certifica datos reales. |
| Eventos inválidos, duplicados y números no finitos | Tests cubren rechazo, duplicate exacto y conflicto de `event_id`; valores no finitos y entradas incompletas. | PASS en transformación unitaria. |
| Moneda Valencia/EUR y Miami/USD | Código valida moneda canónica; test de carga usa EUR/USD para filas de ejemplo. No hay test explícito de transformación para ambas monedas ni persistencia real. | Parcial. |
| Idempotencia/upsert y transacción | Test mock verifica dos upserts, resultado insert/update y un commit; no ejecuta PostgreSQL ni una segunda corrida real. | Parcial. |
| Retry solo ante transitorios | Test parametrizado verifica conectividad/transitorios y no retry para validación/lógica SQL; no inyecta fallos en un DB real. | PASS policy unitaria. |
| Fallo de task opcional no invalida ETL | Test de flow con task snapshot simulada fallida verifica run `completed` y error saneado. | PASS en flow unitario. |
| Runs exitoso y fallido | Tests verifican flow fallido crítico y flow exitoso con snapshot opcional fallido mediante mocks; no crean/actualizan filas en PostgreSQL. | PASS en flow unitario, no E2E. |
| Caché | Test verifica clave determinista por entradas, cambio de contenido y TTL de una hora; no espera expiración en runtime ni ejercita backend de resultados Prefect. | Parcial/unitario. |
| CLI | En la validación inicial solo se inspeccionó parser/llamada al flow. En la actualización del 2026-11-11, `python data/pipelines/pipeline.py --help` mostró `--week-start` y `--trigger-type`; no se invocó el flow. | PASS del parser/help; pipeline no ejecutado. |
| Endpoints `/api/reporting` | Tests HTTP existentes cubren auth, roles, validación lunes, respuesta, filtros y errores saneados para las tres rutas. La última suite focalizada pasó. | PASS con dependencias/repositorios mock; sin DB ni Prefect reales. |
| Compatibilidad `GET /api/telemetry/report` | Nueva prueba HTTP mockeada pasa; las pruebas de métricas Pandas pasan. `analysis.py` idéntico a HEAD. | PASS de contrato local; no consulta base real. |
| Separación de destinos | Revisión estática: extracción hace SELECT a `public.telemetry_events`; todos los INSERT/UPDATE de pipeline apuntan a `reporting.*`. Ninguna prueba de escritura contra DB temporal ejecutada. | Confirmado por código, no por E2E. |
| Migración/contrato físico | Migración, schemas Pydantic, repositorio y diseño coinciden en tabla/columnas/claves/campos revisados. No se aplicó la migración en una DB desechable en esta fase. | Revisión estática; DB no validada. |

No se ejecutó `python data/pipelines/pipeline.py`, no se solicitó un run a
Prefect, no se esperó al cron natural y no se escribió en ninguna base durante
esta fase. `docker compose ps` no mostró servicios activos en esta sesión; no
se inició Compose. La consulta previa de telemetría de la semana
2026-11-02 —documentada en `memory-bank/progress.md`— fue read-only y confirmó
que no hay programa en los eventos; por eso no es una muestra apropiada para
una corrida útil. El código y los tests no prueban que los nuevos eventos ya
hayan llegado a telemetría.

**Conclusión en ese momento:** la Fase 6 tenía validación unitaria y de
contrato sustancial, pero faltaba la prueba de base de datos desechable. La
actualización siguiente cubre el flujo PostgreSQL con fixtures sintéticos; no
convierte en E2E validada la experiencia del dashboard autenticado ni una
corrida del deployment de Prefect.

### Actualización de validación (2026-11-11)

Se amplió la verificación sin lanzar el pipeline ni alterar las bases:

| Área | Comando/evidencia | Resultado y alcance |
|---|---|---|
| Backend reporting/telemetría | `uv run --project services/api python -m pytest services/api/tests/test_weekly_reporting_transform.py services/api/tests/test_weekly_reporting_pipeline.py services/api/tests/test_reporting_api.py services/api/tests/test_telemetry_router.py services/api/tests/test_telemetry_repository.py services/api/tests/test_telemetry_report.py -q` | 58 passed, 1 warning y 4 subtests en 36.82 s. La warning es Starlette/httpx; apareció ruido de logging Prefect al cerrar el servidor temporal después del resumen exitoso. Son tests unitarios/HTTP con dependencias mock, no una prueba PostgreSQL E2E. |
| Frontend | `npm test` en `uis/backoffice/talent-pipeline-tracker` | 89 passed, 0 failed. Node emite warnings `MODULE_TYPELESS_PACKAGE_JSON`; la primera ejecución había incluido por error `--runInBand` (opción de Jest), y se repitió después con el script canónico limpio. |
| Tipos, lint y build | `npx tsc --noEmit`; `npx eslint app/reports/business-analysis/page.tsx lib/business-reporting.ts types/business-reporting.ts`; `npm run build` | Los tres comandos terminaron con código 0. Next.js advierte que infirió la raíz en el lockfile del monorepo y detectó otro lockfile; la compilación de producción terminó correctamente. |
| CLI | `uv run --project services/api python data/pipelines/pipeline.py --help` | PASS: muestra `--week-start` y `--trigger-type {scheduled,manual}`. Solo ayuda/parser; no ejecuta el flow ni conecta con las fuentes/destinos. Un primer intento con `PREFECT_LOGGING_TO_API=false` falló al validar esa configuración inválida de Prefect; se repitió correctamente sin ella. |
| Servicios locales | `docker compose ps`; `curl` al health de Prefect y al dashboard | Backend, interfaces, reporting-db (healthy), Prefect server y worker aparecieron running; health de Prefect HTTP 200 y la ruta `/reports/business-analysis` responde HTTP 200. La navegación del navegador redirigió a `/login` al no haber sesión compartida, por lo que no se inspeccionaron datos renderizados con un usuario autenticado. |
| Protección API | `GET http://localhost:8000/api/reporting/weekly-office-program-performance` sin token | HTTP 401 `Not authenticated`, `WWW-Authenticate: Bearer`; confirma el guard de autenticación en el servicio local, no el resultado autenticado ni los registros de reporting. |
| Deployment Prefect | Lectura de `POST /api/deployments/filter` y `POST /api/flow_runs/filter` (filtros vacíos/por ID) | Deployment `weekly-office-program-performance` encontrado, `READY`, no pausado, pool `reporting-process-pool`; schedule activo `15 0 * * 1`, UTC. El historial devuelto contiene solo 3 runs `SCHEDULED` para 2026-11-16, 2026-11-23 y 2026-11-30; no hay evidencia en esta consulta de una ejecución completada/real. |
| Datos/tablas | No se ejecutaron queries de negocio ni se inspeccionaron tablas del reporting DB en esta actualización. | La salud del contenedor no valida migración aplicada, contenido, permisos de escritura, upsert ni separación efectiva entre bases. |

La matriz anterior debe interpretarse junto con la prueba desechable del
2026-11-11 que sigue. Los tests del backend y frontend, el build y los checks
estáticos pasan; los servicios locales y el deployment respondieron en la
verificación previa. La ejecución de Prefect con bases independientes
confirma migración de reporting, extracción, transformación, frontera semanal
y upsert. La experiencia del dashboard con un usuario autenticado todavía no
se pudo validar en navegador: la URL local fue reescrita por el Dev Tunnel y
redirigida a autenticación de GitHub. No se introdujeron credenciales. La
Fase 6, por tanto, queda **parcialmente verificada**, no E2E cerrada.

### E2E con PostgreSQL desechable (2026-11-11)

Se levantaron dos PostgreSQL 16 independientes en una red Docker de prueba
dedicada, con almacenamiento temporal (tmpfs) y puertos enlazados solo a
loopback: `telemetry_e2e` (fuente) y `reporting_e2e` (destino). No se usó ni
reinició el stack Compose existente, no se consultaron `.env` y no se apuntó a
una base operativa. Se aplicaron las migraciones correspondientes y se
insertaron ocho eventos sintéticos; siete pertenecían a la semana UTC
2026-10-26 y el octavo estaba exactamente en el límite exclusivo
2026-11-02 00:00 UTC.

**Hallazgo de migraciones:** la migración `001_create_telemetry_events.sql`
crea ya la restricción única de `event_id` y el índice GIN con el nombre
`idx_telemetry_events_tags_gin`. Al correr después
`002_align_existing_telemetry_events.sql` sobre esa base recién creada,
`ADD CONSTRAINT telemetry_events_event_id_key UNIQUE (event_id)` y el intento
de renombrar `idx_telemetry_events_tags` chocan con ese esquema. El runner
captura errores por sentencia y aun así imprime que las migraciones acabaron;
por tanto, **no se considera que la migración 002 haya pasado limpiamente**.
Debe revisarse la idempotencia/condiciones de migración y hacer que el runner
falle de forma fiable cuando una migración deja una transacción abortada. Esto
no impidió la prueba del pipeline sobre el esquema de reporting aplicado, pero
sí limita la evidencia de migración de telemetría a que la tabla utilizable
existía tras 001.

| Ejecución sintética | Resultado observado |
|---|---|
| Primera corrida del flow para `2026-10-26` | `completed`; 7 eventos procesados, 2 claves insertadas, 0 actualizadas, 0 rechazadas. El evento en el límite del lunes siguiente quedó fuera. |
| Valencia / `E2E-PROGRAM-01` | Coste inicial `37.50 EUR`; 2 kits entregados, 1 evento de shortage y 1 variancia de coste. |
| Miami / `E2E-PROGRAM-02` | Coste `14.50 USD`; 1 kit entregado, 0 shortages y 0 variancias. Confirma agregación separada y moneda esperada. |
| Segunda corrida sin cambios | `completed`; 7 procesados, 0 insertados, 2 actualizados, 0 rechazados; permanecieron exactamente dos filas para las claves de prueba. |
| Tercera corrida tras cambiar cantidad inbound de Valencia de 3 a 5 | `completed`; volvió a extraer y recomputar el contenido: coste Valencia `62.50 EUR`; upsert actualizó las dos claves sin duplicarlas. |
| Aislamiento de esquemas | La fuente tenía `public.telemetry_events` y no el esquema `reporting`; el destino tenía las tablas `reporting` y no `public.telemetry_events`. |

La validación de usuario autenticado quedó bloqueada por el redireccionamiento
del puerto local hacia la pantalla de acceso de GitHub del Dev Tunnel. Se
inspeccionó que auth usa TinyDB configurable mediante `AUTH_DB_PATH`, que el
secreto JWT procede de `SECRET_KEY` y que el frontend permite
`NEXT_PUBLIC_NEXOVA_API_BASE`; sin embargo, no se inició otra API/UI ni se
creó una cuenta para esta prueba. Así se evitó depender de la base de usuarios
existente o solicitar credenciales. La API ya tiene evidencia automatizada de
endpoints protegidos y de respuesta con repositorios sustituidos, pero no se
afirma que se haya visto el dashboard con sesión autenticada ni que haya
consultado las filas sintéticas.

**Limpieza:** tras verificar por nombre e imagen que eran los dos contenedores
`postgres:16-alpine` de la prueba, se eliminaron
`nexova-e2e-telemetry-db` y `nexova-e2e-reporting-db`, la red
`nexova-reporting-e2e-net` y el directorio de snapshot temporal
`%LOCALAPPDATA%\Temp\nexova-reporting-e2e-snapshot`. Las comprobaciones
posteriores confirmaron que esos nombres/ruta ya no existen. No se ejecutó
`docker compose down`, `docker system prune` ni se tocaron volúmenes o
contenedores del proyecto.

**Conclusión actual:** hay evidencia de ejecución real del flow contra dos
PostgreSQL desechables separados, incluyendo límites UTC, KPI EUR/USD,
extracción fresca y upsert repetido/actualizado. Siguen pendientes la
corrección y una validación limpia de la pareja de migraciones de telemetría,
una prueba autenticada del dashboard accesible fuera del gate del túnel y una
corrida completada del deployment programado de Prefect. No se deben usar
destinos operativos para cerrar esas brechas.

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
## Fase 5 � estado de CLI y API reporting

Implementado en el c�digo: `data/pipelines/pipeline.py` expone `main(argv=None)`
y puede ejecutarse desde la ra�z con `uv run --project services/api python
data/pipelines/pipeline.py [--week-start YYYY-MM-DD]
[--trigger-type manual|scheduled]`. La semana debe comenzar en lunes ISO; sin
fecha se calcula la �ltima semana cerrada. La cadencia aprobada sigue siendo
lunes a las 00:15 UTC. Se despleg� un Prefect Server local en Compose con pool
`reporting-process-pool` y deployment
`weekly_office_program_performance/weekly-office-program-performance`; la API
de Prefect confirma el cron activo `15 0 * * 1` en `UTC`. PostgreSQL de
reporting es una instancia local dedicada y contiene las tablas del esquema
`reporting`.

La API protegida expone `GET /api/reporting/pipeline-runs/latest`,
`POST /api/reporting/pipeline-runs` (solo admin, respuesta 202; delega a un
Prefect deployment) y `GET /api/reporting/weekly-office-program-performance`.
La configuraci�n del deployment se puede sobrescribir con
`REPORTING_PREFECT_DEPLOYMENT`; la persistencia utiliza
`REPORTING_DATABASE_URL`. El backend se reconstruy� con Prefect y se corrigi�
el slug por defecto del flow en el adaptador de disparo.

La conectividad de solo lectura desde el worker a `public.telemetry_events` se
comprob� para la semana UTC 2026-11-02. Hab�a 14 eventos elegibles: 12
`inbound_order_created`, 1 `outbound_order_created` y 1
`stock_threshold_triggered`. Los 14 carec�an de `programme_id`, y solo 6
conten�an `office`; la transformaci�n real en memoria confirm� 14 eventos
rechazados y cero filas agregadas. Por ello no se solicit� un flow run manual
ni se escribi� en reporting: correrlo con esa fuente no generar�a KPI �tiles.
No se modific� ni seed� la telemetr�a. Para completar la prueba end-to-end
hay que producir eventos de negocio con las dimensiones requeridas y repetir
la validaci�n sobre una semana adecuada.

La configuraci�n del schedule est� verificada, pero todav�a no se observ� una
ejecuci�n natural. La siguiente ocurrencia cron esperada es lunes 2026-11-16 a
las 00:15 UTC; una corrida manual no cuenta como verificaci�n del cron. El
backoffice ya tiene Reports/System Analytics; se recomienda considerar una
vista admin de seguimiento del pipeline en esa secci�n, usando los endpoints
protegidos existentes, pero no se modific� la interfaz.

## Fase 5 — Refactorización del pipeline y dashboard Business Analysis

### Por qué se dividió el pipeline

El proceso de reporting reúne trabajos distintos: leer eventos de telemetría,
validar y resumir esos eventos, y guardar los resultados semanales. Se separó
en partes pequeñas para que cada etapa tenga una responsabilidad clara. Así es
más fácil entender dónde ocurre un problema, probar las reglas del informe y
reutilizar cada etapa sin mezclar la lectura de datos con el cálculo o el
guardado.

En Prefect, un **flow** es un proceso que organiza pasos de trabajo. Un
**subflow** es un flow más pequeño que se ejecuta como parte de otro flow. Una
comparación sencilla: el flow principal es el itinerario de un viaje y los
subflows son tramos organizados —por ejemplo, salida, recorrido y llegada—.
Prefect puede registrar esos tramos por separado y mostrar cuál se ejecutó o
dónde se produjo un fallo. En esta implementación, los subflows de extracción,
transformación y carga organizan las etapas; las operaciones concretas se
realizan mediante tareas de Prefect.

### Etapas del cálculo

1. **Extracción:** se leen de `public.telemetry_events` los eventos de negocio
   de la semana solicitada. La semana se interpreta en UTC, desde el lunes a
   las 00:00 incluido hasta el lunes siguiente excluido. Esta lectura se hace
   de nuevo en cada ejecución para que también puedan encontrarse eventos que
   llegaron tarde.
2. **Transformación:** se comprueba que cada evento tenga datos utilizables y
   dimensiones coherentes, y se agrupa por semana, oficina y programa. Se
   rechazan los eventos incompletos o inconsistentes y se evita contar dos
   veces un mismo `event_id`. La oficina también determina la moneda: Valencia
   usa EUR y Miami USD; no se convierten ni mezclan monedas.
3. **Carga:** se guardan los KPI en las tablas de reporting. Si ya existe un
   resultado para la misma semana, oficina y programa, se actualiza en vez de
   crear una copia. El guardado de los resultados de una ejecución se realiza
   en una transacción: si falla una escritura, no se deja una parte de esa
   carga guardada.

La transformación puede reutilizar durante una hora un cálculo para la misma
semana y exactamente los mismos eventos. Si cambia el contenido de los
eventos, la clave del cálculo cambia. La extracción, en cambio, no se almacena
en caché. Los errores temporales de conexión pueden reintentarse; los errores
de datos o de lógica no se tratan como fallos temporales.

### Pruebas y ejecución desde la línea de comandos

Las pruebas de transformación construyen eventos de ejemplo en memoria, como
si fueran movimientos de inventario, y comparan el resultado calculado con el
resultado esperado. Por ejemplo, comprueban que el coste de una entrada sea
cantidad por coste unitario, que las oficinas mantengan sus monedas separadas,
que el KPI de salidas cuente eventos y no unidades, y que los eventos inválidos
o duplicados no inflen los resultados. Son importantes porque permiten
comprobar las reglas con ejemplos controlados sin modificar la telemetría ni
la base de reporting. Estas pruebas no equivalen a ejecutar el flujo completo
contra bases de datos reales.

El pipeline conserva su punto de entrada por línea de comandos desde la raíz
del proyecto:

```text
uv run --project services/api python data/pipelines/pipeline.py --week-start YYYY-MM-DD
```

La fecha debe ser el lunes de la semana ISO que se quiere procesar. También se
puede omitir `--week-start`; en ese caso se usa la última semana cerrada. La
opción `--trigger-type manual|scheduled` permite indicar el tipo de ejecución.
El comando sigue disponible, pero la validación documentada hasta ahora no
incluye ejecutarlo contra bases temporales desechables. Las pruebas unitarias
del pipeline y de transformación sí están documentadas en la sección 7.

### Dashboard Business Analysis y significado de los KPI

El backoffice incorpora **Reports → Business Analysis**. El dashboard no
calcula los KPI en el navegador ni lee directamente los eventos de
telemetría: solicita a la API las filas semanales que el pipeline ya guardó
en `reporting.weekly_office_program_performance`. Por eso, una entrada recién
creada no aparece necesariamente de inmediato: el evento debe llegar primero
a telemetría y luego debe ejecutarse el reporting para la semana que lo
contiene.

Cada tarjeta representa una combinación de semana, oficina y programa. Muestra
los siguientes indicadores:

- **Total material cost:** coste total de las entradas válidas de esa
  combinación. Se calcula sumando cantidad multiplicada por coste unitario y
  se presenta en la moneda de la oficina.
- **Kits delivered:** cantidad de eventos outbound válidos. Según la regla
  aprobada, cada evento cuenta como una entrega, sin sumar su cantidad. El
  evento outbound no demuestra por sí solo que la salida haya sido realmente
  un kit; puede representar una asignación o un consumo genérico.
- **Shortage events:** cantidad de eventos válidos que registran un cruce del
  umbral de stock.
- **Cost variance events:** cantidad de eventos válidos que registran una
  variación de coste de kit.

El selector del dashboard filtra por **semana ISO**, no por día: se elige el
lunes que inicia la semana. Si no se aplica un filtro, se solicitan los
resultados semanales disponibles más recientes. Los resultados de Valencia y
Miami se muestran por separado, con EUR y USD respectivamente; no se presenta
un total combinado entre monedas.

Los interesados pueden abrir el dashboard desde el menú Reports del backoffice
con una sesión autorizada y escoger la semana que quieren consultar. Si no hay
filas, la pantalla informa que no hay resultados disponibles. Esto puede
significar que todavía no se ha ejecutado el pipeline para esa semana o que
sus eventos no aportaron datos válidos para crear una fila; no significa que
el dashboard haya calculado KPI a partir de movimientos incompletos. El
dashboard permite entender y comparar los resultados por semana, oficina y
programa, pero no reemplaza la revisión del origen de los datos ni el informe
técnico de telemetría.

### Problemas encontrados, soluciones y límites pendientes

- En la primera revisión de los eventos existentes se encontró que faltaban
  dimensiones requeridas, como `programme_id`, y que muchas entradas
  históricas no tenían coste unitario. La transformación real en memoria
  confirmó que aquellos 14 eventos de la semana revisada se rechazaban y no
  producían filas. Se mantuvo la regla de no inventar dimensiones ni costes y
  no se inició una corrida de reporting que no pudiera generar KPI útiles.
- Durante una comprobación posterior del pipeline, la API no pudo cargar
  Business Analysis porque una variable `REPORTING_DATABASE_URL` vacía,
  heredada por la sesión de PowerShell, sobrescribía la URL completa del
  archivo `.env`. Se limpió esa variable vacía de la sesión y se recrearon los
  servicios necesarios. Después se comprobó desde el backend una consulta a
  la tabla de reporting. La tabla tenía cero filas en ese momento: la conexión
  ya funcionaba, pero aún no había resultados guardados.
- Al crear un inbound en el backoffice apareció un error 500 porque faltaban
  tablas de valoración en la base SQLite local de inventario. Se ejecutó la
  migración aditiva existente, protegida para el entorno de desarrollo. La
  comprobación posterior encontró las tablas requeridas y conservó los datos
  existentes; no se añadieron movimientos ni datos de demostración como parte
  de esa migración.

La refactorización conserva el CLI y los tests unitarios de transformación,
pero todavía no se ha documentado una corrida end-to-end del CLI/flow contra
bases desechables ni una ejecución natural del horario Prefect. La validación
de extremo a extremo sigue parcial, tal como se detalla en la sección 7. En
particular, la existencia de una fila en el dashboard depende de que haya
eventos nuevos con dimensiones y costes válidos, que se entreguen a telemetría
y que el pipeline procese su semana. El calendario semanal aprobado es los
lunes a las 00:15 UTC; no se debe confundir ese horario con una prueba ya
observada. También sigue pendiente decidir cómo corregir eventos históricos o
de negocio con un identificador distinto, y el KPI de outbound conserva la
limitación descrita: no puede confirmar por sí solo que cada salida sea un
kit.

### Resumen: qué trabajo de las fases anteriores queda documentado aquí

Sí: la guía recoge el trabajo funcional y técnico realizado antes de esta fase
de documentación. Para encontrarlo, las partes están distribuidas entre las
secciones anteriores y la sección **Fase 5 — Refactorización del pipeline y
dashboard Business Analysis**; no todo estaba reunido bajo una sola lista.
Este resumen deja explícito ese alcance:

- **Datos de negocio e inventario:** el catálogo de programas y su asociación
  con movimientos, la conservación de movimientos históricos sin programa,
  la valoración de inventario y los eventos que se generan desde movimientos
  se describen en las secciones de Inventory y fiabilidad de eventos. Se
  explican también el outbox transaccional, el worker, los reintentos y la
  entrega idempotente a telemetría.
- **Pipeline de reporting:** aquí se explican los subflows de extracción,
  transformación y carga; la agregación semanal por oficina y programa; las
  reglas y límites de los cuatro KPI; la caché de transformación, el upsert y
  el horario Prefect.
- **Pruebas unitarias:** la sección 7 registra el comando ejecutado y sus
  resultados, y la matriz indica qué se probó para transformación, deduplicación,
  validación, ventanas UTC, carga, retries, caché y flows. Incluye qué pruebas
  usan mocks o datos sintéticos y qué aspectos no han sido probados contra una
  base real. La sección sobre CLI indica que el comando está implementado, pero
  que no se ejecutó contra bases temporales en la validación documentada.
- **CLI y API:** se documentan cómo indicar la semana al CLI, el lunes ISO
  obligatorio, la selección automática de la última semana cerrada y los
  endpoints protegidos para consultar resultados, revisar ejecuciones y
  solicitar una ejecución Prefect.
- **Dashboard del backoffice:** se explica el acceso a **Reports → Business
  Analysis**, cómo consulta resultados persistidos mediante la API, los estados
  sin resultados, el filtro por semana (lunes) y la lectura de los KPI por
  oficina, programa y moneda. El dashboard está implementado; la aparición de
  datos depende de que existan eventos válidos y se haya ejecutado reporting.

Esto cubre lo desarrollado y la evidencia disponible, pero no significa que
cada parte haya pasado una prueba integral en producción: la guía distingue
las pruebas unitarias y de contrato de una corrida E2E real. En particular,
quedan pendientes la corrida del CLI/flow contra bases temporales de reporting,
la validación con eventos completos de negocio y la observación de una
ocurrencia natural del schedule, como se indica en la sección 7.