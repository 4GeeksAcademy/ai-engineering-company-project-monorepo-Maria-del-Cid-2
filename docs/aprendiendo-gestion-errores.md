# Aprendiendo: Gestión de errores en Nexova

> Documento pedagógico sobre la auditoría de gestión de errores y exposición de
> información sensible en Nexova. Describe el estado comprobado de las Fases 1
> a 5, y separa los hechos observados de las hipótesis y pendientes.

## Introducción

Una API no solo debe funcionar cuando todo sale bien. También debe decidir qué
error se devuelve al cliente, qué información se conserva para diagnosticarlo y
qué información nunca debe aparecer en logs, respuestas o trazas públicas.

En Nexova este aprendizaje se aplica especialmente a:

- el envío de emails de recuperación mediante Resend;
- la creación coordinada de usuarios y perfiles;
- la persistencia local con TinyDB;
- las respuestas HTTP de FastAPI;
- los flujos de autenticación y recuperación de contraseña.

La regla general es separar tres niveles:

1. El cliente recibe un contrato estable y no recibe secretos ni detalles internos.
2. La aplicación conserva un contexto útil para diagnosticar el fallo.
3. La infraestructura registra el error técnico con el menor nivel de exposición posible.

---

## 1. Objetivo y alcance

### ¿Qué vamos a auditar?

El objetivo de `error-handling-audit` es revisar cómo Nexova detecta, transforma,
registra y comunica errores en el backend, con atención especial a la
información sensible.

La auditoría comprueba que:

- los errores previsibles se representen mediante excepciones específicas;
- los logs no incluyan contraseñas, tokens, cabeceras de autorización, API keys,
  emails completos ni cuerpos HTTP completos;
- las respuestas HTTP mantengan sus códigos y contratos salvo una necesidad
  explícita;
- las operaciones parciales dispongan de compensación cuando no existen
  transacciones;
- un fallo de la compensación no quede oculto;
- el handler global de FastAPI permanezca como última barrera para errores
  inesperados;
- las pruebas verifiquen tanto el tratamiento del error como la ausencia de
  datos sensibles.

### Alcance real de esta entrega

La Fase 1 se limita al backend de autenticación, usuarios, perfiles y email de
recuperación. No incluye los scripts Python de análisis ni el frontend. Tampoco
corrige los dos tests pendientes del rate limit de password reset: se documentan
como incidencia separada.

---

## 2. Plan de trabajo por fases

Este es el plan de trabajo de la auditoría y el estado comprobado en esta
entrega. Las fases pendientes no se han ejecutado.

| Fase | Área | Estado | Resultado |
|---|---|---|---|
| 1 | Backend de auth, email, usuarios y perfiles | **Completada** | Logging seguro, excepción de persistencia, compensación observada y pruebas de regresión. |
| 2 | Scripts Python, análisis CSV y errores de procesos auxiliares | **Completada** | Lector estricto, validación de estados, seed preparado antes de persistir y errores CLI controlados. |
| 3 | Clientes API del frontend | **Completada** | Contrato común, timeout, cancelación, parseo seguro y mensajes redactados. |
| 4 | Consumidores frontend y traducción de errores | **Completada** | Mensajes seguros centralizados en consumidores genéricos; cancelaciones esperadas invisibles. |
| 5 | Validación integrada y cierre de la auditoría | **Completada con pendientes** | Suites ejecutadas, hallazgos trazados y riesgos residuales documentados. |

La documentación de esta fase no implica que las fases pendientes estén
verificadas.

---

## 3. Fase 1 — Backend

### 3.1. Adaptador de email: `email.py`

El adaptador `ResendEmailSender` realiza una petición HTTP al proveedor. La
implementación anterior usaba `print` para informar de aceptaciones, rechazos y
fallos de conexión. Esos mensajes incluían el destinatario completo y, en el
caso de un `HTTPError`, leían e imprimían el cuerpo devuelto por el proveedor.

El cambio real introduce el logger estándar de Python y un contexto redactado:

- el email se representa únicamente mediante su dominio;
- un rechazo HTTP conserva el código de estado, por ejemplo `422`;
- los fallos de proveedor conservan el tipo de excepción, como `HTTPError` o
  `URLError`;
