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
---

## 4. Pendiente en este ejercicio

El objetivo inmediato es completar la infraestructura de soporte para agentes de desarrollo.

Pendiente:

- crear el `AGENTS.md` global del repositorio;
- definir reglas en `.agents/rules/`;
- crear al menos una skill reutilizable en `.agents/skills/`;
- completar la estructura de aplicaciones indicada por la plantilla:
  - `uis/website`
  - `uis/backoffice`;
- proporcionar una estructura inicial visible para `backoffice`;
- comprobar que la estructura resultante respeta las instrucciones del monorepo;
- revisar los cambios realizados;
- ejecutar las comprobaciones necesarias;
- preparar commit y PR.

---

## 5. Estructura de agentes pendiente

Debe existir una separación clara entre:

### Configuración de agentes de desarrollo

`.agents/`

Incluye:

- reglas;
- skills reutilizables para el agente de desarrollo.

### Código de producto relacionado con IA

`agents/`

Contiene los agentes que forman parte del producto Nexova.

### Skills de producto

`skills/`

Contiene las skills que forman parte del producto Nexova.

Estas tres áreas no deben mezclarse.

---

## 6. Próximos pasos

Orden previsto:

1. Crear `AGENTS.md` en la raíz.
2. Crear las reglas necesarias en `.agents/rules/`.
3. Crear una skill reutilizable en `.agents/skills/`.
4. Crear o completar `uis/website` según las instrucciones del ejercicio.
5. Crear `uis/backoffice` con su estructura inicial y vista de entrada.
6. Mantener los servicios backend dentro de `services/`.
7. Ejecutar las comprobaciones del proyecto.
8. Revisar `git diff` y `git status`.
9. Crear el commit.
10. Preparar la PR.

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