# Technical Context — Nexova

## 1. Arquitectura general

Nexova utiliza un monorepo para centralizar las diferentes aplicaciones, servicios, recursos de datos y capacidades de IA del proyecto.

Principales áreas:

- `uis/` → aplicaciones frontend.
- `services/` → APIs y servicios backend.
- `data/` → datos y pipelines.
- `agents/` → agentes de IA de producto.
- `skills/` → skills de producto.
- `mcps/` → integraciones MCP.
- `packages/` → paquetes reutilizables.
- `shared/` → recursos compartidos.
- `infra/` → infraestructura.
- `scripts/` → scripts auxiliares.
- `internal/` → recursos internos.
- `docs/` → documentación.
- `memory-bank/` → contexto persistente para agentes de desarrollo.

`.agents/` es diferente de `/agents` y `/skills`.

- `.agents/` → configuración, reglas y skills para los agentes de desarrollo.
- `/agents` → agentes que forman parte del producto Nexova.
- `/skills` → skills que forman parte del producto Nexova.

---

## 2. Organización de aplicaciones

Según las convenciones del monorepo:

- `uis/website` → presencia web pública de Nexova.
- `uis/backoffice` → aplicaciones internas de administración y operaciones.
- `services/` → servicios backend y APIs.

Cada aplicación o servicio debe mantener su propia documentación técnica y funcional.

---

## 3. Talent Pipeline Tracker

La aplicación Talent Pipeline Tracker está actualmente ubicada en:

`uis/backoffice/talent-pipeline-tracker/`

Es una aplicación frontend construida con:

- Next.js `16.3.3`
- React `19.2.8`
- React DOM `19.2.8`
- TypeScript `5`
- Tailwind CSS `4`
- ESLint `9`

Scripts disponibles:

- `npm run dev`
- `npm run build`
- `npm run start`
- `npm run lint`

La aplicación dispone de instrucciones específicas en:

`uis/backoffice/talent-pipeline-tracker/AGENTS.md`

y contexto funcional en:

`uis/backoffice/talent-pipeline-tracker/context.md`

Antes de modificar esta aplicación deben consultarse ambos archivos.

---

## 4. Estructura interna del Talent Pipeline Tracker

La aplicación está organizada principalmente en:

### `app/`

Rutas y páginas de Next.js.

Rutas actualmente conocidas:

- `/` → listado de candidaturas.
- `/new` → creación de una candidatura.
- `/candidates/[id]` → detalle de una candidatura.

### `components/`

Componentes de interfaz agrupados por funcionalidad:

- `candidates/`
- `filters/`
- `notes/`
- `ui/`

### `hooks/`

Lógica de acceso y gestión de datos en cliente:

- `useRecords`
- `useRecord`
- `useNotes`

### `lib/`

Comunicación con la API:

- `api.ts`
- `records.ts`
- `notes.ts`

### `types/`

Contratos TypeScript.

### `constants/`

Estados, etapas, etiquetas y opciones utilizadas por la interfaz.

---

## 5. API

El Talent Pipeline Tracker utiliza actualmente:

`https://playground.4geeks.com/tracker/api/v1`

La comunicación se centraliza mediante:

`lib/api.ts`

No duplicar la lógica de comunicación HTTP en los componentes.

---

## 6. API de candidaturas

`lib/records.ts` contiene:

- `getRecords`
- `getRecordById`
- `createRecord`
- `patchRecord`
- `replaceRecord`
- `deleteRecord`

Endpoints:

- `GET /records`
- `GET /records/{id}`
- `POST /records`
- `PATCH /records/{id}`
- `PUT /records/{id}`
- `DELETE /records/{id}`

---

## 7. API de notas

`lib/notes.ts` contiene:

- `getNotes`
- `addNote`
- `deleteNote`

Endpoints:

- `GET /records/{id}/notes`
- `POST /records/{id}/notes`
- `DELETE /records/{id}/notes/{noteId}`

---

## 8. Modelo de datos

### Candidatura

`RecordOut` contiene:

- `id`
- `full_name`
- `email`
- `phone`
- `position`
- `linkedin_url`
- `cv_url`
- `status`
- `stage`
- `experience_years`
- `notes_count`
- `applied_at`
- `updated_at`
- `notes`

### Creación

`RecordCreate` requiere:

- `full_name`
- `email`
- `phone`
- `position`
- `experience_years`

