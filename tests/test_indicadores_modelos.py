"""Tests de src/indicadores.py y src/modelos.py con datos sintéticos chicos."""

import numpy as np
import pandas as pd
import pytest

from src import indicadores as ind
from src import modelos as mod


def avisos(operacion, barrio, precios, superficie=50, tipo="Departamento", ambientes="2"):
    return pd.DataFrame({"Tipo_Operacion": operacion, "Barrio_Normalizado": barrio, "Tipo_Propiedad": tipo,
                         "Ambientes_Agrupado": ambientes, "Precio_USD": precios,
                         "Superficie_Total_m2": superficie})


# ------------------------------------------------------------ zonas

def test_todos_los_barrios_tienen_comuna():
    assert len(ind.BARRIO_A_COMUNA) == 48
    assert set(ind.COMUNAS) == set(range(1, 16))


def test_zona_h1_principal_y_estricta():
    barrios = pd.Series(["Flores", "Palermo", "Caballito", "Barracas", None])
    assert ind.zona_h1(barrios).tolist()[:4] == ["Sur/Oeste", "Norte premium", "Resto", "Sur/Oeste"]
    assert pd.isna(ind.zona_h1(barrios).iloc[4])
    # Barracas es sur por comuna, pero no está entre los barrios que nombra la propuesta.
    assert ind.zona_h1(barrios, estricta=True).tolist()[:4] == ["Sur/Oeste", "Norte premium", "Resto", "Resto"]


# ------------------------------------------------------------ rentabilidad

def test_rentabilidad_es_razon_de_medianas_y_exige_minimo():
    ventas = pd.concat([avisos("Venta", "Flores", [100_000] * 5), avisos("Venta", "Palermo", [200_000] * 4)])
    alquileres = pd.concat([avisos("Alquiler", "Flores", [500, 600, 700, 800, 900]),
                            avisos("Alquiler", "Palermo", [900] * 5)])
    seg = ind.rentabilidad_segmentos(ventas, alquileres)
    assert seg.Barrio_Normalizado.tolist() == ["Flores"]  # Palermo tiene 4 ventas
    assert seg.Bruta.iloc[0] == pytest.approx(12 * 700 / 100_000)
    assert seg.Bruta_m2.iloc[0] == pytest.approx(seg.Bruta.iloc[0])  # misma superficie


# ------------------------------------------------------------ índice de priorización

def test_score_premia_rentabilidad_alta_y_precio_bajo():
    rent = pd.Series([0.03, 0.05, 0.07])
    subval = pd.Series([0.2, 0.0, -0.2])  # el tercero está 20% por debajo de su referencia
    score = ind.indice_priorizacion(rent, subval, pd.Series([1.0, 1.0, 1.0]))
    assert score.is_monotonic_increasing
    assert score.iloc[2] == pytest.approx(100)


def test_score_respeta_confianza_y_pesos():
    rent, subval = pd.Series([0.03, 0.07]), pd.Series([-0.2, 0.2])
    solo_rent = ind.indice_priorizacion(rent, subval, pd.Series([1.0, 1.0]), peso_rentabilidad=1)
    solo_subval = ind.indice_priorizacion(rent, subval, pd.Series([1.0, 1.0]), peso_rentabilidad=0)
    assert solo_rent.idxmax() == 1 and solo_subval.idxmax() == 0
    assert ind.indice_priorizacion(rent, subval, pd.Series([0.0, 0.6])).iloc[0] == 0
    with pytest.raises(ValueError):
        ind.indice_priorizacion(rent, subval, pd.Series([1.0, 1.0]), peso_rentabilidad=1.5)


def test_factor_confianza():
    flags = pd.DataFrame({"Flag_Anomalia_General": [0, 1, 1, 0], "Flag_Faltantes_Criticos": [0, 0, 1, 0],
                          "Flag_Coordenadas_Anomalas": [0, 0, 0, 1]})
    assert ind.factor_confianza(flags).tolist() == [1.0, 0.6, 0.0, 0.0]


# ------------------------------------------------------------ costos de la inversión

SIN_COSTOS = ind.SupuestosCostos("Sin costos", meses_vacancia=0, meses_comision_alquiler=0,
                                 expensas_extraordinarias_pct=0, mantenimiento_pct_precio=0, abl_pct_precio=0,
                                 costos_entrada_pct=0, costos_salida_pct=0)


