# Auditoría y diseño: procesamiento asíncrono con Celery

> **Documento histórico de Etapa 1:** las descripciones en presente del análisis
> original reflejan el sistema anterior a Celery. Para el estado implementado,
> ver «Estado vigente — Etapa 2» a continuación.

**Etapa:** 1 — auditoría y diseño (sin implementación funcional)  
**Fecha:** 2026-11-18  
**Rama comprobada:** `feature/celery-async-tasks`

## Validación final y documentación — Etapa 4 (2026-11-18)

Esta sección añade la evidencia de validación final. Las observaciones de Etapa
1 y Etapa 2 se mantienen como registro histórico y no se reescriben para que
parezcan mediciones hechas en esta etapa.

### Pruebas y comprobaciones

- **Backend completo:** `uv run pytest -q` desde `services/api` — 216 passed,
  1 skipped, 40 subtests passed, 7 warnings.
- **Focalizadas de Celery:** 11 passed, 7 warnings, incluyendo fiabilidad de
  retries/DLQ y la integración local de cola/worker registrada en la validación.
- **Backoffice:** `npm test` desde
  `uis/backoffice/talent-pipeline-tracker` — 89 passed, 18 suites, 0 failed,
  0 skipped.
- **TypeScript:** `npx tsc --noEmit` en el backoffice — sin errores reportados.
- **Compose:** `docker compose config --quiet` — configuración válida.
- **Higiene de diff:** `git diff --check` — sin errores después de los cambios
  de documentación.
- **Compose operativo:** servicios principales comprobados healthy durante la
  validación controlada. Flower confirmó health de su endpoint, pero no se
  obtuvo verificación del estado de la tarea por Flower; una consulta a la API
  devolvió 401. No se atribuye a Flower confirmación task-level.

### Regresión ampliada de componentes

Se ejecutó además un grupo de suites para auth, Incident Analysis/Celery,
Incident Manager, inventario y su outbox, suppliers y telemetría, con rutas
TinyDB y SQLite temporales. Resultado: **433 passed, 1 failed, 1 skipped, 67
subtests passed, 7 warnings**. El único fallo fue
`test_auth_password_reset.PasswordResetApiTests.test_concurrent_consumption_allows_only_one_reset`:
dos hilos leyeron/escribieron la misma TinyDB JSON simultáneamente y uno
observó un archivo vacío (`JSONDecodeError`). Es un fallo observado en la
regresión actual, no se modificó ni se ocultó. No se estableció con certeza si
es preexistente respecto a esta rama; por tanto, queda **sin clasificar como
preexistente o introducido**. Las suites de componentes presentes en esa misma
ejecución sí pasaron, excepto el caso concurrente señalado. Los skips incluyen
escenarios condicionados a configuración de almacenamiento/servicios externos.

### Prueba controlada de worker y DLQ

Un primer trabajo sintético Compose terminó tras un intento; su causa no quedó
determinada, así que no se usa como evidencia del retry. Después de reiniciar
solo el worker para recargar los módulos montados, una segunda entrada sintética
mostró intentos 1, 2 y 3, estado API `failure`, y una fila DLQ con
`attempt_count=3` y `error_type=FileNotFoundError`. El CSV artificial se eliminó
y el consumidor del worker se restauró sin tareas activas/pendientes al cerrar
la prueba. Estos casos no modificaron la lógica funcional.

### Build y límites

El build del backoffice compiló páginas/rutas, pero Next.js terminó con
`SecurityFatalError` asociado a una vulnerabilidad conocida de la versión
instalada. El propio mensaje sugirió actualizar Next.js; no se ejecutó una
actualización de dependencias sin autorización. Esto es un bloqueo de seguridad
del entorno/dependencia, no un error demostrado de TypeScript. La suite de tests
y `tsc --noEmit` pasaron por separado.

La DLQ y telemetría siguen apuntando a la misma base Supabase/esquema `public`,
con separación a nivel de tabla solamente. No se utilizaron esas credenciales
para el test concurrente fallido. La integración DLQ que usa `CELERY_DATABASE_URL`
requiere un destino de prueba aislado y no debe ejecutarse contra producción.

### Documentación de operación

El runbook de arranque/parada, consulta de tareas, ejecución local en Windows y
Compose, variables y pruebas está en `services/api/README.md`, sección
«Operación de Celery». La guía didáctica está en
`docs/aprendiendo/aprendiendo-colas-mensajeros-tareas-asincronas.md`. Ambas
señalan expresamente que `inventory-outbox-worker` es independiente de Celery.

## Estado vigente — Etapa 2 (2026-11-18)

Esta sección es la referencia actual; el resto del documento conserva el
registro histórico de la auditoría de Etapa 1 y sus propuestas, que fueron
implementadas o reemplazadas por el estado descrito aquí.

