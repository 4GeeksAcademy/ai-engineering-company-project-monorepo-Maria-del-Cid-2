# Audit.md — Auditoría de rendimiento del sitio web público (línea base de producción)

> **Documento:** línea base inicial de rendimiento para el ciclo de mejora incremental.
> **Fecha de medición:** 21/10/2026.
> **Fuentes:** 6 informes JSON de Lighthouse regenerados desde cero contra producción → `audit/json/` (más resúmenes `summary*.txt` y scripts `extract_lighthouse*.py`).
> **Este archivo se ha creado desde cero con los resultados de producción. No contiene datos de mediciones anteriores locales ni de PDFs ya eliminados.**
> **Ampliación (2026-10-21): §9 = línea base del backoffice (Next.js) — Fase 2**, fuente `audit/before/backoffice/*.pdf`.

---

## 1. Condiciones de medición

| Campo | Valor |
|---|---|
| URL producción | `https://4geeksacademy.github.io/ai-engineering-company-project-monorepo-Maria-del-Cid-2/` |
| Páginas auditadas | `index.html`, `application-companies.html`, `application-candidates.html` |
| Herramienta | Lighthouse CLI **13.5.0** (Chrome for Testing **153**, headless, flags de contenedor: `--no-sandbox --disable-dev-shm-usage`) |
| Categorías | Performance, Accessibility, Best Practices, SEO |
| Dispositivos | Escritorio (`--preset=desktop`) y Móvil (emulación Moto G Power, slow-4G) |
| Método de throttling | **Simulado (Lantern)** — `throttlingMethod=simulate` (configuración por defecto del CLI) |
| Modo | Navegación (default), una corrida por página y dispositivo |
| Artefactos | `audit/json/{index,companies,talento}-{desktop,mobile}.json` |

**KPIs principales de este ciclo:** TTFB, LCP, CLS, TBT y puntuación de Rendimiento de Lighthouse.
**INP:** queda **fuera del alcance por decisión del equipo** (no es un KPI exigido). En laboratorio no se mide INP real de campo; se usa **TBT como proxy de laboratorio**. Se documenta como métrica pendiente.

---

## 2. Línea base — Puntuaciones Lighthouse

### Escritorio

| Página | Rendimiento | Accesib. | B. Prácticas | SEO |
|---|---|---|---|---|
| index.html | **96** | 96 | 96 | 100 |
| application-companies.html | **94** | 90 | 96 | 100 |
| application-candidates.html | **98** | 92 | 96 | 100 |

### Móvil (Moto G Power)

| Página | Rendimiento | Accesib. | B. Prácticas | SEO |
|---|---|---|---|---|
| index.html | **72** | 96 | 96 | 100 |
| application-companies.html | **55** | 90 | 96 | 100 |
| application-candidates.html | **75** | 92 | 96 | 100 |

> El déficit de rendimiento se concentra **en móvil** (55–75). Escritorio ya está en 94–98.

---

## 3. Línea base — KPIs de laboratorio

| KPI | index DESK | index MÓVIL | companies DESK | companies MÓVIL | talento DESK | talento MÓVIL |
|---|---|---|---|---|---|---|
| **LCP** | 1.41 s | **8.08 s** | 1.54 s | **8.39 s** | 1.15 s | **6.00 s** |
| **TBT** | 56 ms | 0 ms | 80 ms | **687 ms** | 10 ms | 0 ms |
| **CLS** | **0** | **0** | **0** | **0** | **0** | **0** |
| **FCP** | 549 ms | 2.5 s | 676 ms | 2.3 s | 600 ms | 2.3 s |
| Speed Index | 650 ms | 2.8 s | 885 ms | 2.8 s | 626 ms | 2.8 s |
| **TTFB** | ~2 ms* | ~135 ms* | ~2 ms* | ~18 ms* | ~2 ms* | ~14 ms* |

\* Observado por Lighthouse (`document-latency-insight`: "Server responds quickly"). Verificación externa con `curl`: **TTFB 32–150 ms** (HTTP/2, gzip, `cache-control: max-age=600`, ETag). **TTFB está en verde en todas las páginas.**

### Diagnóstico de apoyo (medido)

