# MEMORY BANK — Nexova

## 1. Propósito de este archivo

Este archivo contiene el contexto persistente y transversal del proyecto Nexova.

Debe consultarse antes de realizar cambios relevantes en el repositorio. Su objetivo es evitar que un agente de IA tenga que reconstruir desde cero el contexto de negocio, la arquitectura general, el estado del proyecto y las decisiones técnicas principales en cada sesión.

Este archivo NO sustituye a:

- `CONTEXT.es.md`: contexto general de negocio de Nexova.
- Los `context.md` específicos de cada aplicación o hito.
- `AGENTS.md`: instrucciones específicas para agentes.
- La documentación técnica específica de cada módulo.
- El código fuente como fuente de verdad sobre el comportamiento actual.

Cuando exista una discrepancia, debe prevalecer la información más específica y actualizada, especialmente el código y la documentación específica del módulo que se está modificando.

---

# 2. Contexto de negocio — Nexova

Nexova Solutions es una consultora de recursos humanos fundada en 2011.

Tiene sede en Valencia y una oficina de expansión en Miami, con aproximadamente 120 empleados y unos 8 millones de dólares de facturación anual.

Sus principales líneas de negocio son:

1. Headhunting de mandos intermedios, managers y directivos.
2. Servicios externalizados de equipos de atención al cliente para empresas tecnológicas.
3. Formación corporativa en soft skills y liderazgo.

Sus principales clientes son empresas medianas, especialmente de los sectores tecnológico, retail y servicios financieros.

El contexto empresarial detallado se encuentra en:

`CONTEXT.es.md`

Ese archivo debe considerarse la fuente de referencia para la información corporativa general de Nexova.

---

# 3. Situación digital del proyecto

El proyecto Nexova se desarrolla como un monorepo orientado a cubrir progresivamente diferentes necesidades digitales y de IA de la empresa.

La solución contempla distintas áreas:

- presencia web corporativa;
- gestión de candidaturas y procesos de selección;
- formación corporativa;
- atención al cliente;
- ventas y desarrollo de negocio;
- recursos humanos internos;
- telemetría y datos;
- agentes de IA;
- RAG;
- automatizaciones y workflows;
- dashboards y herramientas internas.

No todas estas áreas están necesariamente implementadas actualmente.

IMPORTANTE:

No asumir que una funcionalidad descrita como necesidad de negocio ya está desarrollada. Diferenciar siempre entre:

- funcionalidades implementadas;
- funcionalidades en desarrollo;
- funcionalidades previstas para fases posteriores.

---

# 4. Web corporativa de Nexova

La web pública de Nexova ya está desarrollada.

Actualmente incluye:

- página principal con información básica de la empresa;
- información sobre sus oficinas;
- servicios ofrecidos;
- referencias/clientes;
- información de contacto;
- formulario para empresas interesadas en contratar los servicios de Nexova;
- formulario para trabajadores/candidatos interesados en enviar su CV.

La web corporativa y las aplicaciones internas deben considerarse productos relacionados dentro del ecosistema Nexova, pero no deben confundirse entre sí.

---

# 5. Estructura general del repositorio

El repositorio es un monorepo utilizado para desarrollar los diferentes hitos y proyectos de Nexova.

Principales áreas:

- `uis/` → interfaces y aplicaciones frontend.
- `services/` → APIs y servicios backend.
- `data/` → datos, pipelines y procesos relacionados con datos.
- `agents/` → agentes de IA.
- `skills/` → skills y capacidades reutilizables para agentes.
- `mcps/` → integraciones MCP.
- `packages/` → paquetes reutilizables.
- `shared/` → recursos compartidos.
- `infra/` → infraestructura.
- `scripts/` → scripts auxiliares.
- `internal/` → recursos internos.
- `docs/` → documentación y decisiones técnicas.
- `memory-bank/` → memoria persistente y contexto transversal del proyecto.

Regla general:

- Si es una interfaz de usuario → `uis/`
- Si es una API o servicio backend → `services/`
- Si pertenece al procesamiento o gestión de datos → `data/`
- Si es trabajo específico de IA → `agents/`
- Si es una capacidad reutilizable para agentes → `skills/`
- Si es una integración MCP → `mcps/`

