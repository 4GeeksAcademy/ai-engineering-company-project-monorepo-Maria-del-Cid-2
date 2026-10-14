# TESTING — Nexova

## Índice

1. [Requisitos](#1-requisitos)
2. [Tests de TypeScript (utilidades)](#2-tests-de-typescript-utilidades)
3. [Tests de Python (API/auth)](#3-tests-de-python-apiauth)
4. [Cobertura](#4-cobertura)
5. [Configuración](#5-configuración)
6. [Limitaciones conocidas](#6-limitaciones-conocidas)
7. [Solución de problemas](#7-solución-de-problemas)

> **Aviso de alcance** — Este documento describe los **tests existentes** del repositorio y la forma correcta de instalarlos y ejecutarlos. La sección [3.5](#35-cobertura-por-suite-y-por-endpoint) documenta, endpoint a endpoint, qué casos de camino feliz, límite y fallo cubren los tests actuales, y la sección [3.6](#36-casos-no-cubiertos-o-pendientes) lista expresamente lo que **no** está cubierto. No se afirma cobertura que los tests no demuestren.

---

## 1. Requisitos

| Herramienta | Versión | Propósito |
|---|---|---|
| **Node.js** | ≥ 24.14.0 | Ejecución de tests TypeScript (vía Jest) |
| **npm** | ≥ 11.9.0 | Gestor de paquetes |
| **Python** | ≥ 3.11 | Ejecución de tests Python (vía pytest) |
| **pip** | — | Instalación de dependencias Python |
| **uv** (opcional, recomendado) | — | Instalación del grupo `dev` de la API (pip no puede instalar `[dependency-groups]`) |

Dependencias de proyecto:

| Dependencia | Ámbito | Cómo se instala |
|---|---|---|
| `jest` ^30.5.2 | TypeScript — test runner | `npm install` (raíz) |
| `@jest/globals` ^30.0.0 | TypeScript — APIs de test explícitas | `npm install` (raíz) |
| `@swc/jest` ^0.2.39 y `@swc/core` ^1.16.18 | TypeScript — transformación de tests; compatible con TS 7 sin depender de `ts-jest` | `npm install` (raíz) |
| `typescript` ^7.0.2 | TypeScript — compilador | `npm install` (raíz) |
| `pytest` ≥ 9.1.1 | Python — test runner | grupo `dev` (uv) **o** `pip install pytest` |
| `pytest-cov` ≥ 7.1.0 | Python — cobertura | grupo `dev` (uv) **o** `pip install pytest-cov` |
| `httpx` ≥ 0.28.1 | Python — cliente HTTP para tests | grupo `dev` (uv) **o** `pip install httpx` |
| `httpx` (extra `test`) | Python — requerido por `TestClient` | `pip install -e ".[test]"` |

> **Importante**: en `services/api/pyproject.toml` hay **dos** mecanismos distintos:
> - `[project.optional-dependencies] test` → solo instala `httpx>=0.27,<1` (necesario para `TestClient`).
> - `[dependency-groups] dev` (construcción PEP 735 / uv) → declara `httpx>=0.28.1`, `pytest>=9.1.1` y `pytest-cov>=7.1.0`. **Esta agrupación NO es instalable con `pip install -e ".[test]"`**: para reproducir el entorno de test hay que usar `uv sync --group dev` (si se usa `uv`), o instalar cada paquete explícitamente con `pip`.

---

## 2. Tests de TypeScript (utilidades)

### 2.1 Ficheros

| Fichero | Tests | Propósito |
|---|---|---|
| `src/utils/__tests__/collections.test.ts` | 27 | Filtrado y ordenación de candidatos |
| `src/utils/__tests__/search.test.ts` | 17 | Búsqueda por ID, email y salario binario |
| `src/utils/__tests__/transformations.test.ts` | 40 | Estadísticas, puntuación y ranking (incluye `calculateCandidateScore`) |
| `src/utils/__tests__/validations.test.ts` | 27 | Validación de email, candidatos y vacantes |
| `src/utils/__tests__/test-helpers.ts` | — | Factorías `createCandidate`, `createVacancy`, `createProcess` |

**Total: 111 tests**

### 2.2 Comandos

```bash
# Ejecutar todos los tests (una vez)
npm test

# Ejecutar en modo watch (útil durante desarrollo)
npm run test:watch

# Ejecutar con cobertura
npm run test:coverage
```

### 2.3 Cobertura actual

| Métrica | Valor |
|---|---|
| Statements | **100%** (165/165) |
| Branches | **100%** (74/74) |
| Functions | **100%** (40/40) |
| Lines | **100%** (156/156) |
| Ficheros cubiertos | `collections.ts`, `search.ts`, `transformations.ts`, `validations.ts` |

### 2.4 Notas sobre `calculateCandidateScore`

La función `calculateCandidateScore(candidate, vacancy)` asigna una puntuación de 0 a 120 según las siguientes categorías:

| Categoría | Máx. | Criterio |
|---|---|---|
| Required Skills | 40 | 100% → 40; ≥50% → 20; <50% → 0 |
| Preferred Skills | 20 | +10 por skill (capped a 2) |
| Experience | 20 | Dentro del rango → 20; diff ≤ 2 → 10; diff > 2 → 0 |
| Seniority | 15 | Exacto → 15; 1 nivel → 7; ≥2 niveles → 0 |
| English Level | 15 | Suficiente → 15; insuficiente → 0 |
| Salary | 10 | Dentro del rango → 10; ≤120% máx. → 5; >120% → 0 |

Los tests comprueban puntuaciones totales acumuladas (no dependencias mockeadas), por lo que para aislar una categoría los tests ajustan las demás a 0 (ej.: skills sin match, salario fuera de rango, etc.).

---

## 3. Tests de Python (API/auth)

### 3.1 Ficheros

```
services/api/tests/
├── test_analysis.py          (3 tests)
├── test_api.py               (8 tests)
├── test_auth_cors.py         (6 tests)
├── test_auth_email.py        (6 tests)
├── test_auth_password_reset.py  (18 tests)
├── test_auth_unit1.py        (23 tests)
├── test_auth_unit2.py        (71 tests)
├── test_auth_unit3.py        (21 tests)
├── test_auth_unit4.py        (81 tests)
├── test_auth_unit5.py        (22 tests)
├── test_cli.py               (6 tests)
├── test_csv_reader.py        (8 tests)
├── test_export.py            (3 tests)
├── test_incident_manager.py  (5 tests)
├── test_models.py            (3 tests)
├── test_results_export_api.py (5 tests)
├── test_seed_incidents.py    (7 tests)
├── test_supplier_api.py      (9 tests)
├── test_supplier_models.py   (8 tests)
├── test_supplier_seed.py     (2 tests)
├── test_validation.py        (12 tests)
└── __init__.py
```

**Total: 327 tests (248 de auth + 79 de otras áreas)**

> Los recuentos por fichero proceden de contar las funciones `def test_*` (los
> casos `subTest` no se cuentan por separado). Desglose verificado de "otras
> áreas": `test_analysis` (3) + `test_api` (8) + `test_cli` (6) +
> `test_csv_reader` (8) + `test_export` (3) + `test_incident_manager` (5) +
> `test_models` (3) + `test_results_export_api` (5) + `test_seed_incidents` (7)
> + `test_supplier_api` (9) + `test_supplier_models` (8) +
> `test_supplier_seed` (2) + `test_validation` (12) = **79**.

### 3.2 Comandos

```bash
# Opción A (recomendada): desde services/api, uv instala el proyecto,
# nexova-shared (path source) y el grupo dev en el entorno de uv.
cd services/api
uv sync --group dev

# Opción B (pip): desde la raíz instala primero la dependencia local;
# luego la API y las herramientas de test en el mismo entorno de pip.
cd ../..
python -m pip install -e packages/shared/python
cd services/api
python -m pip install -e .
python -m pip install "pytest>=9.1.1" "pytest-cov>=7.1.0" "httpx>=0.28.1"

# Ejecutar todos los tests (desde services/api; uv run usa el entorno creado).
uv run python -m pytest tests/ -v

# Con la opción B (pip), ejecutar en su entorno Python activado:
python -m pytest tests/ -v

# Ejecutar solo tests de autenticación (módulo app.auth; opción A / uv)
uv run python -m pytest tests/ -v --tb=short --cov=app.auth --cov-branch --cov-report=term-missing

# Opción B / pip:
python -m pytest tests/ -v --tb=short --cov=app.auth --cov-branch --cov-report=term-missing

# Ejecutar tests de un fichero concreto (opción A / uv)
uv run python -m pytest tests/test_auth_password_reset.py -v

# Opción B / pip:
python -m pytest tests/test_auth_password_reset.py -v

# Ejecutar un test concreto. Los `::` requieren pytest; citar el node ID es
# seguro para distintos shells:
uv run python -m pytest "tests/test_auth_password_reset.py::PasswordResetApiTests::test_concurrent_consumption_allows_only_one_reset" -v
```

> **Nota sobre el extra `test`**: `python -m pip install -e ".[test]"` solo añade
> `httpx`; no instala `pytest` ni `pytest-cov`. El grupo `[dependency-groups] dev`
> es PEP 735 y se instala con `uv sync --group dev`, no con pip. También se puede
> ejecutar la suite con `unittest` desde la raíz:
> `PYTHONPATH=packages/shared/python/src:services/api python -m unittest discover -s services/api/tests -p 'test_*.py'`

### 3.3 Cobertura del módulo `app.auth`

| Módulo | Statements | Branches |
|---|---|---|
| `app/auth/__init__.py` | 100% | 100% |
| `app/auth/config.py` | 92% | 50% |
| `app/auth/database.py` | 100% | 100% |
| `app/auth/dependencies.py` | 100% | 100% |
| `app/auth/email.py` | 100% | 100% |
| `app/auth/models.py` | 100% | 100% |
| `app/auth/password_reset.py` | 100% | 100% |
| `app/auth/repository.py` | 100% | 100% |
| `app/auth/routers/auth_router.py` | 100% | 100% |
| `app/auth/routers/profiles_router.py` | 100% | 100% |
| `app/auth/routers/users_router.py` | 100% | 100% |
| `app/auth/schemas.py` | 100% | 100% |
| `app/auth/security.py` | 100% | 100% |
| `app/auth/service.py` | 100% | 100% |
| **TOTAL app.auth** | **99%** (731/732) | **98%** (112/113) |

La línea sin cubrir en `config.py` (línea 40) es la rama `elif` de `email_provider` que comprueba un valor inesperado; no afecta a la funcionalidad principal.

### 3.4 Fallos preexistentes

- **Dependencia del dataset `scripts/incidents-nexova.csv`** — Si falta este fichero, fallan `test_analysis.py::test_dataset_matches_expected_unit_four_metrics`, `test_csv_reader.py::test_csv_dataset_has_expected_row_count` y los tres tests de `test_export.py` (todos leen el dataset). `test_api.py` y `test_results_export_api.py` lo leen en `setUpClass`, por lo que no se puede ejecutar ninguna prueba de esas clases sin el fichero, incluidas las que después envían CSV sintéticos. En `test_cli.py` dependen del dataset los tests que invocan el CLI con `DATASET`; en `test_seed_incidents.py`, los tests de persistencia/idempotencia que lo importan. No todos los casos de esas dos suites dependen del fixture. Son dependencias de datos de pruebas, no evidencia de un fallo de la lógica.
- **`test_concurrent_consumption_allows_only_one_reset`** — Falla intermitentemente en la suite completa con `JSONDecodeError`, aunque pasa al ejecutarlo en aislamiento. Dos hilos consumen el mismo token contra TinyDB; véanse la explicación técnica y la alternativa secuencial en [§6.1](#61-test-de-concurrencia-del-reseteo-de-contraseña). El test expresa que solo una solicitud debe ganar, pero su mecanismo de concurrencia expone la limitación de TinyDB.

La presencia del CSV y el fallo intermitente concurrente son problemas distintos: que el dataset esté presente no elimina la fragilidad de TinyDB, y ejecutar el test concurrente por separado no verifica la ausencia del fixture CSV.

### 3.5 Cobertura por suite y por endpoint

Las suites Python están escritas con `unittest.TestCase`; pytest las descubre y ejecuta. **TestClient** significa integración HTTP en memoria con FastAPI, no una prueba desplegada por red o infraestructura real. **Unitario** significa prueba de modelos, servicios o repositorios sin ejercitar el endpoint HTTP.

#### Qué cubre cada suite

| Suite | Tipo y selección de casos |
|---|---|
| `test_auth_unit1.py` (23) | Unitarios de configuración por entorno, bcrypt, creación/decodificación/expiración JWT y schemas de reset/cambio de contraseña. Se prueban credenciales buenas, malas y límites para aislar criptografía y validación. |
| `test_auth_unit2.py` (71) | Unitarios de modelos y repositorios TinyDB con archivos temporales: CRUD, ausencia, errores de persistencia normalizados, regla del último admin, relación/cascada usuario-perfil, tokens expirados/consumidos y concurrencia de creación/promoción. No implica seguridad concurrente de TinyDB entre procesos. |
| `test_auth_unit3.py` (21) | Unitarios de `AuthService` y tests HTTP con app FastAPI mínima para `get_current_user`: token válido/ausente/inválido/expirado, firma, subject, usuario inactivo y semántica 401 frente a 403. No prueba las rutas completas de la aplicación. |
| `test_auth_unit4.py` (81) | Integración HTTP TestClient para login, `/me`, altas/listado/consulta/edición/borrado de usuarios, perfiles y autorización por rol. Incluye duplicados, último admin, compensación ante errores, ausencia de hash, 401/403/404/409/500 y perfil ausente/race. |
| `test_auth_unit5.py` (22) | Integración HTTP de protección JWT en los seis endpoints de suppliers, semántica 401 y `WWW-Authenticate`, y confirmación de que las rutas públicas de incidentes no requieren JWT. |
| `test_auth_password_reset.py` (18) | Integración HTTP y pruebas de servicio para forgot/reset/change password: respuesta genérica, rate limit, envío fallido, token hasheado/de un uso/expirado e invalidación JWT; incluye el test concurrente intermitente. |
| `test_auth_cors.py` (6) | Integración HTTP de configuración de orígenes CORS y preflight de `PUT /api/profiles/me` y `POST /api/users`, incluyendo origen no autorizado. No cubre preflight de todas las rutas. |
| `test_auth_email.py` (6) | Unitarios con proveedor simulado: éxito, rechazo HTTP, timeout, error de conexión y falta de API key. Comprueba que los logs no filtren datos sensibles; no contacta Resend. |
| `test_incident_manager.py` (5) | Integración HTTP TestClient con repositorio TinyDB temporal y auth sobrescrita; cubre autenticación, resumen vacío, creación/listado/detalle, un filtro, transición inválida y validación segura. |
| `test_supplier_api.py` (9) + `test_auth_unit5.py` | Integración HTTP: altas y datos inválidos, listado/filtros, get/404, cambios de tarifa/estado, delete/204/404, seed y permisos JWT; TinyDB aislada. |
| `test_supplier_models.py` (8), `test_supplier_seed.py` (2) | Unitarios de schemas (país/moneda, categorías, tarifa/estado, campos opcionales) y seed (cantidad/idempotencia); no sustituyen comprobaciones HTTP. |
| `test_validation.py` (12), `test_csv_reader.py` (8) | Unitarios de reglas de validación de filas y lectura CSV (columnas, ancho, datos vacíos/no numéricos y sintaxis malformada). El test del dataset depende del fixture externo. |
| `test_analysis.py` (3), `test_models.py` (3), `test_export.py` (3) | Unitarios de agregación/modelos/exportación: entrada vacía, métricas, esquema agregado y ausencia de emails/campos crudos. Algunas pruebas de dataset/archivo requieren el CSV real. |
| `test_api.py` (8), `test_results_export_api.py` (5) | Integración HTTP TestClient para analizar CSV, serializar agregados, validar uploads, manejar errores de forma segura y exportar el último resultado; dependen del CSV cargado en `setUpClass`. |
| `test_cli.py` (6), `test_seed_incidents.py` (7) | Tests de subprocess para CLI/seeder: ruta/entrada inválida, EOF/interrupción, exportación sí/no, errores de persistencia, idempotencia y preservación de datos. Los casos que usan dataset real dependen del CSV; otros usan CSV sintético. |

#### API de incidentes: análisis y exportación (públicos)

| Endpoint | Camino feliz | Casos límite / modos de fallo | Tests concretos y comportamiento esperado |
|---|---|---|---|
| `POST /api/incidents/analyze` | CSV legible → `200` con agregados, sin filas crudas ni emails. | Upload vacío → `400`; campo ausente → `422`; nombre no `.csv` o CSV malformado → `400`; error de validación no expone secretos; excepción inesperada → `500` genérico/log seguro. Sin token debe fallar por CSV, no con `401`. | `test_api.py`: `test_valid_csv_returns_expected_aggregate_response`, `test_response_contains_only_aggregate_fields`, `test_empty_file_returns_bad_request`, `test_missing_file_returns_unprocessable_entity`, `test_non_csv_filename_returns_bad_request`, `test_malformed_csv_returns_bad_request`, `test_validation_error_does_not_expose_password_or_token`, `test_unexpected_error_returns_generic_500_and_safe_log`; `test_auth_unit5.py::IncidentsPublicTests::test_analyze_incidents_without_token_returns_400_not_401`. |
| `GET /api/incidents/results/export` | Tras un análisis → `200` y CSV agregado; un nuevo análisis reemplaza el último resultado. | Sin análisis → `404`; CSV sin email/campos crudos; sin token y sin resultado → `404`, no `401`. | `test_results_export_api.py`: `test_post_then_get_returns_latest_aggregate_csv`, `test_export_contains_all_aggregate_dimensions`, `test_export_contains_no_sensitive_or_raw_fields`, `test_second_post_replaces_latest_result`, `test_export_before_analysis_returns_not_found`; `test_auth_unit5.py::IncidentsPublicTests::test_export_results_without_token_returns_404_not_401`. |

#### API del gestor de incidentes (protegida)

| Endpoint | Camino feliz | Casos límite / modos de fallo | Tests concretos y comportamiento esperado |
|---|---|---|---|
| `POST /api/incidents` | Crear incidente válido → `201`. | Payload inválido → `400` seguro; sin auth → `401`. | `test_incident_manager.py::test_create_list_filters_and_detail` (alta), `test_incident_validation_returns_safe_400`, `test_manager_requires_authentication`. En tests funcionales, la auth se reemplaza por usuario falso. |
| `GET /api/incidents` | Lista; el test aplica filtro `branch`. | Sin auth → `401`; filtros `status`, `origin`, `category` no se ejercitan directamente. | `test_create_list_filters_and_detail`, `test_manager_requires_authentication`; véase §3.6 para huecos. |
| `GET /api/incidents/summary` | Resumen vacío con dimensiones en cero. | Sin auth → `401`; no se prueba aquí un resumen no vacío con todas las dimensiones. | `test_empty_summary_contains_zero_dimensions`, `test_manager_requires_authentication`. |
| `GET /api/incidents/{incident_id}` | ID existente → detalle. | La implementación devuelve `404` si falta, pero no hay test HTTP con ID inexistente; sin auth → `401`. | `test_create_list_filters_and_detail` (existente), `test_manager_requires_authentication`; el 404 no se cubre directamente. |
| `PATCH /api/incidents/{incident_id}/status` | Transición permitida → `200`. | Transición no permitida → `400`, campo `status` y mensaje seguro; ID inexistente → `404` implementado pero no probado por el test manager; sin auth → `401`. | `test_status_transitions_are_restricted` (transición válida e inválida), `test_manager_requires_authentication`. |

#### API de suppliers (protegida)

`test_supplier_api.py` usa un admin falso por override de dependencia para aislar el router; `test_auth_unit5.py` contrasta la protección sin token, con token inválido y con acceso autorizado.

| Endpoint | Camino feliz | Casos límite / modos de fallo | Tests concretos y comportamiento esperado |
|---|---|---|---|
| `POST /api/suppliers` | Alta válida → `201`, ID y `updated_at`. | País/moneda incompatible, categoría desconocida, tarifa no positiva o estado `deleted` → `422`; sin/token inválido → `401`. | `test_supplier_api.py::test_create_valid_supplier_generates_id_and_updated_at`, `test_create_rejects_invalid_supplier_data`; `test_auth_unit5.py::test_create_supplier_no_token_returns_401`, `test_create_supplier_invalid_token_returns_401`, `test_create_supplier_with_valid_token_returns_201`. |
| `GET /api/suppliers` | Lista `200`; filtra por país o categoría por separado. | País inválido → `422`; combinación de filtros no probada; sin token → `401`. | `test_list_and_filters`; `test_auth_unit5.py::test_list_suppliers_no_token_returns_401`, `test_list_suppliers_invalid_token_returns_401`, `test_list_suppliers_with_valid_token_returns_200`. |
| `GET /api/suppliers/{supplier_id}` | Existente → `200`. | Inexistente → `404`; sin/token inválido → `401`. | `test_get_by_id_and_missing_id`; `test_auth_unit5.py::test_get_supplier_no_token_returns_401`, `test_get_supplier_invalid_token_returns_401`, `test_get_supplier_with_valid_token_returns_200_or_404`. |
| `PATCH /api/suppliers/{supplier_id}/rate` | Tarifa positiva actualiza valor y `updated_at` → `200`. | Tarifa no positiva → `422`; ID inexistente → `404`; sin/token inválido → `401`. | `test_update_rate_changes_updated_at_and_rejects_non_positive_rate`; `test_auth_unit5.py::test_update_rate_no_token_returns_401`, `test_update_rate_invalid_token_returns_401`, `test_update_rate_with_valid_token_returns_200_or_404`. |
| `PATCH /api/suppliers/{supplier_id}/status` | Estado válido → `200`, supplier se conserva. | `deleted` → `422`; ID inexistente → `404`; sin/token inválido → `401`. | `test_update_status_validates_and_preserves_supplier`; `test_auth_unit5.py::test_update_status_no_token_returns_401`, `test_update_status_invalid_token_returns_401`, `test_update_status_with_valid_token_returns_200_or_404`. |
| `DELETE /api/suppliers/{supplier_id}` | Borrado → `204` y deja de existir. | ID inexistente/borrado → `404`; sin/token inválido → `401`. | `test_delete_removes_supplier_and_returns_not_found_afterwards`; `test_auth_unit5.py::test_delete_supplier_no_token_returns_401`, `test_delete_supplier_invalid_token_returns_401`, `test_delete_supplier_with_valid_token_returns_204_or_404`. |

#### API de autenticación, usuarios y perfiles

| Endpoint | Camino feliz | Casos límite / modos de fallo | Tests concretos y comportamiento esperado |
|---|---|---|---|
| `POST /api/auth/login` | Formulario OAuth2 válido → `200`, JWT bearer. | Contraseña incorrecta, usuario inexistente/inactivo → `401` genérico y `WWW-Authenticate: Bearer`; no requiere token previo. | `test_auth_unit4.py::AuthLoginTests`: `test_login_valid_credentials_returns_token`, `test_login_returns_token_type_bearer`, `test_login_wrong_password_returns_401`, `test_login_nonexistent_email_returns_401`, `test_login_inactive_user_returns_401`, `test_login_does_not_require_bearer`, `test_login_is_oauth2_compatible`; servicio: `test_auth_unit3.py::AuthServiceTests`. |
| `GET /api/auth/me` | Token válido → `200`, datos seguros, perfil presente o `null`, sin password hash. | Sin/invalid/expired token, subject incorrecto o usuario inactivo → `401` con semántica Bearer. | `test_auth_unit4.py::AuthMeTests` (válido, campos, perfil, ausencia de hash y token inválido/ausente); `test_auth_unit3.py::GetCurrentUserTests` y `AuthHttpSemanticTests` (motivos adicionales de 401 y `WWW-Authenticate`). |
| `POST /api/auth/forgot-password` | Siempre `200` genérico sin revelar existencia de la cuenta; fallo del proveedor conserva la respuesta. | Tres peticiones/hora permitidas, contador por email y vencimiento; usuario inactivo también respuesta genérica. | `test_auth_password_reset.py`: `test_forgot_password_always_returns_generic_200`, `test_forgot_password_rate_limit_allows_three_requests_per_hour`, `test_rate_limit_has_own_counter_per_email_and_expires_after_one_hour`, `test_forgot_password_is_generic_for_inactive_accounts_too`, `test_forgot_password_stays_generic_when_email_provider_fails`, `test_reset_email_contains_html_content_and_link`, `test_audit_log_records_request_and_success_without_secrets`. |
| `POST /api/auth/reset-password` | Token válido → `200`, respuesta sin token/password; JWT previo se invalida y nuevo login funciona. | Expirado/usado/invalidado o usuario inactivo/eliminado → `400 Invalid or expired reset token`; confirmación distinta se rechaza por schema; concurrencia de dos consumos tiene un éxito y un rechazo esperados pero es intermitente. | `test_auth_password_reset.py`: `test_reset_stores_only_token_hash_and_is_one_time`, `test_expired_token_is_rejected`, `test_new_reset_token_invalidates_the_previous_token`, `test_reset_response_does_not_expose_token_or_password`, `test_reset_invalidates_existing_jwt`, `test_reset_password_rejects_inactive_user`, `test_reset_password_rejects_nonexistent_user`, `test_concurrent_consumption_allows_only_one_reset`; schema: `test_auth_unit1.py::AuthSchemasTests::test_password_reset_request_rejects_mismatch`. |
| `POST /api/auth/change-password` | Contraseña actual válida → `200`; nueva contraseña autentica e invalida JWT previo. | Contraseña actual incorrecta → `400`; fallo de actualización probado a nivel de servicio; confirmación distinta probada por schema. Requiere auth. | `test_auth_password_reset.py::test_change_password_requires_current_password_and_invalidates_jwt` (400 y 200, efectos), `test_change_password_rejects_update_password_failure` (servicio), `test_auth_unit1.py::AuthSchemasTests::test_change_password_request_rejects_mismatch` (schema). |
| `POST /api/users` | Registro público → `201`; password hasheado, perfil opcional, sin hash en respuesta. | Email duplicado/concurrente → `409`; overrides role/is_active rechazados; fallo perfil compensa borrando usuario y devuelve `500`. | `test_auth_unit4.py::CreateUserTests`: `test_create_user_without_auth`, `test_create_user_password_is_hashed`, `test_create_user_response_no_hashed_password`, `test_create_user_default_role_is_user`, `test_public_registration_rejects_role_and_active_overrides`, `test_duplicate_registration_returns_409_without_creating_user`, `test_concurrent_duplicate_registration_is_serialized_in_one_process`, `test_create_user_with_profile`, `test_create_user_without_profile_works`, `test_profile_failure_reverts_user_without_exposing_error`, `test_profile_failure_logs_incomplete_rollback_without_sensitive_data`. |
| `GET /api/users` | Autenticado → `200`, campos seguros sin hashes. | Sin token → `401`. | `test_auth_unit4.py::ListUsersTests`: `test_list_users_authenticated_returns_200`, `test_list_users_without_token_returns_401`, `test_list_users_no_hashed_password`, `test_list_users_returns_correct_fields`. |
| `GET /api/users/{user_id}` | Self o admin → `200`. | Otro user/manager → `403`; inexistente → `404`; sin token → `401`; sin hash en respuesta. | `test_auth_unit4.py::GetUserTests`: `test_self_can_get_own_user`, `test_admin_can_get_any_user`, `test_user_cannot_get_another_user`, `test_manager_cannot_get_another_user`, `test_get_nonexistent_user_returns_404`, `test_get_user_without_token_returns_401`, `test_get_user_no_hashed_password`. |
| `PUT /api/users/{user_id}` | Self actualiza email; admin modifica otro usuario/rol permitido. | Email duplicado o último admin → `409`; autorización/rol propio → `403`; inexistente → `404`; admin no cambia su propio rol. | `test_auth_unit4.py::UpdateUserTests`: tests de self/admin, duplicado, permisos y roles, último admin, inexistente y respuesta sin hash; incluye `test_update_maps_last_admin_error_to_409`. |
| `DELETE /api/users/{user_id}` | Self/admin → `204`, perfil en cascada eliminado. | No autorizado → `403`; inexistente → `404`; último admin → `409`; fallo cleanup/borrado/excepción → `500`, no `204`. | `test_auth_unit4.py::DeleteUserTests`: `test_self_can_delete_self`, `test_admin_can_delete_other_user`, `test_user_cannot_delete_another_user`, `test_manager_cannot_delete_another_user`, `test_delete_nonexistent_user_returns_404`, `test_delete_user_also_deletes_profile`, `test_delete_user_does_not_return_204_if_user_delete_fails`, `test_delete_user_stops_if_profile_cleanup_fails`, `test_delete_without_token_returns_401`, `test_last_active_admin_cannot_be_deleted_and_profile_is_kept`, `test_delete_user_unexpected_exception_returns_500`. |
| `GET /api/profiles/me` | Perfil existente del usuario autenticado → `200`. | Ausente → `404`; sin token → `401`; fallo persistencia → `500` genérico. | `test_auth_unit4.py::GetProfileMeTests`: `test_get_profile_me_authenticated_with_profile`, `test_get_profile_me_returns_correct_data`, `test_get_profile_me_without_profile_returns_404`, `test_get_profile_me_without_token_returns_401`, `test_get_profile_me_persistence_error_returns_generic_500`. |
| `PUT /api/profiles/me` | Actualiza nombre/teléfono/dirección o crea perfil ausente → `200`. | `user_id` no permitido → `422`; sin token → `401`; error persistencia → `500`; race duplicate → `409`. | `test_auth_unit4.py::UpdateProfileMeTests`: actualizaciones de campos, `test_update_profile_prevents_user_id_change`, `test_update_profile_without_token_returns_401`, `test_update_profile_without_profile_creates_it`, tests de error y `test_race_condition_create_duplicate_profile_returns_409`. |

### 3.6 Casos no cubiertos o pendientes

- **Gestor de incidentes, lista**: `test_incident_manager.py::test_create_list_filters_and_detail` comprueba solo `branch`. No ejercita por HTTP `status`, `origin`, `category`, sus combinaciones ni valores inválidos.
- **Gestor de incidentes, detalle/estado**: la implementación devuelve `404` para ID inexistente, pero no hay test HTTP que compruebe `GET /api/incidents/{id}` o `PATCH /api/incidents/{id}/status` con un ID inexistente. Tampoco se prueba un resumen no vacío con todas las dimensiones.
- **Incidentes: ficheros/rutas pendientes**: no se prueban todos los límites de tamaño de upload ni los errores de lectura a mitad del stream; los tests HTTP cubren upload vacío, extensión no CSV, estructura malformada y fallo inesperado genérico.
- **Supplier Directory, filtros combinados**: `test_supplier_api.py::test_list_and_filters` prueba país y categoría por separado, no ambos a la vez ni variantes de mayúsculas/minúsculas.
- **Supplier Directory, persistencia y roles**: los tests de API ejercitan el router con un admin falso; no prueban en HTTP la matriz completa de roles (user/manager/admin), concurrencia entre procesos ni durabilidad tras reiniciar la app.
- **CORS**: `test_auth_cors.py` comprueba dos preflights (PUT perfiles y POST usuarios), no todas las rutas ni todos los headers/métodos permitidos.
- **Email externo**: `test_auth_email.py` usa un proveedor simulado; no realiza llamadas reales a Resend ni prueba credenciales/entregabilidad de producción.
- **CLI/seeder**: hay pruebas de rutas y entradas inválidas y de persistencia con base temporal, pero no se verifica una ejecución operativa en producción ni recuperación transaccional completa tras interrupción del proceso.
- **CSV externo**: sin `scripts/incidents-nexova.csv`, fallan los casos que lo leen directamente; en `test_api.py` y `test_results_export_api.py` su lectura en `setUpClass` impide ejecutar también los casos sintéticos de esas clases. Véase la lista precisa en §3.4.
- **Cobertura de código**: el 99% statements / 98% branches de §3.3 corresponde exclusivamente a `app.auth` con `--cov=app.auth`. No se ha medido una cifra equivalente aquí para `app.incidents`, `app.suppliers`, `app.main` ni `scripts/`. Tener tests no equivale a una cifra de cobertura.
- **Alcance de tests no HTTP**: los casos de modelos, schemas, servicios y repositorios no prueban códigos HTTP; el app mínimo de `test_auth_unit3.py` tampoco sustituye pruebas de las rutas reales. El sender de email es falso y no contacta un proveedor.
- **Concurrencia**: `test_concurrent_consumption_allows_only_one_reset` prueba el servicio con dos hilos, no clientes HTTP concurrentes ni coordinación entre procesos/workers. Es intermitente por TinyDB (§6.1 y §6.2).

---

## 4. Cobertura

### Resumen consolidado

| Ámbito | Tests | Statements | Branches | Functions | Lines |
|---|---|---|---|---|---|
| TypeScript (utilidades) | 111 | 100% | 100% | 100% | 100% |
| Python auth (`app.auth`) | 248 | 99% | 98% | — | — |

La cifra de Python es **cobertura de código medida** exclusivamente con `--cov=app.auth`; no implica que las otras suites tengan el mismo nivel de cobertura. Para el detalle de alcance y las áreas no medidas, véanse [§3.3](#33-cobertura-del-módulo-appauth) y [§3.6](#36-casos-no-cubiertos-o-pendientes).

### Cómo reproducir la cobertura

**TypeScript**:
```bash
npm run test:coverage
```

**Python (auth)**:
```bash
cd services/api
python -m pytest tests/ -v --tb=short --cov=app.auth --cov-branch --cov-report=term-missing
```

---

## 5. Configuración

### Jest (`jest.config.cjs`)

- **Ubicación**: raíz del repositorio.
- **Incluye**: `src/utils/__tests__/**/*.test.ts`; entorno `node`.
- **Transformación**: `@swc/jest` transpila TypeScript a CommonJS para Jest. Se usa SWC en vez de `ts-jest` porque la versión disponible de `ts-jest` declara `typescript: >=4.3 <7`, incompatible con el TypeScript 7 del repositorio. SWC transpila, pero no reemplaza una comprobación de tipos.
- **Cobertura**: instrumentación nativa de Jest, incluye `src/utils/*.ts`, excluye `src/utils/__tests__/**`, reporters `['text', 'text-summary']` y salida en `./coverage`.
- **Módulos**: la configuración `.cjs` mantiene CommonJS de configuración, mientras que SWC transforma los imports de los tests para ejecutarlos en Jest.

### pytest (pyproject.toml del API)

- **Ubicación**: `services/api/pyproject.toml`
- `[project.optional-dependencies] test` declara solo `httpx>=0.27,<1`, requerido por `TestClient`; se instala con `python -m pip install -e ".[test]"`.
- Las herramientas de desarrollo se declaran en `[dependency-groups] dev` (PEP 735), que `uv` reconoce, pero pip no instala mediante el extra `test`:
  ```toml
  [dependency-groups]
  dev = ["httpx>=0.28.1", "pytest>=9.1.1", "pytest-cov>=7.1.0"]
  ```
- Para instalar ese grupo desde `services/api/`, usar `uv sync --group dev`. Sin `uv`, instalar `pytest`, `pytest-cov` e `httpx` explícitamente con pip, además del paquete editable de la API y la dependencia local `nexova-shared` (véase §3.2).

---

## 6. Limitaciones conocidas

### 6.1 Test de concurrencia del reseteo de contraseña

**Fichero**: `tests/test_auth_password_reset.py`
**Test**: `test_concurrent_consumption_allows_only_one_reset`

**Síntoma**: Falla intermitentemente cuando se ejecuta en la suite completa (`JSONDecodeError`), pero pasa cuando se ejecuta en aislamiento.

**Causa raíz**: El test lanza dos hilos (`threading.Thread`) que compiten por consumir el mismo token de reseteo. TinyDB (base de datos subyacente) **no es thread-safe a nivel de fichero**: ambos hilos intentan leer/escribir `db.json` simultáneamente, lo que produce un `JSONDecodeError` cuando un hilo lee el fichero mientras el otro lo está escribiendo.

**Estado**: Preexistente (commit `15c08fa`, 2026-10-07). No es una regresión de fases posteriores.

**Alternativa**: Para verificar la lógica de doble consumo sin el problema de concurrencia, se puede llamar al servicio dos veces de forma secuencial — el endpoint ya rechaza el segundo consumo.

### 6.2 TinyDB y concurrencia

TinyDB usa un bloqueo por proceso (`threading.Lock`) que no coordina múltiples workers/processos. Cualquier test que use `threading` para simular concurrencia sobre TinyDB puede fallar intermitentemente.

### 6.3 Test CSV — dataset externo

La dependencia del fichero `scripts/incidents-nexova.csv` varía por suite:

- `test_analysis.py::test_dataset_matches_expected_unit_four_metrics`, `test_csv_reader.py::test_csv_dataset_has_expected_row_count` y los tres tests de `test_export.py` leen el dataset directamente.
- Todos los tests de `test_api.py` y `test_results_export_api.py` requieren el fichero porque sus clases lo leen en `setUpClass`, aunque algunos casos envíen luego CSV sintético.
- En `test_cli.py`, dependen del fichero los casos de análisis del dataset, fin de entrada y exportación sí/no; la ruta inválida y la interrupción simulada no necesitan leerlo.
- En `test_seed_incidents.py`, lo requieren las pruebas de escritura parcial e idempotencia/preservación; las pruebas de entrada ausente o persistencia simulada no.

Si falta el fixture, los fallos de lectura no indican por sí solos un defecto en la lógica analizada. Las pruebas unitarias que usan CSV sintético y no dependen de una clase que cargue el dataset siguen siendo independientes de ese fichero.

---

## 7. Solución de problemas

### TypeScript: test:coverage da 0% o no encuentra ficheros

- Verificar que `jest.config.cjs` existe en la raíz.
- Verificar que los ficheros fuente están en `src/utils/*.ts` y los tests en `src/utils/__tests__/*.test.ts`.
- Ejecutar `npx jest --coverage --runInBand` directamente para ver logs de depuración.

### Python: ModuleNotFoundError (pytest, httpx, etc.)

```bash
# Opción A (uv), desde services/api:
uv sync --group dev
uv run python -m pytest tests/ -v

# Opción B (pip), desde la raíz del repositorio:
python -m pip install -e packages/shared/python
cd services/api
python -m pip install -e .
python -m pip install "pytest>=9.1.1" "pytest-cov>=7.1.0" "httpx>=0.28.1"
python -m pytest tests/ -v
```

### Python: tests auth dan 0% de cobertura

Asegurarse de que `--cov=app.auth` se pasa a pytest. Si se ejecuta desde la raíz, la cobertura puede no encontrar el módulo porque el `sys.path` no incluye `services/api`.

### Dependencia nexova-shared no encontrada

```bash
# Desde la raíz del repositorio, instalar la dependencia local antes que la API:
python -m pip install -e packages/shared/python
cd services/api
python -m pip install -e .
```