def test_sin_costos_la_neta_es_la_bruta_y_la_tir_coincide():
    alquiler, precio, expensas = pd.Series([500.0]), pd.Series([100_000.0]), pd.Series([80.0])
    assert ind.rentabilidad_neta(alquiler, precio, expensas, SIN_COSTOS).iloc[0] == pytest.approx(0.06)
    # Comprar, cobrar 6% por año y revender al mismo precio rinde exactamente 6%.
    assert ind.tir_tenencia(alquiler, precio, expensas, SIN_COSTOS).iloc[0] == pytest.approx(0.06, abs=1e-6)


def test_componentes_del_escenario_base():
    s = ind.SupuestosCostos()
    c = ind.componentes_flujo(pd.Series([1_000.0]), pd.Series([200_000.0]), pd.Series([100.0]), s).iloc[0]
    ocupacion = 24 / 25
    assert c.Ingreso_alquiler == pytest.approx(12_000 * ocupacion)
    assert c.Comision_alquiler == pytest.approx(1_000 * 1.21 * 12 / 25)
    # El propietario paga las ordinarias solo en la vacancia, más las extraordinarias.
    assert c.Expensas_propietario == pytest.approx(1_200 * ((1 - ocupacion) + 0.10))
    assert c.Mantenimiento == pytest.approx(2_000) and c.ABL == pytest.approx(400) and c.Ganancias == 0
    neto = c.Ingreso_alquiler - c[["Comision_alquiler", "Administracion", "Expensas_propietario",
                                   "Mantenimiento", "ABL", "Ganancias"]].sum()
    assert ind.flujo_neto_anual(pd.Series([1_000.0]), pd.Series([200_000.0]), pd.Series([100.0]), s).iloc[0] \
        == pytest.approx(neto)


def test_escenarios_ordenados_y_expensas_faltantes():
    args = (pd.Series([700.0, 700.0]), pd.Series([120_000.0, 120_000.0]), pd.Series([90.0, np.nan]))
    netas = {n: ind.rentabilidad_neta(*args, s).iloc[0] for n, s in ind.ESCENARIOS_COSTOS.items()}
    assert netas["Optimista"] > netas["Base"] > netas["Pesimista"]
    assert np.isnan(ind.rentabilidad_neta(*args).iloc[1])  # sin expensas no hay neta
    tir = ind.tir_tenencia(*args)
    assert np.isnan(tir.iloc[1]) and tir.iloc[0] < netas["Base"]  # los costos de salida bajan el retorno


def test_ordinarias_a_cargo_del_propietario_bajan_la_neta():
    args = (pd.Series([700.0]), pd.Series([120_000.0]), pd.Series([90.0]))
    base = ind.SupuestosCostos()
    assert ind.rentabilidad_neta(*args, ind.con_supuestos(base, expensas_ordinarias_propietario=True)).iloc[0] \
        < ind.rentabilidad_neta(*args, base).iloc[0]
    with pytest.raises(ValueError):
        ind.SupuestosCostos(meses_contrato=0)


# ------------------------------------------------------------ modelos

def test_baseline_usa_cascada_de_comparables():
    entrenamiento = pd.concat([avisos("Venta", "Flores", [100_000] * 8, superficie=50),          # 2000 USD/m²
                               avisos("Venta", "Flores", [300_000] * 8, superficie=100, ambientes="4+")])
    prueba = pd.concat([avisos("Venta", "Flores", [0], superficie=60),                            # celda exacta
                        avisos("Venta", "Flores", [0], superficie=60, ambientes="3")])            # baja a barrio × tipo
    estimado = np.exp(mod.predecir_baseline(entrenamiento, prueba.reset_index(drop=True)))
    assert estimado[0] == pytest.approx(2000 * 60)
    assert estimado[1] == pytest.approx(np.exp(np.log([2000, 3000]).mean()) * 60)  # mediana de 16 valores


def test_grupos_validacion_mantiene_duplicados_juntos():
    df = pd.DataFrame({"Item_ID": ["A", "B", "C"], "Grupo_Duplicado": [7.0, 7.0, np.nan]})
    grupos = mod.grupos_validacion(df)
    assert grupos.iloc[0] == grupos.iloc[1] != grupos.iloc[2]


def test_metricas():
    y = np.log([100, 200, 100, 200])
    m = mod.metricas(y, np.log([105, 190, 115, 400]))  # errores de 5%, 5%, 15% y 100%
    assert m["Dentro_10%"] == 50 and m["Dentro_20%"] == 75
    assert m["MdAPE_%"] == pytest.approx(10)
