# Progress — Nexova

### Dockerización local del monorepo — Fase 1

Implementado el entorno de desarrollo local, sin cambios de producción:

- `docker-compose.yml` define `interfaces` y `backend` en la red explícita
  `nexova-dev-network`, con puertos host `3000`, `3001` y `8000`.
- `uis/Dockerfile` usa Node Alpine, instala el backoffice Next.js y arranca
  `uis/start.sh`; `uis/proxy-server.js` sirve la web estática en `3000`,
  reenvía el backoffice por `3001` y deriva `/api` a `http://backend:8000`.
- `services/Dockerfile` usa Python 3.12, instala `uv` y las dependencias de
  `services/api/requirements.txt`, generado desde `pyproject.toml` y
  `uv.lock`, incluyendo `packages/shared/python`.
- Los bind mounts permiten recarga de Uvicorn y ejecución de Next.js en modo
  desarrollo, y montan `services/data` para persistencia local. SQLite se usa solo en el `.env`
  local para inventario, sin añadir un tercer contenedor.
- `.env.example`, `.dockerignore` raíz, `uis/.dockerignore` y
  `services/.dockerignore` documentan y protegen la configuración local.
- Verificado: `docker compose config`, build de ambas imágenes, arranque de
  ambos contenedores, website en `3000`, backoffice en `3001`, `/api` desde
  ambos puertos, recarga de Uvicorn, bind mounts y persistencia de los JSON
  sin modificar los datos de trabajo.
- `npm test` (8/8) y TypeScript pasan. El lint global mantiene errores
  preexistentes ajenos a Docker. El build local de Next no concluye porque
  Turbopack no puede enlazar un proceso interno en el entorno de validación.
- La web estática actual no realiza peticiones a FastAPI; el proxy queda
  preparado para `/api`, pero no se ha inventado una integración funcional.
- No se ha conectado ni modificado el VPS.

### Frontend de inventario — Fase 1: capa de integración

Iniciado el frontend del módulo de inventario en
`uis/backoffice/talent-pipeline-tracker` (Next.js App Router sobre la API de
`services/api`). Esta fase no añade vistas: define los tipos, la capa API
centralizada y sus pruebas. Fases posteriores añadirán las 4 vistas
(productos con stock coloreado, entrada, salida e histórico de órdenes),
siguiendo esta capa sin abrir `fetch` directamente.

- `types/inventory.ts`: espejo de `services/api/app/inventory/schemas.py`.
  Constantes `INVENTORY_OFFICES = ["Valencia", "Miami"]`,
  `INVENTORY_EXIT_TYPES = ["allocation", "consumption"]` con etiquetas de UI;
  `AssetWithStock` (producto + `current_stock` derivado), `AssetEntry(Create)` y
  `AssetExit(Create)`, y `InventoryOrder` como unión discriminada por `type`
  (`entry` | `exit`). `types/index.ts` re-exporta todo desde `@/types`.
- `lib/inventory.ts`: capa de integración autenticada. Todas las llamadas pasan
  por `nexovaApi.request` con `auth: true` (Bearer). Sigue el patrón inyectable
  de `lib/profile-api.ts`: cada función recibe
  `client: InventoryApiClient = Pick<NexovaApiClient, "request">`; las páginas
  pasan el singleton `nexovaApi`, los tests inyectan un cliente simulado.
  Funciones: `listProducts`, `getProduct(client, id)`, `listOrders`,
  `createInbound(client, payload)`, `createOutbound(client, payload)` e
  `inventoryErrorMessage(error, fallback)` (4xx → detail de la API si no es
  genérico; network/timeout/5xx → `getUserFacingApiError`; cancelado → `null`).
- `tests/inventory-api.test.mjs`: mismo patrón que `tests/profile-api.test.mjs`
  (`MemoryStorage` + `NexovaApiClient` con fetch mock). Cubre GET/POST,
  cabecera Bearer, payload JSON, rechazo 400 por stock insuficiente, 428,
  409, 503 y el traductor de mensajes.
- Verificación desde `uis/backoffice/talent-pipeline-tracker`: `npm test` →
  **70/70 tests frontend**; `npx eslint lib/inventory.ts tests/inventory-api.test.mjs`
  sin errores; `npx tsc --noEmit` sin errores. Los errores de lint en
  `hooks/useRecords.ts` son preexistentes y no se tocaron en esta fase.
- Documentado en `docs/aprendiendo-gestion-inventario-orm-doble-bbdd.md`
  (sección "Fase 1 del frontend"). Los umbrales confirmados para la vista de
  stock se documentarán en su fase: verde ≥ 8, ámbar 2-7, rojo ≤ 1.
- No se creó commit ni push; se espera confirmación del usuario para la Fase 2.

### Frontend de inventario — Fase 2: vista de stock actual con colores

Primera vista de inventario: lista de productos con el stock derivado
coloreado, navegación en el header y rutas protegidas. Los umbrales
confirmados se vuelven visibles en la UI (verde ≥ 8, ámbar 2-7, rojo ≤ 1).

- `types/inventory.ts`: `stockLevelFor(currentStock)` clasifica
  `>= 8 → "healthy"`, `>= 2 → "low"`, resto → `"out"`; `STOCK_LEVEL_LABELS`
  (`Healthy`/`Low`/`Out of stock`). Re-exportados en `types/index.ts`.
- `app/inventory/products/page.tsx`: wrapper fino → panel (patrón suppliers).
- `components/inventory/InventoryCurrentStockPanel.tsx`: carga
  `listProducts(nexovaApi)` al montar; estados loading (Spinner), error
  (`inventoryErrorMessage`) y vacío; por producto muestra avatar stock
  coloreado (número + "units" dentro del cuadro), nombre, SKU · categoría ·
  oficina y badge de nivel; resumen "N productos · M unidades en total";
  accesos "Create inbound"/"Create outbound" con preselección `?product={id}`
  (para fases 3/4). Ambos botones comparten la misma estética secundaria y en
  escritorio se apilan en vertical uno encima del otro.
