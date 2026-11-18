# Nexova API

Servicio FastAPI que reúne Incident Analysis, Supplier Directory y autenticación
de usuarios/perfiles. Los routers están registrados en `app/main.py`; las rutas
incluyen explícitamente el prefijo `/api`.

## Ejecutar

```bash
cd services/api
python -m pip install -e ../../packages/shared/python
python -m pip install -e .
uvicorn app.main:app --reload
```

## Pipeline de reporting de inventario

Las escrituras inbound y outbound guardan el movimiento y su evento en la tabla
`telemetry_outbox` dentro de la misma transacción de inventario. Un proceso
separado (`inventory-outbox-worker`) consume esa outbox y escribe de forma
idempotente en `public.telemetry_events`, usando `event_id` como clave única.
API y worker comparten `DATABASE_URL`; el worker también requiere
`TELEMETRY_DATABASE_URL`. Ejecuta la migración aditiva de inventario antes de
arrancar el worker; no migra al iniciar. Consulta
`services/inventory-outbox-worker/README.md` para ejecución, Compose, reintentos,
leases y retención.

El pipeline emite `inbound_order_created`, `outbound_order_created`,
`stock_threshold_triggered` y `kit_cost_variance_detected`. La alerta de stock
se emite cuando una salida cruza de `stock >= threshold` a `stock < threshold`;
no se repite mientras siga por debajo, y se rearma al reponer hasta el umbral o
más. La variancia del kit usa el coste medio ponderado y los snapshots de
preparación. La entrega es at-least-once con deduplicación por `event_id`; no
existe transacción distribuida entre las dos bases.

El seed de inventario de demostración es explícito y separado del seed
histórico. Ejecuta primero el seed de programas y luego, desde `services/api`,
usa `uv run python -m app.inventory.seed --environment test --programme-id
prog-digital-skills-001 --demo`. Solo se permite con identidad de base
`development` o `test`; no se ejecuta al iniciar la API. Los activos de demo
usan SKU con prefijo `NXV-DEMO-` y los movimientos se crean por operaciones de
dominio para mantener ledger, valoración y outbox coherentes.

Configura `CORS_ORIGINS` como una lista separada por comas de orígenes exactos
(esquema, host y puerto), sin `*`. Si no se define, se incluye `localhost:3000`
y, cuando existe `CODESPACE_NAME`, el origen exacto
`https://<CODESPACE_NAME>-3000.<GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN>`.
En Codespaces, conserva ambos orígenes explícitamente al arrancar la API, por
ejemplo:

