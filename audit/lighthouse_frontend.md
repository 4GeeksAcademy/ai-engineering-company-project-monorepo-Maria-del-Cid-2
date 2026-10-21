Auditoría frontend de Nexova — Análisis de resultados de Lighthouse
Fecha de las mediciones: 19 de octubre de 2026
Herramienta: Lighthouse 13.4.1
Alcance: página principal (index.html), página de empresas (application-companies.html) y página de talento (application-candidates.html).

El objetivo de este análisis es documentar el estado actual del frontend de Nexova a partir de las métricas obtenidas, identificar diferencias entre las tres páginas y evaluar qué áreas presentan los resultados más relevantes. En esta fase no propondré soluciones ni cambios de implementación.
1. Resumen ejecutivo
Puntuaciones de Lighthouse sobre 100 puntos. Resultados extraídos de la primera página de cada PDF.
Index
57
Rendimiento

Companies
69
Rendimiento

Talent
65
Rendimiento



La página principal presenta el rendimiento más bajo, mientras que Companies obtiene la puntuación más alta de las tres. Las tres páginas comparten una puntuación SEO de 63.

Categoría	Index	Companies	Talent
Rendimiento (Performance)	57	69	65
Accesibilidad (Accessibility)	96	90	92
Buenas prácticas (Best Practices)	96	96	100
SEO	63	63	63
Los resultados muestran tres patrones principales:
1. Rendimiento: es el área con mayor margen de mejora aparente. Las tres páginas están por debajo de 70 puntos, y la página principal registra el resultado más bajo.
2. Accesibilidad y buenas prácticas: las puntuaciones son elevadas, aunque los informes siguen identificando incidencias concretas en accesibilidad y errores de consola en algunas páginas.
3. SEO: las tres páginas obtienen 63 puntos y Lighthouse señala en todas ellas que la página está bloqueada para la indexación.
Es importante tener en cuenta que las puntuaciones son estimaciones calculadas a partir de distintas métricas. No representan porcentajes de calidad ni implican que una página con 69 puntos funcione exactamente un 12 % mejor que otra con 57.
2. Condiciones de las pruebas
Las tres mediciones se realizaron en condiciones equivalentes según la información de los informes, lo que permite una comparación razonable entre páginas.
- Dispositivo emulado: Moto G Power.
- Red: Slow 4G throttling, una conexión móvil limitada simulada.
- Tipo de prueba: carga inicial de la página.
- Sesión: página individual.
- Navegador: Chromium 155.0.0.0.
- Versión de Lighthouse: 13.4.1.
Los resultados corresponden a las páginas desplegadas en un entorno de GitHub Codespaces, bajo el dominio app.github.dev.

Esta última circunstancia es relevante para interpretar la auditoría: las puntuaciones describen el comportamiento medido en ese entorno concreto y no necesariamente el que tendrá la web en su dominio de producción. Tampoco constituyen, por sí solas, una medición de la experiencia real de todos los usuarios.
3. Análisis comparativo del rendimiento
Las métricas de rendimiento permiten observar qué experimenta el usuario durante la carga y hasta qué punto la página responde con fluidez.
Puntuación de rendimiento por página
Comparativa de las puntuaciones de Lighthouse sobre 100.


0255075100IndexCompaniesTalent














3.1. Métricas principales
Métrica	Index	Companies	Talent
Performance	57	69	65
First Contentful Paint (FCP)	3,0 s	2,9 s	2,9 s
Largest Contentful Paint (LCP)	8,6 s	6,2 s	6,3 s
Total Blocking Time (TBT)	510 ms	210 ms	330 ms
Cumulative Layout Shift (CLS)	0	0	0
Speed Index	3,0 s	2,9 s	2,9 s
3.2. Interpretación de las métricas

First Contentful Paint (FCP)
2,9–3,0 segundos
Mide el tiempo hasta que aparece el primer contenido visible. Las tres páginas presentan valores prácticamente idénticos, por lo que no se observa una diferencia significativa en esta métrica entre ellas. El primer contenido tarda cerca de tres segundos en aparecer en las condiciones de prueba.




Largest Contentful Paint (LCP)
6,2–8,6 segundos
Representa el tiempo necesario para mostrar el elemento de contenido más grande visible en la zona inicial de la página. Es una de las diferencias más importantes entre las tres mediciones.
- Index: 8,6 s.
- Companies: 6,2 s.
- Talent: 6,3 s.
Index tarda 2,4 segundos más que Companies en alcanzar este hito. Las tres mediciones superan ampliamente los 4 segundos, umbral a partir del cual Google clasifica el LCP como deficiente.