- Incident Analysis usa Celery con Redis: el POST devuelve `202` y un ID de
  tarea; el estado y la exportación se consultan por ese ID. API y worker
  comparten el volumen `incident_analysis_uploads`; el mensaje Celery contiene
  únicamente una referencia opaca al CSV.
- Se reintentan solo fallos transitorios reconocidos, como máximo 2 veces (3
  intentos totales), con backoff de 1 y 2 segundos. El archivo se elimina tras
  éxito o fallo terminal y existe limpieza de temporales antiguos.
- La DLQ persiste en `public.celery_incident_analysis_dlq`, mediante
  `CELERY_DATABASE_URL` y TLS requerido. La migración 003 está registrada; la
  tabla contiene solo metadatos saneados y usa `task_id` como clave idempotente.
- La identidad efectiva comprobada para `CELERY_DATABASE_URL` y
  `TELEMETRY_DATABASE_URL` fue la misma base PostgreSQL de Supabase y el esquema
  `public`. La DLQ y `public.telemetry_events` son tablas distintas: separación
  lógica a nivel de relación, **no** separación por base, esquema o rol. La
  identidad de reporting se comprobó en la base local `nexova_reporting`; las
  tablas de reporting están en el esquema `reporting` y la tabla DLQ no existe
  allí. No se crearon bases/proyectos ni se alteraron tablas de telemetría o
  reporting. La DLQ y telemetría comparten propietario/rol y privilegios amplios;
  no se debe describir esta configuración como aislamiento de permisos.
- En la inspección de Compose el worker de Incident Analysis estaba definido,
  pero no estaba ejecutándose. Por ello el código, la configuración, la
  persistencia y las pruebas están validados; no se afirma que haya despliegue
  operacional activo.
- Validación registrada: 16 pruebas enfocadas de backend y 89 del backoffice
  pasan. La suite backend completa reportó 291 tests y 27 subtests pasados, y un
  fallo ajeno a esta etapa en el CLI de Windows por codificación `cp1252`.

## Alcance y hallazgos

La API FastAPI se registra en `services/api/app/main.py`. El análisis de esta etapa se limitó a operaciones que podrían beneficiarse de ejecución en segundo plano; no se modificaron rutas, lógica de negocio ni infraestructura.

Persistencia relevante para evaluar la solución:

- Incident Analysis no tiene persistencia propia: procesa un CSV recibido en la petición, y conserva únicamente el último agregado en `_latest_result`, una variable en memoria del proceso.
- El gestor de incidencias y Auth usan TinyDB, en archivos separados. La documentación advierte que ciertas operaciones y locks no coordinan múltiples procesos.
- Inventario usa SQLModel y `DATABASE_URL`; telemetría y reporting tienen sus propias conexiones PostgreSQL (`TELEMETRY_DATABASE_URL` y `REPORTING_DATABASE_URL`). No son una base única compartida por toda la aplicación.
- El worker de outbox de inventario procesa eventos transaccionales de telemetría con entrega at-least-once. Tiene una responsabilidad específica y queda fuera de esta propuesta.
- Ya hay un pipeline semanal de reporting que solicita ejecuciones mediante Prefect y devuelve HTTP 202. No conviene duplicar ese trabajo con Celery.
- Ya existe `app/celery_app.py` y la tarea de prueba `nexova.test.add`; se mantienen sin cambios en esta etapa.

## Operaciones candidatas consideradas (evaluación histórica de Etapa 1)

### A. Incident Analysis — seleccionada como primera candidata

`POST /api/incidents/analyze` acepta un CSV y, dentro de la petición, lee y normaliza todas sus filas, valida cada registro y calcula agregados. El coste y la memoria crecen con el tamaño del fichero; actualmente la ruta procesa todo antes de responder. El procesamiento real de los ficheros pequeños de prueba no se ha medido y no se afirma que hoy supere un umbral temporal concreto. La razón para elegirla es que el volumen de filas es variable y su trabajo es por fila, por lo que la latencia HTTP escala con el tamaño de entrada. Esta candidata tiene una limitación material que debe resolverse antes de implementarla: el CSV solo existe hoy en el cuerpo multipart y no hay un almacenamiento duradero/compartido identificado para trasladar la entrada al worker.

### B. Solicitud de restablecimiento de contraseña — no seleccionada

`POST /api/auth/forgot-password` llama sincrónicamente al proveedor Resend; el adaptador de `app/auth/email.py` tiene un timeout de red de 10 segundos. No se elige para evitar incluir el enlace/token de restablecimiento en el mensaje de Celery/Redis sin un diseño explícito de protección y ciclo de vida de secretos, así como por las dependencias del flujo de Auth en TinyDB.

### C. Reporting semanal — no seleccionada

