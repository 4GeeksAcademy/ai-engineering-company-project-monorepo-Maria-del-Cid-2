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

Configura `CORS_ORIGINS` como una lista separada por comas de orígenes exactos
(esquema, host y puerto), sin `*`. Si no se define, se usan los orígenes de
desarrollo indicados en `app/main.py`. En Codespaces, añade el origen reenviado
del frontend. Permite los headers `Authorization` y `Content-Type`.

## Incident Analysis

- `POST /api/incidents/analyze` recibe el campo multipart `file` y devuelve métricas agregadas. Ausencia, formato no CSV, contenido vacío o inválido producen HTTP 400.
- `GET /api/incidents/results/export` descarga como CSV el último resultado agregado del proceso. Antes de un análisis válido responde HTTP 404.
- El último resultado solo vive en memoria del proceso: no es persistente ni
    compartido entre workers. No se guardan ni devuelven filas originales o
    `customer_email`.
- La CLI está en `scripts/analyze.py`; puede exportar resultados agregados de forma interactiva. Revisa el destino antes de ejecutarla porque puede crear un archivo en el directorio de trabajo.

## Incident Manager

El gestor persistente utiliza TinyDB en `services/data/incidents.json` por
defecto o en la ruta indicada por `INCIDENTS_DB_PATH`. Sus tablas están
separadas del resultado temporal de Incident Analysis.

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

`TestClient` necesita `httpx`, declarado en el extra `test` de
`pyproject.toml`. Instálalo con `pip install -e "services/api[test]"` (o
`uv sync --extra test`). Starlette emite un aviso de deprecación a favor de
`httpx2`; no afecta a los resultados.

Estado conocido: con el fixture `scripts/incidents-nexova.csv` presente, la
suite completa pasa (verificado en una copia aislada). Sin él, fallan los tests
de Incident Analysis (`test_analysis`, `test_csv_reader`, `test_export`,
`test_cli`, `test_api`, `test_results_export_api`) porque el fixture, entregado
como adjunto del enunciado, nunca se versionó en el historial. La cobertura de
autenticación, perfiles, CORS y Supplier Directory pasa en ambos casos.

Al ejecutar tests, seeders o scripts que abran TinyDB, confirma que usan rutas
temporales/aisladas cuando no se pretende modificar `services/data`.