---

# 6. Documentación y fuentes de verdad

El repositorio contiene documentación de diferentes niveles.

## Contexto general

`CONTEXT.es.md`

Contiene el contexto de negocio general de Nexova.

## Memoria transversal

`memory-bank/context.md`

Este archivo contiene el contexto persistente del proyecto: arquitectura general, estado conocido, decisiones y reglas transversales.

## Contexto específico de una aplicación

Cada aplicación puede tener su propio `context.md`.

Por ejemplo:

`uis/talent-pipeline-tracker/context.md`

Este documento contiene los requisitos y contexto específicos del Talent Pipeline Tracker.

## Instrucciones para agentes

Los archivos `AGENTS.md` contienen instrucciones específicas para agentes y deben respetarse en el ámbito en el que se encuentren.

Si existe un `AGENTS.md` dentro de una aplicación, sus instrucciones son especialmente relevantes para modificar esa aplicación.

---

# 7. Talent Pipeline Tracker

## Ubicación

La aplicación se encuentra directamente en:

`uis/talent-pipeline-tracker/`

IMPORTANTE:

`uis/prueba/` existe actualmente como carpeta independiente y está vacía.

`talent-pipeline-tracker` NO está dentro de `uis/prueba/`.

---

# 8. Objetivo del Talent Pipeline Tracker

Talent Pipeline Tracker es una aplicación interna para gestionar candidaturas dentro de un proceso de selección de Nexova.

El caso de uso actual corresponde al proceso de selección de:

**Asistente de Dirección**

La aplicación permite centralizar y gestionar las candidaturas recibidas durante el proceso.

El contexto funcional específico se encuentra también en:

`uis/talent-pipeline-tracker/context.md`

---

# 9. Funcionalidades actualmente implementadas

La aplicación permite:

- consultar el listado de candidaturas;
- buscar candidaturas;
- filtrar por estado;
- filtrar por etapa;
- combinar búsqueda y filtros;
- utilizar paginación;
- registrar nuevas candidaturas;
- consultar el detalle de una candidatura;
- actualizar el estado de una candidatura;
- actualizar la etapa de una candidatura;
- consultar notas internas;
- añadir notas internas;
- eliminar notas internas;
- eliminar candidaturas;
- consultar LinkedIn cuando existe;
- consultar la URL del CV cuando existe.

---

# 10. Rutas principales del Talent Pipeline Tracker

Actualmente se conocen las siguientes rutas:

`/`

Listado principal de candidaturas.

Incluye:

- búsqueda;
- filtros;
- contador de resultados;
- listado;
- paginación;
- acceso al registro de nuevas candidaturas.

`/new`

Formulario para registrar una nueva candidatura.

`/candidates/[id]`

Detalle de una candidatura concreta.

Permite consultar la información, modificar estado/etapa, gestionar notas y eliminar la candidatura.

---

# 11. Stack tecnológico del Talent Pipeline Tracker

Según el `package.json` actual:

- Next.js `16.3.3`
- React `19.2.8`
- React DOM `19.2.8`
- TypeScript `5`
- Tailwind CSS `4`
- ESLint `9`

Scripts principales:

- `npm run dev`
- `npm run build`
- `npm run start`
- `npm run lint`

IMPORTANTE:

La aplicación utiliza una versión reciente de Next.js.

Antes de modificar código relacionado con Next.js, consultar las instrucciones de `AGENTS.md` y, cuando corresponda, la documentación local indicada por dichas instrucciones.

No asumir APIs de versiones antiguas de Next.js.

---

# 12. Arquitectura actual del Talent Pipeline Tracker

La aplicación sigue, de forma general, esta estructura:

UI / páginas
↓
components
↓
hooks
↓
lib
↓
API externa

Las responsabilidades principales son:

## `app/`

Define las páginas y rutas de Next.js.

## `components/`

Contiene componentes reutilizables de interfaz agrupados por funcionalidad:

- `candidates/`
- `filters/`
- `notes/`
- `ui/`

## `hooks/`

