"""Tipo de cambio ARS/USD del día de scraping.

Lo usan dos etapas del pipeline:

1. **Scraper** (``scrapper/mercadolibre_scraping_completo.py``): a cada aviso le
   agrega la cotización vigente el día en que se scrapeó (``TC_Scraping``), su
   fecha y su fuente. Consulta la API una sola vez por día de scraping.
2. **Procesamiento** (``data/processing codes/procesar_datos_Mercadolibre.py``):
   completa con la serie histórica los avisos que no la tienen (scrapings
   anteriores a este cambio o días en que la API no respondió).

La conversión de precios a USD se hace después, en ``01_unificacion.ipynb``,
con ``convertir_a_usd``.

Fuentes (APIs públicas, sin autenticación):
- Cotización del día: DolarApi, https://dolarapi.com/v1/dolares/{casa}
- Serie histórica diaria (y respaldo): ArgentinaDatos,
  https://api.argentinadatos.com/v1/cotizaciones/dolares/{casa}
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

URL_DOLARAPI = "https://dolarapi.com/v1/dolares/{casa}"
URL_ARGENTINADATOS = "https://api.argentinadatos.com/v1/cotizaciones/dolares/{casa}"

CASA = "blue"      # criterio del proyecto: dólar blue
PRECIO = "venta"   # precio de venta

ZONA_HORARIA = "America/Argentina/Buenos_Aires"
COLUMNAS_TC = ["TC_Scraping", "Fecha_TC_Scraping", "Fuente_TC_Scraping"]
FUENTE_HISTORICA = "api.argentinadatos.com (histórico, completado en el procesamiento)"

# Si un día no tiene cotización (feriado o fin de semana sin dato) se toma la
# última disponible hacia atrás, hasta este máximo de días.
TOLERANCIA_DIAS = 7
# Si la API falla durante el scraping, se vuelve a intentar recién después de este lapso.
REINTENTO_SEGUNDOS = 600

CASAS_VALIDAS = {"oficial", "blue", "bolsa", "contadoconliqui", "mayorista", "cripto", "tarjeta"}
PRECIOS_VALIDOS = {"compra", "venta"}


@dataclass(frozen=True)
class Cotizacion:
    valor: float   # ARS por USD
    fecha: str     # AAAA-MM-DD de la cotización
    fuente: str

    def como_columnas(self) -> dict[str, object]:
        return {"TC_Scraping": self.valor, "Fecha_TC_Scraping": self.fecha, "Fuente_TC_Scraping": self.fuente}


def _validar(casa: str, precio: str) -> None:
    if casa not in CASAS_VALIDAS:
        raise ValueError(f"Casa '{casa}' no válida. Opciones: {sorted(CASAS_VALIDAS)}")
    if precio not in PRECIOS_VALIDOS:
        raise ValueError(f"Precio '{precio}' no válido. Opciones: {sorted(PRECIOS_VALIDOS)}")


def _get_json(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": "tp-inmobiliario-caba/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fecha_local(valor: str) -> str:
    """Fecha AAAA-MM-DD en hora de Buenos Aires (acepta fechas con hora y zona)."""
    marca = pd.Timestamp(valor)
    if marca.tzinfo is not None:
        marca = marca.tz_convert(ZONA_HORARIA)
    return marca.strftime("%Y-%m-%d")


# ------------------------------------------------------------ cotización del día

def obtener_cotizacion_del_dia(casa: str = CASA, precio: str = PRECIO) -> Cotizacion | None:
    """Cotización vigente ahora. DolarApi y, si falla, el último dato de ArgentinaDatos.

    Devuelve ``None`` si ninguna fuente responde: el scraper sigue y el
    procesamiento completa el dato después con la serie histórica.
    """
    _validar(casa, precio)
    errores = []
    try:
        datos = _get_json(URL_DOLARAPI.format(casa=casa))
        return Cotizacion(float(datos[precio]), _fecha_local(datos["fechaActualizacion"]), "dolarapi.com")
    except Exception as error:  # red caída, timeout, cambio de formato
        errores.append(f"DolarApi: {error!r}")
    try:
        ultimo = max(_get_json(URL_ARGENTINADATOS.format(casa=casa)), key=lambda r: r["fecha"])
        return Cotizacion(float(ultimo[precio]), str(ultimo["fecha"])[:10], "api.argentinadatos.com (último dato)")
    except Exception as error:
        errores.append(f"ArgentinaDatos: {error!r}")
    print("[tipo_cambio] No se pudo obtener la cotización del día: " + " | ".join(errores), flush=True)
    return None


class CotizadorDiario:
    """Consulta la cotización una vez por día calendario y la reutiliza.

    Un scraping largo puede abarcar varios días: cada aviso recibe la
    cotización del día en que se scrapeó. Si la API falla, devuelve ``None`` y
    reintenta recién pasados ``REINTENTO_SEGUNDOS``.
    """

    def __init__(self, casa: str = CASA, precio: str = PRECIO, obtener=None, reloj=time.monotonic):
        _validar(casa, precio)
        self.casa, self.precio = casa, precio
        self._obtener = obtener or obtener_cotizacion_del_dia
        self._reloj = reloj
        self._por_dia: dict[date, Cotizacion] = {}
        self._ultimo_fallo: float | None = None

    def para(self, momento: datetime | None = None) -> Cotizacion | None:
        dia = (momento or datetime.now().astimezone()).date()
        if dia in self._por_dia:
            return self._por_dia[dia]
        if self._ultimo_fallo is not None and self._reloj() - self._ultimo_fallo < REINTENTO_SEGUNDOS:
            return None
        cotizacion = self._obtener(self.casa, self.precio)
        if cotizacion is None:
            self._ultimo_fallo = self._reloj()
            return None
        self._ultimo_fallo = None
        self._por_dia[dia] = cotizacion
        return cotizacion


# ----------------------------------------------------------- serie histórica

def obtener_serie_historica(casa: str = CASA) -> pd.DataFrame:
    """Serie diaria completa de ArgentinaDatos: columnas fecha, compra y venta."""
    _validar(casa, PRECIO)
    return normalizar_serie(_get_json(URL_ARGENTINADATOS.format(casa=casa)))


def normalizar_serie(registros) -> pd.DataFrame:
    serie = pd.DataFrame(registros)
    faltan = {"fecha", "compra", "venta"} - set(serie.columns)
    if faltan:
        raise ValueError(f"La serie de cotizaciones no tiene las columnas {sorted(faltan)}")
    serie = serie[["fecha", "compra", "venta"]].copy()
    serie["fecha"] = pd.to_datetime(serie["fecha"]).dt.normalize()
    serie[["compra", "venta"]] = serie[["compra", "venta"]].astype(float)
    return serie.drop_duplicates("fecha", keep="last").sort_values("fecha").reset_index(drop=True)


def dia_local(fechas: pd.Series) -> pd.Series:
    """Día calendario (sin hora) en hora de Buenos Aires; NaT si la fecha no es válida."""
    dias = pd.to_datetime(fechas, errors="coerce", utc=True)
    return dias.dt.tz_convert(ZONA_HORARIA).dt.tz_localize(None).dt.normalize()


def asignar_por_fecha(fechas: pd.Series, serie: pd.DataFrame, precio: str = PRECIO,
                      tolerancia_dias: int = TOLERANCIA_DIAS) -> pd.DataFrame:
    """Cotización del día de cada fecha (o la última anterior, hasta ``tolerancia_dias``).

    Devuelve un DataFrame alineado con ``fechas``: ``TC`` y ``Fecha_TC`` (AAAA-MM-DD).
    """
    _validar(CASA, precio)
    izquierda = pd.DataFrame({"_orden": range(len(fechas)), "fecha": dia_local(fechas).to_numpy()})
    con_fecha = izquierda.dropna(subset=["fecha"]).sort_values("fecha")
    derecha = serie[["fecha", precio]].rename(columns={precio: "TC"}).assign(Fecha_TC=serie["fecha"])
    unido = pd.merge_asof(con_fecha, derecha, on="fecha", direction="backward",
                          tolerance=pd.Timedelta(days=tolerancia_dias))
    resultado = izquierda[["_orden"]].merge(unido[["_orden", "TC", "Fecha_TC"]], on="_orden", how="left")
    resultado.index = fechas.index
    resultado["Fecha_TC"] = resultado["Fecha_TC"].dt.strftime("%Y-%m-%d")
    return resultado[["TC", "Fecha_TC"]]


def completar_faltantes(datos: pd.DataFrame, serie: pd.DataFrame, faltante: pd.Series,
                        precio: str = PRECIO) -> pd.DataFrame:
    """Completa ``COLUMNAS_TC`` en las filas ``faltante`` con la serie histórica.

    Usa ``Fecha_Scraping`` de cada fila. No toca las filas que ya tienen
    cotización. Devuelve una copia de ``COLUMNAS_TC`` con los valores como texto,
    igual que el resto del CSV procesado. Las filas que no se pudieron completar
    quedan vacías.
    """
    salida = datos[COLUMNAS_TC].copy()
    if not faltante.any():
        return salida
    asignado = asignar_por_fecha(datos.loc[faltante, "Fecha_Scraping"], serie, precio)
    ok = asignado["TC"].notna()
    filas = asignado.index[ok]
    salida.loc[filas, "TC_Scraping"] = asignado.loc[ok, "TC"].map(lambda v: str(float(v)))
    salida.loc[filas, "Fecha_TC_Scraping"] = asignado.loc[ok, "Fecha_TC"]
    salida.loc[filas, "Fuente_TC_Scraping"] = FUENTE_HISTORICA
    sin_dato = asignado.index[~ok]
    salida.loc[sin_dato, COLUMNAS_TC] = ""
    return salida


# --------------------------------------------------------------- conversión

def convertir_a_usd(monto: pd.Series, moneda: pd.Series, tc: pd.Series,
                    moneda_por_defecto: str | None = None) -> pd.Series:
    """Pasa a USD los montos en ARS usando el tipo de cambio de cada fila.

    Montos en USD quedan igual; monedas desconocidas quedan como NaN.
    ``moneda_por_defecto`` completa monedas faltantes (p. ej. "ARS" para expensas).
    """
    moneda = moneda.fillna(moneda_por_defecto) if moneda_por_defecto else moneda
    salida = pd.Series(float("nan"), index=monto.index)
    es_usd = moneda.eq("USD")
    es_ars = moneda.eq("ARS")
    salida[es_usd] = monto[es_usd]
    salida[es_ars] = monto[es_ars] / tc[es_ars]
    return salida