```bash
CORS_ORIGINS=http://localhost:3000,https://friendly-barnacle-qv5p44r9rxq2644j-3000.app.github.dev \
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

No uses `*`. Permite los headers `Authorization` y `Content-Type`.

## Incident Analysis

- `POST /api/incidents/analyze` recibe el campo multipart `file`, valida el CSV y
    responde `202` con un `task_id`. El límite por defecto es 10 MiB y se puede
    cambiar con `INCIDENT_ANALYSIS_MAX_UPLOAD_BYTES`. Ausencia, formato no CSV,
    contenido vacío o inválido producen HTTP 400; los archivos demasiado grandes
    producen HTTP 413.
- `GET /api/tasks/{task_id}` devuelve el estado (`pending`, `started`, `success`,
  `failure`, `retry` o `revoked`) y, al terminar correctamente, el resultado
    agregado. Los errores son genéricos y no exponen excepciones del worker.
- `GET /api/incidents/tasks/{task_id}/export` descarga el CSV agregado de esa
    tarea concreta. No hay resultado global “último”, por lo que las peticiones
    concurrentes no se mezclan.
- En Compose, API y `incident-analysis-worker` comparten el volumen
    `incident_analysis_uploads` en `/var/lib/nexova/incident-analysis`. El broker
    y backend de resultados son Redis. La API publica solo un identificador opaco;
    CSV, emails, descripciones y filas nunca viajan por Celery ni se devuelven.
    Los archivos tienen permisos restrictivos, se eliminan al procesarse y una
    limpieza oportunista retira archivos antiguos tras 24 horas. Si se despliegan
    workers en varios hosts, sustituir el volumen local por almacenamiento de
    objetos compartido.
- La tarea reintenta errores transitorios seleccionados hasta dos veces (tres
    intentos en total), con esperas exponenciales de 1 y 2 segundos. Éxitos y
    fallos terminales eliminan el CSV; los fallos terminales se registran de
    forma idempotente por `task_id` en `public.celery_incident_analysis_dlq`.
- La DLQ usa `CELERY_DATABASE_URL` con TLS obligatorio y una tabla/migración
    propia. La comprobación de identidad efectiva confirmó que este URL y
    `TELEMETRY_DATABASE_URL` llegan a la misma base PostgreSQL de Supabase y al
    esquema `public`; la separación existente es a nivel de tabla: la DLQ y
    `public.telemetry_events` son relaciones independientes, sin compartir ni
    duplicar filas. Reporting permanece en la base local `nexova_reporting`,
    con sus tablas bajo el esquema `reporting`; la tabla DLQ no existe allí.
    No se creó otra base/proyecto ni se modificaron tablas de telemetría o
    reporting. Esta separación es lógica a nivel de tabla, no aislamiento por
    esquema o por rol PostgreSQL.
- La DLQ almacena solo ID/nombre de tarea, fecha, número de intento y clase de
    error saneada; no guarda CSV, filas, emails, descripciones ni mensajes de
    excepción. Las pruebas de Etapa 2 cubren el flujo local con worker real,
    reintentos, limpieza, terminal DLQ/TLS e idempotencia. La validación
    registrada: 16 pruebas enfocadas de backend y 89 pruebas del backoffice
    pasan. La suite completa de backend reportó 291 pasadas, 27 subtests
    pasados y un fallo ajeno a esta etapa en el CLI por codificación `cp1252`
    en Windows.
- La CLI está en `scripts/analyze.py`; puede exportar resultados agregados de forma interactiva. Revisa el destino antes de ejecutarla porque puede crear un archivo en el directorio de trabajo.

### Operación de Celery

#### Docker Compose

Desde la raíz del repositorio, con las variables necesarias definidas en el
`.env` local (no compartas su contenido):

```powershell
docker compose up -d redis backend incident-analysis-worker flower
docker compose ps redis backend incident-analysis-worker flower
docker compose logs -f incident-analysis-worker
```

Redis debe estar healthy antes de que el worker arranque. Para parar solo estos
servicios, sin bajar el resto del stack:

```powershell
docker compose stop flower incident-analysis-worker backend redis
```

No se requiere reiniciar `inventory-outbox-worker` para procesar tareas Celery:
es un consumidor independiente de la outbox de inventario, usa sus propios
`DATABASE_URL` y `TELEMETRY_DATABASE_URL`, y no consume la cola de incidentes.

#### Ejecución local

Requiere Redis accesible en el host, dependencias instaladas desde el proyecto
API, y un directorio de uploads al que API y worker puedan acceder. Desde la
raíz, por ejemplo en PowerShell:

```powershell
$env:REDIS_URL = "redis://localhost:6379/0"
$env:INCIDENT_ANALYSIS_UPLOAD_DIR = Join-Path $env:TEMP "nexova-incident-analysis"
# Define SECRET_KEY mediante la configuración segura local antes de iniciar la API.
New-Item -ItemType Directory -Force $env:INCIDENT_ANALYSIS_UPLOAD_DIR | Out-Null
Set-Location services/api
uv sync --extra test
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

En otras dos terminales, con el mismo `REDIS_URL` y el mismo valor de
`INCIDENT_ANALYSIS_UPLOAD_DIR`:

```powershell
Set-Location services/api
uv run celery -A app.celery_app:celery_app worker --loglevel=INFO --pool=solo
```

```powershell
Set-Location services/api
uv run python -m flower --app=app.celery_app:celery_app `
    --broker=redis://localhost:6379/0 flower --address=127.0.0.1 --port=5555
```

`--pool=solo` es apropiado para desarrollo local en Windows; Compose ejecuta el
worker dentro de Linux con la configuración del servicio. Un directorio local
no es almacenamiento compartido entre máquinas: si el worker corre en otro
host, sustituye el directorio por un almacenamiento accesible y seguro para
ambos procesos.

#### Consultar estado y exportar

Envía el CSV como multipart con el campo `file` a `POST
/api/incidents/analyze`; conserva el `task_id` opaco de la respuesta `202`.
Desde PowerShell, por ejemplo:

```powershell
curl.exe -F "file=@.\incidents.csv;type=text/csv" `
    http://127.0.0.1:8000/api/incidents/analyze
```

Consulta el estado con:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/tasks/<task_id>
```

Cuando el estado sea `success`, descarga el agregado de esa tarea (no un
resultado global compartido) con:

```powershell
Invoke-WebRequest -OutFile .\incident-analysis.csv `
    http://127.0.0.1:8000/api/incidents/tasks/<task_id>/export
```

En los contenedores el broker es `redis://redis:6379/0`; desde procesos locales
que corren en Windows se usa `redis://localhost:6379/0`. No copies la URL del
contenedor al host ni viceversa. API y worker deben compartir el mismo volumen o
directorio de uploads. El estado `pending` por sí solo no distingue una tarea
en cola de un ID desconocido.

