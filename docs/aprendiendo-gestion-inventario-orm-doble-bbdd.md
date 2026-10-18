# Aprendiendo: gestión de inventario con ORM y doble base de datos

## Estado final

Este documento registra la evolución de la gestión de inventario. La Fase 3
implementó modelos SQLModel y contratos HTTP; la Fase 4 añadió consultas y
lecturas; la Fase 5 añadió escrituras transaccionales; la Fase 6 integró y
probó el router; y la Fase 7 añadió un seed manual con barreras de seguridad.
El estado final de la rama `feature/inventory-orm-dual-database` se validó con
la suite backend completa: **374 aprobados, 0 fallidos y 1 omitido**. El usuario
confirmó que el seed se ejecutó en Supabase con seis activos, cuatro entradas y
tres salidas, y que `GET /api/inventory/products` devuelve los seis productos
con `current_stock`. Esa operación externa fue confirmada por el usuario; no se
repitió durante la actualización documental.

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

### Decisiones de diseño vigentes

- TinyDB conserva autenticación, perfiles y otros dominios existentes; PostgreSQL/Supabase es la persistencia independiente de inventario. No se intenta una transacción distribuida entre ambas.
- SQLModel proporciona modelos y sesiones síncronas sobre SQLAlchemy. `get_session` entrega una sesión por solicitud y la cierra; el engine es perezoso. SQLite temporal aísla pruebas ordinarias, pero no certifica semántica PostgreSQL.
- `DATABASE_URL` es una variable privada del backend, no del cliente. La configuración del destino Supabase permitida por el seed es específica y no convierte Supabase en base de pruebas.

### Decisiones abiertas

1. **Identidad y propiedad de datos:** `user_uuid` ya existe para nuevos usuarios como identificador persistente adicional, pero no sustituye al ID entero ni al `sub`. Los usuarios antiguos pueden continuar sin UUID. La asignación a los existentes requiere una operación explícita, idempotente y aprobada por separado; no hay backfill automático. Las lecturas de inventario exigen JWT, pero no filtran recursos por usuario.
2. **Contrato de lectura pendiente:** filtros, orden configurable y paginación no están definidos y por ello no se exponen todavía. El listado de productos no filtra por oficina: el stock se calcula globalmente agregando todos los movimientos del activo. Hay que confirmar si el dominio requiere stock por oficina antes de ofrecer esa vista; los campos `office` de movimientos no se aplican al cálculo global. `GET /inventory/orders` representa una unión discriminada de entradas y salidas (`type: entry | exit`), no una entidad de orden independiente.
3. **Dependencias:** las dependencias están declaradas y resueltas en el lock del servicio API. No se añadió Alembic ni otra herramienta de migraciones.
4. **Configuración y operación:** se eligió `DATABASE_URL` como nombre de configuración del backend. El aprovisionamiento PostgreSQL, los detalles de secretos en despliegue, migraciones y parámetros operativos continúan pendientes.
5. **Dominio:** las escrituras actuales implementan el contrato explícito de productos, entradas y salidas, sin autorización por rol. Sigue pendiente acordar idempotencia, auditoría, criterios de normalización y comportamiento de recuperación ante incidencias de almacenamiento.

## ¿Qué significa mantener dos bases de datos?

Cada dominio utiliza su propio mecanismo de persistencia: TinyDB sigue
atendiendo autenticación y otros dominios heredados, y PostgreSQL atiende el
inventario. En desarrollo, el destino PostgreSQL validado es Supabase; esto no
significa que Supabase gestione autenticación ni que las dos bases compartan
transacciones. Una transacción PostgreSQL no puede revertir una escritura ya
confirmada en TinyDB. El seed solo consulta TinyDB para resolver localmente la
identidad del usuario que atribuirá movimientos; después escribe inventario en
la base SQL. Esa lectura no crea un vínculo FK ni una transacción entre bases.

