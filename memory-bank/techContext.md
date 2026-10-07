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
- `AuthShell`, dentro de `AuthProvider` en el layout raíz, protege `/suppliers` y `/account/profile`, incluidas sus subrutas. No monta contenido privado en estados `loading`, `unauthenticated` o `error`; redirige al login sin sesión y ofrece reintentar si falla la validación. Tracker e Incident Analysis siguen públicos con sus clientes separados.
- Logout reutiliza el cliente compartido y publica `unauthenticated` inmediatamente. La expiración se gestiona con `401` y `/login?expired=1`, sin un temporizador JWT adicional. Una revisión de sesión evita que validaciones o `401` tardíos de una sesión anterior restauren el acceso o invaliden una nueva sesión.
- El guard es de UI, no una barrera de autorización de la API. No hay middleware de auth; el JWT vive en localStorage y el backend valida las solicitudes protegidas.
- Auth usa TinyDB en `services/data/auth.json` por defecto o `AUTH_DB_PATH`. La serialización de registro es un lock dentro del proceso, no entre workers; el README del API documenta esa limitación.

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