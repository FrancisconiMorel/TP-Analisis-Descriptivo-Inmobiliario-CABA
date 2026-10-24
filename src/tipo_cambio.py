"""Tipo de cambio ARS/USD.

Dos cotizaciones con roles distintos:

- **Dólar del scraping** (fijo): la cotización de cada día en que se scrapearon
  los avisos. Se escribe en el código (``TC_SCRAPING_BLUE_VENTA``) porque es un
  dato histórico que no cambia; se usa para convertir los precios a USD.
- **Dólar actual** (API): se descarga cada vez que alguien corre el notebook.
  Fuente principal: DolarApi (https://dolarapi.com/v1/dolares/{casa}).
  Respaldo: último dato de ArgentinaDatos
  (https://api.argentinadatos.com/v1/cotizaciones/dolares/{casa}).
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

URL_DOLARAPI = "https://dolarapi.com/v1/dolares/{casa}"
URL_ARGENTINADATOS = "https://api.argentinadatos.com/v1/cotizaciones/dolares/{casa}"

CASAS_VALIDAS = {"oficial", "blue", "bolsa", "contadoconliqui", "mayorista", "cripto", "tarjeta"}
PRECIOS_VALIDOS = {"compra", "venta", "promedio"}

# Dólar blue, precio de venta, de los días del scraping (14 al 17/08/2026).
# Fuente: ArgentinaDatos, https://api.argentinadatos.com/v1/cotizaciones/dolares/blue/AAAA/MM/DD
# (consultado el 24/10/2026).
TC_SCRAPING_BLUE_VENTA = {
    "2026-08-14": 1545.0,
    "2026-08-15": 1545.0,
    "2026-08-16": 1545.0,
    "2026-08-17": 1545.0,
}
FUENTE_TC_SCRAPING = "api.argentinadatos.com, dólar blue venta (valores fijados en el código)"


@dataclass
class CotizacionActual:
    casa: str
    compra: float
    venta: float
    fecha: str  # tal como la informa la fuente
    fuente: str

    def valor(self, precio: str = "venta") -> float:
        _validar_precio(precio)
        if precio == "promedio":
            return (self.compra + self.venta) / 2
        return getattr(self, precio)


def _validar_casa(casa: str) -> None:
    if casa not in CASAS_VALIDAS:
        raise ValueError(f"Casa '{casa}' no válida. Opciones: {sorted(CASAS_VALIDAS)}")


def _validar_precio(precio: str) -> None:
    if precio not in PRECIOS_VALIDOS:
        raise ValueError(f"Precio '{precio}' no válido. Opciones: {sorted(PRECIOS_VALIDOS)}")


def _get_json(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": "tp-inmobiliario-caba/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------- dólar actual

def _desde_dolarapi(casa: str) -> CotizacionActual:
    datos = _get_json(URL_DOLARAPI.format(casa=casa))
    return CotizacionActual(casa, float(datos["compra"]), float(datos["venta"]),
                            datos["fechaActualizacion"], "dolarapi.com")


def _desde_argentinadatos(casa: str) -> CotizacionActual:
    serie = _get_json(URL_ARGENTINADATOS.format(casa=casa))
    ultimo = max(serie, key=lambda r: r["fecha"])
    return CotizacionActual(casa, float(ultimo["compra"]), float(ultimo["venta"]),
                            ultimo["fecha"], "api.argentinadatos.com (último dato)")


def obtener_cotizacion_actual(casa: str = "blue") -> CotizacionActual | None:
    """Cotización vigente al momento de la corrida.

    Prueba DolarApi y, si falla, ArgentinaDatos. Si ninguna responde devuelve
    ``None`` (el pipeline sigue: el dólar actual no interviene en ``Precio_USD``).
    """
    _validar_casa(casa)
    errores = []
    for fuente in (_desde_dolarapi, _desde_argentinadatos):
        try:
            return fuente(casa)
        except Exception as error:  # red caída, timeout, cambio de formato
            errores.append(f"{fuente.__name__}: {error}")
    print("[tipo_cambio] No se pudo obtener el dólar actual:\n  " + "\n  ".join(errores))
    return None


# ------------------------------------------------------------ dólar del scraping

def dia_local(fechas: pd.Series) -> pd.Series:
    """Día calendario en hora de Buenos Aires (acepta fechas con hora y zona)."""
    dias = pd.to_datetime(fechas, errors="coerce", utc=True)
    return dias.dt.tz_convert("America/Argentina/Buenos_Aires").dt.strftime("%Y-%m-%d")


def asignar_tc_scraping(fechas: pd.Series, tabla: dict[str, float] = TC_SCRAPING_BLUE_VENTA) -> pd.Series:
    """Cotización fija del día de scraping de cada aviso (NaN si el día no está en la tabla)."""
    return dia_local(fechas).map(tabla).astype(float)


def convertir_a_usd(monto: pd.Series, moneda: pd.Series, tc: pd.Series, moneda_por_defecto: str | None = None) -> pd.Series:
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


# --------------------------------------------------------------------- metadata

@dataclass
class MetadataTipoCambio:
    fecha_corrida: str
    casa: str
    precio: str
    tc_scraping: dict
    fuente_tc_scraping: str
    tc_actual: float | None
    fecha_tc_actual: str | None
    fuente_tc_actual: str | None

    def guardar(self, ruta: Path) -> None:
        Path(ruta).write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")


def construir_metadata(casa: str, precio: str, tabla_scraping: dict, actual: CotizacionActual | None) -> MetadataTipoCambio:
    return MetadataTipoCambio(
        fecha_corrida=datetime.now().astimezone().isoformat(timespec="seconds"),
        casa=casa,
        precio=precio,
        tc_scraping=dict(tabla_scraping),
        fuente_tc_scraping=FUENTE_TC_SCRAPING,
        tc_actual=actual.valor(precio) if actual else None,
        fecha_tc_actual=actual.fecha if actual else None,
        fuente_tc_actual=actual.fuente if actual else None,
    )
