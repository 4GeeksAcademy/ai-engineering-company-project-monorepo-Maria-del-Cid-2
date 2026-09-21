# AGENTS.md — Nexova

## 1. Propósito

Este archivo define las reglas generales que debe seguir cualquier agente de programación que trabaje en el monorepo de Nexova.

Estas reglas se aplican a todo el repositorio. Los archivos `AGENTS.md` situados en subdirectorios pueden añadir o sobrescribir reglas para su ámbito específico.

---

## 2. Contexto obligatorio antes de trabajar

Antes de modificar código, el agente debe comprender el contexto actual del proyecto.

Debe leer:

1. `memory-bank/projectbrief.md`
2. `memory-bank/techContext.md`
3. `memory-bank/progress.md`

El siguiente archivo contiene contexto adicional y debe consultarse cuando sea relevante:

- `memory-bank/context.md`

Además, antes de crear una nueva carpeta o comenzar a trabajar en un área concreta, el agente debe revisar el `README.md` correspondiente.

Por ejemplo:

- Trabajo en `uis/` → leer `uis/README.md`
- Trabajo en `services/` → leer `services/README.md`
- Trabajo dentro de una aplicación concreta → revisar su documentación y su `AGENTS.md`

---

## 3. Antes de escribir código

El agente no debe comenzar directamente a implementar código.

Antes de realizar cambios debe:

1. Comprender el objetivo solicitado.
2. Identificar la aplicación, servicio, paquete o área de configuración afectada.
3. Leer el README y las reglas de agente aplicables.
4. Revisar la implementación existente antes de modificarla.
5. Identificar dependencias y posibles efectos secundarios.
6. Definir un plan breve de implementación.
7. Preguntar al usuario si los requisitos son ambiguos o existe una decisión arquitectónica importante que no pueda determinarse con seguridad.

No se deben crear nuevas carpetas ni estructuras arquitectónicas sin revisar previamente el README correspondiente y la estructura existente del repositorio.

---

## 4. Estructura del repositorio

El repositorio debe utilizarse de acuerdo con las responsabilidades establecidas:

- `uis/` → interfaces y aplicaciones de usuario.
- `services/` → servicios backend y APIs.
- `data/` → datos y datasets.
- `agents/` → agentes de IA e implementaciones de agentes.
- `skills/` → capacidades reutilizables de IA.
- `.agents/` → configuración, reglas y skills para agentes de programación.
- `memory-bank/` → contexto persistente del proyecto.
- `packages/` → paquetes compartidos.
- `shared/` → recursos compartidos.
- `infra/` → infraestructura.
- `scripts/` → scripts de desarrollo y operaciones.
- `docs/` → documentación del proyecto.

No confundir:

- `.agents/` con `agents/`
- `.agents/skills/` con `skills/`

`.agents/` contiene instrucciones y capacidades destinadas a los agentes de programación.

`agents/` y `skills/` son áreas del proyecto destinadas a funcionalidades de IA.

---

## 5. Principios de desarrollo

Los agentes deben:

- Priorizar la arquitectura y las convenciones existentes antes que introducir nuevos patrones.
- Reutilizar componentes, utilidades y servicios existentes cuando sea apropiado.
- Evitar dependencias innecesarias.
- Mantener los cambios centrados en el objetivo solicitado.
- Evitar refactorizaciones no relacionadas con la tarea.
- Preservar la funcionalidad existente salvo que el cambio solicitado requiera modificarla.
- Aplicar siempre el `AGENTS.md` más específico disponible.
- Mantener sincronizada la documentación y el contexto del proyecto cuando se produzcan cambios relevantes.

---

## 6. Estructura de las aplicaciones de Nexova

Cuando se trabaje en interfaces de usuario, debe seguirse la estructura establecida del monorepo:

- Web pública → `uis/website`
- Aplicaciones internas → `uis/backoffice`
- Servicios backend → `services/`

Las aplicaciones internas deben disponer de su propio layout y de una vista de entrada funcional y visible desde el principio.

Antes de crear una nueva aplicación o duplicar funcionalidad existente, se debe inspeccionar primero lo que ya existe en el repositorio.

---

## 7. Mantenimiento del Memory Bank

El Memory Bank representa el contexto activo del proyecto y no debe tratarse como documentación estática.

El agente debe actualizar el archivo correspondiente cuando se produzcan decisiones relevantes o cambios significativos en el proyecto.

Utilizar:

- `projectbrief.md` → propósito empresarial estable y objetivos del proyecto.
- `techContext.md` → arquitectura, tecnologías y decisiones técnicas.
- `progress.md` → estado actual de implementación, trabajo completado y trabajo pendiente.
- `context.md` → información transversal adicional sobre el negocio o el proyecto.

`progress.md` debe mantenerse actualizado a medida que evoluciona el proyecto.

---

## 8. Validación antes del commit

Antes de crear un commit, el agente debe:

1. Revisar los cambios realizados.
2. Ejecutar las pruebas relevantes.
3. Ejecutar el lint cuando esté disponible.
4. Ejecutar los checks de build y tipos cuando estén disponibles.
5. Verificar que no se hayan modificado archivos no relacionados.
6. Revisar `git status`.
7. Revisar el `git diff` final.
8. Actualizar `memory-bank/progress.md` si ha cambiado el estado del proyecto.
9. Confirmar que el objetivo solicitado está realmente completado.

Si una validación falla, el agente debe investigar y solucionar el problema antes del commit siempre que sea posible.

El agente no debe ocultar, revertir ni sobrescribir cambios realizados por el usuario.

---

## 9. Proceso de commit y entrega

Solo se permite crear un commit después de completar el proceso de validación.

Antes del commit se debe confirmar que:

- La implementación cumple el objetivo solicitado.
- Las validaciones relevantes han pasado correctamente.
- La documentación y el contexto se han actualizado cuando sea necesario.
- El working tree contiene únicamente los cambios previstos.

Los mensajes de commit deben ser breves y describir el cambio realizado.

Una vez completado el trabajo, los cambios deben quedar preparados para su entrega mediante el flujo de PR establecido en el repositorio y se debe informar al responsable técnico.

---

## 10. Cuándo detenerse y preguntar

El agente debe detenerse y preguntar al usuario cuando:

- Los requisitos sean ambiguos.
- Existan dos enfoques arquitectónicos con consecuencias relevantes diferentes.
- El cambio solicitado entre en conflicto con las reglas existentes del proyecto.
- Sea necesaria una operación destructiva.
- Puedan exponerse credenciales, secretos o información sensible.
- No pueda determinarse con seguridad el comportamiento esperado.
- Una dependencia o servicio externo necesario no esté disponible.

El agente no debe realizar suposiciones cuando sea necesaria una decisión empresarial o arquitectónica.

---

## 11. Control del alcance

Solo deben modificarse los archivos necesarios para realizar la tarea solicitada.

No se debe:

- Reescribir código no relacionado.
- Realizar refactorizaciones amplias sin aprobación.
- Añadir dependencias sin justificación.
- Modificar configuraciones no relacionadas con la tarea.
- Subir secretos, API keys o credenciales.
- Subir archivos generados salvo que el proyecto lo requiera explícitamente.

---

## 12. Entrega final

Cuando la tarea esté terminada, el agente debe informar de:

1. Qué se ha modificado.
2. Qué validaciones se han realizado.
3. Qué problemas o limitaciones quedan pendientes, si los hubiera.
4. Si se ha actualizado el Memory Bank.

El resultado final debe ser reproducible y comprensible para otro desarrollador o agente de programación.