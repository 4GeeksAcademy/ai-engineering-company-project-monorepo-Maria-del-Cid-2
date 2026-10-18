# Aprendiendo: gestión de inventario con ORM y doble base de datos

## Estado de esta fase

Este documento registra la evolución de la gestión de inventario. La Fase 3 implementó modelos SQLModel y contratos de validación HTTP; la Fase 4 añadió consultas y endpoints de lectura; la Fase 5 añade escrituras transaccionales de productos y movimientos. No se ejecutan seeds ni migraciones.

### Hechos observados e infraestructura implementada

- La API actual está en `services/api` y utiliza FastAPI.
- Autenticación, perfiles, Supplier Directory e Incident Manager persisten actualmente en TinyDB, con configuración propia por dominio.
- La identidad primaria de autenticación sigue siendo `User.id`, entero almacenado en TinyDB. El JWT conserva `sub=str(user.id)` y `get_current_user` resuelve ese ID en TinyDB.
- Los usuarios creados desde esta fase reciben un `user_uuid` generado en el servidor y persistido junto al usuario. El campo es opcional al parsear: documentos históricos sin él siguen siendo legibles y autenticables; su lectura no asigna ni persiste un UUID.
- `services/api/pyproject.toml` declara SQLModel (`sqlmodel>=0.0.24,<0.1`) y psycopg (`psycopg[binary]>=3.2,<4`); `uv.lock` fija las versiones resueltas. El entorno `uv` del servicio se usa para ejecutar el backend.
- `services/api/app/inventory/database.py` contiene la configuración aislada. Lee `DATABASE_URL` al solicitar el engine, crea el engine de forma perezosa y proporciona `get_session` con cierre garantizado. La importación del módulo no lee configuración ni crea engine; crear el engine tampoco abre por sí solo una conexión.
- `services/api/app/inventory/models.py` define `Asset`, `AssetEntry` y `AssetExit` con relaciones ORM, FK a assets y restricciones de SKU único, cantidades positivas y coherencia `exit_type`/`assigned_to`. `Asset` no persiste `current_stock`.
- `services/api/app/inventory/schemas.py` separa requests y responses. `current_stock` aparece solo en `AssetWithStockResponse`, calculado por consulta y no persistido. `user_uuid` se omite de los schemas de creación y se tipa como UUID en respuestas. Orders usa una unión discriminada por `type`: `entry` o `exit`.
- `services/api/app/inventory/queries.py` calcula sumas de entradas y salidas de forma independiente por `asset_id` antes de unirlas a activos, y expone una lista unificada de movimientos sin combinar modelos de movimiento entre sí.
- `services/api/app/inventory/router.py` registra `GET /api/inventory/products`, `GET /api/inventory/products/{asset_id}` y `GET /api/inventory/orders`. Todas las rutas requieren `get_current_user`; no se añadieron roles específicos. El detalle inexistente responde 404.
- `services/api/app/inventory/operations.py` implementa creación de productos, entradas y salidas transaccionales; la salida bloquea la fila del producto en PostgreSQL antes de leer el stock derivado.
- El router expone también `POST /api/inventory/products`, `POST /api/inventory/orders/inbound` y `POST /api/inventory/orders/outbound`. Los movimientos usan UUID de `get_current_user`; un usuario autenticado histórico sin UUID obtiene 428 y no causa mutaciones.
- `main.py` registra el router. Se conserva el prefijo `/api` y el contrato JWT existente; la app no se conecta a PostgreSQL durante import o startup.

### Supuestos de trabajo, no decisiones aprobadas

- La propuesta considerada es mantener las persistencias actuales y añadir PostgreSQL como almacén independiente para inventario.
- SQLModel proporciona los modelos y las sesiones síncronas sobre SQLAlchemy. Los endpoints de lectura ya usan la sesión de inventario mediante una dependencia; el engine sigue siendo perezoso y no se conecta al iniciar la app.
- PostgreSQL será el destino de producción; SQLite podría servir para pruebas rápidas de la capa ORM, no para certificar propiedades específicas de PostgreSQL.

### Decisiones abiertas

