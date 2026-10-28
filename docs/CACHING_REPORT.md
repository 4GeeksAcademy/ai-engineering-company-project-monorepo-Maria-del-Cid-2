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

**Justificación de la selección de `Modal`** (hechos verificados en el código;
la elección no está documentada como decisión histórica, por lo que se presenta
como evaluación de esta revisión):

- El único `<Modal>` de la página se encuentra en `SupplierRow`
  (`SupplierDirectoryPanel.tsx`, línea 164): `Modal` es un **overlay de UI puro**
  — sin datos propios ni peticiones — que solo tiene sentido tras una interacción
  del usuario (el botón "View notes" de un proveedor, que además solo se muestra
  si `supplier.notes` existe).
- El diálogo está en el árbol de render de cada fila desde la carga de la página
  con `open={notesOpen}` (`notesOpen` inicia en `false`, línea 117), de modo que
  su módulo viajaba en la carga inicial aunque nunca se abriera.
- Al ser interacción rara y sin dependencias de datos, es el candidato de menor
  riesgo para `ssr: false`.

**Justificación de la selección de `NoteSection`** (misma condición: evaluación
de esta revisión sobre hechos verificados):

- `NoteSection` combina `NoteList` + `NoteForm` y, al montarse, dispara una
  petición de datos: `useEffect(() => fetchNotes(recordId))` (`NoteSection.tsx`,
  líneas 16-18). Es una **carga secundaria** de la página de detalle de
  candidato: el resto del detalle (datos del candidato) es independiente de las
  notas.
- Se mostraba completo en el arranque de `app/candidates/[id]/page.tsx` aunque
  el usuario nunca interactuara con la zona de notas.
- Por ser una sección autónoma con datos propios, además de `ssr: false` se le
  añadió `loading` con esqueleto para cubrir la ventana de descarga del chunk.
- En `@/components/notes`, `NoteSection` es el único consumidor real en la app
  (solo `CandidateDetail` lo importa). En cambio, `Modal` pertenece a
  `@/components/ui`, conjunto compartido: por eso la guía señala que los
  módulos compartidos merecen revisión si su peso crece.

### 2.6 `useMemo` en `OutboundFormPanel.tsx`

- **Archivo**: `components/inventory/OutboundFormPanel.tsx`, líneas 77, 85 y 91.
- **Cálculos memorizados y dependencias**:

| Cálculo | Línea | Dependencias |
|---|---|---|
| `selectedProduct` | 77 | `[products, form.asset_id]` |
| `insufficientStock` | 85 | `[selectedProduct, quantity, available]` |
| `canSubmit` | 91 | `[selectedProduct, quantity, insufficientStock, form.exit_type, assigneeText]` |

- No se memorizaron los cálculos triviales (`quantity`, `available`,
  `assigneeText`). `canSubmit` alimenta `disabled={!canSubmit}` (línea 307).

**Beneficio esperado vs. medido** (los datos de la sección 4 proceden solo del
backend; el frontend no se midió):

| | |
|---|---|
| **Beneficio esperado** (expectativa, no medido) | Evitar recalcular en cada re-render `selectedProduct` (búsqueda de producto en `products`), `insufficientStock` (comprobación de stock) y `canSubmit` (validación encadenada de 4 condiciones). Las dependencias garantizan que se recalculan solo cuando cambia algo relevante del formulario, y la habilitación del botón de envío (`disabled`) refleja el estado validado sin coste añadido por render. Expectativa cualitativa: mayor relevancia cuanto más re-renders genere el formulario y más productos haya. |
| **Realmente medido** | Únicamente validación funcional: `npm test` → 70/70 y `npm run build` → 0 errores TypeScript, 18 páginas. **No se midió** tiempo de render, número de re-renders ni ganancia de CPU en el cliente: **no se atribuyen mejoras cuantitativas a `useMemo`** (limitación declarada en la sección 3). |

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

### 2.8 Perfil de los endpoints cacheados

Los **hechos** de esta sección (consultas, llamadas y puntos de invalidación)
proceden de la inspección del código. Las **frecuencias de llamada y de
actualización son estimaciones cualitativas**: la aplicación no registra
métricas de uso (no hay telemetría ni contadores de llamadas), por lo que no
existen cifras de frecuencia que reportar.

