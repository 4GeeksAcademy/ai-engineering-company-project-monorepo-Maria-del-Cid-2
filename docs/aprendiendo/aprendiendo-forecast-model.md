# Aprendiendo: predicción de ingresos mensuales de Nexova



Guía didáctica del desarrollo por fases de un sistema de *forecasting* de

ingresos. Este documento se actualizó al cierre de las siete fases. **Estado actual: Fase 7 — documentación y revisión final completadas.**



## 1. Objetivo de negocio



El propósito es estimar los ingresos mensuales consolidados de Nexova y dar a
dirección una referencia cuantitativa para presupuestación, planificación de
capacidad y revisión de desviaciones. El modelo predice `revenue_usd` por mes;
no identifica por sí solo causas comerciales ni prescribe decisiones. Marcos,
Laura y otros responsables pueden comparar el pronóstico con resultados reales
y combinarlo con información de contratos, pipeline y contexto empresarial que
no está presente en esta serie. No sustituye el criterio de gestión.



La fuente indicada es `data/raw/nexova_sales.csv`. El análisis debe conservar

el CSV original y utilizar únicamente observaciones `business_line =

consolidated`. Los porcentajes de peso de las líneas de negocio que aparecen en

el briefing son contexto aproximado, no datos mensuales, y no permiten calcular
el cambio real del mix de negocio. La serie consolidada se eligió porque es el
objetivo mensual del proyecto y evita fingir precisión por línea cuando no hay
observaciones mensuales segmentadas verificadas. Por ello el modelo no mide ni
predice composición del negocio, margen, contratos o ingresos por línea.

El pasado es solo una referencia: cambios de mercado, precios, clientes,
capacidad, adquisiciones o calidad del origen pueden romper patrones históricos.
Una serie pequeña y un único holdout tampoco permiten asegurar el comportamiento
futuro ni inferir causalidad.



## 2. Fases previstas



| Fase | Objetivo | Estado |

|---|---|---|

| 1. Exploración | Conocer arquitectura, contexto y calidad/patrones del CSV. | **Completada en esta entrega** |

| 2. Preparación | Definir validaciones, variables causales y split cronológico 96/24. | **Completada en esta entrega** |

| 3. Entrenamiento | Random Forest entrenado solo con 2016–2023; forecast recursivo 2024–2025. | **Completada en esta entrega** |

| 4. Evaluación | Calcular métricas acordadas con el período 2024–2025. | **Completada** |

| 5. Visualización | Mostrar realidad, predicción y banda orientativa calibrada con validación temporal. | **Completada** |

| 6. Pruebas | Verificar split, calidad, reproducibilidad y ausencia de fuga temporal. | **Completada; suite combinada: 25 passed (Phase 6: 10 passed)** |

| 7. Documentación y revisión | Consolidar decisiones, resultados y límites del sistema. | **Completada** |



Las fases 1–7 están cerradas. Las mejoras futuras indicadas aquí son propuestas y no forman parte de la implementación actual.



## 3. Fase 1 — exploración y diagnóstico

### Conceptos de Machine Learning usados en el proyecto

Este trabajo es **aprendizaje supervisado**: cada ejemplo de entrenamiento
contiene features (información de calendario e ingresos pasados) y una etiqueta
conocida, el ingreso del mes objetivo. Como esa etiqueta es numérica, es un
problema de **regresión**. El modelo aprende relaciones predictivas; no demuestra
que una feature cause el ingreso.

El conjunto de **entrenamiento** son los meses 2016–2023, usados para ajustar los
árboles. El **holdout** son 2024–2025, reservado para medir rendimiento en meses
posteriores. En series temporales los datos no se barajan al azar: una división
aleatoria podría permitir que meses futuros influyeran en el entrenamiento y
simular un escenario que no existiría al predecir en producción. La evaluación
de holdout es una medición posterior del resultado, no una entrada para ajustar
el modelo.

La **ingeniería de features** transforma el historial en información útil para
el algoritmo. Un lag es un valor anterior (por ejemplo, `revenue_lag_1` para
enero de 2024 es diciembre de 2023); una estadística móvil resume meses previos.
La tendencia es un índice temporal creciente; mes, trimestre y seno/coseno
codifican el calendario. La **estacionalidad** son patrones que se repiten por
época del año (como enero alto y agosto bajo en esta serie); la tendencia es el
cambio de nivel a lo largo del tiempo. Se usan ambas representaciones porque
son señales distintas.

Un **Random Forest** ajusta muchos árboles de decisión sobre muestras aleatorias
de filas/features y promedia sus resultados de regresión. El promedio suele
reducir la inestabilidad de un árbol individual, pero no garantiza extrapolar
bien una tendencia ni superar un baseline simple. `random_state=42` fija la
aleatoriedad usada por el bosque para que, con los mismos datos y dependencias,
la ejecución sea reproducible; no garantiza idénticos resultados entre todas
las versiones de librerías o plataformas.