| Diagnóstico | index | companies | talento |
|---|---|---|---|
| Tamaño transferido total | 1,383 KiB | 1,291 KiB | 946 KiB |
| Render-blocking (ahorro est.) | **1,480 ms móvil** / 320 ms desk. | **1,510 ms móvil** / 320 ms desk. | **1,480 ms móvil** / 360 ms desk. |
| Trabajo hilo principal | 1.1 s móvil / 0.4 s desk. | **1.4 s móvil** / 0.4 s desk. | 1.1 s móvil / 0.3 s desk. |
| Long tasks | 3 (570 ms máx.) | 3 (**737 ms máx.**) | 3 (567 ms máx.) |
| Tareas largas escritorio | 1 (190 ms) | 2 (210 ms) | 1 (141 ms) |
| Ahorro imagen (`image-delivery-insight`) | **1,196 KiB móvil** / 1,002 KiB desk. | 808 / 807 KiB | 808 / 807 KiB |
| Ahorro caché (`cache-insight`) | 804 KiB | 1,059 KiB | 742 KiB |
| JS sin usar | 39 KiB (31% de Tailwind CDN) | 39 KiB | 38 KiB |
| Elementos DOM | 284 | 223 | 213 |

---

## 4. Problemas identificados (con causa raíz)

Convención: **[HECHO]** = reproducido en los JSON; **[HIPÓTESIS]** = explicación razonable aún no aislada experimentalmente (se validará con la corrección y re-medición).

### P1 — Logo PNG gigante descargado en todas las páginas `[HECHO]`
- **Evidencia:** `Logo nexova Negro y naranja.png` = **828,004 B** (1254×1254, PNG RGB) → **809 KiB transferidos** en cada página. Se muestra a **56×56 px (móvil) / 96×96 px (escritorio)** (`img.h-14 … sm:h-16`).
- **Impacto:** `image-delivery-insight` ❌ ahorro estimado **807–1,196 KiB**; es el mayor recurso de la página en las 3 URLs; `cache-insight` ❌ (vida de caché 600 s → 759 KiB "desperdiciados" por visita fría).
- **KPI afectado:** LCP (peso de red en cascada), puntuación Rendimiento, TBT secundario (decode).
- **Causa raíz:** asset sin optimizar ni dimensionar para su uso real; sin `width/height` explícitos ni `srcset`.

### P2 — Hero del index: imagen externa grande sin prioridad `[HECHO]`
- **Evidencia:** elemento LCP de index (escritorio y móvil) = `main > section#hero > div.relative > img.absolute` → Unsplash `photo-1521737711867…?w=1600&q=80`, **374,687 B (366 KiB)**. `lcp-discovery-insight` ❌: **`fetchpriority=high` NO aplicado** (`priorityHinted: false`); sí es descubrible en el documento y no usa `loading=lazy` ✓. Sin `width/height`.
- **Desglose LCP (móvil):** TTFB 153 ms + retardo descubrimiento 23 ms + carga 36 ms + **retardo de render del elemento 1,117 ms** → 8.08 s (modelo Lantern; amplificación por throttling simulado).
- **KPI afectado:** LCP de index (8.08 s móvil / 1.41 s escritorio) y CLS (riesgo sin dimensionado).

### P3 — Tailwind CSS por CDN render-blocking `[HECHO]`
- **Evidencia:** las 3 páginas cargan `<script src="https://cdn.tailwindcss.com">` (Play CDN v3.4.17, 407,279 B → **124 KiB** transfer). `render-blocking-insight` ❌ en las 6 corridas: ahorro est. **1,480–1,510 ms en móvil** y **320–360 ms en escritorio** (`wastedMs` del script: 764–772 ms móvil / 209–240 ms desk.). Además: 39 KiB (31%) sin usar, ~40–69 ms de hilo principal de tercero (`third-parties-insight`), y **cero orígenes con preconnect** (`network-dependency-tree-insight`).
- **Impacto directo en LCP de companies/talento (móvil):** su elemento LCP es **texto** (`h1/h2#application-title`, `p.mt-6`), no una imagen; su render depende de que Tailwind compila/aplique CSS. Desglose: `elementRenderDelay` **1,308 ms** (móvil) — el mayor componente tras la red.
- **Causa raíz:** CSS generado en cliente al cargar la página en lugar de servirse compilado; bloquea el primer pintado.
- **KPI afectado:** LCP (todas), FCP, puntuación Rendimiento.

