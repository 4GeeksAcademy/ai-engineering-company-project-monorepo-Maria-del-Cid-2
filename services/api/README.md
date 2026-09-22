# Incident Analysis API

Servicio backend previsto para la funcionalidad **Incident Analysis** de Nexova.

## Estado actual

La Unidad 5 añade exportación segura de los resultados agregados de análisis,
además de la validación aislada y el lector/normalizador CSV:

- categorías y estados permitidos;
- códigos de errores de validación;
- modelos internos para incidencias y resultados agregados;
- lectura UTF-8 con cabecera y separador coma;
- normalización de espacios y conversión conservadora del score;
- validación de negocio con siete códigos de error estables;
- exportación agregada con columnas `metric`, `dimension` y `value`.

Todavía no incluye:

- aplicación FastAPI;
- endpoints HTTP;
- CLI;
- persistencia.

La exportación sólo recibe un `IncidentAnalysisResult` y nunca serializa filas
originales ni `customer_email`.

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
