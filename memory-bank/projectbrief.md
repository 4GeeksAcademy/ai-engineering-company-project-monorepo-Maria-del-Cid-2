# Project Brief — Nexova

## 1. Propósito del proyecto

Nexova es un proyecto transversal de AI Engineering para desarrollar progresivamente soluciones digitales y de inteligencia artificial que den soporte a las diferentes áreas de negocio de Nexova Solutions.

El objetivo es construir una base tecnológica común que permita desarrollar aplicaciones frontend, servicios backend, soluciones de datos, agentes de IA, RAG, automatizaciones y herramientas internas de forma organizada y reutilizable.

El proyecto debe evolucionar manteniendo un contexto persistente de negocio y técnico para que los agentes de desarrollo puedan trabajar sobre el repositorio sin tener que reconstruir su contexto en cada sesión.

---

## 2. Empresa

Nexova Solutions es una consultora de recursos humanos fundada en 2011.

Cuenta con sede en Valencia y una oficina de expansión en Miami, aproximadamente 120 empleados y unos 8 millones de dólares de facturación anual.

Sus principales líneas de negocio son:

1. Headhunting de mandos intermedios, managers y directivos.
2. Servicios externalizados de equipos de atención al cliente para empresas tecnológicas.
3. Formación corporativa en soft skills y liderazgo.

Sus principales clientes son empresas medianas, especialmente de los sectores tecnológico, retail y servicios financieros.

La información corporativa completa y el briefing empresarial se encuentran en:

`CONTEXT.es.md`

Ese documento debe considerarse la referencia principal para el contexto general del negocio.

---

## 3. Problemas de negocio que motivan el proyecto

Nexova presenta diferentes necesidades de digitalización y automatización, entre ellas:

- procesos de selección con tareas manuales;
- falta de visibilidad en tiempo real sobre las candidaturas;
- gestión de formación mediante documentos, formularios y hojas de cálculo;
- problemas relacionados con SLA y operaciones de atención al cliente;
- información de CRM inconsistente;
- procesos comerciales y de marketing parcialmente manuales;
- gestión interna de RRHH mediante correo y hojas de cálculo;
- stack tecnológico desconectado;
- ausencia de una capa unificada de telemetría y logging;
- generación de informes con procesos manuales y retrasados.

El proyecto de AI Engineering pretende proporcionar progresivamente soluciones para estos problemas.

---

## 4. Ecosistema de aplicaciones

El proyecto contempla diferentes tipos de soluciones:

- web corporativa pública;
- aplicaciones internas de back-office;
- gestión de candidaturas;
- herramientas para formación corporativa;
- soluciones de atención al cliente;
- herramientas comerciales;
- herramientas internas de RRHH;
- sistemas de datos y telemetría;
- agentes de IA;
- soluciones RAG;
- workflows y automatizaciones;
- dashboards;
- herramientas de soporte a la dirección.

Estas áreas representan el alcance general del proyecto y no deben interpretarse automáticamente como funcionalidades ya implementadas.

---

## 5. Web corporativa

La web pública de Nexova forma parte del ecosistema del proyecto.

La web incluye:

- información general de Nexova;
- información sobre sus oficinas;
- servicios;
- referencias/clientes;
- información de contacto;
- formulario para empresas interesadas en contratar servicios de Nexova;
- formulario para trabajadores/candidatos interesados en enviar su CV.

La aplicación pública debe ubicarse en:

`uis/website`

siguiendo la estructura definida por la plantilla del monorepo.

---

## 6. Aplicaciones internas

Las aplicaciones internas de Nexova deben ubicarse en:

`uis/backoffice`

Esta área está destinada a las herramientas internas de administración y operaciones de la compañía.

Puede incluir progresivamente capacidades como:

- autenticación;
- gestión de personas;
- gestión de operaciones;
- comunicación interna;
- herramientas de selección;
- herramientas de RRHH;
- otros procesos internos.

---

## 7. Talent Pipeline Tracker

Uno de los productos actualmente desarrollados es el Talent Pipeline Tracker.

Su objetivo es facilitar la gestión interna de candidaturas durante procesos de selección de Nexova.

La aplicación permite centralizar información que anteriormente podía estar distribuida entre hojas de cálculo y otros canales.

Actualmente la aplicación permite:

- consultar candidaturas;
- buscar candidaturas;
- filtrar por estado;
- filtrar por etapa;
- utilizar paginación;
- registrar nuevas candidaturas;
- consultar el detalle de una candidatura;
- actualizar estado y etapa;
- gestionar notas internas;
- eliminar candidaturas.

La aplicación existente se encuentra actualmente en:

`uis/talent-pipeline-tracker`

Su contexto funcional específico está documentado en:

`uis/talent-pipeline-tracker/context.md`

---

## 8. Caso de uso actual del Talent Pipeline Tracker

El caso de uso documentado corresponde al proceso de selección de:

**Asistente de Dirección**

La herramienta está destinada a ayudar a gestionar un volumen elevado de candidaturas y a mantener actualizado el estado del proceso de selección.

La información específica del proceso, requisitos y criterios funcionales se encuentra en el `context.md` de la aplicación.

---

## 9. Evolución prevista

El contexto empresarial contempla futuras soluciones basadas en IA y automatización, entre ellas:

### Selección

- scoring y ranking de candidatos;
- búsqueda semántica/RAG de candidatos;
- portal de candidatos;
- agentes de comunicación.

### Formación

- recomendaciones personalizadas;
- chatbot de formación.

### Atención al cliente

- chatbot RAG;
- base de conocimiento semántica;
- dashboard en tiempo real;
- análisis de sentimiento.

### Ventas

- dashboards;
- automatización de prospección;
- generación de argumentos comerciales mediante IA.

### RRHH interno

- portal interno;
- onboarding;
- KPIs;
- agente interno.

### Tecnología y datos

- telemetría;
- logging;
- pipelines de datos;
- agente de ingeniería.

### Dirección

- dashboard ejecutivo;
- informes;
- asistente ejecutivo.

Estas funcionalidades forman parte del contexto y evolución prevista del proyecto. No deben considerarse implementadas hasta que exista código o documentación específica que lo confirme.

---

## 10. Principio de desarrollo

El proyecto debe evolucionar de forma incremental.

Los agentes deben trabajar sobre la estructura y funcionalidades existentes y evitar reconstrucciones innecesarias.

Antes de implementar una nueva funcionalidad se debe comprobar:

1. si ya existe una implementación;
2. dónde está ubicada;
3. qué documentación la describe;
4. qué contratos o tipos utiliza;
5. qué dependencias tiene;
6. qué reglas de desarrollo son aplicables.

El contexto de negocio no sustituye a la documentación técnica específica y el estado del código debe utilizarse para determinar qué está realmente implementado.