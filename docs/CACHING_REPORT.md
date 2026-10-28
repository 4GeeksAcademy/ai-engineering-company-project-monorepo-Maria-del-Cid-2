# Informe de optimización de rendimiento (caching)

Informe técnico de las optimizaciones implementadas en la rama
`feature/caching-optimisation` y de su evaluación experimental.

## 1. Objetivo y alcance

**Objetivo**: reducir el coste de peticiones de lectura frecuentes y
descargar trabajo del hilo principal del frontend, sin Redis, sin dependencias
nuevas y sin añadir datos de prueba.

**Alcance (fases 1-8)**:

| Fase | Cambio | Componente |
|---|---|---|
| 1 | Middleware de medición HTTP | Backend |
| 2 | Clase reutilizable `TTLCache` | Backend |
| 3 | Caché de `GET /api/inventory/products` (TTL 30 s) | Backend |
| 4 | Caché de `GET /api/incidents/summary` (TTL 10 s) | Backend |
| 5 | Carga diferida de `Modal` | Frontend |
| 6 | Carga diferida de `NoteSection` | Frontend |
| 7 | `useMemo` en `OutboundFormPanel` | Frontend |
| 8 | Comparación con/sin caché | Evaluación |

**Fuera de alcance**: Redis u otros servicios de caché, nuevas dependencias,
cambios de contrato de API, datos de prueba artificiales, y la corrección de
las 6 vulnerabilidades *low* de la cadena jest/deepmerge (requieren
`npm audit fix --force`, cambio *breaking*).

## 2. Cambios técnicos

### 2.1 Middleware de medición HTTP

- **Archivo**: `services/api/app/middleware/timing.py` (exportado en
  `app/middleware/__init__.py`).
- **Registro**: `services/api/app/main.py` — `app.add_middleware(TimingMiddleware)`
  **después** de `CORSMiddleware`, más `logging.basicConfig(level=logging.INFO,
  stream=sys.stderr, format="%(message)s")`.
- **Comportamiento**: ASGI puro; mide con `time.monotonic()`, intercepta
  `http.response.start` para capturar el estado y registra en bloque `finally`
  (también en excepción): `method=%s path=%s status=%d duration_ms=%.2f`.
- **Privacidad**: no lee cuerpos de petición, no registra cabeceras
  sensibles (`Authorization`), IPs ni parámetros de query.
- **Utilidad de verificación**: `services/api/scripts/verify_timing_logs.sh`.

### 2.2 Clase `TTLCache`

- **Archivo**: `services/api/app/cache/ttl_cache.py` (exportado en
  `app/cache/__init__.py`).
- **API**: `get(key)`, `set(key, value, ttl=None)`, `delete(key)`, `clear()`,
  `invalidate(prefix)` y propiedad `size`.
- **Comportamiento**: `dict` en memoria con caducidad por `time.monotonic()`;
  `get` devuelve `None` en ausencia **o** caducidad (y purga la entrada
  caducada); distingue `None` cacheado de "no encontrado" con un centinela
  interno; `invalidate(prefix)` borra todas las claves con ese prefijo.
  `__slots__ = ("_default_ttl", "_store")`.
- **Validaciones**: `default_ttl` y `ttl` deben ser positivos (`ValueError`).

### 2.3 Caché de `GET /api/inventory/products` (TTL 30 s)

- **Archivo**: `services/api/app/inventory/router.py`.
- **Constantes/estado**: `CACHE_TTL_PRODUCTS: float = 30.0`;
  `_products_cache: TTLCache[list[AssetWithStockResponse]]`.
- **Lectura**: `get("list")` → si hay valor se responde sin consultar la BD; si
  no, `list_assets_with_stock(session)` + `set("list", result)`.
- **Invalidación**: `_products_cache.invalidate("list")` en los tres puntos de
  escritura del router (crear producto, entrada y salida de inventario).

### 2.4 Caché de `GET /api/incidents/summary` (TTL 10 s)

- **Archivo**: `services/api/app/incidents/manager_router.py`.
- **Constantes/estado**: `CACHE_TTL_SUMMARY: float = 10.0`;
  `_summary_cache: TTLCache[IncidentSummary]`.
- **Lectura**: `get("summary")` en `incident_summary()`; en miss,
  `repository.summary()` + `set("summary", result)`.
- **Invalidación**: `_summary_cache.invalidate("summary")` en `create_incident`
  y en el endpoint de cambio de estado.

### 2.5 Carga diferida (`next/dynamic`)

- `components/suppliers/SupplierDirectoryPanel.tsx` (línea 24):
  `const Modal = dynamic(() => import("@/components/ui").then(m => m.Modal), { ssr: false })`.
- `components/candidates/CandidateDetail.tsx` (línea 10):
  `const NoteSection = dynamic(() => import("@/components/notes").then(m => m.NoteSection), { ssr: false, loading: () => <div className="h-32 animate-pulse …"/> })`.

