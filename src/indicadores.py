"""Indicadores de inversión Buy to Rent: zonas, base analítica, rentabilidad y score.

Lo usa ``notebooks/05_analisis_de_hipotesis.ipynb``. Las funciones no leen ni
escriben archivos: reciben un DataFrame con el esquema de
``data/processed/dataframe_limpio.csv`` y devuelven objetos nuevos, sin
modificar la entrada.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Barrios oficiales de CABA por comuna (Ley 1777).
COMUNAS = {
    1: ["Retiro", "San Nicolás", "Puerto Madero", "San Telmo", "Monserrat", "Constitución"],
    2: ["Recoleta"],
    3: ["Balvanera", "San Cristóbal"],
    4: ["La Boca", "Barracas", "Parque Patricios", "Nueva Pompeya"],
    5: ["Almagro", "Boedo"],
    6: ["Caballito"],
    7: ["Flores", "Parque Chacabuco"],
    8: ["Villa Soldati", "Villa Riachuelo", "Villa Lugano"],
    9: ["Liniers", "Mataderos", "Parque Avellaneda"],
    10: ["Villa Real", "Monte Castro", "Versalles", "Floresta", "Vélez Sarsfield", "Villa Luro"],
    11: ["Villa General Mitre", "Villa Devoto", "Villa del Parque", "Villa Santa Rita"],
    12: ["Coghlan", "Saavedra", "Villa Urquiza", "Villa Pueyrredón"],
    13: ["Núñez", "Belgrano", "Colegiales"],
    14: ["Palermo"],
    15: ["Chacarita", "Villa Crespo", "La Paternal", "Villa Ortúzar", "Agronomía", "Parque Chas"],
}
BARRIO_A_COMUNA = {barrio: comuna for comuna, barrios in COMUNAS.items() for barrio in barrios}

# H1. Definición principal por comunas; la estricta usa los barrios que nombra la propuesta.
ZONAS_H1 = {"Sur/Oeste": [4, 7, 8, 9, 10], "Norte premium": [2, 13, 14]}
ZONAS_H1_ESTRICTA = {"Sur/Oeste": ["Flores", "Parque Avellaneda", "Mataderos"],
                     "Norte premium": ["Palermo", "Recoleta", "Belgrano"]}

CLAVES_SEGMENTO = ["Barrio_Normalizado", "Tipo_Propiedad", "Ambientes_Agrupado"]

# Superficies fuera de este rango no son unidades residenciales plausibles para el análisis.
SUPERFICIE_MIN_M2, SUPERFICIE_MAX_M2 = 15, 2000


def zona_h1(barrios: pd.Series, estricta: bool = False) -> pd.Series:
    """'Sur/Oeste', 'Norte premium' o 'Resto' para cada barrio; nulo si no hay barrio."""
    if estricta:
        mapa = {b: zona for zona, bs in ZONAS_H1_ESTRICTA.items() for b in bs}
        zona = barrios.map(mapa)
    else:
        mapa = {c: zona for zona, cs in ZONAS_H1.items() for c in cs}
        zona = barrios.map(BARRIO_A_COMUNA).map(mapa)
    return zona.fillna("Resto").where(barrios.notna())


def criterios_base(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Criterios de la base analítica, en orden. Cada uno es una máscara booleana.

    Se exige precio y superficie utilizables, flags de calidad sin conflicto,
    barrio y ambientes informados, y se excluyen los alquileres temporarios
    declarados y los avisos repetidos (sobrantes de un grupo de duplicados).
    """
    return {
        "Precio positivo": df.Precio_USD.gt(0),
        f"Superficie total entre {SUPERFICIE_MIN_M2} y {SUPERFICIE_MAX_M2} m²":
            df.Superficie_Total_m2.between(SUPERFICIE_MIN_M2, SUPERFICIE_MAX_M2),
        "Sin flags de precio, operación, tipo o superficie": (
            df.Flag_Precio_Anomalo.eq(0) & df.Flag_Operacion_Anomala.eq(0)
            & df.Flag_Tipo_Propiedad_Anomalo.eq(0) & df.Flag_Superficie_Anomala.eq(0)),
        "Barrio y ambientes informados": df.Barrio_Normalizado.notna() & df.Ambientes_Agrupado.notna(),
        "No es alquiler temporario declarado": ~df.Tipo_Alquiler.eq("Temporario"),
        "No es aviso repetido (sobrante de duplicado)": df.Flag_Duplicado_Sobrante.eq(0),
    }


