# Nexova — Backend Architecture Proposal

**Estado:** Proposal técnico  
**Fecha:** 16 de septiembre de 2026  
**Alcance:** arquitectura y organización del backend; no incluye implementación funcional

---

## 1. Objetivo

Este documento propone cómo debería estructurarse el backend de **Nexova**, teniendo en cuenta:

- La naturaleza real de Nexova como consultora de recursos humanos.
- Los casos de uso previstos: gestión de candidatos, vacantes, empresas y procesos de selección, además de formularios públicos y funcionalidades internas.
- El trabajo desarrollado hasta ahora en el proyecto, donde ya existe un frontend React/TypeScript separado de un backend FastAPI.
- La necesidad de que la aplicación pueda crecer sin convertir el backend en un único archivo o en una colección de módulos fuertemente acoplados.
- El uso de FastAPI como API HTTP consumida por el frontend.

El objetivo no es aplicar una arquitectura compleja por defecto, sino elegir una estructura que proporcione **separación de responsabilidades, facilidad de mantenimiento y capacidad de evolución proporcional al tamaño y necesidades de Nexova**.

---

## 2. Contexto técnico y de negocio

Nexova es una empresa de consultoría de recursos humanos. El sistema que se está construyendo debe dar soporte tanto a usuarios externos como al trabajo interno de la empresa.

Los principales ámbitos funcionales identificados son:

- **Candidatos:** datos personales y profesionales, CV, habilidades, seniority, experiencia, disponibilidad y estado dentro del proceso.
- **Vacantes:** ofertas gestionadas por Nexova, requisitos, estado y relación con candidatos.
- **Empresas/clientes:** empresas que solicitan servicios de selección y con las que Nexova mantiene una relación comercial.
- **Procesos de selección:** relación entre vacantes y candidatos y evolución de cada candidatura.
- **Formularios públicos:** entrada de información desde empresas que solicitan servicios y desde trabajadores que quieren incorporarse a la bolsa de candidatos.
- **Gestión interna:** funcionalidades para que el equipo de Nexova consulte y gestione la información.
- **Analítica y métricas:** el proyecto ya ha trabajado con endpoints y modelos orientados a métricas, por lo que esta capacidad debe poder evolucionar sin mezclarse con la lógica principal de candidatos y vacantes.

Actualmente el proyecto utiliza un **monorepo con frontend y backend separados**. El frontend está construido con React, TypeScript, Vite y Tailwind, mientras que el backend utiliza FastAPI. En el estado actual del proyecto, el frontend se comunica con el backend mediante una API HTTP y durante el desarrollo se utiliza Docker Compose para levantar ambos servicios.

Esta separación es importante: aunque frontend y backend puedan vivir en el mismo repositorio, deben seguir siendo aplicaciones con responsabilidades y dependencias independientes.

---

# 3. Patrón arquitectónico propuesto

## 3.1. Decisión

Se propone utilizar una **arquitectura modular en capas, organizada principalmente por dominio**, implementada inicialmente como un **monolito modular con FastAPI**.

La arquitectura combinaría:

1. **API / presentación**
2. **Aplicación / servicios de caso de uso**
3. **Dominio**
4. **Infraestructura**

La organización principal del código se realizaría por **dominios de negocio**, y dentro de cada dominio se separarían las responsabilidades por capas.

De forma conceptual:

```text
Cliente HTTP
     │
     ▼
API / Routers
     │
     ▼
Application / Services
     │
     ▼
Domain
     │
     ▼
Infrastructure
     │
     ├── Base de datos
     ├── almacenamiento de CV
     ├── email
     └── servicios externos
```

No se propone utilizar MVC como patrón principal ni adoptar microservicios/serverless en esta fase.

---

## 3.2. Por qué no MVC como arquitectura principal

MVC es especialmente útil cuando el backend genera directamente vistas o HTML y existe una separación clara entre modelos, vistas y controladores.

En Nexova, el frontend React es una aplicación independiente y el backend actúa principalmente como **API**. Por tanto, no existe una capa de "View" tradicional dentro del backend.

Los routers de FastAPI cumplen parte de la función de entrada/controlador, pero reducir toda la arquitectura a:

```text
models/
views/
controllers/
```

no representa adecuadamente los diferentes tipos de responsabilidad que tendrá Nexova.

El backend necesita distinguir, por ejemplo:

- validación y contratos HTTP;
- reglas de negocio;
- casos de uso;
- acceso a datos;
- almacenamiento de CV;
- integración con servicios externos;
- configuración.

