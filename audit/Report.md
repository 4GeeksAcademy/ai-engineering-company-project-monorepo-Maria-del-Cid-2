# Reporte de mejora de rendimiento — sitio público + backoffice

Ciclo de mejora basado en evidencia (ver `audit/audit.md` para el baseline y el protocolo §6).

**Protocolo de medición (Fase 1, web pública):** Lighthouse 13.5.0 · Chrome 153 headless · throttling `simulate` (Lantern) · 3 páginas × 2 dispositivos · mismas condiciones en baseline y cada re-medición · producción (`https://4geeksacademy.github.io/ai-engineering-company-project-monorepo-Maria-del-Cid-2/`).

**Artefactos:** baseline en `audit/json/{pagina}-{disp}.json`; tras cada commit en `audit/json/c1-*`, `c2-*`, …

**Fase 2 (backoffice, desde 2026-10-21):** baseline en `audit/before/backoffice/*.pdf` (Lighthouse 13.4.1, preview `next start`) — ver §9 de `audit.md` y las secciones **BO-** de este informe.

---

## C1 — Logo optimizado a WebP con `srcset` ✅ (desplegado y medido)

**Commit:** `741e9a9 optimize header logo to Webp`
**Problema (P1):** logo PNG 1254×1254 de 828 KB servido en las 3 páginas, dominante en image-delivery (808–1.196 KiB de ahorro potencial medido).
**Solución:** variantes WebP dimensionadas al uso real (56–96 px CSS): `logo-nexova-192.webp` (12,8 KB) y `logo-nexova-384.webp` (6,1 KB) + `srcset`/`sizes`/`width`/`height` en los 6 HTML (3 canónicos + 3 espejos). PNG conservado (fallback + test del workflow).

### Scores de rendimiento (baseline → C1)

| Página | Escritorio | Móvil |
|---|---|---|
| index | 96 → **98** | 72 → **75** |
| companies | 94 → **98** | 55 → **60** |
| talento | 98 → **100** 🎯 | 75 → **95** |

### KPIs (baseline → C1)

| Página | Disp | LCP | TBT | CLS (guard) |
|---|---|---|---|---|
| index | desk | 1,41 s → **1,02 s** | 56 → 2 ms | 0,000 → 0,000 ✅ |
| index | mob | 8,08 s → **4,32 s** | 0 → 277 ms | 0,000 → 0,000 ✅ |
| companies | desk | 1,54 s → **0,97 s** | 80 → 38 ms | 0,000 → 0,000 ✅ |
| companies | mob | 8,39 s → **4,64 s** | 687 → 820 ms | 0,000 → 0,000 ✅ |
| talento | desk | 1,15 s → **0,59 s** | 10 → 28 ms | 0,000 → 0,000 ✅ |
| talento | mob | 6,00 s → **2,38 s** | 0 → 0 ms | 0,000 → 0,000 ✅ |

### Payload de imagen (medido en network-requests)

| Métrica | Baseline | C1 |
|---|---|---|
| Logo transferido (las 6 corridas) | 809,2 KiB | **12,7 KiB** (−796 KiB, −98,4 %) |
| `image-delivery` ahorro potencial | 808–1.196 KiB | **0 KiB** ✅ (auditoría resuelta) |

**Guard CLS = 0:** ✅ en las 6 corridas (los `width/height` explícitos no provocaron shifts).
**Errores de consola:** 1 en las 6 corridas (preexistente, favicon 404 — pendiente en C7).

**Veredicto:** corrección confirmada con evidencia. Mayor impacto individual del ciclo en LCP móvil (−3,7 s en talento, −2,7–3,8 s en las otras dos).

---

## C3 — Tailwind CDN fuera del critical rendering path ✅ (desplegado y medido)