Y permite opcionalmente:

- `linkedin_url`
- `cv_url`

### Actualización

`RecordPatch` permite actualizar:

- `status`
- `stage`

---

## 9. Estados y etapas

La API utiliza códigos técnicos.

### Estados

- `received`
- `in_progress`
- `selected`
- `discarded`

La UI utiliza:

- `Recibida`
- `En proceso`
- `Seleccionada`
- `Descartada`

### Etapas

- `pending`
- `review`
- `personal_interview`
- `technical_interview`
- `offer_presented`

La UI utiliza:

- `Pendiente de revisión`
- `En revisión`
- `Entrevista personal`
- `Entrevista técnica`
- `Oferta presentada`

Los códigos internos de API no deben mostrarse directamente al usuario.

Las etiquetas y opciones se centralizan en:

`constants/index.ts`

---

## 10. Listado, búsqueda y filtros

El listado de candidaturas permite:

- búsqueda;
- filtro por estado;
- filtro por etapa;
- paginación.

Los parámetros utilizados por `GET /records` son:

- `status`
- `stage`
- `search`
- `page`
- `limit`

El tamaño de página por defecto es:

`20`

La búsqueda tiene un debounce aproximado de `350 ms`.

Los filtros y la paginación se gestionan mediante parámetros de URL.

---

## 11. Gestión de candidaturas

La interfaz permite:

- crear candidaturas;
- consultar candidaturas;
- actualizar estado;
- actualizar etapa;
- consultar notas;
- añadir notas;
- eliminar notas;
- eliminar candidaturas.

La creación valida los campos obligatorios antes de enviar la petición.

La eliminación de una candidatura requiere confirmación del usuario.

---

## 12. Principios técnicos

Antes de modificar código:

1. Leer el `memory-bank/context.md`.
2. Leer el contexto específico de la aplicación.
3. Leer el `AGENTS.md` aplicable.
4. Revisar la implementación existente.
5. Reutilizar tipos, hooks, servicios y componentes existentes cuando corresponda.
6. Evitar duplicar lógica.
7. No introducir dependencias innecesarias.
8. No modificar contratos de API sin comprobar sus dependencias.
9. Mantener separadas las representaciones internas de API y las etiquetas de UI.
10. Mantener los cambios limitados al alcance de la tarea.

---

## 13. Next.js

La aplicación utiliza Next.js `16.3.3`.

El `AGENTS.md` de la aplicación indica que esta versión puede contener cambios respecto a versiones anteriores.

Antes de implementar o modificar APIs específicas de Next.js:

- consultar las instrucciones de `uis/backoffice/talent-pipeline-tracker/AGENTS.md`;
- consultar la documentación local de Next.js indicada por dichas instrucciones cuando sea necesario.

No asumir comportamiento de versiones antiguas de Next.js.

---

## 14. Estado de la arquitectura

La arquitectura actual conocida del Talent Pipeline Tracker puede resumirse como:

`app → components → hooks → lib → API`

Los tipos y constantes proporcionan contratos y valores compartidos entre las distintas capas.

La arquitectura debe mantenerse coherente con esta separación de responsabilidades.

---

## 15. Configuración de agentes

La configuración de agentes de desarrollo debe mantenerse separada del código de producto.

Las reglas generales del agente se encuentran en:

`.agents/rules/`

Las skills reutilizables para el agente de desarrollo se encuentran en:

`.agents/skills/`

Las instrucciones globales del repositorio se encuentran en:

`AGENTS.md`

Estas configuraciones deben complementar, no sustituir, las instrucciones específicas de cada aplicación.

---

## 16. API Nexova: módulos y configuración

La aplicación FastAPI de `services/api` registra Incident Analysis, Supplier
Directory y las rutas de autenticación/perfiles en una sola instancia. Los
prefijos `/api` están incluidos en las rutas; la base frontend debe terminar en
`/api`, sin duplicar ese prefijo.

El cliente Nexova usa `NEXT_PUBLIC_NEXOVA_API_BASE` y, si no se configura,
`http://localhost:8000/api`. En Codespaces se debe usar el origen reenviado del
puerto 8000 más `/api`, y permitir el origen exacto del frontend en
`CORS_ORIGINS`. No usar `*`. Las variables `NEXT_PUBLIC_*` son públicas y no
deben contener secretos.