### 2.6 `useMemo` en `OutboundFormPanel.tsx`

- **Archivo**: `components/inventory/OutboundFormPanel.tsx`, líneas 77, 85 y 91.
- **Cálculos memorizados y dependencias**:

| Cálculo | Línea | Dependencias |
|---|---|---|
| `selectedProduct` | 77 | `[products, form.asset_id]` |
| `insufficientStock` | 85 | `[selectedProduct, quantity, available]` |
| `canSubmit` | 91 | `[selectedProduct, quantity, insufficientStock, form.exit_type, assigneeText]` |

- No se memorizaron los cálculos triviales (`quantity`, `available`,
  `assigneeText`). `canSubmit` alimenta `disabled={!canSubmit}` (línea 302).

### 2.7 Commit de actualización de versión de Next.js (`a760da8`)

- **Commit**: `fix(deps): patch Next.js security vulnerabilities` (`a760da8`),
  en la misma rama; modifica **únicamente** `package-lock.json`
  (47 líneas cambiadas; `package.json` sin cambios).
- **Causa**: durante la fase 7, la primera ejecución de `npm run build` mostró
  el aviso `SecurityFatalError` de Next.js que notificaba vulnerabilidades de
  seguridad presentes en la instalación. La revisión de `npm audit` confirmó
  **8 vulnerabilidades** en `next@16.4.0` y dependencias:
  - 🔴 **GHSA-2464-fhr4-w9xw** — ejecución remota de código (RCE) en la API de
    Image Optimization con SVG.
  - 🔴 **GHSA-673q-mjm6-r5xr** — RCE en `use cache` con *typed arrays*.
  - 🟠 **GHSA-p3m5-59mp-jv5r** — denegación de servicio en Server Actions del
    App Router.
  - 🟠 **GHSA-mrhx-c7xc-m3w5** — agotamiento de memoria en `zod` (< 4.6.6,
    transitiva vía `eslint-plugin-react-hooks`; solo desarrollo).
  - 6 *low* de la cadena `deepmerge → jest` (solo desarrollo).
- **Mitigación previa existente**: `dangerouslyAllowSVG` **no** está activo en
  `next.config.ts`, por lo que el vector SVG estaba inactivo; las asesorías
  seguían aplicándose a la versión instalada.
- **Corrección aplicada**: `npm audit fix` **sin** `--force` (aviso explícito de
  no usar `--force` ni `next upgrade --agent=security`). Versiones resultantes:
  `next 16.4.0 → 16.4.3` (con `@next/env` y `@next/swc-*`), `zod 4.4.3 → 4.6.7`,
  `ts-jest 29.4.14 → 29.4.15`.
- **Resultado de `npm audit`**: 8 vulnerabilidades → **6 *low***
  (pendientes por diseño: corregirlas exige `npm audit fix --force`, que
  instalaría `jest@25`, cambio *breaking* fuera de alcance).
- **Verificación tras la actualización**: backend sin cambios; frontend
  `npm test` → 70/70 en verde y `npm run build` → 0 errores de TypeScript,
  18 páginas.
- **Relación con el rendimiento**: es un parche de **seguridad**, no una
  optimización de rendimiento; no se han medido efectos de rendimiento de
  16.4.0 → 16.4.3 y no se atribuye ninguna mejora cuantitativa a este commit.

## 3. Metodología de evaluación

La comparación de la fase 8 ejecutó **las mismas peticiones con y sin caché**
en condiciones idénticas:

- **Condición "con caché"**: servicio principal (`:8000`) con la implementación
  de las fases 1-4.
- **Condición "sin caché"**: instancia temporal de referencia en el **mismo
  contenedor** (`:8100`) con el mismo código y la misma base de datos, con
  `_products_cache` y `_summary_cache` sustituidos por una caché nula
  (`sitecustomize.py` en `/tmp`, activado por `NEXOVA_BYPASS_CACHE=1`).
  **Sin modificar código de la aplicación ni datos.**
- **Fuente de métrica**: los `duration_ms` del `TimingMiddleware` de cada
  instancia (prefijo `BEFORE ` en la de referencia). Los logs del middleware de
  ambas instancias son la fuente primaria; la latencia del cliente se registró
  como referencia secundaria.
- **Autenticación**: JWT emitido dentro del contenedor sobre un usuario
  existente (`create_access_token({'sub': '1', 'credentials_version': 1})`);
  no se creó ningún usuario ni dato.
- **Condiciones de la prueba**: espera de **31 s** previa (TTLs: 30 s y 10 s)
  para garantizar estado frío; **1 petición fría + 30 cálidas** por endpoint y
  condición → **n = 31 mediciones por celda**; endpoint de control **sin caché**
  (`/api/incidents`) medido en paralelo para calibrar el ruido de fondo.