Contiene lógica de interacción con los datos:

- `useRecords`
- `useRecord`
- `useNotes`

## `lib/`

Contiene la comunicación con la API:

- `api.ts`
- `records.ts`
- `notes.ts`

## `types/`

Contiene los contratos TypeScript de la aplicación.

## `constants/`

Contiene las etiquetas, opciones y configuraciones relacionadas con estados y etapas.

---

# 13. API utilizada

La aplicación utiliza la API:

`https://playground.4geeks.com/tracker/api/v1`

La comunicación se centraliza mediante:

`lib/api.ts`

Este helper:

- construye las URLs;
- añade parámetros de consulta;
- realiza las peticiones HTTP;
- establece `Content-Type: application/json`;
- gestiona errores HTTP;
- gestiona respuestas `204 No Content`.

No duplicar esta lógica en los componentes.

---

# 14. Operaciones de candidaturas

`lib/records.ts` contiene las operaciones principales sobre candidaturas:

- `getRecords`
- `getRecordById`
- `createRecord`
- `patchRecord`
- `replaceRecord`
- `deleteRecord`

Endpoints principales:

`GET /records`

Obtiene el listado paginado y permite filtros.

`GET /records/{id}`

Obtiene el detalle de una candidatura.

`POST /records`

Crea una candidatura.

`PATCH /records/{id}`

Actualiza estado y/o etapa.

`PUT /records/{id}`

Reemplaza todos los campos de una candidatura.

`DELETE /records/{id}`

Elimina una candidatura.

---

# 15. Operaciones de notas

`lib/notes.ts` gestiona las notas internas.

Endpoints:

`GET /records/{id}/notes`

Obtiene las notas de una candidatura.

`POST /records/{id}/notes`

Crea una nota.

`DELETE /records/{id}/notes/{noteId}`

Elimina una nota.

Las notas son información interna asociada a una candidatura.

---

# 16. Modelo de candidatura

El modelo completo `RecordOut` contiene:

- `id`
- `full_name`
- `email`
- `phone`
- `position`
- `experience_years`
- `linkedin_url`
- `cv_url`
- `status`
- `stage`
- `notes_count`
- `applied_at`
- `updated_at`
- `notes`

Los campos `linkedin_url`, `cv_url` y `notes` pueden no estar disponibles según el registro/respuesta.

---

# 17. Creación de candidaturas

Para crear una candidatura son obligatorios:

- nombre completo;
- email;
- teléfono;
- puesto;
- años de experiencia.

Son opcionales:

- LinkedIn;
- URL del CV.

El formulario realiza validación básica antes de enviar los datos.

Los años de experiencia deben ser `0` o superiores y el formulario permite incrementos de `0.5`.

Después de crear correctamente una candidatura, la aplicación redirige al detalle de la candidatura creada.

---

# 18. Estados de candidatura

La API utiliza estos valores técnicos:

- `received`
- `in_progress`
- `selected`
- `discarded`

La interfaz los muestra como:

- `Recibida`
- `En proceso`
- `Seleccionada`
- `Descartada`

---

# 19. Etapas de candidatura

La API utiliza:

- `pending`
- `review`
- `personal_interview`
- `technical_interview`
- `offer_presented`

La interfaz muestra:

- `Pendiente de revisión`
- `En revisión`
- `Entrevista personal`
- `Entrevista técnica`
- `Oferta presentada`

---

# 20. Regla importante: API vs UI

Los valores técnicos de `status` y `stage` son valores internos de la API.

NO mostrar directamente estos códigos técnicos en la interfaz.

Siempre utilizar las etiquetas definidas en `constants/index.ts`.

Ejemplo:

Correcto:

`Recibida`

Incorrecto:

`received`

Esta separación debe mantenerse en futuras modificaciones.

---

# 21. Búsqueda, filtros y paginación

El listado principal permite:

- búsqueda;
- filtro por estado;
- filtro por etapa;
- paginación.

La búsqueda se aplica sobre el filtro de búsqueda gestionado por `useRecords`.

Actualmente el campo de búsqueda utiliza un debounce de aproximadamente `350 ms`.