El cliente Incident Analysis es independiente (`lib/incident-analysis-api.ts`)
y usa `NEXT_PUBLIC_INCIDENT_ANALYSIS_API_BASE`, con default
`http://localhost:8000/api`. No comparte sesión ni base URL con el cliente
Nexova ni con el Tracker de 4Geeks.

## 17. Autenticación

- `POST /api/auth/login` recibe formulario OAuth2 URL-encoded con `username` igual al email y `password`.
- `POST /api/users` recibe JSON con `email` y `password`; el registro no inicia sesión. Un email duplicado devuelve `409` y una entrada inválida `422`.
- `GET /api/auth/me` valida el JWT de la sesión.
- El frontend guarda el token bajo `nexova_access_token`; el cliente solo envía `Authorization: Bearer` cuando la operación opta explícitamente por auth. Un `401` en una solicitud protegida invalida la sesión local.
- Login y registro son públicos. Supplier Directory requiere autenticación; Incident Analysis no la requiere. El registro por sí solo no habilita solicitudes protegidas.
- `AuthShell`, dentro de `AuthProvider` en el layout raíz, protege `/suppliers`, `/account/profile` y `/account/change-password`, incluidas sus subrutas. No monta contenido privado en estados `loading`, `unauthenticated` o `error`; redirige al login sin sesión y ofrece reintentar si falla la validación. Tracker e Incident Analysis siguen públicos con sus clientes separados.
- Logout reutiliza el cliente compartido y publica `unauthenticated` inmediatamente. La expiración se gestiona con `401` y `/login?expired=1`, sin un temporizador JWT adicional. Una revisión de sesión evita que validaciones o `401` tardíos de una sesión anterior restauren el acceso o invaliden una nueva sesión.
- El guard es de UI, no una barrera de autorización de la API. No hay middleware de auth; el JWT vive en localStorage y el backend valida las solicitudes protegidas.
- Auth usa TinyDB en `services/data/auth.json` por defecto o `AUTH_DB_PATH`. La serialización de registro es un lock dentro del proceso, no entre workers; el README del API documenta esa limitación.
- Password reset reutiliza el dominio `app/auth`: tokens opacos aleatorios con solo su hash en la tabla `password_reset_tokens`, expiración y consumo único. `POST /api/auth/forgot-password` responde siempre `200` con mensaje genérico.
- Los JWT incluyen `credentials_version`. Al cambiar o restablecer una contraseña se incrementa esa versión y `get_current_user` rechaza tokens anteriores; no se usa una segunda estrategia `password_changed_at`.
- El envío de recuperación depende de la interfaz `EmailSender` y su adaptador Resend. `RESEND_API_KEY` y `RESEND_FROM_EMAIL` son configuración exclusiva del backend en `services/api/.env`; los tests inyectan un fake y no contactan con Resend.
- El frontend concentra las validaciones y peticiones de password reset en `lib/password-reset.ts` y reutiliza `PasswordResetForm` para forgot, reset y change. `/reset-password` recibe el token mediante `searchParams`; no se persiste en localStorage ni en `AuthProvider`. Forgot y reset usan `auth: false`; change usa `auth: true` y cierra la sesión local después del éxito.
- La auditoría de seguridad mantiene `forgot-password` homogéneo para emails existentes, inexistentes e inactivos. El token usa `secrets.token_urlsafe(32)`, solo se almacena su SHA-256, expira, se consume una vez y se reemplaza al solicitar otro. El repositorio serializa rotación y consumo; `UserRepository.update_password` serializa el incremento de `credentials_version`.
- Tras un reset correcto el frontend usa `router.replace("/login?reset=1")`, una redirección fija que evita conservar el token en la URL. No hay redirect arbitrario ni logs de password, token, JWT o API key en el flujo auditado.
- TinyDB sigue siendo una persistencia de un solo proceso: los locks no coordinan varios workers o instancias. La operación segura multi-worker requeriría una base con transacciones/operaciones atómicas; no forma parte de esta fase.

## 18. Incident Analysis

- `POST /api/incidents/analyze` recibe un CSV en el campo multipart `file` y devuelve métricas agregadas. El cliente no debe fijar manualmente `Content-Type` para `FormData`.
- `GET /api/incidents/results/export` exporta el último resultado agregado del proceso. Antes de un análisis correcto devuelve `404`; el resultado es temporal, compartido por proceso y no persistido.
- La respuesta y la exportación no incluyen filas originales ni emails.
- No se encontró ningún CSV en el workspace, aunque las pruebas referencian `scripts/incidents-nexova.csv`. La disponibilidad de ese fixture y cualquier conclusión que dependa de sus datos quedan pendientes de confirmación.

