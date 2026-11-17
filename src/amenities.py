"""Tratamiento de amenities y condiciones comerciales: ¿el 0 es "no tiene" o "no informado"?

El procesamiento del scraping completa con 0 todo amenity no informado, así que
un 0 mezcla "no tiene" con "el aviso no lo dice". Este módulo genera columnas
nuevas ``<variable>_Tratada`` (1, 0 o nulo) sin tocar las originales, en dos pasos:

**B. Reglas lógicas** (corrigen ceros que el propio aviso contradice):
- ``Balcon = 1`` si el aviso informa una superficie de balcón plausible.
- ``Ascensor = 1`` en departamentos ubicados en un piso alto.

**A. Regla por variable** (decide qué ceros pasan a nulo):
- *Campo no disponible:* algunas variables casi nunca aparecen fuera de los
  departamentos porque Mercado Libre no muestra el campo (admite mascotas,
  apto profesional). En PH y casas sus ceros pasan a nulo.
- *Sensible a la completitud:* si una variable aparece bastante más en los
  avisos que completan más campos que en los poco informados, sus ceros en los
  avisos poco informados son mayormente "no lo dijo" y pasan a nulo. En el
  resto de los avisos el 0 se mantiene como "no tiene".
- *Estable:* si la presencia no depende de cuánto informa el aviso, el 0 se
  mantiene como "no tiene" (típico de los amenities de edificio que el aviso
  destaca: pileta, gimnasio, SUM).

Lo usa ``notebooks/02_calidad_y_limpieza.ipynb``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

AMENITIES = ["Amoblado", "Ascensor", "Balcon", "Terraza", "Patio", "Pileta", "Parrilla", "SUM", "Gimnasio",
             "Laundry", "Seguridad", "Aire_Acondicionado", "Calefaccion", "Lavadero", "Dormitorio_Suite"]
CONDICIONES = ["Admite_Mascotas", "Apto_Credito", "Apto_Profesional"]
VARIABLES = AMENITIES + CONDICIONES

# Campos opcionales que NO son amenities: cuántos completa el aviso mide qué tan informado está.
CAMPOS_COMPLETITUD = ["Orientacion", "Disposicion", "Antiguedad_limpia", "Estado_Inmueble_Limpio",
                      "Expensas_USD_Limpio", "Departamentos_Por_Piso", "Bauleras", "Subtipo_Propiedad",
                      "Piso", "Cantidad_Pisos_Edificio", "Superficie_Cubierta_m2"]

# Mercado Libre muestra estos campos para departamentos; en PH y casas casi nunca aparecen.
CAMPOS_SOLO_DEPARTAMENTO = ["Admite_Mascotas", "Apto_Profesional"]
TIPOS_SIN_CAMPO = ["PH", "Casa"]

DECISION_ESTABLE = "0 = no tiene"
DECISION_SENSIBLE = "0 → nulo en avisos poco informados"
DECISION_SIN_CAMPO = "Campo no disponible: 0 → nulo"
DECISION_POCO_FRECUENTE = "0 = no tiene (poco frecuente en el tipo)"


@dataclass(frozen=True)
class ParametrosAmenities:
    cuantil_poco_informado: float = 0.20   # el 20% de avisos menos completos de cada tipo
    umbral_ratio: float = 1.30             # presencia en el resto / en poco informados a partir de la cual es "sensible"
    prevalencia_minima: float = 0.05       # por debajo, el ratio es ruido y el 0 se mantiene
    balcon_max_m2: float = 60.0            # ≈ percentil 99 de los balcones declarados (53 m²)
    piso_min_ascensor: int = 5             # desde el piso 5, el Ascensor = 0 vale como los que lo declaran
    piso_max_valido: int = 60              # valores mayores son números de unidad, no pisos


def completitud(df: pd.DataFrame) -> pd.Series:
    """Proporción de campos opcionales (no amenities) que informa cada aviso."""
    return df[CAMPOS_COMPLETITUD].notna().mean(axis=1)


def aviso_poco_informado(df: pd.DataFrame, cuantil: float = 0.20) -> pd.Series:
    """True para el ``cuantil`` de avisos menos completos dentro de cada tipo de propiedad."""
    pct = completitud(df).groupby(df.Tipo_Propiedad).rank(method="first", pct=True)
    return pct.le(cuantil)


def regla_balcon(df: pd.DataFrame, maximo_m2: float = 60.0) -> pd.Series:
    """Avisos con Balcon = 0 que informan una superficie de balcón entre 0 y ``maximo_m2``."""
    return df.Balcon.eq(0) & df.Superficie_Balcon_m2.gt(0) & df.Superficie_Balcon_m2.le(maximo_m2)


def regla_ascensor(df: pd.DataFrame, piso_min: int = 5, piso_max: int = 60) -> pd.Series:
    """Departamentos con Ascensor = 0 ubicados entre ``piso_min`` y ``piso_max``."""
    return df.Tipo_Propiedad.eq("Departamento") & df.Ascensor.eq(0) & df.Piso.between(piso_min, piso_max)


def diagnostico(df: pd.DataFrame, poco_informado: pd.Series,
                p: ParametrosAmenities = ParametrosAmenities()) -> pd.DataFrame:
    """Evidencia y decisión para cada tipo de propiedad × variable."""
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
    """Aplica las reglas B y A. Devuelve (columnas nuevas, diagnóstico).

    Las columnas nuevas son ``<variable>_Tratada`` para las 18 variables, más
    ``Completitud_Aviso``, ``Flag_Aviso_Poco_Informado``, ``Flag_Balcon_Por_Superficie``,
    ``Flag_Ascensor_Por_Piso``, ``Amenities_Sin_Dato`` (cantidad de nulos entre las
    15 amenities tratadas) y ``Tasa_Confort_Tratada`` (proporción de amenities
    presentes entre las informadas).
    """
    poco = aviso_poco_informado(df, p.cuantil_poco_informado)
    diag = diagnostico(df, poco, p)
    tratadas = df[VARIABLES].astype(float).copy()

    # B. Reglas lógicas: se aplican primero y pasan el 0 a 1.
    por_balcon = regla_balcon(df, p.balcon_max_m2)
    por_piso = regla_ascensor(df, p.piso_min_ascensor, p.piso_max_valido)
    tratadas.loc[por_balcon, "Balcon"] = 1.0
    tratadas.loc[por_piso, "Ascensor"] = 1.0

    # A. Regla por variable sobre los ceros que quedan.
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