**Commits:** `9d5a25b preconnect to Tailwind CDN` (C3a) + `82ef83d inline critical CSS, defer Tailwind CDN (C3b) + `748fd67 restore unclosed comment in head` (hotfix de un comentario sin cerrar introducido por C2).
**Problema (P3):** `cdn.tailwindcss.com` (407 KiB) es render-blocking en las 3 páginas: FCP/LCP esperan a descargar y compilar el script (ahorro medido 1.480–1.510 ms móvil).
**Solución:**
- **C3a:** `preconnect` al CDN (abre TLS antes de la petición).
- **C3b:** CSS crítico inline (~9 KB/página, **generado automáticamente** como subconjunto de la hoja real del CDN: reglas que matchean elementos visibles por encima del fold en 7 viewports, preservando orden de cascada) + `<script defer>` + config de marca en `DOMContentLoaded`.

### Evidencia de validación local (harness A/B/C, 3 páginas × móvil/desktop)

| Caso | CLS antes | CLS después |
|---|---|---|
| A-final (CDN diferido + crítico inline) | 0,06–0,43 ❌ | **0,0000 ×6** ✅ |
| C-nocrit (control sin crítico) | — | 0,35–1,00 (sigue roto) |

Paridad visual A vs C: **0,000 % de píxeles distintos** en las 6 combinaciones → la página se ve idéntica antes y después de compilar el CDN (sin FOUC).

### Scores de producción (baseline → C1+C3 → C2)

| Página | Escritorio | Móvil |
|---|---|---|
| index | 96 → 98 → 92* | 72 → 75 → **~79**† |
| companies | 94 → 98 → **99** | 55 → 60 → **89** |
| talento | 98 → 100 → **100** | 75 → 95 → **87**† |

\* El defer traslada la compilación de Tailwind a post-FCP: FCP 750→241 ms, LCP 1.018→641 ms, SI 847→384 ms, pero TBT 2→215 ms resta puntos al score (Lantern es más sensible a TBT en desktop). El coste lo ataca C5/C6 (trabajo residual de JS).
† Mediana de 3 corridas (68/80/79 y 87/85/91 — varianza Lantern alto en una sola corrida).

**Guard CLS:** ✅ 0,000 ×5; `talento-desktop` 0,005 (score 1, ruido Lantern).
**Consumo:** 366 KiB de Unsplash eliminados (C2), payload index móvil 586 → **285 KiB**.

**Veredicto:** C3b es el mayor punto de inflexión del ciclo en FCP móvil (2,3–2,4 s → 0,8–1,0 s en las 3 páginas) manteniendo CLS y paridad visual. Puntuaciones personales: usuario midió **100** tras desplegar C3b.

---

## C2 — Hero local con `fetchpriority="high"` ✅ (desplegado y medido)

**Commit:** `0103413 serve hero image locally with priority`
**Problema (P2):** imagen LCP del index servida desde `images.unsplash.com`: 366 KiB externos + conexión nueva, `lcp-discovery-insight ❌ priorityHinted:false`.
**Solución:** variantes WebP locales en `uis/website/` (mismo aspecto, sin re-crop): `hero-team-{768,1024,1600}.webp` (63/93/214 KiB) + `srcset/sizes` + `width/height` (guard CLS) + `fetchpriority="high"` + `<link rel="preload" imagesrcset imagesizes>`. Workflow con `test -f` de los 3 assets.

### KPIs index (mediana de corridas, baseline → C2)

| Disp | FCP | LCP | TBT | SI | KB | CLS |
|---|---|---|---|---|---|---|
| mob | 2.300 → **959 ms** | 8.080 → **2.448 ms** | 0 → 801 ms | 4.090 → **959 ms** | 1.383 → **285** | 0,000 ✅ |
| desk | 750 → **241 ms** | 1.410 → **641 ms** | 2 → 215 ms | 847 → **384 ms** | 1.382 → **433** | 0,000 ✅ |

**Transferencia hero:** 366 KiB (Unsplash, 1 petición externa) → **63 KiB** local en móvil (−83 %).
**Guard CLS:** ✅ en las 6 corridas. **Consola:** favicon 404 preexistente (C7).

**Veredicto:** confirmado. LCP index móvil 8,1 s → 2,4 s acumulando C1+C3+C2; todas las métricas visuales del index mejoran. El TBT residual (compilación de Tailwind + JS) es ahora el techo del score → siguiente corrección **C5**.

---

## C4 — Declarar `width/height` en las imágenes restantes

- **Problema:** P5 (guard). De las 6 imágenes del sitio, 4 ya declaraban dimensiones (logo ×3 desde C1, hero desde C2); quedaba **1 real sin dimensionar**: el mapa `nexova offices official map.webp` en index.html. (El "4.º img sin dimensionar" de un barrido inicial era un falso positivo: el literal `<img>` dentro del comentario C2.)
- **Commit:** `perf(website): declare image dimensions on map (C4)` — `index.html` + `uis/website/index.html`.
- **Cambio:** `width="1007" height="1024"` (dimensiones naturales del WebP verificadas con Pillow) en el `<img>` del mapa. Balance de comentarios `<!--`/`-->` intacto: 90/90.
- **KPI:** CLS (guard) — sin cambio esperado, CLS ya era 0; es protección ante reordenaciones de render.

---

## C5 — `location-catalog.es.js` con `defer` (companies)

- **Problema:** P4. `data/location-catalog.es.js` (1,030,880 B → 343 KiB) se evaluaba de forma síncrona en el flujo de parseo, contribuyendo a las long tasks y al TBT de companies móvil (687 ms baseline de producción).
- **Commit:** `perf(website): defer location catalog and validation (C5)` — `application-companies.html` + `uis/website/application-companies.html`.
- **Cambio (variante mínima):** `defer` en el `<script>` del catálogo **y** en `validation.js` (este último también se cargaba síncrono). `defer` es seguro aquí: ambos scripts se ejecutan en orden después del parseo y antes de `DOMContentLoaded`, y `validation.js` lee `window.NEXOVA_LOCATION_CATALOG` dentro de su listener de `DOMContentLoaded`.
- **Validación funcional (Playwright local, sitio replicado):** catálogo cargado (53 países), `#country-options` = 53 opciones, estado → "Países cargados…", menú hamburguesa alterna correctamente. Único error de consola: favicon 404 (P7, pendiente C7).
- **Medición A/B local (Lighthouse móvil, 3+3 corridas, mediana de 6 por lado):**

