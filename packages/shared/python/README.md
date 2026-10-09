# Nexova shared Python package

Este paquete contiene lógica Python pura compartida entre el API y los scripts
del monorepo. Actualmente expone la validación del payload del Gestor de
Incidencias; no contiene la validación histórica específica de Incident
Analysis.

Para desarrollo local, instala el paquete junto con la API:

```bash
python -m pip install -e packages/shared/python
python -m pip install -e services/api
```