### P4 — `location-catalog.es.js` de 1 MB evaluado en el hilo principal (companies) `[HECHO] + [HIPÓTESIS parcial]`
- **Evidencia:** `data/location-catalog.es.js` = **1,030,880 B** → **343 KiB** transfer, solo en companies. Long task **737 ms** (móvil) y `scriptEvaluation` **831 ms** de un hilo principal de 1.4 s; TBT **687 ms** (único TBT alto de toda la suite). Escritorio: 2 long tasks (210 ms) y TBT 80 ms.
- **[HECHO]** la correlación: la página con este script es la única con TBT alto.
- **[HIPÓTESIS]** que la long task de 737 ms es la evaluación/parseo de ese archivo (asignación única en `window.NEXOVA_LOCATION_CATALOG`); se validará con la corrección (C5).
- **KPI afectado:** TBT (proxy de INP), puntuación Rendimiento móvil de companies (55).

### P5 — CLS = 0 actual: riesgo latente sin `width/height` `[HECHO — guard]`
- **Evidencia:** CLS **0** en las 6 corridas, `cls-culprits-insight` ✅. Pero logo y hero **no declaran `width/height`** y dependen de clases CSS/Tailwind para reservar espacio: si P1/P2/P3 cambian el orden de render, puede aparecer desplazamiento.
- **Acción:** mantener CLS=0 como **indicador de regresión** tras cada corrección de Fase 1.

### P6 — Caché corta (600 s) fijada por GitHub Pages `[HECHO — limitación]`
- **Evidencia:** `cache-insight` ❌ ahorro 742–1,059 KiB; todos los recursos con `max-age=600`.
- **Causa raíz:** GitHub Pages fija `cache-control: max-age=600`; **no permite cabeceras personalizadas**. No es corregible en Pages; mitigación parcial: versionado en URL de assets grandes.

### P7 — `favicon.ico` → 404 en consola `[HECHO]`
- **Evidencia:** `errors-in-console` ❌ en las 6 corridas: `GET https://4geeksacademy.github.io/favicon.ico` = 404. Afecta a Best Practices (96) y a la limpieza de consola.

### P8 — Sin preconnect a orígenes de terceros `[HECHO]`
- **Evidencia:** "no origins were preconnected" en las 6 corridas. Aplica a `cdn.tailwindcss.com` (e index: `images.unsplash.com`).

### Problemas secundarios (fuera de KPIs principales; fase posterior)
- **Contraste de color insuficiente** (`color-contrast` ❌ en las 6 → Accesibilidad 90–96).
- **`aria-allowed-attr`** ❌ (companies/talento) y **`label-content-name-mismatch`** ❌ (solo index).
- **`valid-source-maps`** ❌ (companies, JS grande sin sourcemap).
- Tailwind CDN es runtime JS de tercero → afecta también a la advertencia de cookies de Best Practices.

---

## 5. Análisis de refactorización (alcance de las correcciones)

**Objetivo:** mejora incremental y medible de los KPIs, **un problema por commit**, sin reestructurar la arquitectura del frontend.

| # | Corrección (commit) | Problema | KPI objetivo | Evidencia que la justifica |
|---|---|---|---|---|
| **C1** | Optimizar logo: dimensionar (≤256 px útil), convertir a WebP/AVIF + `srcset`, `width/height` | P1 | **LCP** móvil (3 páginas), puntuación, bytes | 809 KiB → objetivo <20 KiB; ahorro 807–1,196 KiB medido |
| **C2** | Hero index: servir local (AVIF/WebP dimensionado), `fetchpriority="high"`, `width/height`, preload | P2 | **LCP** index + guard CLS | `lcp-discovery-insight` ❌ `priorityHinted:false`; 366 KiB externos |
| **C3** | Render-blocking de Tailwind CDN — variantes incrementales: (a) `preconnect`, (b) CSS crítico inline + defer del CDN; cada variante = commit aparte | P3 | **LCP** (todas), FCP | ahorro 1,480–1,510 ms móvil / 320–360 ms desk. |
| **C4** | Declarar `width/height` en todas las imágenes | P5 | **CLS** (guard) | CLS actual = 0; imágenes sin dimensionado |
| **C5** | `location-catalog.es.js`: carga diferida (`defer`/bajo demanda) fuera del bloqueo del render | P4 | **TBT** companies (proxy INP) | TBT 687 ms, long task 737 ms, 343 KiB |
| **C6** | Revisar JS de menú/formularios inline duplicado y long tasks residuales | P4/P3 | TBT, TTI | long tasks 567–570 ms móvil (index/talento) |
| **C7** | Añadir `favicon.ico` local (+ preconnect residual si C3a no lo cubre) | P7/P8 | Best Practices, consola | 404 en las 6 corridas |