`POST /api/reporting/pipeline-runs` ya solicita una ejecución Prefect con timeout cero y devuelve 202; tiene historial y almacenamiento de reporting propios. Usar Celery para sustituir o envolver ese flujo duplicaría el mecanismo de orquestación y no está justificado en esta primera integración.

## Operación elegida y alcance funcional propuesto

- **Nombre:** análisis agregado y seguro de CSV de incidencias (Incident Analysis).
- **Endpoint actual:** `POST /api/incidents/analyze` (el path HTTP es exactamente ese; definido directamente en `app/main.py`). El endpoint de exportación actual es `GET /api/incidents/results/export`.
- **Archivos principales:**
  - `services/api/app/main.py`: endpoint, decodificación del upload, serialización y `_latest_result`.
  - `services/api/app/incidents/csv_reader.py`: lectura, normalización y errores estructurales CSV.
  - `services/api/app/incidents/validation.py`: reglas de validación de filas.
  - `services/api/app/incidents/analysis.py`: agregación de métricas.
  - `services/api/app/incidents/models.py` y `schemas.py`: modelo agregado y contrato HTTP.
  - `services/api/app/incidents/export.py`: exportación agregada CSV.
  - `uis/backoffice/talent-pipeline-tracker/lib/incident-analysis-api.ts` y `components/incidents/IncidentAnalysisPanel.tsx`: consumidor actual que espera el resultado del análisis en la respuesta del POST y exporta el último resultado.
- **Funciones utilizadas hoy:** `read_incidents_csv`, `analyze_incidents`, `_serialize_result` y, para exportar, `export_analysis_csv`.
- **Qué resolvería:** la llamada HTTP dejaría de esperar a la lectura/validación/agregación completa; permitiría soportar ficheros crecientes sin mantener la conexión abierta durante todo el cálculo. Es razonable esperar menor latencia de respuesta tras encolar, pero el objetivo de <200 ms necesita medirse en condiciones normales y no se garantiza por este diseño.
- **Resultado:** exclusivamente las métricas agregadas que expone hoy `IncidentAnalysisResponse` (totales, dimensiones de categoría/estado/satisfacción y tipos de error). No debe devolver ni almacenar como resultado campos de filas originales, emails o descripciones.

## Flujo asíncrono propuesto en Etapa 1 (implementado en Etapa 2)

1. El cliente carga el CSV mediante `POST /api/incidents/analyze`.
2. FastAPI valida nombre/extensión, presencia y tamaño del upload; también debe validar de forma síncrona la estructura CSV suficiente para rechazar errores de petición antes de encolar, sin realizar el análisis de todas las filas.
3. La API guarda el archivo en un almacenamiento temporal durable y accesible desde API y worker, con nombre interno opaco (UUID), permisos restrictivos y política de borrado/retención. Celery recibe solo la referencia opaca, no el contenido CSV ni un objeto `UploadFile`/sesión.
4. La API encola la tarea registrada en la única instancia `celery_app` existente y responde `202` con `{"task_id":"..."}`.
5. Redis, configurado con `REDIS_URL`, transporta el mensaje y actúa como backend de resultados. La API local puede usar `redis://localhost:6379/0`; los contenedores usarán `redis://redis:6379/0`.
6. Un worker separado recupera el archivo de la ubicación compartida, ejecuta el análisis usando las funciones de dominio existentes y guarda el resultado agregado bajo el ID de tarea. Debe cerrar y eliminar el archivo de entrada en los casos de éxito y fallo terminal, además de contar con limpieza para temporales huérfanos.
7. Celery registra estado/resultado en el backend y, agotados los intentos, el error terminal se conserva también en la DLQ persistente definida en la Etapa 2.
8. El cliente consulta `GET /api/tasks/{task_id}` y recibe el estado real y, cuando corresponda, el agregado seguro. Un `PENDING` no permite distinguir por sí solo entre mensaje en cola y tarea desconocida/estado aún no guardado.

La ruta de estado propuesta es `GET /api/tasks/{task_id}` según la convención `/api` de la API actual. Si el contrato requerido debe ser literalmente `/tasks/{task_id}`, habrá que acordar antes cómo se integra con esa convención existente.

## Cambios que requería la Etapa 2 (ya implementados)