#### Configuración y verificación

Variables relevantes (los valores dependen del entorno; nunca publiques sus
valores reales):

| Variable | Uso |
|---|---|
| `REDIS_URL` | Broker y backend de resultados de Celery; hostname `redis` en Compose, normalmente `localhost` en local. |
| `INCIDENT_ANALYSIS_UPLOAD_DIR` | Directorio compartido entre API y worker. |
| `INCIDENT_ANALYSIS_MAX_UPLOAD_BYTES` | Tamaño máximo de carga; Compose usa 10 MiB. |
| `INCIDENT_ANALYSIS_UPLOAD_RETENTION_SECONDS` | Retención de temporales huérfanos; Compose configura 24 horas. |
| `CELERY_DATABASE_URL` | PostgreSQL de DLQ; requiere TLS. Configúralo únicamente donde deban persistirse fallos terminales. |
| `SECRET_KEY` | Necesaria para importar la configuración de autenticación de la API y ejecutar suites que cargan la aplicación. |
| `AUTH_DB_PATH`, `SUPPLIER_DIRECTORY_DB_PATH`, `INCIDENTS_DB_PATH` | Permiten aislar las bases TinyDB durante tests locales. |

Desde `services/api`, las suites útiles son:

```powershell
uv run pytest -q tests/test_incident_analysis_task_reliability.py tests/test_async_incident_analysis_api.py
uv run pytest -q tests/test_local_celery_incident_analysis_integration.py
uv run pytest -q
```

La integración local usa Redis y ejecuta un worker Celery en proceso; su caso
que persiste en la DLQ requiere `CELERY_DATABASE_URL` configurada y escribe en
esa base, por lo que no debe apuntarse a producción. La suite de todo el backend
también necesita `SECRET_KEY` y rutas TinyDB temporales/aisladas. El conjunto
focalizado y los resultados observados en la validación Stage 4 están anotados
en `CELERY_ASYNC_AUDIT.md`; los skips dependientes de configuración no son
pruebas de fallo.

## Incident Manager

El gestor persistente utiliza TinyDB en `services/data/incidents.json` por
defecto o en la ruta indicada por `INCIDENTS_DB_PATH`. Sus tablas están
separadas del resultado temporal de Incident Analysis.

Todos los endpoints del gestor requieren un JWT Bearer válido, igual que
Supplier Directory. La interfaz obtiene el token mediante `/api/auth/login` y
lo envía automáticamente en las peticiones protegidas.

- `POST /api/incidents` crea una incidencia.
- `GET /api/incidents` lista y filtra por `status`, `origin`, `branch` y
    `category`.
- `GET /api/incidents/{id}` obtiene el detalle.
- `PATCH /api/incidents/{id}/status` aplica únicamente transiciones válidas.
- `GET /api/incidents/summary` devuelve totales por estado, categoría, origen y
    sede, incluyendo ceros cuando la base está vacía.

El seed histórico se ejecuta explícitamente desde la raíz:

```bash
INCIDENTS_DB_PATH=/tmp/nexova-incidents.json \
PYTHONPATH=packages/shared/python/src:services/api python scripts/seed_incidents.py
```

Lee exclusivamente `scripts/incidents-nexova.csv`, aplica las transformaciones
definidas en `CONTEXT-INCIDENT-MANAGER.md`, informa de las filas descartadas y
comprueba los conteos transformados esperados. Las claves de `ticket_id` se
conservan solo en una tabla técnica de idempotencia; nunca forman parte del
modelo ni de la respuesta API.

El CSV debe estar disponible exactamente en `scripts/incidents-nexova.csv`. Si
no está presente, el seed no puede ejecutarse y los tests históricos que
dependen de ese fixture fallan. El seed no se ejecuta al arrancar FastAPI y
debe usar `INCIDENTS_DB_PATH` temporal para validaciones que no deban modificar
`services/data`.

## Autenticación

- `POST /api/auth/login`: formulario OAuth2 URL-encoded; `username` contiene el email y se envía también `password`.
- `GET /api/auth/me`: valida la identidad del JWT Bearer.
- `POST /api/auth/forgot-password`: solicita un enlace de recuperación. Siempre responde `200` con un mensaje genérico, exista o no la cuenta y aunque el proveedor de email no esté disponible.
- `POST /api/auth/reset-password`: consume un token temporal de un solo uso y actualiza la contraseña.
- `POST /api/auth/change-password`: ruta protegida; verifica la contraseña actual y actualiza la nueva contraseña.
- `POST /api/users`: recibe JSON con `email` y `password`; responde `201` al crear, `409` si el email ya existe y `422` si falla la validación. El registro no inicia sesión.
- Las rutas de perfiles están en el router registrado desde `app/main.py`.

