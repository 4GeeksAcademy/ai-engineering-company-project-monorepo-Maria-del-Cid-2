# `scripts` folder

This folder contains **helper scripts** for the monorepo: development automation, maintenance utilities, repetitive tasks (setup, lint, migrations, data generation, etc.), and internal tooling.

- **Main purpose**: group support tools that do not belong to a specific app, agent, or pipeline but make the team’s work easier.
- **Recommendation**: document each script (what it does, parameters, requirements, usage examples) and keep them reproducible (and safe) across environments.

> _Spanish version: [README.es.md](./README.es.md)._

## Incident Manager

`seed_incidents.py` carga el histórico oficial de `incidents-nexova.csv` en el
gestor persistente. El script no genera ni sustituye el CSV y debe ejecutarse
con `INCIDENTS_DB_PATH` apuntando a una base aislada cuando se está validando.
