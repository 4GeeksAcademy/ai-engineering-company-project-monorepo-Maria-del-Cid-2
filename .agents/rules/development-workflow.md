# Development Workflow

## Objetivo

Definir el flujo obligatorio que debe seguir un agente cuando desarrolla o modifica funcionalidades en Nexova.

## 1. Preparación

Antes de comenzar cualquier cambio, el agente debe:

1. Leer `AGENTS.md` de la raíz.
2. Leer `memory-bank/projectbrief.md`.
3. Leer `memory-bank/techContext.md`.
4. Leer `memory-bank/progress.md`.
5. Revisar el `README.md` del área en la que va a trabajar.
6. Revisar cualquier `AGENTS.md` más específico existente en esa área.
7. Inspeccionar el código existente relacionado con la tarea.

## 2. Planificación

Antes de implementar:

1. Identificar los archivos que probablemente serán modificados.
2. Identificar dependencias con otras partes del proyecto.
3. Definir una estrategia de implementación breve.
4. Comprobar que la solución respeta la arquitectura existente.

Si existe una decisión importante que no puede determinarse a partir del contexto disponible, el agente debe preguntar antes de implementar.

## 3. Implementación

Durante el desarrollo:

- Mantener el alcance limitado a la tarea solicitada.
- Reutilizar código existente cuando sea apropiado.
- Seguir las convenciones del área.
- Evitar introducir dependencias innecesarias.
- No modificar archivos no relacionados.
- No sobrescribir cambios realizados previamente por el usuario.
- No incluir secretos, credenciales o API keys.

## 4. Validación

Antes de considerar terminada una tarea, el agente debe ejecutar las validaciones relevantes disponibles para el área modificada.

Como mínimo, cuando corresponda:

- Type checking.
- Lint.
- Tests.
- Build.

Si una validación falla, el agente debe investigar el motivo y corregirlo cuando sea posible.

## 5. Revisión antes del commit

Antes de crear un commit:

1. Ejecutar `git status`.
2. Revisar `git diff`.
3. Confirmar que todos los cambios están relacionados con la tarea.
4. Confirmar que no hay secretos ni archivos sensibles.
5. Ejecutar las validaciones relevantes.
6. Actualizar `memory-bank/progress.md` si el estado del proyecto ha cambiado.

Solo después de estas comprobaciones se puede realizar el commit.

## 6. Finalización

Al terminar una tarea, el agente debe indicar:

- Qué se ha implementado.
- Qué archivos o áreas se han modificado.
- Qué validaciones se han ejecutado.
- Si existen problemas pendientes.
- Si se ha actualizado el Memory Bank.

El trabajo debe quedar preparado para continuar con el flujo de entrega mediante PR.