- no se registra el token incluido en la URL de recuperación;
- no se registra la cabecera `Authorization` ni la API key;
- no se lee ni se imprime el cuerpo HTTP completo del proveedor;
- el mensaje público sigue siendo `EmailDeliveryError` sin detalles internos.

Por ejemplo, el contexto de diagnóstico puede indicar:

```text
provider=resend recipient_domain=example.com status=422 failure_type=HTTPError
```

Esto permite distinguir un rechazo del proveedor de una indisponibilidad de red
sin convertir el log en una copia de la petición o de la respuesta.

### 3.2. Persistencia de perfiles: `repository.py`

`ProfileRepository.create()` encapsula los errores de construcción o inserción
en TinyDB mediante `ProfilePersistenceError`. La capa HTTP ya no necesita
capturar cualquier excepción como si fuese una decisión de negocio.

La excepción específica tiene dos objetivos:

1. Definir el evento que el caso de uso sabe tratar: no se pudo persistir el
   perfil.
2. Mantener separados los detalles de TinyDB del router y de la respuesta HTTP.

La excepción original queda encadenada internamente para conservar diagnóstico,
pero no se copia a la respuesta del cliente.

### 3.3. Creación de usuarios y perfiles: `users_router.py`

`POST /api/users` puede crear primero el usuario y después un perfil opcional.
TinyDB no ofrece aquí una transacción que cubra ambas tablas, por lo que el
flujo utiliza compensación manual:

1. Se hashea la contraseña.
2. Se crea el usuario.
3. Se intenta crear el perfil.
4. Si falla el perfil, se intenta eliminar el usuario recién creado.
5. La API conserva la respuesta HTTP 500 y el mensaje de contrato existente.

El router trata específicamente `ProfilePersistenceError`. Si el borrado
compensatorio devuelve `False` o lanza otra excepción, se registra un mensaje
seguro con el `user_id` y los tipos de fallo. No se registran el email, la
contraseña, el hash, tokens ni el contenido de la excepción.

El handler global de `FastAPI` continúa actuando como última barrera para errores
inesperados y devuelve un mensaje genérico. No se cambian los códigos existentes
de registro correcto, email duplicado ni validación.

### 3.4. Pruebas de la Fase 1

Se añadieron pruebas para el adaptador de email y se adaptaron las pruebas de
usuarios y perfiles:

- un `HTTPError` conserva el estado HTTP y no registra destinatario, token ni
  cuerpo del proveedor;
- un error de conexión registra solo el tipo de fallo y no su detalle sensible;
- una entrega correcta registra dominio y estado, no el email completo;
- un fallo de perfil devuelve HTTP 500 y elimina el usuario creado;
- un rollback fallido o incompleto queda registrado sin exponer secretos;
- las respuestas no contienen detalles internos.

Validaciones ejecutadas:

- `test_auth_email` y `test_auth_unit2`: **46 tests correctos**;
- `test_auth_unit4`: **66 tests correctos**;
- ejecución focalizada final de email, usuarios y perfiles: **69/69 correctos**;
- suite ampliada de autenticación: **191/193 correctos**;
- compilación de los módulos modificados: correcta;
- comprobación estática de errores en los archivos modificados: sin errores;
- `git diff --check`: correcto.

Para ejecutar `TestClient` fue necesario instalar `httpx2` únicamente en el
virtualenv local, porque la versión instalada de Starlette lo exigía. No se
modificó `pyproject.toml` ni se añadió una dependencia de runtime.

---

## 4. Fase 2 — Scripts Python y archivos CSV

### 4.1. Lector CSV y validación

La Fase 2 confirmó que el lector compartido debía distinguir entre errores de
estructura del archivo y errores de negocio de una fila.

En `services/api/app/incidents/csv_reader.py` se aplicaron estos cambios:

- el parser usa `strict=True`;
- `csv.Error` se convierte en `CsvReadError`;
- el mensaje conserva el número de registro lógico cuando está disponible;
- los errores de apertura ya no incluyen la ruta completa en el mensaje;
- los errores estructurales siguen diferenciando cabecera ausente, columnas
  obligatorias ausentes y anchura incorrecta de una fila.

