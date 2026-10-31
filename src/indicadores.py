"""Indicadores de inversión Buy to Rent: zonas, base analítica, rentabilidad, costos e índice de priorización.

Lo usa ``notebooks/05_analisis_de_hipotesis.ipynb``. Las funciones no leen ni
escriben archivos: reciben un DataFrame con el esquema de
``data/processed/dataframe_limpio.csv`` y devuelven objetos nuevos, sin
modificar la entrada.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

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


# ---------------------------------------------------------------- costos de la inversión

@dataclass(frozen=True)
class SupuestosCostos:
    """Supuestos de costos de una inversión Buy to Rent en CABA (2026).

    Los porcentajes sobre el alquiler se aplican al alquiler mensual; los
    porcentajes sobre el precio, al precio publicado. Las fuentes de cada valor
    del escenario base están en el README (sección "Costos de la inversión").
    """
    nombre: str = "Base"
    meses_contrato: float = 24             # duración típica del contrato
    meses_vacancia: float = 1.0            # meses sin inquilino entre contratos (30 a 60 días para alquilar)
    meses_comision_alquiler: float = 1.21  # 1 mes + IVA por contrato, a cargo del propietario en CABA (Ley 5859)
    administracion_pct_alquiler: float = 0.0   # 4% a 6% si se terceriza la administración
    expensas_ordinarias_propietario: bool = False  # en la práctica las paga el inquilino, salvo en la vacancia
    expensas_extraordinarias_pct: float = 0.10     # supuesto: extraordinarias como % de las ordinarias
    mantenimiento_pct_precio: float = 0.01     # supuesto del grupo desde la PE2
    abl_pct_precio: float = 0.002              # supuesto: la valuación fiscal no está en el dataset
    ganancias_pct_renta: float = 0.0           # alquiler de vivienda exento desde 2026 (Ley 27.802, Decreto 406/2026)
    costos_entrada_pct: float = 0.086          # comisión 4% + IVA, escribano 2% + IVA, mitad de sellos 2,7%
    costos_salida_pct: float = 0.054           # comisión 3% + IVA, mitad de sellos, certificados
    anios_tenencia: int = 10

    def __post_init__(self):
        if self.meses_contrato <= 0 or self.meses_vacancia < 0:
            raise ValueError("meses_contrato debe ser positivo y meses_vacancia no negativo")


ESCENARIOS_COSTOS = {
    "Optimista": SupuestosCostos("Optimista", meses_vacancia=0.5, meses_comision_alquiler=1.0,
                                 expensas_extraordinarias_pct=0.0, mantenimiento_pct_precio=0.005,
                                 abl_pct_precio=0.001, costos_entrada_pct=0.06, costos_salida_pct=0.045),
    "Base": SupuestosCostos(),
    "Pesimista": SupuestosCostos("Pesimista", meses_vacancia=2.0, administracion_pct_alquiler=0.05,
                                 expensas_extraordinarias_pct=0.20, mantenimiento_pct_precio=0.015,
                                 abl_pct_precio=0.004, costos_entrada_pct=0.10, costos_salida_pct=0.06),
}


def componentes_flujo(alquiler_mensual: pd.Series, precio: pd.Series, expensas_mensuales: pd.Series,
                      s: SupuestosCostos = ESCENARIOS_COSTOS["Base"]) -> pd.DataFrame:
    """Ingreso y cada costo anual de la inversión, en USD por año (los costos con signo positivo).

    El ingreso es el alquiler de los meses ocupados: con contratos de ``meses_contrato``
    y ``meses_vacancia`` entre uno y otro, la ocupación es contrato / (contrato + vacancia).
    Las comisiones se pagan una vez por contrato y se anualizan sobre ese ciclo.
    Si faltan las expensas, los costos que dependen de ellas quedan nulos.
    """
    ciclo = s.meses_contrato + s.meses_vacancia
    ocupacion = s.meses_contrato / ciclo
    renta = 12 * alquiler_mensual * ocupacion
    expensas_anuales = 12 * expensas_mensuales
    fraccion_ordinarias = 1.0 if s.expensas_ordinarias_propietario else (1 - ocupacion)
    return pd.DataFrame({
        "Ingreso_alquiler": renta,
        "Vacancia": 12 * alquiler_mensual - renta,
        "Comision_alquiler": alquiler_mensual * s.meses_comision_alquiler * 12 / ciclo,
        "Administracion": s.administracion_pct_alquiler * renta,
        "Expensas_propietario": expensas_anuales * (fraccion_ordinarias + s.expensas_extraordinarias_pct),
        "Mantenimiento": s.mantenimiento_pct_precio * precio,
        "ABL": s.abl_pct_precio * precio,
        "Ganancias": s.ganancias_pct_renta * renta,
    })


def flujo_neto_anual(alquiler_mensual, precio, expensas_mensuales, s=ESCENARIOS_COSTOS["Base"]) -> pd.Series:
    """Ingreso por alquiler menos todos los costos anuales (USD por año)."""
    c = componentes_flujo(alquiler_mensual, precio, expensas_mensuales, s)
    return c.Ingreso_alquiler - c.drop(columns=["Ingreso_alquiler", "Vacancia"]).sum(axis=1, min_count=6)


def rentabilidad_neta(alquiler_mensual, precio, expensas_mensuales, s=ESCENARIOS_COSTOS["Base"]) -> pd.Series:
    """Flujo neto anual sobre la inversión total (precio + costos de entrada)."""
    return flujo_neto_anual(alquiler_mensual, precio, expensas_mensuales, s) / (precio * (1 + s.costos_entrada_pct))


def tir_tenencia(alquiler_mensual, precio, expensas_mensuales, s=ESCENARIOS_COSTOS["Base"],
                 valorizacion_anual: float = 0.0) -> pd.Series:
    """TIR anual de comprar, alquilar ``s.anios_tenencia`` años y vender.

    Flujos: −precio × (1 + costos de entrada) al inicio; el flujo neto anual cada año;
    y el precio de venta (con ``valorizacion_anual`` en USD) menos los costos de salida
    al final. Con valorización 0 supone que el precio en USD se mantiene: no es un pronóstico.
    A diferencia del payback (1 / rentabilidad), incorpora los costos de entrada y salida
    y el valor temporal del dinero.
    """
    precio = pd.Series(precio, dtype=float)
    flujo = pd.Series(flujo_neto_anual(alquiler_mensual, precio, expensas_mensuales, s), index=precio.index)
    n = s.anios_tenencia
    inversion = (precio * (1 + s.costos_entrada_pct)).to_numpy()
    venta = (precio * (1 + valorizacion_anual) ** n * (1 - s.costos_salida_pct)).to_numpy()
    f = flujo.to_numpy()

    def vpn(r):
        descuento = (1 + r)[:, None] ** -np.arange(1, n + 1)[None, :]
        return -inversion + f * descuento.sum(axis=1) + venta * descuento[:, -1]

    bajo, alto = np.full(len(f), -0.99), np.full(len(f), 1.0)
    for _ in range(100):  # bisección vectorizada: el VPN decrece con la tasa
        medio = (bajo + alto) / 2
        positivo = vpn(medio) > 0
        bajo, alto = np.where(positivo, medio, bajo), np.where(positivo, alto, medio)
    tir = (bajo + alto) / 2
    return pd.Series(np.where(np.isfinite(f) & np.isfinite(inversion), tir, np.nan), index=precio.index)


def con_supuestos(s: SupuestosCostos, **cambios) -> SupuestosCostos:
    """Copia de ``s`` con algunos supuestos cambiados (para sensibilidad)."""
    return replace(s, **cambios)


# ------------------------------------------------------------- índice de priorización

def factor_confianza(df: pd.DataFrame, valor_no_critico: float = 0.6) -> pd.Series:
    """1 sin anomalías, ``valor_no_critico`` con alguna no crítica, 0 con faltantes críticos o coordenadas anómalas."""
    critico = df.Flag_Faltantes_Criticos.eq(1) | df.Flag_Coordenadas_Anomalas.eq(1)
    factor = np.where(df.Flag_Anomalia_General.eq(1), valor_no_critico, 1.0)
    return pd.Series(np.where(critico, 0.0, factor), index=df.index)


def indice_priorizacion(rentabilidad: pd.Series, subvaluacion: pd.Series, confianza: pd.Series,
                        peso_rentabilidad: float = 0.5, metodo: str = "rango") -> pd.Series:
    """Índice 0-100 para ordenar qué avisos revisar primero (screening, no recomendación de compra).

    Combina rentabilidad (más es mejor) y subvaluación (más negativa es mejor).
    ``subvaluacion`` es (precio / precio estimado − 1), así que se invierte antes de normalizar.
    Los pesos son un supuesto: no hay datos de resultados posteriores para validar la
    regla de decisión, así que el notebook 05 mide cuánto cambia el orden si se modifican.
    """
    if not 0 <= peso_rentabilidad <= 1:
        raise ValueError("peso_rentabilidad debe estar entre 0 y 1")
    componente = (peso_rentabilidad * normalizar(rentabilidad, metodo)
                  + (1 - peso_rentabilidad) * normalizar(-subvaluacion, metodo))
    return 100 * componente * confianza