- **Tamaño de muestra**: 31 por condición y endpoint, un único conjunto de
  mediciones (fase 8; no se repitió).

**Limitaciones del método**:

1. No es una comparación histórica anterior a la implementación: es una
   comparación controlada de las mismas peticiones con la caché anulada.
2. Dataset actual pequeño (`inventory.db`, `incidents.json`): las consultas son
   baratas; con más volumen el comportamiento puede diferir (no medido).
3. Un solo conjunto de mediciones en un entorno de desarrollo (Codespaces,
   contenedores Docker); el ruido de fondo es medible (ver control).
4. El orden de ejecución de la primera ronda provocó un artefacto (1200,25 ms
   en products "frío con caché") que **se descartó** tras no reproducirse con
   orden invertido en 3 rondas; por eso **no se presentan tiempos de caché
   fría como mejora demostrada**.
5. El frontend (fases 5-7) **no se midió por separado**; no se atribuyen
   mejoras cuantitativas al frontend.

## 4. Resultados medidos

Fuente: `duration_ms` del middleware, **31 mediciones por condición y endpoint**.

| Endpoint | Métrica | Sin caché | Con caché |
|---|---|---|---|
| `/api/inventory/products` | Media | 9,31 ms | 6,09 ms |
| `/api/inventory/products` | Mediana | 4,53 ms | 5,26 ms |
| `/api/inventory/products` | Máximo | 133,62 ms | 16,90 ms |
| `/api/incidents/summary` | Media | 5,66 ms | 5,42 ms |
| `/api/incidents/summary` | Mediana | 5,06 ms | 5,18 ms |
| `/api/incidents/summary` | Máximo | 24,81 ms | 9,12 ms |

**Endpoint de control** (no utiliza caché): `/api/incidents` — media de
**5,30 ms sin caché** y **6,44 ms** en la otra condición (n = 31).

## 5. Interpretación de los resultados

**Resultados observados**:

- La mejora más clara se observa en los **tiempos máximos**: products
  133,62 → 16,90 ms y summary 24,81 → 9,12 ms.
- Las **medianas son similares** y, en products, la condición con caché fue
  incluso ligeramente superior (4,53 → 5,26 ms): diferencias dentro del ruido.
- El **endpoint de control sin caché también varió** entre condiciones
  (5,30 → 6,44 ms en media, +21 %), lo que confirma la existencia de ruido de
  fondo en el entorno.

**Interpretación** (separada de los datos):

- La caché actúa como **estabilizador**: elimina picos y colas ocasionales más
  que acelerar el caso típico con este volumen de datos.
- Las diferencias pequeñas de mediana **no deben presentarse como mejoras
  demostradas**, dado que el control sin caché se movió en magnitud comparable.
- Con consultas más costosas (más datos, agregaciones mayores) el beneficio en
  media y mediana debería crecer; es una hipótesis razonable, **no medida**.

**Limitaciones**:

- Los resultados corresponden al **conjunto de datos actual** y no garantizan
  las mismas mejoras con otras cargas.
- **No** es una comparación histórica anterior a la implementación.
- **No** se atribuyen mejoras cuantitativas al frontend al no haber medido sus
  optimizaciones por separado.
- Los tiempos de caché fría quedan **fuera** de las conclusiones por el artefacto
  de orden descrito en la metodología.

## 6. Validación y estado

Únicamente comprobaciones realizadas con evidencia:

| Comprobación | Resultado |
|---|---|
| `pytest tests/test_cache.py tests/test_inventory_cache.py tests/test_incident_summary_cache.py` | **32 passed** (18 + 7 + 7) |
| `uv run pytest` (suite backend completa) | **411 passed, 1 skipped, 4 failed** — los 4 fallos son **preexistentes** y ajenos (sanitización de errores, reset de JWT, CORS PATCH/DELETE de proveedores) |
| `npm test` (frontend) | **70 passed, 0 failed** |
| `npm run build` (frontend) | Compila sin errores de TypeScript; **18/18 páginas** |
| Logs del middleware | Líneas `method=… duration_ms=…` verificadas en ambas instancias (93 peticiones servidas por la instancia de referencia, coincidentes con la emisión) |
| `npm audit` (tras `a760da8`) | 8 vulnerabilidades → **6 *low*** de desarrollo (jest/deepmerge), pendientes por exigir cambio *breaking* |

**Estado de la rama**: fases 1-7 commiteadas (`18e314c`, `2f19736`, `5cbc76b`)
y el parche de seguridad (`a760da8`); documentación de la fase 9 sin commitear
(queda a decisión del mantenedor). Las fases 1-8 requirieron además la
actualización de seguridad de Next.js descrita en la sección 2.7, motivada por
el aviso `SecurityFatalError` observado en el build de la fase 7.