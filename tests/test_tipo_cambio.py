"""Tests de src/tipo_cambio.py. No usan internet: las APIs se reemplazan por datos fijos."""

import json

import numpy as np
import pandas as pd
import pytest

from src import tipo_cambio as tc

RESPUESTA_DOLARAPI = {"moneda": "USD", "casa": "blue", "compra": 1545, "venta": 1565,
                      "fechaActualizacion": "2026-10-23T20:57:00.000Z"}
RESPUESTA_ARGENTINADATOS = [
    {"casa": "blue", "compra": 1500, "venta": 1520, "fecha": "2026-10-21"},
    {"casa": "blue", "compra": 1540, "venta": 1560, "fecha": "2026-10-22"},
]


def sin_red(*_a, **_k):
    raise ConnectionError("sin red")


# ------------------------------------------------------------ dólar del scraping

def test_tabla_fija_cubre_los_dias_del_scraping():
    assert set(tc.TC_SCRAPING_BLUE_VENTA) == {"2026-08-14", "2026-08-15", "2026-08-16", "2026-08-17"}
    assert all(v > 0 for v in tc.TC_SCRAPING_BLUE_VENTA.values())


def test_asigna_por_dia_en_hora_de_buenos_aires():
    tabla = {"2026-08-13": 1520.0, "2026-08-14": 1545.0}
    # 23:30 del 13/08 en Buenos Aires ya es 14/08 en UTC: debe tomar el día local.
    fechas = pd.Series(["2026-08-14T11:22:54-03:00", "2026-08-13T23:30:00-03:00"], index=[7, 3])
    res = tc.asignar_tc_scraping(fechas, tabla)
    assert res.tolist() == [1545.0, 1520.0]
    assert list(res.index) == [7, 3]


def test_dia_fuera_de_tabla_o_fecha_invalida_queda_nan():
    res = tc.asignar_tc_scraping(pd.Series(["2026-09-30T10:00:00-03:00", None, "no es fecha"]))
    assert res.isna().all()


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


# ---------------------------------------------------------------- dólar actual

def test_actual_desde_dolarapi(monkeypatch):
    monkeypatch.setattr(tc, "_get_json", lambda url, **_k: RESPUESTA_DOLARAPI)
    actual = tc.obtener_cotizacion_actual("blue")
    assert actual.fuente == "dolarapi.com"
    assert actual.valor("venta") == 1565
    assert actual.valor("promedio") == 1555


def test_actual_respaldo_argentinadatos(monkeypatch):
    def respuesta(url, **_k):
        if "dolarapi" in url:
            raise ConnectionError("caída")
        return RESPUESTA_ARGENTINADATOS

    monkeypatch.setattr(tc, "_get_json", respuesta)
    actual = tc.obtener_cotizacion_actual("blue")
    assert actual.fecha == "2026-10-22"
    assert actual.valor("venta") == 1560


def test_actual_sin_red_devuelve_none(monkeypatch):
    monkeypatch.setattr(tc, "_get_json", sin_red)
    assert tc.obtener_cotizacion_actual("blue") is None


def test_validaciones():
    with pytest.raises(ValueError):
        tc.obtener_cotizacion_actual("euro")
    with pytest.raises(ValueError):
        tc.CotizacionActual("blue", 1, 2, "x", "y").valor("blue")


# --------------------------------------------------------------------- metadata

@pytest.mark.parametrize("con_actual", [True, False])
def test_metadata_se_guarda(tmp_path, monkeypatch, con_actual):
    monkeypatch.setattr(tc, "_get_json", (lambda *_a, **_k: RESPUESTA_DOLARAPI) if con_actual else sin_red)
    actual = tc.obtener_cotizacion_actual("blue")
    meta = tc.construir_metadata("blue", "venta", tc.TC_SCRAPING_BLUE_VENTA, actual)
    ruta = tmp_path / "meta.json"
    meta.guardar(ruta)
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["tc_scraping"]["2026-08-15"] == 1545.0
    assert datos["tc_actual"] == (1565 if con_actual else None)