Por ello, una arquitectura en capas resulta más adecuada.

---

## 3.3. Por qué no serverless

Una arquitectura serverless podría ser útil para determinadas funciones aisladas, pero no es la opción inicial recomendada para Nexova.

El sistema tiene un conjunto de dominios relacionados entre sí: candidatos, vacantes, empresas y procesos de selección. Estas áreas comparten información y reglas de negocio.

Separarlas prematuramente en funciones independientes introduciría complejidad adicional:

- más componentes que desplegar;
- mayor complejidad de observabilidad;
- comunicación entre funciones;
- gestión de contratos entre servicios;
- duplicación de lógica;
- mayor complejidad para desarrollar y probar localmente.

No existe actualmente una necesidad demostrada de escalar cada funcionalidad de manera independiente.

Serverless podría incorporarse posteriormente para tareas concretas, por ejemplo procesamiento asíncrono de documentos, envío de notificaciones o trabajos programados, sin convertir todo el backend en una arquitectura serverless.

---

## 3.4. Por qué un monolito modular es adecuado para Nexova

El concepto de **monolito modular** permite mantener una única aplicación desplegable, pero con límites claros entre los dominios.

Esto encaja con Nexova porque:

- el equipo y el proyecto están todavía en una fase de construcción;
- los dominios están estrechamente relacionados;
- se necesita avanzar rápidamente sin mantener múltiples servicios;
- existe una única API principal para el frontend;
- la complejidad operativa de microservicios no aporta todavía un beneficio proporcional;
- la separación por dominios permite evolucionar posteriormente determinadas partes si las necesidades de negocio lo justifican.

La arquitectura, por tanto, debe permitir que el monolito sea sencillo hoy sin impedir una evolución futura.

---

# 4. Principios arquitectónicos

La estructura propuesta se basa en los siguientes principios:

### 4.1. Separación de responsabilidades

Cada módulo debe tener una responsabilidad clara.

Un router no debería contener consultas complejas a base de datos ni reglas de negocio.

### 4.2. Organización por dominio

El código relacionado con candidatos debe permanecer próximo al resto del código de candidatos. Lo mismo debe ocurrir con vacantes, empresas y procesos de selección.

Esto reduce la dispersión de una misma funcionalidad por todo el proyecto.

### 4.3. Dependencias en una sola dirección

La dirección conceptual debería ser:

```text
API
 ↓
Application
 ↓
Domain
 ↑
Infrastructure
```

La capa de dominio no debería depender de FastAPI, HTTP o detalles concretos de la base de datos.

### 4.4. Contratos explícitos

Los modelos utilizados para recibir y devolver información mediante la API deben estar claramente definidos y no deben confundirse automáticamente con las entidades internas del dominio o con los modelos de persistencia.

### 4.5. Configuración externa

URLs, credenciales, secretos y configuración dependiente del entorno no deben quedar codificados en el código.

FastAPI recomienda precisamente utilizar variables de entorno para valores de configuración que pueden cambiar entre entornos o que contienen información sensible. citeturn0search3turn0search4

---

# 5. Estructura de carpetas propuesta

Se propone una estructura similar a la siguiente:

```text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── dependencies.py
│   │
│   ├── api/
│   │   ├── router.py
│   │   └── health.py
│   │
│   ├── domains/
│   │   ├── candidates/
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   ├── models.py
│   │   │   ├── service.py
│   │   │   └── repository.py
│   │   │
│   │   ├── vacancies/
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   ├── models.py
│   │   │   ├── service.py
│   │   │   └── repository.py
│   │   │
│   │   ├── companies/
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   ├── models.py
│   │   │   ├── service.py
│   │   │   └── repository.py
│   │   │
│   │   ├── applications/
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   ├── models.py
│   │   │   ├── service.py
│   │   │   └── repository.py
│   │   │
│   │   └── analytics/
│   │       ├── router.py
│   │       ├── schemas.py
│   │       └── service.py
│   │
│   ├── infrastructure/
│   │   ├── database/
│   │   ├── storage/
│   │   ├── email/
│   │   └── external/
│   │
│   └── shared/
│       ├── exceptions.py
│       ├── pagination.py
│       └── types.py
│
├── tests/
│   ├── candidates/
│   ├── vacancies/
│   ├── companies/
│   ├── applications/
│   └── analytics/
│
├── .env.example
├── Dockerfile
├── pyproject.toml
└── README.md
```