## 19. Supplier Directory y persistencia

Supplier Directory expone `GET/POST /api/suppliers`,
`GET /api/suppliers/{id}`, `PATCH /api/suppliers/{id}/rate`,
`PATCH /api/suppliers/{id}/status` y `DELETE /api/suppliers/{id}`. Todas estas
rutas requieren JWT. Un `401` significa que falta o no es válido el token; un
array vacío, por sí solo, no demuestra un fallo del endpoint.

La base TinyDB usa `services/data/suppliers.json` por defecto o
`SUPPLIER_DIRECTORY_DB_PATH`. El seeder es explícito, idempotente por nombre y
no se ejecuta al iniciar FastAPI. Comprueba la ruta efectiva del proceso antes
de concluir que la base está vacía o de ejecutar un seed. En la inspección
actual, el archivo por defecto existe y contiene 15 proveedores; no se debe
asumir que otras instalaciones tienen los mismos datos.

## 21. Decisiones de persistencia de la Fase 4

Password reset dispone además de una plantilla HTML generada en backend, un
límite local de 3 solicitudes por email cada hora y dos tablas TinyDB auxiliares
(`password_reset_rate_limits` y `password_reset_audit_log`). La auditoría
registra timestamp, IP, email cuando procede y tipo de evento, nunca tokens ni
credenciales. Estas extensiones son opcionales y los locks solo coordinan un
proceso.

## 20. Hallazgos de diagnóstico frontend

El cliente Nexova conserva fetchers inyectados para tests y enlaza el fetch
nativo con `globalThis` (`globalThis.fetch.bind(globalThis)`). Si se cambia el
cliente, no guardar el fetch nativo sin binding y después invocarlo como método:
el receptor puede ser incorrecto en el navegador.

`AuthForm` evita comparar HTML distinto entre SSR e hidratación: el formulario
se monta en cliente después del placeholder inicial. La causa exacta de las
mutaciones de DOM observadas anteriormente no quedó demostrada; no atribuirla a
LastPass u otra extensión sin reproducción. Tests/build tampoco sustituyen la
comprobación manual del login y registro en Chrome.

## 22. Inventario ORM con persistencia dual — estado final

### Hechos comprobados en código

- Rama trabajada: `feature/inventory-orm-dual-database`. Contexto de aprendizaje
  detallado: `docs/aprendiendo-gestion-inventario-orm-doble-bbdd.md`.
- Auth continúa en TinyDB; `app.auth.database.get_database_path()` selecciona
  `AUTH_DB_PATH` o, si no está definida, `services/data/auth.json`. Inventario
  usa SQLModel/SQLAlchemy síncrono y PostgreSQL mediante `DATABASE_URL`, aislado
  en `services/api/app/inventory/database.py`. `get_engine()` es perezoso y
  `get_session()` cierra la sesión por solicitud. No hay transacción distribuida
  entre TinyDB y PostgreSQL.
- ORM: `Asset` (tabla `assets`) tiene relaciones a `AssetEntry` y `AssetExit`
  (tablas `asset_entries` y `asset_exits`) por FK `asset_id`. SKU es único;
  cantidades son positivas; salidas limitan `exit_type` a `allocation` o
  `consumption` y aplican la regla de `assigned_to`. `Asset` no almacena stock.
- `queries.py` deriva `current_stock` como total de `AssetEntry.quantity` menos
  total de `AssetExit.quantity`, con agregados separados por activo para evitar
  multiplicar filas. Activos sin movimientos parten de cero. El saldo es global
  por activo, no por oficina. El router de `app/main.py` tiene prefijo
  `/api/inventory`; `GET /api/inventory/products` devuelve productos con
  `current_stock`. Las rutas de inventario requieren JWT.
- `operations.py` usa transacciones; la salida insuficiente se rechaza. En
  PostgreSQL, outbound bloquea la fila de activo con `SELECT FOR UPDATE` y usa
  `READ COMMITTED` para recalcular stock después del lock. SQLite no valida esa
  concurrencia.