Un pronóstico de horizonte largo requiere **recursión**: después de predecir
enero de 2024, esa predicción entra al historial para crear features de febrero;
no se dispone del ingreso real futuro. La **fuga de datos** ocurre si se usa
información que no estaría disponible en el momento de pronosticar, por ejemplo
el ingreso real de febrero para construir sus lags o para ajustar un scaler con
todo el periodo. Las ventanas se desplazan una observación y el holdout se
agrega al historial como predicciones, no como valores reales. En este pipeline
no existe un transformador de preprocesamiento aprendido separado del estimador.



### 3.1. Qué se inspeccionó



El dataset está en `data/raw/nexova_sales.csv` (la ubicación real coincide con

la esperada). Se revisaron la estructura general del monorepo, las convenciones

de `data/raw/` y `scripts/`, el contexto `CONTEXT.es.md` y las guías existentes

en `docs/aprendiendo/`. Estas guías suelen comenzar con objetivo/estado,

explicar conceptos y decisiones con secciones numeradas, y separar hechos

comprobados de propuestas o limitaciones; se adopta ese estilo.



`CONTEXT.md` es todavía un archivo plantilla y nombra un briefing que no está

presente con ese nombre. Para esta fase se contrastó el contexto Nexova

disponible en `CONTEXT.es.md`: describe a Nexova Solutions y a Marcos Ibáñez

(Ventas y Desarrollo de Negocio) y Laura Mendoza (CEO), pero **no define el

esquema de este CSV ni su frecuencia**. La definición de columnas y patrones

usada aquí procede del encargo, y no debe presentarse como contrato encontrado

en el archivo de contexto.



### 3.2. Calidad estructural comprobada



Inspección del archivo original, sin editarlo:



| Comprobación | Resultado observado |

|---|---|

| Filas / meses | 120 |

| Columnas | `month`, `revenue_usd`, `active_contracts`, `avg_contract_value_usd`, `business_line` |

| Serie consolidada | 120 filas; todas tienen `business_line=consolidated` |

| Rango de fechas | 2016-01-01 a 2025-12-01 |

| Inicio de mes | Las 120 fechas corresponden al día 1 |

| Continuidad | Ningún mes faltante en 2016-01–2025-12 |

| Duplicados de fecha | Ninguno; 120 fechas únicas |

| Celdas vacías | Ninguna en las columnas del CSV |

| Ingresos | Todos positivos y convertibles a número |

| Contratos y valor promedio | Los 120 valores se pudieron convertir a entero/decimal y son positivos |



El archivo CSV no almacena tipos explícitos: la fecha viene como texto ISO y

los valores numéricos como texto decimal. El análisis los interpretó como

fecha, enteros y decimales al validarlos. La serie satisface las condiciones

básicas de cobertura y continuidad solicitadas. Esta validación no demuestra

por sí sola la procedencia ni la exactitud contable de los importes.

Las columnas disponibles son `month` (mes de observación), `revenue_usd`
(ingreso mensual en USD), `active_contracts` (contratos activos),
`avg_contract_value_usd` (valor medio de contrato) y `business_line` (segmento
de negocio). La serie usada cubre enero de 2016 a diciembre de 2025. En la
revisión exploratoria se encontraron 120 filas consolidadas, una por cada mes,
sin duplicados, huecos, nulos ni valores de ingreso no positivos; las fechas
corresponden al primer día de mes y los campos numéricos se pudieron convertir.



### 3.3. Crecimiento y estacionalidad observados



El promedio mensual aumenta de **673.772,39 USD en 2016** a **987.746,21 USD

en 2025**. Las sumas por año y su variación frente al año anterior fueron:



| Año | Ingresos anuales (USD) | Variación anual de la suma |

|---:|---:|---:|

| 2016 | 8.085.268,72 | — |

| 2017 | 8.643.839,91 | +6,91 % |

| 2018 | 8.702.041,09 | +0,67 % |

| 2019 | 9.293.138,53 | +6,79 % |

| 2020 | 9.417.553,34 | +1,34 % |

| 2021 | 10.109.350,62 | +7,35 % |

| 2022 | 10.159.753,31 | +0,50 % |

| 2023 | 10.893.866,04 | +7,23 % |

| 2024 | 11.171.763,36 | +2,55 % |

| 2025 | 11.852.954,58 | +6,10 % |



Las variaciones se calcularon sobre la suma anual, no comparando diciembre con

diciembre. Esa diferencia importa porque hay estacionalidad y fluctuaciones

dentro de cada año. La secuencia alterna años cercanos al 7 % y al 1 % hasta

