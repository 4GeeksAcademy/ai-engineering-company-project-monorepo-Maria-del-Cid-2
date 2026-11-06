# Aprendiendo: almacenamiento de telemetría en Supabase

## Estado de esta práctica

Este documento acompaña la transición del receptor HTTP provisional a un
almacenamiento durable de eventos en Supabase. La Fase 1 creó y alineó el
esquema; la Fase 2 implementó el receptor real y sus pruebas automatizadas. El
frontend no se ha modificado.

La distinción sigue siendo importante: que una API acepte un evento con HTTP
200 no demuestra por sí solo que el evento llegue a Supabase. Ahora
`POST /api/telemetry/events` valida cada evento, intenta persistir los válidos
y devuelve contadores; la confirmación funcional de filas reales queda para la
Fase 3.

## Arquitectura confirmada

El recorrido actual es el siguiente:

```text
TelemetryService (Next.js)
  -> POST {"events": [...]} a /api/telemetry/events
  -> proxy /api del backoffice, cuando se usa Docker
  -> router FastAPI /api/telemetry/events
  -> validación Pydantic actual y logs
```

El frontend configura la URL con `NEXT_PUBLIC_TELEMETRY_ENDPOINT`. En Docker
el valor previsto es la ruta relativa `/api/telemetry/events`; el proxy de
`uis/proxy-server.js` la reenvía al servicio `backend`. Por tanto, la futura
persistencia debe permanecer detrás de ese mismo endpoint. Las variables
`NEXT_PUBLIC_*` se entregan al navegador y no pueden contener la URL privada de
PostgreSQL ni claves de Supabase.

`TelemetryEvent` está en `services/api/app/telemetry/models.py`. Representa el
envelope CloudEvents 1.0: `specversion`, `source`, `id`, `type`, `time`,
`datacontenttype`, `data`, `traceparent`, `sessionId` y `schemaVersion`. La
fase de almacenamiento debe reutilizarlo sin modificarlo.

La API ya usa PostgreSQL/Supabase para inventario mediante SQLModel y `psycopg`,
con `DATABASE_URL` privada y engine perezoso. Auth, proveedores e incidencias
siguen usando TinyDB. TinyDB no es adecuado para esta práctica porque no ofrece
JSONB ni las consultas e índices PostgreSQL requeridos.

## Eventos, contratos y dimensiones

El catálogo normativo es `docs/telemetry/event-schemas.json`; el plan de
producto está en `docs/telemetry/telemetry-plan.md`. Allí figuran 20 eventos
principales y el auxiliar `form_opened`. El frontend emite actualmente solo un
subconjunto: autenticación, navegación, formularios, inventario, incidencias y
proveedores; `section_viewed` está permitido pero no conectado desde el
provider.

Las propiedades de negocio viven en `data`. Al almacenarlas como `tags`, el
adaptador futuro tendrá que copiar únicamente las propiedades incluidas en el
schema/allowlist del tipo de evento y conservar dimensiones de Nexova como
`product_id`, `product_sku`, `office`, `branch`, `category`, `origin`,
`supplier_id`, `currency`, `form_id`, `instance_id` y `user_uuid` cuando estén
permitidas y presentes. No debe añadir una identidad ni conservar campos que
no estén aprobados. El modelo Pydantic actual valida el envelope, pero todavía
no aplica esos allowlists por tipo: es una diferencia conocida que el plan de
implementación debe resolver sin cambiar el contrato del cliente.

### Eventos con seguimiento activo en Supabase

La instrumentación activa del backoffice envía los siguientes 13 eventos al
endpoint, que los persiste en Supabase cuando se producen. La clasificación
procede de `telemetry-plan.md`:

| Evento | Clasificación |
|---|---|
| `inbound_order_created` | Obligatorio |
| `outbound_order_created` | Obligatorio |
| `login_succeeded` | Adicional |
| `login_failed` | Adicional |
| `account_created` | Adicional |
| `session_expired` | Adicional |
| `frontend_page_loaded` | Adicional |
| `frontend_render_error` | Adicional |
| `form_validation_failed` | Adicional |
| `form_opened` | Adicional |
| `form_abandoned` | Adicional |
| `incident_status_changed` | Adicional |
| `supplier_rate_updated` | Adicional |