En `services/api/app/incidents/constants.py` y
`services/api/app/incidents/validation.py` se añadió el código estable
`INVALID_STATUS`. Un estado desconocido ahora produce un `ValidationResult`
inválido, en lugar de lanzar el `ValueError` genérico
`validated row contains an unsupported domain value`.

La validación compartida de `packages/shared/python` no necesitó cambios: sus
consumidores siguen recibiendo la misma tupla de `ValidationIssue` y sus tests
continúan pasando.

### 4.2. Seed de incidencias

`scripts/seed_incidents.py` ahora:

1. Lee y transforma todas las filas antes de abrir la base de datos.
2. Acumula las filas inválidas y prepara las válidas en memoria.
3. Solo comienza a insertar después de que la lectura y preparación terminen.
4. Captura errores esperables en `main()`.
5. Escribe mensajes controlados por `stderr` y devuelve código `1` ante errores.
6. Usa `raise SystemExit(main())` para propagar el código al proceso CLI.

Esto evita inserciones parciales causadas por un CSV ilegible o sintácticamente
inválido. La persistencia de TinyDB sigue sin ser transaccional: si falla una
escritura después de comenzar el seed, pueden quedar inserciones parciales; no
existe rollback automático. El error se comunica de forma genérica y la base se
cierra mediante `finally`.

El seed distingue entre la calidad del conjunto importado y el total global de
la base. La comprobación de 96 registros se realiza sobre las filas válidas del
CSV y sus conteos por estado y categoría; `database_total` refleja también las
incidencias manuales que ya existían. Esto evita tratar una base correctamente
cargada como errónea por contener datos operativos previos.

En la base efectiva `services/data/incidents.json`, la carga verificada
preservó la incidencia manual ID 1, importó 96 registros y dejó 97 incidencias
totales junto con 96 claves en `incident_seed_keys`. La segunda ejecución
insertó 0 registros y mantuvo el total en 97. El endpoint `GET /api/incidents`
devolvió los 97 registros, incluidos la incidencia manual y los ejemplos del
CSV.

El comportamiento correcto se conserva:

- primera ejecución aislada: **96** incidencias insertadas;
- filas inválidas: `18`, `44`, `87`, `91`;
- segunda ejecución con la misma base: **0** nuevas inserciones.

### 4.3. Pruebas de la Fase 2

Se añadieron regresiones para:

- CSV sintácticamente inválido con número de fila y sin email en el error;
- estado desconocido sin excepción inesperada;
- archivo de entrada inexistente;
- seed inválido sin crear una base con inserciones parciales;
- fallo de persistencia con `stderr`, código distinto de cero y sin traceback;
- fallo en la segunda escritura real de TinyDB: la primera incidencia y su clave
  de seed permanecen persistidas después del error, sin rollback;
- idempotencia del seed.

El módulo nuevo es `services/api/tests/test_seed_incidents.py`. El slice de
lector, validación, análisis, exportación, CLI, API y seed ejecutó **42/42
tests correctos**, incluida la prueba de fallo concreto de persistencia. Los
tests de validación compartida ejecutaron **2/2 correctos**.

La prueba de persistencia deja que TinyDB escriba la primera incidencia y su
entrada en `incident_seed_keys`, y fuerza un `OSError` en la segunda escritura
de la tabla `incidents`. La CLI devuelve código `1`, escribe un mensaje seguro
en `stderr` y no muestra traceback. Tras cerrar la base queda una incidencia y
una clave de seed: el comportamiento observado confirma que TinyDB puede dejar
datos parciales y que esta fase no implementa rollback.

`scripts/analyze.py` y la exportación no se modificaron. Los riesgos de
`EOFError` y escritura parcial de resultados quedan pendientes, tal como se
definió para esta fase.

---

## 5. Incidencias pendientes

### 5.1. Tests de rate limit de password reset

La suite ampliada de autenticación produjo dos fallos reproducibles en
`services/api/tests/test_auth_password_reset.py`.

#### `PasswordResetApiTests.test_forgot_password_rate_limit_allows_three_requests_per_hour`

El test realiza tres solicitudes y después una cuarta. Espera que solo se
envíen tres emails, por lo que comprueba:

```text
expected: 3
actual:   4
```

El fallo se produce en la aserción `len(self.email_sender.messages) == 3`.

