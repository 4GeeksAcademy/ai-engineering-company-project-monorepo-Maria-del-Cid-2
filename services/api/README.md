# Incident Analysis API

Servicio backend previsto para la funcionalidad **Incident Analysis** de Nexova.

## Estado actual

La Unidad 3 añade validación aislada sobre los contratos mínimos del dominio y el
lector/normalizador CSV:

- categorías y estados permitidos;
- códigos de errores de validación;
- modelos internos para incidencias y resultados agregados;
- lectura UTF-8 con cabecera y separador coma;
- normalización de espacios y conversión conservadora del score;
- validación de negocio con siete códigos de error estables.

Todavía no incluye:

- aplicación FastAPI;
- endpoints HTTP;
- CLI;
- exportación;
- persistencia.

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