Total Blocking Time (TBT)
210–510 milisegundos
Mide el tiempo acumulado durante el que las tareas largas bloquean la ejecución del hilo principal e impiden responder con normalidad a interacciones.

Index presenta 510 ms, frente a 330 ms en Talent y 210 ms en Companies. Esto indica que la página principal tiene la mayor carga de bloqueo durante el periodo medido.




Cumulative Layout Shift (CLS)
0 en las tres páginas
Mide los desplazamientos inesperados de los elementos durante la carga. El resultado es favorable: en estas pruebas no se han registrado cambios de disposición que contribuyan al CLS.




Speed Index
2,9–3,0 segundos
Estima la rapidez con la que se completa visualmente el contenido de la pantalla. Los resultados son muy similares entre páginas. No obstante, el Speed Index no sustituye al LCP: ambos indicadores evalúan aspectos diferentes de la carga visual.



3.3. Comparativa del LCP
Largest Contentful Paint por página
Tiempo en segundos. Menor es mejor; 2,5 s es el límite de la categoría buena.


0 s2,5 s5 s7,5 s10 sIndexCompaniesTalent














El LCP es especialmente relevante porque refleja cuándo aparece el contenido principal, no solo cuándo se dibuja algún elemento inicial.

Con los datos disponibles, Index es la página con el comportamiento de carga visual más desfavorable. Companies y Talent se sitúan en un rango similar, aunque tampoco alcanzan el umbral de buena experiencia para esta métrica.

Como referencia, los umbrales habituales de Core Web Vitals para LCP son:
- Bueno: hasta 2,5 s.
- Necesita mejorar: más de 2,5 s y hasta 4 s.
- Deficiente: más de 4 s.
Estos umbrales permiten clasificar los valores observados, aunque las mediciones de Lighthouse aquí presentadas son pruebas de laboratorio, no datos de campo de usuarios reales.
4. Diagnósticos de rendimiento compartidos
Los informes incluyen varias auditorías que ayudan a caracterizar el tipo de carga que presenta el frontend.
Diagnóstico	Index	Companies	Talent
Ahorro estimado en entrega de imágenes	1.132 KiB	808 KiB	808 KiB
Ahorro estimado por caché	648 KiB	657 KiB	648 KiB
Ahorro estimado por recursos que bloquean el renderizado	1.290 ms	1.390 ms	1.350 ms
Trabajo del hilo principal	2,4 s	2,4 s	2,4 s
JavaScript no utilizado (ahorro estimado)	38 KiB	39 KiB	38 KiB
Elementos de imagen sin ancho y alto explícitos	Sí	Sí	Sí
Tareas largas del hilo principal	7	6	6
Fuente: páginas 2 y 3 de los respectivos informes. KiB y ms corresponden a las unidades mostradas por Lighthouse. Los ahorros son estimaciones del diagnóstico, no mejoras ya conseguidas ni valores que deban sumarse directamente.
4.1. Entrega de imágenes
Lighthouse estima un ahorro potencial de 1.132 KiB en Index y de 808 KiB tanto en Companies como en Talent.

La página principal destaca en esta auditoría por el mayor volumen de ahorro estimado. La coincidencia de los resultados de Companies y Talent sugiere que ambas presentan un perfil similar en este diagnóstico, aunque el informe no demuestra que utilicen exactamente los mismos archivos ni que todas sus imágenes tengan idéntico peso.
4.2. Caché y recursos que bloquean el renderizado
Las tres páginas muestran oportunidades detectadas relacionadas con los tiempos de caché y los recursos que bloquean el renderizado inicial.

El ahorro estimado asociado al bloqueo del renderizado se encuentra entre 1.290 y 1.390 ms. Companies presenta la cifra más alta en esta auditoría, pese a obtener la mejor puntuación de rendimiento.

Esto es importante para interpretar los resultados: una oportunidad de optimización individual no determina por sí sola la puntuación global. Lighthouse combina diversas métricas, y el impacto de cada una depende de su comportamiento dentro de la carga completa.
4.3. Ejecución de JavaScript y tareas largas
Los tres informes registran 2,4 segundos de trabajo del hilo principal. Además, identifican tareas largas: siete en Index y seis en cada una de las otras páginas.