La estructura es una **propuesta conceptual**. No implica que todos estos archivos deban crearse inmediatamente. La estructura debe crecer a medida que aparezcan necesidades reales.

---

# 6. Criterio de separación

La separación propuesta combina dos criterios.

## 6.1. Primer nivel: dominio

El primer criterio es el negocio:

```text
domains/
├── candidates/
├── vacancies/
├── companies/
├── applications/
└── analytics/
```

Esto permite responder fácilmente a preguntas como:

> "¿Dónde está la lógica relacionada con candidatos?"

La respuesta debería ser principalmente:

```text
domains/candidates/
```

y no cinco carpetas distintas repartidas por toda la aplicación.

---

## 6.2. Segundo nivel: responsabilidad

Dentro de cada dominio se separan las responsabilidades.

### `router.py`

Contiene únicamente la exposición HTTP:

- rutas;
- parámetros;
- dependencias;
- códigos de respuesta;
- conexión entre HTTP y los casos de uso.

No debería contener lógica empresarial compleja.

### `schemas.py`

Define los contratos de entrada y salida de la API.

Por ejemplo:

- datos necesarios para crear un candidato;
- datos devueltos al consultar un candidato;
- filtros;
- respuestas paginadas.

### `models.py`

Representa las entidades o modelos propios del dominio/persistencia, según la tecnología elegida para la base de datos.

Debe evitarse asumir que un modelo de persistencia tiene que ser exactamente igual que el contrato público de la API.

### `service.py`

Contiene los casos de uso y reglas de aplicación.

Ejemplos:

- crear candidato;
- actualizar disponibilidad;
- asociar candidato a una vacante;
- cambiar el estado de una candidatura;
- calcular determinadas métricas.

### `repository.py`

Aísla el acceso a los datos.

El servicio debería expresar qué necesita obtener o guardar, mientras que el repositorio se encarga de cómo hacerlo.

---

# 7. Dominios principales de Nexova

## 7.1. Candidates

Responsabilidad: gestionar el perfil profesional de los candidatos.

Información potencial:

- identificación;
- contacto;
- CV;
- experiencia;
- habilidades;
- seniority;
- nivel de idiomas;
- disponibilidad;
- estado del candidato.

Este dominio no debería contener la lógica específica de una candidatura a una vacante.

---

## 7.2. Vacancies

Responsabilidad: gestionar las posiciones que Nexova debe cubrir.

Puede incluir:

- título;
- descripción;
- requisitos;
- habilidades;
- seniority;
- rango salarial;
- empresa asociada;
- estado de la vacante;
- fechas relevantes.

---

## 7.3. Companies

Responsabilidad: gestionar las empresas clientes.

Puede incluir:

- información de la empresa;
- datos de contacto;
- servicios contratados;
- relación con vacantes;
- información necesaria para la gestión comercial.

---

## 7.4. Applications / Selection Processes

Responsabilidad: representar la relación entre un candidato y una vacante.

Este dominio es importante porque una candidatura no es simplemente una propiedad del candidato.

Una misma persona puede:

- estar asociada a varias vacantes;
- encontrarse en diferentes fases de procesos distintos;
- ser descartada para una posición y continuar activa para otra.

Por ello, el estado de una candidatura debe pertenecer al proceso de selección y no exclusivamente al candidato.

---

## 7.5. Analytics

Responsabilidad: métricas y agregaciones.

El proyecto ya ha trabajado con métricas y endpoints como:

- métricas generales;
- categorías;
- comparaciones;
- alertas;
- indicadores B2B/B2C.

Estas funcionalidades deberían mantenerse separadas de la lógica transaccional de candidatos y vacantes.

Analytics puede consultar información de otros dominios, pero no debería convertirse en el lugar donde se almacenen reglas de negocio pertenecientes a esos dominios.

---

# 8. Organización de endpoints y routers de FastAPI

FastAPI proporciona `APIRouter` precisamente para agrupar operaciones relacionadas y distribuir una aplicación grande en múltiples módulos. Los routers pueden tener prefijos, tags y dependencias comunes, y posteriormente incluirse en la aplicación principal. citeturn0search0turn0search2

Por ello, Nexova debería utilizar routers separados por dominio.

Una organización conceptual sería:

```text
/api
├── /candidates
├── /vacancies
├── /companies
├── /applications
└── /analytics
```

## 8.1. Candidates

Ejemplos conceptuales:

```text
GET    /api/candidates
GET    /api/candidates/{id}
POST   /api/candidates
PUT    /api/candidates/{id}
DELETE /api/candidates/{id}
```