#### `PasswordResetApiTests.test_rate_limit_has_own_counter_per_email_and_expires_after_one_hour`

El test verifica un contador independiente por email y una nueva solicitud tras
la expiración. Espera cinco emails en total, pero obtiene seis:

```text
expected: 5
actual:   6
```

La cuarta solicitud inicial de `alice@example.com` también se permite, de modo
que se añade un email antes de la comprobación de expiración.

### 5.2. Discrepancia de configuración

La implementación actual define en `services/api/app/auth/password_reset.py`:

```python
PASSWORD_RESET_REQUEST_LIMIT = 5
PASSWORD_RESET_RATE_LIMIT_WINDOW = timedelta(minutes=30)
```

Los nombres y las aserciones de los tests describen un límite esperado de tres
solicitudes por hora. Por tanto, la discrepancia principal es:

- configuración actual: hasta **5** solicitudes en la ventana;
- expectativa de los tests: hasta **3** solicitudes en la ventana.

La ventana actual es de 30 minutos. Su cambio desde
`timedelta(hours=0)` a `timedelta(minutes=30)` no explica por sí solo estos dos
fallos: con cualquiera de esas ventanas, la cuarta solicitud sigue estando por
debajo del límite configurado de cinco. Además, el segundo test avanza una hora,
que supera tanto 30 minutos como cero.

No se corrigen estos tests ni la configuración dentro de esta auditoría.

### 5.3. Hechos y evidencia disponible

Hechos observados:

- los dos tests fallan al ejecutarse de forma aislada;
- los errores son `AssertionError: 4 != 3` y `AssertionError: 6 != 5`;
- el código actual usa `PASSWORD_RESET_REQUEST_LIMIT = 5`;
- la ventana actual es de 30 minutos;
- los tests relacionados no tenían cambios locales durante la auditoría;
- el commit `02728e0` cambió la ventana de cero a 30 minutos.

La evidencia permite afirmar que los fallos son incompatibilidades entre los
tests actuales y la configuración actual, y que no fueron introducidos por los
cambios de la Fase 1. No permite afirmar que se haya ejecutado una versión
anterior de la suite con éxito: no existe en esta auditoría un registro histórico
de esa ejecución anterior. Por eso se describen como **preexistentes respecto a
la Fase 1 por alcance y estado del código**, no como una ejecución histórica
comprobada.

---

### 5.4. Resolución posterior

La discrepancia quedó resuelta fuera de la ejecución original de esta auditoría.
El contrato previsto es **3 solicitudes por dirección de email durante una hora**
y la implementación y los dos tests fueron alineados con ese contrato,
conservando el contador independiente por email y la comprobación de expiración.

La suite backend completa posterior pasa **279/279 tests**. La validación visual
o E2E y la comprobación contra servicios desplegados reales siguen pendientes y
no se consideran realizadas.

## 6. Conceptos de aprendizaje

### 6.1. Excepciones específicas

Una excepción específica comunica qué evento conoce la capa superior. En este
caso, `ProfilePersistenceError` distingue un fallo de persistencia de perfil de
un email duplicado o de un error HTTP de entrada.

Capturar `Exception` directamente en un router mezcla errores esperables con
fallos desconocidos. Es preferible que el repositorio traduzca detalles de su
biblioteca de persistencia a una excepción del dominio técnico y que el router
trate únicamente esa excepción cuando necesita aplicar una compensación.

### 6.2. Logging seguro

Un log puede acabar en sistemas compartidos, proveedores externos o archivos
con retención prolongada. Por eso no es una copia de la petición.

En Nexova no deben registrarse:

- contraseñas ni hashes;
- tokens de recuperación o JWT;
- cabeceras `Authorization`;
- API keys y secretos de configuración;
- cuerpos HTTP completos;
- emails completos cuando basta con un contexto menos identificable.

El estado HTTP, el proveedor, el dominio del destinatario y el tipo de
excepción suelen ser suficientes para comenzar un diagnóstico.

### 6.3. Rollback y operaciones compensatorias

Cuando dos cambios no comparten una transacción, el segundo puede fallar después
de que el primero haya tenido éxito. El borrado del usuario tras fallar el perfil
es una operación compensatoria.