2023, coherente en términos generales con el patrón descrito, pero las tasas

calculadas sobre sumas anuales no reproducen exactamente el patrón especificado

para un crecimiento interanual comparable. En 2024 y 2025 la alternancia no es

exacta. Por ello conviene documentar esta discrepancia y no asumir que los datos

siguen una fórmula perfectamente determinista.



Para hacer visible la estacionalidad, se comparó cada ingreso con el promedio

del mismo año y después se promedió esa diferencia porcentual entre años:



| Mes | Desviación media frente al promedio de su año |

|---|---:|

| Enero | +16,94 % |

| Febrero | +16,40 % |

| Marzo–julio | entre -2,36 % y +0,61 % |

| Agosto | -21,55 % |

| Septiembre–diciembre | entre -2,23 % y -0,87 % |



Las cifras apoyan los patrones del briefing: enero/febrero son altos, agosto

presenta una caída marcada y los otros meses están próximos al promedio anual.

Es un resumen exploratorio, no una prueba causal de que vacaciones o

presupuestos produzcan esas diferencias.

Decisiones de exploración: conservar el CSV de origen sin editar, filtrar la
línea consolidada y no desagregar con porcentajes aproximados del briefing.
También se distinguió el crecimiento de sumas anuales del crecimiento YoY del
mismo mes; sus cifras no son intercambiables. Estos controles describen
estructura y patrones, no validan la contabilidad ni el origen de los datos.



### 3.4. Dependencias y convenciones del proyecto



Las dependencias específicas del pipeline de forecasting se declaran en
`data/process/requirements.txt`, separadas de las dependencias del servicio API.
Desde la raíz del repositorio se instalan en el entorno `.venv` con:

```powershell
uv pip install --python .venv\Scripts\python.exe -r data/process/requirements.txt
```



La documentación de `data/raw/` lo caracteriza como zona de aterrizaje para

datos originales sin transformar. `scripts/` se reserva para utilidades

auxiliares. Todavía no se decide dónde persistir modelo y artefactos: se

revisará la arquitectura aplicable antes de crear rutas.



### 3.5. Problemas y límites encontrados



1. **Contexto de datos incompleto:** `CONTEXT.md` es plantilla y `CONTEXT.es.md`

   no describe el dataset. Se usó el contrato incluido en el encargo para

   interpretar columnas y patrones, dejando explícita la diferencia.

2. **Crecimiento no perfectamente coincidente:** el cambio anual de sumas

   alterna aproximadamente entre 7 % y 1 % en 2017–2023, con valores fuera de

   ese rango en otros años. La suma anual no es idéntica a una tasa interanual

   de un mes; en fases posteriores se deberá acordar cómo se medirá el patrón

   antes de juzgarlo.

3. **Dependencias de ML ausentes del entorno consultado:** no se añadieron ni

   instalaron; se requiere resolverlo antes del entrenamiento.

4. **PSI:** puede comparar distribuciones de variables observadas, pero el CSV

   solo contiene el total consolidado. No permite medir el PSI del mix mensual

   entre outsourcing, headhunting y training.

5. **Gini y caídas anómalas:** Gini no es una métrica estándar de regresión; la

   definición operacional de caída y la suficiencia de casos deben acordarse y

   comprobarse con resultados, sin forzar una puntuación.

6. **K2 Score:** implementado con autorización como RMSSE para Nexova. El

  nombre K2 es propio del proyecto, no universal. Se calcula como la raíz del

  MSE de los 24 pronósticos congelados dividido por el MSE estacional ingenuo

  de entrenamiento (lag 12), calculado exclusivamente con los 96 meses de

  2016-01 a 2023-12 (84 diferencias). K2 < 1 indica error por debajo de la

  escala de referencia; = 1, igual; > 1, por encima. No es porcentaje de

  exactitud ni probabilidad. No se reentrenó el modelo ni se alteraron

  hiperparámetros; la visualización se completó en Fase 5.



No se modificó ni corrigió el CSV. Los pesos de negocio del briefing no se

usaron para construir observaciones inexistentes.



## Fase 5 - visualización de resultados (2025-06)

Se añadió `data/process/visualize_sales_forecast.py`. Lee el CSV de predicciones congeladas de Fase 3 y los resultados existentes de Fase 4; no reentrena ni modifica el modelo o las predicciones del holdout.

### Banda orientativa de variabilidad

Se reprodujo el procedimiento recursivo en tres validaciones de origen expansivo, con orígenes enero de 2020, enero de 2021 y enero de 2022, cada una con horizonte de 12 meses. En cada fold, el Random Forest se ajustó solo con observaciones previas al origen y con las variables e hiperparámetros guardados en `training_metadata.json`. Los meses pronosticados se añadieron al historial como predicciones, no como reales. Todos los errores de calibración son anteriores al holdout de 2024-2025.

