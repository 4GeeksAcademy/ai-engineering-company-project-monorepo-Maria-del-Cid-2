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

`uis/talent-pipeline-tracker/`

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

`uis/talent-pipeline-tracker/AGENTS.md`

y contexto funcional en:

`uis/talent-pipeline-tracker/context.md`

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

- consultar las instrucciones de `uis/talent-pipeline-tracker/AGENTS.md`;
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