- Seed manual: `services/api/app/inventory/seed.py`, no forma parte del startup.
  Requiere el argumento `--environment development|test`, `DATABASE_URL` que
  pase los guardas de entorno/destino, y `NEXOVA_INVENTORY_SEED_USER_EMAIL`.
  El email se usa localmente para resolver una única cuenta activa con
  `user_uuid` válido ya persistido en la tabla `users` de TinyDB. La lectura usa
  `get_database_path()` en modo solo lectura. No se genera UUID, no se acepta
  el ID del documento TinyDB como identidad y el comando no imprime UUID, email,
  URL ni credenciales.
- Los UUID se asignan en servidor a usuarios nuevos y se persisten en TinyDB;
  registros legacy pueden carecer del campo. JWT sigue basado en el ID entero
  (`sub`). La API no devuelve `user_uuid` en el response público de usuario.
  No existe FK entre usuarios TinyDB y movimientos PostgreSQL. Una cuenta
  legacy sin UUID puede seguir autenticándose/leyendo, pero no puede escribir
  movimientos (428); no hay backfill automático.
- Dataset del seed: 6 activos, 4 entradas y 3 salidas. El seed solo inserta,
  exige coincidencia completa para reutilizar SKU, evita movimientos naturales
  duplicados para el mismo UUID, rechaza saldo negativo y usa un advisory
  transaction lock en PostgreSQL. La sesión debe estar limpia antes de entrar
  en la operación.

### Decisiones y convenciones que deben preservarse

- Mantener auth y dominios TinyDB independientes de inventario PostgreSQL; no
	mover datos ni intentar simular atomicidad entre bases.
- Al localizar TinyDB de auth, usar `get_database_path()` y verificar el
	entorno/ruta real del proceso. No suponer que el servidor API y la CLI usan
	la misma base si arrancaron con variables distintas.
- El destino del seed debe seguir restringido: Supabase solo se admite en
	desarrollo para el proyecto de desarrollo autorizado en el código y la DB
	estándar `postgres`; se rechaza como destino de tests. Otros nombres de DB y
	archivos SQLite deben identificar explícitamente el entorno con `_dev` o
	`_test`; SQLite en memoria es solo para test. Nunca usar la URL de desarrollo
	como base de pruebas.
- Variables relevantes (nombres únicamente; no registrar sus valores):
  `DATABASE_URL`, `NEXOVA_INVENTORY_SEED_USER_EMAIL`, `AUTH_DB_PATH`,
  `NEXOVA_INVENTORY_TEST_POSTGRES_URL` (optativa para concurrencia PostgreSQL,
  solo con una base desechable cuyo nombre termine en `_test`), y `SECRET_KEY`
  para la configuración de auth.
- La CLI no carga `.env` automáticamente. En un entorno local se ha verificado
  la forma `uv run --env-file .env python -m app.inventory.seed
  --environment development` desde `services/api`, con la variable de email
  definida localmente. No se debe almacenar el email de prueba ni incluir
  secretos o valores de configuración en logs/docs.
- Para arrancar la API desde `services/api`, el README documenta
  `uvicorn app.main:app --reload`; Swagger está disponible en `/docs`. Para la
  suite backend completa, desde `services/api`: `uv run pytest`.
- Antes de modificar TinyDB o ejecutar un seed, leer este contexto, `progress.md`
  y la documentación específica; confirmar código, rutas y variables reales y
  preservar datos. No crear endpoints temporales, modificar registros
  directamente ni desactivar guardas si existe una vía normal, autorizada y
  segura.

### Estado final, verificación y límites

- Resultado verificado de la suite backend completa desde `services/api`:
  `uv run pytest` → **374 aprobados, 0 fallidos, 1 omitido**. El omitido es la
  prueba opcional de concurrencia PostgreSQL. Los tests usan almacenamiento
  aislado; no se empleó Supabase como DB de pruebas.
- La ejecución de seed en Supabase con 6 activos, 4 entradas y 3 salidas, y la
  respuesta de `GET /api/inventory/products` con los seis productos y
  `current_stock`, fueron confirmadas por el usuario. No se volvió a ejecutar
  seed ni se accedió a Supabase durante el cierre documental.
- Pendiente: ejecutar concurrencia en PostgreSQL desechable usando
  `NEXOVA_INVENTORY_TEST_POSTGRES_URL`; definir/aprovisionar migraciones formales;
  decidir si se requiere saldo por oficina, filtros/paginación y una estrategia
  aprobada para usuarios históricos sin UUID. El resultado de pytest y la
  confirmación del usuario no sustituyen dichas comprobaciones pendientes.