La semiamplitud es `q90(|real - predicho|)` en los 36 errores absolutos agrupados de los folds; se representa `predicción ± semiamplitud`. Se denomina **banda orientativa de variabilidad**, no intervalo de confianza: hay solo tres folds, se agrupan horizontes de 1 a 12 y no se garantiza cobertura futura. Ningún error del holdout interviene en este cálculo.

### Lectura de diferencias y etiquetas

Un marcador rojo indica un real fuera de la banda (`|real - predicho| > semiamplitud`). Es una desviación respecto a la variabilidad de los folds, no una anomalía de negocio confirmada. La cruz morada muestra por separado la etiqueta de Fase 4: crecimiento interanual real bajo el percentil 10 de entrenamiento para el mismo mes calendario. La regla de Fase 4 marcó 3 de los 24 meses del holdout. Son criterios distintos.

El gráfico resume totales, diferencia acumulada, RMSE y K2. K2 = 1.181745 (>1) indica que el error supera la escala de error estacional ingenua en este holdout; no se presenta como mejora frente al baseline. Los totales y métricas describen este periodo; no son medidas de rentabilidad ni garantías futuras.

### Generación y limitaciones

Desde la raíz del repositorio, con las dependencias de forecasting instaladas,
ejecutar:

```powershell
uv run python -m data.process.visualize_sales_forecast
```

Se usa `-m` para ejecutar el módulo dentro del paquete: el script contiene
importaciones relativas que requieren ese contexto.

El PNG se guarda en `data/process/artifacts/sales_forecast_phase5.png`. La calibración se guarda en `forecast_variability_calibration.csv` y `forecast_variability_calibration.json`. La banda usa pocos folds históricos, no modela incertidumbre específica por horizonte y no garantiza cobertura; el gráfico cubre 24 meses de ingresos consolidados. Un punto fuera de banda no establece por sí mismo una causa comercial.

## 4. Decisiones técnicas y límites



- Confirmar/registrar un contrato de datos que documente esquema, unidades,

  consolidación y forma correcta de comparar crecimiento anual.

- Se fijó en Fase 2 un split cronológico: 96 meses de entrenamiento

  (2016–2023) y 24 de prueba (2024–2025), sin aleatorización.

- Se eligió Random Forest (no XGBoost) tras revisar dependencias, tamaño reducido y

  estrategia temporal. No se eligió ni entrenó un modelo en esta fase.

- Se definieron features causales y predicción recursiva que no consulta ingresos

  reales del período de prueba para los lags o ventanas móviles.

- Se acordó una definición operativa de caída anómala para ROC-AUC/Gini y se revisó

  reales hay; no calcularla antes de esa decisión.

- Se documentó el K2 Score con la definición aprobada basada en RMSSE; no es una

  documentada.

- Se eligió una metodología basada solo en validación de entrenamiento para la banda

  de variabilidad y una ubicación de artefactos coherente con el monorepo.



## 5. Comprobaciones de esta fase



La inspección se ejecutó con el script temporal `audit/forecast_phase1_inspect.py`

y PowerShell. El script de auditoría fue una herramienta de análisis, no un

pipeline de entrenamiento. Comprobaciones observadas: 120 filas, cinco columnas,

120 filas consolidadas, 120 meses únicos y consecutivos, cero fechas fuera del

primer día, cero vacíos, cero ingresos no positivos y conversiones numéricas

correctas. Las sumas anuales y desviaciones estacionales se resumen en la

sección 3. No se ejecutaron pruebas unitarias del futuro pipeline ni se entrenó

modelo en Fase 1.



Comandos/herramientas usados: PowerShell `Get-Content`, `Import-Csv`,

`Get-ChildItem` y `Select-String`; script de inspección ejecutado con el Python

del entorno seleccionado (`services/api/.venv/Scripts/python.exe`).



## 6. Conclusión de Fase 1



El CSV está en la ruta esperada, tiene el volumen temporal esperado y pasa las

validaciones estructurales examinadas. La señal exploratoria contiene tendencia

creciente y estacionalidad clara, especialmente en enero, febrero y agosto. Aún

no se puede afirmar que el patrón anual sea exactamente determinista ni que la

fuente esté respaldada por un contexto de datos formal. La próxima fase debe

preparar una estrategia temporal reproducible, que quedó fijada en la Fase 2.



## 7. Fase 2 — preparación causal (completada)



### 7.1. Módulo y contrato de preparación