La configuración y ciclo de vida de la conexión PostgreSQL deben quedar encapsulados en un módulo de inventario o infraestructura claramente aislado. No se debe sustituir globalmente la persistencia de TinyDB ni hacer que importar la app principal abra conexiones. La construcción del engine puede ser perezosa y la sesión debe crearse por solicitud; el cierre de la sesión debe quedar garantizado incluso si la ruta falla.

## ORM, engine, sesión y transacción

- **Modelo ORM:** clase Python que describe una tabla y convierte objetos en operaciones SQL. `Asset`, `AssetEntry` y `AssetExit` declaran tablas; no se incorporó una herramienta de migraciones. El seed/API confirmados presuponen que el esquema ya está disponible en el destino; el aprovisionamiento/migraciones formales quedan pendientes.
- **Engine:** configuración y punto de acceso al pool de conexiones. Crear el objeto engine no debería ejecutar consultas por sí solo; una conexión real se usa cuando se abre una conexión o sesión y se ejecuta SQL.
- **Session:** unidad de trabajo que agrupa lectura y escritura ORM. En FastAPI es habitual proporcionar una sesión por solicitud mediante una dependencia con `yield` y cerrarla en un bloque `finally`.
- **Transacción:** conjunto de operaciones confirmado o revertido conjuntamente **dentro de una misma base de datos**. Debe hacerse `commit` solo cuando la operación de dominio esté lista; ante un error se hace rollback y se propaga una respuesta de error apropiada. Cerrar una sesión no equivale a confirmar una transacción.
- **Solicitud HTTP:** la sesión por solicitud administra recursos, pero no significa que todas las solicitudes formen una transacción única ni que un proceso en TinyDB y otro en PostgreSQL compartan atomicidad.

## Configuración y diferencias entre entornos

La URL de conexión viene de `DATABASE_URL` en el entorno del backend, nunca del cliente ni de variables públicas `NEXT_PUBLIC_*`. `get_database_url()` falla explícitamente si no está configurada, sin revelar su contenido. La dependencia HTTP transforma esa ausencia en un `503` genérico. `app/auth/config.py` carga `services/api/.env` al importarse para la configuración de auth; el módulo de base de datos de inventario no carga dotenv y solo lee `DATABASE_URL` al solicitar el engine. Al ejecutar la CLI manual puede usarse `uv run --env-file .env` para inyectar las variables locales sin mostrar su contenido. La importación de la app y su arranque no crean el engine ni conectan a PostgreSQL; el engine se construye ante la primera solicitud de sesión que lo necesita.

Las pruebas usan SQLite en memoria o archivo temporal, de forma aislada. La
prueba PostgreSQL concurrente es opcional y requiere
`NEXOVA_INVENTORY_TEST_POSTGRES_URL` dirigido a una base desechable que termine
en `_test`; no uses el destino de desarrollo/Supabase como base de pruebas. Para
un seed local, los nombres de DB/archivo deben identificar `_dev` o `_test`.
El único destino Supabase aceptado por el guard del seed es el proyecto de
desarrollo autorizado por código; su DB estándar `postgres` se admite solo con
`--environment development`. En el resto de servidores PostgreSQL, se exige el
sufijo de entorno en el nombre de base. SQLite en memoria solo se permite para
`test`.

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

## Fase 6 — integración y pruebas de regresión

Se revisó el registro del router en `app/main.py`, la sesión SQLModel perezosa, los schemas y modelos, las consultas, las rutas y su dependencia JWT. Los endpoints efectivos están bajo `/api/inventory`: `GET /products`, `GET /products/{asset_id}`, `GET /orders`, `POST /products`, `POST /orders/inbound` y `POST /orders/outbound`. Se conserva la unión discriminada de movimientos `entry | exit`, el stock derivado y la identidad JWT basada en el ID entero TinyDB. El usuario antiguo sin UUID sigue autenticándose y leyendo; las escrituras de movimientos responden 428 sin mutar ni generar UUID.

Verificación de regresión desde `services/api`, con `PYTHON_DOTENV_DISABLED=1`, `SECRET_KEY` de prueba y bases TinyDB temporales para auth, proveedores e incidencias:

```text
uv run pytest tests -q --tb=short
358 passed, 1 skipped, 49 subtests passed
```

El único skip corresponde a la prueba de concurrencia PostgreSQL opcional: necesita `NEXOVA_INVENTORY_TEST_POSTGRES_URL` que apunte a una base desechable cuyo nombre termine en `_test`; no se configuró ni se conectó a ninguna base PostgreSQL. La suite valida en SQLite flujos HTTP, validación, autenticación, recursos inexistentes, conflictos, stock derivado y rollback, pero no la semántica real de bloqueo/aislamiento de PostgreSQL. No se encontró ni corrigió una regresión en la suite ejecutada. `git diff --check` pasó. No se cargó `.env`, ni se accedió a Supabase, ejecutaron seeds/migraciones o alteraron datos persistentes.

## Fase 7 — seed de desarrollo seguro e idempotente

`services/api/app/inventory/seed.py` implementa un comando manual independiente
del startup. Desde `services/api`, la forma de invocación que se usó para la
carga de desarrollo fue:

```bash
NEXOVA_INVENTORY_SEED_USER_EMAIL="<email-de-la-cuenta-autorizada>" \\
uv run --env-file .env python -m app.inventory.seed --environment development
```

No copies el email real en documentación, historial compartido o logs. `--environment`
es obligatorio y sus opciones están limitadas a `development`/`test`; no existe
un marcador equivalente que sustituya ese argumento. La CLI lee
`NEXOVA_INVENTORY_SEED_USER_EMAIL` y `DATABASE_URL` del entorno ya cargado. El
comando no carga dotenv por sí mismo; `uv run --env-file .env` es el mecanismo
de la invocación anterior para cargar la configuración local. La API puede
cargar `services/api/.env` a través de `app/auth/config.py`, pero eso no debe
confundirse con el comportamiento de la CLI.

Antes de crear el engine o escribir, el seed valida el entorno y el destino.
Para PostgreSQL no Supabase se exige que el nombre de la base termine en
`_dev`/`_test`, según el entorno. SQLite requiere archivo con sufijo
`_dev.sqlite3`/`_dev.db` o `_test.sqlite3`/`_test.db`; SQLite en memoria solo
se acepta para `test`. Para Supabase se valida la forma del host directo
`db.<ref>.supabase.co` o el username del pooler `postgres.<ref>`; solo el
proyecto autorizado en código puede usarse para desarrollo, con la base
estándar `postgres` o una terminada en `_dev`. Supabase se rechaza en `test`.
Los errores no imprimen URL ni credenciales. Estas barreras reducen el riesgo
de una escritura accidental, pero no sustituyen revisar de forma independiente
las variables y el destino inmediatamente antes de ejecutar.

El usuario se resuelve por email normalizado, en la tabla `users` de TinyDB,
usando `get_database_path()` de `app.auth.database`. Esa función prioriza
`AUTH_DB_PATH`; si no está configurada, la ruta predeterminada es
`services/data/auth.json` (resuelta desde el código del servicio). El seed abre
TinyDB en modo lectura, exige un único registro activo y un `user_uuid` válido
ya persistido. No crea UUID, no usa el ID entero/documento TinyDB y no imprime
email ni UUID. Los usuarios nuevos obtienen UUID en servidor, persistido junto
al registro; los usuarios históricos pueden no tenerlo. La API no devuelve el
UUID en su respuesta pública de usuario. El seed no crea enlace FK entre las
bases ni prueba identidad mediante la API; por eso es esencial que auth y CLI
usen la misma ruta/localización efectiva. Si falta `AUTH_DB_PATH`, comprueba la
ruta por defecto del proceso, no asumas que es la base usada por un servidor
que se arrancó con otro entorno.