Una compensación no debe darse por hecha: puede devolver que no eliminó nada o
puede lanzar otra excepción. El sistema debe registrar ese hecho de manera
segura y mantener una respuesta pública que no revele la causa interna.

La compensación manual es útil en esta implementación, pero TinyDB no debe
presentarse como si ofreciera una transacción distribuida.

### 6.4. Errores HTTP

Los errores internos y los errores de contrato tienen públicos distintos:

- `409` comunica un email ya registrado;
- `422` comunica que la entrada no cumple el esquema;
- `500` comunica que el servidor no pudo completar una operación;
- el detalle técnico debe quedar en el diagnóstico interno, no en la respuesta.

FastAPI permite declarar excepciones HTTP específicas en las rutas y un handler
global para errores inesperados. El handler global es una última barrera, no un
sustituto de las excepciones específicas de cada caso de uso.

### 6.5. Manejo de errores en frontend

El frontend debe traducir los contratos HTTP a mensajes útiles sin mostrar
trazas, tokens ni detalles internos. Debe distinguir, por ejemplo, validación,
credenciales no válidas, sesión expirada y fallo temporal del servidor.

La validación del frontend mejora la experiencia, pero la validación real debe
seguir en FastAPI. Esta fase no modifica el frontend; el análisis de sus estados
visibles queda para la Fase 3.

### 6.6. Validación defensiva

La validación defensiva comprueba entradas y estados en cada frontera:

- Pydantic valida el cuerpo y rechaza campos no previstos;
- el repositorio valida la forma de los datos persistidos;
- el cliente no debe controlar el `user_id` del perfil de otra persona;
- los identificadores y resultados ausentes producen respuestas controladas;
- la aplicación no debe confiar en que una compensación siempre tendrá éxito.

Validar en una frontera no elimina la necesidad de validar en las siguientes:
el cliente puede ser manipulado y la persistencia puede contener datos antiguos
 o incompletos.

### 6.7. Errores de CSV

El análisis de incidentes usa archivos CSV como entrada. Un archivo ausente,
vacío, con una codificación inválida, con columnas incorrectas, con una sintaxis
CSV inválida o con filas no válidas debe producir un error controlado y no una
traza interna para el usuario.

El lector separa el error de parseo del error de negocio. Por ejemplo, una
comilla mal formada produce `CsvReadError`, mientras que un estado desconocido
produce `INVALID_STATUS` en el resultado de validación. Esta separación permite
que la CLI y el seed decidan si deben detener el archivo completo o contar una
fila como inválida.

Los resultados de análisis deben ser agregados y no deben devolver campos
sensibles como `customer_email`. La Fase 2 aplicó estas comprobaciones al
lector CSV y al seed; la auditoría específica de los resultados de análisis
queda fuera de esta fase.

### 6.8. Pruebas de regresión

Una prueba de regresión fija una propiedad que no debe volver a romperse. En
esta auditoría no basta con comprobar que Resend falla: también se comprueba que
el log no contiene los datos que no deben salir.

Las pruebas deben cubrir el camino feliz, el error previsto, el error del
proveedor, la compensación correcta y el fallo de la compensación. Cuando una
expectativa de test no coincide con la configuración real, como ocurre con el
rate limit, la discrepancia debe documentarse antes de cambiar código.

---

## 7. Estado actual y próximos pasos

### Terminado

- Auditoría de logging y errores en el adaptador Resend.
- Excepción específica para persistencia de perfiles.
- Tratamiento y diagnóstico seguro del rollback de creación de usuarios.
- Pruebas de regresión para logs y respuestas sin información sensible.
- Ejecución de las pruebas focalizadas y de la suite ampliada de autenticación.
- Documentación de los dos fallos de rate limit sin corregirlos.
- Lector CSV estricto, código `INVALID_STATUS` y seed con preparación previa.
- Tests de regresión de scripts y CSV, con idempotencia comprobada en base temporal
  y fallo de escritura parcial documentado.

### Pendiente

- Decidir si el contrato correcto del rate limit es tres solicitudes por hora o
  cinco solicitudes en 30 minutos.
- Adaptar conjuntamente configuración y tests cuando esa decisión esté tomada.
- Diseñar y validar la presentación de errores en el frontend.
- Decidir cómo tratar fallos de persistencia del seed si se requiere atomicidad
  real, ya que TinyDB no ofrece rollback transaccional.
