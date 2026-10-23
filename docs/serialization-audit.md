# Auditoría de Serialización — Nexova Backend

> **Rama de trabajo:** `serialization-audit` (creada desde `Containerization` @ `a1b89b8`)
> **Fecha de inicio:** 2026-10-23
> **Alcance:** Serialización de contratos HTTP del backend FastAPI en `services/api`
> **Documento vivo:** este archivo se actualizará al final con el estado final. El estado inicial queda preservado en la sección *Estado inicial (histórico)*.

---

## 1. Inventario completo de rutas (31 rutas de negocio)

### Infraestructura (fuera del inventario de negocio)

| Método | Ruta | Uso |
|---|---|---|
| GET | `/__test/unexpected-error` | **Exclusiva de tests.** Se registra solo cuando `tests/test_api.py` la añade mediante `app.add_api_route`. No está registrada en producción. |

### Auth — `/api/auth` (`auth_router.py`) — TinyDB

| # | Método | Ruta | response_model | Observación |
|---|---|---|---|---|
| 1 | POST | `/api/auth/login` | `TokenResponse` | OAuth2 form; 401 genérico |
| 2 | GET | `/api/auth/me` | `UserMeResponse` | Anida `profile: Profile \| None` |
| 3 | POST | `/api/auth/forgot-password` | `GenericMessageResponse` | Mensaje idéntico si el correo existe o no |
| 4 | POST | `/api/auth/reset-password` | `GenericMessageResponse` | 400 si el token es inválido/vencido |
| 5 | POST | `/api/auth/change-password` | `GenericMessageResponse` | 400 si la contraseña actual es incorrecta |

### Users — `/api/users` (`users_router.py`) — TinyDB

| # | Método | Ruta | response_model | Observación |
|---|---|---|---|---|
| 6 | POST | `/api/users` | `UserResponse` (201) | Público; nunca expone `hashed_password` |
| 7 | GET | `/api/users` | `list[UserResponse]` | |
| 8 | GET | `/api/users/{user_id}` | `UserResponse` | Autorización por rol |
| 9 | PUT | `/api/users/{user_id}` | `UserResponse` | Solo admins cambian rol; 409 `LastAdminError` |
| 10 | DELETE | `/api/users/{user_id}` | 204 | |

### Profiles — `/api/profiles` (`profiles_router.py`) — TinyDB

| # | Método | Ruta | response_model | Observación |
|---|---|---|---|---|
| 11 | GET | `/api/profiles/me` | `Profile` | 404 si no existe |
| 12 | PUT | `/api/profiles/me` | `Profile` | Crea si falta; 409 en carrera |

### Suppliers — `/api/suppliers` (`router.py`) — TinyDB

| # | Método | Ruta | response_model | Observación |
|---|---|---|---|---|
| 13 | POST | `/api/suppliers` | `Supplier` (201) | **Resuelto (F1):** el cliente ya no envía `status`; el servidor fija `active` |
| 14 | GET | `/api/suppliers` | `list[Supplier]` | Filtros country/category |
| 15 | GET | `/api/suppliers/{supplier_id}` | `Supplier` | 404 |
| 16 | PATCH | `/api/suppliers/{supplier_id}/rate` | `Supplier` | 404 |
| 17 | PATCH | `/api/suppliers/{supplier_id}/status` | `Supplier` | 404 |
| 18 | DELETE | `/api/suppliers/{supplier_id}` | 204 | |

### Inventory — `/api/inventory` (`router.py`) — PostgreSQL/SQLModel

| # | Método | Ruta | response_model | Observación |
|---|---|---|---|---|
| 19 | GET | `/api/inventory/products` | `list[AssetWithStockResponse]` | |
| 20 | GET | `/api/inventory/products/{asset_id}` | `AssetWithStockResponse` | 404 |
| 21 | GET | `/api/inventory/orders` | `list[InventoryOrderResponse]` | Unión discriminada `type` |
| 22 | POST | `/api/inventory/products` | `AssetWithStockResponse` (201) | 409 SKU duplicado |
| 23 | POST | `/api/inventory/orders/inbound` | `AssetEntryResponse` (201) | 404/409/428 |
| 24 | POST | `/api/inventory/orders/outbound` | `AssetExitResponse` (201) | 400/404/409/428 |

### Incidents manager — `/api/incidents` (`manager_router.py`) — TinyDB

| # | Método | Ruta | response_model | Observación |
|---|---|---|---|---|
| 25 | POST | `/api/incidents` | `Incident` (201) | `status` por defecto `open` |
| 26 | GET | `/api/incidents` | `list[Incident]` | Filtros status/origin/branch/category |
| 27 | GET | `/api/incidents/summary` | `IncidentSummary` | |
| 28 | GET | `/api/incidents/{incident_id}` | `Incident` | 404 |
| 29 | PATCH | `/api/incidents/{incident_id}/status` | `Incident` | 400 transición ilegal |

