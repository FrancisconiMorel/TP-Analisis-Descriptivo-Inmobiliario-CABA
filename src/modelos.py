"""Modelos de precio de referencia ("precio justo") y su validación fuera de muestra.

Lo usa ``notebooks/05_analisis_de_hipotesis.ipynb``. El objetivo es log(precio
publicado en USD). Se comparan tres estimadores con validación cruzada
agrupada: los avisos repetidos de un mismo inmueble (``Grupo_Duplicado``)
caen siempre en el mismo pliegue, para que el modelo no se evalúe contra
copias de avisos que vio al entrenar.

- ``baseline``: mediana de precio/m² de comparables × superficie, en cascada
  (barrio × tipo × ambientes, barrio × tipo, barrio; mínimo 8 avisos). Es la
  lógica del ``Indice_Subvaluacion`` original.
- ``ridge``: regresión lineal hedónica con penalización leve.
- ``hgb``: gradient boosting por histogramas, que admite no linealidades e
  interacciones (por ejemplo, ubicación fina por latitud y longitud).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

AMENITIES = ["Admite_Mascotas", "Apto_Credito", "Apto_Profesional", "Amoblado", "Ascensor", "Balcon",
             "Terraza", "Patio", "Pileta", "Parrilla", "SUM", "Gimnasio", "Laundry", "Seguridad",
             "Aire_Acondicionado", "Calefaccion", "Lavadero", "Dormitorio_Suite"]
ENTORNO = ["Distancia_Subte_m", "Cantidad_Colectivos_500m", "Cantidad_Delitos_1000m",
           "Distancia_Hospital_m", "Superficie_Verde_1000m_m2", "Distancia_Espacio_Verde_m"]
NUMERICAS = (["log_superficie", "ratio_cubierta", "Ambientes", "Dormitorios", "Baños", "cocheras",
              "Antiguedad_limpia", "Latitud", "Longitud"] + ENTORNO + AMENITIES)
CATEGORICAS = ["Barrio_Normalizado", "Tipo_Propiedad", "Estado_Inmueble_Limpio"]
CASCADA_BASELINE = [["Barrio_Normalizado", "Tipo_Propiedad", "Ambientes_Agrupado"],
                    ["Barrio_Normalizado", "Tipo_Propiedad"], ["Barrio_Normalizado"]]
MINIMO_COMPARABLES = 8
SEMILLA = 42


def preparar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Copia de ``df`` con las variables del modelo. Valores implausibles pasan a nulo, no se borran filas."""
    d = df.copy()
    d["log_superficie"] = np.log(d.Superficie_Total_m2)
    d["ratio_cubierta"] = (d.Superficie_Cubierta_m2 / d.Superficie_Total_m2).where(lambda s: s.between(0.05, 1))
    d["cocheras"] = d.Cocheras_Tratada.where(d.Cocheras_Tratada.le(10))
    for col in ["Dormitorios", "Baños"]:
        d[col] = d[col].where(d[col].le(15))
    # Sin coordenadas confiables, tampoco son confiables las variables de entorno derivadas de ellas.
    d.loc[d.Flag_Coordenadas_Anomalas.eq(1), ["Latitud", "Longitud"] + ENTORNO] = np.nan
    d["Estado_Inmueble_Limpio"] = d.Estado_Inmueble_Limpio.fillna("Sin dato")
    return d


def grupos_validacion(df: pd.DataFrame) -> pd.Series:
    """Grupo de cada aviso para la validación cruzada: su grupo de duplicados o, si no tiene, su Item_ID."""
    return df.Grupo_Duplicado.astype("string").fillna("ID_" + df.Item_ID.astype(str))


