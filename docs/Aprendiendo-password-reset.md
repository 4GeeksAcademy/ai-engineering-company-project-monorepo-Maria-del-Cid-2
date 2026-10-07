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

## Próximas actualizaciones

- **Fase 2:** formularios, navegación, estados de UI, query string y redirección.
- **Fase 3:** user enumeration, replay, logs, URLs, API keys y seguridad de sesiones.
- **Fase 4:** rate limiting, audit log, plantillas HTML, reintentos y conclusiones.