1. Extender `app/celery_app.py` (sin crear otra instancia), añadir autodiscovery/inclusión de la tarea y definir expiración de resultados y serialización JSON.
2. Añadir el módulo de tarea real a `app/tasks/`, separando la ejecución del transporte HTTP y reusando el dominio de incidentes.
3. Cambiar el POST a respuesta 202 y añadir consulta de estado bajo `/api/tasks/{task_id}`.
4. Adaptar el cliente del backoffice: hoy espera el agregado inmediatamente y descarga la exportación del último resultado global; deberá seguir el estado y mostrar/descargar el resultado de esa tarea. Se debe reemplazar la semántica global `_latest_result` por una asociada a cada tarea para evitar resultados cruzados entre usuarios, peticiones y procesos.
5. Introducir almacenamiento de entrada compartido y transitorio con borrado seguro. El repositorio inspeccionado no muestra un object store/almacenamiento de uploads ya establecido ni una ruta dedicada a ello. Esta es una decisión bloqueante: un archivo temporal local de la API no es una referencia fiable para un worker en otro contenedor. El análisis síncrono de estructura puede requerir leer una vez el archivo antes de encolar; se deben definir límites de tamaño y forma de evitar una carga completa en memoria.
6. Persistir DLQ en una base relacional existente y accesible desde worker/API, con migración e idempotencia por `task_id`; no usar Redis como único registro ni asociar la DLQ a la base de reporting/telemetría por conveniencia. Antes de implementarlo habrá que confirmar qué almacén PostgreSQL operativo y política de migraciones se debe usar.
7. Preservar las respuestas actuales de validación CSV inválido y las garantías de privacidad; documentar que el resultado ahora es por tarea, no “el último resultado” global.

## Riesgos y mitigaciones considerados durante Etapa 1

- **Concurrencia/aislamiento:** varias tareas simultáneas no deben escribir un resultado global compartido. Se recomienda asociar resultados a su `task_id` y hacer la API idempotente respecto a la referencia de entrada.
- **Archivos sensibles:** el CSV contiene campos como email, descripción e identificadores. No poner sus filas en el broker, logs, resultado Celery ni DLQ; limitar acceso y retención al archivo temporal y eliminarlo incluso tras fallo terminal.
- **Reintentos:** el análisis es determinista y no debe tener efectos de negocio; repetirlo es seguro si la salida se guarda por ID de tarea y el borrado de entrada contempla ejecución/reentrega repetida. Registrar en DLQ de forma idempotente.
- **Fallo del broker o almacenamiento:** si Redis no está disponible, no devolver una aceptación 202 que prometa una tarea que no se pudo encolar; responder con un error temporal seguro. Si falla el almacenamiento compartido o su limpieza, registrar el fallo sin exponer rutas/datos sensibles y establecer limpieza operacional.
- **Límites de entrada:** decidir y aplicar un tamaño máximo de upload y considerar uso de memoria, CSV malformado y ficheros grandes; la tarea no debe aceptar una referencia arbitraria enviada por el cliente.
- **Estado `PENDING`:** puede representar tanto una tarea en espera como un ID inexistente; el endpoint debe evitar presentarlo como confirmación de que está en cola.
- **Worker/Windows:** conservar el arranque local probado con `--pool=solo`; en Docker/Linux valorar `prefork` tras verificar dependencias y concurrencia del acceso a archivos/DB.

## Verificaciones de esta etapa

- Rama activa comprobada: `feature/celery-async-tasks`.
- La salida de `git status --short` estaba vacía al iniciar; no había cambios locales mostrados.
- Revisión estática de módulos/rutas, adaptador frontend y persistencias descritas arriba.
- No se ejecutaron tests: no hubo cambios de código o comportamiento que requirieran pruebas.
- No se modificó ni sustituyó `inventory_outbox_worker.py`, Prefect ni la tarea de prueba Celery.

## Decisiones aprobadas para la Etapa 2 (registro histórico)

- **CSV:** usar un volumen Docker compartido entre FastAPI y el worker Celery, montado en la misma ruta interna. Guardar con nombres opacos generados por el servidor, limitar tamaño y permisos, aplicar retención/limpieza y no enviar contenido CSV por Redis. Esta elección corresponde al Compose actual de un solo host; si los workers pasan a varios hosts, reevaluar almacenamiento de objetos.
- **DLQ (decisión inicial, reemplazada):** se eligió una tabla/migración propia, clave única por `task_id` y metadatos saneados, sin CSV, secretos ni filas. La implementación vigente usa `CELERY_DATABASE_URL`. La comprobación posterior encontró que su destino efectivo coincide con el destino de `TELEMETRY_DATABASE_URL`; la separación actual es por tabla en `public`, no por base ni por esquema. Reporting usa otra base.
- **Autorización:** la usuaria autorizó pasar a Etapa 2 después de aprobar estas propuestas.

## Estado del antiguo bloqueo de DLQ

El bloqueo descrito durante Etapa 1 (SQLite en `DATABASE_URL`, sin PostgreSQL
identificado) está superado para la persistencia técnica: la tabla de DLQ existe
en la base Supabase usada por `CELERY_DATABASE_URL`, la migración está registrada
y las escrituras de integración se validaron. No obstante, esa base también es
el destino efectivo de `TELEMETRY_DATABASE_URL`; la separación es solo por tabla
en el esquema `public`. El destino de reporting es independiente. Esta
configuración no proporciona aislamiento por esquema/rol y el worker no estaba
activo en Compose durante la comprobación.