La autenticación usa TinyDB en `services/data/auth.json` por defecto o la ruta
de `AUTH_DB_PATH`. El lock de registro protege solo dentro de un proceso; usa un
único worker con esta persistencia. Varios workers requieren una persistencia
con unicidad atómica de email.

Los tokens de recuperación se guardan únicamente como hash en la tabla
`password_reset_tokens` de la misma BD de auth. Caducan, se invalidan al emitir
uno nuevo y solo pueden consumirse una vez. Al cambiar o restablecer una
contraseña se incrementa `credentials_version`; los JWT emitidos con la versión
anterior dejan de ser válidos.

### Email de recuperación

La API usa un adaptador aislado para Resend. Para activar el envío real, crea
`services/api/.env` (archivo local ignorado por git) y añade:

```text
RESEND_API_KEY=tu_api_key_de_resend
RESEND_FROM_EMAIL=Nexova <tu-remitente-verificado@example.com>
PASSWORD_RESET_FRONTEND_URL=http://localhost:3000/reset-password
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=30
```

No introduzcas la API key en el código, en `services/data/`, en el frontend ni
en variables `NEXT_PUBLIC_*`. Los tests usan un email sender falso y no realizan
llamadas a Resend.

Como extensiones opcionales, el email incluye una versión HTML generada por el
adaptador, `forgot-password` limita a 3 solicitudes por email en una ventana de
una hora y los eventos de solicitud/reset se guardan en la tabla TinyDB
`password_reset_audit_log` con timestamp, IP, email cuando está disponible y
tipo de evento. No se guardan tokens ni contraseñas. Estas extensiones solo
coordinan dentro de un proceso.

## Supplier Directory

Todas las rutas de proveedores requieren JWT Bearer:

- `GET /api/suppliers` lista y acepta filtros opcionales `country` y `category`.
- `POST /api/suppliers` crea un proveedor (`201`).
- `GET /api/suppliers/{supplier_id}` obtiene un proveedor.
- `PATCH /api/suppliers/{supplier_id}/rate` actualiza su tarifa.
- `PATCH /api/suppliers/{supplier_id}/status` actualiza su estado.
- `DELETE /api/suppliers/{supplier_id}` elimina un proveedor (`204`).

La persistencia es TinyDB independiente de auth. Usa
`services/data/suppliers.json` por defecto o `SUPPLIER_DIRECTORY_DB_PATH`. El
seeder de `app/suppliers/seed.py` es explícito e idempotente; no se ejecuta al
arrancar FastAPI. Antes de diagnosticar una lista vacía, verifica la ruta
efectiva del proceso y que el token sea válido: sin credenciales o con JWT
inválido la API responde `401`, no una lista vacía.

## Verificación

Desde la raíz del repositorio:

```bash
PYTHONPATH=packages/shared/python/src:services/api \
SECRET_KEY=... \
AUTH_DB_PATH=$(mktemp -d)/auth.json \
SUPPLIER_DIRECTORY_DB_PATH=$(mktemp -d)/suppliers.json \
python -m unittest discover -s services/api/tests -p 'test_*.py'
```

`SECRET_KEY` es obligatoria: `app/auth/config.py` falla al importarse sin ella.
Las rutas TinyDB temporales son necesarias porque `AuthSemanticTests` e
`IncidentsPublicTests` (`tests/test_auth_unit5.py`) construyen la app real sin
aislar la base de datos y, por defecto, abrirían `services/data/auth.json`.

`TestClient` necesita `httpx2`, declarado en el extra `test` de
`pyproject.toml`. Instálalo con `pip install -e "services/api[test]"` (o
`uv sync --extra test`). La versión instalada de Starlette usa `httpx2` para
crear el cliente de pruebas.

Estado conocido: con el fixture `scripts/incidents-nexova.csv` presente, la
suite completa pasa (verificado en una copia aislada). Sin él, fallan los tests
de Incident Analysis (`test_analysis`, `test_csv_reader`, `test_export`,
`test_cli`, `test_api`, `test_results_export_api`) porque el fixture, entregado
como adjunto del enunciado, nunca se versionó en el historial. La cobertura de
autenticación, perfiles, CORS y Supplier Directory pasa en ambos casos.

Al ejecutar tests, seeders o scripts que abran TinyDB, confirma que usan rutas
temporales/aisladas cuando no se pretende modificar `services/data`.
