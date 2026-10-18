# Aprendiendo: gestión de inventario con ORM y doble base de datos

## Estado de esta fase

Este documento recoge la investigación y las decisiones necesarias para preparar una futura gestión de inventario. **No implica que el dominio de inventario esté implementado.** En esta fase no se han añadido modelos, routers, movimientos, cálculo de stock, semillas ni migraciones.

### Hechos observados e infraestructura implementada

- La API actual está en `services/api` y utiliza FastAPI.
- Autenticación, perfiles, Supplier Directory e Incident Manager persisten actualmente en TinyDB, con configuración propia por dominio.
- La identidad primaria de autenticación sigue siendo `User.id`, entero almacenado en TinyDB. El JWT conserva `sub=str(user.id)` y `get_current_user` resuelve ese ID en TinyDB.
- Los usuarios creados desde esta fase reciben un `user_uuid` generado en el servidor y persistido junto al usuario. El campo es opcional al parsear: documentos históricos sin él siguen siendo legibles y autenticables; su lectura no asigna ni persiste un UUID.
- `services/api/pyproject.toml` declara SQLModel (`sqlmodel>=0.0.24,<0.1`) y psycopg (`psycopg[binary]>=3.2,<4`); `uv.lock` fija las versiones resueltas. El entorno `uv` del servicio se usa para ejecutar el backend.
- `services/api/app/inventory/database.py` contiene la configuración aislada. Lee `DATABASE_URL` al solicitar el engine, crea el engine de forma perezosa y proporciona `get_session` con cierre garantizado. La importación del módulo no lee configuración ni crea engine; crear el engine tampoco abre por sí solo una conexión.
- No hay modelos ni router de inventario registrado. `main.py` no se ha conectado a PostgreSQL ni se han alterado el contrato JWT, el ID entero de usuario o los flujos de autenticación. La adición no disruptiva del UUID persistido para usuarios nuevos se describe en la sección de identidad.
- Las rutas actuales de la API incluyen el prefijo `/api`; esto no determina por sí solo el prefijo final del futuro módulo de inventario.

### Supuestos de trabajo, no decisiones aprobadas

- La propuesta considerada es mantener las persistencias actuales y añadir PostgreSQL como almacén independiente para inventario.
- SQLModel proporciona la futura capa de modelos y las sesiones síncronas sobre SQLAlchemy; esta fase solo implementa engine/sesión y no declara modelos.
- PostgreSQL será el destino de producción; SQLite podría servir para pruebas rápidas de la capa ORM, no para certificar propiedades específicas de PostgreSQL.

### Decisiones abiertas

1. **Identidad y propiedad de datos:** `user_uuid` ya existe para nuevos usuarios como identificador persistente adicional, pero no sustituye al ID entero ni al `sub`. Los usuarios antiguos pueden continuar sin UUID. La asignación a los existentes requiere una operación explícita, idempotente y aprobada por separado; no hay backfill automático ni asociación de inventario implementada.
2. **Prefijo HTTP:** decidir entre `/api/inventory/...` y `/inventory/...`. La convención actual `/api` es un antecedente, no una aprobación del nuevo contrato.
3. **Dependencias:** las dependencias están declaradas y resueltas en el lock del servicio API. No se añadió Alembic ni otra herramienta de migraciones.
4. **Configuración y operación:** se eligió `DATABASE_URL` como nombre de configuración del backend. El aprovisionamiento PostgreSQL, los detalles de secretos en despliegue, migraciones y parámetros operativos continúan pendientes.
5. **Dominio:** acordar reglas de activos, entradas, salidas, cantidades, permisos, auditoría y consistencia antes de diseñar el esquema.

## ¿Qué significa mantener dos bases de datos?

Significa que cada dominio utiliza su propio mecanismo de persistencia y configuración: TinyDB sigue atendiendo los dominios existentes y PostgreSQL atendería el futuro inventario. No significa que una operación que escriba en ambas bases sea automáticamente atómica. Sin un coordinador distribuido, una transacción de PostgreSQL no puede revertir una escritura ya confirmada en TinyDB. Por ello, la primera integración debe evitar escrituras cruzadas o definir explícitamente compensación, idempotencia y recuperación antes de necesitarlas.

La configuración y ciclo de vida de la conexión PostgreSQL deben quedar encapsulados en un módulo de inventario o infraestructura claramente aislado. No se debe sustituir globalmente la persistencia de TinyDB ni hacer que importar la app principal abra conexiones. La construcción del engine puede ser perezosa y la sesión debe crearse por solicitud; el cierre de la sesión debe quedar garantizado incluso si la ruta falla.

## ORM, engine, sesión y transacción

- **Modelo ORM:** clase Python que describe una tabla y convierte objetos en operaciones SQL. Un modelo de SQLModel destinado a persistencia suele declarar `table=True`; todavía no se definen aquí tablas de inventario.
- **Engine:** configuración y punto de acceso al pool de conexiones. Crear el objeto engine no debería ejecutar consultas por sí solo; una conexión real se usa cuando se abre una conexión o sesión y se ejecuta SQL.
- **Session:** unidad de trabajo que agrupa lectura y escritura ORM. En FastAPI es habitual proporcionar una sesión por solicitud mediante una dependencia con `yield` y cerrarla en un bloque `finally`.
- **Transacción:** conjunto de operaciones confirmado o revertido conjuntamente **dentro de una misma base de datos**. Debe hacerse `commit` solo cuando la operación de dominio esté lista; ante un error se hace rollback y se propaga una respuesta de error apropiada. Cerrar una sesión no equivale a confirmar una transacción.
- **Solicitud HTTP:** la sesión por solicitud administra recursos, pero no significa que todas las solicitudes formen una transacción única ni que un proceso en TinyDB y otro en PostgreSQL compartan atomicidad.

