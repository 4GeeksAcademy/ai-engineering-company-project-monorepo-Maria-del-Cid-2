# Plan integral de telemetría para Nexova

> **Estado:** Fase 4 — Documentación definitiva (pendiente de aprobación de decisiones de negocio para implementación).
> **Archivo relacionado:** `event-schemas.json` — contratos JSON de los 20 eventos + auxiliares.

---

## Índice

1. [Objetivo y alcance](#1-objetivo-y-alcance)
2. [Arquitectura propuesta](#2-arquitectura-propuesta-d1)
3. [Catálogo de eventos (20 principales + auxiliares)](#3-catálogo-de-eventos)
4. [Contratos de evento (envelope CloudEvents 1.0)](#4-contratos-de-evento)
5. [Métricas A1–A11](#5-métricas-a1a11)
6. [Evaluación de privacidad](#6-evaluación-de-privacidad)
7. [Dependencias contractuales con el modelo de datos](#7-dependencias-contractuales)
8. [Tabla de decisiones D1–D16](#8-tabla-de-decisiones)
9. [Anexo: dependencias de desarrollo](#9-anexo-dependencias-de-desarrollo)

---

## 1. Objetivo y alcance

### 1.1 Objetivo general

Diseñar un sistema de telemetría para Nexova que permita medir resultados de negocio y salud técnica de la aplicación, basado exclusivamente en el análisis del repositorio y la funcionalidad existente.

### 1.2 Restricciones de diseño

- **No existe infraestructura de telemetría hoy** en el repositorio.
- **No existen workers, colas, schedulers ni cron jobs**.
- La base de datos operativa es **PostgreSQL (Supabase)** para inventario y **TinyDB** (JSON flat file) para auth, incidents y suppliers.
- El backend es **FastAPI (Python)** con **SQLModel/SQLAlchemy**.
- El frontend es **Next.js/TypeScript**.
- La caché existente es **TTLCache** en memoria.
- El middleware existente es **TimingMiddleware** (logs method, path, status, duration_ms; no lee body, Authorization ni IP).

### 1.3 Convenciones del documento

| Notación | Significado |
|---|---|
| ✅ **Propuesta técnica definida** | El diseño está completo; puede implementarse. |
| ⏳ **Pendiente de aprobación** | Requiere decisión de negocio. |
| ❌ **Requiere desarrollo** | Dependencia técnica que no existe hoy. |
| *Cursiva* | Evento auxiliar (fuera del catálogo principal de 20). |

---

## 2. Arquitectura propuesta (D1)

### 2.1 Diagrama de flujo

```
Cliente (Next.js)             Backend (FastAPI)              PostgreSQL
      │                             │                           │
      │  POST /api/telemetry/event   │                           │
      │─────────────────────────────>│                           │
      │                             │  Valida envelope           │
      │                             │  (CloudEvents 1.0)         │
      │                             │  Valida schema (Pydantic)  │
      │                             │  Asigna ingested_at        │
      │                             │  INSERT con idempotency    │
      │                             │──────────────────────────>│
      │                             │                           │
      │  201 Created / 409 Conflict  │                           │
      │<─────────────────────────────│                           │
```

### 2.2 Tabla propuesta

```sql
CREATE TABLE IF NOT EXISTS telemetry_events (
    id              BIGSERIAL       PRIMARY KEY,
    specversion     VARCHAR(5)      NOT NULL DEFAULT '1.0',
    source          VARCHAR(255)    NOT NULL,
    type            VARCHAR(100)    NOT NULL,
    idempotency     UUID            NOT NULL,
    time            TIMESTAMPTZ     NOT NULL,
    datacontenttype VARCHAR(50)     DEFAULT 'application/json',
    data            JSONB           NOT NULL,
    traceparent     VARCHAR(55),
    ingested_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_telemetry_events_idempotency UNIQUE (idempotency)
);

CREATE INDEX idx_telemetry_events_type_time
    ON telemetry_events (type, time);
CREATE INDEX idx_telemetry_events_source_time
    ON telemetry_events (source, time);
```

### 2.3 Aspectos verificados y no verificados

| Aspecto | Estado | Detalle |
|---|---|---|
| Conexión PostgreSQL | ✅ Verificada | Configurada vía `DATABASE_URL` + `create_engine()` con `pool_pre_ping=True`. Engine lazy (`lru_cache`). |
| Disponibilidad de PostgreSQL | ❌ No verificado | La instancia es externa (Supabase). No hay contenedor PostgreSQL en `docker-compose.yml`. |
| Validación de eventos | ⚠️ Propuesta | Usar Pydantic (disponible en el stack) para validar envelope + schema de cada evento antes de insertar. No existe hoy. |
| Manejo de errores de persistencia | ⚠️ Propuesta | Si falla la inserción: log local + reintento. No bloquear la petición original. No implementado. |
| Estrategia de reintentos | ✅ Propuesta definida | `INSERT ... ON CONFLICT (idempotency) DO NOTHING`. El UUID idempotency evita duplicados en reintentos. |
| Garantía de entrega | ❌ **Best-effort explícito** | El endpoint síncrono no garantiza entrega. Si el backend falla entre la recepción y la escritura, el evento se pierde. Para garantía se necesitaría un buffer externo (Redis Streams, Kafka) en una fase posterior. |

### 2.4 Alternativas evaluadas y descartadas para la fase inicial

| Alternativa | Motivo del descarte |
|---|---|
| Apache Kafka | Overkill para monorepo sin workers ni streaming. Requiere Zookeeper/KRaft, otro contenedor, especialización operativa. |
| Redis Streams | Buena opción futura como buffer, pero añade dependencia externa sin necesidad actual. |
| RabbitMQ | Orientado a colas de trabajo, no a eventos de telemetría. |
| HTTP externo (SaaS) | Posible en fase de producción. Para desarrollo inicial el endpoint interno es suficiente. |
| TinyDB | No soporta concurrencia, JSONB, ni consultas analíticas. |

---

## 3. Catálogo de eventos

### 3.1 Catálogo principal (20 eventos)

| # | `event_type` | Categoría | Clasificación | Funcionalidad subyacente | ¿Emisible hoy? | Frecuencia esperada |
|---|---|---|---|---|---|---|
| 1 | `inbound_order_created` | inventory | **Obligatorio** | `POST /api/inventory/orders/inbound` | ✅ Sí (backend) | Baja |
| 2 | `outbound_order_created` | inventory | **Obligatorio** | `POST /api/inventory/orders/outbound` | ✅ Sí (backend) | Baja–media |
| 3 | `stock_threshold_triggered` | inventory | **Obligatorio** | Umbrales mínimos (solo frontend visual) | ❌ No (sin backend) | Media |
| 4 | `direct_stock_edit_rejected` | inventory | **Obligatorio** | Trazabilidad (solo órdenes autorizadas) | ❌ No (sin intento) | Muy baja |
| 5 | `kit_cost_variance_detected` | inventory | **Adicional** | Catálogo con costes (no existe) | ❌ No (sin datos) | Baja |
| 6 | `login_succeeded` | auth | **Adicional** | Backend auth existente | ✅ Sí (backend) | Alta |
| 7 | `login_failed` | auth | **Adicional** | Backend auth existente | ✅ Sí (backend) | Media |
| 8 | `account_created` | auth | **Adicional** | Backend auth existente | ✅ Sí (backend) | Baja |
| 9 | `session_expired` | auth | **Adicional** | Backend auth (JWT expira) | ✅ Sí (backend) | Media |
| 10 | `api_request_completed` | infra | **Adicional** | TimingMiddleware existente | ✅ Sí (backend) | Muy alta |
| 11 | `unhandled_api_error` | infra | **Adicional** | Excepciones no capturadas | ✅ Sí (backend) | Baja |
| 12 | `frontend_render_error` | frontend | **Adicional** | Error boundaries (no existen) | ❌ No (sin frontend) | Baja |
| 13 | `frontend_page_loaded` | frontend | **Adicional** | Navegación Next.js | ❌ No (sin frontend) | Alta |
| 14 | `form_validation_failed` | frontend | **Adicional** | Validación frontend existente | ❌ No (sin frontend) | Media |
| 15 | `section_viewed` | frontend | **Adicional** | Secciones de UI (no implementado) | ❌ No (sin frontend) | Alta |
| 16 | `form_abandoned` | frontend | **Adicional** | Heartbeat + detección (no existe) | ❌ No (sin frontend) | Media |
| 17 | `candidate_record_created` | talent | **Adicional** | Módulo talento (no localizado) | ❌ No (sin backend) | Baja |
| 18 | `incident_analysis_completed` | incidents | **Adicional** | `GET /api/incidents/analysis` | ✅ Sí (backend) | Baja |
| 19 | `incident_status_changed` | incidents | **Adicional** | `PATCH /api/incidents/{id}/status` | ✅ Sí (backend) | Media |
| 20 | `supplier_rate_updated` | suppliers | **Adicional** | `PATCH /api/suppliers/{id}/rate` | ✅ Sí (backend) | Baja |

**Eventos emitibles hoy sin cambios:** 11 (eventos 1, 2, 6, 7, 8, 9, 10, 11, 18, 19, 20).

### 3.2 Eventos auxiliares (fuera del catálogo principal)

| `event_type` | Categoría | Propósito | Dependencia |
|---|---|---|---|
| `form_opened` | frontend | Soporte para métrica A6 (tasa de abandono) | Requiere heartbeat + detección de cierre |

---

## 4. Contratos de evento

### 4.1 Envelope común (CloudEvents 1.0)

```json
{
  "specversion": "1.0",
  "source": "/nexova/inventory",
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "type": "inbound_order_created",
  "time": "2026-10-29T12:00:00.000Z",
  "datacontenttype": "application/json",
  "data": { },
  "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
}
```

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `specversion` | `string` | ✅ | Versión del envelope. Fijo `"1.0"`. |
| `source` | `string` (URI) | ✅ | Origen del evento. Ej. `/nexova/inventory`, `/nexova/auth`, `/nexova/incidents`, `/nexova/suppliers`, `/nexova/frontend`, `/nexova/infra`. |
| `id` | `string` (UUID) | ✅ | Identificador único del evento (idempotencia). |
| `type` | `string` | ✅ | `event_type` del catálogo. |
| `time` | `string` (RFC 3339) | ✅ | Timestamp del momento en que ocurrió el hecho. |
| `datacontenttype` | `string` | No | Tipo MIME del contenido. Por defecto `"application/json"`. |
| `data` | `object` | ✅ | Payload específico del evento (ver contratos abajo). |
| `traceparent` | `string` | No | Identificador de traza distribuida (W3C Trace Context). |

### 4.2 Contratos por evento

#### Evento 1 — `inbound_order_created`

```json
{
  "data": {
    "product_id": 42,
    "product_sku": "NXV-IT-001",
    "product_category": "training_kit",
    "programme_id": "prog-onboarding-q1-2027",
    "quantity": 10.0,
    "supplier": "TechDistrib Valencia S.L.",
    "office": "Valencia",
    "currency": "EUR",
    "unit_cost": null,
    "user_uuid": "f1a2b3c4-d5e6-7890-abcd-ef1234567890"
  }
}
```

| Propiedad | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `product_id` | `integer` | ✅ | ID del producto (`Asset.id`). |
| `product_sku` | `string` | ✅ | SKU del producto (`Asset.sku`). |
| `product_category` | `string` | ✅ | Categoría funcional (`training_kit`, `certification`, `onboarding_equipment`, etc.). |
| `programme_id` | `string` | No | Programa asociado. No existe en el modelo actual. |
| `quantity` | `number` | ✅ | Cantidad recibida (`AssetEntry.quantity`). |
| `supplier` | `string` | ✅ | Nombre del proveedor (`AssetEntry.supplier`). |
| `office` | `string` | ✅ | Oficina de destino (`AssetEntry.office`). |
| `currency` | `string` | ✅ | Moneda del coste (`EUR` / `USD`). No existe en `AssetEntry` hoy (tomado del proveedor). |
| `unit_cost` | `number` | No | Coste unitario por producto. No existe hoy. `null` hasta que se implemente (véase D9). |
| `user_uuid` | `string` (UUID) | ✅ | Usuario que realizó la entrada (`AssetEntry.user_uuid`). |

#### Evento 2 — `outbound_order_created`

```json
{
  "data": {
    "product_id": 42,
    "product_sku": "NXV-IT-001",
    "product_category": "training_kit",
    "programme_id": "prog-onboarding-q1-2027",
    "quantity": 2.0,
    "exit_type": "allocation",
    "office": "Valencia",
    "user_uuid": "f1a2b3c4-d5e6-7890-abcd-ef1234567890"
  }
}
```

| Propiedad | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `product_id` | `integer` | ✅ | ID del producto (`Asset.id`). |
| `product_sku` | `string` | ✅ | SKU del producto (`Asset.sku`). |
| `product_category` | `string` | ✅ | Categoría funcional. |
| `programme_id` | `string` | No | Programa asociado. No existe en el modelo actual. |
| `quantity` | `number` | ✅ | Cantidad de salida (`AssetExit.quantity`). |
| `exit_type` | `string` | ✅ | Tipo de salida (`allocation` / `consumption`). |
| `office` | `string` | ✅ | Oficina de origen (`AssetExit.office`). |
| `user_uuid` | `string` (UUID) | ✅ | Usuario que autorizó la salida (`AssetExit.user_uuid`). |

#### Evento 3 — `stock_threshold_triggered`

```json
{
  "data": {
    "product_id": 42,
    "product_sku": "NXV-IT-001",
    "product_category": "training_kit",
    "office": "Valencia",
    "current_stock": 3.0,
    "threshold": 5.0,
    "stock_level": "low"
  }
}
```

| Propiedad | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `product_id` | `integer` | ✅ | ID del producto. |
| `product_sku` | `string` | ✅ | SKU del producto. |
| `product_category` | `string` | ✅ | Categoría funcional. |
| `office` | `string` | ✅ | Oficina (`Asset.office`). |
| `current_stock` | `number` | ✅ | Stock derivado tras el movimiento (`SUM(entries) - SUM(exits)`). |
| `threshold` | `number` | ✅ | Umbral mínimo configurado para ese producto-oficina. **No existe hoy en backend** (solo en frontend: `stockLevelFor()` con healthy=8, low=2). |
| `stock_level` | `string` | ✅ | Nivel (`healthy` / `low` / `out`). |

#### Evento 4 — `direct_stock_edit_rejected`

```json
{
  "data": {
    "product_id": 42,
    "product_sku": "NXV-IT-001",
    "attempted_action": "set_stock",
    "reason": "direct_stock_edit_not_permitted",
    "user_uuid": "f1a2b3c4-d5e6-7890-abcd-ef1234567890"
  }
}
```

| Propiedad | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `product_id` | `integer` | ✅ | ID del producto. |
| `product_sku` | `string` | ✅ | SKU del producto. |
| `attempted_action` | `string` | ✅ | Acción rechazada. |
| `reason` | `string` | ✅ | Motivo del rechazo. |
| `user_uuid` | `string` (UUID) | ✅ | Usuario que intentó la acción. |

#### Evento 5 — `kit_cost_variance_detected`

```json
{
  "data": {
    "product_id": 42,
    "product_sku": "NXV-IT-001",
    "product_category": "training_kit",
    "kit_composition": ["NXV-IT-001", "NXV-PER-001"],
    "expected_cost": 850.00,
    "actual_cost": 920.50,
    "variance_percent": 8.29,
    "currency": "EUR",
    "office": "Valencia"
  }
}
```

| Propiedad | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `product_id` | `integer` | ✅ | ID del kit/producto compuesto. |
| `product_sku` | `string` | ✅ | SKU del kit. |
| `product_category` | `string` | ✅ | Categoría (`training_kit`, `certification`, `onboarding_equipment`). |
| `kit_composition` | `array[string]` | No | Lista de SKUs que componen el kit. |
| `expected_cost` | `number` | ✅ | Coste esperado del kit. |
| `actual_cost` | `number` | ✅ | Coste real calculado. |
| `variance_percent` | `number` | ✅ | Diferencia porcentual. |
| `currency` | `string` | ✅ | Moneda. |
| `office` | `string` | ✅ | Oficina. |

#### Evento 6 — `login_succeeded`

```json
{
  "data": {
    "user_uuid": "f1a2b3c4-d5e6-7890-abcd-ef1234567890"
  }
}
```

#### Evento 7 — `login_failed`

```json
{
  "data": {
    "user_uuid": "f1a2b3c4-d5e6-7890-abcd-ef1234567890",
    "failure_reason": "invalid_credentials"
  }
}
```

| Propiedad | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `user_uuid` | `string` (UUID) | ✅ | Usuario que intentó el login (seudonimizado). |
| `failure_reason` | `string` | No | Motivo del fallo (`invalid_credentials`, `account_locked`, `account_disabled`). |

#### Evento 8 — `account_created`

```json
{
  "data": {
    "user_uuid": "f1a2b3c4-d5e6-7890-abcd-ef1234567890"
  }
}
```

#### Evento 9 — `session_expired`

```json
{
  "data": {
    "user_uuid": "f1a2b3c4-d5e6-7890-abcd-ef1234567890",
    "session_duration_seconds": 3540
  }
}
```

| Propiedad | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `user_uuid` | `string` (UUID) | ✅ | Usuario de la sesión expirada. |
| `session_duration_seconds` | `integer` | No | Duración de la sesión en segundos. |

#### Evento 10 — `api_request_completed`

```json
{
  "data": {
    "method": "POST",
    "path": "/api/inventory/orders/inbound",
    "status_code": 201,
    "duration_ms": 145
  }
}
```

| Propiedad | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `method` | `string` | ✅ | Método HTTP (`GET`, `POST`, `PATCH`, `DELETE`). |
| `path` | `string` | ✅ | Ruta del endpoint (sin query params). |
| `status_code` | `integer` | ✅ | Código de respuesta HTTP. |
| `duration_ms` | `integer` | ✅ | Duración de la petición en milisegundos. |

> **Nota de privacidad:** No se incluyen body, Authorization, IP, ni query params. Coherente con `TimingMiddleware` existente.

#### Evento 11 — `unhandled_api_error`

```json
{
  "data": {
    "method": "POST",
    "path": "/api/inventory/orders/inbound",
    "status_code": 500,
    "error_type": "IntegrityError",
    "error_message": "duplicate key value violates unique constraint"
  }
}
```

| Propiedad | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `method` | `string` | ✅ | Método HTTP. |
| `path` | `string` | ✅ | Ruta del endpoint. |
| `status_code` | `integer` | ✅ | Código de error HTTP (5xx). |
| `error_type` | `string` | ✅ | Tipo de la excepción. |
| `error_message` | `string` | No | Mensaje de error (sin datos sensibles). |

#### Evento 12 — `frontend_render_error`

```json
{
  "data": {
    "component": "InventoryCurrentStockPanel",
    "error_type": "TypeError",
    "error_message": "Cannot read properties of undefined"
  }
}
```

#### Evento 13 — `frontend_page_loaded`

```json
{
  "data": {
    "path": "/backoffice/inventory/products",
    "page_load_ms": 2340,
    "user_uuid": "f1a2b3c4-d5e6-7890-abcd-ef1234567890"
  }
}
```

#### Evento 14 — `form_validation_failed`

```json
{
  "data": {
    "form_id": "inbound-form",
    "field": "quantity",
    "validation_error": "must_be_positive",
    "instance_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901"
  }
}
```

| Propiedad | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `form_id` | `string` | ✅ | Identificador del formulario. |
| `field` | `string` | No | Campo que falló la validación. |
| `validation_error` | `string` | ✅ | Código del error de validación. |
| `instance_id` | `string` (UUID) | ✅ | Identificador de la instancia del formulario (para emparejar con A6). |

#### Evento 15 — `section_viewed`

```json
{
  "data": {
    "section_id": "inventory-products-list",
    "user_uuid": "f1a2b3c4-d5e6-7890-abcd-ef1234567890",
    "time_on_section_ms": 45000
  }
}
```

| Propiedad | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `section_id` | `string` | ✅ | Identificador de la sección. |
| `user_uuid` | `string` (UUID) | ✅ | Usuario que visualizó. |
| `time_on_section_ms` | `integer` | No | Tiempo estimado en la sección. |

#### Evento 16 — `form_abandoned`

```json
{
  "data": {
    "form_id": "inbound-form",
    "instance_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "abandon_reason": "navigation_away",
    "time_open_ms": 320000,
    "last_section": "step-2-details"
  }
}
```

| Propiedad | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `form_id` | `string` | ✅ | Identificador del formulario abandonado. |
| `instance_id` | `string` (UUID) | ✅ | Identificador de la instancia (para emparejar con `form_opened`). |
| `abandon_reason` | `string` | No | Causa (`navigation_away`, `tab_close`, `inactivity_timeout`, `browser_crash`). |
| `time_open_ms` | `integer` | No | Tiempo que el formulario estuvo abierto. |
| `last_section` | `string` | No | Última sección/interacción registrada. |

#### Evento 17 — `candidate_record_created`

```json
{
  "data": {
    "candidate_id": "cand-a1b2c3d4",
    "programme_id": "prog-onboarding-q1-2027",
    "source": "job_board"
  }
}
```

#### Evento 18 — `incident_analysis_completed`

```json
{
  "data": {
    "analysis_id": "3",
    "incident_count": 45,
    "top_category": "technical_failure",
    "analysis_duration_ms": 3200
  }
}
```

#### Evento 19 — `incident_status_changed`

```json
{
  "data": {
    "incident_id": 101,
    "from_status": "open",
    "to_status": "in_progress",
    "category": "technical_failure",
    "origin": "customer",
    "branch": "valencia_operations",
    "user_uuid": "f1a2b3c4-d5e6-7890-abcd-ef1234567890"
  }
}
```

| Propiedad | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `incident_id` | `integer` | ✅ | ID del incidente (`Incident.id`). |
| `from_status` | `string` | ✅ | Estado anterior. |
| `to_status` | `string` | ✅ | Nuevo estado. |
| `category` | `string` | ✅ | Categoría del incidente (`Incident.category`). |
| `origin` | `string` | ✅ | Origen (`Incident.origin`). |
| `branch` | `string` | ✅ | Sucursal (`Incident.branch`). |
| `user_uuid` | `string` (UUID) | No | Usuario que realizó el cambio. |

#### Evento 20 — `supplier_rate_updated`

```json
{
  "data": {
    "supplier_id": 5,
    "supplier_name": "TechDistrib S.L.",
    "old_rate": 5000.00,
    "new_rate": 5500.00,
    "currency": "EUR",
    "country": "Spain"
  }
}
```

| Propiedad | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `supplier_id` | `integer` | ✅ | ID del proveedor. |
| `supplier_name` | `string` | ✅ | Nombre del proveedor. |
| `old_rate` | `number` | ✅ | Tarifa mensual anterior (`Supplier.monthly_rate` previo). |
| `new_rate` | `number` | ✅ | Tarifa mensual nueva. |
| `currency` | `string` | ✅ | Moneda de la tarifa (`Supplier.currency`). |
| `country` | `string` | ✅ | País del proveedor (`Supplier.country`). |

#### Evento auxiliar — `form_opened`

```json
{
  "data": {
    "form_id": "inbound-form",
    "instance_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "user_uuid": "f1a2b3c4-d5e6-7890-abcd-ef1234567890"
  }
}
```

| Propiedad | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `form_id` | `string` | ✅ | Identificador del formulario. |
| `instance_id` | `string` (UUID) | ✅ | Identificador único de esta apertura (generado en el cliente). |
| `user_uuid` | `string` (UUID) | No | Usuario que abrió el formulario. |

---

## 5. Métricas A1–A11

### 5.1 Métricas obligatorias

#### A1 — Tasa de éxito de inicio de sesión

```
A1(período) = COUNT(login_succeeded) / COUNT(login_failed)  [ratio]
o bien:
A1_tasa_éxito = COUNT(login_succeeded) / (COUNT(login_succeeded) + COUNT(login_failed))
```

| Propiedad | Valor |
|---|---|
| Eventos fuente | `login_succeeded` (#6), `login_failed` (#7) |
| Frecuencia propuesta | Diaria |
| Decisión de negocio | **Pendiente (D6)** |
| Permite detectar | Intentos de acceso anómalos, problemas de autenticación |

#### A2 — Tasa de error de API

```
A2(período) = COUNT(unhandled_api_error) / COUNT(api_request_completed)  * 100
```

| Propiedad | Valor |
|---|---|
| Eventos fuente | `api_request_completed` (#10), `unhandled_api_error` (#11) |
| Frecuencia propuesta | Diaria |
| Decisión de negocio | **Pendiente (D6)** |
| Permite detectar | Degradación del backend, errores no controlados |

#### A3 — Latencia de API

```
A3(período) = P50, P95, P99 de api_request_completed.duration_ms
```

| Propiedad | Valor |
|---|---|
| Evento fuente | `api_request_completed` (#10) |
| Agrupación | Por endpoint (`path`), por código de estado (`status_code`) |
| Frecuencia propuesta | Diaria |
| Permite detectar | Cuellos de botella, endpoints lentos |

#### A4 — Tasa de errores de validación en formularios

```
A4(período, form_id) = COUNT(form_validation_failed) / COUNT(form_opened)
```

| Propiedad | Valor |
|---|---|
| Eventos fuente | `form_validation_failed` (#14), `form_opened` (auxiliar) |
| Agrupación | Por `form_id` |
| Frecuencia propuesta | Diaria |
| Decisión de negocio | **Pendiente (D6)** |
| Permite detectar | Formularios confusos, validaciones incorrectas |

#### A5 — Engagement por sección

```
A5(período, section_id) = COUNT(section_viewed)
A5_tiempo_medio(período, section_id) = AVG(section_viewed.time_on_section_ms)
```

| Propiedad | Valor |
|---|---|
| Evento fuente | `section_viewed` (#15) |
| Agrupación | Por `section_id` |
| Frecuencia propuesta | Semanal |
| Decisión de negocio | **Pendiente (D6)** |

### 5.2 Métricas adicionales

#### A6 — Tasa de abandono de formularios

```
A6(form_id, período) = COUNT(DISTINCT instance_id)
                        ────────────────────────────
                        COUNT(form_opened)

  donde instance_id pertenece a form_abandoned SIN
  evento de éxito asociado en la misma instancia
```

**Reglas de exclusión:**
1. Un evento de éxito (`inbound_order_created`, `outbound_order_created`, `incident_created`, etc.) cancela el abandono si comparte el mismo `instance_id`.
2. La ventana de emparejamiento es de 5 minutos antes/después del `form_abandoned`.
3. Se usa `COUNT(DISTINCT instance_id)` para evitar doble conteo.

**Tratamiento de intentos abiertos:**
- Un intento (instance_id) se considera **cerrado** cuando ocurre cualquiera de:
  - Se emite evento de éxito para ese `instance_id`.
  - Se emite `form_abandoned` para ese `instance_id`.
  - Pasan >24h desde `form_opened` sin resolución (límite de seguridad).
- Hasta entonces, ese `instance_id` no cuenta ni en el numerador ni en el denominador.

**Detección de abandono:**
- `beforeunload` no es fiable (no funciona en móvil, no permite peticiones asíncronas).
- Alternativa propuesta: heartbeat cada 30s mientras el formulario está abierto. Si el heartbeat cesa >60s + `visibilitychange` no recuperado, se emite `form_abandoned`.
- Timeout de inactividad: **pendiente de validación (D16)**. Propuesta: 30 minutos.

**Eventos fuente:** `form_abandoned` (#16), `form_opened` (auxiliar), eventos de éxito del catálogo.

| Propiedad | Valor |
|---|---|
| Frecuencia propuesta | Diaria |
| Decisiones de negocio | Timeout inactividad (D16), frecuencia (D6) |

#### A7 — Tasa de creación de cuentas

```
A7(período) = COUNT(account_created)
```

| Propiedad | Valor |
|---|---|
| Evento fuente | `account_created` (#8) |
| Agrupación | Por período |
| Frecuencia propuesta | Diaria |

#### A8 — Coste medio por unidad recibida

```
coste_medio_por_unidad(producto, proveedor, oficina, moneda, período) =
    SUM(quantity × unit_cost)
    ─────────────────────────
    SUM(quantity)

  coste_total_por_proveedor(proveedor, moneda, período) = SUM(quantity × unit_cost)
```

**Importante:**
- Se calcula **por unidad recibida** (no por movimiento).
- Los resultados se agrupan y presentan **separados por moneda**. No se suman importes en EUR y USD sin una política de conversión aprobada (D15).
- `unit_cost` no existe hoy en `AssetEntry` (véase D9). Hasta su implementación, A8 devuelve `null`.

**Ortogonalidad con `supplier_rate_updated`:**
- `supplier_rate_updated` mide cambios en el **coste fijo contractual mensual** del proveedor.
- A8 mide el **coste variable por unidad de producto recibida**.
- Ambas métricas son independientes: un proveedor puede mantener su tarifa mensual sin cambios mientras los costes unitarios de sus productos varían, y viceversa.

| Propiedad | Valor |
|---|---|
| Evento fuente | `inbound_order_created` (#1) |
| Agrupación | Por `product_id`, `supplier`, `office`, `currency` |
| Frecuencia propuesta | Mensual |
| Decisiones de negocio | Política de conversión EUR/USD (D15), umbral variación (D8) |

#### A9 — Tasa de productos por debajo del umbral

```
A9(período, office) = COUNT(stock_threshold_triggered)
```

| Propiedad | Valor |
|---|---|
| Evento fuente | `stock_threshold_triggered` (#3) |
| Agrupación | Por `office`, `stock_level` |
| Frecuencia propuesta | Diaria |
| Nota | **No emisible hoy.** Requiere backend de umbrales. |

#### A10 — Variación de tarifa de proveedor

```
A10(proveedor, período) = ABS(new_rate - old_rate) / old_rate * 100
A10_tasa = COUNT(supplier_rate_updated)
```

| Propiedad | Valor |
|---|---|
| Evento fuente | `supplier_rate_updated` (#20) |
| Agrupación | Por `supplier_id`, `currency` |
| Frecuencia propuesta | Mensual |
| Decisión de negocio | Umbral de alerta (D8) |

#### A11 — Incidentes estancados en estado `open`

```
A11(período, umbral_N) = COUNT(incidentes WHERE
                              status = 'open' AND
                              (CURRENT_TIMESTAMP - created_at) > N_días)

tiempo_medio_abierto = AVG(CURRENT_TIMESTAMP - created_at)
                       para incidentes con status = 'open'
```

**Base técnica (verificada en el código):**
- El grafo de transiciones (`manager_models.py`) no permite volver a `open` una vez abandonado.
- Por tanto, el estado `open` siempre se entra en `created_at` y nunca se reentra.
- `updated_at` refleja la última transición de estado, que para incidentes en `open` equivale a `created_at`.
- **No se necesita `incident_transition_log`** para esta métrica concreta. El log histórico solo sería necesario para calcular tiempo acumulado en otros estados para incidentes ya cerrados.

**Detección:**
1. Consultar `GET /api/incidents?status=open` (endpoint existente).
2. Para cada resultado: `tiempo_abierto = CURRENT_TIMESTAMP - created_at`.
3. Si `tiempo_abierto > N_días`: estancado.

| Propiedad | Valor |
|---|---|
| Evento fuente | `incident_status_changed` (#19) — permite trazar cuándo se cerraron |
| Consulta adicional | `GET /api/incidents?status=open` (existente) |
| Frecuencia propuesta | Diaria |
| Decisión de negocio | Umbral N (D7) — **pendiente** |

---

## 6. Evaluación de privacidad

| Aspecto | Decisión | Justificación |
|---|---|---|
| `user_uuid` | ✅ Incluido | Es un UUID. No contiene información personal reversible. **Seudonimización**, no anonimización. |
| `assigned_to` (nombres) | ❌ Excluido | Nombre de persona. No se emite en ningún evento. |
| Body de peticiones | ❌ Excluido | No se emite nunca. Coherente con `TimingMiddleware`. |
| IP del cliente | ❌ Excluido | No se emite nunca. |
| Authorization / tokens | ❌ Excluido | No se emite nunca. |
| `error_message` | ⚠️ Incluido opcional | Solo en `unhandled_api_error`. Debe auditarse para evitar datos sensibles. |
| SHA-256 / HMAC | ❌ No aplicado | No se necesita seudonimización adicional porque `user_uuid` ya es un UUID opaco. Si en el futuro se requiere anonimización, HMAC con clave rotada es la opción recomendada. |

---

## 7. Dependencias contractuales

Las siguientes propiedades aparecen en los contratos de eventos pero **no existen actualmente en el modelo de datos del repositorio**:

| Propiedad | Eventos | Existencia actual | Acción requerida |
|---|---|---|---|
| `unit_cost` | #1, #5 | ❌ No existe | Añadir a `AssetEntry` (D9) |
| `currency` en `AssetEntry` | #1 | ❌ No existe | Añadir a `AssetEntry` (derivado del proveedor) |
| `threshold` por producto-oficina | #3 | ❌ No existe backend | Crear modelo de umbrales |
| `kit_composition` | #5 | ❌ No existe | Modelo de kits compuestos |
| `expected_cost` / `actual_cost` | #5 | ❌ No existe | Depende de `unit_cost` |
| `programme_id` | #1, #2, #5, #17 | ❌ No existe | Modelo de programas |
| `product_category` funcional | #1, #2, #3, #5 | ⚠️ Parcial | `Asset.category` es string libre; se necesita un vocabulario controlado (`training_kit`, `certification`, `onboarding_equipment`) |
| `incident_transition_log` | #19 | ❌ No existe | Para trazabilidad histórica opcional |
| Heartbeat de formularios | #16, auxiliar | ❌ No existe | Implementación frontend |

---

## 8. Tabla de decisiones

| ID | Tema | Tipo | Estado | Dependencia / Notas |
|---|---|---|---|---|
| **D1** | Transporte y persistencia | Técnica | ✅ **Propuesta definida** | PostgreSQL (`telemetry_events`) + endpoint `POST /api/telemetry/event`. Best-effort. Sin garantía de entrega. |
| **D2** | Formato de evento (envelope) | Técnica | ✅ **Propuesta definida** | CloudEvents 1.0. |
| **D3** | Idempotencia | Técnica | ✅ **Propuesta definida** | UUID por evento, `CONSTRAINT UNIQUE`. |
| **D4** | Privacidad: user_uuid | Técnica | ✅ **Propuesta definida** | Seudonimización con UUID existente. |
| **D5** | Privacidad: assigned_to | Técnica | ✅ **Propuesta definida** | Excluido de todos los eventos. |
| **D6** | Frecuencia de métricas batch | **Negocio** | ⏳ **Pendiente de aprobación** | Propuesta: diaria para A1–A4, A6, A7, A9 y A11; semanal para A5; mensual para A8 y A10. |
| **D7** | Umbral N para estancamiento (A11) | **Negocio** | ⏳ **Pendiente de aprobación** | Propuesta: 7 días. |
| **D8** | Umbral de variación de coste | **Negocio** | ⏳ **Pendiente de aprobación** | Aplica a `supplier_rate_updated` (tarifa mensual). Propuesta: alertar si Δ > 10%. No afecta a `unit_cost` de A8. |
| **D9** | `unit_cost` en AssetEntry | **Desarrollo** | ❌ **Requiere desarrollo** | Añadir `unit_cost: float` y `currency: Currency` a `AssetEntry`. Impacto en `inventory/models.py`, `schemas.py`, `operations.py`. |
| **D10** | Historial de transiciones de incidentes | **Desarrollo** | ❌ **No necesario para A11** | Se confirma que no es necesario para detectar incidentes abiertos (se usa `created_at`). Sería necesario solo para análisis histórico de otros estados. |
| **D11** | Retención/archivo de eventos | **Negocio** | ⏳ **Pendiente de validación** | Propuesta: 90 días en `telemetry_events`, luego archivo externo o borrado. |
| **D12** | `form_opened` como auxiliar | Técnica | ✅ **Propuesta definida** | Fuera del catálogo principal de 20 eventos. Solo para soporte de A6. |
| **D13** | Exclusion rule por instance_id | Técnica | ✅ **Propuesta definida** | El éxito se asocia al mismo `instance_id`. Ventana de 5 min. Pendiente de validar con producto. |
| **D14** | Validación de eventos del frontend | Técnica | ⏳ **Requiere definición** | Propuesta: endpoint intermedio que valida schema con Pydantic antes de insertar. Eventos del backend se emiten directamente desde la lógica de negocio. |
| **D15** | Política de conversión de moneda | **Negocio** | ⏳ **Pendiente de aprobación** | Necesaria para agregar costes en EUR+USD en A8. Propuesta: tipo de cambio fijo mensual definido por administración. |
| **D16** | Timeout de inactividad en formularios | **Negocio** | ⏳ **Pendiente de validación** | Propuesta: 30 minutos. |

---

## 9. Anexo: dependencias de desarrollo

### 9.1 Desarrollo necesario para emitir eventos hoy

| Evento | ¿Qué falta? | Prioridad |
|---|---|---|
| #3 stock_threshold_triggered | Backend de umbrales + trigger post-movimiento | Alta |
| #4 direct_stock_edit_rejected | Endpoint de edición directa + validación | Baja |
| #5 kit_cost_variance_detected | Catálogo con costes, composición de kits | Media |
| #12 frontend_render_error | Error boundaries en Next.js | Media |
| #13 frontend_page_loaded | Hook de navegación en Next.js | Alta |
| #14 form_validation_failed | Hook de validación en frontend | Alta |
| #15 section_viewed | Tracking de secciones en frontend | Media |
| #16 form_abandoned | Heartbeat + detección de abandono | Alta |
| #17 candidate_record_created | Módulo de talento completo | Baja |

### 9.2 Desarrollo necesario para métricas

| Métrica | Dependencia | Prioridad |
|---|---|---|
| A6 | #14, #16, `form_opened`, heartbeat | Alta |
| A8 | `unit_cost`, `currency` en AssetEntry (D9) | Media |
| A9 | #3, backend de umbrales | Media |
| A10 | #20 | Alta (ya emisible) |
| A11 | #19 (ya emisible) | Alta |