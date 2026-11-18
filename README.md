# Análisis inmobiliario de CABA para Buy to Rent

El proyecto ayuda a un inversor a elegir qué avisos de viviendas usadas revisar para comprar y alquilar de manera tradicional. El presupuesto se aplica a la **inversión inicial estimada**: precio publicado más costos de compra del escenario base. El orden de revisión combina rentabilidad neta estimada y diferencia frente al precio de referencia. La [propuesta de negocio](extras/propuesta_negocio_descriptiva.pdf) define un capital disponible de USD 80.000 a 250.000.

## Alcance y datos

La unidad observada es un aviso de Mercado Libre. La muestra de departamentos, PH y casas corresponde a la captura de agosto de 2026. Los importes son precios publicados. El tipo de cambio documentado en cada aviso representa el dólar blue de venta del día de la captura. Se conservan los identificadores originales y se marcan republicaciones probables.

Las fuentes integradas en las variables de entorno son subte, colectivos, delitos, hospitales y espacios verdes. Las estaciones de tren y Metrobús tienen archivos limpios de referencia. Sus distancias quedan fuera de la base unificada y de los contrastes. El conteo de delitos describe hechos registrados dentro de un radio, sin ajustar por población o flujo de personas. Las distancias son en línea recta y algunas ubicaciones de avisos son aproximadas.

### Amenities

Las columnas originales indican detección en el aviso. Un cero original puede reflejar falta de información. Se conserva la cochera tratada del notebook 02, con reglas por tipo y bandera de imputación. El notebook 02 aplica reglas por variable y tipo de propiedad, corrige contradicciones de balcón y ascensor, y conserva los campos originales. H2 usa la cochera tratada y exige cinco amenities de edificio informados en su especificación principal. La robustez repite el contraste con las columnas originales. El modelo predictivo conserva los indicadores originales de mención en el aviso.

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

