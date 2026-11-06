# Aprendiendo: contenerización de Nexova con Docker

## Estado final

Este documento explica, de forma sencilla, la práctica de contenerización
realizada en la rama `Containerization`. Se preparó un entorno Docker para
trabajar localmente con la web pública, el backoffice y la API de Nexova.

El despliegue en un VPS no forma parte del alcance de esta práctica. No se
realizó y no debe asumirse que exista un entorno remoto disponible.

## 1. ¿Qué problema resuelve Docker?

Un proyecto suele necesitar varias herramientas para funcionar: Node.js para la
interfaz, Python para la API, dependencias concretas y determinadas variables de
configuración. Si cada persona instala todo directamente en su ordenador,
pueden aparecer diferencias: una versión distinta, una biblioteca ausente o
una configuración que funciona en un equipo pero no en otro.

Docker permite preparar pequeños entornos aislados llamados **contenedores**.
Cada contenedor incluye lo necesario para ejecutar una parte del proyecto. Así,
la interfaz y la API pueden arrancar de una manera más parecida en distintos
ordenadores.

Un contenedor no es una máquina virtual completa. Es un proceso aislado que
comparte parte del sistema operativo del ordenador, pero tiene sus propios
archivos, puertos y configuración.

## 2. ¿Qué se ha contenido en Nexova?

La configuración de `docker-compose.yml` crea dos servicios:

| Servicio | Qué contiene | Puerto visible en el ordenador |
|---|---|---:|
| `interfaces` | Web pública, backoffice, Next.js y proxy | `3000` y `3001` |
| `backend` | API FastAPI ejecutada con Uvicorn | `8000` |

Por tanto:

- `http://localhost:3000` muestra la web pública.
- `http://localhost:3001` muestra el backoffice.
- `http://localhost:8000` corresponde a la API.

La palabra `localhost` en estas direcciones significa “este ordenador” y sirve
para que una persona acceda desde su navegador. No es la dirección que deben
usar los contenedores para hablar entre sí.

## 3. ¿Qué hace Docker Compose?

Docker Compose es el archivo que describe cómo deben trabajar juntos varios
contenedores. En este proyecto, `docker-compose.yml` indica:

- qué imagen o Dockerfile usar para cada servicio;
- qué puertos publicar;
- qué carpetas compartir con cada contenedor;
- qué variables de entorno necesita cada proceso;
- qué red permite que los servicios se encuentren;
- qué volúmenes conservan dependencias y cachés.

La idea es que `interfaces` y `backend` se inicien como partes de una misma
aplicación, aunque técnicamente sean procesos separados.

## 4. Cómo se construye cada contenedor

### Contenedor de interfaces

`uis/Dockerfile` parte de una imagen de Node.js. Instala las dependencias del
backoffice y copia la web pública, el backoffice, el proxy y el script de
arranque.

Después, `uis/start.sh` inicia dos procesos dentro del mismo contenedor:

1. Next.js en modo desarrollo.
2. El proxy Node de `uis/proxy-server.js`.

Next.js escucha internamente en el puerto `3002` por defecto. Los usuarios no
acceden directamente a ese puerto: el proxy presenta la web pública en `3000`
y el backoffice en `3001`.

### Contenedor del backend

`services/Dockerfile` parte de una imagen de Python, instala las dependencias
de la API y arranca FastAPI mediante Uvicorn.

Uvicorn se inicia con `--reload`. Esto significa que, durante el desarrollo,
observa los archivos y vuelve a cargar la API cuando detecta cambios. No es una
configuración pensada como solución final de producción; es útil para trabajar
rápido en local.

## 5. ¿Qué son los bind mounts?

Un bind mount conecta una carpeta del ordenador con una carpeta dentro del
contenedor. De esta forma, el contenedor puede usar el código que se está
editando sin tener que reconstruir la imagen después de cada cambio.

La configuración monta, entre otras, estas carpetas:

- `uis/website` para la web pública;
- `uis/backoffice/talent-pipeline-tracker` para el backoffice;
- `services/api` para la API;
- `packages/shared/python` para el paquete Python compartido;
- `services/data` para los datos locales del backend;
- `uis/proxy-server.js` y `uis/start.sh` para el proxy y el arranque.

Algunas monturas son de solo lectura porque el contenedor solo necesita leerlas.
Los directorios `node_modules` y `.next` usan volúmenes Docker separados. Esto
evita mezclar dependencias instaladas dentro del contenedor con las del sistema
host y permite conservar la caché de Next.js.

## 6. Cómo se comunican los contenedores

Docker crea una red compartida llamada `nexova`. Dentro de esa red, un servicio
puede localizar a otro usando su nombre. Por eso la dirección interna correcta
del backend es:

```text
http://backend:8000
```

Aquí `backend` no es una palabra inventada: es el nombre del servicio definido
en `docker-compose.yml`.

No se debe cambiar esa dirección interna por:

```text
http://localhost:8000
```

Desde el contenedor de interfaces, `localhost` significa el propio contenedor
de interfaces, no el contenedor del backend. Tampoco se debe usar una IP fija,
porque Docker puede cambiar las IP internas al recrear los contenedores.

## 7. Por qué el navegador usa `/api`

Hay una diferencia importante entre el navegador y los contenedores:

- El proxy dentro de Docker sí puede resolver `backend`.
- El navegador de la persona usuaria no conoce la red interna de Docker.

Por eso las variables públicas del frontend tienen estos valores en Docker:

```text
NEXT_PUBLIC_NEXOVA_API_BASE=/api
NEXT_PUBLIC_INCIDENT_ANALYSIS_API_BASE=/api
```

Cuando el backoffice hace una petición a `/api/auth/me`, el navegador la envía
al mismo origen donde está abierta la interfaz. El proxy de
`uis/proxy-server.js` detecta `/api` y la reenvía internamente a
`http://backend:8000`.

El recorrido es:

```text
navegador → localhost:3001/api/... → proxy de interfaces → backend:8000/api/...
```

La web pública en `3000` utiliza el mismo principio.

## 8. Los valores `localhost:8000` que siguen en el código

Los clientes de `lib/nexova-api.ts` y `lib/incident-analysis-api.ts` conservan
`http://localhost:8000/api` como valor alternativo.

Ese valor sirve para ejecutar el frontend directamente en el ordenador, sin
Docker, cuando la API también se ha arrancado localmente en el puerto `8000`.

En Docker, Compose proporciona `/api`, por lo que el fallback no se utiliza.
Si alguien elimina accidentalmente esas variables del entorno del contenedor,
el navegador intentará llamar a su propio `localhost:8000`; esa dirección no
representa automáticamente al servicio `backend` y el flujo puede fallar.

La regla práctica es: para Docker, conservar siempre las variables públicas con
valor `/api` y `BACKEND_URL` con valor `http://backend:8000`.

## 9. Variables de entorno importantes

`.env.example` sirve como lista de configuración esperada. Entre sus valores
se encuentran:

| Variable | Para qué sirve |
|---|---|
| `WEBSITE_PORT` | Puerto visible de la web pública |
| `BACKOFFICE_PORT` | Puerto visible del backoffice |
| `BACKEND_PORT` | Puerto visible de la API |
| `NEXT_INTERNAL_PORT` | Puerto interno de Next.js |
| `BACKEND_URL` | Dirección interna del backend para el proxy |
| `NEXT_PUBLIC_NEXOVA_API_BASE` | Base pública del cliente Nexova |
| `NEXT_PUBLIC_INCIDENT_ANALYSIS_API_BASE` | Base pública de Incident Analysis |
| `DOCKER_NETWORK_NAME` | Nombre de la red Docker |
| `CORS_ORIGINS` | Orígenes permitidos para peticiones del navegador |

Las variables que empiezan por `NEXT_PUBLIC_` pueden llegar al navegador. No
deben contener contraseñas, API keys, secretos de firma ni credenciales.

## 10. Qué significa recarga en caliente

La recarga en caliente permite editar un archivo y ver el cambio sin detener y
arrancar manualmente todos los servicios.

En esta práctica:

- Next.js usa `npm run dev` y observa el código del backoffice.
- Uvicorn usa `--reload` y observa el código de la API.
- Los bind mounts hacen que los cambios del ordenador estén disponibles dentro
  de los contenedores.

La recarga está pensada para desarrollo. Un despliegue de producción debe
decidir otra estrategia, con imágenes versionadas, procesos controlados,
secretos seguros, logs y una política de reinicio adecuada.

## 11. Qué se verificó

La revisión de la práctica comprobó:

- puertos publicados;
- bind mounts;
- comandos de arranque;
- recarga de Next.js y Uvicorn;
- red Docker compartida;
- variables de entorno;
- proxy de interfaces;
- clientes de API y sus bases URL;
- ausencia de URLs hardcodeadas de `localhost` o IPs para la comunicación entre
  contenedores.

El funcionamiento de la web pública en `3000`, el backoffice en `3001` y la API
en `8000` fue confirmado durante la práctica. También se indicó que las pruebas
locales anteriores habían pasado.

## 12. Qué queda fuera y qué revisar en el futuro

El VPS queda fuera de esta práctica. Antes de plantear un despliegue remoto
habría que definir, entre otras cosas, dominio, HTTPS, gestión de secretos,
persistencia, copias de seguridad, logs, reinicios, firewall y estrategia de
actualización.

Para futuros desarrollos dentro del monorepo:

1. Revisar primero `docker-compose.yml`, `.env.example` y los Dockerfiles.
2. Usar nombres de servicio Docker para la comunicación interna.
3. Mantener las peticiones del navegador en `/api` cuando exista un proxy.
4. No introducir `localhost` ni IPs fijas como destinos entre contenedores.
5. Comprobar que una nueva variable pública no contenga secretos.
6. Verificar la ruta real de `services/data` antes de ejecutar seeds o scripts
   que escriban datos.
7. Recordar que pasar los tests o compilar no sustituye una comprobación manual
   de los tres puntos de entrada cuando el flujo lo requiera.

## 13. Archivos principales de la práctica

- `docker-compose.yml`: coordinación de servicios, puertos, red, variables y
  montajes.
- `uis/Dockerfile`: imagen y dependencias de las interfaces.
- `services/Dockerfile`: imagen y arranque de la API.
- `uis/start.sh`: arranque de Next.js y del proxy.
- `uis/proxy-server.js`: publicación de interfaces y reenvío de `/api`.
- `.env.example`: configuración de referencia para Docker.
- `uis/backoffice/talent-pipeline-tracker/lib/nexova-api.ts`: cliente API
  autenticado de Nexova.
- `uis/backoffice/talent-pipeline-tracker/lib/incident-analysis-api.ts`:
  cliente de Incident Analysis.