- `components/inventory/index.ts`: barrel del dominio.
- `components/auth/AuthShell.tsx`: dropdown **Inventory** (escritorio y móvil)
  con Current Stock, Inbounds, Outbounds y All Orders; `DropdownName` incluye
  `"inventory"`.
- `lib/auth-navigation.ts`: `protectedRoutes` incluye `/inventory/products`,
  `/inventory/orders/inbound`, `/inventory/orders/outbound`,
  `/inventory/orders`.
- Verificación: `npm test` → **70/70 tests frontend**; ESLint limpio en
  archivos nuevos/cambiados; `npx tsc --noEmit` sin errores. Los errores de
  lint en `hooks/useRecord.ts`/`hooks/useRecords.ts` son preexistentes.
- Documentado (sección "Fase 2 del frontend" en
  `docs/aprendiendo-gestion-inventario-orm-doble-bbdd.md`). Sin commit/push;
  se espera confirmación para la Fase 3.

### Frontend de inventario — Fase 3: formulario de entrada (inbound)

Formulario para registrar una entrada (recepción) en
`POST /inventory/orders/inbound`, reutilizando `createInbound` (Fase 1) y la
preselección `?product={id}` preparada en la Fase 2.

- `app/inventory/orders/inbound/page.tsx`: server component que lee
  `searchParams.product` (patrón login/reset-password; soporta string o array)
  y pasa `initialProductId` al panel.
- `components/inventory/InboundFormPanel.tsx` (cliente): select de producto
  cargado con `listProducts(nexovaApi)` en el montaje (placeholder por estado:
  cargando/error/vacío, deshabilitado sin productos); preselección por
  `?product={id}`; campos `quantity` (min 1), `supplier` (requerido) y
  `office` (`INVENTORY_OFFICE_OPTIONS`); al elegir producto muestra el stock
  actual de contexto; envío con `createInbound` (quantity a Number), estados
  saving/error/created (banner verde con "#ID"), reset tras crear; enlace
  "Back to current stock".