También podrían existir endpoints específicos para:

- búsqueda y filtrado;
- habilidades;
- disponibilidad;
- CV.

El criterio es que todas las operaciones relacionadas directamente con candidatos estén agrupadas en el router de candidatos.

---

## 8.2. Vacancies

```text
GET    /api/vacancies
GET    /api/vacancies/{id}
POST   /api/vacancies
PUT    /api/vacancies/{id}
DELETE /api/vacancies/{id}
```

Podrían existir filtros por:

- estado;
- seniority;
- habilidades;
- empresa;
- rango salarial.

---

## 8.3. Companies

```text
GET    /api/companies
GET    /api/companies/{id}
POST   /api/companies
PUT    /api/companies/{id}
```

También se podrían exponer consultas relacionadas con:

- vacantes de una empresa;
- procesos activos;
- información de contacto.

---

## 8.4. Applications

```text
GET    /api/applications
GET    /api/applications/{id}
POST   /api/applications
PUT    /api/applications/{id}
```

El dominio podría incluir operaciones como:

- asociar un candidato a una vacante;
- cambiar el estado de una candidatura;
- consultar candidatos de una vacante;
- consultar las vacantes de un candidato.

---

## 8.5. Analytics

```text
GET /api/analytics/metrics
GET /api/analytics/summary
GET /api/analytics/categories
GET /api/analytics/comparison
GET /api/analytics/alerts
```

Los endpoints de métricas que ya existen en el prototipo deberían evolucionar hacia este espacio conceptual.

No significa que las URLs actuales deban cambiar inmediatamente; la propuesta establece el criterio para la evolución del backend.

---

## 8.6. Health

Los endpoints técnicos deberían mantenerse separados de los dominios de negocio:

```text
GET /health
```

Su responsabilidad sería comprobar que el servicio está disponible y, si posteriormente fuese necesario, comprobar dependencias técnicas.

---

# 9. Qué debería contener `main.py`

`main.py` debería ser deliberadamente pequeño.

Su responsabilidad principal sería:

1. crear la aplicación FastAPI;
2. cargar configuración;
3. registrar middleware;
4. registrar routers;
5. configurar elementos globales de la aplicación.

No debería contener:

- consultas a la base de datos;
- reglas de negocio;
- modelos de candidatos;
- lógica de selección;
- generación de métricas.

La documentación oficial de FastAPI utiliza precisamente un `main.py` que incorpora diferentes `APIRouter` en la aplicación principal. citeturn0search0

---

# 10. Cómo influye la estructura habitual de FastAPI

La documentación oficial de FastAPI propone, para aplicaciones mayores, separar la aplicación en varios módulos y utilizar `APIRouter` para agrupar endpoints. El ejemplo oficial incluye un `main.py`, un módulo de dependencias y una carpeta de routers separados por funcionalidad. citeturn0search0

Esta convención influye directamente en la propuesta de Nexova:

| Convención habitual | Aplicación en Nexova |
|---|---|
| `main.py` | Punto de entrada de la aplicación |
| `APIRouter` | Router independiente por dominio |
| `dependencies.py` | Dependencias compartidas y de infraestructura |
| Pydantic | Schemas y contratos de API |
| Settings/env vars | Configuración por entorno |
| Tags de routers | Organización de la documentación OpenAPI |

Sin embargo, Nexova necesita una organización algo más rica que el ejemplo mínimo de FastAPI porque ya existen varios dominios de negocio.

Por eso se propone utilizar `domains/` como nivel organizativo adicional.

La documentación de FastAPI demuestra que `APIRouter` puede incluirse también dentro de otros routers, lo que permite organizar una API jerárquica cuando el proyecto lo necesite. citeturn0search2

---

# 11. Frontend y backend como sistemas separados

## 11.1. Separación lógica

Aunque frontend y backend estén dentro del mismo repositorio, deben considerarse dos aplicaciones:

```text
Nexova
├── frontend/
└── backend/
```

El frontend no debe importar directamente módulos Python del backend.

La comunicación debe producirse mediante el contrato HTTP de la API.

```text
React / TypeScript
       │
       │ HTTP / JSON
       ▼
FastAPI
       │
       ▼
Domain + Infrastructure
```

Esto permite que cualquiera de las dos partes evolucione internamente sin romper la separación arquitectónica.

---

# 12. Monorepo frente a repositorios separados

Para el estado actual de Nexova, mantener frontend y backend en un **monorepo** es razonable.

Ventajas:

- cambios coordinados;
- una única ubicación para documentación;
- facilidad para levantar el sistema completo;
- posibilidad de ejecutar pruebas de integración;
- cambios de contrato API y frontend en el mismo Pull Request.

GitHub documenta precisamente escenarios en los que aplicaciones frontend/backend se benefician de coordinar cambios y pruebas dentro del mismo repositorio. citeturn1search0

Esto no significa que monorepo implique acoplamiento de código.

La separación debe mantenerse a nivel de aplicaciones, dependencias y responsabilidades.

Una separación posterior en repositorios independientes sería técnicamente posible si el tamaño del equipo, los ciclos de despliegue o las necesidades de organización lo justificaran.

---

# 13. Comunicación mediante API

El frontend debe consumir el backend exclusivamente mediante endpoints HTTP documentados.

Por ejemplo:

```text
Frontend
   │
   ├── GET /api/candidates
   ├── GET /api/vacancies
   ├── POST /api/applications
   └── GET /api/analytics/metrics
          │
          ▼
       FastAPI
```

El contrato debe definir:

- URL;
- método HTTP;
- parámetros;
- cuerpo de petición;
- respuesta;
- errores;
- códigos HTTP.

Esto es especialmente importante porque actualmente existe una representación de tipos en TypeScript y otra en Pydantic/Python. La duplicación de tipos debe gestionarse conscientemente para evitar que frontend y backend evolucionen con contratos incompatibles.

---

# 14. Variables de entorno

La configuración dependiente del entorno debe permanecer fuera del código fuente.

Ejemplos:

```text
DATABASE_URL
CORS_ALLOWED_ORIGINS
API_BASE_URL
SECRET_KEY
STORAGE_BUCKET
EMAIL_SERVICE_URL
```

La aplicación debería distinguir al menos entre:

```text
development
test
production
```

Los valores reales no deberían almacenarse en Git.

Se recomienda mantener un archivo:

```text
.env.example
```

con los nombres de las variables necesarias y valores de ejemplo no sensibles.

FastAPI documenta el uso de variables de entorno para configuración, incluyendo credenciales, URLs de bases de datos y claves secretas. citeturn0search3turn0search4

---

# 15. CORS

Cuando frontend y backend tienen diferentes orígenes, el navegador aplica la política de mismo origen y las peticiones cross-origin requieren una configuración CORS adecuada. citeturn1search1turn0search8