1. **Identidad y propiedad de datos:** `user_uuid` ya existe para nuevos usuarios como identificador persistente adicional, pero no sustituye al ID entero ni al `sub`. Los usuarios antiguos pueden continuar sin UUID. La asignación a los existentes requiere una operación explícita, idempotente y aprobada por separado; no hay backfill automático. Las lecturas de inventario exigen JWT, pero no filtran recursos por usuario.
2. **Contrato de lectura pendiente:** filtros, orden configurable y paginación no están definidos y por ello no se exponen todavía. El listado de productos no filtra por oficina: el stock se calcula globalmente agregando todos los movimientos del activo. Hay que confirmar si el dominio requiere stock por oficina antes de ofrecer esa vista; los campos `office` de movimientos no se aplican al cálculo global. `GET /inventory/orders` representa una unión discriminada de entradas y salidas (`type: entry | exit`), no una entidad de orden independiente.
3. **Dependencias:** las dependencias están declaradas y resueltas en el lock del servicio API. No se añadió Alembic ni otra herramienta de migraciones.
4. **Configuración y operación:** se eligió `DATABASE_URL` como nombre de configuración del backend. El aprovisionamiento PostgreSQL, los detalles de secretos en despliegue, migraciones y parámetros operativos continúan pendientes.
5. **Dominio:** las escrituras actuales implementan el contrato explícito de productos, entradas y salidas, sin autorización por rol. Sigue pendiente acordar idempotencia, auditoría, criterios de normalización y comportamiento de recuperación ante incidencias de almacenamiento.

## ¿Qué significa mantener dos bases de datos?

Significa que cada dominio utiliza su propio mecanismo de persistencia y configuración: TinyDB sigue atendiendo los dominios existentes y PostgreSQL atendería el futuro inventario. No significa que una operación que escriba en ambas bases sea automáticamente atómica. Sin un coordinador distribuido, una transacción de PostgreSQL no puede revertir una escritura ya confirmada en TinyDB. Por ello, la primera integración debe evitar escrituras cruzadas o definir explícitamente compensación, idempotencia y recuperación antes de necesitarlas.

La configuración y ciclo de vida de la conexión PostgreSQL deben quedar encapsulados en un módulo de inventario o infraestructura claramente aislado. No se debe sustituir globalmente la persistencia de TinyDB ni hacer que importar la app principal abra conexiones. La construcción del engine puede ser perezosa y la sesión debe crearse por solicitud; el cierre de la sesión debe quedar garantizado incluso si la ruta falla.

## ORM, engine, sesión y transacción

- **Modelo ORM:** clase Python que describe una tabla y convierte objetos en operaciones SQL. Los modelos de inventario declaran `table=True`; todavía no se han creado tablas mediante migración ni en una base de datos.
- **Engine:** configuración y punto de acceso al pool de conexiones. Crear el objeto engine no debería ejecutar consultas por sí solo; una conexión real se usa cuando se abre una conexión o sesión y se ejecuta SQL.
- **Session:** unidad de trabajo que agrupa lectura y escritura ORM. En FastAPI es habitual proporcionar una sesión por solicitud mediante una dependencia con `yield` y cerrarla en un bloque `finally`.
- **Transacción:** conjunto de operaciones confirmado o revertido conjuntamente **dentro de una misma base de datos**. Debe hacerse `commit` solo cuando la operación de dominio esté lista; ante un error se hace rollback y se propaga una respuesta de error apropiada. Cerrar una sesión no equivale a confirmar una transacción.
- **Solicitud HTTP:** la sesión por solicitud administra recursos, pero no significa que todas las solicitudes formen una transacción única ni que un proceso en TinyDB y otro en PostgreSQL compartan atomicidad.

## Configuración segura prevista

La URL de conexión viene de `DATABASE_URL` en el entorno del backend, nunca del cliente ni de variables públicas `NEXT_PUBLIC_*`. `get_database_url()` falla explícitamente si no está configurada, sin revelar su contenido. La dependencia HTTP transforma esa ausencia en un `503` genérico. El `.env` local no se inspecciona. La importación del módulo y el arranque de la app no crean el engine ni conectan a PostgreSQL; el engine se construye en la primera solicitud de sesión que lo necesita. No se añade aquí un hook de apagado porque el engine es perezoso y aún no se integra con el ciclo de vida de la app.

Antes de habilitar la base real, habrá que confirmar TLS/red, credenciales de mínimo privilegio, timeouts, pool, cierre en shutdown, manejo de indisponibilidad y observabilidad sin revelar la URL. Nada de ello se valida mediante una base local de prueba.

## Pruebas aisladas y límites de SQLite

