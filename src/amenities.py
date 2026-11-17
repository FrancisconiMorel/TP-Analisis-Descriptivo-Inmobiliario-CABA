"""Tratamiento de amenities y condiciones comerciales del notebook 02.

Las reglas distinguen ceros compatibles con ausencia de ceros poco informativos
y corrigen los que contradicen otros campos del aviso. Las columnas originales
se conservan.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

AMENITIES = ["Amoblado", "Ascensor", "Balcon", "Terraza", "Patio", "Pileta", "Parrilla", "SUM", "Gimnasio",
             "Laundry", "Seguridad", "Aire_Acondicionado", "Calefaccion", "Lavadero", "Dormitorio_Suite"]
CONDICIONES = ["Admite_Mascotas", "Apto_Credito", "Apto_Profesional"]
VARIABLES = AMENITIES + CONDICIONES

CAMPOS_COMPLETITUD = ["Orientacion", "Disposicion", "Antiguedad_limpia", "Estado_Inmueble_Limpio",
                      "Expensas_USD_Limpio", "Departamentos_Por_Piso", "Bauleras", "Subtipo_Propiedad",
                      "Piso", "Cantidad_Pisos_Edificio", "Superficie_Cubierta_m2"]
CAMPOS_SOLO_DEPARTAMENTO = ["Admite_Mascotas", "Apto_Profesional"]
TIPOS_SIN_CAMPO = ["PH", "Casa"]

DECISION_ESTABLE = "0 = no tiene"
DECISION_SENSIBLE = "0 → nulo en avisos poco informados"
DECISION_SIN_CAMPO = "Campo no disponible: 0 → nulo"
DECISION_POCO_FRECUENTE = "0 = no tiene (poco frecuente en el tipo)"


@dataclass(frozen=True)
class ParametrosAmenities:
    cuantil_poco_informado: float = 0.20
    umbral_ratio: float = 1.30
    prevalencia_minima: float = 0.05
    balcon_max_m2: float = 60.0
    piso_min_ascensor: int = 5
    piso_max_valido: int = 60


def completitud(df: pd.DataFrame) -> pd.Series:
    """Proporción de campos opcionales informados."""
    return df[CAMPOS_COMPLETITUD].notna().mean(axis=1)


def aviso_poco_informado(df: pd.DataFrame, cuantil: float = 0.20) -> pd.Series:
    """Marca el cuantil menos completo dentro de cada tipo de propiedad."""
    pct = completitud(df).groupby(df.Tipo_Propiedad).rank(method="first", pct=True)
    return pct.le(cuantil)


def regla_balcon(df: pd.DataFrame, maximo_m2: float = 60.0) -> pd.Series:
    return df.Balcon.eq(0) & df.Superficie_Balcon_m2.gt(0) & df.Superficie_Balcon_m2.le(maximo_m2)


def regla_ascensor(df: pd.DataFrame, piso_min: int = 5, piso_max: int = 60) -> pd.Series:
    return df.Tipo_Propiedad.eq("Departamento") & df.Ascensor.eq(0) & df.Piso.between(piso_min, piso_max)


def diagnostico(df: pd.DataFrame, poco_informado: pd.Series,
                p: ParametrosAmenities = ParametrosAmenities()) -> pd.DataFrame:
    """Evidencia y decisión por tipo de propiedad y variable."""
    filas = []
    for tipo, d in df.groupby("Tipo_Propiedad"):
        poco = poco_informado.loc[d.index]
        for v in VARIABLES:
            prev, en_poco, en_resto = d[v].mean(), d.loc[poco, v].mean(), d.loc[~poco, v].mean()
            ratio = en_resto / en_poco if en_poco > 0 else np.inf
            if v in CAMPOS_SOLO_DEPARTAMENTO and tipo in TIPOS_SIN_CAMPO:
                decision = DECISION_SIN_CAMPO
            elif prev < p.prevalencia_minima:
                decision = DECISION_POCO_FRECUENTE
            elif ratio >= p.umbral_ratio:
                decision = DECISION_SENSIBLE
            else:
                decision = DECISION_ESTABLE
            filas.append({"Tipo_Propiedad": tipo, "Variable": v, "Pct_con_1": 100 * prev,
                          "Pct_en_poco_informados": 100 * en_poco, "Pct_en_resto": 100 * en_resto,
                          "Ratio_resto_vs_poco": ratio, "Decision": decision})
    return pd.DataFrame(filas)


def tratar(df: pd.DataFrame, p: ParametrosAmenities = ParametrosAmenities()):
    """Devuelve las 24 columnas del tratamiento y la tabla de diagnóstico."""
    poco = aviso_poco_informado(df, p.cuantil_poco_informado)
    diag = diagnostico(df, poco, p)
    tratadas = df[VARIABLES].astype(float).copy()

    por_balcon = regla_balcon(df, p.balcon_max_m2)
    por_piso = regla_ascensor(df, p.piso_min_ascensor, p.piso_max_valido)
    tratadas.loc[por_balcon, "Balcon"] = 1.0
    tratadas.loc[por_piso, "Ascensor"] = 1.0

    for fila in diag.itertuples():
        en_tipo = df.Tipo_Propiedad.eq(fila.Tipo_Propiedad)
        es_cero = tratadas[fila.Variable].eq(0)
        if fila.Decision == DECISION_SIN_CAMPO:
            tratadas.loc[en_tipo & es_cero, fila.Variable] = np.nan
        elif fila.Decision == DECISION_SENSIBLE:
            tratadas.loc[en_tipo & es_cero & poco, fila.Variable] = np.nan

    salida = tratadas.add_suffix("_Tratada")
    salida["Completitud_Aviso"] = completitud(df)
    salida["Flag_Aviso_Poco_Informado"] = poco.astype(int)
    salida["Flag_Balcon_Por_Superficie"] = por_balcon.astype(int)
    salida["Flag_Ascensor_Por_Piso"] = por_piso.astype(int)
    amen = tratadas[AMENITIES]
    salida["Amenities_Sin_Dato"] = amen.isna().sum(axis=1)
    salida["Tasa_Confort_Tratada"] = amen.mean(axis=1, skipna=True)
    return salida, diag