Se añadió `data/process/sales_forecast.py`, que carga el CSV original sin modificarlo, filtra `business_line=consolidated`, convierte fechas y campos numéricos, ordena por mes y falla explícitamente ante columnas faltantes, nulos, duplicados, ingresos no positivos, fechas que no sean inicio de mes, cantidad distinta de 120 o discontinuidad entre enero de 2016 y diciembre de 2025. Los conteos de filas de origen no se reducen al crear features; las primeras filas pueden tener `NaN` en lags porque aún no existe suficiente historia.



El módulo construye año, mes, trimestre, tendencia temporal (índice 0-based desde el inicio de la serie), seno/coseno del mes, lags de ingresos 1/2/3/6/12, medias móviles de 3/6/12 y desviación estándar móvil de 12 meses. “Lag 1” de enero significa el ingreso conocido de diciembre anterior. Cada ventana aplica primero el desplazamiento de una observación: por tanto, la fila de un mes nunca incluye el ingreso objetivo de ese mismo mes.



Las columnas de contratos activos y valor medio del contrato se validan como datos de origen, pero no entran en `build_features`: el CSV no acredita que sus valores futuros estén disponibles cuando se emite una predicción. Esta decisión evita usar de forma inadvertida información futura. La lista de columnas de predicción contiene únicamente calendario y antecedentes de ingresos.



### 7.2. Split temporal y uso recursivo



`temporal_split` fija entrenamiento en 2016-01–2023-12 (96 observaciones) y prueba en 2024-01–2025-12 (24 observaciones). No hay aleatorización y los meses no se solapan. Se separan los meses originales antes de descartar o tratar valores iniciales no disponibles por lags; el tamaño nominal del test continúa siendo 24.



Para uso futuro, `make_recursive_features` crea una fila para el mes objetivo a partir de una secuencia explícita de al menos 12 ingresos anteriores. El llamador debe iniciar esa secuencia con los ingresos reales hasta diciembre de 2023 y, mes a mes en prueba, agregar la predicción previa, nunca la observación real del mes de prueba. El helper no recibe el DataFrame de test ni accede al CSV. La prueba automatizada verifica que la fila del segundo mes utiliza la predicción indicada como lag 1 y el último ingreso histórico como lag 2. No se entrenó ningún predictor ni se calculó predicción alguna en esta fase.



### 7.3. Comparación interanual del mismo mes



Se añadió `year_over_year_growth`, que compara cada mes con el mismo mes del año precedente (por ejemplo, enero de 2024 con enero de 2023), separando esta tasa de la variación de sumas anuales de la sección 3.3. La media de las doce tasas mensuales de cada año fue:



| Año de comparación | Promedio de tasas YoY mensuales |

|---:|---:|

| 2017 | +6,93 % |

| 2018 | +0,78 % |

| 2019 | +6,75 % |

| 2020 | +1,46 % |

| 2021 | +7,64 % |

| 2022 | +0,60 % |

| 2023 | +7,16 % |

| 2024 | +2,82 % |

| 2025 | +6,22 % |



Esta comparación por mismo mes muestra una alternancia aproximada de tasas altas/bajas en 2017–2023, aunque no idéntica a 7 %/1 %. En 2024 el promedio no alcanza 7 %, y 2025 tampoco es exactamente 1 %; no se debe extrapolar una alternancia determinista. Promedios de tasas mensuales no son lo mismo que tasa calculada sobre ingresos anuales agregados. Como resumen adicional (promedio de observaciones YoY por mes calendario en 2017–2025), los valores estuvieron entre +3,79 % (octubre) y +5,28 % (agosto); este promedio mezcla años altos y bajos, no constituye una tendencia aislada de temporada.



### 7.4. Pruebas y resultado



Se añadió `data/process/test_sales_forecast_phase2.py`. Las cuatro pruebas verifican la carga y el split 96/24 con límites exactos, nombres de features y exclusión de campos de negocio/objetivo, lags y medias móviles calculados solo con meses anteriores, funcionamiento recursivo con una predicción explícita y fórmula de YoY contra el mismo mes del año previo. Resultado observado:



```text

python -m pytest data/process/test_sales_forecast_phase2.py -q

4 passed

```



Durante la primera ejecución, una comparación exacta de dos promedios flotantes falló por una diferencia de representación menor que 0,000000001; se cambió a una comparación con tolerancia (`pytest.approx`). También hubo un error transitorio al editar imports con saltos de línea en PowerShell; se corrigió y la suite final pasó. La prueba demuestra la interfaz del helper (solo consume los ingresos que se le proporcionan), no ejecuta ni valida un entrenamiento o rollout completo de 24 meses.



### 7.5. Límites y transición a la siguiente fase



La Fase 2 quedó cerrada con validación de datos, features, split fijo, cálculo interanual mensual y salvaguardas de preparación recursiva. En aquel cierre se dejaron para fases posteriores la decisión de entorno y los asuntos de evaluación/anomalías; se resolvieron/documentaron en las fases siguientes.


