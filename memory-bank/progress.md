# Progress — Nexova

## 1. Estado general

El proyecto Nexova se encuentra en una fase de construcción progresiva de su ecosistema digital y de AI Engineering.

Ya existe una base de aplicaciones y documentación, y se está incorporando una estructura persistente para que los agentes de desarrollo puedan trabajar de forma consistente sobre el monorepo.

---

## 2. Completado

### Contexto y documentación

- `CONTEXT.es.md` contiene el contexto general de negocio de Nexova.
- Se ha revisado el README general del monorepo.
- Se ha revisado `uis/README.md`.
- Se ha revisado `services/README.md`.
- Se ha revisado la documentación específica del Talent Pipeline Tracker.
- Se ha creado el `memory-bank` del proyecto.
- Se han creado:
  - `memory-bank/projectbrief.md`
  - `memory-bank/techContext.md`
  - `memory-bank/progress.md`

### Web corporativa

La web pública de Nexova está desarrollada e incluye:

- información corporativa;
- oficinas;
- servicios;
- referencias/clientes;
- contacto;
- formulario para empresas;
- formulario para candidatos/trabajadores.

### Talent Pipeline Tracker

La aplicación está ubicada actualmente en:

`uis/talent-pipeline-tracker/`

Funcionalidades implementadas y verificadas:

- listado de candidaturas;
- búsqueda;
- filtro por estado;
- filtro por etapa;
- paginación;
- creación de candidaturas;
- detalle de candidatura;
- actualización de estado;
- actualización de etapa;
- consulta de notas;
- creación de notas;
- eliminación de notas;
- eliminación de candidaturas;
- acceso a LinkedIn cuando existe;
- acceso al CV cuando existe.

### Arquitectura técnica verificada

Se ha revisado y confirmado la existencia y funcionamiento previsto de:

- páginas de Next.js;
- componentes;
- hooks;
- cliente API;
- operaciones de candidaturas;
- operaciones de notas;
- tipos TypeScript;
- constantes para estados y etapas.

### Autenticación del backoffice — AUTH-02, fase 2

Implementada la infraestructura frontend de cliente Nexova y sesión JWT en
`uis/backoffice/talent-pipeline-tracker`:

- cliente compartido con token Bearer opt-in, almacenamiento local, validación
  de sesión mediante `/auth/me`, cierre local e invalidación ante `401`;
- el fetch nativo se almacena enlazado a `globalThis`, manteniendo fetchers
  inyectados para tests y evitando invocarlo con receptor incorrecto;
- tipos de usuario/sesión y `AuthProvider` compatible con SSR;
- integración autenticada de Supplier Directory; Tracker e Incident Analysis
  permanecen separados;
- configuración `NEXT_PUBLIC_NEXOVA_API_BASE` y pruebas nativas del cliente.

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

---

## 3. Estado actual del Talent Pipeline Tracker

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
- No hay archivos CSV en el workspace, aunque las pruebas hacen referencia a
  `scripts/incidents-nexova.csv`. La causa y el efecto sobre pruebas/demos
  dependen de confirmar o recuperar ese fixture; no se generó uno.
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