Los filtros y la página se reflejan en los parámetros de URL.

El número de elementos por página por defecto es:

`20`

Los filtros pueden limpiarse mediante la opción `Limpiar filtros`.

---

# 22. Gestión del detalle de candidatura

El detalle muestra:

- nombre;
- puesto;
- email;
- teléfono;
- años de experiencia;
- fecha de aplicación;
- LinkedIn, si existe;
- CV, si existe;
- estado;
- etapa.

También permite:

- actualizar estado;
- actualizar etapa;
- gestionar notas;
- eliminar la candidatura.

La eliminación requiere confirmación del usuario antes de ejecutarse.

---

# 23. Notas internas

Las notas son visibles desde el detalle de una candidatura.

Permiten:

- consultar notas existentes;
- crear nuevas notas;
- eliminar notas.

Las notas representan información interna del proceso de selección.

---

# 24. Reglas técnicas

Antes de modificar una aplicación:

1. Consultar este `memory-bank/context.md`.
2. Consultar el `context.md` específico de la aplicación.
3. Consultar el `AGENTS.md` aplicable.
4. Revisar el código existente antes de introducir nuevas estructuras.
5. Mantener las convenciones y arquitectura existentes.
6. Evitar duplicar lógica que ya existe en hooks, `lib`, `constants` o componentes reutilizables.
7. No asumir que el README genérico representa necesariamente el estado actual de la aplicación.
8. No modificar archivos que no sean necesarios para resolver la tarea.
9. No introducir dependencias nuevas sin una razón clara.
10. Antes de modificar código de Next.js, respetar las instrucciones específicas de `AGENTS.md`.

---

# 25. Estado actual vs roadmap

El hecho de que una necesidad aparezca en `CONTEXT.es.md` NO significa que esté implementada.

Actualmente debe considerarse implementado, según la revisión realizada:

- web corporativa básica;
- formularios públicos de empresa y candidatos;
- Talent Pipeline Tracker con las funcionalidades descritas en este documento.

Las siguientes áreas pertenecen al contexto/roadmap general de Nexova y no deben asumirse como implementadas si no existe código o documentación específica que lo confirme:

- scoring y ranking de candidatos mediante IA;
- búsqueda RAG de candidatos;
- portal avanzado de candidatos;
- agentes de comunicación;
- sistemas de recomendación de formación;
- chatbot de formación;
- chatbot RAG para soporte;
- dashboards avanzados;
- automatización comercial mediante IA;
- portal interno avanzado de RRHH;
- agentes internos de IA;
- telemetría avanzada;
- pipelines de datos;
- agentes de ingeniería;
- dashboard ejecutivo;
- asistente ejecutivo.

Antes de trabajar en cualquiera de estas áreas, revisar el estado real del repositorio.

---

# 26. Principios para agentes de IA

El agente debe trabajar sobre el proyecto existente, no reconstruirlo desde cero.

Antes de implementar una funcionalidad:

- buscar si ya existe;
- identificar el módulo responsable;
- revisar sus tipos;
- revisar sus hooks;
- revisar sus servicios/API;
- revisar las instrucciones locales.

Preferir modificaciones pequeñas y coherentes con la arquitectura existente.

No crear una segunda implementación de una funcionalidad que ya existe.

No cambiar contratos de API o modelos de datos sin comprobar primero sus dependencias.

No sustituir valores técnicos de la API por etiquetas de UI en los tipos que representan el contrato de backend.

No exponer información interna de las notas fuera del contexto de la candidatura.

---

# 27. Regla de mantenimiento de este Memory Bank

Este archivo debe mantenerse actualizado cuando se produzcan cambios estructurales o decisiones relevantes del proyecto.

Actualizarlo cuando, por ejemplo:

- se incorpore una nueva aplicación importante;
- cambie la arquitectura;
- cambie el stack tecnológico;
- cambie un contrato de API relevante;
- se complete una fase importante;
- se establezca una nueva convención transversal;
- se tome una decisión arquitectónica relevante.

No utilizar este archivo como registro de cada pequeño cambio de código.

El objetivo es conservar contexto estable y útil para futuras sesiones de desarrollo.