`services/api/tests/test_inventory_database.py` verifica la ausencia de configuración, la creación perezosa y cacheada del engine con SQLite temporal, y el cierre de sesión en terminación normal y al propagarse una excepción. `services/api/tests/test_inventory_models.py` valida schemas, UUID, relaciones ORM y restricciones SQL. `services/api/tests/test_inventory_api.py` sustituye `get_session` por SQLite temporal y la identidad autenticada por una identidad de prueba; cubre listados, detalle, 404, cálculo con múltiples entradas y salidas, activo sin movimientos, unión discriminada de orders y que las tres rutas requieren autenticación. Las pruebas no abren conexiones externas ni leen `.env`.

El cálculo agregado de stock no aplica partición por oficina: entradas menos salidas de todas las oficinas asociadas al activo. Filtros, paginación y orden configurable permanecen fuera del contrato hasta recibir definición funcional. No se fija un rol específico para consultar o escribir: basta con un JWT válido, según el patrón de las rutas protegidas existentes. SQLite comprueba la lógica SQL básica, pero no certifica comportamiento PostgreSQL ni concurrencia.

SQLite puede comprobar parte del mapeo SQL y el ciclo básico de sesión, pero **no valida PostgreSQL**. En particular, no demuestra la semántica de bloqueo concurrente (`SELECT ... FOR UPDATE`), aislamiento, niveles de transacción, restricciones/tipos específicos, concurrencia entre workers ni comportamiento del pool PostgreSQL. Las salidas toman lock de la fila `assets` con `SELECT ... FOR UPDATE` en el dialecto PostgreSQL y conservan el lock hasta commit/rollback. Esto serializa las operaciones de salida que siguen este mismo protocolo; la transacción fuerza `READ COMMITTED`, de modo que tras esperar por el lock las consultas agregadas obtienen un snapshot nuevo y observan la salida recién confirmada por la transacción anterior. No se añade un contador de stock duplicado. Esto depende de PostgreSQL y de ejecutar las escrituras dentro de la transacción; SQLite ignora `FOR UPDATE`. La prueba de concurrencia PostgreSQL está preparada para una URL explícita `NEXOVA_INVENTORY_TEST_POSTGRES_URL` cuya base termine en `_test`; crea un schema aleatorio y lo elimina. No se configuró ni ejecutó aquí, por lo que la garantía real de concurrencia aún requiere correrla en PostgreSQL desechable antes de producción.

## Identidad: UUID persistente compatible con usuarios existentes

El campo `user_uuid` se genera con UUID aleatorio en el servidor al crear un usuario nuevo y se almacena en el documento TinyDB. La API de creación no acepta el campo del cliente. La lectura de documentos antiguos acepta la ausencia del campo y devuelve internamente `user_uuid=None`; no modifica TinyDB ni crea un valor distinto en cada lectura. Esto preserva los JWT existentes: `sub` sigue conteniendo el ID entero en texto y la autenticación no requiere UUID ni añade un claim UUID. Los roles y la comprobación de `credentials_version` permanecen sin cambios.

No se ha ejecutado backfill. Los usuarios históricos **no tienen necesariamente UUID**. Para asignar uno a esos registros hace falta definir y aprobar una operación explícita, idempotente, con validación de unicidad y estrategia de recuperación. Las lecturas continúan disponibles para esos usuarios porque solo necesitan JWT. Para las nuevas escrituras de movimientos, el router devuelve HTTP 428 `Precondition Required` si el usuario autenticado carece de UUID persistente; no genera ni acepta UUID del cliente, y la comprobación precede a cualquier mutación. Por tanto, ese usuario no puede registrar entradas o salidas hasta un backfill aprobado. La creación de producto no necesita UUID y sigue disponible a todo usuario autenticado.

Archivos de auth modificados y cobertura: `services/api/app/auth/models.py`, `services/api/tests/test_auth_unit2.py` y `services/api/tests/test_auth_unit3.py`. Las pruebas verifican generación, persistencia/estabilidad al releer, lectura de un registro legacy sin mutación, rechazo de UUID en el payload cliente, conservación de `sub` y autenticación con token existente sin claim UUID.

## Resultado de la fase de infraestructura y modelos

Archivos añadidos durante la preparación y la Fase 3:

- `services/api/app/inventory/__init__.py`
- `services/api/app/inventory/database.py`
- `services/api/tests/test_inventory_database.py`
- `services/api/app/inventory/models.py`
- `services/api/app/inventory/schemas.py`
- `services/api/tests/test_inventory_models.py`

La función `clear_engine_cache()` permite disponer el engine cacheado y limpiar la caché en pruebas o en una integración futura controlada. No se conecta a una base durante import o startup. `uv run pytest tests/test_inventory_models.py tests/test_inventory_database.py -q --tb=short` dio **11 passed, 5 subtests passed**. Los tests usan una base SQLite temporal; no son una certificación de PostgreSQL ni habilitan escrituras de inventario. No se ejecutaron migraciones, no se crearon tablas en Supabase ni se leyó `.env`.

### Decisiones y dudas que quedan explícitas

- `quantity` se representa como `float`, ya que el enunciado recibido exige que sea positiva pero no aclara si los activos se cuentan en unidades enteras o admiten fracciones. El schema y la base exigen `> 0`; confirmar el tipo de negocio antes de diseñar movimientos/endpoints.
- `category`, `office`, `name`, `sku` y `supplier` son textos requeridos sin vocabularios cerrados ni reglas adicionales de normalización; no se inventaron catálogos o límites de longitud.
- `exit_type` está restringido en HTTP y base de datos a `allocation`/`consumption`. La base también exige `assigned_to` no nulo para `allocation` y nulo para `consumption`.
- Los UUID de los movimientos son campos requeridos y tipados, sin default/generación en PostgreSQL. En operaciones futuras deben obtenerse del usuario autenticado. El backfill de cuentas antiguas sin UUID sigue pendiente de aprobación independiente.
- El timestamp predeterminado es UTC. No se definió un contrato para aceptar o modificarlo desde solicitudes; los schemas de creación lo omiten.

## Fase 4 — consultas y endpoints de lectura

`services/api/app/inventory/queries.py` implementa consultas de lectura. Para los listados de activos, agrega entradas y salidas por separado y después las une a `assets`; así evita el producto cartesiano entre múltiples entradas y salidas. El detalle utiliza subconsultas escalares para calcular el mismo total de un único activo. En ambos casos `current_stock = SUM(entries.quantity) - SUM(exits.quantity)` y los activos sin movimientos reciben stock cero. El valor nunca se persiste ni se actualiza en la tabla.

La consulta de órdenes combina los registros existentes de `AssetEntry` y `AssetExit` mediante `UNION ALL`, con proyección común y campos propios de cada variante. El schema es una unión discriminada por `type`: `entry` conserva `supplier`; `exit` conserva `exit_type` y `assigned_to`; ambos contienen `id`, `asset_id`, `quantity`, `office`, `created_at` y `user_uuid`. No existe ni se añade una tabla/modelo de órdenes independiente. Las respuestas de productos y movimientos se validan contra schemas HTTP, no se devuelven entidades ORM directamente. Las consultas seleccionan solo los datos necesarios, sin cargar relaciones por fila ni generar consultas N+1.

El router protegido se registra en `app/main.py`. La ruta efectiva sigue la convención actual `/api`: `GET /api/inventory/products`, `GET /api/inventory/products/{asset_id}` y `GET /api/inventory/orders`. La dependencia común valida JWT con `get_current_user`; no se inventaron permisos por rol. La falta de configuración de la persistencia conserva el manejo 503 de la dependencia de sesión y el detalle inexistente devuelve 404.

Verificación: `uv run pytest tests/test_inventory_api.py tests/test_inventory_models.py tests/test_inventory_database.py -q --tb=short`, ejecutado desde `services/api`: **15 passed, 8 subtests passed**. Las pruebas usan SQLite en directorio temporal mediante `get_session` sobreescrito; la autenticación se reemplaza por usuario de prueba, salvo el caso sin token, que comprueba 401. Estos tests verifican la lógica del endpoint, no la concurrencia ni las propiedades específicas de PostgreSQL.

### Decisiones pendientes de contrato

- **Filtros/paginación:** no se implementaron porque el requisito no especifica campos de filtro, límites, cursores ni forma de respuesta paginada.
- **Oficinas y stock:** el stock mostrado es global por activo, sumando movimientos de todas las oficinas. No representa saldo por oficina. Confirmar el alcance del inventario antes de ofrecer filtro o agregado por `office`.
- **Orden de orders:** se presenta del movimiento más reciente al más antiguo, con desempate estable por `type` e `id`. No hay orden configurable hasta definir el contrato.
- **Autorización:** se requiere JWT válido; no se aplican roles ni aislamiento por propietario. Definirlos si el dominio necesita restricciones más específicas.

