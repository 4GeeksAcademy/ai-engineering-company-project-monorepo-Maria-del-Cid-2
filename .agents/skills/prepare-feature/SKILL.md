# Prepare Feature

## Objetivo

Preparar una funcionalidad de Nexova para su entrega, verificando que el cambio cumple el objetivo solicitado, respeta la arquitectura existente y está correctamente validado.

Esta skill debe utilizarse cuando una funcionalidad ha sido implementada y necesita una revisión antes de su entrega.

## Entradas

La skill necesita:

- Descripción del objetivo o funcionalidad implementada.
- Archivos modificados.
- Contexto actual del proyecto disponible en `memory-bank/`.
- Reglas aplicables de `AGENTS.md` y `.agents/rules/`.

## Proceso

### 1. Revisar el contexto

Leer:

- `memory-bank/projectbrief.md`
- `memory-bank/techContext.md`
- `memory-bank/progress.md`

Consultar `memory-bank/context.md` cuando sea relevante.

Revisar también las reglas específicas aplicables al área modificada.

### 2. Revisar la implementación

Comprobar que:

- La funcionalidad implementa el objetivo solicitado.
- Se respeta la arquitectura existente.
- Se reutilizan componentes y utilidades existentes cuando corresponde.
- No existen cambios innecesarios relacionados con otras áreas.
- No se han introducido dependencias innecesarias.

### 3. Validar

Ejecutar las comprobaciones disponibles y relevantes para el área modificada:

- Type checking.
- Lint.
- Tests.
- Build.

Registrar cualquier error encontrado y corregirlo cuando sea posible.

### 4. Revisar cambios

Ejecutar:

```bash
git status
git diff