Los campos de título y descripción necesarios para auditar avisos y probar la sensibilidad se leen del [CSV original de Mercado Libre](https://drive.google.com/file/d/1l2Xgb9xCmSfVGG7uE_JkXDR-RuG6U4LW/view?usp=drive_link), unido por `Item_ID`.

## Método

El notebook 05 evalúa los contrastes con errores agrupados por barrio o bootstrap jerárquico, según corresponda. La tabla de resultados informa intervalos, magnitudes, robustez y ajuste de Holm. El modelo de precio se compara con un baseline de comparables y se evalúa fuera de muestra, agrupando posibles publicaciones del mismo inmueble. El modelo de alquiler estima rentas de avisos en venta. La cobertura exige comparables del mismo barrio, tipo y grupo de ambientes, además de una superficie dentro del rango de la tipología.

| Hipótesis | Formulación resumida |
|---|---|
| H1 | Los barrios del sur y oeste presentan mayor rentabilidad estimada que los barrios premium del norte. |
| H2 | Amenities y cochera incrementan proporcionalmente más el precio de venta que el alquiler y pueden reducir la rentabilidad relativa. |
| H3 | Las unidades de uno y dos ambientes presentan mayor rentabilidad estimada que las unidades de tres o más ambientes. |
| H4 | Una mayor distancia al subte se relaciona con un menor precio por m², incluso comparando dentro de un mismo barrio. |
| H4.5 | Una mayor cantidad de estaciones de subte dentro de 500 m se asocia con un mayor precio por m² dentro del barrio. Mide disponibilidad local, mientras H4 mide distancia a la estación más cercana. |
| H4b | Una mayor accesibilidad a colectivos se relaciona con diferencias de precio dentro de una misma zona. |
| H5 | Una mayor concentración de delitos se relaciona con menores precios por m², controlando por características y barrio. |
| H6 | Las publicaciones de particulares tienen mayor probabilidad de aparecer subvaluadas que las de inmobiliarias. |
| H7 | El acceso a espacios verdes tiene una relación diferencial con el precio de las unidades familiares de tres o más ambientes. |
| H8 | La distancia al centro de salud más cercano se relaciona con diferencias en el precio de venta por m². |

La estimación, la incertidumbre y la conclusión de cada contraste están en [resultados_hipotesis.csv](data/processed/resultados_hipotesis.csv). H4 mide la distancia mínima al subte y H4.5 la cantidad de estaciones accesibles en un radio. Ambos figuran en la familia ajustada. H4b se contrasta en ambas direcciones.

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

La **rentabilidad bruta** observada por segmento es el alquiler mediano anualizado sobre el precio mediano de venta. La **rentabilidad neta por aviso** divide el flujo anual estimado del propietario, con vacancia y costos, por el capital invertido con costos de entrada. La **TIR** agrega un escenario de reventa con costos de salida. Los supuestos de mantenimiento, ABL y expensas extraordinarias se aplican de forma homogénea. Se publican escenarios en los indicadores.

### Orden de revisión

1. Se construye la lista de avisos comparables dentro del presupuesto del inversor. El rango de inversión se aplica al precio más los costos de entrada del escenario base.
2. La renta neta y el descuento ante la referencia se convierten a percentiles con pesos iguales. El factor anterior solo se usa para diagnosticar la sensibilidad del orden.
3. Las señales de texto, los precios extremos y las decisiones de `revision_manual.csv` definen la lista principal, la lista **Validar antes** y el registro de excluidos con motivo. Los avisos de uso comercial u hotelero, ventas parciales y anticipos detectados requieren otro análisis. Una señal automática activa revisión del texto.
4. Las expensas imputadas conservan una alerta. Se vuelve a calcular el indicador con el P75 de expensas observadas del mismo barrio y tipo, con un mínimo de cinco referencias y un piso en el valor imputado. Si un aviso cae fuera de los primeros cien bajo ese supuesto o carece de comparables de expensas, queda para validar.

La revisión manual se aplica por ID y se actualiza si cambia la lista. El puesto ordena la lectura. Antes de decidir se deben verificar estado, destino del inmueble, costos, precio total y disponibilidad.

### Sensibilidad a temporarios

El notebook 05 vuelve a estimar el alquiler excluyendo avisos con señales textuales fuertes y, en una segunda variante, también señales débiles. Informa cantidades de alquileres, cobertura y puestos por barrio. El corte de señales fuertes se compara con 30 reentrenamientos que retiran al azar la misma cantidad de alquileres por barrio. Los cambios de neta del corte por texto y del control se miden sobre un panel fijo de ventas. Son medidas de sensibilidad del modelo. La ausencia de una señal deja la modalidad sin confirmar. La lectura de control queda en [revision_temporarios.csv](data/processed/revision_temporarios.csv).

## Reproducción

Usar Python 3.13. Desde la raíz del proyecto:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest tests
```

Descargar el CSV original enlazado en Fuentes de datos como `data/raw/mercadolibre_caba_scraping_completo.csv`. También se puede configurar `AVISOS_CRUDOS` con la ubicación del archivo. Ejecutar los notebooks en orden, desde una copia escribible del proyecto. Para reproducir el análisis con el corte congelado, usar los insumos procesados versionados.

| Notebook | Salida o análisis |
|---|---|
| [01 — Unificación](notebooks/01_unificacion.ipynb) | `dataframefinal.csv`, con la muestra residencial y las variables de entorno integradas. |
| [02 — Calidad](notebooks/02_calidad_y_limpieza.ipynb) | `dataframe_limpio.csv`, con indicadores de calidad, duplicados e imputaciones trazables. La salida tiene 138 columnas, incluidas las 24 del tratamiento de amenities. |
| [03 — Exploración](notebooks/03_eda_inicial.ipynb) | Distribuciones y relaciones descriptivas. |
| [04 — Análisis multivariado](notebooks/04_outliers_y_analisis_multivariado.ipynb) | Sensibilidad exploratoria, extremos y comparables. |
| [05 — Hipótesis e indicadores](notebooks/05_analisis_de_hipotesis.ipynb) | Contrastes, indicadores, índice y sensibilidades. Usa el CSV original y la revisión manual como entradas adicionales. |

### Preparar los insumos desde las fuentes

Los notebooks usan los CSV de un corte congelado. Los siguientes comandos permiten preparar de nuevo los insumos. La preparación inmobiliaria necesita conexión si debe recuperar cotizaciones históricas.

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

El orquestador de extracción está en `scrapper/mercadolibre_scraping_completo.py`. Importa `scrapper/MercadoLibre_scraper.py` para analizar las publicaciones. Para reproducir el corte histórico se usa el CSV original. Una extracción nueva refleja una población y fechas distintas.

### Exportaciones

- [Indicadores por aviso](data/processed/indicadores_avisos.csv)
- [Indicadores por barrio](data/processed/indicadores_barrio.csv)
- [Rentabilidad por segmento](data/processed/rentabilidad_segmentos.csv)
- [Resultados de hipótesis](data/processed/resultados_hipotesis.csv)
- [Sensibilidad a temporarios](data/processed/sensibilidad_temporarios.csv)

## Dashboard

El acceso al informe de Power BI requiere una cuenta institucional del ITBA. [Abrir el dashboard en Power BI](https://app.powerbi.com/groups/121e50ac-80d8-4c58-83ad-0411ff098e3a/reports/5b42d890-b1e5-446e-b8b2-daa5c407b603/03858e5a0bb3ec97cb83?ctid=a1f50a97-21c0-49a7-a9d4-f244ebb42da7&experience=power-bi).

## Seguimiento de observaciones

El [commit f6ef906](https://github.com/FrancisconiMorel/TP-Analisis-Descriptivo-Inmobiliario-CABA/commit/f6ef906) registra los cambios iniciales de priorización, auditoría y contraste. El tratamiento de amenities y la especificación de H2 siguen los commits [ea63b83](https://github.com/FrancisconiMorel/TP-Analisis-Descriptivo-Inmobiliario-CABA/commit/ea63b8399126dbc01b06b578da0f9dc3ae04d6a4) y [fbf834b](https://github.com/FrancisconiMorel/TP-Analisis-Descriptivo-Inmobiliario-CABA/commit/fbf834b26190e7211316f42f9d1fae2fdcef8a99). La tabla indica dónde comprobar cada punto.

| Observación | Estado | Qué cambió | Dónde se verifica |
|---|---|---|---|
| Factor de confianza y H6 | Resuelta | El índice usa percentiles sin multiplicador. Se verifican cambios de orden y la lectura de H6 distingue proporciones descriptivas y ajustes. | Notebook 05, secciones 9, 10.3 y 12. |
| Revisión de avisos y presupuesto | Resuelta | Auditoría por ID, dos listas y motivo de exclusión. El presupuesto incluye los costos de compra; se compara con el filtro por precio. | `data/processed/revision_manual.csv` y notebook 05, sección 10.3. |
| Temporarios y cobertura por barrio | Resuelta | Se comparan cobertura y puestos, y se mide la variación de la rentabilidad estimada frente a exclusiones aleatorias sobre las mismas ventas. | [Notebook 05](notebooks/05_analisis_de_hipotesis.ipynb), sección 10.4, y [sensibilidad_temporarios.csv](data/processed/sensibilidad_temporarios.csv). |
| Interpretaciones como Markdown | Resuelta | Lecturas próximas a sus salidas y conclusiones ajustadas. | Notebooks 04 y 05. |
| Afirmación de negociación en H4b | Resuelta | Se informa la asociación estimada con el precio publicado. | Notebook 05, sección 6. |
| H4.5 | Resuelta | Se explica la métrica y se informa el contraste por separado dentro de la familia de Holm. | Notebook 05, secciones 6 y 12, y `resultados_hipotesis.csv`. |
| Consistencia del tablero, mapa y filtros | No resuelta | El tablero publicado todavía requiere actualización y validación. Sus cifras pueden diferir de las exportaciones finales. | Informe institucional y salidas del notebook 05. |
| Módulo del scraper y coherencia de fuentes | Resuelta | Se agrega el parser con una prueba sin conexión y se documentan el tratamiento de amenities y el alcance de tren y Metrobús. | `scrapper/`, [tratamiento de amenities](src/amenities.py), notebooks 01, 02 y 05. |
| Cierre del repositorio | Resuelta | Se integra el historial de `main` y se verifican H2, el ranking y la sensibilidad con el CSV oficial de 138 columnas. | README, notebooks y dependencias. |

## Uso académico y licencias

Este repositorio fue desarrollado con fines académicos.

Los datasets públicos pertenecen al Gobierno de la Ciudad Autónoma de Buenos Aires y mantienen las licencias informadas en sus respectivas fichas de Buenos Aires Data.

Las publicaciones inmobiliarias pertenecen a Mercado Libre y a sus respectivos anunciantes. Su utilización en este proyecto corresponde a una muestra académica y no implica afiliación con la plataforma.

Antes de reutilizar o redistribuir los datos, se recomienda revisar las condiciones y licencias vigentes de cada fuente.