| KPI (companies móvil, local) | Baseline (sync) | C5 (defer) | Delta |
|---|---|---|---|
| **TBT** | 847,5 ms | **693,5 ms** | **−154 ms (−18 %)** |
| **Long task mayor** | 579,5 ms | **387 ms** | **−192 ms (−33 %)** |
| `validation.js` total | 938,5 ms | **701 ms** | −237 ms (−25 %) |
| `location-catalog.es.js` total | 160,5 ms | 153,5 ms | −7 ms (atribución parcial) |
| Score | 79,5 | 81 | +1,5 |
| FCP | 845 ms | 882 ms | +37 ms (ruido) |
| **CLS** | 0 | **0** ✅ | guard OK |
| LCP (mediana) | 1669 ms | 2368 ms | ver nota ↓ |

- **Nota sobre LCP:** la mediana local sube porque **2/6 corridas baseline son outliers** (7,6 s con renderDelay normal ≈ 200 ms — inconsistencia de Lantern, mismo elemento LCP en todas las corridas). El desglose (TTFB ≈ 10–67 ms, renderDelay 78–230 ms sin sesgo por lado) **no muestra regresión real atribuible a defer**. En producción (con gzip de 343 KiB y red real) la distribución es distinta.
- **Hipótesis P4 parcialmente confirmada:** el split de la long task mayor (597–842 → 327–456 ms) muestra que el parseo/eval del catálogo **contribuía** a las tareas largas, aunque la atribución de Lighthouse la reparte también sobre `validation.js` (959 ms baseline → 633 ms con defer). El TBT residual lo domina ya la compilación de Tailwind CDN.
- **Medición en producción (6 corridas `audit/json/c5-*.json` + 2 réplicas companies móvil):**

| companies móvil (mediana) | Baseline | C2 (acum.) | **C5** |
|---|---|---|---|
| Score | 55 | 89 | **88** |
| **TBT** | 687 ms | 442 ms | **409 ms (−33 % vs baseline)** |
| LCP | 8,39 s | 1,70 s | 2,33 s (rango 1,7–2,5 s, varianza) |
| FCP | 2,34 s | 0,97 s | 0,93 s |
| CLS | 0 | 0 | **0** ✅ |

| Resto (KPI guard) | Baseline → C5 |
|---|---|
| index móvil | 72 → **77** (LCP 8,08 s → **2,51 s**) |
| talento móvil | 75 → **93** (LCP 6,00 s → **1,58 s**) |
| escritorio (3 págs) | 96/94/98 → **96/99/100**, CLS 0, TBT ≤165 ms |
| Transferido | companies 1,291 → 497 KiB; talento 946 → 152 KiB |