### Frontend de inventario — Fase 1: capa de integración (inventario)

- Ruta del frontend: `uis/backoffice/talent-pipeline-tracker` (Next.js App
  Router). La API de inventario se consume bajo `/api/inventory` con
  `NEXT_PUBLIC_NEXOVA_API_BASE` (por defecto `http://localhost:8000/api`).
- `types/inventory.ts`: espejo de los schemas de `services/api` de inventario.
  Constantes `INVENTORY_OFFICES = ["Valencia", "Miami"]` y
  `INVENTORY_EXIT_TYPES = ["allocation", "consumption"]` con sus etiquetas de
  UI. Modelos: `AssetWithStock` (producto + `current_stock` derivado),
  `AssetEntryCreate`/`AssetEntry`, `AssetExitCreate`/`AssetExit` (con
  `exit_type` y `assigned_to` opcional) e `InventoryOrder` como unión
  discriminada por `type`: `"entry" | "exit"`. `types/index.ts` re-exporta
  todo para `@/types`.
- `lib/inventory.ts`: capa de integración autenticada. Todas las llamadas van a
  través de `nexovaApi.request` con `auth: true` (Bearer desde
  `nexova_access_token`). Sigue el patrón inyectable de `lib/profile-api.ts`
  (funciones reciben `InventoryApiClient = Pick<NexovaApiClient, "request">`);
  las páginas pasan el singleton `nexovaApi` y los tests inyectan un cliente
  con fetch/storage simulados. Importa con rutas relativas y extensión `.ts`
  para que el runner de Node (`node --experimental-strip-types`) lo ejecute.
  Exporta `listProducts`, `getProduct`, `listOrders`, `createInbound`,
  `createOutbound` e `inventoryErrorMessage`.
- `tests/inventory-api.test.mjs`: patrón de `tests/profile-api.test.mjs`
  (`MemoryStorage` + `NexovaApiClient` mock). Cubre GET, POST, Bearer, payloads
  JSON, rechazo 400 stock insuficiente, 428 UUID, 409, 503 y traducción de
  mensajes de error.
- Umbrales confirmados para la vista de stock (fases posteriores): verde ≥ 8,
  ámbar 2-7 inclusive, rojo ≤ 1.
- Verificación Fase 1: `npm test` → **70/70 tests frontend**; lint de los
  archivos nuevos y `npx tsc --noEmit` sin errores. Errores preexistentes de
  lint en `hooks/useRecords.ts` ajenos a esta fase. Sin commit/push.

### Frontend de inventario — Fase 2: vista de stock actual (inventario)

- Umbrales implementados en `types/inventory.ts`: `stockLevelFor(currentStock)`
  (`>= 8 → "healthy"`, `>= 2 → "low"`, resto → `"out"`) y `STOCK_LEVEL_LABELS`
  (`Healthy`/`Low`/`Out of stock`). Re-exportados en `types/index.ts`.
- `app/inventory/products/page.tsx` (wrapper fino) +
  `components/inventory/InventoryCurrentStockPanel.tsx` (cliente): carga
  `listProducts(nexovaApi)` al montar; Spinner/error/estado vacío; por fila
  avatar de stock coloreado, nombre, SKU · categoría · oficina y badge
  `Healthy`/`Low`/`Out of stock`; resumen "N productos · M unidades"; enlaces
  "Create inbound"/"Create outbound" con `?product={id}` (fases 3/4).
  `components/inventory/index.ts` = barrel del dominio.
- `components/auth/AuthShell.tsx`: `DropdownName` incluye `"inventory"`;
  dropdown **Inventory** (desktop) y bloque etiquetado (móvil) entre
  Incidents y Suppliers con Current Stock, Inbounds, Outbounds, All Orders.
- `lib/auth-navigation.ts`: `protectedRoutes` añade `/inventory/products`,
  `/inventory/orders/inbound`, `/inventory/orders/outbound`,
  `/inventory/orders` (redirección a `/login` ya existente en `AuthShell`).
- Verificación Fase 2: `npm test` → **70/70 tests frontend**; ESLint limpio en
  archivos nuevos/cambios; `npx tsc --noEmit` sin errores. Errores de lint
  preexistentes en `hooks/useRecord.ts`/`hooks/useRecords.ts`. Sin commit/push.