Index también presenta un TBT de 510 ms, superior al de las otras dos páginas. La combinación de estas mediciones sitúa a la página principal como la más desfavorable en términos de bloqueo del hilo principal.

Companies presenta el TBT más bajo, con 210 ms, y Talent queda en una posición intermedia, con 330 ms.
4.4. Tamaño del DOM y otros diagnósticos
Lighthouse también incluye las auditorías «Optimize DOM size» y «LCP breakdown» en las tres páginas. La presencia de estas auditorías indica que el informe ha evaluado esas dimensiones, pero las capturas aportadas no muestran sus detalles desplegados.

Por tanto, no es posible determinar con estos documentos el número exacto de nodos DOM, la profundidad del árbol, ni la contribución temporal de cada fase al LCP. Tampoco conviene atribuir el resultado de rendimiento a una causa técnica concreta sin esos datos.
5. Análisis de accesibilidad
Las puntuaciones de accesibilidad son elevadas en las tres páginas, aunque los informes muestran diferencias relevantes.
Indicador	Index	Companies	Talent
Puntuación	96	90	92
Auditorías superadas	23	20	25
Elementos pendientes de comprobación manual	10	10	10
Contraste insuficiente	Detectado	Detectado	Detectado
Problemas de atributos ARIA	No indicado	Detectado	Detectado
Fuente: páginas 3 de los tres informes. La tabla refleja las incidencias visibles en las capturas; no implica que las auditorías superadas sean idénticas entre páginas.
5.1. Contraste de colores
Lighthouse detecta insuficiencias en la relación de contraste entre el fondo y el texto en las tres páginas.

Es un hallazgo relevante porque el contraste afecta a la legibilidad, especialmente para personas con baja visión o dificultades para distinguir determinados colores. La puntuación general elevada no significa que todos los elementos de la interfaz cumplan los requisitos de accesibilidad.
5.2. Atributos ARIA
En Companies y Talent aparece el aviso de que algunos atributos aria-* no se corresponden con los roles de los elementos.

ARIA es el conjunto de atributos que proporciona información adicional sobre la función y el estado de los componentes a las tecnologías de asistencia, como los lectores de pantalla.

Este hallazgo no aparece en la sección de incidencias visibles del informe de Index. Esto no permite asegurar que Index esté libre de cualquier problema relacionado con ARIA, sino únicamente que Lighthouse no muestra ese aviso en el resumen aportado.
5.3. Revisiones manuales pendientes
Las tres páginas indican diez elementos adicionales que deben comprobarse manualmente.

Lighthouse advierte expresamente que sus pruebas automáticas solo detectan una parte de los posibles problemas de accesibilidad. Por ello, las puntuaciones de 90 a 96 deben interpretarse como resultados de las comprobaciones automatizadas y no como una certificación completa de accesibilidad.

Conclusión de esta categoría: la accesibilidad automatizada presenta un estado favorable, pero existen hallazgos compartidos de contraste y otros relacionados con ARIA en dos de las páginas.
6. Análisis de buenas prácticas
Indicador	Index	Companies	Talent
Puntuación	96	96	100
Auditorías superadas	12	12	13
Errores de consola señalados	Sí	Sí	No indicado
6.1. Errores de consola
Los informes de Index y Companies indican que se han registrado errores del navegador en la consola. Este hallazgo no aparece en el resumen de Talent.

La auditoría no incluye el contenido concreto de los errores, por lo que no es posible determinar su origen, gravedad, frecuencia o efecto funcional. La presencia de un error de consola tampoco significa necesariamente que la página haya dejado de funcionar.
6.2. Seguridad y compatibilidad
Los tres informes enumeran comprobaciones relativas a:
- Content Security Policy (CSP) y protección frente a ataques XSS.
- Política HSTS.
- Aislamiento de origen mediante COOP.
- Protección frente al clickjacking.
- Trusted Types para mitigar determinados ataques XSS basados en DOM.
Estas comprobaciones aparecen dentro de la sección de seguridad, pero su aparición en el informe no significa automáticamente que se haya confirmado una vulnerabilidad. Para determinar el estado de cada control sería necesario consultar el resultado detallado de la auditoría correspondiente.

Talent obtiene 100 puntos en buenas prácticas, frente a 96 en las otras dos páginas. Es el único resultado perfecto de esta categoría, dentro de las pruebas realizadas.
7. Análisis SEO
El comportamiento de las tres páginas es idéntico en la puntuación general de SEO.
Indicador	Index	Companies	Talent
Puntuación SEO	63	63	63
Auditorías superadas	7	7	7
Página bloqueada para indexación	Sí	Sí	Sí
Comprobaciones manuales adicionales	1	1	1
7.1. Bloqueo de indexación
En las tres páginas, Lighthouse muestra el aviso Page is blocked from indexing.