### Incident analysis — inline en `main.py` — en memoria

| # | Método | Ruta | response_model | Observación |
|---|---|---|---|---|
| 30 | POST | `/api/incidents/analyze` | `IncidentAnalysisResponse` | **Resuelto (F2):** `response_model` añadido; payload sin cambios |
| 31 | GET | `/api/incidents/results/export` | `StreamingResponse` CSV | Clase A |

---

## 2. Clasificación inicial A/B/C

### Clase A — Correcto, sin cambios

- **Salidas con `response_model` y schemas de salida propios:** auth (TokenResponse, UserMeResponse, UserResponse, GenericMessageResponse), profiles (Profile), suppliers (Supplier), inventory (AssetWithStockResponse, InventoryOrderResponse, AssetEntryResponse, AssetExitResponse), incidents manager (Incident, IncidentSummary).
- **Rutas 204** (DELETE) sin cuerpo.
- **Export CSV** (`/api/incidents/results/export`): `StreamingResponse` con `media_type="text/csv"` y `Content-Disposition: attachment; filename=results.csv`.
- **Campos sensibles**: `User` interno contiene `hashed_password`, `user_uuid`, `credentials_version`, pero ninguna respuesta HTTP de auth lo expone. `_user_to_response()` lo excluye explícitamente.

### Clase B — Fallo de contrato, cambio realizado

1. **`SupplierCreate` heredaba de `SupplierFields` junto con `Supplier`** → el cliente decidía el `status` inicial en `POST /api/suppliers`. **Resuelto (Fase 1):** `SupplierCreate` independiente sin `status`; el servidor fija `active`.
2. **`POST /api/incidents/analyze` no declaraba `response_model`** → faltaba un contrato explícito de salida. **Resuelto (Fase 2):** `IncidentAnalysisResponse` añadido como `response_model`; el payload de salida no cambió.

### Clase C — Observación, sin cambios en esta tarea

- **Errores**: varias familias (400 de validación del manager, 422 del resto, 404, 409, 428, 401, 500 sanitizado). Se documentan y se añaden pruebas de contrato; **no** se unifican.
- **Listados**: sin paginación ni proyección reducida (decisión deliberada para no alterar contratos consumidos por el frontend).
- **`incidents/results/export`** se mantiene en CSV (no se convierte a JSON).

---

## 3. Estado inicial (histórico)

*Sección preservada — no sobrescribir. Registra el punto de partida verificado antes de los cambios.*

### 3.1 Estado git

- Rama `serialization-audit` creada desde `Containerization` (`a1b89b8`), 0 adelante / 0 atrás contra `origin/Containerization`, working tree limpio.
- `main` = `origin/main` = `2c177b2`; sin modificaciones en `main` ni `Containerization`.

### 3.2 Línea base de tests (backend)

Metodología reproducible:
- Las tres bases TinyDB aisladas mediante rutas temporales:
  - `AUTH_DB_PATH=$TMPDIR/data/auth.json`
  - `INCIDENTS_DB_PATH=$TMPDIR/data/incidents.json`
  - `SUPPLIER_DIRECTORY_DB_PATH=$TMPDIR/data/suppliers.json`
- `DATABASE_URL=sqlite:///$TMPDIR/data/inventory_dev.db` (sin tocar Supabase real).
- **`env -u CORS_ORIGINS`**: necesario porque el entorno inyecta `CORS_ORIGINS=http://localhost:3000,http://localhost:3001`, lo que desactiva el cálculo automático del origin de Codespaces que el `.env` sí prevé y que los tests CORS esperan.

Resultado real (con `env -u CORS_ORIGINS` y rutas aisladas):

```
374 passed, 1 skipped, 62 subtests passed in 132.13s (0:02:12)
```

Diagnóstico de fallos previos (sin aislamiento):
- **4 fallos** eran de entorno: las variables globales apuntaban a `/app/services/data/*.json` (rutas del contenedor), causando `PermissionError: [Errno 13] Permission denied: '/app'`.
- **+2 fallos CORS** adicionales al aislar rutas pero manteniendo `CORS_ORIGINS`: los tests esperan el origin de Codespaces (`https://friendly-barnacle-...-3000.app.github.dev/`) que el `.env` de `services/api` define; la variable del entorno la sobrescribe. Con `env -u CORS_ORIGINS` desaparecen.

### 3.3 Comandos base verificados