def mascara_base(df: pd.DataFrame, excluir: tuple[str, ...] = ()) -> pd.Series:
    """Conjunción de ``criterios_base`` salvo los nombrados en ``excluir`` (para robustez)."""
    mascara = pd.Series(True, index=df.index)
    for nombre, criterio in criterios_base(df).items():
        if nombre not in excluir:
            mascara &= criterio.fillna(False)
    return mascara


def rentabilidad_segmentos(ventas: pd.DataFrame, alquileres: pd.DataFrame,
                           claves: list[str] = CLAVES_SEGMENTO, minimo: int = 5) -> pd.DataFrame:
    """Rentabilidad bruta por segmento como razón de medianas de avisos distintos.

    ``Bruta = 12 × mediana(alquiler mensual) / mediana(precio de venta)``.
    ``Bruta_m2`` hace la misma cuenta con precios por m², para controlar que el
    alquiler y la venta del segmento no tengan superficies distintas.
    Solo se conservan los segmentos con al menos ``minimo`` avisos de cada operación.
    """
    def agregar(datos):
        return datos.assign(_m2=datos.Precio_USD / datos.Superficie_Total_m2).groupby(
            claves, observed=True).agg(n=("Precio_USD", "size"), precio=("Precio_USD", "median"),
                                       precio_m2=("_m2", "median"),
                                       superficie=("Superficie_Total_m2", "median"))

    seg = agregar(ventas).add_suffix("_venta").join(agregar(alquileres).add_suffix("_alquiler"), how="inner")
    seg = seg.loc[seg.n_venta.ge(minimo) & seg.n_alquiler.ge(minimo)].copy()
    seg["Bruta"] = 12 * seg.precio_alquiler / seg.precio_venta
    seg["Bruta_m2"] = 12 * seg.precio_m2_alquiler / seg.precio_m2_venta
    return seg.reset_index()


def normalizar(serie: pd.Series, metodo: str = "rango") -> pd.Series:
    """Lleva una serie a [0, 1]. 'rango' usa el percentil (robusto a extremos); 'minmax' la escala lineal."""
    if metodo == "rango":
        return serie.rank(pct=True)
    if metodo == "minmax":
        minimo, maximo = serie.min(), serie.max()
        return (serie - minimo) / (maximo - minimo)
    raise ValueError(f"Método '{metodo}' no válido. Opciones: 'rango', 'minmax'")


def factor_confianza(df: pd.DataFrame, valor_no_critico: float = 0.6) -> pd.Series:
    """1 sin anomalías, ``valor_no_critico`` con alguna no crítica, 0 con faltantes críticos o coordenadas anómalas."""
    critico = df.Flag_Faltantes_Criticos.eq(1) | df.Flag_Coordenadas_Anomalas.eq(1)
    factor = np.where(df.Flag_Anomalia_General.eq(1), valor_no_critico, 1.0)
    return pd.Series(np.where(critico, 0.0, factor), index=df.index)


def score_oportunidad(rentabilidad: pd.Series, subvaluacion: pd.Series, confianza: pd.Series,
                      peso_rentabilidad: float = 0.5, metodo: str = "rango") -> pd.Series:
    """Score 0-100: combina rentabilidad (más es mejor) y subvaluación (más negativa es mejor).

    ``subvaluacion`` es (precio / precio estimado − 1), así que se invierte antes de normalizar.
    """
    if not 0 <= peso_rentabilidad <= 1:
        raise ValueError("peso_rentabilidad debe estar entre 0 y 1")
    componente = (peso_rentabilidad * normalizar(rentabilidad, metodo)
                  + (1 - peso_rentabilidad) * normalizar(-subvaluacion, metodo))
    return 100 * componente * confianza