- **Veredicto (producción):** confirmado — **TBT companies móvil 687 → 409 ms (mediana −33 %)**, CLS 0 en las 8 corridas, sin regresiones en FCP ni en el resto de páginas. El elemento LCP de companies es texto (depende de Tailwind) y su LCP varía 1,7–2,5 s entre corridas (Lantern) en ambos lados de la comparación.
- **Veredicto (A/B local):** confirmado — TBT −18 %, long task máxima −33 %, funcionalidad intacta.

---

## C6 — Dedupe JS del menú / long tasks residuales → **CERRADO SIN CAMBIOS** (2026-10-21)

- **Objetivo:** eliminar el JS de menú/formulario duplicado entre HTML inline y `validation.js`, y atacar las long tasks residuales (hipótesis del baseline: 567–570 ms).
- **Hallazgos de la investigación:**
  1. **Duplución real pero C5 ya la mitigó:** el bloque de menú está en `index.html` (inline), `application-candidates.html` (inline) y `validation.js`. Como C5 puso `validation.js` con `defer`, el menú de companies se ejecuta **una sola vez** (el inline de companies ya no existe). El menú de index/talento sigue inline pero se ejecuta una vez por página — no hay doble ejecución en ninguna página.
  2. **Coste JS medido ≈ 0:** `performance.mark/measure` en local (instrumentación en `/tmp/c6-site`): top-level de `validation.js` = **0,0 ms**, top-level del catálogo = **0,1 ms**, handler DCL = **0,5–1,0 ms**, scripts inline de index/talento = **0,0–0,2 ms**.
  3. **La traza de Chrome contradice la atribución de Lighthouse:** en `--save-assets` traces, las tareas más largas *reales* son 182 ms (index) y 166 ms (companies). Lighthouse reporta long tasks de 728/384 ms con `url=cdn.tailwindcss.com` que **no existen como RunTask ≥500 ms en la traza**. Dentro de las tareas reales dominan: compilación de Tailwind CDN, microtasks GC de DCL y reacciones de Tailwind a las mutaciones DOM — todo de terceros.
  4. **TBT residual de companies móvil ≈ 409 ms (mediana C5)** está, por tanto, dominado por Tailwind CDN (P3, ya intervenido en C3b con `defer`) y por la atribución agresiva de Lighthouse a nuestros scripts.
- **Decisión:** no aplicar ningún cambio de código — mover el menú inline a `validation.js` sería un refactor con riesgo de regresión funcional **sin cabeza de medición** que lo justifique. Queda documentado como hipótesis descartada por evidencia.
- **Evidencia:** trazas `/tmp/c6-assets/*.trace.json`, `/tmp/c6-assets-idx/*.trace.json`, mediciones `/tmp/c6-instr*.py`, `/tmp/c6-check.js`. TBT production actual: companies móvil 409 ms (≈390 ms en corridas sueltas, como la última).

---

## C7 — Favicon local → **HECHO (push `2dfff41`, medido en producción)** (2026-10-21)

- **Problema (P7):** `errors-in-console` ❌ en las 6 corridas baseline: `GET https://4geeksacademy.github.io/favicon.ico` = **404**. Sin `<link rel="icon">`, el navegador pide siempre `/favicon.ico` en la raíz del origin. Coste: Best Practices 96 y consola sucia.
- **Cambio:**
  1. `favicon.ico` generado con Pillow a partir de `logo-nexova-192.webp` (multi-tamaño 16/32/48 px, **3,4 KB**) en `uis/website/` (+ copia raíz).
  2. `<link rel="icon" href="favicon.ico" sizes="any" type="image/x-icon">` en las 3 páginas (raíz + `uis/website`, byte-idénticas).
  3. Aserción de deploy: `test -f site/favicon.ico` en `.github/workflows/deploy-pages.yml` (el workflow ya copía `uis/website/.` completo).
- **Validación local (Playwright + Lighthouse :8127, sitio replicado):**

