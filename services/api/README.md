# Incident Analysis API

Servicio backend previsto para la funcionalidad **Incident Analysis** de Nexova.

## Estado actual

La Unidad 8 añade almacenamiento temporal en memoria del último resultado y
`GET /api/incidents/results/export`. La Unidad 7 añade una aplicación FastAPI
con `POST /api/incidents/analyze`. La
Unidad 6 añade una CLI que ejecuta el análisis y, opcionalmente, la
exportación segura de los resultados agregados. La Unidad 5 añadió la
exportación segura de los resultados agregados de análisis,
además de la validación aislada y el lector/normalizador CSV:

- categorías y estados permitidos;
- códigos de errores de validación;
- modelos internos para incidencias y resultados agregados;
- lectura UTF-8 con cabecera y separador coma;
- normalización de espacios y conversión conservadora del score;
- validación de negocio con siete códigos de error estables;
- exportación agregada con columnas `metric`, `dimension` y `value`.
- CLI ejecutable con `python scripts/analyze.py <ruta.csv>`.
- endpoint multipart `POST /api/incidents/analyze` para analizar un CSV.
- endpoint `GET /api/incidents/results/export` para descargar el último
    resultado agregado como CSV.

La funcionalidad Supplier Directory se integrará en esta misma aplicación
FastAPI. El prefijo actual de rutas es explícito (`/api`) en cada endpoint de
Incident Analysis; por tanto, el router futuro de proveedores deberá exponer el
contrato `/api/suppliers` sin crear una segunda aplicación FastAPI.

La persistencia inicial del Supplier Directory utiliza TinyDB y queda aislada
en `app/suppliers/database.py`. En esta unidad sólo se añaden los contratos
Pydantic y la inicialización de TinyDB; todavía no se implementan el seeder,
los endpoints ni el frontend.

Todavía no incluye:

- persistencia.

La exportación sólo recibe un `IncidentAnalysisResult` y nunca serializa filas
originales ni `customer_email`.

La CLI termina preguntando `Export results to CSV? [y / n]:`; responde `y` para
crear `results.csv` en el directorio de ejecución o `n` para no crear ningún
archivo.

### Ejecutar la API

Instala las dependencias del servicio y arranca FastAPI con:

```bash
cd services/api
python -m pip install -e .
uvicorn app.main:app --reload
```

El endpoint recibe el campo multipart `file` y devuelve únicamente métricas
agregadas. Los archivos ausentes, vacíos, no CSV o mal formados responden con
HTTP 400.

Después de un análisis correcto, el resultado agregado se conserva sólo en
memoria y el endpoint GET lo exporta reutilizando `export_analysis_csv`. Si aún
no existe un análisis, responde HTTP 404. No se almacenan filas originales,
emails ni persistencia en disco.

## Estructura prevista

```text
services/api/
├── app/
│   └── incidents/
│       ├── constants.py
│       └── models.py
└── tests/
    └── test_models.py
```

La lógica de dominio se mantendrá separada de los adaptadores HTTP y CLI para que ambos puedan reutilizarla sin duplicación.

## Verificación actual

Desde la raíz del repositorio:

```bash
PYTHONPATH=services/api python -m unittest discover -s services/api/tests -p 'test_*.py'
```

La configuración de dependencias y ejecución de FastAPI se añadirá en la unidad correspondiente, cuando se implemente la API.

## Configuración de autenticación y CORS

Configura `CORS_ORIGINS` como una lista separada por comas de orígenes exactos
(esquema, host y puerto), sin comodines. Si no se define, se permiten los
orígenes de desarrollo `http://localhost:3000` y el Codespace configurado en
`app/main.py`. En despliegues no locales, establece explícitamente la allowlist
del frontend; el servidor rechaza `*`. Se permiten los headers `Authorization`
y `Content-Type`, y el método `PUT` necesario para actualizar perfiles.

La base de autenticación usa TinyDB. El registro serializa la comprobación y la
creación de emails dentro del proceso, por lo que el servicio debe ejecutarse
con un único worker. Este lock no coordina varios procesos; desplegar varios
workers requiere una persistencia con unicidad atómica para el email.
