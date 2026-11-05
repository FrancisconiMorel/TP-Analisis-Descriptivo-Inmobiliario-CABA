"""Tests de src/amenities.py con datos sintéticos chicos."""

import numpy as np
import pandas as pd
import pytest

from src import amenities as am


def base(n, tipo="Departamento", **valores):
    """n avisos con todas las variables en 0 y los campos de completitud vacíos."""
    d = pd.DataFrame({"Tipo_Propiedad": [tipo] * n})
    for v in am.VARIABLES:
        d[v] = 0
    for c in am.CAMPOS_COMPLETITUD:
        d[c] = np.nan
    d["Superficie_Balcon_m2"] = np.nan
    for k, v in valores.items():
        d[k] = v
    return d


def test_completitud_y_poco_informados_por_tipo():
    d = base(10)
    for i, c in enumerate(am.CAMPOS_COMPLETITUD):
        d.loc[d.index >= i % 10, c] = 1  # los primeros avisos completan menos campos
    poco = am.aviso_poco_informado(d, cuantil=.2)
    assert poco.sum() == 2 and poco.iloc[:2].all()
    assert am.completitud(d).is_monotonic_increasing


def test_regla_balcon():
    d = base(4, Balcon=[0, 0, 0, 1], Superficie_Balcon_m2=[6.0, 80.0, np.nan, 5.0])
    assert am.regla_balcon(d, maximo_m2=60).tolist() == [True, False, False, False]


def test_regla_ascensor_solo_departamentos_en_piso_alto():
    d = pd.concat([base(3, Piso=[7, 2, 301]), base(1, tipo="PH", Piso=[7])], ignore_index=True)
    assert am.regla_ascensor(d).tolist() == [True, False, False, False]  # 301 es número de unidad


def test_tratar_aplica_reglas_y_decisiones():
    n = 50
    d = base(n, Piso=np.r_[[8] * 5, [np.nan] * 45])
    d["Superficie_Balcon_m2"] = np.r_[[6.0] * 3, [np.nan] * 47]
    # Los primeros 10 avisos informan poco; el resto, todo.
    for c in am.CAMPOS_COMPLETITUD:
        d.loc[d.index >= 10, c] = 1
    # Calefacción: 5% en poco informados, 40% en el resto -> sensible.
    d.loc[d.index >= 10, "Calefaccion"] = (np.arange(40) < 16).astype(int)
    d.loc[0, "Calefaccion"] = 1
    # Pileta: misma presencia en ambos grupos -> estable.
    d["Pileta"] = (np.arange(n) % 5 == 0).astype(int)
    ph = base(10, tipo="PH")
    ph.loc[:4, "Apto_Credito"] = 1
    datos = pd.concat([d, ph], ignore_index=True)

    salida, diag = am.tratar(datos)
    dec = diag.set_index(["Tipo_Propiedad", "Variable"]).Decision
    assert dec[("Departamento", "Calefaccion")] == am.DECISION_SENSIBLE
    assert dec[("Departamento", "Pileta")] == am.DECISION_ESTABLE
    assert dec[("PH", "Admite_Mascotas")] == am.DECISION_SIN_CAMPO

    calef = salida.Calefaccion_Tratada
    assert calef.iloc[1:10].isna().all()          # ceros de avisos poco informados -> nulo
    assert calef.iloc[0] == 1                     # un 1 nunca se toca
    assert calef.iloc[10:].notna().all()          # en el resto el 0 se mantiene
    assert salida.Pileta_Tratada.notna().all()
    assert salida.Balcon_Tratada.iloc[:3].eq(1).all() and salida.Flag_Balcon_Por_Superficie.sum() == 3
    assert salida.Ascensor_Tratada.iloc[:5].eq(1).all() and salida.Flag_Ascensor_Por_Piso.sum() == 5
    assert salida.loc[50:, "Admite_Mascotas_Tratada"].isna().all()
    assert salida.loc[50:, "Apto_Credito_Tratada"].notna().all()


def test_no_modifica_la_entrada_y_tasa_confort():
    d = base(5, Pileta=[1, 0, 0, 0, 0])
    copia = d.copy()
    salida, _ = am.tratar(d)
    pd.testing.assert_frame_equal(d, copia)
    assert salida.Tasa_Confort_Tratada.iloc[0] == pytest.approx(1 / 15)