- Ejecutar la validación integrada posterior a la Fase 3.

### Validaciones siguientes

1. Confirmar la regla de negocio esperada para el rate limit.
2. Actualizar tests y configuración de forma coordinada, fuera de esta fase.
3. Decidir si el seed necesita una estrategia de persistencia atómica o una
  recuperación explícita ante fallos de escritura.
4. Ejecutar la suite completa de autenticación y comprobar que no quedan fallos
   no explicados.
5. Auditar los scripts sin ejecutar operaciones destructivas sobre datos locales.
6. Validar en frontend que los mensajes son útiles y no exponen detalles del
   backend.

## 8. Fase 3 — Clientes API del frontend

La Fase 3 refuerza los clientes API de
`uis/backoffice/talent-pipeline-tracker` sin modificar componentes visuales.

### 8.1. Contrato compartido

`lib/api-errors.ts` centraliza la clasificación de errores HTTP, red, timeout,
parseo y cancelación. Interpreta formatos conocidos de FastAPI, conserva
`status` y `field` cuando son válidos y aplica mensajes seguros por defecto. Los
detalles se limitan y redactan para no exponer emails, tokens, URLs ni rutas
internas.

`NexovaApiError` conserva sus propiedades públicas y
`IncidentAnalysisApiError` mantiene `status`; los tipos de éxito y las firmas
existentes de los clientes se conservan.

### 8.2. Clientes actualizados

Se actualizaron `lib/api.ts`, `lib/nexova-api.ts` y
`lib/incident-analysis-api.ts` para aceptar respuestas JSON, texto plano y
cuerpos vacíos; clasificar JSON inválido en respuestas correctas; priorizar el
código HTTP antes del cuerpo de error; aplicar timeout configurable de 10
segundos por defecto; distinguir timeout de cancelación externa; limpiar
temporizadores y listeners; y conservar la exportación como `Blob`.

Los clientes de candidaturas, notas, proveedores, perfil, Incident Manager y
password reset no necesitaron cambios de producción porque ya delegan en sus
clientes existentes o traducen sus errores de negocio.

### 8.3. Verificación

Se añadieron pruebas para respuestas correctas, `204`, cuerpos vacíos, texto
plano, JSON inválido, errores HTTP con JSON/texto/sin cuerpo, errores de red,
timeout, cancelación externa, redacción de datos sensibles y compatibilidad de
las propiedades públicas de los errores.

Resultados comprobados:

- tests nuevos de Tracker e Incident Analysis: **9/9 correctos**;
- tests del cliente Nexova: **24/24 correctos**;
- suite frontend completa: **56/56 correctos**;
- TypeScript: correcto;
- build de Next.js: correcto.

El lint mantiene **3 errores y 5 warnings preexistentes** en el Tracker,
relacionados con `app/page.tsx`, `hooks/useRecord.ts`, `hooks/useRecords.ts`,
`components/filters/FilterBar.tsx` y `components/notes/NoteItem.tsx`. No se
modificaron esos archivos.

Los consumidores genéricos de perfil, proveedores y análisis usan ahora el
traductor común de la Fase 4. Las traducciones específicas de autenticación,
password reset e Incident Manager se mantienen separadas.

## 9. Fase 4 — Consumidores frontend y traducción de errores

La Fase 4 conecta el contrato de [api-errors.ts](../uis/backoffice/talent-pipeline-tracker/lib/api-errors.ts)
con los consumidores genéricos que muestran errores al usuario. La traducción
común vive en `lib/api-error-messages.ts` y no reemplaza las reglas específicas
de autenticación, restablecimiento de contraseña ni Incident Manager.

Los hooks de candidaturas y notas, el perfil, Supplier Directory e Incident
Analysis ya no propagan directamente `error.message`. Usan mensajes seguros por
categoría para red, timeout, `401`, `403`, `404`, `409`, `422` y errores `5xx`.
Los errores desconocidos usan el fallback contextual del consumidor.

