
# TP – Análisis Descriptivo Inmobiliario de CABA

Análisis descriptivo del mercado inmobiliario de la Ciudad Autónoma de Buenos Aires orientado a un modelo de inversión **Buy to Rent**.

El proyecto construye un dataset propio de publicaciones inmobiliarias de Mercado Libre, lo complementa con información geográfica de transporte público, delitos, salud y espacios verdes de CABA, y unifica todo en un único dataset analítico con KPIs de inversión a nivel publicación.

## Objetivo del proyecto

El objetivo es analizar propiedades residenciales de CABA para identificar zonas y tipologías con potencial de inversión mediante la comparación de:

- Precios de venta y alquiler.
- Precio por metro cuadrado.
- Superficie, ambientes y antigüedad.
- Expensas y amenities.
- Tipo de propiedad.
- Ubicación geográfica.
- Cercanía al transporte público.
- Presencia de espacios verdes.
- Concentración de hechos delictivos.

El análisis está orientado a un inversor que busca comprar una propiedad, alquilarla de manera tradicional y conservarla durante varios años.

## Alcance

- **Ubicación:** Ciudad Autónoma de Buenos Aires.
- **Operaciones:** venta y alquiler.
- **Propiedades principales:** departamentos, PH y casas.
- **Propiedades conservadas pero fuera del análisis residencial:** oficinas y locales.
- **Período inmobiliario:** publicaciones activas durante el scraping realizado entre el 14 y el 17 de agosto de 2026.
- **Delitos:** años 2023, 2024 y 2025.
- **Unidad de análisis inmobiliaria:** una publicación de Mercado Libre.

## Contexto macroeconómico

Los datos son una foto de agosto de 2026. Estas condiciones del mercado ayudan a leer los resultados:

| Tema | Situación | Qué implica para el análisis |
|---|---|---|
| Inflación y alquileres | Inflación de 33,4% en 12 meses a septiembre de 2026 (1,9% mensual). En el mismo período, el alquiler de un 2 ambientes en CABA subió 28,7%. | Los alquileres se publican mayormente en pesos y se ajustan; las ventas, en dólares. La rentabilidad en USD depende del tipo de cambio (ver la sensibilidad del notebook 04). |
| Precios de venta | El m² de un departamento en CABA ronda USD 2.484, con una suba de 1,4% en 2026. | Con alquileres que suben y precios estables, la rentabilidad bruta está en máximos de casi 25 años (5,7% según Zonaprop). |
| Oferta de alquileres | Desde la derogación de la Ley de Alquileres (DNU 70/2023), la oferta pasó de unas 4.000 a cerca de 17.000 unidades. Una unidad tarda de 30 a 60 días en alquilarse. | Hay que contar vacancia: la rentabilidad neta la incluye en los tres escenarios de costos. |
| Crédito hipotecario | Solo el 17% de las escrituras de CABA de agosto de 2026 tuvo hipoteca (4 puntos menos que un año antes). | La compra depende del ahorro en dólares, lo que limita la demanda al revender (liquidez). |
| Impuestos | Desde 2026, el alquiler de vivienda está exento de Ganancias para personas humanas (Ley 27.802 y Decreto 406/2026). Sellos en CABA: 2,7% hasta $226,1 millones y 3,5% por encima. | El escenario base no descuenta Ganancias. Un inversor no accede a la exención de sellos por vivienda única. |

Por eso los resultados describen un mercado en transición: si vuelve el crédito o se estabiliza la oferta de alquileres, la relación entre precio y renta puede cambiar.