## Fase 3 — Random Forest y forecast recursivo

Se seleccionó `RandomForestRegressor` de scikit-learn con `random_state=42`, 300 árboles, profundidad máxima 5, `min_samples_split=4`, `min_samples_leaf=2` y `max_features=0.8`. La configuración conservadora evita una búsqueda de hiperparámetros guiada por el período holdout. Del período 2016–2023 hay 96 meses; las variables causales requieren 12 meses de historia y quedan 84 observaciones objetivo para ajustar el estimador (enero 2017–diciembre 2023).

El pronóstico se genera secuencialmente para los 24 meses de enero de 2024 a diciembre de 2025. La historia de cada iteración contiene los ingresos reales del entrenamiento y las predicciones previas; nunca se incorporan ingresos reales del período de test al ajuste ni a las variables recursivas. Las pruebas confirman además que multiplicar los valores reales de 2024–2025 no modifica las predicciones.

Artefactos reproducibles en `data/process/artifacts/`: `sales_random_forest.joblib`, `sales_forecast_predictions.csv`, `feature_importance.csv` y `training_metadata.json`. La variable de mayor importancia impurity-based fue `revenue_lag_12` (~0,753), seguida por `month` (~0,063) y `revenue_roll_mean_12` (~0,045). Esta importancia no es causal y puede distorsionarse por la correlación entre retardos y promedios móviles.

La selección de Random Forest y la configuración se documentan en `data/process/PHASE3_RANDOM_FOREST.md`; el entrenamiento está implementado en `train_sales_forecast.py`. Se conservó el modelo y sus predicciones congeladas al completar las fases siguientes.

## Fase 4 — evaluación del holdout

`evaluate_sales_forecast.py` lee las predicciones congeladas y calcula métricas; no vuelve a ajustar el modelo. Verifica que existan exactamente los 24 meses esperados y evalúa regresión, cambio de distribución de features (PSI), ranking de riesgo de caída (ROC-AUC/Gini) y K2 definido operativamente como RMSSE estacional. Los resultados completos están en `artifacts/evaluation_report.json`, `evaluation_report.md`, `psi_by_feature.csv` y `anomaly_risk_evaluation.csv`.

### Resultados verificados

| Métrica | Resultado | Qué indica y qué no indica |
|---|---:|---|
| MSE | 3812985067.1854653 USD² | Media de los errores al cuadrado; penaliza más los errores grandes y queda en unidades cuadradas. |
| RMSE | 61749.37301046437 USD | Raíz del MSE, en unidades de ingreso; resume el tamaño del error, no la dirección. |
| RMSE / ingreso medio real | 6.436495578851573% | RMSE dividido por el ingreso medio del holdout (959363.2474999999 USD). No es una probabilidad ni un porcentaje de meses correctos. |
| ROC-AUC | 0.5714285714285714 | Capacidad de ordenar positivos sobre negativos para la etiqueta de riesgo elegida; 0.5 equivale a azar en interpretación idealizada. |
| Gini | 0.1428571428571428 | `2 × ROC-AUC − 1`; resume el mismo ranking, no es una segunda evidencia independiente. |
| Nexova K2 (RMSSE) | 1.181744769252833 | Raíz del MSE holdout dividido por el MSE de diferencias estacionales de 12 meses en entrenamiento. Mayor que 1: el error excede la escala de referencia estacional naïve. |

K2 es el nombre operativo del proyecto para esta definición aprobada de RMSSE,
no una métrica universal llamada K2. El valor **no demuestra mejora frente al
baseline estacional naïve**; con esta definición queda por encima de su escala
de error. No debe denominarse exactitud ni probabilidad.

La etiqueta de anomalía de Fase 4 es crecimiento YoY real por debajo del
percentil 10 histórico para el mismo mes calendario; hay **3 positivos entre 24**.
ROC-AUC y Gini se basan en solo tres casos positivos y tienen incertidumbre alta;
son descriptivos, no una validación estadística robusta. La regla es operativa,
no un umbral de pérdida aprobado por el negocio.

PSI compara distribuciones de features calculadas sobre entrenamiento con las
features recursivas del holdout. La implementación usa hasta diez bins definidos
por cuantiles de entrenamiento, límites infinitos y piso epsilon para evitar
logaritmos de cero. PSI alto indica cambio de distribución bajo este esquema,
no diagnostica su causa ni prueba por sí solo degradación predictiva. Se omiten
los índices monótonos `year` y `trend` porque su desplazamiento cronológico es
esperable. Los valores de la tabla son los del artefacto congelado:

| Feature | PSI | Feature | PSI |
|---|---:|---|---:|
| `revenue_roll_mean_12` | 12.267849060308903 | `revenue_roll_mean_6` | 10.896828069482316 |
| `revenue_roll_mean_3` | 9.426190484838484 | `revenue_lag_12` | 8.332302495132154 |
| `revenue_lag_2` | 8.168126867711694 | `revenue_lag_3` | 8.107061441410115 |
| `revenue_lag_6` | 8.105511607138943 | `revenue_lag_1` | 6.86778120421177 |
| `revenue_roll_std_12` | 4.152021202950776 | `month_cos` | 0.0 |
| `month_sin` | 0.0 | `quarter` | 0.0 |
| `month` | 0.0 | | |

Los PSI de features de ingresos son grandes bajo la convención de bins usada;
no se interpretan como evidencia automática de error de código. Reflejan una
diferencia marcada entre el historial de entrenamiento y la distribución
recursiva posterior. Las guías heurísticas habituales de umbral PSI no son
universales y estos valores extremos, con 24 meses de comparación, requieren
investigar estabilidad antes de un uso operativo.

## Fase 5 — visualización y banda de variabilidad

`visualize_sales_forecast.py` lee el CSV congelado, el informe de evaluación y
las filas de anomalía, y guarda `data/process/artifacts/sales_forecast_phase5.png`.
La línea real muestra ingresos observados del holdout; la línea predicha muestra
el pronóstico recursivo fijado en Fase 3. La banda centrada en la predicción usa
el percentil empírico 90 de errores absolutos recursivos de tres folds de
validación anteriores al holdout, con 12 meses por fold y 36 errores agrupados.
Su semianchura congelada es 85365.16010281869 USD (aprox. ±85,365 USD). Es una banda
orientativa de variabilidad, no un intervalo de confianza: no tiene cobertura
probabilística garantizada ni es específica del horizonte mensual.

Los marcadores de desviación señalan reales fuera de la banda (3 en el holdout).
No son automáticamente anomalías de negocio: la banda es una referencia
empírica y no explica causas. Es distinto de la etiqueta de Fase 4, que identifica
3 meses con crecimiento YoY bajo un umbral estacional de entrenamiento. La
coincidencia en el conteo no hace iguales las definiciones ni necesariamente los
meses señalados.

## Fase 6 — pruebas automatizadas (completada)

La validación combinada de Fases 2, 3, 4 y 6 terminó con **25 passed**; la suite
individual Phase 6 contiene **10 passed**. La cobertura incluye split y fechas,
warm-up y filas de entrenamiento, validación de datos, features causales,
recursión, independencia frente a valores reales del holdout, semilla y
reproducibilidad contra el artefacto congelado, evaluación sobre el holdout,
calibración pre-holdout y conservación de artefactos congelados mediante hashes.
Las pruebas con salidas escriben en directorios temporales.

Desde la raíz del repositorio, con el Python del entorno seleccionado:

```powershell
python -m pytest data/process/test_sales_forecast_phase2.py data/process/test_sales_forecast_phase3.py data/process/test_sales_forecast_phase4.py data/process/test_sales_forecast_phase6.py -q
python -m pytest data/process/test_sales_forecast_phase6.py -q
```

## Fase 7 — documentación y reproducción

### Mapa de archivos

| Ruta | Responsabilidad |
|---|---|
| `data/raw/nexova_sales.csv` | Fuente original; se mantiene sin editar. |
| `data/process/sales_forecast.py` | Validación/carga, split, features causales, YoY y helper recursivo. |
| `data/process/train_sales_forecast.py` | Ajusta el RF fijo, genera pronóstico recursivo y artefactos de Fase 3. |
| `data/process/evaluate_sales_forecast.py` | Evalúa predicciones existentes y persiste reporte/PSI/anomalías. |
| `data/process/visualize_sales_forecast.py` | Genera gráfico y resumen de calibración sin reentrenar el artefacto final. |
| `data/process/test_sales_forecast_phase{2,3,4,6}.py` | Pruebas unitarias e integración del pipeline por fase. |
| `data/process/artifacts/` | Modelo, predicciones, metadatos, evaluación, calibración y gráfico existentes. |

El entrenamiento usa calendario (`year`, `month`, `quarter`, `trend`, seno y
coseno del mes) y valores pasados de ingresos (lags 1/2/3/6/12, medias móviles
3/6/12 y desviación móvil 12). Se excluyen `active_contracts` y
`avg_contract_value_usd`: no hay garantía de que esos campos futuros estén
disponibles al emitir un pronóstico. También se excluye la etiqueta actual de
ingresos de las features. Las primeras 12 filas carecen de historia completa;
por eso se ajusta con enero de 2017–diciembre de 2023 (84 objetivos), aunque el
periodo nominal de entrenamiento siga teniendo 96 meses.