Las cancelaciones esperadas se clasifican mediante `kind === "cancelled"` y
devuelven `null` al traductor. Los consumidores limpian su estado de error antes
de cada petición, por lo que cancelar una petición no muestra un aviso ni deja
un error visible. Las cancelaciones siguen siendo distinguibles internamente de
fallos de red y timeout.

### 9.1. Verificación de la fase

Se añadieron pruebas del traductor común para transporte, estados HTTP, ausencia
de exposición de detalles y cancelación invisible. Las pruebas de la fase pasan
como parte de la suite frontend (**58/58**), TypeScript y build; `git diff --check`
también pasa. El lint conserva únicamente los 3 errores y 5 warnings
preexistentes documentados en la Fase 3.

Los traductores especializados de `lib/auth-forms.ts`, `lib/password-reset.ts`
y `lib/incidents-api.ts` permanecen sin sustituir. No se modificaron backend,
rate limiting, CSV ni seeders.

## 10. Fase 5 — Validación integrada y cierre

La Fase 5 valida el estado actual sin introducir cambios funcionales. No se
encontró un catálogo numerado `ERR-001` a `ERR-013` en el árbol ni en el
historial Git consultado; la matriz se reconstruye a partir de los hallazgos
narrativos de `progress.md` y `techContext.md`.

### 10.1. Resultados de ejecución

Validación focalizada:

- auth, email, perfiles y password reset: **127 tests; 125 correctos y 2
  fallos**, ambos de rate limit conocidos;
- CSV, validación, análisis, exportación, CLI y seed: **36/36 correctos**;
- API HTTP, Incident Manager, Supplier Directory, modelos, seed de proveedores
  y CORS: **36/36 correctos**;
- frontend completo de clientes, sesión, password reset, perfil y mensajes:
  **58/58 correctos**.

Validación completa:

- backend: **267 tests; 265 correctos y 2 fallos**;
- frontend: **58/58 correctos**;
- TypeScript: correcto;
- build de Next.js: correcto;
- `git diff --check`: correcto.

El fixture `scripts/incidents-nexova.csv` estaba presente durante esta
ejecución y tenía 101 líneas. El primer intento del slice de datos omitió la
raíz del repositorio en `PYTHONPATH`, lo que impidió importar `scripts`; se
repitió correctamente y obtuvo **36/36**. Esto fue un problema del comando de
validación, no un fallo de producto.

### 10.2. Matriz de hallazgos y evidencia

| Hallazgo | Evidencia | Estado | Recomendación |
|---|---|---|---|
| Logging de Resend sensible | Tests de email y código con logger redactado | Verificado automáticamente | Mantener revisión de logs ante cambios del proveedor. |
| Persistencia de perfiles | `ProfilePersistenceError` y tests HTTP/repositorio | Parcialmente verificado | Añadir una prueba integrada si se necesita cubrir todas las rutas de fallo de TinyDB. |
| Compensación usuario-perfil | Tests de rollback correcto y fallido | Verificado automáticamente en los casos cubiertos | Mantener monitorización de compensaciones fallidas. |
| Handler global FastAPI | Contrato genérico documentado, sin prueba específica de excepción inesperada | Parcialmente verificado | Añadir prueba explícita del handler global. |
| CSV y estados inválidos | `CsvReadError`, `INVALID_STATUS`, **36/36** del slice de datos | Verificado automáticamente | Mantener fixture y casos sintácticos aislados. |
| Seed y persistencia parcial | Tests de idempotencia y fallo de escritura | Verificado con límite conocido | No asumir rollback transaccional de TinyDB; evaluar persistencia atómica aparte. |
| Errores CLI | Tests de stderr, código no cero y ausencia de traceback | Verificado automáticamente | Mantener ejecución con rutas temporales. |
| Timeout, red y cancelación frontend | Clientes API y tests de fase 3 | Verificado automáticamente en clientes | Añadir E2E cuando exista infraestructura. |
| HTTP `401`-`5xx` y mensajes seguros | Clientes, traductor común y **58/58** frontend | Verificado automáticamente en lógica | Comprobar mensajes visuales manualmente. |
| Formularios y persistencia | Tests de auth/perfil y errores de guardado | Parcialmente verificado | Validar visualmente éxito, error y reintento en cada formulario. |
| Password reset y email | Tests focalizados; 2 fallos de rate limit | Parcialmente verificado | Decidir conjuntamente el contrato de rate limit y corregirlo fuera de esta fase. |
| Incident Manager y análisis CSV | **36/36** HTTP/datos y **58/58** frontend | Verificado automáticamente | Realizar prueba manual de carga, análisis y descarga cuando haya navegador. |
| Recuperación global Next.js | `app/error.tsx` y `app/global-error.tsx` implementados con mensajes genéricos, `reset()` y navegación a `/` | Verificado automáticamente; validación visual pendiente | Comprobar visualmente mensajes, reintento y navegación cuando haya navegador. |