En desarrollo, Nexova puede tener, por ejemplo:

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
```

Estos son orígenes diferentes porque el puerto forma parte del origen.

En producción podrían existir dominios separados o un proxy que los presente bajo un mismo dominio.

La configuración CORS debería:

- permitir únicamente los orígenes necesarios;
- distinguir desarrollo y producción;
- no utilizar `*` indiscriminadamente;
- coordinarse con el sistema de autenticación si posteriormente se utilizan cookies o credenciales.

MDN recomienda limitar `Access-Control-Allow-Origin` al mínimo necesario, especialmente para APIs privadas. citeturn1search2

---

# 16. Evolución del backend actual

El backend actual contiene una estructura inicial en la que `main.py` registra la aplicación y un archivo de rutas concentra buena parte de la lógica, incluyendo modelos, generación de datos, transformaciones y handlers.

Esta estructura es válida como punto de partida o prototipo, pero no debería mantenerse cuando el sistema incorpore los dominios reales de Nexova.

El principal cambio propuesto es pasar progresivamente de:

```text
app/
├── main.py
└── routes.py
```

a una estructura donde:

- los routers estén separados;
- los dominios estén identificados;
- los casos de uso estén separados de HTTP;
- la persistencia esté aislada;
- las métricas estén separadas de las operaciones transaccionales.

No es necesario realizar toda esta reorganización de una sola vez. Puede hacerse de manera incremental a medida que se implementen funcionalidades reales.

---

# 17. Testing

La estructura propuesta también debe reflejarse en las pruebas.

Se recomienda separar:

```text
tests/
├── candidates/
├── vacancies/
├── companies/
├── applications/
└── analytics/
```

Deberían existir diferentes niveles de prueba:

### Unitarias

Para reglas de negocio y servicios.

### Integración

Para comprobar la interacción con base de datos, almacenamiento u otros servicios.

### API

Para verificar que los routers cumplen el contrato HTTP esperado.

### End-to-end

Para comprobar flujos completos entre frontend y backend cuando el proyecto alcance suficiente madurez.

La separación por dominios permite localizar rápidamente qué pruebas deben modificarse cuando cambia una funcionalidad.

---

# 18. Riesgos y puntos de atención

## 18.1. Riesgo: volver a concentrar la lógica en los routers

Si el equipo coloca consultas, reglas de negocio y transformaciones directamente dentro de los endpoints, los routers terminarán creciendo demasiado.

Consecuencias:

- dificultad para probar la lógica;
- duplicación;
- endpoints difíciles de mantener;
- fuerte acoplamiento entre HTTP y negocio.

**Mitigación:** los routers deben actuar principalmente como adaptadores HTTP y delegar los casos de uso en servicios.

---

## 18.2. Riesgo: mezclar dominios

Por ejemplo, colocar toda la lógica relacionada con candidaturas dentro de `candidates/` aunque realmente corresponda al proceso de selección.

Esto puede provocar que el modelo de candidato termine acumulando información que pertenece a una relación concreta entre candidato y vacante.

**Mitigación:** definir claramente los límites de cada dominio y utilizar `applications/` para la relación candidato-vacante.

---

## 18.3. Riesgo: romper el contrato frontend/backend

Si se cambia un schema del backend sin actualizar el consumidor TypeScript, el frontend puede seguir compilando pero fallar en tiempo de ejecución, o interpretar incorrectamente la respuesta.

**Mitigación:**

- documentar el contrato;
- mantener schemas explícitos;
- añadir pruebas de API;
- considerar generación de tipos/cliente a partir de OpenAPI cuando el proyecto madure.

---

## 18.4. Riesgo: configuración incorrecta entre entornos

Si URLs, credenciales o CORS quedan codificados en el código, el comportamiento puede funcionar en local y fallar en producción.

**Mitigación:** configuración mediante variables de entorno y archivos `.env` únicamente para desarrollo local, sin subir secretos al repositorio.

---

## 18.5. Riesgo: sobrearquitectura

Una estructura demasiado compleja también puede perjudicar al proyecto.

Crear demasiadas abstracciones, repositorios o servicios antes de que exista una necesidad real puede aumentar el tiempo de desarrollo y dificultar que nuevos miembros entiendan el sistema.

**Mitigación:** aplicar la arquitectura de manera incremental. Crear una capa únicamente cuando exista una responsabilidad real que separar.

---

# 19. Decisión final propuesta

La arquitectura recomendada para Nexova es:

> **Monolito modular con FastAPI, organizado por dominios de negocio y estructurado internamente mediante capas de API, aplicación, dominio e infraestructura.**

En términos prácticos:

```text
Nexova
│
├── frontend/
│   └── React + TypeScript
│
└── backend/
    └── FastAPI
        │
        ├── API
        │   └── routers
        │
        ├── Domains
        │   ├── candidates
        │   ├── vacancies
        │   ├── companies
        │   ├── applications
        │   └── analytics
        │
        ├── Infrastructure
        │   ├── database
        │   ├── storage
        │   ├── email
        │   └── external services
        │
        └── Core
            ├── configuration
            ├── security
            └── dependencies
```

Esta solución mantiene el backend suficientemente sencillo para la fase actual de Nexova, pero introduce límites claros que permiten añadir nuevas funcionalidades sin convertir el proyecto en un único bloque de código.

La decisión clave no es utilizar una arquitectura "compleja", sino **separar los dominios de negocio y evitar que la capa HTTP, la lógica de negocio y la infraestructura se mezclen**.

---

# 20. Fuentes consultadas

- FastAPI — *Bigger Applications - Multiple Files*. Documentación oficial sobre `APIRouter` y organización de aplicaciones grandes. citeturn0search0
- FastAPI — *APIRouter class*. Referencia oficial sobre prefijos, tags, dependencias e inclusión de routers. citeturn0search2
- FastAPI — *Settings and Environment Variables*. Configuración mediante variables de entorno. citeturn0search3
- FastAPI — *CORS*. Configuración de Cross-Origin Resource Sharing. citeturn0search8
- FastAPI — *Full Stack FastAPI Template*. Ejemplo oficial de una aplicación con frontend React y backend FastAPI. citeturn0search5
- GitHub Docs — *Multi-ecosystem updates*. Consideraciones sobre aplicaciones full-stack y monorepos. citeturn1search0
- MDN — *Cross-Origin Resource Sharing (CORS)*. Funcionamiento de las peticiones cross-origin desde aplicaciones web. citeturn1search1
- MDN — *CORS configuration*. Consideraciones de seguridad para limitar los orígenes permitidos. citeturn1search2