Los artefactos de Fase 3 son `sales_random_forest.joblib`,
`sales_forecast_predictions.csv`, `feature_importance.csv` y
`training_metadata.json`. Evaluación añade `evaluation_report.json`,
`evaluation_report.md`, `psi_by_feature.csv` y `anomaly_risk_evaluation.csv`;
Fase 5 añade el PNG y archivos de calibración. El conjunto versionado/congelado
debe tratarse como salida de referencia; no lo sobrescribas al repetir tests.

### Pasos para reproducir

1. Usa Windows y un Python compatible con las dependencias declaradas. La
  implementación fue verificada con Python 3.14.6; `.python-version` y
  `pyproject.toml` documentan el entorno fijado del repositorio. Comprueba
  versiones compatibles si utilizas otro Python.
2. Desde la raíz, crea/activa un entorno virtual `.venv` (por ejemplo,
  `uv venv --python 3.14`). No reutilices el entorno de otro servicio si sus
  dependencias interfieren.
3. Instala las dependencias de forecasting con el comando verificado:

  ```powershell
  uv pip install --python .venv\Scripts\python.exe -r data/process/requirements.txt
  ```

4. Para volver a entrenar explícitamente —esto **sobrescribe** los artefactos
  de Fase 3 y por ello no es necesario para evaluar o visualizar los resultados
  congelados— ejecuta desde la raíz:

  ```powershell
  .venv\Scripts\python.exe -m data.process.train_sales_forecast
  ```

5. Para recalcular evaluación de los artefactos existentes, ejecuta:

  ```powershell
  uv run python -m data.process.evaluate_sales_forecast
  ```

  `uv run` usa el entorno del proyecto, que debe incluir las dependencias del
  pipeline; si solo se instaló el requirements específico en `.venv`, usa
  `.venv\Scripts\python.exe -m data.process.evaluate_sales_forecast`. El
  módulo no reentrena, pero guarda/sobrescribe reporte, PSI y anomalías. Para
  preservar los resultados congelados, lee los informes existentes en vez de
  ejecutarlo.
6. Para regenerar únicamente el gráfico y calibración, sin reentrenar, usa el
  comando verificado:

  ```powershell
  uv run python -m data.process.visualize_sales_forecast
  ```

  `-m` importa y ejecuta el archivo como módulo dentro de `data.process`;
  es necesario porque el script emplea imports relativos. El visualizador lee
  artefactos existentes y escribe sus salidas de gráfico/calibración.
7. Ejecuta las dos órdenes de pytest de la sección Fase 6. Para el mismo
  intérprete elegido explícitamente, antepone a cada una
  `.venv\Scripts\python.exe -m pytest` en lugar de `python -m pytest`. En
  este proyecto, `uv run` usa el entorno declarado en `pyproject.toml`; instala
  allí las dependencias de `data/process/requirements.txt` si ejecutas el
  comando de pytest con `uv run`.

### Problemas resueltos y límites finales

El warm-up de 12 meses se trató como disponibilidad de historia, no como una
razón para mover los límites del split. La recursión usa reales solo hasta
diciembre de 2023 y después añade predicciones; las pruebas de perturbación del
holdout comprueban que sus reales no contaminan el forecast ni la calibración.
Para comparar errores se definió K2 explícitamente con RMSSE estacional naïve
de lag 12, calculado con 84 diferencias de entrenamiento. Para la banda se
eligieron folds recursivos pre-holdout porque los errores del propio test no
deben calibrar una banda que luego se presenta sobre ese test. Se usa `python
-m`/`uv run ... -m` donde los imports relativos requieren el contexto del
paquete. Las dependencias se aislaron en `.venv`.

El proyecto implementa un flujo reproducible de datos mensuales consolidados,
entrenamiento, pronóstico, evaluación, visualización y tests. En este holdout,
RMSE es 6.44% del ingreso medio, pero K2=1.181745 está por encima de 1: no hay
evidencia de superioridad frente a la referencia estacional naïve. PSI indica
cambio fuerte en la distribución de varias features; ROC-AUC/Gini tienen solo
tres positivos. El dataset contiene 120 meses, el holdout 24 y el análisis
consolidado no permite valorar mix de negocio. La banda tampoco es un intervalo
de confianza. Son límites sustantivos, no detalles que una sola métrica pueda
resolver.

Posibles mejoras (no implementadas): más historia y evaluación walk-forward con
múltiples periodos; comparación explícita de pronósticos y baseline naïve por
horizonte; umbrales de desviación acordados con negocio; más datos de drivers
disponibles al origen de forecast; análisis de estabilidad y recalibración
periódica; y monitoreo operativo. El proyecto no está integrado en la API ni en
la web y no debe describirse como listo para producción.

La Fase 7 cierra la documentación de este ejercicio. No se modificaron el modelo,
los hiperparámetros, predicciones congeladas ni resultados de evaluación.