`section_viewed` está permitido por el catálogo, pero no está conectado en el
provider activo y, por tanto, no se incluye en este listado. Los demás tipos del
catálogo son propuestas o eventos no instrumentados actualmente.

## Modelo de datos aprobado

El enunciado de la práctica exige una tabla `telemetry_events` de ocho columnas
y los índices individuales de `timestamp`, `event_type` y GIN sobre `tags`.
Sin embargo, el plan histórico propone diez columnas (`id`, `specversion`,
`source`, `type`, `idempotency`, `time`, `datacontenttype`, `data`,
`traceparent`, `ingested_at`) y dos índices compuestos distintos. No son el
mismo contrato y el repositorio no contiene otro documento que fije las ocho
columnas solicitadas.

Se aprobó el esquema canónico de ocho columnas orientadas a consulta. La
migración versionada `services/api/scripts/migrations/001_create_telemetry_events.sql`
lo declara, pero todavía no se ha aplicado contra Supabase:

| Columna | Tipo PostgreSQL | Nulos | Procedencia | Motivo |
|---|---|---|
| `id` | `BIGINT GENERATED ALWAYS AS IDENTITY` | no | servidor | clave primaria técnica de la fila |
| `event_id` | `UUID` | no | `TelemetryEvent.id` | idempotencia; único |
| `event_type` | `VARCHAR(100)` | no | `TelemetryEvent.type` | segmentación analítica |
| `timestamp` | `TIMESTAMPTZ` | no | `TelemetryEvent.time` | momento del hecho |
| `source` | `VARCHAR(255)` | no | `TelemetryEvent.source` | área emisora |
| `session_id` | `VARCHAR(100)` | sí | `TelemetryEvent.sessionId` | correlación opcional |
| `schema_version` | `VARCHAR(20)` | sí | `TelemetryEvent.schemaVersion` | evolución opcional |
| `tags` | `JSONB` | no | `TelemetryEvent.data` filtrado | dimensiones variables aprobadas |

El esquema desplaza `specversion`, `datacontenttype` y `traceparent` fuera de la
persistencia. Se seguirán validando al recibirlos, pero no serán consultables
históricamente. `event_id` tiene restricción única; su semántica ante reintentos
se implementará y probará en la fase del endpoint.

## PostgreSQL, Supabase y JSONB

Supabase aporta la instancia PostgreSQL que ya usa el dominio de inventario. En
esta práctica no implica usar credenciales desde el navegador: la conexión debe
originarse solo en FastAPI mediante configuración privada.

`JSONB` guarda un objeto JSON en formato que PostgreSQL puede indexar y
consultar. Es apropiado para `tags` porque los eventos comparten un envelope,
pero sus dimensiones varían por tipo. Un índice GIN permitirá filtrar por esas
claves y valores sin crear una columna física para cada propiedad. Los índices
normativos sobre tiempo y tipo atienden consultas temporales y por categoría.

Los eventos representan hechos inmutables. La aplicación solo necesitará la
operación de inserción masiva; no se diseñarán endpoints, repositorios ni
permisos de aplicación para actualizar o borrar eventos. La retención o el
borrado administrativo, si se aprueba, es una política operativa separada.

## Validación parcial y bulk insert

La forma actual `TelemetryBatch(events: list[TelemetryEvent])` hace que FastAPI
valide el lote antes de entrar al handler: un elemento inválido causa HTTP 422 y
descarta el lote entero. Eso contradice la aceptación parcial requerida para el
almacenamiento.

El cambio previsto recibirá el envelope de forma laxa, comprobará que `events`
es un array y ejecutará `TelemetryEvent.model_validate(raw_event)` uno por uno.
Los `ValidationError` incrementarán `rejected` y no impedirán procesar los
siguientes elementos. Los válidos se convertirán en filas y se enviarán en una
sola operación de inserción. Si la lista de filas queda vacía, no se abrirá una
operación de escritura. La respuesta prevista será:

```json
{"received": 3, "stored": 2, "rejected": 1}
```

La inserción debe ser un único bulk insert por lote, no un `INSERT` dentro del
bucle. Un error de persistencia no debe fingirse como éxito: se registrará sin
datos sensibles y se devolverá un error de servidor coherente; los contadores
solo representarán eventos efectivamente insertados. La semántica exacta ante
duplicados debe alinearse con la decisión pendiente de idempotencia.