Este es el hallazgo SEO más significativo de los informes. Indica que la comprobación de rastreo e indexación ha detectado un impedimento para que los buscadores indexen las páginas.

El resultado tiene especial importancia si el objetivo de Nexova es que estas páginas sean accesibles desde los resultados orgánicos de búsqueda. Sin embargo, las capturas no identifican el mecanismo exacto que causa el bloqueo, por lo que no permiten afirmar si procede de una directiva noindex, de una cabecera HTTP u otra condición.

También hay que distinguir entre la capacidad técnica de indexación y el posicionamiento: una puntuación SEO de Lighthouse no mide directamente la posición que una página ocupa en Google.
7.2. Limitaciones de la evaluación SEO
La puntuación de 63 refleja las comprobaciones incluidas en Lighthouse. El propio informe aclara que existen otros factores que pueden influir en el posicionamiento y que no están incluidos en esa puntuación.

Por tanto, estos resultados no permiten concluir que las tres páginas tengan exactamente la misma calidad de contenido, relevancia para las búsquedas o rendimiento orgánico real. Lo que sí muestran es que comparten el mismo resultado en las comprobaciones automatizadas presentadas.
8. Comparativa global: principales hallazgos

Rendimiento — principal área de preocupación

Index obtiene 57 puntos y presenta un LCP de 8,6 segundos y un TBT de 510 ms. Companies y Talent obtienen puntuaciones superiores, pero sus LCP de 6,2 y 6,3 segundos también son deficientes según los umbrales de referencia.




Accesibilidad — resultados elevados con incidencias identificadas

Las puntuaciones están entre 90 y 96. El contraste insuficiente aparece en las tres páginas y los problemas de atributos ARIA se señalan en Companies y Talent.




Buenas prácticas — resultado favorable

Index y Companies obtienen 96 puntos, mientras que Talent alcanza 100. Los errores de consola aparecen en los informes de las dos primeras páginas.




SEO — incidencia compartida

Las tres páginas obtienen 63 puntos y Lighthouse señala un bloqueo de indexación en todas ellas.



9. Conclusiones de la auditoría
A partir exclusivamente de los tres informes adjuntos, se pueden establecer las siguientes conclusiones sobre el estado actual del frontend de Nexova:

1. La página principal presenta el rendimiento más desfavorable. Su puntuación es de 57, frente a 69 en Companies y 65 en Talent. Las diferencias más destacadas se encuentran en el LCP y el TBT.

2. La carga del contenido principal es lenta en las tres páginas. Los LCP superan los seis segundos en todos los casos y alcanzan 8,6 segundos en Index.

3. Las tres páginas comparten un perfil similar en varios diagnósticos técnicos. Lighthouse identifica oportunidades relacionadas con la entrega de imágenes, la caché, los recursos que bloquean el renderizado, el trabajo del hilo principal y el JavaScript no utilizado.

4. La accesibilidad automatizada obtiene puntuaciones elevadas, pero no está exenta de incidencias. El contraste insuficiente es común a las tres páginas, y los avisos sobre ARIA aparecen en Companies y Talent.

5. Las buenas prácticas presentan los mejores resultados globales. Talent alcanza 100 puntos, aunque los errores de consola identificados en las otras dos páginas requieren distinguir entre el resultado agregado y los hallazgos particulares.

6. La indexación es una cuestión transversal. Las tres páginas obtienen 63 puntos en SEO y presentan el aviso de bloqueo de indexación. Su relevancia funcional dependerá de si la web debe estar disponible en los resultados de búsqueda.

7. Los resultados deben interpretarse dentro del contexto de la prueba. Las mediciones se realizaron con un dispositivo móvil emulado y una conexión Slow 4G, en un entorno de Codespaces. No representan por sí solas las métricas de campo ni la experiencia de todos los visitantes.

En definitiva, la auditoría inicial refleja un frontend con puntuaciones elevadas en accesibilidad y buenas prácticas, pero con un rendimiento de carga mejorable y una incidencia de indexación compartida por las tres páginas. Este es el diagnóstico del estado medido, sin entrar todavía en las causas definitivas ni en las posibles soluciones.