- Backend tests: `uv run pytest tests -q --tb=short` (desde `services/api`)
- Frontend (Hito 2 TS, fuera de alcance): `npm test` → 111 passed; `npm run test:coverage` → 100% en `src/utils/*`

---

## 4. Cambios a realizar (plan aprobado)

### Cambio 1 — Suppliers, Opción A (separar esquema de creación)

- `services/api/app/suppliers/models.py`: crear `SupplierCreate` independiente de `SupplierFields` (campos de cliente: `name`, `country`, `categories`, `monthly_rate`, `currency`, `contract_renewal_date`, `contact_email`, `notes`). **Eliminar `status` de la entrada de creación.**
- El servidor fija `status="active"` al crear (`Supplier.from_create`).
- `services/api/app/suppliers/router.py`: sin cambio funcional más allá de lo que implica el nuevo esquema.
- `services/api/app/suppliers/seed.py`: mantener `status` en los datos semilla (siguen siendo válidos como `Supplier`), pero el seed crea proveedores con el status servido por el servidor — revisar si algunos semillas están `suspended` (ver §6).
- Frontend:
  - `uis/backoffice/talent-pipeline-tracker/types/supplier.ts`: `SupplierCreatePayload` sin `status`.
  - `uis/backoffice/talent-pipeline-tracker/components/suppliers/SupplierDirectoryPanel.tsx`: eliminar el selector de Status del formulario de creación; el backend siempre crea `active`.
  - **El endpoint PATCH `/status` sigue funcionando** para cambiar el estado posteriormente.
- Tests: adaptar `test_supplier_models.py`, `test_supplier_api.py` (el payload `PAYLOAD` incluye `status: "active"`), `test_supplier_seed.py` (`seed_suppliers` usa `SupplierCreate`).

### Cambio 2 — Incident analysis: `IncidentAnalysisResponse`

- `services/api/app/incidents/schemas.py` (nuevo): definir `IncidentAnalysisResponse` con exactamente los campos de `_serialize_result`:
  - `total_records: int`, `valid_records: int`, `invalid_records: int`
  - `by_category: dict[IncidentCategory, int]`
  - `by_status: dict[IncidentStatus, int]`
  - `satisfaction_distribution: dict[str, int]`
  - `average_satisfaction: float | None`
  - `invalid_by_type: dict[ValidationErrorCode, int]`
- `services/api/app/main.py`: añadir `response_model=IncidentAnalysisResponse` a `POST /api/incidents/analyze`. Mantener `_serialize_result` (o migrar la serialización al modelo) preservando **exactamente** el payload actual (el test `test_response_contains_only_aggregate_fields` y el contrato frontend `IncidentAnalysisResult` lo verifican).

### Cambio 3 — Pruebas de contrato

- **Campos sensibles**: garantizar que ninguna respuesta de auth expone `hashed_password`/`user_uuid`/`credentials_version`.
- **Análisis**: garantizar que el payload de `/api/incidents/analyze` no cambia y que solo contiene campos agregados.
- **Errores por familia**: pruebas que fijan los contratos 400/401/404/409/422/428/500 existentes.

---

## 5. Decisiones y justificaciones (documentación de errores, listados, CSV, test route)

### 5.1 Errores — se documentan por familia, no se unifican

| Familia | Endpoints | Formato | Test de contrato |
|---|---|---|---|
| 400 validación manager | `POST/PATCH /api/incidents`, `PATCH /status` | `{field, message}` (castellano) | Sí (existe) |
| 422 validación request | Resto de rutas (salvo incidents manager/analysis) | `detail: [...]` sanitizado (sin `input`/`ctx`) | Sí |
| 400 dominio | `analyze` (CSV), `outbound` (stock) | `{detail}` | Sí |
| 401 | Auth + dependencia `get_current_user` | `{detail}` genérico | Sí |
| 404 | Entidades inexistentes | `{detail}` | Sí |
| 409 | `users` last admin, `inventory` SKU | `{detail}` | Sí |
| 428 | `inventory` sin user_uuid | `{detail}` | Sí |
| 500 | Genérico sanitizado | `{message}` genérico, sin detalles internos | Sí |

**Justificación de no unificar:** cada módulo ya contrata su familia con el frontend; unificar cambiaría códigos/formatos sin beneficio de serialización.

### 5.2 Listados — sin paginación ni proyección

Se documenta la decisión: **no** se añade paginación ni proyección reducida en esta tarea. Justificación: (1) los consumidores frontend ya dependen de las listas completas actuales; (2) la paginación es una mejora transversal de contrato que merece su propia tarea; (3) el alcance de esta auditoría es la serialización correcta, no el rendimiento de listados.