### 10.3. Lint, entorno y validación manual

El lint terminó con **3 errores y 5 warnings preexistentes**, en los hooks y
componentes del Tracker ya documentados. No aparecieron problemas nuevos en los
archivos de esta auditoría. FastAPI emitió un aviso de deprecación sobre el uso
de `httpx` en `TestClient`, sin afectar los resultados; no se instalaron
dependencias.

No se realizó validación interactiva en navegador porque no hay Chromium,
Chrome ni runner E2E disponible en el entorno. Por tanto, no se declara
verificado manualmente el comportamiento visual de mensajes, reintentos,
login/registro, sesión expirada, perfil, proveedores, Incident Manager ni
descarga CSV.

### 10.4. Riesgos residuales

- Los dos tests de rate limit siguen fallando porque la configuración permite
  cinco solicitudes en 30 minutos y las aserciones esperan tres en una hora.
- TinyDB no ofrece rollback transaccional ni coordinación multiworker.
- En el cierre de la Fase 5 no existía Error Boundary global en Next.js; la
  implementación posterior queda pendiente de comprobación visual.
- La comprobación manual de navegador y E2E queda pendiente.
- El estado final confirma que las pruebas automatizadas cubren los casos
  implementados, pero no demuestra comportamiento contra servicios desplegados
  reales.

### 10.5. Corrección posterior a la Fase 5: Error Boundaries de Next.js

Tras la validación de la Fase 5 se añadieron
`uis/backoffice/talent-pipeline-tracker/app/error.tsx` y
`uis/backoffice/talent-pipeline-tracker/app/global-error.tsx`. Ambos son Client
Components compatibles con Next.js 16.3.3 y App Router. Proporcionan mensajes
genéricos en español, recuperación mediante `reset()` y navegación a `/`, sin
mostrar `error.message`, trazas ni datos internos. El registro técnico se
limita a `error.digest` cuando existe.

La implementación no modifica autenticación, `AuthShell`, logout, clientes API,
backend ni dependencias. Se validó con **58/58 tests frontend correctos**,
TypeScript correcto, build de Next.js correcto y `git diff --check` correcto.
No se realizó validación visual en navegador, por lo que los flujos visuales de
mensaje, reintento y navegación permanecen pendientes de comprobación manual.

### 10.6. Actualización posterior del backend

El rate limit de password reset queda documentado y verificado con el contrato
de 3 solicitudes por dirección de email durante una hora. La suite backend
completa posterior pasa **279/279 tests**. La validación visual/E2E y contra
servicios desplegados reales siguen pendientes.

---

## Documentos utilizados como referencia

- `docs/Aprendiendo-asegurando-API.md`: estructura por unidades, explicación
  paso a paso de FastAPI, validación, autenticación, configuración y conceptos
  de seguridad.
- `docs/Aprendiendo-password-reset.md`: formato pedagógico de fases, aplicación
  concreta en Nexova, tokens, email, rate limiting, errores y pruebas.
- `docs/ARCHITECTURE_proposal.md`: separación entre API, aplicación, dominio e
  infraestructura, y criterio de mantener responsabilidades claras.
- `services/api/README.md`: endpoints, contratos HTTP, configuración y comandos
  de validación del backend.
- `memory-bank/progress.md`: estado registrado de la Fase 1 y resultados de las
  pruebas ejecutadas.

Este documento no representa como resueltos los dos fallos preexistentes del
rate limit de password reset, la falta de atomicidad multioperación de TinyDB ni
la validación manual contra servicios desplegados reales. El handler global de
FastAPI y la persistencia de perfiles conservan los estados y recomendaciones
documentados en sus respectivas filas de la matriz.