## Configuración segura prevista

La URL de conexión viene de `DATABASE_URL` en el entorno del backend, nunca del cliente ni de variables públicas `NEXT_PUBLIC_*`. `get_database_url()` falla explícitamente si no está configurada, sin revelar su contenido. La dependencia HTTP transforma esa ausencia en un `503` genérico. El `.env` local no se inspecciona. La importación del módulo y el arranque de la app no crean el engine ni conectan a PostgreSQL; el engine se construye en la primera solicitud de sesión que lo necesita. No se añade aquí un hook de apagado porque el engine es perezoso y aún no se integra con el ciclo de vida de la app.

Antes de habilitar la base real, habrá que confirmar TLS/red, credenciales de mínimo privilegio, timeouts, pool, cierre en shutdown, manejo de indisponibilidad y observabilidad sin revelar la URL. Nada de ello se valida mediante una base local de prueba.

## Pruebas aisladas y límites de SQLite

`services/api/tests/test_inventory_database.py` verifica la ausencia de configuración, la creación perezosa y cacheada del engine con SQLite temporal, y el cierre de sesión en terminación normal y al propagarse una excepción. La ruta SQLite temporal y su engine se eliminan/disponen al finalizar cada prueba. Las pruebas no abren conexiones externas ni leen `.env`; no se añadió una prueba de router porque aún no hay endpoints.

SQLite puede comprobar parte del mapeo SQL y el ciclo básico de sesión, pero **no valida PostgreSQL**. En particular, no demuestra la semántica de bloqueo concurrente (`SELECT ... FOR UPDATE`), aislamiento, niveles de transacción, restricciones/tipos específicos, concurrencia entre workers ni comportamiento del pool PostgreSQL. Esas propiedades necesitarán pruebas de integración contra una instancia PostgreSQL desechable y aislada, en una fase autorizada posterior; no se usa ni se contacta una base real en esta fase.

## Identidad: UUID persistente compatible con usuarios existentes

El campo `user_uuid` se genera con UUID aleatorio en el servidor al crear un usuario nuevo y se almacena en el documento TinyDB. La API de creación no acepta el campo del cliente. La lectura de documentos antiguos acepta la ausencia del campo y devuelve internamente `user_uuid=None`; no modifica TinyDB ni crea un valor distinto en cada lectura. Esto preserva los JWT existentes: `sub` sigue conteniendo el ID entero en texto y la autenticación no requiere UUID ni añade un claim UUID. Los roles y la comprobación de `credentials_version` permanecen sin cambios.

No se ha ejecutado backfill. Los usuarios históricos **no tienen necesariamente UUID**. Para asignar uno a esos registros hace falta definir y aprobar una operación explícita, idempotente, con validación de unicidad y estrategia de recuperación. Hasta entonces, consumidores futuros deben tratar el UUID como opcional para usuarios preexistentes. No se implementaron modelos/endpoints de inventario ni se expuso `user_uuid` en las respuestas HTTP actuales.

Archivos de auth modificados y cobertura: `services/api/app/auth/models.py`, `services/api/tests/test_auth_unit2.py` y `services/api/tests/test_auth_unit3.py`. Las pruebas verifican generación, persistencia/estabilidad al releer, lectura de un registro legacy sin mutación, rechazo de UUID en el payload cliente, conservación de `sub` y autenticación con token existente sin claim UUID.

## Resultado de la fase de infraestructura

Archivos añadidos para la fase:

- `services/api/app/inventory/__init__.py`
- `services/api/app/inventory/database.py`
- `services/api/tests/test_inventory_database.py`

La función `clear_engine_cache()` permite disponer el engine cacheado y limpiar la caché en pruebas o en una integración futura controlada. No se conecta a una base durante import o startup. La validación de esta fase se limita a los tests focalizados ejecutados con `uv` desde `services/api`; no es una certificación de PostgreSQL ni habilita todavía escrituras de inventario.

## Secuencia sugerida para fases futuras

1. Aprobar contrato de identidad y prefijo de rutas, junto a la semántica de inventario.
2. Confirmar configuración de despliegue de PostgreSQL y política de secretos; las dependencias están declaradas.
3. Diseñar modelos y migraciones revisables; validar compatibilidad con PostgreSQL en infraestructura de prueba aislada.
4. Implementar endpoints y transacciones del dominio, control de acceso y auditoría según contratos aprobados.
5. Planificar despliegue, migración y cualquier asociación/backfill de usuarios con copia, validación, observabilidad y rollback documentados.

Cada fase debe comprobar explícitamente que no altera el comportamiento de TinyDB y que sus pruebas usan almacenamiento aislado. Este orden es orientativo; no autoriza por sí mismo ninguna operación futura.