**Fuera de alcance (no-goals explícitos):**
- No se reescribe el frontend (sigue siendo HTML estático + Tailwind).
- No se migra el backoffice Next.js en este ciclo.
- No se cambia de hosting (limitaciones de Pages documentadas en §7).
- INP real (campo) queda pendiente; TBT es el proxy de laboratorio.
- Auditorías secundarias (contraste, ARIA, source maps) → fase 5, después de los KPIs.

---

## 6. Protocolo de medición del ciclo

1. **Corrección incremental:** 1 commit = 1 problema (C1…C7).
2. **Despliegue:** push a `main` → workflow de GitHub Pages (esperar run verde + ~1 min de propagación).
3. **Medición:** Lighthouse CLI 13.5, mismas flags y presets que §1, JSON → `audit/json/` (manteniendo la línea base; el "antes" vive en esta y en los JSON de 21/10).
4. **Registro:** cada commit anotado en `Report.md` con problema ↔ KPI ↔ fecha ↔ medición antes/después (móvil + escritorio, 3 páginas).
5. **Guard de regresión:** CLS debe seguir en **0** tras cada corrección de Fase 1; verificar también que no suben FCP ni TBT.
6. **Impacto global:** al terminar C1–C6, medición final agregada (4 KPIs × 3 páginas × 2 dispositivos) y ranking de impacto real en `Report.md`.

---

## 7. Limitaciones de la plataforma (GitHub Pages)

- **Caché:** `max-age=600` fijo; no se pueden enviar cabeceras propias (P6).
- **Sin cabeceras personalizadas:** no CSP, no HSTS, no `X-Content-Type-Options` configurables.
- **Compresión:** gzip servido por Pages; no se controla Brotli.
- **Sin SSR ni control de red:** el TTFB medido (2–150 ms) ya es excelente; las mejoras restantes son de cliente.
- **Backoffice:** despliegue aparte en PaaS con `npm run build` / `npm run start` (fuera del ciclo web estático). **Ampliado el 21/10/2026:** se abre Fase 2 de mejora del backoffice con el mismo protocolo (ver §9).

---

## 8. Resumen ejecutivo de la línea base

- **TTFB ✓** (2–150 ms) y **CLS ✓** (0 en todo) ya están en objetivo → se protegen como guard.
- **LCP móvil es el problema nº1** (6.0–8.4 s vs objetivo ≤2.5 s): tres causas evidenciadas — logo de 809 KiB (P1), hero sin prioridad (P2) y render-blocking del CDN de Tailwind (P3).
- **TBT de companies móvil (687 ms)** es el problema nº2, ligado a `location-catalog.es.js` de 1 MB (P4).
- Escritorio ya puntúa 94–98; el recorrido de mejora está en móvil (55–75).
- Orden de impacto esperado: **C1 + C3** (LCP global) → **C2** (LCP index) → **C5** (TBT companies) → resto (guards y secundarios).

---

## 9. Fase 2 — Línea base del backoffice (Next.js) (2026-10-21)

> Fase 2: mismo proceso (baseline → correcciones incrementales → medición antes/después en `Report.md`) aplicado a `uis/backoffice/talent-pipeline-tracker`.

### 9.1 Condiciones de medición

| Campo | Valor |
|---|---|
| URL medida | Preview del Codespace (`https://friendly-barnacle-qv5p44r9rxq2644j-3000.app.github.dev`) sirviendo `npm run build` + `npm run start` (Next.js **16**, React **19**, Tailwind **4**) |
| Páginas auditadas | `/` (home talent pipeline), `/login`, `/incidents` (incidents manager) |
| Herramienta | Lighthouse **13.4.1** (DevTools/emulación, Chromium 155) |
| Dispositivos | Escritorio emulado y Móvil Moto G Power (slow-4G) |
| Formato artefactos | Informes PDF → `audit/before/backoffice/*.pdf` (6 ficheros) |
| Nota `incidents manager.pdf` | Corrida móvil **extra** del 19/10/26 (fecha ≠ resto del 21/10); sirve como referencia, se marca como corrida inicial |

**Mismos KPIs que Fase 1:** TTFB, LCP, CLS, TBT y puntuación de Rendimiento. INP fuera de alcance (TBT como proxy).

### 9.2 Línea base — Puntuaciones Lighthouse

