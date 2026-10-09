# Progress — Nexova

## 1. Estado general

El proyecto Nexova se encuentra en una fase de construcción progresiva de su ecosistema digital y de AI Engineering.

Ya existe una base de aplicaciones y documentación, y se está incorporando una estructura persistente para que los agentes de desarrollo puedan trabajar de forma consistente sobre el monorepo.

---

## 2. Completado

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

Backend: 222 tests, 212 correctos. Los 10 fallos restantes provienen de un
único fixture ausente, `scripts/incidents-nexova.csv`, que nunca estuvo
versionado; afectan a Incident Analysis (`test_analysis`, `test_csv_reader`,
`test_export`, `test_cli`, `test_api`, `test_results_export_api`) y no a
autenticación. Auth, perfiles, CORS y Supplier Directory pasan por completo.
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
orden de importación. Sigue pendiente restaurar el fixture CSV: existe como
archivo sin seguimiento dentro del stash `stash@{1}` (`git show
stash@{1}^3:scripts/incidents-nexova.csv`); con él, la suite completa (233
ejecuciones) pasa en una copia aislada y `analyze.py` reproduce los valores
esperados (100 filas, 96 válidas, media 3.84).


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