### 5.3 CSV — se conserva el formato actual

- Columnas: `metric`, `dimension`, `value` (solo campos agregados de `IncidentAnalysisResult`).
- `Content-Type`: `text/csv`.
- `Content-Disposition`: `attachment; filename=results.csv`.
- Garantías de privacidad: nunca se exportan `customer_email`, `ticket_id`, ni `description`; solo agregados.
- **No** se convierte la exportación a JSON.

### 5.4 `/__test/unexpected-error` — exclusiva de tests

- Se registra únicamente en `tests/test_api.py` mediante `app.add_api_route(...)`, en el propio módulo de tests.
- **Verificado:** no está registrada en producción (no aparece en `main.py` como ruta de la app; solo el handler genérico de 500 existe en la app).
- Se documenta su propósito: validar que el handler genérico no filtra detalles internos en tests (`test_validation_error_does_not_expose_password_or_token`).

---

## 6. Riesgos y decisiones que requieren confirmación

- **Seed de suppliers** *(resuelto durante Fase 1)*: los datos semilla tienen
  `status` explícito (13 `active`, 2 `suspended` intencionales: Greenhouse —
  "Suspendido tras no renovar..."; Coursera for Teams — "Suspendido por bajo
  uso"). El seed filtra `status` del payload de cliente antes de validar contra
  `SupplierCreate` (que lo rechaza con `extra="forbid"`) y preserva el estado
  explícito vía `Supplier.from_create(..., status=seed_status)`. Se verifica en
  `test_supplier_seed.py` que los semillas conservan su estado.
- La clasificación inicial de `POST /api/incidents/analyze` como Clase B era
  conservadora: la serialización de salida ya era correcta, pero faltaba el
  contrato OpenAPI (`response_model`). **Resuelto en Fase 2.**

---

## 7. Verificación final (completada)

### 7.1 Cambios realizados

| Archivo | Cambio |
|---|---|
| `app/suppliers/models.py` | `SupplierCreate` independiente, sin `status`; `Supplier.from_create(..., status="active")` |
| `app/suppliers/seed.py` | Filtra `status` del payload cliente; preserva estados semilla vía parámetro interno |
| `app/incidents/schemas.py` | **Nuevo:** `IncidentAnalysisResponse` (8 campos agregados) |
| `app/main.py` | `response_model=IncidentAnalysisResponse` en `POST /api/incidents/analyze` |
| `tests/test_supplier_models.py` | Tests `cannot_set_status`, `defaults_to_active`, `preserve_seed_status` |
| `tests/test_supplier_api.py` | Tests `rejects_client_controlled_status`, `always_starts_supplier_active` |
| `tests/test_supplier_seed.py` | Verifica estados semilla conservados |
| `tests/test_auth_unit5.py` | 3 payloads de creación sin `status` + assert `status=="active"` |
| `tests/test_api.py` | +`test_analyze_response_has_exactly_aggregate_keys`, +`test_openapi_declares_incident_analysis_response_schema` |
| `uis/backoffice/.../types/supplier.ts` | `SupplierCreatePayload` sin `status` |
| `uis/backoffice/.../SupplierDirectoryPanel.tsx` | Eliminado selector de Status en creación |
| `memory-bank/progress.md` | Sección de cierre de la auditoría |

### 7.2 Resultados reales

- Backend (baseline inicial): `374 passed, 1 skipped, 62 subtests`.
- Backend (final, tras F1+F2+F3): **381 passed, 1 skipped, 63 subtests** —
  con `env -u CORS_ORIGINS` y las tres bases TinyDB aisladas en rutas
  temporales (ver §3.2 para la metodología).
- Frontend TS relevante: `npx tsc --noEmit` sin errores; `eslint` en
  `SupplierDirectoryPanel.tsx` y `types/supplier.ts` sin warnings.
- `git diff --check`: **sin errores** (verificado al cierre).

### 7.3 Contratos verificados (resumen)

- [x] No se exponen campos sensibles (auth: `hashed_password`/`user_uuid`/`credentials_version` nunca en respuestas; análisis: nunca `customer_email`/`ticket_id`/`description`).
- [x] Payload de análisis conservado: juego de claves bloqueado a los 8 campos agregados; OpenAPI documenta `IncidentAnalysisResponse`.
- [x] Errores por familia: 400/401/404/409/422/428/500 con sus formatos existentes (no unificados; ver §5.1).
- [x] Suppliers: el cliente no decide el estado inicial (`active` garantizado por servidor); `PATCH /status` intacto.
- [x] Estado inicial preservado en §3 (histórico no sobrescrito).

> **Pendiente por política:** no se realizaron commits ni pull requests (decisión explícita del usuario).