## Plan de ejecución previsto

1. Fase completada: se aprobó el esquema y se creó la migración SQL versionada
   con la tabla y los tres índices requeridos. Falta aplicarla explícitamente
   contra el destino Supabase autorizado.
2. Crear un adaptador de persistencia aislado para telemetría, reutilizando las
   dependencias PostgreSQL ya resueltas por la API y una única llamada bulk por
   lote. Añadir solo configuración privada de backend si es imprescindible.
3. Sustituir el stub del router sin cambiar su ruta ni el envelope. Mantener
   `TelemetryEvent`, pero recibir datos sin validar por lote y validar cada
   elemento dentro del handler.
4. Transformar `data` en `tags` mediante los allowlists documentados, preservar
   dimensiones aprobadas y ampliar la respuesta a `received`, `stored` y
   `rejected`.
5. Añadir pruebas de lote válido, inválido, mixto, vacío y malformed envelope;
   comprobar la única llamada de inserción, la ausencia de inserción sin válidos
   y el mapeo de tags. Ejecutar las pruebas con una base aislada, nunca contra
   Supabase de trabajo.
6. Validar manualmente el flujo en el backoffice con entrada, salida y evento
   técnico, y comprobar las filas en Supabase. Esta comprobación sigue pendiente
   y no se afirma como realizada.

## Seguridad, errores y verificación

Las credenciales de Supabase, incluidas posibles claves `service_role`, deben
permanecer en variables privadas del backend, archivos locales ignorados o el
gestor de secretos del despliegue. No se escriben en documentación, logs ni
variables públicas. La respuesta al frontend seguirá dependiendo principalmente
del código HTTP; se añaden contadores sin exigir que el cliente cambie.

Antes de cerrar la siguiente etapa, las pruebas automatizadas deberán cubrir un
evento válido, uno inválido, lotes mixtos/todos válidos/todos inválidos/vacíos,
el envelope sin array, el mapeo de `tags`, los allowlists y la única inserción.
Una petición manual mezclada debe confirmar HTTP 200 y los tres contadores
cuando la inserción funcione. Ver los tests pasar no sustituye comprobar en
Supabase que las filas reales llegaron.

### Resultado de la aplicación de la migración

La migración se intentó desde el contenedor local `backend`, para usar su
configuración privada sin revelar valores. No llegó a ejecutar sentencias SQL:
la variable `DATABASE_URL` de ese entorno apunta a SQLite y `psycopg` rechazó
esa cadena antes de abrir una conexión. SQLite tampoco soporta `TIMESTAMPTZ`,
`JSONB` ni el índice GIN definidos para PostgreSQL.

Por tanto, no se creó ni modificó ninguna tabla local o remota. Para aplicar la
migración se necesita arrancar o ejecutar el backend con una `DATABASE_URL` de
PostgreSQL/Supabase autorizada. Este resultado no demuestra conectividad con
Supabase ni valida el DDL en PostgreSQL; solo confirma que el entorno Docker
actual no es el destino adecuado para esta migración.

### Verificación posterior de la tabla en Supabase

Tras crear la tabla manualmente en Supabase, se consultó su catálogo PostgreSQL
en modo solo lectura. Inicialmente existían las ocho columnas, los índices de
`timestamp` y `event_type`, un índice GIN sobre `tags`, y un trigger `BEFORE`
que bloquea tanto `UPDATE` como `DELETE` mediante
`prevent_telemetry_events_mutation()`. Sin embargo, faltaban restricciones de
nulabilidad, longitudes y unicidad de `event_id`.

Antes de cambiar el esquema se comprobó que la tabla estaba vacía y no contenía
datos incompatibles. Se aplicó entonces
`services/api/scripts/migrations/002_align_existing_telemetry_events.sql`. Esta
migración usa únicamente `ALTER TABLE` y `ALTER INDEX`: no recrea la tabla ni
modifica filas. También elimina el `DEFAULT gen_random_uuid()` de `event_id`,
porque el identificador debe proceder del evento CloudEvents validado y no ser
silenciosamente sustituido por uno del servidor.

La consulta posterior confirmó el contrato aprobado:

| Elemento | Resultado verificado |
|---|---|
| `id` | `BIGINT GENERATED ALWAYS AS IDENTITY`, clave primaria |
| `event_id` | `UUID NOT NULL`, restricción única |
| `event_type` | `VARCHAR(100) NOT NULL` |
| `timestamp` | `TIMESTAMPTZ NOT NULL` |
| `source` | `VARCHAR(255) NOT NULL` |
| `session_id` | `VARCHAR(100)` anulable |
| `schema_version` | `VARCHAR(20)` anulable |
| `tags` | `JSONB NOT NULL` |
| Índices analíticos | `idx_telemetry_events_timestamp`, `idx_telemetry_events_event_type`, `idx_telemetry_events_tags_gin` |
| Inmutabilidad | trigger `BEFORE UPDATE OR DELETE` presente |

La tabla seguía con cero filas al final de esta verificación. Se confirmó la
definición del trigger en el catálogo; no se insertaron eventos de prueba ni se
intentó modificar o borrar una fila para no alterar datos de telemetría.

## Fase 2: endpoint real de almacenamiento

La Fase 2 sustituye el stub sin cambiar el contrato de transporte del cliente.
La ruta sigue siendo `POST /api/telemetry/events` y el body sigue siendo
`{ "events": [...] }`. No se cambió código del frontend ni el modelo
`TelemetryEvent`.

### Conexión aislada de Supabase

El inventario conserva `DATABASE_URL`, que en Docker de desarrollo puede ser
SQLite. Telemetría usa exclusivamente `TELEMETRY_DATABASE_URL`: es una variable
privada del backend, debe contener una URL PostgreSQL/Supabase y nunca lleva el
prefijo `NEXT_PUBLIC_`. No existe fallback a `DATABASE_URL`.

`TelemetryRepository` obtiene esa configuración de forma perezosa, solo si ya
hay eventos válidos que insertar. Si falta o apunta a SQLite, la petición con
eventos válidos responde HTTP 503 sin exponer la URL ni el error del driver. Un
lote vacío o completamente inválido responde sus contadores sin abrir conexión.

### Validación parcial y proyección a tags

El handler recibe `Any`, verifica que existe un array `events` y recorre cada
elemento. Para cada uno llama a `TelemetryEvent.model_validate(raw_event)`.
Un `ValidationError` incrementa `rejected`; no cancela el resto del lote.

Los eventos válidos se convierten en registros con los campos de la tabla. La
función `filter_tags()` copia a JSONB solo claves permitidas en el catálogo de
Nexova. Por ejemplo, un `inbound_order_created` conserva `product_id`,
`product_sku` y `quantity`, pero descarta cualquier clave no documentada. El
allowlist está en código para no depender de leer archivos de documentación en
tiempo de ejecución.

### Bulk insert e idempotencia

El repositorio construye una única sentencia `INSERT` con todas las filas
válidas y usa `ON CONFLICT (event_id) DO NOTHING`. No contiene bucles de
inserciones, `UPDATE` ni `DELETE`. El `RETURNING event_id` permite calcular
`stored` como filas realmente insertadas. Un reintento de un ID ya almacenado
no es un error de validación: puede responder `stored: 0` y `rejected: 0`.

El resultado normal es `{ "received": N, "stored": M, "rejected": R }`.
Los bodies que no contienen un array `events` devuelven HTTP 400. Un fallo de
conexión o inserción devuelve HTTP 503 con un mensaje seguro.

### Pruebas realizadas

Se ejecutaron 29 pruebas focalizadas y todas pasaron. Cubren los modelos
Pydantic, la configuración exclusiva de telemetría, el filtrado de tags y el
handler HTTP con un repositorio falso. Se comprobaron: evento válido, lote
mixto, todos inválidos, lote vacío, envelope inválido, duplicado idempotente,
error de persistencia y una única llamada al repositorio por lote válido.

No se insertaron eventos de prueba en Supabase durante esta fase. La integración
HTTP no abre una conexión real porque sustituye el repositorio; por ello no
sustituye la validación funcional de la Fase 3.

El contenedor no tenía la dependencia que exige `starlette.testclient`. Se
instaló temporalmente para validar y se declaró `httpx2` exclusivamente en el
extra `test` de `services/api/pyproject.toml`; `uv.lock` quedó actualizado. No
se añadió ninguna dependencia de producción.