def predecir_baseline(entrenamiento: pd.DataFrame, prueba: pd.DataFrame) -> np.ndarray:
    """log(precio) estimado como mediana de log(precio/m²) de comparables + log(superficie)."""
    log_m2 = np.log(entrenamiento.Precio_USD / entrenamiento.Superficie_Total_m2)
    estimado = pd.Series(np.nan, index=prueba.index)
    for claves in CASCADA_BASELINE:
        grupos = log_m2.groupby([entrenamiento[c] for c in claves]).agg(["median", "size"])
        medianas = grupos.loc[grupos["size"].ge(MINIMO_COMPARABLES), "median"]
        indice = pd.MultiIndex.from_frame(prueba[claves]) if len(claves) > 1 else prueba[claves[0]]
        estimado = estimado.fillna(pd.Series(medianas.reindex(indice).to_numpy(), index=prueba.index))
    estimado = estimado.fillna(log_m2.median())
    return (estimado + np.log(prueba.Superficie_Total_m2)).to_numpy()


def _matriz_hgb(datos: pd.DataFrame, categorias: dict[str, pd.Index] | None = None):
    x = datos[NUMERICAS + CATEGORICAS].copy()
    categorias = categorias or {c: pd.Index(sorted(x[c].dropna().unique())) for c in CATEGORICAS}
    for col in CATEGORICAS:
        x[col] = pd.Categorical(x[col], categories=categorias[col])
    return x, categorias


def ajustar_hgb(datos: pd.DataFrame, y: np.ndarray):
    """Ajusta el gradient boosting. Devuelve una función que predice log(precio) para un DataFrame."""
    x, categorias = _matriz_hgb(datos)
    modelo = HistGradientBoostingRegressor(max_iter=600, learning_rate=0.06, max_leaf_nodes=48,
                                           min_samples_leaf=20, categorical_features="from_dtype",
                                           random_state=SEMILLA).fit(x, y)
    return lambda nuevos: modelo.predict(_matriz_hgb(nuevos, categorias)[0])


def ajustar_ridge(datos: pd.DataFrame, y: np.ndarray):
    """Ajusta la regresión hedónica lineal. Devuelve una función que predice log(precio)."""
    transformador = ColumnTransformer([
        ("num", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()), NUMERICAS),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAS)])
    modelo = make_pipeline(transformador, Ridge(alpha=1.0)).fit(datos, y)
    return modelo.predict


def validacion_cruzada(datos: pd.DataFrame, pliegues: int = 5) -> pd.DataFrame:
    """Predicciones fuera de muestra (log) de los tres estimadores para cada fila de ``datos``.

    ``datos`` debe venir de ``preparar_features``. Devuelve columnas ``y``,
    ``baseline``, ``ridge``, ``hgb`` y ``pliegue``, con el mismo índice.
    """
    y = np.log(datos.Precio_USD.to_numpy())
    salida = pd.DataFrame({"y": y, "pliegue": -1}, index=datos.index)
    for nombre in ["baseline", "ridge", "hgb"]:
        salida[nombre] = np.nan
    divisor = GroupKFold(n_splits=pliegues)
    for numero, (ent, pru) in enumerate(divisor.split(datos, groups=grupos_validacion(datos))):
        entrenamiento, prueba = datos.iloc[ent], datos.iloc[pru]
        filas = datos.index[pru]
        salida.loc[filas, "pliegue"] = numero
        salida.loc[filas, "baseline"] = predecir_baseline(entrenamiento, prueba)
        salida.loc[filas, "ridge"] = ajustar_ridge(entrenamiento, y[ent])(prueba)
        salida.loc[filas, "hgb"] = ajustar_hgb(entrenamiento, y[ent])(prueba)
    return salida


def metricas(y_log: np.ndarray, pred_log: np.ndarray) -> dict[str, float]:
    """Errores en la escala de precio. ``APE`` = |estimado / real − 1|."""
    y_log, pred_log = np.asarray(y_log), np.asarray(pred_log)
    ape = np.abs(np.exp(pred_log - y_log) - 1)
    residuo = pred_log - y_log
    return {"MAE_log": float(np.mean(np.abs(residuo))),
            "MdAPE_%": float(100 * np.median(ape)),
            "Dentro_10%": float(100 * np.mean(ape <= 0.10)),
            "Dentro_20%": float(100 * np.mean(ape <= 0.20)),
            "R2_log": float(1 - np.sum(residuo ** 2) / np.sum((y_log - y_log.mean()) ** 2))}