Fuentes: [INDEC vía Finanzas Digital (13/10/2026)](https://finanzasdigital.com/inflacion-argentina-septiembre-2026-indec-ipc-acumulada/), [Zonaprop, Index CABA septiembre 2026](https://www.zonaprop.com.ar/blog/wp-content/uploads/2026/10/INDEX_CABA_REPORTE_2026-09.pdf), [iProfesional, rentabilidad récord (20/07/2026)](https://www.iprofesional.com/realestate/460148-la-rentabilidad-que-deja-alquilar-un-departamento-toco-un-record-en-casi-25-anos), [iProfesional, oferta récord de alquileres (06/09/2026)](https://www.iprofesional.com/realestate/463807-record-de-oferta-de-alquileres-en-caba-que-pasara-con-los-precios), [iProfesional, días para alquilar (2025)](https://www.iprofesional.com/realestate/426144-cuantos-dias-tarda-en-alquilarse-un-departamento-en-caba), [elDiarioAR, exención de Ganancias (01/06/2026)](https://www.eldiarioar.com/economia/gobierno-reglamento-exenciones-ganancias-alquileres-vivienda-venta-inmuebles_1_13266176.html), [Colegio de Escribanos, Código Fiscal 2026](https://www.colegio-escribanos.org.ar/noticias/2025_12_19-Codigo-Fiscal-2026-INFORME.pdf).

## Cambios respecto de la primera entrega

La segunda entrega consolida lo desarrollado en el TP1 y agrega una etapa reproducible de calidad, EDA y análisis multivariado:

| Aspecto | Incorporación en el TP2 |
|---|---|
| Dataset analítico | Se parte de `dataframefinal.csv` (91 columnas) y se genera `dataframe_limpio.csv` (114 columnas). |
| Faltantes | Se documenta su cobertura y se aplican tratamientos explícitos únicamente cuando existe una regla acordada; cada imputación queda identificada. |
| Valores anómalos | Se distinguen datos inválidos, valores sospechosos y extremos plausibles. No se eliminan publicaciones automáticamente. |
| Duplicados | Se identifican grupos seguros y probables sin borrar filas del archivo original. |
| EDA | Se integran el análisis cualitativo, cuantitativo y las relaciones exploratorias entre variables. |
| Profundización | Se incorporan outliers contextuales, análisis de sensibilidad, modelos ajustados y escenarios Buy to Rent. |
| Reproducibilidad | Los cuatro notebooks quedan numerados y conectados mediante entradas y salidas explícitas. |

## Preguntas e hipótesis de trabajo

El análisis busca responder cuatro grupos de preguntas:

- **Descriptivas:** ¿cómo se distribuyen los precios, superficies, tipologías, ambientes y amenities en CABA?
- **Diagnósticas:** ¿qué características del inmueble y del entorno se relacionan con las diferencias de precio y rentabilidad?
- **Predictivas:** ¿qué variables permiten construir un precio de referencia para comparar publicaciones?
- **Prescriptivas:** ¿qué barrios y segmentos presentan condiciones más atractivas para una estrategia Buy to Rent bajo distintos supuestos?

Las hipótesis iniciales del proyecto son:

| Hipótesis | Formulación resumida |
|---|---|
| H1 | Los barrios del sur y oeste presentan mayor rentabilidad estimada que los barrios premium del norte. |
| H2 | Amenities y cochera incrementan proporcionalmente más el precio de venta que el alquiler y pueden reducir la rentabilidad relativa. |
| H3 | Las unidades de uno y dos ambientes presentan mayor rentabilidad estimada que las unidades de tres o más ambientes. |
| H4 | Una mayor distancia al subte se relaciona con un menor precio por m², incluso comparando dentro de un mismo barrio. |
| H4b | Una mayor accesibilidad a colectivos se relaciona con diferencias de precio dentro de una misma zona. |
| H5 | Una mayor concentración de delitos se relaciona con menores precios por m², controlando por características y barrio. |
| H6 | Las publicaciones de particulares tienen mayor probabilidad de aparecer subvaluadas que las de inmobiliarias. |
| H7 | El acceso a espacios verdes tiene una relación diferencial con el precio de las unidades familiares de tres o más ambientes. |
| H8 | La distancia al centro de salud más cercano se relaciona con diferencias en el precio de venta por m². |

Estas hipótesis se consideran puntos de partida. Los notebooks distinguen evidencia descriptiva, asociaciones ajustadas y resultados no concluyentes; no se interpretan como relaciones causales.

## Principales resultados del TP2

- El dataset limpio conserva las **55.582 publicaciones residenciales** y amplía la base de 91 a **114 variables**, sin modificar las columnas originales.
- El barrio, la superficie, el tipo de propiedad y el nivel de amenities concentran gran parte de las diferencias observadas en los precios publicados.
- Los valores extremos no se eliminan de manera automática: los errores o datos imposibles se apartan de los cálculos correspondientes y los extremos plausibles se conservan para evitar sesgar la oferta premium.
- En los modelos ajustados no aparece evidencia clara de una prima por cercanía al subte. La concentración de delitos presenta una asociación negativa con los precios, pero su magnitud es sensible a los extremos y no debe interpretarse causalmente.
- El efecto diferencial de los espacios verdes sobre las unidades familiares no resulta robusto entre especificaciones.
- Los escenarios Buy to Rent son exploratorios y dependen de la cobertura del alquiler tradicional, las expensas, la vacancia, el mantenimiento y el tipo de cambio. No constituyen una recomendación de inversión.

## Flujo general de datos

```mermaid
flowchart LR
    A[Mercado Libre Inmuebles] --> B[Scraping de listados]
    B --> C[Extracción de cada publicación]
    C --> D[Dataset inmobiliario crudo]
    D --> E[Procesamiento y controles de calidad]

    F[Buenos Aires Data] --> G[Datasets públicos crudos]
    G --> H[Limpieza y normalización]

    E --> I[Dataset inmobiliario procesado]
    H --> J[Transporte, delitos, salud y espacios verdes]
    I --> U[01 Unificación y cálculo de KPIs]
    J --> U
    U --> V[dataframefinal.csv]
    V --> Q[02 Calidad y limpieza]
    Q --> L[dataframe_limpio.csv]
    L --> K[03 EDA descriptivo]
    L --> M[04 Outliers y análisis multivariado]
    L --> N[05 Análisis de hipótesis]
    N --> O[Indicadores para el dashboard]
```

## Estructura del repositorio

```text
.
├── README.md
├── .gitignore
├── src/
│   ├── tipo_cambio.py
│   ├── indicadores.py
│   └── modelos.py
├── tests/
│   ├── test_tipo_cambio.py
│   ├── test_pipeline_tipo_cambio.py
│   └── test_indicadores_modelos.py
├── scrapper/
│   ├── mercadolibre_scraping_completo.py
│   └── MercadoLibre_scraper.py
├── data/
│   ├── raw/
│   │   ├── delitos_2023.csv
│   │   ├── delitos_2024.csv
│   │   ├── delitos_2025.csv
│   │   ├── espacio_verde_publico.csv
│   │   ├── estaciones-de-metrobus.csv
│   │   ├── estaciones_de_subte.csv
│   │   ├── estaciones_ferroviarias.csv
│   │   ├── hospitales.csv
│   │   ├── paradas-de-colectivo.csv
│   │   └── enlace_output_scrappeo_MeLi
│   ├── processing codes/
│   │   ├── limpiar_colectivos.py
│   │   ├── limpiar_espacios_verdes.py
│   │   ├── limpiar_hospitales.py
│   │   ├── limpiar_metrobus.py
│   │   ├── limpiar_subte.py
│   │   ├── limpiar_trenes.py
│   │   ├── procesar_datos_Mercadolibre.py
│   │   └── unificar_delitos.py
│   └── processed/
│       ├── colectivos_limpio.csv
│       ├── delitos_2023_2025_unificado_limpio.csv
│       ├── espacios_verdes_familiares_limpio.csv
│       ├── hospitales_limpio.csv
│       ├── mercadolibre_caba_procesado.csv
│       ├── metrobus_limpio.csv
│       ├── subte_limpio.csv
│       ├── tren_limpio.csv
│       ├── dataframefinal.csv
│       ├── dataframe_limpio.csv
│       ├── enlace_scrappeo_procesado_MeLi
│       ├── indicadores_avisos.csv
│       ├── indicadores_barrio.csv
│       ├── rentabilidad_segmentos.csv
│       └── resultados_hipotesis.csv
├── notebooks/
│   ├── 01_unificacion.ipynb
│   ├── 02_calidad_y_limpieza.ipynb
│   ├── 03_eda_inicial.ipynb
│   ├── 04_outliers_y_analisis_multivariado.ipynb
│   └── 05_analisis_de_hipotesis.ipynb
└── extras/
    ├── propuesta_negocio_descriptiva.pdf
    └── resumen_calidad_mercadolibre_caba.pdf
```

- `data/raw/`: archivos originales sin modificar.
- `data/processing codes/`: scripts utilizados para limpiar y transformar los datos.
- `data/processed/`: archivos preparados para el análisis.
- `src/`: lógica estable que usan los scripts y notebooks: el tipo de cambio (`tipo_cambio.py`), la base analítica, la rentabilidad por segmento, los costos de la inversión y el índice de priorización (`indicadores.py`), y el modelo de precio de referencia con su validación (`modelos.py`).
- `tests/`: tests automáticos de `src/` (`python -m pytest tests`).
- `scrapper/`: código utilizado para obtener las publicaciones inmobiliarias.
- `notebooks/`: análisis sobre el dataset unificado (EDA inicial, limpieza de faltantes y duplicados, y análisis multivariado).
- `extras/`: documentación complementaria y reportes de calidad.
- `data/processed/dataframefinal.csv`: salida de `notebooks/01_unificacion.ipynb` (91 columnas).
- `data/processed/dataframe_limpio.csv`: salida de `notebooks/02_calidad_y_limpieza.ipynb` (114 columnas). **Está versionado** y es la entrada de los notebooks 03 y 04.

## Fuentes de datos

### Mercado Libre Inmuebles

El dataset inmobiliario fue construido mediante un scraper propio sobre las publicaciones públicas de [Mercado Libre Inmuebles](https://inmuebles.mercadolibre.com.ar/).

La búsqueda se dividió por:

- Operación: venta y alquiler.
- Tipo: departamento, PH, casa, oficina y local.
- Barrio de CABA.
- Página de resultados.

Esta división permitió recorrer una mayor cantidad de publicaciones que utilizando una única búsqueda general.

### Buenos Aires Data

Los datasets geográficos complementarios fueron descargados del portal oficial [Buenos Aires Data](https://data.buenosaires.gob.ar/):

- [Estaciones de subte](https://data.buenosaires.gob.ar/dataset/subte-estaciones)
- [Estaciones ferroviarias](https://data.buenosaires.gob.ar/dataset/estaciones-ferrocarril)
- [Estaciones de Metrobus](https://data.buenosaires.gob.ar/dataset/metrobus)
- [Paradas de colectivo](https://data.buenosaires.gob.ar/dataset/colectivos-paradas)
- [Delitos](https://data.buenosaires.gob.ar/dataset/delitos)
- [Espacios verdes](https://data.buenosaires.gob.ar/dataset/espacios-verdes)
- [Hospitales](https://data.buenosaires.gob.ar/dataset/hospitales)

Los archivos guardados en el repositorio son una copia de los datos utilizados en el trabajo. Las fuentes oficiales pueden actualizarse posteriormente.

## Extracción de Mercado Libre

El scraping se realizó en dos etapas.

### 1. Descubrimiento de publicaciones

Se recorrieron las páginas de resultados y se guardaron los enlaces, identificadores y datos básicos de cada publicación.

### 2. Extracción del detalle

Se ingresó individualmente a cada publicación para obtener la mayor cantidad posible de atributos estructurados y textuales.

Entre las variables obtenidas se encuentran:

- Identificador y enlace.
- Operación.
- Tipo de propiedad.
- Precio y moneda.
- Expensas.
- Dirección y barrio publicado.
- Latitud y longitud.
- Ambientes, dormitorios y baños.
- Superficie total y cubierta.
- Antigüedad.
- Estado del inmueble.
- Vendedor.
- Amenities y características.
- Título y descripción.
- Fecha y hora del scraping.
- Tipo de cambio del día del scraping (`TC_Scraping`, `Fecha_TC_Scraping`, `Fuente_TC_Scraping`).

### Tipo de cambio del día

El orquestador agrega a cada aviso la cotización del dólar blue (precio de venta) vigente el día en que se scrapeó, con la lógica de [`src/tipo_cambio.py`](src/tipo_cambio.py):

- Consulta [DolarApi](https://dolarapi.com/v1/dolares/blue) **una vez por día de scraping** y reutiliza el valor para todos los avisos de ese día. Si el scraping dura varios días, cada aviso queda con el dólar de su día.
- Si DolarApi no responde, usa el último dato de [ArgentinaDatos](https://api.argentinadatos.com/v1/cotizaciones/dolares/blue).
- Si ninguna responde, **el scraping sigue**: los avisos quedan con `N/A`, se registra en el log y el procesamiento los completa después con la serie histórica. Vuelve a intentar a los 10 minutos.
- Un CSV de una corrida anterior, sin estas columnas, se actualiza al esquema nuevo antes de seguir agregando avisos.

### Controles del scraper

El scraper implementa:

- Deduplicación por `Item_ID`.
- Control adicional de duplicados por enlace.
- Guardado incremental cada 50 publicaciones.
- Checkpoint para continuar una ejecución interrumpida.
- Registro de errores y URLs fallidas.
- Pausas entre solicitudes.
- Detección de captcha o bloqueo.
- Detención segura ante demasiados errores consecutivos.
- Escritura atómica para reducir el riesgo de archivos corruptos.

No se intentan evadir captchas ni mecanismos de protección del sitio.

### Resultado de la extracción

El dataset crudo contiene:

- **65.846 publicaciones**
- **56.553 publicaciones de venta**
- **9.293 publicaciones de alquiler**
- **186 columnas** (las corridas nuevas agregan 3 de tipo de cambio: 189)
- **0 identificadores duplicados**
- **0 enlaces duplicados**

Por tipo de propiedad:

- Departamento: 45.222
- PH: 6.060
- Casa: 4.300
- Oficina: 4.329
- Local: 5.935

Para el análisis Buy to Rent residencial se consideran principalmente los **55.582 departamentos, PH y casas**. Las oficinas y los locales se conservan, pero quedan fuera del alcance principal.

El **dataset procesado** (`data/processed/mercadolibre_caba_procesado.csv`, 33 MB) está incluido en el repositorio.

El **dataset crudo**, con las 186 columnas originales, se distribuye por Google Drive porque excede el límite práctico de GitHub:

- [Dataset crudo de Mercado Libre](https://drive.google.com/file/d/1l2Xgb9xCmSfVGG7uE_JkXDR-RuG6U4LW/view?usp=drive_link)

## Limpieza del dataset inmobiliario

El archivo crudo fue procesado con [`procesar_datos_Mercadolibre.py`](data/processing%20codes/procesar_datos_Mercadolibre.py).

El procesamiento:

- Conserva las 65.846 publicaciones.
- Selecciona 56 variables relevantes y conserva las 3 de tipo de cambio.
- Genera un dataset final de 70 columnas.
- Completa el tipo de cambio de los avisos que no lo tienen (los del scraping de agosto de 2026, anterior a esas columnas, o los de días en que la API no respondió) con la serie histórica de ArgentinaDatos para su `Fecha_Scraping`. `Fuente_TC_Scraping` indica qué avisos se completaron así. Si hay que completar y no hay conexión, el script se detiene.
- No convierte precios entre monedas en esta etapa (la conversión se realiza en la unificación).
- No elimina publicaciones por ser outliers.
- No modifica precios, superficies o coordenadas originales.
- Conserva los textos originales necesarios para auditoría.
- Completa con `0` los valores faltantes de 18 variables binarias de amenities.
- Agrega controles de calidad y motivos de anomalía.

En las variables binarias de amenities:

- `1` significa que la característica fue detectada.
- `0` significa que no fue informada o no fue detectada.

Por lo tanto, un `0` no garantiza que el inmueble no tenga esa característica.

### Flags de calidad

Se incorporaron los siguientes controles:

- `Flag_Precio_Anomalo`
- `Flag_Operacion_Anomala`
- `Flag_Tipo_Propiedad_Anomalo`
- `Flag_Superficie_Anomala`
- `Flag_Ambientes_Anomalo`
- `Flag_Coordenadas_Anomalas`
- `Flag_Expensas_Anomalas`
- `Flag_Amenities_Anomalos`
- `Flag_Faltantes_Criticos`
- `Flag_Anomalia_General`
- `Motivo_Anomalia`

Estos flags permiten identificar registros que requieren revisión sin eliminarlos automáticamente.

## Limpieza de transporte público

Los datasets de transporte se normalizaron para obtener nombres de columnas compatibles, coordenadas separadas y variables de control.

### Subte

Archivo original: 90 estaciones.

Mejoras realizadas:

- Conversión de geometría WKT a `Latitud` y `Longitud`.
- Normalización del nombre de estación y línea.
- Control de coordenadas fuera de rango.
- Control de duplicados.
- Conservación de las 90 estaciones.

### Ferrocarril

Archivo original: 301 estaciones.

Mejoras realizadas:

- Conversión de geometría WKT a coordenadas.
- Normalización de nombres de líneas y ramales.
- Conservación de barrio, comuna y localidad.
- Creación de `Flag_Fuera_CABA`.
- Control de coordenadas y duplicados.

El archivo incluye estaciones del AMBA. No se eliminaron las estaciones externas: 231 quedaron marcadas como fuera del rectángulo de control de CABA y 70 quedaron dentro.

### Metrobus

Archivo original: 390 estaciones.

Mejoras realizadas:

- Normalización de latitud y longitud.
- Unión de las columnas `L1` a `L6`.
- Conservación del sentido de cada línea.
- Reconstrucción de direcciones faltantes.
- Creación de identificadores técnicos.
- Control de coordenadas y duplicados.

Se conservaron las 390 filas.

### Colectivos

Archivo original: 6.962 paradas.

Mejoras realizadas:

- Conversión de coordenadas con coma decimal.
- Unión y deduplicación de líneas.
- Conservación de los sentidos de circulación.
- Reconstrucción de direcciones faltantes.
- Normalización de comunas.
- Control de coordenadas anómalas.
- Marcado de posibles duplicados.

Las filas sospechosas fueron marcadas, pero no eliminadas. Se detectó una coordenada anómala y 206 registros potencialmente duplicados.

## Limpieza y unificación de delitos

Los archivos de 2023, 2024 y 2025 contienen en conjunto **447.938 registros**.

El script [`unificar_delitos.py`](data/processing%20codes/unificar_delitos.py):

- Unifica los tres años.
- Conserva el identificador original.
- Conserva año, mes, día, fecha y franja horaria.
- Conserva tipo y subtipo de delito.
- Conserva indicadores de uso de arma y moto.
- Conserva barrio, comuna y cantidad.
- Convierte latitud y longitud a valores numéricos.
- No elimina registros por coincidencia de fecha o ubicación si tienen identificadores diferentes.
- No inventa ni repara coordenadas.

Se descartan únicamente los registros con:

- Coordenadas faltantes.
- Coordenadas no numéricas o no finitas.
- Coordenadas iguales a cero.
- Coordenadas fuera de los límites geográficos utilizados para CABA.

Resultado esperado al ejecutar el script:

- **438.081 registros conservados**
- **9.857 registros descartados por coordenadas**
- **0 identificadores perdidos**
- **0 identificadores presentes en ambas salidas**

Los registros descartados se guardan en un CSV separado junto con el motivo de exclusión.

## Limpieza de espacios verdes

El dataset original contiene **2.176 espacios o polígonos verdes**.

Para el análisis se aplicó un criterio conservador orientado a lugares verdes grandes o de uso familiar.

Se incluyeron:

- Plazas sin evidencia de conflicto.
- Parques con superficie mínima de 1.000 m².
- Jardines identificados con al menos 5.000 m² o patio de juegos.
- Jardín Botánico.
- Reservas ecológicas.

Se excluyeron:

- Canteros centrales.
- Plazoletas pequeñas.
- Patios y paseos pequeños.
- Espacios asociados principalmente a canchas, clubes o plazas secas.
- Polígonos que no representan un espacio verde familiar independiente.

Resultado:

- **428 espacios verdes seleccionados**
- 359 plazas
- 58 parques
- 8 jardines o paseos verdes
- 2 reservas ecológicas
- 1 jardín botánico

El procesamiento geográfico:

- Repara geometrías inválidas cuando es posible.
- Proyecta temporalmente las geometrías a UTM 21S.
- Calcula el centroide geométrico.
- Conserva el centroide original.
- Utiliza un punto representativo interno cuando el centroide cae fuera del polígono.
- Devuelve las coordenadas finales en EPSG:4326.
- Marca los casos que requieren revisión manual.

Las columnas `Latitud_Centroide` y `Longitud_Centroide` contienen el centro geométrico. Las columnas principales `Latitud` y `Longitud` contienen un punto utilizable dentro del espacio verde.

## Unificación y construcción del dataset final

El notebook [`01_unificacion.ipynb`](notebooks/01_unificacion.ipynb) toma el dataset inmobiliario procesado, lo acota al universo residencial, calcula los KPI originales y agrega las variables de entorno derivadas de los datasets geográficos. Su salida es `dataframefinal.csv`, que luego pasa por el notebook de calidad y limpieza.

### 1. Acotamiento del universo

- Se conservan únicamente las publicaciones de **departamento, PH y casa**: **55.582 filas**.
- Oficinas y locales quedan fuera del dataset final.

### 2. Normalización de barrios

`Barrio_Publicado` mezcla barrios oficiales con denominaciones comerciales. Se creó `Barrio_Normalizado` mapeando los casos frecuentes a los 48 barrios oficiales de CABA:

| Publicado | Normalizado |
|---|---|
| Once | Balvanera |
| Barrio Norte | Recoleta |
| Las Cañitas | Palermo |
| Paternal | La Paternal |
| Santa Rita | Villa Santa Rita |
| Villa Gral. Mitre | Villa General Mitre |
| Velez Sarsfield | Vélez Sarsfield |

El notebook incluye una verificación que corta la ejecución si aparece algún barrio sin mapear. Quedaron **133 publicaciones sin barrio informado**, que se excluyen de los KPIs por zona pero se conservan en el dataset.

### 3. Conversión de moneda

Los precios se llevan a una unidad común mediante `Precio_USD` y `Expensas_USD`, con el dólar del día de scraping de cada aviso. El tipo de cambio **no se calcula en la unificación**: llega en el dataset desde el scraper.

| Columna | Qué es | Origen |
|---|---|---|
| `TC_Scraping` | Dólar blue (venta) vigente el día en que se scrapeó el aviso. **Con este se calculan `Precio_USD` y `Expensas_USD`.** | El scraper, desde [DolarApi](https://dolarapi.com/v1/dolares/blue). Para avisos sin dato, el procesamiento, desde la serie histórica de [ArgentinaDatos](https://api.argentinadatos.com/v1/cotizaciones/dolares/blue) |
| `Fecha_TC_Scraping` | Fecha de la cotización. | La API consultada |
| `Fuente_TC_Scraping` | De dónde salió la cotización. | — |

- Los avisos del scraping de agosto de 2026 se scrapearon antes de existir estas columnas, así que su cotización la completó el procesamiento con la serie histórica.
- Cada scraping nuevo trae la cotización de su propio día, sin tocar el código.
- El notebook se detiene si algún aviso no tiene `TC_Scraping`.

Cuando `Moneda_Expensas` está vacía se asume ARS.

### 4. Limpieza de antigüedad y ambientes

- `Antiguedad_limpia`: conserva únicamente valores entre 0 y 150 años; el resto queda como nulo.
- `Ambientes_Agrupado`: agrupa en `1`, `2`, `3` y `4+` para tener volumen suficiente por categoría.

### 5. Filtro de calidad para KPIs monetarios

Los cálculos de precio exigen que la publicación:

- Tenga `Flag_Precio_Anomalo`, `Flag_Operacion_Anomala` y `Flag_Superficie_Anomala` en `0`.
- Tenga superficie total mayor a cero.
- Tenga un `Precio_m2_USD` dentro de los percentiles 1 y 99 **de su tipo de operación**.

Resultado: **53.628 de 54.720** publicaciones pasan el filtro.

Las publicaciones que no lo pasan no se eliminan: quedan en el dataset pero no participan de los agregados de precio.

### 6. KPIs calculados

**Tasa de confort (`Tasa_Confort_Amenities`)**

Proporción de amenities presentes sobre una lista de 15 características de confort (amoblado, ascensor, balcón, terraza, patio, pileta, parrilla, SUM, gimnasio, laundry, seguridad, aire acondicionado, calefacción, lavadero, dormitorio en suite). Media 0,25 y mediana 0,20.

**Precio por metro cuadrado**

Promedio y mediana de `Precio_m2_USD` agregados por barrio y operación, y en una segunda tabla desagregados también por tipo de propiedad.

> **Versión PE2.** Los KPIs de inversión de esta sección se conservan porque `02_calidad_y_limpieza.ipynb` los usa para diagnosticar la cobertura. Para las conclusiones se usan los del notebook 05 (sección "PreEntrega 3"): rentabilidad neta por aviso con costos, índice de subvaluación fuera de muestra e índice de priorización. El **payback** y el **score de oportunidad** se eliminaron.

**Rentabilidad por zona**

Se agrupa por **barrio × tipo de propiedad × ambientes agrupados**, exigiendo un mínimo de 5 avisos por combinación para confiar en la mediana. Quedan **139 combinaciones** que tienen simultáneamente avisos de venta y de alquiler suficientes.

```text
Rentabilidad_Bruta_Estimada = (Alquiler_Mediano × 12) / Precio_Venta_Mediano

Rentabilidad_Neta_Estimada  = (Alquiler_Mediano × 12
                               − Expensas_Medianas × 12
                               − Precio_Venta_Mediano × 1%) / Precio_Venta_Mediano
```

Esta neta resta las expensas ordinarias completas, que en un alquiler paga el inquilino, y no incluye vacancia, comisiones, ABL ni costos de compra. La versión corregida está en el notebook 05.

**Índice de sobre/subvaluación (versión PE2)**

Para cada publicación se estima un precio esperado a partir de la mediana de `Precio_m2_USD` de sus comparables, multiplicada por su superficie. Los comparables se buscan en cascada, bajando de granularidad hasta encontrar al menos 8 avisos:

1. Barrio × tipo × rango de antigüedad × rango de confort
2. Barrio × tipo × rango de antigüedad
3. Barrio × tipo
4. Barrio

```text
Indice_Subvaluacion = (Precio_USD − Precio_Predicho_USD) / Precio_Predicho_USD
```

**Problema conocido:** el grupo de comparables incluye al propio aviso, así que el índice queda sesgado hacia cero. Se conserva solo como referencia; el notebook 05 lo reemplaza por `Indice_Subvaluacion_Modelo`, calculado fuera de muestra.

### 7. Variables de entorno geográfico

Las distancias se calculan proyectando latitud y longitud a coordenadas cartesianas sobre una esfera de radio 6.371 km y consultando un árbol `cKDTree` de SciPy. A la escala de CABA la diferencia respecto de la distancia sobre la superficie es despreciable.

| Variable | Descripción | Fuente |
|---|---|---|
| `Distancia_Subte_m` | Metros a la estación de subte más cercana | `subte_limpio.csv` (90 estaciones) |
| `Distancia_Hospital_m` | Metros al hospital más cercano | `hospitales_limpio.csv` |
| `Cantidad_Delitos_1000m` | Delitos registrados entre 2023 y 2025 dentro de un radio de 1.000 m | `delitos_2023_2025_unificado_limpio.csv` (438.081 registros) |
| `Cantidad_Colectivos_500m` | Paradas de colectivo dentro de un radio de 500 m | `colectivos_limpio.csv`, excluyendo paradas con coordenada anómala |

`Cantidad_Delitos_1000m` es un **conteo acumulado de los tres años**, no una tasa anual ni una tasa por habitante. Sirve para comparar entornos entre sí, no como medida absoluta de inseguridad.

Las **63 publicaciones sin coordenadas** quedan con estas cuatro variables en nulo.

### 8. Salida

El resultado se exporta como `dataframefinal.csv`: 55.582 filas con las variables originales del dataset procesado más las columnas de normalización, KPIs y entorno descriptas arriba.

> **Reproducibilidad:** el notebook resuelve todas las rutas a partir de la raíz del repositorio, de modo que funciona desde cualquier copia local sin depender de Google Drive. Requiere `scipy`, y se ejecuta desde un entorno virtual con las dependencias del proyecto instaladas.

## Limpieza de faltantes, outliers y duplicados

El notebook [`02_calidad_y_limpieza.ipynb`](notebooks/02_calidad_y_limpieza.ipynb) toma `dataframefinal.csv`, diagnostica faltantes, precios fuera de contexto y avisos repetidos, y agrega columnas de marcas y tratamientos. No replica el EDA ni los modelos: su responsabilidad termina al generar `dataframe_limpio.csv`.

**Qué NO hace:** no borra ninguna fila y no modifica ningún valor de las 91 columnas originales. Antes de guardar, el notebook verifica con `assert` que las filas y los valores originales no cambiaron. Todo lo nuevo va en columnas aparte, así que cualquier tratamiento se puede ignorar.

**Entrada:** `data/processed/dataframefinal.csv`. **Salida:** `data/processed/dataframe_limpio.csv` (las mismas 55.582 filas, 91 columnas originales + 23 nuevas).

### Decisiones de grupo

| # | Tema | Decisión | Estado |
|---|---|---|---|
| 1 | Rentabilidad y H1 | H1 se evalúa solo en los barrios con rentabilidad en el nivel original; la cascada es prueba de robustez. | Aplicada |
| 2 | Precio por m² fuera de contexto | Se marcan con umbrales 0,40 y 2,50; no se borra. | Aplicada |
| 3 | Duplicados | Se marcan todos, con nivel `Seguro` o `Probable`; no se borra. | Aplicada |
| 4 | Cocheras en PH | Un nulo significa "no tiene": se imputa 0 y queda marcado. | Aplicada |
| 5 | Alquiler tradicional o temporario | Se informan resultados amplios y estrictos; la baja cobertura se declara como limitación. | Cerrada sin reclasificación automática |
| 7 | Expensas de PH y casas en la rentabilidad | Los ceros cuentan en la mediana de la celda. | Aplicada en `01_unificacion.ipynb` |
| 8 | Expensas de departamentos | Se imputan con la mediana de su celda y quedan marcadas. | Aplicada |
| | Balcón | Los nulos se conservan para no confundir ausencia de información con ausencia de balcón. | Cerrada sin imputación |

### Parámetros del notebook

| Parámetro | Valor | Significado |
|---|---|---|
| `IMPUTAR_COCHERAS_PH` | `True` | Imputa 0 en las cocheras nulas de PH (decisión 4). |
| `BALCON_0_ES_NO_TIENE` | `False` | Mantiene nula la superficie de balcón cuando no está informada; no se asume automáticamente que equivale a 0. |
| `EXPENSAS_CERO_DEPTO_ES_FALTANTE` | `True` | Los ceros de expensas de departamentos se tratan como faltantes. |
| `UNIFICACION_CUENTA_CEROS_PH_CASA` | `True` | Replica la versión actual de `01_unificacion.ipynb`, donde los ceros de expensas de PH y casas cuentan en la mediana. |
| `UMBRAL_BAJO`, `UMBRAL_ALTO` | `0,40`, `2,50` | Umbrales del precio por m² relativo a su grupo (decisión 2). |
| `K_VECINOS`, `MIN_N`, `MIN_N_GRUPO` | `15`, `5`, `8` | Vecinos para asignar barrio, mínimo de avisos por celda de rentabilidad y mínimo de avisos por grupo de precio. |

### Diccionario de las 23 columnas nuevas

Los conteos son sobre las 55.582 filas (ventas y alquileres), salvo que se indique otra cosa.

**Rentabilidad**

| Columna | Definición |
|---|---|
| `Motivo_Rentabilidad_Nula` | Por qué un aviso no tiene `Rentabilidad_Neta_Zona`. Valores: `Calculada` (42.067), `Faltan alquileres (<5)` (11.888), `Sin barrio o ambientes` (1.025), `Sin expensas válidas` (395) y `Faltan ventas y alquileres (<5 c/u)` (207). Replica la lógica de `01_unificacion.ipynb` y coincide en el 100% de los avisos. |
| `Flag_Rentabilidad_No_Calculable` | 1 si `Rentabilidad_Neta_Zona` es nula (13.515 filas). |
| `Rentabilidad_Neta_Cascada` | Rentabilidad neta con cascada de granularidad: Barrio × Tipo × Ambientes (igual a `Rentabilidad_Neta_Zona`, verificado con `assert`), después Barrio × Tipo y después Barrio. 327 nulos. **Columna experimental: no reemplaza** a la original. |
| `Nivel_Rentabilidad_Cascada` | Con qué nivel se calculó: `Barrio x Tipo x Ambientes` (42.067), `Barrio x Tipo` (8.493) o `Barrio` (4.695). Los valores de niveles gruesos no son comparables con los del nivel original. |

**Faltantes y codificaciones**

| Columna | Definición |
|---|---|
| `Estado_Inmueble_Limpio` | `Estado_Inmueble` con el texto "Desconocido" convertido en nulo (41.894 nulos). Informados: A estrenar 7.226, En pozo 3.554, Reciclado 1.591, A refaccionar 1.317. |
| `Tipo_Alquiler_Limpio` | `Tipo_Alquiler` con "Desconocido" convertido en nulo. También es nulo en las ventas (no aplica). Solo 454 alquileres están clasificados: Tradicional 239 y Temporario 215. |
| `Superficie_Balcon_m2_Tratada` | Igual a `Superficie_Balcon_m2` mientras `BALCON_0_ES_NO_TIENE = False`. Con `True`, pasa a 0 donde `Balcon = 0` y la superficie es nula. |
| `Flag_Balcon_Sin_Dato` | 1 donde `Balcon = 0` y la superficie de balcón es nula (21.522 filas). Se calcula siempre, se imputen o no. |
| `Cocheras_Tratada` | `Cocheras`, con las cocheras nulas de PH pasadas a 0 (decisión 4). 3 nulos. |
| `Flag_Cocheras_PH_Sin_Dato` | 1 en los PH con `Cocheras` nula, es decir, los imputados (5.201 filas). |
| `Expensas_USD_Limpio` | `Expensas_USD` con los ceros de **departamentos** pasados a nulo (en departamentos, un 0 casi siempre es "todavía no hay expensas fijadas"). En PH y casas los ceros se mantienen. 19.028 nulos. |
| `Expensas_USD_Imputada` | `Expensas_USD_Limpio`, y en los departamentos sin expensas, la mediana de su celda: Barrio × Ambientes (mínimo 5 avisos), si no el Barrio, si no la mediana global. En la validación cruzada, este método aproxima mejor que una regresión con amenities (error mediano de 32,7% contra 37,1%). 1.406 nulos, que son PH y casas con expensas nulas y no se imputan. |
| `Flag_Expensas_Imputada` | 1 en los departamentos con expensa imputada (17.622 filas: 16.215 ceros y 1.407 nulos). |
| `Flag_Antiguedad_Cero_Sin_Estado` | 1 si `Antiguedad = 0` y el estado no es "A estrenar" ni "En pozo" (11.132 filas). Marca los ceros que no se pueden verificar. **La antigüedad 0 no se trata como faltante.** |
| `Barrio_Completo` | `Barrio_Normalizado`, y para los 133 avisos sin barrio, el más frecuente entre los 15 avisos más cercanos por coordenadas. Acierta en el 87,4% de la validación. Es un dato **aproximado**: sirve para describir por barrio y no se usa para recalcular KPIs. |
| `Flag_Barrio_Por_Vecinos` | 1 en los avisos cuyo barrio se asignó por vecinos (133 filas). |

**Precios fuera de contexto**

| Columna | Definición |
|---|---|
| `Ratio_Precio_m2_vs_Mediana` | `Precio_m2_USD` dividido por la mediana de su grupo (Barrio × Tipo × Operación, mínimo 8 avisos; si no alcanza, Barrio × Operación). 1 significa igual a la mediana. 54.555 no nulos. |
| `Flag_Precio_m2_Muy_Bajo` | 1 si el ratio es menor a 0,40 (319 filas). Pueden ser oportunidades o errores de carga: se revisan a mano, no se borran. |
| `Flag_Precio_m2_Muy_Alto` | 1 si el ratio es mayor a 2,50 (210 filas). |

**Duplicados de contenido**

Se consideran el mismo inmueble los avisos con igual barrio, tipo, dirección, precio, superficie y ambientes (4.957 avisos en 2.218 grupos), aunque tengan `Item_ID` y `Link` distintos.

| Columna | Definición |
|---|---|
| `Grupo_Duplicado` | Identificador del grupo de avisos repetidos. Nulo si el aviso no tiene repetidos. Solo sirve para agrupar. |
| `Duplicado_Nivel` | Certeza del grupo. `Alto`: mismo piso informado, probable republicación (2.048 avisos). `Medio`: piso no informado, no se puede distinguir (2.372). `Bajo`: pisos distintos, probables unidades distintas (537). |
| `Duplicado_Sobrante_Nivel` | Para los avisos que no son la primera aparición de su grupo: `Seguro` (nivel Alto, 1.106) o `Probable` (nivel Medio, 1.295). Nulo en los demás, incluidos los de nivel Bajo. |
| `Flag_Duplicado_Sobrante` | 1 si `Duplicado_Sobrante_Nivel` no es nulo (2.401 filas). |

### Limitaciones

- Varios tratamientos descansan en supuestos que no se pueden probar con los datos (por ejemplo, que una cochera nula en PH significa "no tiene"). Por eso todos van en columnas aparte, con su marca.
- `Expensas_USD_Imputada` se validó en departamentos que sí informan expensas, que tienden a ser edificios más viejos. Aplicarla a edificios nuevos es una extrapolación: probablemente subestima.
- Los valores de `Rentabilidad_Neta_Cascada` en niveles distintos del original no son comparables entre sí.
- El impacto estadístico de los extremos y las decisiones de calidad se estudia en `04_outliers_y_analisis_multivariado.ipynb`; no se replica aquí el ranking de oportunidades.


## Documentación complementaria

En la carpeta `extras/` se incluyen los documentos requeridos para el trabajo:

- [Propuesta de negocio y contextualización](extras/propuesta_negocio_descriptiva.pdf)
- [Resumen de calidad del dataset inmobiliario](extras/resumen_calidad_mercadolibre_caba.pdf)

La propuesta de negocio desarrolla:

- Contexto del inversor Buy to Rent.
- Preguntas descriptivas, diagnósticas, predictivas y prescriptivas.
- Hipótesis iniciales.
- KPIs propuestos.
- Limitaciones detectadas.
- Plan de integración geoespacial.
- Hoja de ruta del proyecto.

## Ejecución de los scripts

Desde la raíz del repositorio:

### Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pandas numpy requests beautifulsoup4 urllib3 shapely pyproj scipy matplotlib seaborn statsmodels scikit-learn jupyter ipykernel pytest
```

### Transporte

```bash
python3 "data/processing codes/limpiar_subte.py" \
  --entrada data/raw/estaciones_de_subte.csv \
  --salida data/processed/subte_limpio.csv

python3 "data/processing codes/limpiar_trenes.py" \
  --entrada data/raw/estaciones_ferroviarias.csv \
  --salida data/processed/tren_limpio.csv

python3 "data/processing codes/limpiar_metrobus.py" \
  --entrada data/raw/estaciones-de-metrobus.csv \
  --salida data/processed/metrobus_limpio.csv

python3 "data/processing codes/limpiar_colectivos.py" \
  --entrada data/raw/paradas-de-colectivo.csv \
  --salida data/processed/colectivos_limpio.csv
```

### Delitos

```bash
python3 "data/processing codes/unificar_delitos.py" \
  --entrada-2023 data/raw/delitos_2023.csv \
  --entrada-2024 data/raw/delitos_2024.csv \
  --entrada-2025 data/raw/delitos_2025.csv \
  --salida data/processed/delitos_2023_2025_unificado_limpio.csv \
  --descartados data/processed/delitos_coordenadas_descartadas.csv
```

### Espacios verdes

```bash
python3 "data/processing codes/limpiar_espacios_verdes.py" \
  --entrada data/raw/espacio_verde_publico.csv \
  --salida data/processed/espacios_verdes_familiares_limpio.csv \
  --excluidos data/processed/espacios_verdes_excluidos_revision.csv
```

### Hospitales

```bash
python3 "data/processing codes/limpiar_hospitales.py"
```

### Mercado Libre

Después de descargar el CSV crudo desde Google Drive:

```bash
python3 "data/processing codes/procesar_datos_Mercadolibre.py" \
  --entrada data/raw/mercadolibre_caba_scraping_completo.csv \
  --salida data/processed/mercadolibre_caba_procesado.csv \
  --reporte extras/reporte_anomalias.csv
```

Necesita conexión a internet si algún aviso no trae `TC_Scraping` (como el CSV crudo de agosto de 2026), para completarlo con la serie histórica del dólar.

### Unificación

Una vez generados todos los archivos anteriores, se ejecuta `notebooks/01_unificacion.ipynb`, que produce `dataframefinal.csv`. No necesita internet: el tipo de cambio ya viene en `mercadolibre_caba_procesado.csv`.

### Tests

```bash
python -m pytest tests
```

Los tests no usan internet: reemplazan las APIs por datos fijos. Tampoco necesitan `MercadoLibre_scraper.py`: lo reemplazan por un módulo mínimo.

> **Nota técnica:** `mercadolibre_scraping_completo.py` funciona como orquestador y utiliza el módulo `MercadoLibre_scraper.py`, que contiene los parsers de extracción. Para reproducir el scraping desde cero, ambos archivos deben encontrarse dentro de `scrapper/`.

### Notebooks de análisis

El notebook 02 lee `dataframefinal.csv`; los notebooks 03, 04 y 05 leen `dataframe_limpio.csv`. Los notebooks localizan la raíz del repositorio con rutas relativas, por lo que deben ejecutarse dentro de una copia local del repositorio.

| Orden | Notebook | Qué hace | Escribe |
|---|---|---|---|
| 1 | `notebooks/01_unificacion.ipynb` | Integra las fuentes, normaliza y construye los KPI originales. | `dataframefinal.csv` |
| 2 | `notebooks/02_calidad_y_limpieza.ipynb` | Diagnostica faltantes, valores extremos y duplicados; agrega tratamientos trazables. | `dataframe_limpio.csv` |
| 3 | `notebooks/03_eda_inicial.ipynb` | EDA descriptivo general: distribuciones y relaciones exploratorias no ajustadas. | nada |
| 4 | `notebooks/04_outliers_y_analisis_multivariado.ipynb` | Outliers contextuales, sensibilidad, modelos ajustados y escenarios Buy to Rent. | nada |
| 5 | `notebooks/05_analisis_de_hipotesis.ipynb` | Evaluación formal de las hipótesis, modelo de precio validado fuera de muestra, indicadores por aviso y barrio con costos de la inversión, índice de priorización con sensibilidad y segmentación de barrios. | `indicadores_avisos.csv`, `indicadores_barrio.csv`, `rentabilidad_segmentos.csv`, `resultados_hipotesis.csv` |

Para reproducir el flujo completo se ejecutan los notebooks en orden. Como ambos CSV están versionados, también es posible ejecutar directamente los notebooks 03, 04 y 05 usando `dataframe_limpio.csv`. El notebook 05 tarda unos minutos (validación cruzada y bootstrap); sus semillas están fijas.

## Limitaciones

### Del dataset inmobiliario

- Las publicaciones representan una fotografía del mercado durante los días del scraping.
- Los precios y la disponibilidad pueden cambiar o desaparecer.
- Mercado Libre puede mostrar ubicaciones aproximadas por privacidad.
- La ausencia de un amenity en una publicación no implica necesariamente que el inmueble no lo tenga. En consecuencia, la `Tasa_Confort_Amenities` mide qué tan completa es la publicación tanto como qué tan equipado está el inmueble.
- La clasificación entre alquiler tradicional y temporario tiene cobertura limitada.

### De los KPIs de inversión

- La conversión a dólares usa el dólar blue del día de scraping de cada aviso (`TC_Scraping`). Los avisos de venta suelen publicarse en USD y los de alquiler en pesos, así que la elección del tipo de cambio (blue, MEP u oficial) impacta directamente sobre la rentabilidad estimada. El notebook 04 cuantifica esa sensibilidad con escenarios de ±20%.
- La rentabilidad se calcula comparando **medianas de zona**, no propiedades individuales: no existe una misma unidad publicada simultáneamente en venta y en alquiler.
- El volumen de avisos de alquiler es mucho menor que el de venta (4.591 contra 47.127 en el modelo de valuación). Solo 139 combinaciones de barrio, tipo y ambientes tienen datos suficientes de ambas operaciones, lo que acota fuertemente la cobertura de la rentabilidad por zona. El notebook 05 la amplía con una rentabilidad por aviso basada en un modelo de alquiler.
- La rentabilidad neta del notebook 05 incluye vacancia, comisiones, expensas a cargo del dueño, mantenimiento, ABL y costos de compra y venta, con tres escenarios. El ABL, las expensas extraordinarias y el mantenimiento son supuestos sin dato por aviso.
- El índice de subvaluación de la PE2 compara cada aviso contra la mediana de su propio grupo, que lo incluye. El notebook 05 lo reemplaza por un índice fuera de muestra.
- Los pesos del `Indice_Priorizacion` (50/50) y los supuestos de costos no son resultados empíricos: el notebook 05 mide cuánto cambia el orden si se modifican. No hay datos de resultados posteriores para validar el índice como regla de inversión, así que se usa solo para decidir qué avisos revisar primero.
- Un aviso "subvaluado" puede simplemente tener características no capturadas en los datos (estado, orientación, piso, calidad de la construcción).

### Del cruce geoespacial

- Los límites rectangulares utilizados para validar CABA son controles de plausibilidad, no reemplazan un cruce con el polígono oficial.
- El dataset ferroviario contiene estaciones fuera de CABA, identificadas mediante un flag.
- Los posibles duplicados de transporte se marcan, pero no se eliminan automáticamente.
- Las distancias son en línea recta, no de recorrido a pie.
- El conteo de delitos no está normalizado por población ni por flujo de personas, por lo que las zonas céntricas y de alta circulación aparecen con valores altos aunque no sean necesariamente más riesgosas para un residente.

## PreEntrega 3: análisis de hipótesis, modelos e indicadores

El notebook [`05_analisis_de_hipotesis.ipynb`](notebooks/05_analisis_de_hipotesis.ipynb) pasa de la exploración a un análisis validado y orientado a la decisión. La lógica reutilizable está en [`src/indicadores.py`](src/indicadores.py) y [`src/modelos.py`](src/modelos.py), con tests en `tests/test_indicadores_modelos.py`; el notebook orquesta, muestra e interpreta.

### Metodología

- **Base analítica común** (`indicadores.criterios_base`): precio y superficie (15–2.000 m²) utilizables, flags de calidad sin conflicto, barrio y ambientes informados, sin alquileres temporarios declarados y **sin avisos repetidos**. Quedan 45.825 ventas y 4.099 alquileres. El notebook muestra cuántos avisos elimina cada criterio.
- **Contrastes con dirección preespecificada** (la de la propuesta), p-valor unilateral y **corrección de Holm** sobre los 11 contrastes.
- **Incertidumbre que respeta la estructura de los datos:** errores agrupados por barrio en los modelos por aviso (los avisos de un mismo barrio no son independientes) y **bootstrap jerárquico** (barrios y avisos) para la rentabilidad por segmento.
- **Magnitud y robustez:** cada efecto se traduce a % de precio, USD o puntos de rentabilidad, y se repite con especificaciones alternativas (solo departamentos, sin precios fuera de contexto, con repetidos, definiciones alternativas).
- **Modelo de precio de referencia:** baseline de comparables (la lógica del `Indice_Subvaluacion` original) contra regresión ridge y gradient boosting, con validación cruzada de 5 pliegues **agrupada por inmueble**. Fuera de muestra, el gradient boosting baja el error mediano de 16,9% a 9,7% en venta y de 17,0% a 12,1% en alquiler. El intervalo de predicción del 90% se valida por cobertura.
- **Costos de la inversión:** la rentabilidad neta por aviso descuenta vacancia, comisión por alquilar, expensas a cargo del dueño, mantenimiento, ABL y costos de compra, en tres escenarios (optimista, base y pesimista). La **TIR a 10 años** con costos de compra y de venta reemplaza al payback.

### Costos de la inversión

Supuestos de `ind.SupuestosCostos` (escenario base y rango optimista–pesimista):

| Costo | Base | Optimista – pesimista | Fuente o criterio |
|---|---|---|---|
| Vacancia | 1 mes por contrato de 24 | 0,5 – 2 meses | 30 a 60 días para alquilar ([iProfesional](https://www.iprofesional.com/realestate/426144-cuantos-dias-tarda-en-alquilarse-un-departamento-en-caba)); oferta en máximos ([iProfesional](https://www.iprofesional.com/realestate/463807-record-de-oferta-de-alquileres-en-caba-que-pasara-con-los-precios)) |
| Comisión por alquilar | 1 mes + IVA por contrato, a cargo del propietario | 1 mes – 1 mes + IVA | Ley 5859 de CABA ([Infozona](https://www.infozona.com.ar/?p=350997)) |
| Administración | 0% | 0% – 5% del alquiler | Entre 4% y 6% si se terceriza ([Infozona](https://www.infozona.com.ar/?p=350997)) |
| Expensas a cargo del dueño | Ordinarias solo en la vacancia + extraordinarias (10% de las ordinarias) | 0% – 20% | Las ordinarias las paga el inquilino; las extraordinarias, el propietario ([iProfesional](https://www.iprofesional.com/legales/459135-la-guia-para-saber-que-debe-pagar-el-dueno-y-el-inquilino-en-las-expensas-extraordinarias)). El 10% es un supuesto |
| Mantenimiento | 1% del precio por año | 0,5% – 1,5% | Supuesto del grupo |
| ABL | 0,2% del precio por año | 0,1% – 0,4% | Supuesto: se calcula sobre la valuación fiscal, que no está en el dataset |
| Ganancias | 0% | 0% | Exención para alquiler de vivienda desde 2026 ([elDiarioAR](https://www.eldiarioar.com/economia/gobierno-reglamento-exenciones-ganancias-alquileres-vivienda-venta-inmuebles_1_13266176.html)) |
| Costos de compra | 8,6% del precio | 6% – 10% | Comisión 4% + IVA, escribano 2% + IVA y la mitad de sellos de 2,7% ([Mudafy](https://mudafy.com.ar/guias/post/que-gastos-se-afrontan-al-comprar-una-propiedad), [Ámbito](https://www.ambito.com/real-estate/cuales-son-los-gastos-que-pagan-comprador-y-vendedor-una-propiedad-us100000-caba-y-provincia-n6287354), [Colegio de Escribanos](https://www.colegio-escribanos.org.ar/noticias/2025_12_19-Codigo-Fiscal-2026-INFORME.pdf)) |
| Costos de venta | 5,4% del precio | 4,5% – 6% | Comisión 3% + IVA, mitad de sellos y certificados ([iProfesional](https://www.iprofesional.com/realestate/423461-cuanto-cuesta-escriturar-una-casa-2025-como-se-hace)) |

Resultado: la rentabilidad mediana de las ventas en soporte pasa de **6,3% bruta a 4,0% neta** en el escenario base (2,7% a 5,0% según el escenario). La TIR a 10 años, sin valorización, es de **2,9%**. El sur/oeste rinde más que el norte premium en los tres escenarios. La liquidez entra solo por los costos de salida, porque el dataset no tiene tiempos de venta.

### Estado de las hipótesis

| Hipótesis | Resultado | Estado |
|---|---|---|
| H1 — Rentabilidad Sur/Oeste > Norte premium | +21% relativo para una misma tipología (~+1 p.p. sobre 5,0%); IC95% +8% a +41%. No significativa con la definición estricta de barrios | Sostenida |
| H2 — Cochera y amenities encarecen más la venta que el alquiler | Primas similares (cochera: 14% venta, 18% alquiler; amenities: 6,5% y 6,3%) | No sostenida |
| H3 — 1–2 ambientes rinden más que 3+ | Diferencia mediana −0,6% dentro del mismo barrio y tipo | No sostenida |
| H4 / H4.5 — Cercanía al subte → mayor precio | Efectos menores al 1,5% e indistinguibles de cero dentro del barrio | No sostenida |
| H4b — Colectivos → diferencias de precio | Más paradas a 500 m: −4,3% de USD/m² (P25→P75); 6 de 6 especificaciones | Sostenida |
| H5 — Delitos → menor precio | Sin asociación una vez que la incertidumbre se agrupa por barrio | No sostenida |
| H6 — Particulares más subvaluados | +4,3 p.p. (p sin ajustar 0,011), pero no supera Holm; los particulares también aparecen más sobrevaluados | No sostenida (evidencia sugestiva) |
| H7 — Verde × unidad familiar (reformulada, sin escuelas) | El verde se asocia con alquileres más altos, pero no más en 3+ ambientes | No sostenida |
| H8 — Distancia al hospital → menor precio | Indistinguible de cero | No sostenida |

### Indicadores consolidados (fuente del dashboard)

| Archivo | Contenido |
|---|---|
| `indicadores_avisos.csv` | Una fila por venta de la base: precio estimado fuera de muestra con intervalo del 90%, `Indice_Subvaluacion_Modelo`, alquiler estimado, rentabilidad bruta y neta por aviso, soporte del modelo de alquiler, rentabilidad neta en los escenarios optimista y pesimista, TIR a 10 años, factor de confianza, `Indice_Priorizacion` y `Orden_Revision` dentro del presupuesto del interlocutor (USD 80.000–250.000). |
| `indicadores_barrio.csv` | Una fila por barrio: cobertura, precios por m², rentabilidad observada y modelada (neta base y pesimista, TIR a 10 años), % de avisos subvaluados, entorno y segmento de barrio. |
| `rentabilidad_segmentos.csv` | Rentabilidad bruta observada por barrio × tipo × ambientes (≥5 ventas y ≥5 alquileres). |
| `resultados_hipotesis.csv` | Estimación, IC95%, p-valor unilateral y de Holm, magnitud, robustez y estado de cada contraste. |

El **índice de priorización** (antes "score de oportunidad") combina la rentabilidad neta del aviso y la subvaluación fuera de muestra, normalizadas por percentiles, con pesos de 50/50 y ponderadas por la confianza en el dato. Sirve para ordenar **qué avisos revisar primero**; no es una recomendación de compra, porque no hay datos de resultados posteriores para validarlo como regla de inversión. Los avisos con precio/m² menor al 40% de su grupo se apartan para revisión manual. Mover ±25 puntos el peso entre ambos componentes conserva el 81–83% del top 100, y cambiar los supuestos de costos, el 98–99%. La segmentación de barrios (k-means, k=4, ARI bootstrap mediano 0,90) separa los barrios sobre todo por centralidad y precio de entrada.

### Pendiente para completar la PreEntrega 3

- **Dashboard** para el interlocutor, alimentado exclusivamente por los cuatro CSV anteriores.

## Estado de la PreEntrega 2

**La PreEntrega 2 se considera finalizada dentro del alcance definido.** No quedan tareas obligatorias pendientes para esta entrega: las limitaciones que permanecen están documentadas y se contemplan al interpretar los resultados.

### Completado en el TP2

- EDA cualitativo, cuantitativo y exploratorio en `notebooks/03_eda_inicial.ipynb`.
- Diagnóstico y tratamiento trazable de faltantes, expensas, amenities, duplicados y valores anómalos en `notebooks/02_calidad_y_limpieza.ipynb`.
- Incorporación al dataset de distancia al subte y hospitales, cantidad de colectivos y delitos, y distancia, cantidad y superficie de espacios verdes.
- Visualizaciones descriptivas, análisis contextual de outliers, sensibilidad y modelos ajustados en los notebooks 03 y 04.
- Escenarios exploratorios Buy to Rent con costos, vacancia y tipo de cambio.

La integración de tren y Metrobus, un índice sintético de conectividad, mapas finales y un ranking operativo de inversión fueron desestimados para esta entrega porque no son requisitos de la consigna. La cobertura limitada de la clasificación entre alquiler tradicional, temporario y desconocido se conserva como una limitación explícita, no como una tarea pendiente.

## Uso académico y licencias

Este repositorio fue desarrollado con fines académicos.

Los datasets públicos pertenecen al Gobierno de la Ciudad Autónoma de Buenos Aires y mantienen las licencias informadas en sus respectivas fichas de Buenos Aires Data.

Las publicaciones inmobiliarias pertenecen a Mercado Libre y a sus respectivos anunciantes. Su utilización en este proyecto corresponde a una muestra académica y no implica afiliación con la plataforma.

Antes de reutilizar o redistribuir los datos, se recomienda revisar las condiciones y licencias vigentes de cada fuente.

## Detalle de los scripts de limpieza

En esta sección se resume, a grandes rasgos, qué procesamiento realiza cada uno de los archivos ubicados en la carpeta `data/processing codes/`.

### `procesar_datos_Mercadolibre.py`

Procesa el archivo completo obtenido mediante el scraping de Mercado Libre.

El script:

- Conserva todas las publicaciones obtenidas.
- Reduce las 186 columnas originales a 56 variables relevantes para el análisis, y conserva las 3 de tipo de cambio que agrega el scraper.
- Completa el tipo de cambio faltante con la serie histórica del dólar para la fecha de scraping.
- Agrega 9 flags temáticos de control de calidad.
- Agrega un flag general y una descripción del motivo de la anomalía.
- Mantiene separados el precio y la moneda.
- Conserva las coordenadas geográficas de las propiedades.
- No convierte monedas.
- No elimina automáticamente outliers.
- Completa con `0` los amenities no informados para que puedan utilizarse como variables binarias.

El resultado es un dataset de 70 columnas preparado para el análisis descriptivo.

### `limpiar_subte.py`

Procesa el archivo de estaciones de subte.

El archivo original almacenaba las coordenadas dentro de una geometría con formato:

```text
POINT (longitud latitud)
```

El script:

- Separa la geometría en las columnas `Latitud` y `Longitud`.
- Normaliza los nombres de las estaciones.
- Normaliza las líneas de subte.
- Agrega la variable `Tipo_Transporte`.
- Controla que las coordenadas se encuentren dentro de valores razonables.
- Marca posibles coordenadas anómalas.
- Marca posibles registros duplicados.
- Conserva las 90 estaciones originales.

Estas coordenadas permiten calcular la distancia entre cada propiedad y la estación de subte más cercana (`Distancia_Subte_m`).

### `limpiar_trenes.py`

Procesa el archivo de estaciones ferroviarias.

El script:

- Separa la geometría WKT en `Latitud` y `Longitud`.
- Normaliza los nombres de las líneas ferroviarias.
- Conserva el nombre de la estación y el ramal.
- Conserva barrio, comuna y localidad cuando están informados.
- Agrega la variable `Tipo_Transporte`.
- Marca coordenadas anómalas.
- Crea un flag para identificar estaciones ubicadas fuera de CABA.
- Controla posibles duplicados.

El archivo contiene estaciones de CABA y del resto del AMBA. Por ese motivo, las estaciones externas no fueron eliminadas, sino identificadas mediante `Flag_Fuera_CABA`.

### `limpiar_metrobus.py`

Procesa el archivo de estaciones de Metrobus.

El script:

- Normaliza las coordenadas geográficas.
- Utiliza `X` como longitud y `Y` como latitud.
- Utiliza `coord_X` y `coord_Y` como respaldo y validación.
- Combina las columnas `L1` a `L6` en una única columna llamada `Lineas`.
- Conserva el sentido de circulación de cada línea.
- Reconstruye direcciones faltantes cuando existe información suficiente.
- Crea identificadores técnicos para las estaciones.
- Marca coordenadas anómalas.
- Controla posibles duplicados.
- Conserva las 390 estaciones originales.

El resultado permite calcular la cercanía de cada inmueble a la red de Metrobus.

### `limpiar_colectivos.py`

Procesa el archivo de paradas de colectivo.

El script:

- Convierte las coordenadas con coma decimal a valores numéricos.
- Separa las coordenadas en `Latitud` y `Longitud`.
- Combina las líneas disponibles en cada parada.
- Elimina líneas repetidas dentro de un mismo registro.
- Conserva el sentido de circulación.
- Calcula la cantidad de líneas por parada.
- Reconstruye direcciones faltantes a partir de la calle y la altura.
- Normaliza barrios y comunas.
- Marca coordenadas anómalas.
- Identifica posibles duplicados.

Se conservaron las 6.962 filas originales. Los registros sospechosos fueron marcados mediante flags, pero no se eliminaron automáticamente.

Este dataset se utiliza para calcular `Cantidad_Colectivos_500m`, excluyendo las paradas marcadas con coordenada anómala.

### `unificar_delitos.py`

Procesa y unifica los archivos de delitos correspondientes a 2023, 2024 y 2025.

El script:

- Une los tres archivos en un único dataset.
- Conserva el identificador original de cada hecho.
- Conserva el año, mes, día, fecha y franja horaria.
- Conserva el tipo y subtipo de delito.
- Conserva los indicadores de uso de arma y moto.
- Conserva barrio, comuna y cantidad.
- Convierte `Latitud` y `Longitud` a valores numéricos.
- Verifica que los identificadores sean únicos.
- Guarda los registros rechazados en un archivo separado.

Se eliminaron únicamente los registros con:

- Coordenadas faltantes.
- Coordenadas iguales a cero.
- Coordenadas no numéricas.
- Coordenadas no finitas.
- Coordenadas fuera de los límites utilizados para CABA.

Los archivos originales contenían 447.938 registros. Luego del procesamiento se conservaron 438.081 y se separaron 9.857 por problemas en sus coordenadas.

Este dataset se utiliza para calcular `Cantidad_Delitos_1000m`.

### `limpiar_espacios_verdes.py`

Procesa el archivo de espacios verdes públicos.

El archivo original contenía plazas, parques, plazoletas, canteros centrales, patios recreativos y otros tipos de espacios urbanos.

Para el análisis se conservaron principalmente los espacios verdes grandes o destinados al uso familiar.

Se incluyeron:

- Plazas sin conflictos evidentes.
- Parques con una superficie mínima de 1.000 m².
- Jardines identificados con al menos 5.000 m² o con patio de juegos.
- El Jardín Botánico.
- Reservas ecológicas.

Se excluyeron:

- Canteros centrales.
- Plazoletas pequeñas.
- Patios y paseos de superficie reducida.
- Canchas, clubes y plazas secas.
- Espacios que no representaban claramente un área verde familiar independiente.

El script también realizó un procesamiento geográfico:

- Validó las geometrías.
- Reparó geometrías inválidas cuando fue posible.
- Proyectó temporalmente los polígonos a UTM 21S.
- Calculó el centroide de cada espacio verde.
- Verificó si el centroide se encontraba dentro del polígono.
- Utilizó un punto interno cuando el centroide quedaba fuera.
- Convirtió las coordenadas finales a EPSG:4326.
- Agregó flags de revisión y calidad geométrica.

Las columnas `Latitud_Centroide` y `Longitud_Centroide` conservan el centro geométrico calculado.

Las columnas principales `Latitud` y `Longitud` contienen un punto válido ubicado dentro del espacio verde, que puede utilizarse para representarlo en un mapa.

El resultado final contiene 428 espacios verdes:

- 359 plazas.
- 58 parques.
- 8 jardines o paseos verdes.
- 2 reservas ecológicas.
- 1 jardín botánico.

### `limpiar_hospitales.py`

Procesa el listado de hospitales y efectores de salud.

El archivo original guarda las coordenadas en una geometría `POINT (x y)` expresada en la proyección local del GCBA (Gauss-Krüger, faja "0 de Flores"), no en latitud y longitud.

El script:

- Extrae `x` e `y` de la geometría.
- Aplica un offset de calibración sobre el falso origen de la proyección.
- Reproyecta a EPSG:4326 con `pyproj`.
- Crea las columnas `latitud` y `longitud`.

El offset fue calibrado comparando la posición calculada del Hospital Garrahan contra su ubicación real. Conviene validarlo contra hospitales adicionales distribuidos por la ciudad: si el error creciera hacia los bordes, indicaría que además hay una diferencia de datum no contemplada.

Este dataset se utiliza para calcular `Distancia_Hospital_m`.

## Utilidad de las coordenadas geográficas

La incorporación y normalización de las coordenadas geográficas permite relacionar cada publicación inmobiliaria con las características de su entorno.

A partir de las columnas `Latitud` y `Longitud` ya se calcularon:

- Distancia a la estación de subte más cercana.
- Distancia al hospital más cercano.
- Cantidad de paradas de colectivo dentro de un radio de 500 metros.
- Cantidad de delitos dentro de un radio de 1.000 metros.
- Distancia al espacio verde familiar más cercano.
- Cantidad y superficie de espacios verdes accesibles dentro de un radio de 1.000 metros.

Las distancias a tren y Metrobus, la cantidad de líneas y un índice general de conectividad no forman parte del alcance final de la PreEntrega 2. Se conservaron sus fuentes limpias como material complementario, pero su integración fue desestimada y no constituye una tarea pendiente.

El análisis se realiza utilizando la ubicación individual de cada propiedad, en lugar de asignar el mismo valor promedio a todos los inmuebles de un barrio.

De esta manera, dos propiedades ubicadas dentro del mismo barrio pueden diferenciarse según su cercanía real al transporte público, los espacios verdes y otros elementos del entorno urbano.
