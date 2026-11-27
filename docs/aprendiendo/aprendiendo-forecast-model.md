# Aprendiendo: predicción de ingresos mensuales de Nexova



Guía didáctica del desarrollo por fases de un sistema de *forecasting* de

ingresos. Este documento se actualizará al cerrar cada fase. **Estado actual: Fase 3 — entrenamiento y forecast recursivo completados. Fase 4 (evaluación) pendiente de autorización.
preparado un modelo ni un pipeline.



## 1. Objetivo de negocio



El propósito es estimar los ingresos mensuales consolidados de Nexova y ayudar

a dirección a reconocer desviaciones que merezcan atención. La predicción no

sustituye el criterio de Marcos ni Laura: ofrece una referencia cuantitativa

cuyo error y limitaciones deberán explicarse en términos comprensibles.



La fuente indicada es `data/raw/nexova_sales.csv`. El análisis debe conservar

el CSV original y utilizar únicamente observaciones `business_line =

consolidated`. Los porcentajes de peso de las líneas de negocio que aparecen en

el briefing son contexto aproximado, no datos mensuales, y no permiten calcular

el cambio real del mix de negocio.



## 2. Fases previstas



| Fase | Objetivo | Estado |

|---|---|---|

| 1. Exploración | Conocer arquitectura, contexto y calidad/patrones del CSV. | **Completada en esta entrega** |

| 2. Preparación | Definir validaciones, variables causales y split cronológico 96/24. | **Completada en esta entrega** |

| 3. Entrenamiento | Random Forest entrenado solo con 2016–2023; forecast recursivo 2024–2025. | **Completada en esta entrega** |

| 4. Evaluación | Calcular métricas acordadas con el período 2024–2025. | Pendiente |

| 5. Visualización | Mostrar realidad, predicción y una banda de error con método explícito. | Pendiente |

| 6. Pruebas | Verificar split, calidad, reproducibilidad y ausencia de fuga temporal. | Fases 2 y 3 completadas; evaluación pendiente |

| 7. Documentación y revisión | Consolidar decisiones, resultados y límites del sistema. | Pendiente |



No se avanzará a una fase posterior sin autorización expresa del usuario.



## 3. Fase 1 — exploración y diagnóstico



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



### 3.4. Dependencias y convenciones del proyecto



El `pyproject.toml` de la raíz no declara dependencias de ML. El manifiesto

`services/api/pyproject.toml` sí declara pandas, pero no scikit-learn, XGBoost,

Matplotlib ni NumPy de forma explícita. En el intérprete Python seleccionado

para el entorno local se comprobaron imports: pandas, NumPy y pytest disponibles;

scikit-learn, XGBoost y Matplotlib no disponibles. La disponibilidad local no

equivale a una dependencia declarada ni garantiza que el entorno de despliegue

las tenga. **No se instaló ninguna dependencia en esta fase.** Antes de la

implementación habrá que decidir en qué manifiesto/entorno corresponde

declararlas y confirmar si se necesitan todas.



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

6. **K2 Score:** no se encontró una definición en los documentos consultados;

   el barrido exploratorio del repositorio no aportó una definición aplicable.

   Su significado no se debe inventar. La implementación queda detenida hasta

   investigar/definir una fórmula y obtener aprobación expresa.



No se modificó ni corrigió el CSV. Los pesos de negocio del briefing no se

usaron para construir observaciones inexistentes.



## 4. Decisiones técnicas pendientes



- Confirmar/registrar un contrato de datos que documente esquema, unidades,

  consolidación y forma correcta de comparar crecimiento anual.

- En Fase 2, usar un split cronológico fijo: 96 meses de entrenamiento

  (2016–2023) y 24 de prueba (2024–2025), sin aleatorización.

- Elegir Random Forest o XGBoost tras revisar dependencias, tamaño reducido y

  estrategia temporal. No se eligió ni entrenó un modelo en esta fase.

- Definir features causales y predicción recursiva que no consulte ingresos

  reales del período de prueba para los lags o ventanas móviles.

- Acordar definición de caída anómala para ROC-AUC/Gini y revisar cuántos casos

  reales hay; no calcularla antes de esa decisión.

- Investigar K2 Score y solicitar aprobación para cualquier definición no

  documentada.

- Elegir una metodología respaldada por datos de entrenamiento para la banda

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

preparar una estrategia temporal reproducible, previa autorización expresa.



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



### 7.5. Límites y siguiente autorización



La Fase 2 está cerrada: validación de datos, features, split fijo, cálculo interanual mensual y salvaguardas de preparación recursiva implementados y probados. Queda pendiente la decisión de dependencias y entorno antes de entrenar, además de los asuntos de Gini/ROC-AUC, K2, caída anómala y banda de variabilidad documentados arriba. No se inició la Fase 3. Se requiere autorización expresa antes de seleccionar o ajustar modelos.


## 8. Fase 3 — Random Forest y forecast recursivo

Se seleccionó `RandomForestRegressor` de scikit-learn con `random_state=42`, 300 árboles, profundidad máxima 5, `min_samples_split=4`, `min_samples_leaf=2` y `max_features=0.8`. La configuración conservadora evita una búsqueda de hiperparámetros guiada por el período holdout. Del período 2016–2023 hay 96 meses; las variables causales requieren 12 meses de historia y quedan 84 observaciones objetivo para ajustar el estimador (enero 2017–diciembre 2023).

El pronóstico se genera secuencialmente para los 24 meses de enero de 2024 a diciembre de 2025. La historia de cada iteración contiene los ingresos reales del entrenamiento y las predicciones previas; nunca se incorporan ingresos reales del período de test al ajuste ni a las variables recursivas. Las pruebas confirman además que multiplicar los valores reales de 2024–2025 no modifica las predicciones.

Artefactos reproducibles en `data/process/artifacts/`: `sales_random_forest.joblib`, `sales_forecast_predictions.csv`, `feature_importance.csv` y `training_metadata.json`. La variable de mayor importancia impurity-based fue `revenue_lag_12` (~0,753), seguida por `month` (~0,063) y `revenue_roll_mean_12` (~0,045). Esta importancia no es causal y puede distorsionarse por la correlación entre retardos y promedios móviles.

Las cuatro métricas de evaluación acordadas no se calcularon en esta fase. Fase 4 queda pendiente de autorización explícita.