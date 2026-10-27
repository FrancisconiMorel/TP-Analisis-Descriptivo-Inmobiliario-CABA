"""Tests de src/tipo_cambio.py. No usan internet: las APIs se reemplazan por datos fijos."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from src import tipo_cambio as tc

RESPUESTA_DOLARAPI = {"moneda": "USD", "casa": "blue", "compra": 1525, "venta": 1545,
                      "fechaActualizacion": "2026-08-15T02:30:00.000Z"}  # 14/08 23:30 en Buenos Aires
SERIE = [
    {"casa": "blue", "compra": 1500, "venta": 1520, "fecha": "2026-08-13"},
    {"casa": "blue", "compra": 1525, "venta": 1545, "fecha": "2026-08-14"},
    # 15 y 16 faltan a propósito (fin de semana sin dato)
    {"casa": "blue", "compra": 1530, "venta": 1550, "fecha": "2026-08-17"},
]


def sin_red(*_a, **_k):
    raise ConnectionError("sin red")


# ------------------------------------------------------------ cotización del día

def test_cotizacion_del_dia_desde_dolarapi_en_hora_local(monkeypatch):
    monkeypatch.setattr(tc, "_get_json", lambda url, **_k: RESPUESTA_DOLARAPI)
    cot = tc.obtener_cotizacion_del_dia()
    assert cot == tc.Cotizacion(1545.0, "2026-08-14", "dolarapi.com")
    assert cot.como_columnas() == {"TC_Scraping": 1545.0, "Fecha_TC_Scraping": "2026-08-14",
                                   "Fuente_TC_Scraping": "dolarapi.com"}


def test_cotizacion_del_dia_respaldo_argentinadatos(monkeypatch):
    def respuesta(url, **_k):
        if "dolarapi" in url:
            raise ConnectionError("caída")
        return SERIE

    monkeypatch.setattr(tc, "_get_json", respuesta)
    cot = tc.obtener_cotizacion_del_dia(precio="compra")
    assert (cot.valor, cot.fecha) == (1530.0, "2026-08-17")
    assert "argentinadatos" in cot.fuente


def test_cotizacion_del_dia_sin_red_devuelve_none(monkeypatch):
    monkeypatch.setattr(tc, "_get_json", sin_red)
    assert tc.obtener_cotizacion_del_dia() is None


def test_validaciones():
    with pytest.raises(ValueError):
        tc.obtener_cotizacion_del_dia(casa="euro")
    with pytest.raises(ValueError):
        tc.obtener_cotizacion_del_dia(precio="promedio")


# ------------------------------------------------------------ cotizador diario

def test_cotizador_consulta_una_vez_por_dia():
    llamadas = []

    def obtener(casa, precio):
        llamadas.append(1)
        return tc.Cotizacion(1500.0 + len(llamadas), "x", "fake")

    cotizador = tc.CotizadorDiario(obtener=obtener)
    dia1 = datetime(2026, 8, 14, 10, tzinfo=timezone.utc)
    assert cotizador.para(dia1).valor == 1501
    assert cotizador.para(dia1.replace(hour=20)).valor == 1501
    assert cotizador.para(datetime(2026, 8, 15, 9, tzinfo=timezone.utc)).valor == 1502
    assert len(llamadas) == 2


def test_cotizador_espera_antes_de_reintentar():
    reloj = {"t": 0.0}
    respuestas = [None, tc.Cotizacion(1545.0, "2026-08-14", "fake")]
    cotizador = tc.CotizadorDiario(obtener=lambda *_a: respuestas.pop(0), reloj=lambda: reloj["t"])
    momento = datetime(2026, 8, 14, 10, tzinfo=timezone.utc)
    assert cotizador.para(momento) is None
    reloj["t"] = tc.REINTENTO_SEGUNDOS - 1
    assert cotizador.para(momento) is None          # todavía no reintenta
    assert len(respuestas) == 1
    reloj["t"] = tc.REINTENTO_SEGUNDOS + 1
    assert cotizador.para(momento).valor == 1545    # reintenta y la guarda


# ----------------------------------------------------------- serie histórica

@pytest.fixture
def serie():
    return tc.normalizar_serie(SERIE)


def test_normalizar_serie():
    s = tc.normalizar_serie(list(reversed(SERIE)))
    assert s["fecha"].is_monotonic_increasing
    with pytest.raises(ValueError):
        tc.normalizar_serie([{"fecha": "2026-08-14", "venta": 1}])


def test_asignar_por_fecha(serie):
    fechas = pd.Series(["2026-08-14T11:22:54-03:00",   # día con dato
                        "2026-08-13T23:30:00-03:00",   # en UTC ya es 14/08: debe usar el 13
                        "2026-08-16T10:00:00-03:00",   # sin dato: usa el 14
                        "2026-09-30T10:00:00-03:00",   # fuera de tolerancia
                        "no es fecha"], index=[9, 8, 7, 6, 5])
    res = tc.asignar_por_fecha(fechas, serie)
    assert list(res.index) == [9, 8, 7, 6, 5]
    assert res["TC"].tolist()[:3] == [1545, 1520, 1545]
    assert res["Fecha_TC"].tolist()[:3] == ["2026-08-14", "2026-08-13", "2026-08-14"]
    assert res["TC"].iloc[3:].isna().all()


def test_completar_faltantes_no_toca_lo_del_scraper(serie):
    datos = pd.DataFrame({
        "Fecha_Scraping": ["2026-08-14T10:00:00-03:00", "2026-08-15T10:00:00-03:00", "2026-09-30T10:00:00-03:00"],
        "TC_Scraping": ["1565.0", "", "N/A"],
        "Fecha_TC_Scraping": ["2026-08-14", "", "N/A"],
        "Fuente_TC_Scraping": ["dolarapi.com", "", "N/A"],
    })
    faltante = pd.Series([False, True, True])
    res = tc.completar_faltantes(datos, serie, faltante)
    assert res.iloc[0].tolist() == ["1565.0", "2026-08-14", "dolarapi.com"]
    assert res.iloc[1].tolist() == ["1545.0", "2026-08-14", tc.FUENTE_HISTORICA]
    assert res.iloc[2].tolist() == ["", "", ""]  # sin dato en la serie: queda vacío


# --------------------------------------------------------------- conversión

def test_convertir_a_usd():
    monto = pd.Series([1000.0, 154500.0, 50.0, 3090.0])
    moneda = pd.Series(["USD", "ARS", "EUR", None])
    tc_fila = pd.Series([1545.0] * 4)
    sin_default = tc.convertir_a_usd(monto, moneda, tc_fila)
    assert sin_default[0] == 1000
    assert sin_default[1] == pytest.approx(100)
    assert np.isnan(sin_default[2]) and np.isnan(sin_default[3])
    con_default = tc.convertir_a_usd(monto, moneda, tc_fila, moneda_por_defecto="ARS")
    assert con_default[3] == pytest.approx(2)