- Corrección posterior (probado con entrada real): `resetForm()` limpiaba
  `created` con `setCreated(null)` justo tras haberse fijado, y con el batching
  de React 19 el banner nunca se renderizaba. Se elimina `resetForm()`, tras
  crear solo se hace `setForm({ ...EMPTY_FORM })`; `created` guarda ahora
  `{ id, productName, quantity }` para un mensaje en inglés y amigable
  ("Inbound order #<id> created successfully." + "N units of <producto> added
  to stock."); `updateField` oculta el banner al editar. Verificado 70/70.
- `components/inventory/index.ts`: barrel ampliado con `InboundFormPanel`.
- Verificación: `npm test` → **70/70 tests frontend**; ESLint limpio en los
  archivos nuevos; `npx tsc --noEmit` sin errores. Errores preexistentes de
  lint en `hooks/useRecord.ts`/`hooks/useRecords.ts` ajenos a esta fase.
- Documentado (sección "Fase 3 del frontend" en
  `docs/aprendiendo-gestion-inventario-orm-doble-bbdd.md`). Sin commit/push;
  se esperaba confirmación para la Fase 4.

### Frontend de inventario — Fase 4: formulario de salida (outbound)

- `app/inventory/orders/outbound/page.tsx`: server component análogo al de
  inbound (lee `searchParams.product`, string o array, pasa `initialProductId`).
- `components/inventory/OutboundFormPanel.tsx` (cliente): select de producto
  con `listProducts(nexovaApi)` al montar (placeholder por estado, disabled sin
  productos, preselección `?product={id}`); campos `quantity` (min 1),
  `exit_type` (Allocation/Consumption), `office` y `assigned_to` (visible y
  requerido solo en Allocation; al pasar a Consumption se limpia).
- **Stock disponible antes de enviar**: panel "Available stock for X: N units"
  coloreado por nivel (verde/ámbar/rojo, umbrales de Fase 2).
- **Aviso en cliente de stock insuficiente**: si `quantity > current_stock`,
  advertencia roja "Only N units available… Reduce the quantity" y botón
  deshabilitado; `submit` no llama a la API (doble salvaguarda; el backend 400
  "Insufficient stock" queda como red de seguridad).
- **Envío**: `createOutbound(nexovaApi, payload)`; `assigned_to` → null en
  consumption, texto recortado en allocation; estados saving/error/created
  (banner verde en inglés: "Outbound order #ID created successfully." + "N
  units of <producto> removed from stock [and allocated/consumed.]"), reset de
  campos sin borrar el banner (patrón corregido en Fase 3).
- `components/inventory/index.ts`: barrel ampliado con `OutboundFormPanel`.
- Verificación: `npm test` → **70/70 tests frontend**; ESLint limpio en los
  archivos nuevos; `npx tsc --noEmit` sin errores. Errores preexistentes de
  lint en `hooks/useRecord.ts`/`hooks/useRecords.ts` ajenos a esta fase.
- Documentado (sección "Fase 4 del frontend" en
  `docs/aprendiendo-gestion-inventario-orm-doble-bbdd.md`). Sin commit/push;
  se espera confirmación para la Fase 5.

### Frontend de inventario — Fase 5: historial de órdenes (read-only)

Vista `/inventory/orders` que lista todos los movimientos de entrada y salida,
la más reciente primero, con **nombre del producto** y **creador abreviado**.

- `app/inventory/orders/page.tsx`: server component sin `searchParams` que
  renderiza el panel.
- `components/inventory/OrdersHistoryPanel.tsx` (cliente): carga en paralelo
  `listOrders(nexovaApi)` + `listProducts(nexovaApi)` (Promise.all), construye
  el mapa `asset_id → name` y pinta tarjetas read-only.
- **Decisión sobre el creador (consultada con el usuario):** la API no expone
  `user_uuid → nombre` (GET /api/users no incluye `user_uuid`, el JWT solo
  lleva `sub` numérico + `credentials_version`, `/profiles/me` es solo el
  propio). Se muestra el `user_uuid` abreviado (`a1b2c3d4…`) en mono con la
  etiqueta clara **"Created by"** delante y `title="User ${user_uuid}"` para
  ver el UUID completo. El **nombre** del usuario quedó **fuera de alcance por
  decisión explícita** (el nombre legible vive en `Profile.name` ligado a
  `user_id`; sin backend no se resuelve). Si se quiere el nombre real habrá
  que ampliar el backend (exponer `user_uuid` en `/api/users` o resolver el
  creador en `list_inventory_orders` devolviendo `email`/`name`) — fuera del
  alcance frontend.
- **Cada tarjeta**: badge Inbound (verde) / Outbound (ámbar), nombre del
  producto (o `Product #<asset_id>` si no existe en el catálogo), `#id` mono,
  cantidad con plural; detalle por tipo (entry: Supplier + Office; exit: Type +
  Office + Assigned to si aplica); columna derecha con creador abreviado y
  fecha `toLocaleString`. Sin acciones (read-only). Orden: la API ya devuelve
  `ORDER BY created_at DESC`.
- `components/inventory/index.ts`: barrel ampliado con `OrdersHistoryPanel`.
- `listOrders` ya existía y estaba cubierto desde la Fase 1 ("lists the
  discriminated union of movement orders"); no se añadieron funciones nuevas
  al data-layer.
- Verificación: `npm test` → **70/70 tests frontend**; ESLint limpio en
  `OrdersHistoryPanel.tsx`, `app/inventory/orders/page.tsx` y el barrel;
  `npx tsc --noEmit` sin errores; `git diff --check` limpio. Errores
  preexistentes de lint en `hooks/useRecord.ts`/`hooks/useRecords.ts` ajenos.
- Documentado (sección "Fase 5 del frontend" en
  `docs/aprendiendo-gestion-inventario-orm-doble-bbdd.md`). Sin commit/push;
  se espera confirmación del usuario.

### Gestión de inventario — cierre de `feature/inventory-orm-dual-database`

Estado final documentado de la funcionalidad de inventario ORM con doble base
de datos. `services/api/app/inventory/seed.py` es un comando manual, no forma
parte del startup. Requiere `--environment development|test`, un `DATABASE_URL`
que pase el guard del entorno/destino y `NEXOVA_INVENTORY_SEED_USER_EMAIL` que
resuelva una cuenta única y activa con `user_uuid` válido ya persistido en la
TinyDB elegida por `AUTH_DB_PATH` o su ruta por defecto. La resolución abre
TinyDB en solo lectura mediante `app.auth.database.get_database_path()`; no
genera UUID, no usa el ID de documento y no imprime PII ni URL.

La persistencia se mantiene separada: TinyDB contiene auth y otros dominios
existentes; PostgreSQL/Supabase es el almacén de inventario. Los modelos
SQLModel son `Asset`, `AssetEntry`, `AssetExit`; el stock se calcula como suma
de entradas menos salidas y no se persiste. El seed carga 6 activos, 4 entradas
y 3 salidas. La comprobación final fue reportada por el usuario: el seed se
ejecutó correctamente en Supabase y `GET /api/inventory/products` devolvió los
seis productos con `current_stock`. No se repitió la carga en este cierre.

El guard solo permite Supabase para el destino de desarrollo explícitamente
autorizado por código; contempla el nombre estándar `postgres` y rechaza
Supabase para tests. Otros destinos PostgreSQL/SQLite deben identificar el
entorno mediante sufijo y SQLite en memoria se limita a `test`. El seed solo
inserta, aborta ante conflicto/stock negativo, deduplica por identidad natural
incluido el UUID y usa advisory transaction lock en PostgreSQL. Mantener estas
barreras; nunca usar Supabase como DB de pruebas.

Verificación final desde `services/api`: `uv run pytest` → **374 passed, 0
failed, 1 skipped**. El skip corresponde a la prueba opcional de concurrencia
PostgreSQL; SQLite no prueba `FOR UPDATE`, advisory locks o aislamiento real de
PostgreSQL. No se modificó código durante la validación final.

**Advertencia a futuros agentes:** antes de cambiar TinyDB o ejecutar cualquier
seed, consultar `memory-bank/techContext.md`, `memory-bank/progress.md` y la
documentación específica; comprobar las rutas efectivas y variables reales del
proceso, y preservar datos existentes. No crear endpoints temporales, editar
registros directamente ni desactivar las protecciones si existe un flujo
normal, autorizado y seguro. No leer, copiar o registrar secretos, UUID reales
ni emails personales en documentación.

Documentación de aprendizaje: `docs/aprendiendo-gestion-inventario-orm-doble-bbdd.md`.
Hechos verificados en código y tests se distinguen allí de la carga remota y la
comprobación API confirmadas por el usuario. Quedan pendientes la prueba real
de concurrencia PostgreSQL en una DB desechable, las migraciones/aprovisionamiento
formal y decisiones funcionales sobre stock por oficina/filtros/paginación y
un eventual backfill aprobado para usuarios históricos sin UUID.

### Gestión de inventario — Fase 6: integración y regresión

Revisada la integración del router `/api/inventory` con `main.py`, sesiones
SQLModel, auth TinyDB/JWT, UUID legacy, schemas, modelos, consultas y escrituras.
Confirmados los seis endpoints (listado/detalle de productos, orders
discriminadas `entry | exit`, creación de producto, inbound y outbound), el
stock derivado y respuestas de error esperadas. La suite completa de backend
se ejecutó desde `services/api` con `uv` y bases TinyDB temporales:
`uv run pytest tests -q --tb=short` → **358 passed, 1 skipped, 49 subtests
passed**. El skip es el test de concurrencia PostgreSQL; no se configuró ni
usó una base PostgreSQL. No se encontraron regresiones en esta ejecución.

SQLite verificó flujo HTTP, autenticación, validación, stock y rollback; no
certifica `FOR UPDATE`, `READ COMMITTED` ni concurrencia PostgreSQL. El usuario
antiguo sin UUID conserva JWT/lecturas y recibe 428 para escrituras de
movimientos, sin mutación. `git diff --check` pasó. No se leyó `.env`, no se
accedió a Supabase/BD real ni se ejecutaron seeds o migraciones.

### Gestión de inventario — Fase 5: escrituras y operaciones

Implementados `POST /api/inventory/products`, `/orders/inbound` y
`/orders/outbound`, con schemas estrictos, responses HTTP tipadas, controles de
integridad y transacciones SQLModel. El stock sigue derivado de movimientos.
Las salidas rechazan stock insuficiente con 400. En PostgreSQL se bloquea la
fila del activo con `SELECT FOR UPDATE` antes de calcular disponibilidad, para
serializar salidas del mismo activo sin mantener un contador redundante.

Los movimientos se atribuyen al `user_uuid` del contexto JWT; nunca se acepta
del payload. Usuarios históricos sin UUID pueden leer y crear productos, pero
reciben 428 al intentar escribir movimientos. No hay backfill implícito. La
prueba PostgreSQL concurrente está implementada pero opcional; SQLite no
certifica `FOR UPDATE`.

Verificación desde `services/api`: `uv run pytest tests/test_inventory_api.py
tests/test_inventory_models.py tests/test_inventory_database.py -q --tb=short`:
**24 passed, 1 skipped, 16 subtests passed**. El único skip es la prueba real de
concurrencia, por no haber URL a una base PostgreSQL de test. Se documentan los
detalles y límites en `docs/aprendiendo-gestion-inventario-orm-doble-bbdd.md`.
No se accedió a Supabase ni a `.env`; no se ejecutaron migraciones, commits o
pushes.

### Gestión de inventario — Fase 4: consultas y endpoints de lectura

Implementados `GET /api/inventory/products`, `GET
/api/inventory/products/{asset_id}` y `GET /api/inventory/orders`, todos
protegidos por `get_current_user` sin nuevos roles. El stock se calcula como
entradas menos salidas: las sumas se agrupan por activo antes del join para
evitar multiplicar cantidades cuando hay varios movimientos de ambos tipos.
Orders combina movimientos en respuesta discriminada `type: entry|exit` y
conserva `supplier` o `exit_type`/`assigned_to` según corresponda.

Las pruebas HTTP usan SQLite temporal y sustituyen tanto la sesión como el
usuario; cubren stock con varios movimientos, cero sin movimientos, lista y
detalle, 404, discriminadores y 401. Verificación conjunta con modelos e
infraestructura: `uv run pytest tests/test_inventory_api.py
tests/test_inventory_models.py tests/test_inventory_database.py -q --tb=short`
desde `services/api`: **15 passed, 8 subtests passed**. Filtros y paginación no se implementaron
porque siguen sin contrato. El stock se agrega globalmente por activo, sin
desglose por oficina; confirmar si se necesita stock por oficina. No se conectó
a PostgreSQL/Supabase, no se leyó `.env` y no se instalaron dependencias.

### Gestión de inventario — Fase 3: modelos y esquemas

Añadidos los modelos SQLModel `Asset`, `AssetEntry` y `AssetExit`, con SKU
único, FK y relaciones, timestamps UTC, UUID obligatorio en movimientos,
cantidades positivas y reglas de tipo de salida/asignación. Los schemas HTTP
separan creación y respuesta; `current_stock` está únicamente en una respuesta
que recibirá el valor calculado en una fase posterior. No se añadieron rutas,
repositorios, lógica operativa de stock, seeds ni migraciones.

Verificación: tests de modelos y de infraestructura **11 passed, 5 subtests
passed**, usando SQLite temporal. No se conectó a PostgreSQL/Supabase, no se
leyó `.env` ni se alteraron datos reales. El enunciado disponible no resuelve
si `quantity` debe ser entero o decimal; se dejó como `float` provisional y la
duda quedó documentada en `docs/aprendiendo-gestion-inventario-orm-doble-bbdd.md`.

### Gestor centralizado de incidencias — carga histórica desde CSV

Corregido `scripts/seed_incidents.py` para validar los conteos de calidad sobre
las filas importables del CSV, sin exigir que el total global de TinyDB sea 96.
El resultado distingue `total` de registros válidos del CSV y
`database_total` de registros persistidos, por lo que las incidencias manuales
no se consideran errores.

La base efectiva compartida por API y seed es `services/data/incidents.json`.
La carga real preservó la incidencia manual ID 1, importó 96 registros válidos
y creó 96 claves en `incident_seed_keys`, dejando 97 incidencias en total. Una
segunda ejecución insertó 0 registros y mantuvo el total en 97. `GET
/api/incidents` devolvió 97 registros incluyendo la incidencia manual y los
ejemplos históricos.

Verificación: tests focalizados de seed y gestor API **12/12 correctos**; CSV
con 100 filas, 96 válidas, cuatro descartadas y conteos esperados por estado y
categoría. No se eliminó ni reinició la base, no se instalaron dependencias y
no se creó commit.

### Actualización posterior — rate limit de password reset

El contrato se fijó en **3 solicitudes por dirección de email durante una hora**.
La implementación y los dos tests del rate limit quedaron alineados con ese
contrato, manteniendo el contador independiente por email y la expiración de la
ventana.

La suite backend completa pasa **279/279 tests**. La validación visual/E2E y la
comprobación contra servicios desplegados reales siguen pendientes; no se han
declarado como realizadas.

## 1. Estado general

El proyecto Nexova se encuentra en una fase de construcción progresiva de su ecosistema digital y de AI Engineering.

Ya existe una base de aplicaciones y documentación, y se está incorporando una estructura persistente para que los agentes de desarrollo puedan trabajar de forma consistente sobre el monorepo.

---

## 2. Completado

### Error-handling-audit — Fase 1 backend

Reforzada la gestión de errores y el diagnóstico seguro en autenticación:

- El adaptador Resend usa `logging` con dominio del destinatario, tipo de fallo
  y estado HTTP, sin emails completos, tokens ni cuerpos de respuesta.
- La creación de perfiles usa `ProfilePersistenceError`; el registro de usuario
  conserva la compensación y registra de forma segura los fallos del rollback.
- Las respuestas de error mantienen los códigos y contratos existentes.

Verificación: 46 tests de email/repositorios y 66 tests HTTP de usuarios,
perfiles y autenticación focalizada pasan. La suite ampliada de auth ejecuta
193 tests: 191 pasan y 2 fallan en el rate limit de password reset, un fallo
preexistente y ajeno a estos archivos. No se modificaron scripts Python ni el
frontend.

### Error-handling-audit — Fase 2 scripts y CSV

Implementado el tratamiento controlado de errores en el lector CSV y el seed de
incidencias. El parser usa modo estricto y convierte `csv.Error` en
`CsvReadError` con número de fila; los estados desconocidos generan
`INVALID_STATUS` sin `ValueError` inesperado. El seed prepara todas las filas
antes de abrir la base y devuelve código no cero por `stderr` ante errores
esperables, sin afirmar rollback transaccional de TinyDB.

Verificación: slice de lector, validación, análisis, exportación, CLI, API y
seed con 41 tests correctos; validación compartida con 2 tests correctos; seed
aislado con 96 inserciones en la primera ejecución y 0 en la segunda. La suite
backend completa ejecuta 266 tests: 264 correctos y 2 fallan en los tests
preexistentes de rate limit de password reset. `analyze.py`, exportación,
frontend, autenticación y rate limiting no se modificaron.

### Error-handling-audit — Fase 3 clientes API del frontend

Reforzados los clientes API de `uis/backoffice/talent-pipeline-tracker` sin
modificar componentes visuales. Se añadió `lib/api-errors.ts` para clasificar
errores HTTP, red, timeout, parseo y cancelación, interpretar formatos de error
conocidos y redactar emails, tokens, URLs y rutas internas.

`lib/api.ts`, `lib/nexova-api.ts` y `lib/incident-analysis-api.ts` ahora
gestionan cuerpos JSON, texto plano, respuestas vacías, JSON inválido, timeout
configurable y cancelación externa. La exportación conserva el tipo `Blob` y
los clientes existentes mantienen sus firmas de éxito.

Verificación: tests nuevos de Tracker e Incident Analysis **9/9**, tests de
Nexova **24/24**, suite frontend completa **56/56**, TypeScript correcto y build
correcto. El lint mantiene 3 errores y 5 warnings preexistentes en archivos del
Tracker no relacionados con esta fase. Los componentes visuales y los clientes
de negocio que delegan en Nexova no se modificaron; la traducción uniforme de
mensajes en esos consumidores queda pendiente para la siguiente fase.

### Error-handling-audit — Fase 4 consumidores frontend y validación integrada

Añadido `lib/api-error-messages.ts` para centralizar mensajes seguros en los
consumidores genéricos. Los hooks de candidaturas y notas, perfil, Supplier
Directory e Incident Analysis ya no propagan directamente `error.message`.
Mantienen sus fallbacks contextuales y dejan intactas las traducciones
específicas de autenticación, password reset e Incident Manager.

Las cancelaciones esperadas devuelven `null` y no generan mensajes visibles;
red, timeout y errores HTTP siguen distinguiéndose internamente. Se añadieron
2 pruebas focalizadas para el traductor común.

La Fase 4 queda verificada con la suite frontend
completa **58/58**, TypeScript
y build correctos, y `git diff --check` correcto. El lint mantiene 3 errores y
5 warnings preexistentes. No se modificaron backend, rate limiting, CSV,
seeders ni se creó commit.

### Error-handling-audit — Fase 5 validación integrada y cierre

Se ejecutaron primero los slices focalizados sobre bases TinyDB temporales:
auth/email/perfiles/password reset **127 tests, 125 correctos y 2 fallos** del
rate limit conocido; CSV/validación/análisis/exportación/CLI/seed **36/36**; API
HTTP/Incident Manager/Supplier/CORS **36/36**; y frontend **58/58**.

La suite backend completa ejecutó **267 tests: 265 correctos y 2 fallos**, los
mismos asserts del rate limit. La suite frontend completa quedó en **58/58**.
TypeScript, build de Next.js y `git diff --check` pasaron. Lint mantiene 3
errores y 5 warnings preexistentes. FastAPI emitió únicamente el warning de
deprecación sobre `httpx`/`TestClient`.

El fixture `scripts/incidents-nexova.csv` estuvo presente durante la validación
y tenía 101 líneas. No se ejecutaron seeders contra datos reales, no se
instalaron dependencias y no se creó commit. No existen Error Boundaries
globales en el Tracker y no hay navegador/runner E2E disponible, por lo que la
validación visual queda pendiente.

Los riesgos residuales son el contrato no resuelto del rate limit, la falta de
atomicidad multioperación de TinyDB, la ausencia de Error Boundary global y la
falta de verificación contra servicios desplegados reales. La matriz completa
de hallazgos y recomendaciones está en `docs/aprendiendo-gestion-errores.md`.

### Error Boundaries globales de Next.js — corrección posterior a la Fase 5

Implementados `app/error.tsx` y `app/global-error.tsx` en
`uis/backoffice/talent-pipeline-tracker`. Ambos son Client Components
compatibles con Next.js 16.3.3 y App Router. Muestran mensajes genéricos en
español, permiten reintentar mediante `reset()` y ofrecen navegación a `/` sin
exponer mensajes de error, trazas ni datos internos. El registro técnico se
limita al identificador `error.digest` cuando está disponible.

No se modificaron `AuthProvider`, `AuthShell`, autenticación, logout, clientes
API, backend ni dependencias. La suite frontend ejecuta **58/58 tests
correctos**, TypeScript y el build de Next.js pasan, y `git diff --check` es
correcto. No se realizó validación visual en navegador; esa comprobación queda
pendiente.

### Password reset — Fase 1 backend

Implementado el flujo backend de recuperación y cambio de contraseña bajo el
dominio de auth existente:

  expiración y uso único en una tabla TinyDB separada.
  real ni se han enviado emails.

### Contexto y documentación

  - `memory-bank/projectbrief.md`
  - `memory-bank/techContext.md`
  - `memory-bank/progress.md`

### Web corporativa

La web pública de Nexova está desarrollada e incluye:


### Talent Pipeline Tracker

La aplicación está ubicada actualmente en:

`uis/talent-pipeline-tracker/`

Funcionalidades implementadas y verificadas:


### Arquitectura técnica verificada

Se ha revisado y confirmado la existencia y funcionamiento previsto de:


### Autenticación del backoffice — AUTH-02, fase 2

Implementada la infraestructura frontend de cliente Nexova y sesión JWT en
`uis/backoffice/talent-pipeline-tracker`:

  de sesión mediante `/auth/me`, cierre local e invalidación ante `401`;
  inyectados para tests y evitando invocarlo con receptor incorrecto;
  permanecen separados;

Esta fase no añade pantallas de autenticación ni protección global de rutas.
Verificación: 12 tests, TypeScript, lint focalizado y build pasan. El lint global
sigue reportando errores React preexistentes en `app/page.tsx`,
`hooks/useRecord.ts` y `hooks/useRecords.ts`.

### Autenticación del backoffice — AUTH-02, fase 3

Implementadas las rutas `/login` y `/register` con un formulario compartido,
validación en español, estados de envío, prevención de peticiones duplicadas y
controles accesibles. El login envía el formulario OAuth2 esperado, guarda el
JWT mediante el cliente compartido, valida `/auth/me` y redirige a `/`; el
registro envía únicamente email y contraseña, y ofrece continuar al login sin
crear sesión. No se añadieron guards ni se protegieron rutas existentes.

Verificación: 21 tests frontend, 64 tests backend de auth, TypeScript, lint
focalizado, build y comprobación HTTP SSR completados. El lint global sigue
fallando solo por los tres errores React preexistentes indicados en fase 2.

### Autenticación del backoffice — fases 4 y 5

La fase 4 se considera verificada por el usuario: registro, login, perfil,
Supplier Directory, Incident Analysis, menú `My Profile` y logout funcional.

En fase 5 se revisaron el proveedor, almacenamiento/token, cliente, logout,
layout, rutas y requisitos backend. Ya existía `AuthShell`: protege
`/suppliers` y `/account/profile` y sus subrutas; login/registro son públicos.
Tracker e Incident Analysis mantienen sus clientes separados y acceso público.
Se reutilizó este guard, sin crear middleware ni otro `PrivateRoute`.

Se reprodujo y corrigió una carrera: una respuesta pendiente de `/auth/me`
podía restaurar `authenticated` después del logout. El cliente ahora descarta
resultados obsoletos y evita que un `401` anterior invalide una sesión nueva.
Se mantiene la expiración existente por `401` y el reintento ante errores de
red/servidor, que bloquean contenido sin eliminar el token.

Verificación: 34 tests frontend, TypeScript, lint focalizado, build de Next y
`git diff --check` pasan. Persiste el aviso de múltiples lockfiles. Chromium
completó 18 escenarios en escritorio (1440px) y móvil (390px), con API simulada
y peticiones externas bloqueadas: acceso privado sin sesión, login/registro,
acceso autenticado a perfil/proveedores, logout y reentrada denegada, token
rechazado por `401` y validación fallida por red/503. Se revisaron capturas.
No equivale a un nuevo E2E contra la API real. Las herramientas de navegador
se instalaron temporalmente fuera del repo; no se añadieron dependencias.
No se modificó backend ni `services/data/`, ni se ejecutaron seeders,
commits o push.

### Password reset — Fase 2 frontend

Implementadas las pantallas `/forgot-password`, `/reset-password` y
`/account/change-password` en `uis/backoffice/talent-pipeline-tracker`.
El token de recuperación se lee desde `searchParams` y no se guarda en
localStorage ni en `AuthProvider`. Las peticiones públicas no envían Bearer;
el cambio de contraseña reutiliza el cliente autenticado y cierra la sesión
local tras completarse, porque el backend invalida el JWT.

Se añadió `PasswordResetForm` con validación, mensajes genéricos, estados de
éxito/error y prevención de envíos concurrentes. `/account/change-password`
queda protegido por el `AuthShell` existente y el login incluye el enlace de
recuperación.

Verificación realizada: 41 tests frontend, `npx tsc --noEmit`. Pendientes de
ejecutar en esta fase: lint y build. No se modificó backend, `services/data/`,
`uis/website`, ni se creó commit o push.

### Password reset — Fase 3 seguridad

Auditado y reforzado el flujo completo de password reset. `forgot-password`
mantiene respuestas homogéneas para cuentas existentes, inexistentes e
inactivas. Los tokens usan fuente criptográficamente segura, solo se persiste
su hash, tienen expiración, uso único y rotación; la rotación y el consumo
quedan protegidos por locks de proceso. La actualización de contraseña también
serializa el incremento de `credentials_version`.

El frontend redirige a `/login?reset=1` tras un reset correcto, eliminando el
token de la URL mediante una ruta fija. No se introdujeron almacenamientos,
logs ni redirects controlados por el usuario. Resend sigue siendo backend-only,
CORS continúa usando origins explícitos y bcrypt no se ha sustituido.

Verificación focalizada: 11 tests backend de password reset correctos. La
limitación de TinyDB multi-worker queda documentada: los locks solo coordinan
un proceso y no sustituyen una base de datos transaccional distribuida.

### Password reset — Fase 4 extensiones opcionales

Implementadas las tres extensiones no evaluables: plantilla HTML sencilla para
el email mediante `EmailSender`, rate limiting de 3 solicitudes por email en
una ventana de una hora y auditoría TinyDB de solicitudes/resultados con
timestamp, IP, email cuando procede y tipo de evento. No se guardan secretos,
contraseñas, tokens ni JWT. Los tests usan `FakeEmailSender`; Resend no se ha
activado ni modificado operativamente.

### Fase 6 — Auditoría final previa a la entrega

La auditoría histórica ejecutó 222 tests backend, con 212 correctos; los fallos
restantes se atribuyeron entonces a un fixture ausente,
`scripts/incidents-nexova.csv`, que no estaba disponible en aquella ejecución.
En la validación integrada actual el fixture está presente y la suite backend
ejecuta 267 tests, con 265 correctos y solo los 2 fallos conocidos de rate
limit. Auth, perfiles, CORS, Supplier Directory, CSV, análisis y seed pasan en
los slices cubiertos.
La suite se ejecutó sobre una copia aislada en `/tmp` porque
`AuthSemanticTests`/`IncidentsPublicTests` abren la BD por defecto.

Frontend: 34 tests, TypeScript, build y los 18 escenarios de navegador pasan.
El lint global mantiene 3 errores y 5 avisos preexistentes de React en
`app/page.tsx`, `hooks/useRecord.ts`, `hooks/useRecords.ts` y dos componentes
del Tracker; ningún archivo de autenticación aparece afectado.

Hallazgo de seguridad corregido: `services/data/` no estaba ignorado y
`git add -A` habría subido `auth.json` (emails y hashes bcrypt) y
`suppliers.json`. Se añadió al `.gitignore` raíz junto a `.env.local.save`.
Los archivos no se leyeron ni modificaron.

Pendientes resueltos tras la auditoría: `httpx` se declara en el extra `test`
de `services/api/pyproject.toml` (y `uv.lock`); `ConfigTests`
(`test_auth_unit1`) carga una copia aislada de `config.py` y ya no depende del
orden de importación. En la validación integrada de Fase 5 el fixture CSV está
presente y los tests de datos pasan; se mantiene la recomendación de verificar
su ubicación antes de ejecutar pruebas.


## 3. Estado actual del Talent Pipeline Tracker

## Fase 1 — Gestor de Incidencias Centralizado

Implementados el dominio persistente del gestor en TinyDB, sus endpoints
CRUD/summary y la validación de transiciones de estado. El modelo del gestor es
independiente del dominio existente de Incident Analysis. También se añadió
`scripts/seed_incidents.py`, que transforma exclusivamente
`scripts/incidents-nexova.csv`, descarta las filas inválidas y controla
duplicados sin almacenar `ticket_id` en `Incident`.

Verificación de seed en base temporal: 96 inserciones iniciales, 0 inserciones
en la segunda ejecución, 4 filas descartadas (`18`, `44`, `87`, `91`), estados
`open=27`, `resolved=56`, `discarded=13` y categorías
`technical_failure=49`, `process_error=35`, `client_complaint=12`. El API del
gestor tiene 4 tests focalizados correctos. La fase frontend queda pendiente de
confirmación explícita.
confirmación explícita.

## Fase 2 — Frontend del Gestor de Incidencias

Implementado el frontend del gestor en `/incidents/manager`, manteniendo
`/incidents` para Incident Analysis. Incluye creación de incidentes, filtros por
estado/origen/sede/categoría, resumen por estado, listado y transiciones de
estado válidas. La ruta del manager queda protegida por el `AuthShell` y se
añadió al menú principal.

Se añadieron contratos TypeScript, cliente API autenticado y propagación de
errores estructurados con campo. La validación de navegación y del parser de
errores queda cubierta por la suite frontend.

Verificación: 46 tests frontend correctos, TypeScript y build de Next.js
correctos. El lint global sigue fallando únicamente por los tres errores React
preexistentes en `app/page.tsx`, `hooks/useRecord.ts` y `hooks/useRecords.ts`,
con cinco avisos preexistentes. No se modificó backend en esta fase.

## Fase 3 — Integración, documentación y validación final

El backend del Incident Manager quedó protegido con JWT Bearer mediante la
dependencia común de autenticación. Se actualizaron los tests focalizados para
cubrir `401` sin credenciales y se documentaron API, configuración CORS,
`INCIDENTS_DB_PATH`, ubicación del CSV, seed idempotente, ejecución y pruebas en
los README del servicio y del frontend.

Validación aislada del seed: 96 inserciones en la primera ejecución, 0 en la
segunda, con TinyDB temporal. La suite focalizada del manager pasa: 5 tests.
La suite backend completa ejecuta 253 tests: 251 pasan y 2 fallan únicamente en
los tests ajenos de rate-limit de password reset, debido al cambio existente en
`services/api/app/auth/password_reset.py` que no se modificó.

Frontend: 46 tests, TypeScript y build pasan. El lint global conserva los tres
errores y cinco avisos preexistentes del Tracker. `git diff --check` pasa.

La API se reinició en `localhost:8000` con `CORS_ORIGINS` explícito para
localhost y `https://friendly-barnacle-qv5p44r9rxq2644j-3000.app.github.dev`,
además de TinyDB temporales. Se comprobó el preflight HTTPS (`200`), el login
válido (`200` con CORS), el login inválido (`401` con CORS) y el manager sin
token (`401`). El default de `app/main.py` también deriva el origen exacto de
Codespaces desde `CODESPACE_NAME`, sin permitir wildcard. La navegación vuelve a
mostrar Login, registro y recuperación mientras no hay sesión validada, y
mantiene perfil/cambio de contraseña para sesiones autenticadas.

La suite focalizada de CORS, auth y manager pasa: 75 tests. Frontend: 46 tests,
TypeScript y build pasan. Los dos fallos de password reset y los tres errores de
ESLint del Tracker siguen siendo preexistentes y ajenos; no se modificó
`services/api/app/auth/password_reset.py`.

La validación visual interactiva en navegador no se realizó porque no hay una
herramienta de navegador automatizado disponible en este entorno. Para la
revisión manual, abrir `http://localhost:3000/login`, iniciar sesión con un
usuario válido y comprobar `/incidents/manager` en escritorio y móvil; verificar
también que `/incidents` continúa mostrando Incident Analysis.

### Header responsive del backoffice

`AuthShell` ahora ofrece navegación horizontal con dropdowns accesibles para
Incidents y Account/Profile en escritorio, y un menú hamburguesa compacto en
móvil. Los menús se cierran al seleccionar un enlace, pulsar Escape, hacer
click fuera o cerrar sesión; se mantienen las rutas existentes, el guard de
autenticación y el logout compartido.

Verificación: 46 tests frontend, TypeScript y build pasan; `git diff --check`
también pasa. El lint global mantiene los 3 errores y 5 avisos preexistentes
del Tracker. No se realizó validación visual automatizada en navegador.

El Talent Pipeline Tracker dispone actualmente de una estructura funcional completa para el caso de uso de gestión de candidaturas.

La arquitectura conocida es:

`app → components → hooks → lib → API`

La aplicación utiliza la API de 4Geeks:

`https://playground.4geeks.com/tracker/api/v1`

El frontend está construido con:

- Next.js 16.3.3
- React 19.2.8
- TypeScript 5
- Tailwind CSS 4

La aplicación está ubicada actualmente en `uis/backoffice/talent-pipeline-tracker`, siguiendo la estructura definida para las aplicaciones internas de Nexova. La web pública existente está organizada en `uis/website`.

- Validación final: `npm run build` ejecutado desde `uis/backoffice/talent-pipeline-tracker` correctamente. Next.js compiló TypeScript y generó todas las rutas sin errores. Se mantiene únicamente el warning sobre múltiples `package-lock.json`.
- Validación visual: comprobadas correctamente la website pública y el backoffice mediante las previsualizaciones de Codespaces.
---

## 4. Hallazgos y pendientes confirmados

- La ruta predeterminada de Supplier es `services/data/suppliers.json`; no se
  detectó override en el entorno inspeccionado y el archivo existe con 15
  entradas. Esto no demuestra qué ruta usó un proceso histórico ni por qué se
  observó `[]` anteriormente.
- Sin token, Supplier responde `401 Not authenticated`; con token inválido,
  `401 Invalid credentials`. El registro no inicia sesión automáticamente.
- En la validación de Fase 5 `scripts/incidents-nexova.csv` está presente y
  contiene 101 líneas; el slice de CSV, análisis, exportación, CLI y seed pasa
  36/36. La ubicación efectiva debe seguir verificándose antes de ejecutar
  procesos en otros entornos.
- La causa exacta de los errores de hidratación observados no está confirmada.
  La solución actual evita renderizar el formulario antes de hidratar, pero se
  debe completar la validación de login/registro en Chrome.
- El README de `services/api` estaba desactualizado respecto a Supplier y se
  sincronizó con la implementación actual.

## 5. Siguiente trabajo

1. Validar manualmente login, registro, persistencia de sesión y acceso a
   Supplier Directory en Chrome con API/base URL y CORS correctos.
2. Confirmar la disponibilidad y ubicación esperada del CSV de pruebas de
   Incident Analysis.
3. Si reaparece una respuesta vacía de Supplier, registrar URL/base efectiva,
   estado HTTP, presencia/validez del token (nunca su valor) y ruta DB del
   proceso antes de atribuir una causa.

No se ejecutaron tests, seeders ni scripts de análisis durante esta actualización
documental para evitar efectos sobre datos locales.

---

## 7. Criterio para actualizar este archivo

Este archivo debe actualizarse cuando cambie de forma relevante el estado del proyecto.

Registrar:

- nuevas funcionalidades completadas;
- nuevas aplicaciones;
- cambios importantes de arquitectura;
- decisiones técnicas relevantes;
- tareas importantes pendientes;
- problemas relevantes encontrados y resueltos.

No registrar aquí cada pequeño cambio de código.

El objetivo es que un agente pueda leer este archivo y entender rápidamente dónde está el proyecto y cuál es el siguiente trabajo pendiente.
