# Aprendiendo: Password Reset

> Documento educativo independiente de la implementación de Nexova. Se actualiza
> progresivamente cuando cada fase del ejercicio se completa.

## Introducción

Una contraseña puede cambiarse de dos formas distintas:

- **Cambio de contraseña:** la persona ya tiene una sesión válida y conoce su contraseña actual.
- **Recuperación de contraseña:** la persona no puede autenticarse y demuestra control de su email mediante un enlace temporal.

Aunque ambos flujos terminan almacenando un nuevo hash de contraseña, sus requisitos de seguridad son diferentes.

## Fase 1 — Backend

### 1. Flujo conceptual

El flujo de recuperación tiene tres pasos:

1. La persona solicita instrucciones indicando su email.
2. El servidor genera un secreto temporal y envía un enlace.
3. La persona presenta el secreto y define una nueva contraseña.

La respuesta de la solicitud inicial debe ser genérica. El sistema no debe confirmar si el email pertenece a una cuenta, porque esa diferencia permitiría enumerar usuarios.

El cambio de contraseña es distinto: requiere una sesión autenticada, comprueba la contraseña actual y no necesita enviar un email.

### 2. Token aleatorio frente a JWT

Un token aleatorio opaco es una cadena sin significado que se genera con un generador criptográficamente seguro. El servidor puede guardar un hash del token y comparar el hash del valor recibido posteriormente.

Un JWT de recuperación contiene claims firmados y puede incluir una fecha de expiración. Sin embargo, la firma y la expiración no resuelven por sí solas el uso único ni la invalidación. Para esas propiedades habría que añadir estado servidor, por ejemplo una lista de tokens usados.

Para un flujo de recuperación temporal, un token opaco suele ser más sencillo: el estado necesario para expirar e invalidar el token forma parte explícita del modelo.

### 3. Almacenamiento seguro del token

El token original funciona como un secreto temporal. Por eso no debe guardarse en texto claro en la base de datos. El servidor puede almacenar un hash SHA-256 y volver a calcularlo cuando recibe el token desde el enlace.

Esto limita el impacto de una lectura de la base de datos: quien obtenga los registros no obtiene automáticamente los enlaces utilizables.

El token tampoco debe aparecer en logs, respuestas JSON, mensajes de error ni almacenamiento permanente del navegador.

### 4. Expiración y uso único

Un token de recuperación debe tener al menos:

- fecha de creación;
- fecha de expiración;
- referencia al usuario;
- indicador de consumo, como `used_at`.

La validación debe rechazar un token inexistente, expirado o ya utilizado. Después de cambiar la contraseña, el token debe marcarse como consumido. También es razonable invalidar tokens anteriores cuando se emite uno nuevo.

Una persistencia como TinyDB es suficiente para aprender el patrón, pero sus locks no coordinan varios procesos. Esa limitación debe quedar documentada antes de usar una arquitectura multi-worker.

### 5. Hashing de contraseñas

Las contraseñas no se cifran para poder recuperarlas: se almacenan mediante un hash lento con una sal, como bcrypt. Para comprobar una contraseña, el servidor verifica el texto recibido contra el hash persistido.

El token de recuperación y la contraseña tienen propósitos distintos:

- el token es un secreto temporal que se invalida;
- la contraseña se transforma en un hash persistente;
- el JWT identifica una sesión y tiene su propio ciclo de vida.

No se debe reutilizar un mecanismo como sustituto de otro.

### 6. Email transaccional y secretos de configuración

El servicio de recuperación no debería depender directamente de un proveedor concreto. Una interfaz de envío permite probar el flujo con un fake y cambiar de proveedor sin modificar la lógica de tokens.

La API key del proveedor debe vivir en la configuración privada del backend, nunca en el frontend ni en el repositorio. Los archivos de ejemplo pueden mostrar el nombre de la variable, pero no una clave utilizable.

## Aplicación en Nexova — Fase 1

Nexova mantiene el flujo dentro de `services/api/app/auth` y usa una tabla `password_reset_tokens` en la TinyDB de autenticación. Se implementaron tres endpoints:

- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`
- `POST /api/auth/change-password`

`forgot-password` responde siempre HTTP 200 con un mensaje genérico. Los tokens se generan aleatoriamente y solo se guarda su hash. El correo está aislado mediante `EmailSender`, con un adaptador para Resend y un fake para tests.

Para invalidar sesiones existentes se eligió `credentials_version` frente a `password_changed_at`. El valor entero se incluye en el JWT y se incrementa al actualizar la contraseña. `get_current_user` rechaza tokens cuya versión ya no coincide con el usuario persistido. Esta opción encaja con el modelo actual y no requiere comparar fechas ni depender de precisión temporal.

La configuración local prevista está en `services/api/.env`:

```text
RESEND_API_KEY=tu_api_key_de_resend
RESEND_FROM_EMAIL=Nexova <remitente-verificado@example.com>
PASSWORD_RESET_FRONTEND_URL=http://localhost:3000/reset-password
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=30
```

La API key todavía no se configura ni se usa durante los tests. Los tests inyectan un servicio de email falso y no realizan llamadas externas.

## Fase 2 — Frontend

### 1. Separar los tres casos de uso

El frontend presenta tres formularios diferentes sobre el mismo contrato de auth:

- `forgot-password` pide solo el email y muestra siempre un resultado genérico.
- `reset-password` recibe el token desde el query string y pide la nueva contraseña dos veces.
- `change-password` es una pantalla protegida, pide la contraseña actual y usa la sesión existente.

La validación local mejora la experiencia, pero no sustituye la validación del backend. Las reglas de longitud y confirmación se repiten en la interfaz para evitar peticiones innecesarias y se vuelven a aplicar en la API.

### 2. Query string y límites de estado

El enlace del email termina en `/reset-password?token=...`. La página servidor lee `searchParams` y pasa el token al componente cliente. El token no se guarda en `localStorage`, `AuthProvider` ni en un estado global; solo se utiliza para construir la petición de reset.

Después de un reset correcto, la interfaz vuelve a `/login?reset=1`. Después de un cambio autenticado, cierra la sesión local y vuelve a `/login?changed=1`, porque el backend ha invalidado el JWT al incrementar `credentials_version`.

### 3. Errores, privacidad y navegación

El formulario de forgot no revela si el email existe. Los errores de token inválido o caducado se muestran como un mensaje único, y el error de contraseña actual se presenta solo en el flujo autenticado. Las peticiones públicas desactivan explícitamente el Bearer; solo `change-password` usa la opción autenticada del cliente.

La protección de `/account/change-password` se añade al `AuthShell` existente. No se crea middleware ni un proveedor de sesión paralelo: la autorización real continúa siendo responsabilidad de la API.

## Aplicación en Nexova — Fase 2

La aplicación `uis/backoffice/talent-pipeline-tracker` incorpora un helper compartido para validaciones, llamadas a los tres endpoints y traducción de errores. `PasswordResetForm` reutiliza los componentes `Input`, `Button` y `AuthSubmissionGate` para mantener estados accesibles, evitar envíos concurrentes y permitir reintentos.

Las rutas añadidas son `/forgot-password`, `/reset-password` y `/account/change-password`. La suite frontend verifica validaciones, payloads, flags de autenticación, token ausente, errores principales y el guard de rutas.

## Fase 3 — Seguridad

### 1. Evitar user enumeration

El endpoint `forgot-password` devuelve el mismo HTTP 200 y el mismo mensaje tanto si el email existe como si no. Tampoco devuelve el email ni genera errores distintos para una cuenta inexistente o inactiva. Así, quien llama a la API no puede construir una lista de usuarios registrados a partir de las respuestas.

La validación de formato sigue pudiendo devolver 422 para una entrada que no es un email válido: eso valida el contrato del request, no revela la existencia de una cuenta.

### 2. Tokens opacos, expiración y replay attacks

El reset usa un token opaco generado con `secrets.token_urlsafe(32)`. El valor tiene suficiente aleatoriedad para que adivinarlo no sea una estrategia viable. TinyDB guarda únicamente su hash SHA-256, nunca el token utilizable.

El token tiene fecha de expiración y `used_at`. El consumo comprueba ambos campos dentro del lock del repositorio, por lo que dos solicitudes simultáneas solo pueden aceptar una. Una solicitud nueva invalida el token anterior antes de crear el reemplazo. Un token usado, expirado o reemplazado produce el mismo error genérico.

Un replay attack consiste en reutilizar un secreto capturado. La expiración limita su ventana temporal y `used_at` limita su número de usos. El hash reduce el impacto de una lectura de la base de datos, aunque el token debe seguir tratándose como un secreto mientras esté activo.

### 3. Sesiones, contraseñas y secretos

Reset y change pasan las nuevas contraseñas por bcrypt; nunca se guardan en texto plano ni se incluyen en respuestas. Al actualizar la contraseña se incrementa `credentials_version`, de modo que los JWT anteriores dejan de ser válidos. Un login posterior crea un JWT con la versión nueva.

`RESEND_API_KEY` solo se lee en el backend desde `services/api/.env`. No se usa en variables `NEXT_PUBLIC_*`, frontend, respuestas ni logs. Los archivos `.env` y las bases locales están ignorados por Git; la documentación solo contiene placeholders.

### 4. Query strings y logs

El frontend acepta únicamente `token` en `/reset-password` y no usa parámetros de redirección proporcionados por el usuario. Tras un reset correcto hace `router.replace("/login?reset=1")`, una URL fija que elimina el token del historial visible. Si el token es inválido o falla el reset, permanece disponible para permitir el reintento.

El backend no registra passwords, tokens, JWT, API keys ni emails de recuperación. Los errores públicos son genéricos: el usuario recibe una explicación útil sin recibir secretos o detalles internos.

### 5. CORS y TinyDB

CORS mantiene una lista explícita de origins y rechaza `*`. Los endpoints de password reset pasan por el mismo middleware que el resto de la API.

TinyDB no ofrece las garantías de transacción, unicidad y coordinación entre procesos de una base de datos relacional. En esta implementación los locks protegen la rotación, el consumo de tokens y la versión de credenciales dentro de un único proceso. Para varios workers o despliegues distribuidos se necesitaría una persistencia con operaciones atómicas; esta fase no convierte TinyDB en una base de datos multi-worker.

### Aplicación en Nexova

La auditoría añadió pruebas de paridad de `forgot-password`, tokens válidos, expirados, usados, reemplazados y consumidos concurrentemente, ausencia del token claro en TinyDB, hashes bcrypt, invalidación de JWT, login posterior, respuestas sin datos sensibles, CORS explícito y redirección fija. No fue necesario cambiar el algoritmo bcrypt, la configuración CORS ni la integración de Resend porque ya cumplían estos límites.

## FASE 4 — EXTENSIONES OPCIONALES

Estas tres funcionalidades son extensiones opcionales del ejercicio. No forman
parte de los requisitos obligatorios evaluables de las fases anteriores.

### Email HTML

Además del texto plano, el adaptador de email genera una plantilla HTML sencilla
con estilos inline. Incluye el enlace de reset, la expiración del token y una
indicación para ignorar el mensaje si la persona no realizó la solicitud. La
abstracción `EmailSender` sigue aislando al proveedor y los tests usan
`FakeEmailSender`.

### Rate limiting

Se limita `forgot-password` a **3 solicitudes por dirección de email durante una
ventana de una hora**. El contador se guarda en una tabla TinyDB separada y
también cuenta emails desconocidos, por lo que la respuesta pública continúa
siendo idéntica y no revela si una cuenta existe. Una dirección diferente tiene
su propio contador.

### Registro de auditoría

Los eventos se guardan en otra tabla TinyDB con timestamp, dirección IP, email
cuando puede conocerse y tipo de evento (`forgot_password_requested`,
`reset_password_succeeded` o `reset_password_failed`). No se guardan
contraseñas, tokens, JWT ni API keys.

La implementación es intencionadamente sencilla y está coordinada por los
locks de proceso ya existentes. TinyDB no ofrece coordinación entre varios
workers, por lo que este registro y el rate limiting no son una solución
distribuida o empresarial.