## Fase 5 — escrituras y operaciones de inventario

`services/api/app/inventory/operations.py` y el router implementan:

- `POST /api/inventory/products`: valida `AssetCreate`, prohíbe campos extra como `id` o `current_stock`, crea el activo y responde 201 con `current_stock: 0`. SKU duplicado produce 409 usando la restricción única ya existente.
- `POST /api/inventory/orders/inbound`: valida `AssetEntryCreate`, verifica el activo, usa `user_uuid` de la identidad autenticada y responde 201 con el movimiento validado por schema.
- `POST /api/inventory/orders/outbound`: valida `AssetExitCreate` (cantidad positiva, `exit_type` permitido y compatibilidad `assigned_to`), verifica el activo, calcula stock desde los movimientos y rechaza stock insuficiente con 400 antes de insertar. Las FK y checks del modelo siguen protegiendo la persistencia; conflictos de integridad se responden 409.

Los clientes no pueden proporcionar `id`, timestamp, `current_stock` ni `user_uuid`; el esquema `extra="forbid"` rechaza esos campos y el servidor establece UUID desde el usuario de `get_current_user`. Las operaciones hacen flush y commit al finalizar el bloque transaccional; `IntegrityError` causa rollback y respuesta genérica de conflicto, sin dejar un movimiento parcial. El stock nunca se almacena ni modifica aparte de los movimientos.

Para evitar la carrera en dos salidas concurrentes, en PostgreSQL se bloquea la fila padre del activo con `SELECT ... FOR UPDATE` dentro de la transacción antes de consultar sumas. La operación establece explícitamente aislamiento `READ COMMITTED`; el `SELECT` de sumas tras obtener el lock usa un snapshot nuevo, por lo que una segunda solicitud que esperó ve el commit anterior y recibe 400 si ya no alcanza. Todos los escritores de salidas deben utilizar este mismo protocolo. El mecanismo no previene que una ruta externa que inserte directamente en `asset_exits` lo omita, ni prueba SQLite este comportamiento. No se reduplica stock como columna/contador.

Una cuenta antigua válida para JWT puede carecer de `user_uuid`. Se decidió bloquear solo las escrituras de movimientos con 428, sin backfill ni generación automática en petición. La creación de productos no requiere atribución de movimiento y permanece permitida. La integración de auth actual conserva el ID entero/JWT y no se modifica.

Cobertura añadida a `services/api/tests/test_inventory_api.py`: creación válida/inválida y SKU duplicado; entradas/salidas y stock derivado; salida insuficiente y FK inexistente sin persistencia; tipos de salida/asignado y cantidad inválidos; cliente intentando fijar UUID; usuario legacy sin UUID; integridad y rollback de inserción inducido con trigger SQLite; compilación SQL de la cláusula PostgreSQL `FOR UPDATE`. Prueba opcional de concurrencia real: se habilita solo con `NEXOVA_INVENTORY_TEST_POSTGRES_URL` a una base de test cuyo nombre termine `_test`; genera un schema temporal privado, compite dos salidas de 7 sobre stock 10 y verifica que solo una confirma, luego elimina ese schema. No se ejecutó porque no se configuró ni se accedió a una base PostgreSQL.

## Secuencia sugerida para fases futuras

1. Confirmar filtros, paginación, alcance por oficina, orden e idempotencia/auditoría; confirmar si 428 es el status preferido para cuentas legacy sin UUID.
2. Ejecutar la prueba opcional de concurrencia sobre una instancia PostgreSQL desechable aislada, y comprobar el aislamiento/schema de test en la versión de psycopg/PostgreSQL del despliegue.
3. Confirmar configuración de despliegue de PostgreSQL y política de secretos; las dependencias están declaradas.
4. Diseñar migraciones revisables y validar constraints/tipos PostgreSQL en infraestructura de prueba aislada.
5. Planificar cualquier backfill aprobado de UUID con copia, validación, observabilidad y rollback documentados.

Cada fase debe comprobar explícitamente que no altera el comportamiento de TinyDB y que sus pruebas usan almacenamiento aislado. Este orden es orientativo; no autoriza por sí mismo ninguna operación futura.