| Dimensión | `GET /api/inventory/products` | `GET /api/incidents/summary` |
|---|---|---|
| **Coste de la operación en miss** (verificado) | SQL con dos agregaciones (`GROUP BY` + `SUM` sobre `AssetEntry` y `AssetExit`), `LEFT JOIN` con `Asset` y construcción de la lista de respuestas (`inventory/queries.py`, `list_assets_with_stock`). | `repository.summary()` llama a `self.list()`, que lee **todos** los documentos de TinyDB, los valida uno a uno con Pydantic y después ejecuta 4 conteos en Python (`manager_repository.py`, líneas 79-87). Coste creciente con el número de incidencias. |
| **Frecuencia de lectura** (estimación cualitativa) | Llamada por montaje de 4 paneles (`InventoryCurrentStockPanel`, `OutboundFormPanel`, `InboundFormPanel`, `OrdersHistoryPanel`), todos vía `useEffect` en el montaje. Sin *polling* ni refresco automático: lecturas **por visita a las páginas de inventario**. | Se lanza en paralelo con la lista de incidencias en `loadData` (`IncidentManagerPanel.tsx`, línea 192), que se ejecuta al montar el panel, **al cambiar cualquier filtro** y al actualizar una incidencia (línea 211). Lecturas **por visita y por interacción de filtro**. |
| **Frecuencia de actualización** (estimación cualitativa) | Escrituras en los 3 endpoints de mutación del router (crear producto, entrada, salida): ocurren al registrar movimientos de inventario, no en segundo plano. | Escrituras en 2 endpoints (crear incidencia, cambiar estado): ocurren al gestionar incidencias, no en segundo plano. |
| **TTL** | 30 s (`CACHE_TTL_PRODUCTS`) | 10 s (`CACHE_TTL_SUMMARY`) |
| **Invalidación anticipada** | `invalidate("list")` en los 3 puntos de escritura | `invalidate("summary")` en crear y cambiar estado |
| **Efecto de la caché** (verificado) | En hit, responde sin abrir consulta a la base de datos. | En hit, responde sin leer TinyDB ni validar con Pydantic. |

### 2.9 Frescura frente a rendimiento (elección de los TTL)

El equilibrio es: **reutilizar un resultado ya calculado** (menos coste por
petición) frente al riesgo de **servir datos desactualizados** durante el TTL.
En esta implementación ese equilibrio se apoya en dos mecanismos y conviene no
confundirlos:

- **Invalidación anticipada (mecanismo principal de frescura)**: cada escritura
  borra la entrada correspondiente de forma inmediata. Con ella, una lectura
  posterior sufre *miss* y reconstruye el valor: los datos que cambian por los
  caminos de escritura conocidos **no dependen del TTL** para quedar frescos.
- **TTL (red de seguridad)**: el TTL solo limita la ventana de frescura ante
  escrituras que la invalidación no cubra. Por eso los valores escogidos son
  cortos (30 s y 10 s): incluso en el peor caso, la antigüedad máxima de una
  respuesta cacheada es de 30 s y 10 s respectivamente.
- **Asimetría 30 s / 10 s**: el resumen de incidencias se lee con más frecuencia
  (se refresca con cada cambio de filtro) y su recomputación barata en dataset
  pequeño pero crece con el número de incidencias; su ventana máxima de
  staleness se mantiene más corta (10 s). El listado de productos combina una
  consulta con agregaciones SQL con escrituras que ya invalidan la entrada, y se
  leen en cascada varios paneles de inventario; 30 s actúa como red de seguridad
  sin exponerse en los caminos de escritura conocidos. **Estas razones de diseño
  son una justificación a posteriori de los valores existentes (evaluación de
  esta revisión); no constan como documentación de decisión histórica.** No se
  han variado los TTL ni la invalidación.

### 2.10 Qué no se cachea y por qué

*Evaluación realizada durante esta revisión*: no existe constancia en el
desarrollo de que se evaluara cachear otros endpoints; lo que sigue es el
análisis efectuado ahora sobre el código, no una decisión histórica.

- **`GET /api/auth/me` (candidato descartado)** — es el ejemplo de mayor riesgo
  porque su respuesta es **personalizada por usuario** (email, rol, fechas y
  perfil): `read_current_user` (`auth/routers/auth_router.py`, a partir de la
  línea 68) construye `UserMeResponse` a partir del JWT de cada petición. La
  caché actual `TTLCache` es **única por proceso, compartida entre todas las
  sesiones y sin partición por usuario**: cachearla con una clave derivada de la
  ruta serviría los datos de un usuario a otro (**fuga de datos**). Cachearla
  correctamente exige claves por `user_id` y, además, invalidarla en logout,
  cambio de contraseña y rotación de credenciales (`credentials_version`), porque
  el JWT no es la clave de la caché. A esto se suma que su coste es bajo (dos
  consultas puntuales) y se llama en el montaje de `AuthProvider` y en el inicio
  de sesión, no en bucle → beneficio mínimo con riesgo máximo.
- **`GET /api/inventory/orders` (descartado)**: su coste de consulta es
  similar al ya cacheado (`union_all` de entradas y salidas, `queries.py`), pero
  no se identificó ningún otro consumidor que lo usara, con lo que el beneficio
  de cachearlo sería marginal frente a cubrir sus mutaciones.
- **`GET /api/suppliers` y `GET /api/incidents` (descartados)**: son listados
  sencillos y baratos; además, `GET /api/incidents` admite **filtros de query**,
  lo que multiplicaría las claves de caché y su invalidación por el número de
  combinaciones de filtros, para un coste de consulta que hoy es bajo.

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