| Página | Dispositivo | Rendimiento | Accesib. | B. Prácticas | SEO |
|---|---|---|---|---|---|
| `/` (talent) | Escritorio | **99** | 88 | 100 | 60 |
| `/` (talent) | Móvil | **94** | 88 | 100 | 60 |
| `/login` | Escritorio | **100** | 96 | 100 | 60 |
| `/login` | Móvil | **92** | 96 | 100 | 60 |
| `/incidents` | Escritorio | **100** | 89 | 100 | 60 |
| `/incidents` | Móvil (19/10, ref.) | **88** | 89 | 100 | 60 |

> **Contexto favorable:** el backoffice ya está en 88–100 de Rendimiento (la web empezó en 55–75 móvil). El déficit no está en la puntuación de rendimiento sino en: **Accesibilidad 88–96** (contraste, labels de `<select>`), **SEO 60** (`x-robots-tag: noindex, nofollow`) y TBT móvil (200–430 ms).

### 9.3 Línea base — KPIs de laboratorio

| KPI | `/` DESK | `/` MÓVIL | `/login` DESK | `/login` MÓVIL | `/incidents` DESK | `/incidents` MÓVIL (ref. 19/10) |
|---|---|---|---|---|---|---|
| **LCP** | 0,6 s | **2,2 s** | 0,4 s | **1,4 s** | 0,4 s | **2,2 s** |
| **TBT** | 0 ms | **200 ms** | 0 ms | **350 ms** | 0 ms | **430 ms** |
| **CLS** | 0 | 0,026 | 0 | 0,001 | 0 | 0 |
| **FCP** | 0,4 s | 0,9 s | 0,4 s | 1,2 s | 0,4 s | 1,0 s |
| Speed Index | 1,3 s | **3,9 s** | 0,5 s | 1,6 s | 0,4 s | 1,2 s |
| **TTFB** | 110 ms | 150 ms | 140 ms | 100 ms | 60 ms | n/d |

- **LCP móvil (0,6–2,2 s):** en verde (≤2,5 s) en las 3 páginas; `/` y `/incidents` rozan el umbral.
- **TBT móvil (200–430 ms):** es el KPI con recorrido en rendimiento; escritorio 0 ms.
- **CLS:** 0 en escritorio; móvil 0,026 (`/`) y 0,001 (`/login`) — por debajo del umbral 0,1 (verde), pero no perfecto → **guard**.
- **TTFB:** 60–150 ms ✓ (SSR de `next start` local).

### 9.4 Diagnóstico de apoyo (medido en los PDFs)

| Diagnóstico | hallazgo |
|---|---|
| Render-blocking | CSS del chunk `…css` en cadena (latencia ruta crítica 234–669 ms); **sin preconnect** |
| Long tasks | `/incidents` móvil: **8 long tasks** (`avoid-long-main-thread-tasks` ❌) |
| JS sin usar | "Reduce unused JavaScript" 21–27 KiB; "Legacy JavaScript" (polyfills Baseline) 14 KiB; "Minify JavaScript" 12 KiB |
| LCP breakdown | `elementRenderDelay` domina en móvil: 1.650 ms (`/`), 410 ms (`/login`), 250 ms (`/incidents`) |
| Errores de consola | **0** en las 6 corridas (sin 404 — a diferencia de la web) |

### 9.5 Problemas identificados (backoffice)

Convención igual que Fase 1: **[HECHO]** = reproducido en los PDFs; **[HIPÓTESIS]** = pendiente de aislamiento.

**B1 — Accesibilidad 88–96: contraste y labels `[HECHO] — corregido 2026-10-21, ver Report.md BO-C1`**
- `color-contrast` ❌: botón naranja (`button…rounded-full`), `p.text-brand-anthracite/50`, `text-zinc-400`, enlaces sobre fondo blanco.
- `select` sin `<label>` asociado (múltiples selects en `/`).
- **KPI afectado:** Accesibilidad (88–96). Auditoría secundaria respecto a los KPIs de rendimiento.
- **Resultado (móvil, antes/después):** `/` 88→100, `/login` 96→100, `/incidents` 89→100 (0 fails).

**B2 — SEO = 60 por `x-robots-tag: noindex, nofollow` `[CERRADO SIN CAMBIOS — 2026-10-21]`**
- `noindex-seo` ❌ en las 6 corridas: cabecera `x-robots-tag: noindex, nofollow` bloquea indexación (decisión deliberada para un backoffice: **esperable, probablemente no-error**). El resto de auditorías SEO (6) pasan; `robots.txt`/canonical "no aplicables" en el preview.
- **KPI afectado:** SEO (60 en todas). Verificar si se mantiene intencionadamente en producción.
- **Resolución:** la cabecera NO existe ni en el código ni en el servidor local (`curl -I localhost:3000`); la inyecta el proxy de previsualización de Codespaces. Medido localmente: SEO **100/100/100** (`/`, `/login`, `/incidents`). Ver `Report.md` BO-C2.

