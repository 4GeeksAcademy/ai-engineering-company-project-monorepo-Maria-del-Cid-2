# Incident Analysis API

Servicio backend previsto para la funcionalidad **Incident Analysis** de Nexova.

## Estado actual

La Unidad 7 añade una aplicación FastAPI con `POST /api/incidents/analyze`. La
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