El dataset actual contiene seis activos (`NXV-IT-001`, `NXV-IT-002`,
`NXV-PER-001`, `NXV-PER-002`, `NXV-OFF-001`, `NXV-TRN-001`), cuatro entradas y
tres salidas. Las entradas son 10 y 5 unidades de `NXV-IT-001`, 8 de
`NXV-PER-001` y 12 de `NXV-PER-002`. Las salidas son 2 unidades de
`NXV-IT-001` por asignación, 1 unidad de consumo sin asignatario y 1 unidad de
`NXV-PER-001` por asignación. En ausencia de movimientos previos, los saldos
netos por orden de SKU son 12, 0, 7, 12, 0 y 0.

El seed solo inserta. Reutiliza un SKU existente únicamente si todos sus
atributos coinciden; ante una diferencia aborta y revierte la transacción de
esta ejecución sin modificar filas existentes. Omite movimientos que ya
coinciden por activo, cantidad, campos de dominio y UUID (no ID ni timestamp);
el mismo conjunto puede repetirse para el mismo UUID sin duplicar esos
movimientos. Rechaza saldos previos negativos o salidas que produzcan stock
negativo. PostgreSQL utiliza un advisory transaction lock para serializar
ejecuciones del seed. La sesión debe llegar sin transacción abierta. Esto no
implica atomicidad entre TinyDB y PostgreSQL.

La cobertura de `tests/test_inventory_seed.py` usa DB aisladas e incluye el
guard de destinos, selección de cuenta activa con UUID persistido y no mutación
de TinyDB, dataset, idempotencia y rollback. La suite backend completa terminó
con **374 aprobados, 0 fallidos y 1 omitido**; el omitido corresponde a la
prueba opcional de concurrencia PostgreSQL. Los tests SQLite no prueban advisory
locks ni comportamiento de producción PostgreSQL.

## Arranque, pruebas y comprobación manual

Desde `services/api`, el README del servicio documenta el arranque local:

```bash
uvicorn app.main:app --reload
```

La API requiere la configuración de auth, incluida `SECRET_KEY`; para inventario
también necesita `DATABASE_URL` en el entorno del backend. Tras iniciar, abre
`/docs` en el mismo host/puerto para Swagger UI, autentícate con el mecanismo
JWT de la API y prueba `GET /api/inventory/products`. La respuesta es una lista
de productos que incluye `current_stock`. Un `503` al acceder a inventario suele
indicar que `DATABASE_URL` no está configurada; no compartas la URL al
diagnosticarlo.

Para la suite backend completa, desde `services/api`:

```bash
uv run pytest
```

Resultado final verificado en esta rama: **374 passed, 0 failed, 1 skipped**.
Mantén `AUTH_DB_PATH` y otras rutas TinyDB de las pruebas aisladas según los
fixtures/configuración de test del proyecto. No se debe usar Supabase como DB
de test.

## Hechos, decisiones y pendientes para fases futuras

**Comprobado en código/tests:** `current_stock` se deriva de movimientos; las
rutas están protegidas por JWT; las salidas bloquean activo en PostgreSQL y
rechazan stock insuficiente; el seed tiene barreras, lectura TinyDB y rollback.
La suite completa está verde. La carga de Supabase y el GET con seis productos
son hechos reportados por el usuario en esta entrega, no una conexión realizada
durante la actualización documental.

**Decisiones que deben preservarse:** mantener separadas TinyDB y PostgreSQL;
no generar `user_uuid` a demanda ni aceptar el UUID desde payloads HTTP; usar
`get_database_path()` para localizar auth; mantener validaciones del seed y
usar DB de test aislada; calcular stock desde movimientos, nunca desde un
contador duplicado.

**Pendiente de comprobación/definición:** concurrencia en PostgreSQL real
mediante la prueba opcional y una DB de test desechable; migraciones/aprovisionamiento
formal; filtros, paginación y stock por oficina; política futura de backfill
para usuarios antiguos sin UUID. SQLite no valida el lock PostgreSQL.

Cada fase debe comprobar explícitamente que no altera el comportamiento de TinyDB y que sus pruebas usan almacenamiento aislado. Este orden es orientativo; no autoriza por sí mismo ninguna operación futura.
