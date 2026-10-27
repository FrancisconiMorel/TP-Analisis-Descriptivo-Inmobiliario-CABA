"""Integración del tipo de cambio en el scraper y en el procesamiento, sin internet.

El parser real (scrapper/MercadoLibre_scraper.py) no está en el repositorio:
se reemplaza por un módulo mínimo con la misma interfaz que usa el orquestador.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

from src import tipo_cambio as tc

RAIZ = Path(__file__).resolve().parents[1]
SERIE = tc.normalizar_serie([
    {"fecha": "2026-08-14", "compra": 1525, "venta": 1545},
    {"fecha": "2026-08-17", "compra": 1525, "venta": 1545},
])


def cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = modulo  # necesario para los dataclasses del módulo
    spec.loader.exec_module(modulo)
    return modulo


# ------------------------------------------------------------------ scraper

@pytest.fixture
def scraper(monkeypatch, tmp_path):
    falso = types.ModuleType("MercadoLibre_scraper")
    falso.COLUMNS = ["Item_ID", "Link", "Precio", "Fecha_Scraping"]
    falso.LINK_COLUMNS = ["Item_ID", "Link", "Tipo_Operacion"]
    falso.output_frame = lambda frame: frame.reindex(columns=falso.COLUMNS).fillna("N/A")
    monkeypatch.setitem(sys.modules, "MercadoLibre_scraper", falso)
    monkeypatch.chdir(tmp_path)  # el scraper crea output_mercadolibre/ y su log al importarse
    modulo = cargar("scraper_test", RAIZ / "scrapper" / "mercadolibre_scraping_completo.py")
    monkeypatch.setattr(modulo, "DATA_FILE", tmp_path / "datos.csv")
    return modulo


def test_scraper_agrega_columnas_de_tipo_de_cambio(scraper):
    lote = [{"Item_ID": "MLA1", "Link": "l1", "Precio": "100", "Fecha_Scraping": "x", "TC_Scraping": 1545.0,
             "Fecha_TC_Scraping": "2026-08-14", "Fuente_TC_Scraping": "dolarapi.com"},
            {"Item_ID": "MLA2", "Link": "l2", "Precio": "200", "Fecha_Scraping": "x"}]  # API caída
    salida = scraper.output_data_frame(pd.DataFrame(lote))
    assert list(salida.columns) == scraper.DATA_COLUMNS
    assert salida.loc[0, "TC_Scraping"] == 1545.0
    assert salida.loc[1, scraper.TC_COLUMNS].tolist() == ["N/A"] * 3


def test_scraper_migra_csv_viejo_sin_columnas(scraper):
    pd.DataFrame([{"Item_ID": "MLA1", "Link": "l1", "Precio": "100", "Fecha_Scraping": "x"}]).to_csv(
        scraper.DATA_FILE, index=False, encoding="utf-8-sig")
    datos, removidos = scraper.load_and_normalize_data()
    assert removidos == 0
    encabezado = list(pd.read_csv(scraper.DATA_FILE, nrows=0).columns)
    assert encabezado == scraper.DATA_COLUMNS          # el archivo quedó con el esquema nuevo
    assert datos.loc[0, "TC_Scraping"] == "N/A"


def test_scraper_rechaza_esquema_parcial(scraper):
    pd.DataFrame([{"Item_ID": "MLA1", "Link": "l1", "Precio": "1", "Fecha_Scraping": "x", "TC_Scraping": "1"}]).to_csv(
        scraper.DATA_FILE, index=False)
    with pytest.raises(RuntimeError):
        scraper.read_data_checked(scraper.DATA_FILE)


# ------------------------------------------------------------ procesamiento

@pytest.fixture(scope="module")
def procesamiento():
    return cargar("procesamiento_test", RAIZ / "data" / "processing codes" / "procesar_datos_Mercadolibre.py")


def fuente_minima(proc, con_tc, como_read_source=True):
    fila = {col: "" for col in proc.REQUIRED_INPUT_COLUMNS}
    filas = []
    for i, (fecha, tc_valor) in enumerate([("2026-08-14T10:00:00-03:00", "1565.0"),
                                           ("2026-08-16T10:00:00-03:00", "N/A")]):
        f = dict(fila, Item_ID=f"MLA{i}", Fecha_Scraping=fecha)
        if con_tc:
            f.update(TC_Scraping=tc_valor, Fecha_TC_Scraping="2026-08-14" if tc_valor != "N/A" else "N/A",
                     Fuente_TC_Scraping="dolarapi.com" if tc_valor != "N/A" else "N/A")
        filas.append(f)
    datos = pd.DataFrame(filas)
    if como_read_source:  # read_source agrega vacías las columnas que no trae un CSV viejo
        for columna in proc.TC_COLUMNS:
            if columna not in datos.columns:
                datos[columna] = ""
    return datos


def test_procesamiento_lee_csv_viejo_y_nuevo(procesamiento, tmp_path):
    for con_tc in (False, True):
        ruta = tmp_path / f"entrada_{con_tc}.csv"
        fuente_minima(procesamiento, con_tc, como_read_source=False).to_csv(ruta, index=False, encoding="utf-8-sig")
        fuente, _ = procesamiento.read_source(ruta)
        assert set(procesamiento.TC_COLUMNS) <= set(fuente.columns)


def test_procesamiento_completa_solo_los_faltantes(procesamiento):
    fuente = fuente_minima(procesamiento, con_tc=True)
    completo = procesamiento.complete_exchange_rate(fuente, SERIE)
    assert completo.iloc[0].tolist() == ["1565.0", "2026-08-14", "dolarapi.com"]      # del scraper, intacto
    assert completo.iloc[1].tolist() == ["1545.0", "2026-08-14", tc.FUENTE_HISTORICA]  # 16/08 -> último dato (14/08)


def test_procesamiento_sin_faltantes_no_usa_la_red(procesamiento, monkeypatch):
    fuente = fuente_minima(procesamiento, con_tc=True).iloc[[0]]
    monkeypatch.setattr(tc, "_get_json", lambda *_a, **_k: pytest.fail("no debería consultar la API"))
    procesamiento.complete_exchange_rate(fuente)


def test_procesamiento_sin_red_y_con_faltantes_falla_claro(procesamiento, monkeypatch):
    def sin_red(*_a, **_k):
        raise ConnectionError("sin red")

    monkeypatch.setattr(tc, "_get_json", sin_red)
    with pytest.raises(RuntimeError, match="conexion"):
        procesamiento.complete_exchange_rate(fuente_minima(procesamiento, con_tc=False))