**B3 — TBT móvil 200–430 ms + 8 long tasks en `/incidents` `[CERRADO SIN CAMBIOS — 2026-10-21]`**
- `/incidents` móvil: TBT 430 ms y 8 long tasks; `/` 200 ms; `/login` 350 ms.
- "Reduce unused JavaScript" 21–27 KiB y "Legacy JavaScript" 14 KiB (transpilación de Baseline).
- **[HIPÓTESIS]** las long tasks proceden del bundle Next (chunks de framework/app) evaluados en el hilo principal; se validará con trazas (método C6) antes de tocar nada.
- **KPI afectado:** TBT (proxy de INP), puntuación móvil.
- **Resolución:** hipótesis confirmada con traza DevTools: única tarea larga real = `EvaluateScript` 40,8 ms del chunk runtime de Next (`appBootstrap`), más `ScriptCompiled`/`v8.run` 33 ms. Toda la traza: 1 RunTask >50 ms (52 ms). La página no tiene JS propio en el crítico. `browserslist` probado y revertido (impacto 0: chunk y transfer idénticos). TBT local ~238 ms (el baseline de 430 ms incluía el proxy de preview). Reducir más exige cambios de arquitectura (fuerza de no-goal). Ver `Report.md` BO-C3.

**B4 — CLS móvil 0,026 / 0,001 (no perfecto) `[HECHO — corregido 2026-10-21]`**
- Por debajo de 0,1 (verde) pero no 0 como la web. Causa típica en Next: fuentes/layout que llegan después del primer render.
- **Acción:** mantener CLS < 0,1 y preferirlo en 0 como guard de regresión.
- **Resolución:** traza DevTools → 1 único shift: el `<p>` "N resultados" (render condicional `!loading`) aparecía al cargar datos (+40 px) y empujaba la lista. `<p>` ahora siempre renderizado con `min-h-4`. Resultado: **CLS 0,02647 → 0,000 ×3** (local). Ver `Report.md` BO-C4.

**B5 — Render-blocking del CSS del chunk + sin preconnect `[CERRADO SIN CAMBIOS — 2026-10-21]`**
- Cadena de dependencia: documento → `…css` (8,5 KiB) con latencia 234–669 ms; ningún origen preconectado.
- **KPI afectado:** LCP móvil (elementRenderDelay 250–1.650 ms), FCP.
- **Resolución:** local solo 1 CSS crítico (ahorro est. 80 ms — 165 ms era inflación del proxy) que es obligatorio para evitar FOUC; preconnect imposible (Lighthouse: "No additional origins" — todo same-origin); woff2 de Geist ya con `preload` inyectado por `next/font`. LCP = TTFB 10 ms + elementRenderDelay 330 ms (render delay del bootstrap de Next, ver BO-C3). Sin palanca sin tocar arquitectura. Ver `Report.md` BO-C5.

### 9.6 Plan de correcciones (Fase 2 — a concretar en `Report.md`)

| # | Corrección (commit) | Problema | KPI objetivo |
|---|---|---|---|
| **B-C1** | Contraste de color + `label` en selects + heading-order | B1 | Accesibilidad ✅ (88/96/89 → 100/100/100) |
| **B-C2** | Revisar `x-robots-tag` (¿intencionado?) | B2 | SEO ✅ (era del proxy de preview; local 100×3, sin cambios) |
| **B-C3** | Reducir TBT móvil: auditar bundle (legacy/unused JS) con trazas | B3 | TBT ✅ cerrado sin cambios (tarea real = runtime Next 40 ms; local ~238 ms) |
| **B-C4** | Guard CLS móvil (0,026 → 0) | B4 | CLS ✅ (0,02647 → 0,000 ×3) |
| **B-C5** | CSS del chunk: prioridad/preconnect | B5 | LCP móvil ✅ cerrado sin cambios (CSS crítico obligatorio, "no additional origins", fonts preloaded) |

**No-goals (iguales que Fase 1):** sin reescritura ni cambio de arquitectura; 1 problema por commit; medir antes/después; KPIs de rendimiento primero, auditorías secundarias después.