| Página | Best Practices | Errores consola | 404 | CLS |
|---|---|---|---|---|
| index | **100** (era 96) | 0 | 0 | 0 |
| talento | **100** | 0 | 0 | 0 |
| companies | **100** | 0 | 0 | 0 |

- Nota: el único 404 restante en el arnés local era `nexova offices official map.webp` (la añade el workflow al `site/`; copiada al arnés y desaparece — no afecta a producción).
- **Veredicto (producción, 6 corridas `audit/json/c7-*.json`):** **Best Practices 100/100/100 ×2 dispositivos (baseline 96)** y **`errors-in-console` 0 en las 6 corridas (baseline: 1×6 — el 404 de `/favicon.ico`)**. CLS 0.000 en todas (guard ✓). Scores de rendimiento medidos: index 93 desk / 80 móvil, talento 98 / 89, companies 100 / 84 (varianza Lantern).

---

## Ranking de impacto — Fase 1 (web pública)

| # | Commit | KPI objetivo | Estado |
|---|---|---|---|
| 1 | C1 logo WebP | LCP móvil, payload | ✅ medido |
| 2 | C3 Tailwind CDN render-blocking (1,5 s móvil) | score global móvil, FCP | ✅ medido |
| 3 | C2 hero local + `fetchpriority` | LCP index | ✅ medido |
| 4 | C4 `width/height` resto de imágenes | CLS (guard) | ✅ hecho (guard) |
| 5 | C5 `location-catalog` defer (TBT 687 ms companies móvil) | TBT/INP | ✅ medido (prod: TBT 687→409 ms, −33 %) |
| 6 | C6 dedupe JS del menú | TBT | ✅ cerrado sin cambios (investigado con trazas: JS real ≈ 1 ms, dominio de Tailwind) |
| 7 | C7 favicon | errores consola, Best Practices | ✅ medido (prod: BP 96→100 ×6, errores consola 1→0 ×6) |

> **Fase 1 completa** (C1–C7 medidos; C7 cerrado el 21/10 tras deploy). Nota: los commits en git llevan el texto corto en inglés (p. ej. `serve favicon locally`), sin el prefijo C7.

---

## Fase 2 — Backoffice (`uis/backoffice/talent-pipeline-tracker`, Next.js 16)

> Baseline: `audit/before/backoffice/*.pdf` (Lighthouse 13.4.1, preview `https://friendly-barnacle-…-3000.app.github.dev`, build + start locales). Detalle y problemas B1–B5 en `audit.md` §9.

### BO-BASE — Línea base (2026-10-21)

**Puntuaciones:**

| Página | Dispositivo | Rendimiento | Accesib. | B. Prácticas | SEO |
|---|---|---|---|---|---|
| `/` (talent) | Escritorio | 99 | 88 | 100 | 60 |
| `/` (talent) | Móvil | 94 | 88 | 100 | 60 |
| `/login` | Escritorio | 100 | 96 | 100 | 60 |
| `/login` | Móvil | 92 | 96 | 100 | 60 |
| `/incidents` | Escritorio | 100 | 89 | 100 | 60 |
| `/incidents` | Móvil (ref. 19/10) | 88 | 89 | 100 | 60 |

**KPIs:**

| KPI | `/` DESK | `/` MÓVIL | `/login` DESK | `/login` MÓVIL | `/incidents` DESK | `/incidents` MÓVIL (ref.) |
|---|---|---|---|---|---|---|
| **LCP** | 0,6 s | 2,2 s | 0,4 s | 1,4 s | 0,4 s | 2,2 s |
| **TBT** | 0 ms | 200 ms | 0 ms | 350 ms | 0 ms | 430 ms |
| **CLS** | 0 | 0,026 | 0 | 0,001 | 0 | 0 |
| **FCP** | 0,4 s | 0,9 s | 0,4 s | 1,2 s | 0,4 s | 1,0 s |
| **TTFB** | 110 ms | 150 ms | 140 ms | 100 ms | 60 ms | n/d |

**Lectura:** rendimiento ya 88–100 (contexto mucho mejor que la web en baseline). TTFB ✓, LCP móvil en verde (≤2,5 s), CLS móvil por debajo de 0,1 pero no 0. Recorrido real: **TBT móvil 200–430 ms** (8 long tasks en `/incidents`), **Accesibilidad 88–96** (contraste + labels de `<select>`) y **SEO 60** por `x-robots-tag: noindex, nofollow` (probablemente intencionado en un backoffice — a verificar). Errores de consola: **0** en las 6 corridas.