## Problemas encontrados y conclusiones

El problema documental y contractual inicial se resolvió con el esquema de ocho
columnas aprobado y la migración de alineación aplicada sin recrear la tabla.
La Fase 1 y la Fase 2 quedan completadas. Antes de la Fase 3 hay que configurar
`TELEMETRY_DATABASE_URL` en el proceso FastAPI activo y verificar desde el
backoffice que los eventos de entrada, salida y un evento técnico llegan a
Supabase. Esa comprobación no se ha realizado todavía.

## Fase 3: verificación end-to-end en curso

Se ejecutó de nuevo la suite focalizada de telemetría: **29 pruebas correctas**.
Esto cubre la validación parcial, los contadores, el filtrado de `tags` y la
única llamada al repositorio, pero usa un repositorio falso y no prueba una
escritura PostgreSQL real.

La configuración inicial de `TELEMETRY_DATABASE_URL` tuvo varios problemas de
formato: ausencia de valor, corchetes alrededor de un hostname DNS, parámetro
de URI sin valor y caracteres reservados sin codificar. Tras corregir la URI y
actualizar la contraseña, el backend conectó con Supabase usando esta variable
privada, sin alterar `DATABASE_URL` ni el frontend.

Se envió un lote mixto real al endpoint activo a través del proxy del
backoffice (`http://localhost:3001/api/telemetry/events`). Contenía una entrada
válida y otra con UUID inválido. El resultado fue **HTTP 200**:

```json
{"received":2,"stored":1,"rejected":1}
```

La fila del UUID válido se consultó directamente en `public.telemetry_events`.
Se confirmó `event_type: inbound_order_created`, `source: /nexova/inventory`,
`session_id: e2e-session`, `schema_version: 1.0.0` y las etiquetas
`product_id`, `product_sku`, `quantity` y `office`. La propiedad no aprobada
añadida deliberadamente al payload no se almacenó. Esto confirma el recorrido
real proxy → API → inserción PostgreSQL/Supabase y el filtrado de `tags`.

Una petición equivalente para reproducir el lote es:

```bash
curl -i -X POST http://localhost:3001/api/telemetry/events \
  -H 'Content-Type: application/json' \
  -d '{"events":[
    {"specversion":"1.0","source":"/nexova/inventory","id":"<uuid-valido>","type":"inbound_order_created","time":"2026-11-04T12:00:00Z","datacontenttype":"application/json","data":{"product_id":42,"product_sku":"NXV-E2E-42","quantity":1,"office":"madrid"},"sessionId":"e2e-session","schemaVersion":"1.0.0"},
    {"specversion":"1.0","source":"/nexova/inventory","id":"uuid-invalido","type":"inbound_order_created","time":"2026-11-04T12:00:00Z","datacontenttype":"application/json","data":{}}
  ]}'
```

La validación manual del backoffice se completó después de esperar el intervalo
de envío del cliente. Supabase contenía tres filas nuevas, en orden temporal:

| Acción realizada | Evento comprobado | Source | Etiquetas comprobadas |
|---|---|---|---|
| Crear una orden de entrada | `inbound_order_created` | `/nexova/inventory` | producto, cantidad, sede, proveedor y moneda |
| Crear una orden de salida | `outbound_order_created` | `/nexova/inventory` | producto, cantidad, sede y tipo de salida |
| Intentar iniciar sesión con contraseña incorrecta | `login_failed` | `/nexova/auth` | `failure_reason` |

Las tres filas tenían `session_id` y `schema_version: 1.0.0`. Esta comprobación
verifica que la instrumentación real del backoffice, su envío agrupado y la
persistencia en Supabase funcionan para los tres escenarios exigidos. La Fase 3
queda completada.

La comprobación final detectó que el catálogo histórico marcaba `user_uuid`
como obligatorio para `login_failed`, mientras que el flujo seguro de login
fallido solo almacena `failure_reason`: antes de autenticar no existe una sesión
ni se debe derivar una identidad a partir de credenciales introducidas. Se
alinearon el catálogo y el plan para que `user_uuid` sea opcional en este evento.
El allowlist ya admitía `failure_reason`, por lo que no fue necesario cambiar
frontend, backend ni `TelemetryEvent`.