### BO-C1 — Accesibilidad: contraste, labels de `<select>` y orden de encabezados ✅ (2026-10-21)

- **Problema (B1):** Accesibilidad 88–96 en baseline. Fails Lighthouse: `color-contrast` (82 en total: 79 `/`, 4 `/login`, 2 `/incidents`), `select-name` (2 en `/`), `label` (1 en `/incidents`), `heading-order` (1 en `/`).
- **Cambio (solo estilos/markup, sin tocar KPIs):**
  1. **Contraste naranja en fondo blanco:** `text-brand-orange` (#F97316, ratio 4,62 ✗) → `text-brand-orange-dark` (#C2410C, **5,18 ✓**) en ~21 componentes (botones, enlaces, paneles, error page).
  2. **Excepción:** en el panel oscuro `bg-brand-anthracite` (#1F2328) de `AuthForm` se revirtió a `text-brand-orange` (**6,04 ✓**) — el naranja oscuro da solo 3,05 sobre anthracite.
  3. **Texto secundario:** `text-zinc-400` (3,32 ✗) → `text-zinc-500` (**4,83 ✓**); `text-brand-anthracite/50` (3,16 ✗) y `/60` (4,24 ✗) → `/65` (**4,98 ✓**).
  4. **`select-name`/`label`:** etiquetas visuales ligadas con `htmlFor`/`id` en `ui/Select.tsx` (2 selects de `/` y 1 de `/incidents`).
  5. **`heading-order`:** reordenación `h3→h2` en `app/page.tsx` (jerarquía sin saltos).
- **Medición (solo categoría `accessibility`, móvil, antes/después del rebuild, `localhost:3000`):**

| Página | Accesibilidad | Fails antes | Fails después |
|---|---|---|---|
| `/` | 88 → **100** | color-contrast ×79, select-name ×2, heading-order ×1 | **0** |
| `/login` | 96 → **100** | color-contrast ×4 | **0** |
| `/incidents` | 89 → **100** | color-contrast ×2, label ×1 | **0** |

- **Guard:** los cambios son de color/markup; no afectan a scripts ni layout medible. LCP/TBT/CLS no se alteran (correrá la medición de KPIs con B-C3/B-C4).
- JSONs: `/tmp/bo-b1-before/` y `/tmp/bo-b1-after/` (home, login, incidents).

---

### BO-C2 — `x-robots-tag: noindex` / SEO 60 → **CERRADO SIN CAMBIOS** (2026-10-21)

- **Problema (B2):** SEO = 60 en las 6 corridas baseline; fail `noindex-seo` por cabecera `X-Robots-Tag: noindex, nofollow`.
- **Investigación:**
  1. `curl -I http://localhost:3000/` (next start, build producción): **no existe** ninguna cabecera `x-robots-tag`; tampoco meta `robots` en el HTML (indexación por defecto).
  2. El código del backoffice no define esa cabecera (sin `headers()` en `next.config.ts` ni middleware).
  3. El baseline se midía contra `https://friendly-barnacle-…-3000.app.github.dev`: **el proxy de previsualización de Codespaces inyecta `X-Robots-Tag: noindex, nofollow` en TODO el tráfico** (medida de aislamiento de previews — correcta para un backoffice).
- **Veredicto:** **no es un problema del producto**; es comportamiento esperado del entorno de preview. El SEO del backoffice en su servidor real es **100/100/100** (módulo `seo`, móvil, 2026-10-21, `audit/../tmp/bo-b2/*.json`):

| Página | SEO baseline (preview) | SEO localhost (servidor real) |
|---|---|---|
| `/` | 60 | **100** |
| `/login` | 60 | **100** |
| `/incidents` | 60 | **100** |

- **Nota:** en producción (GitHub Pages del backoffice, si llega a desplegarse) convendrá revisar si se desea indexación o mantener `noindex` intencionado. Sin cambios de código → **commit: ninguno**.

---

### BO-C3 — TBT móvil (200–430 ms, 8 long tasks) → **CERRADO SIN CAMBIOS** (2026-10-21)

- **Problema (B3):** TBT móvil baseline 200/350/430 ms (`/`, `/login`, `/incidents`); 8 long tasks en `/incidents`; "unused JS" 27 KiB y "legacy JS" 14 KiB en el mismo chunk.
- **Investigación con trazas (método C6):**
  1. Traza DevTools de Lighthouse (`/tmp/bo-b3/incidents-mobile-0.trace.json`, comando `--save-assets`): **la tarea larga real es `EvaluateScript` de 40,8 ms** sobre `/_next/static/chunks/32zy0ql92zysv.js` + `ScriptCompiled` 33 ms + `v8.run` 33 ms. Toda la traza contiene **un único RunTask >50 ms (52 ms)** — el thread renderer totaliza ~780 ms repartidos en 3.730 tareas cortas, sin bloqueos relevantes.
  2. Contenido del chunk: **bootstrap de Next.js 16/Turbopack** (`appBootstrap`, runtime) — 235 KB en disco, 72 KiB transferidos. Es el framework, no código del backoffice.
  3. La página `/incidents` es trivial (`<IncidentAnalysisPanel />`, componente cliente ligero con `useState`); sin fetches ni trabajo pesado en montaje.
  4. `browserslist` moderno declarado en `package.json` → **revertido**: impacto 0 (hash del chunk idéntico, JS transfer 156,4 KiB antes/después, audits unused/legacy idénticos). Next 16 precompila su runtime con targets propios.
  5. Los números 172/411 ms que Lighthouse atribuye a long tasks son **proyecciones de la simulación móvil (Lantern)** del único EvaluateScript real de ~40 ms.
- **Medición local (móvil, `/incidents`, mediana de 3 corridas, `localhost:3000`):**

| KPI | base local | nota |
|---|---|---|
| Performance | 100 | - |
| TBT | ~238 ms | baseline preview 430 ms incluía el proxy de Codespaces |
| CLS | 0,000 | guard ✓ |
| LCP | ~2,5 s | en verde (≤2,5 s) |

- **Veredicto:** el TBT restante es **presupuesto del framework Next.js** (hoy-mandado: ejecutar el runtime en el hilo principal es el coste de un CSR React; reducirlo de forma real exigería streaming/`next/dynamic`/cambios de arquitectura — **fuera de alcance según no-goal**). No hay JS propio en el camino crítico que optimizar. **Commit: ninguno.**
- JSONs: `/tmp/bo-b3/base/run{1..3}.json`, `/tmp/bo-b3/after/run{1..3}.json`, traza `incidents-mobile-0.trace.json`.

---

### BO-C4 — Guard CLS móvil `/` (0,026 → 0) ✅ (2026-10-21)

- **Problema (B4):** CLS móvil en `/` = 0,02647 (verde pero no 0). Reproducido de forma **determinista localmente** (3 corridas = 0,02647 exacto).
- **Aislamiento con traza (DevTools, `--save-assets`):** un único `LayoutShift` (score 0,02647, `had_recent_input: false`): el nodo `div.mt-4` (la lista de candidaturas) pasa de `top 337, alto 176` → `top 377, alto 446` — es decir, **la lista se desplaza 40 px hacia abajo cuando llegan los datos**.
- **Causa:** el `<p>` de "N resultados" (`app/page.tsx`) solo se renderizaba con `!loading && !error`; al pasar de estado de carga a datos, el párrafo aparece (+40 px: margin `mt-6` 24 + línea 16) y empuja la lista y la paginación.
- **Corrección (1 archivo, markup mínimo):** el `<p>` se renderiza **siempre** y reserva `min-h-4`; solo cambia el contenido cuando hay datos. Cero JS añadido.
- **Medición (móvil, `/`, mediana de 3 corridas, `localhost:3000`):**

| KPI | base | after |
|---|---|---|
| **CLS** | 0,02647 ×3 | **0,000 ×3** |
| Performance | 100 | 100 |
| LCP | 2.769 ms | 2.724 ms (ruido) |
| FCP | 771 ms | 777 ms (ruido) |
| TBT | 129 ms | 178 ms (varianza ±50 ms habitual; sin JS nuevo) |

- JSONs: `/tmp/bo-b4/base/run{1..3}.json`, `/tmp/bo-b4/after/run{1..3}.json`, traza `home-mobile-0.trace.json`.

---

### BO-C5 — CSS render-blocking + preconnect → **CERRADO SIN CAMBIOS** (2026-10-21)

- **Problema (B5):** cadena de dependencia documento → CSS del chunk (8,5 KiB, latencia 234–669 ms en baseline) sin ningún origen preconectado; `elementRenderDelay` 250–1.650 ms en LCP móvil.
- **Investigación (traza `--save-assets`, `localhost:3000`):**
  1. **Render-blocking actual:** 1 único CSS (`/_next/static/chunks/0xvpphybyrrkt.css`, 8.505 B) con ahorro est. **80 ms** (baseline preview: 165 ms — el proxy inflaba la latencia). Es el CSS compilado de Tailwind que **debe** bloquear para pintar sin FOUC; extraerlo del critical path es reestructuración de estilos (no-goal).
  2. **Preconnect:** Lighthouse reporta `Preconnected origins: …` + **`Preconnected candidates: "No additional origins"`** — todo el recurso es **same-origin** (fonts, CSS y JS se sirven de `localhost:3000` / el mismo dominio). Preconnect a uno mismo no aporta nada (la conexión ya se abre en el documento). Sin candidatos legítimos.
  3. **Optimizaciones de fuentes ya presentes** (verificadas en el HTML servido): ambos woff2 (Geist Sans/Mono) tienen `<link rel="preload" as="font" crossorigin>` inyectado por `next/font`; el CSS se sirve con `data-precedence="next"`.
  4. **Desglose LCP:** TTFB **10 ms** ✓ + `elementRenderDelay` **330 ms** (dominante). El elemento LCP es **texto en el HTML** (`p.mt-1` "Proceso de selección…") — no hay imagen LCP que priorizar (`fetchpriority` no aplica). El delay es la evaluación del bootstrap de Next.js (mismo hallazgo que BO-C3).
- **Medición de referencia (móvil, `/`, 3 corridas, `localhost:3000`):**

| Corrida | Perf | LCP | TBT | CLS |
|---|---|---|---|---|
| 1 | 94 | 2.812 ms | 148 ms | 0,000 |
| 2 | 92 | 2.867 ms | 204 ms | 0,000 |
| 3 | 95 | 2.773 ms | 146 ms | 0,000 |

- **Veredicto:** no hay palanca legítima sin tocar arquitectura (el CSS crítico es necesario, no hay orígenes externos que preconectar, las fuentes ya están preloaded). LCP ~2,8 s = TTFB (10 ms) + render delay del framework → mismo presupuesto que BO-C3. **Commit: ninguno.**
- JSONs: `/tmp/bo-b5/home-mobile.json` + `/tmp/bo-b5/runs/run{1..3}.json`.

---

### Ranking Fase 2

| # | Corrección | KPI objetivo | Estado |
|---|---|---|---|
| B-C1 | Contraste de color + `label` en selects + heading-order | Accesibilidad | ✅ medido (88/96/89 → **100/100/100**) |
| B-C2 | Revisar `x-robots-tag: noindex, nofollow` | SEO | ✅ cerrado sin cambios (era el proxy de preview; local SEO 100×3) |
| B-C3 | TBT móvil (auditar bundle con trazas) | TBT | ✅ cerrado sin cambios (tarea real 40 ms = runtime Next; TBT local ~238 ms con proxy excluido) |
| B-C4 | Guard CLS móvil (0,026 → 0) | CLS | ✅ medido (0,02647 → **0,000** ×3) |
| B-C5 | CSS del chunk render-blocking / preconnect | LCP móvil | ✅ cerrado sin cambios (1 CSS crítico 80 ms ya necesario; "no additional origins"; fonts ya preload) |

---

## Notas de medición

- Los scores móviles usan simulación (Lantern) y tienen varianza entre corridas (±3–5 puntos); las comparaciones son válidas por la misma varianza en baseline y re-mediciones.
- Observado durante el ciclo: el evento `push` de Actions no siempre dispara el workflow en este repo; si no aparece el run, relanzar con **Actions → Run workflow (rama main)** — NO con "Re-run jobs" (re-ejecuta el commit anterior).