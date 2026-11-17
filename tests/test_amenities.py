"""Pruebas del tratamiento de amenities con avisos sintéticos."""

import numpy as np
import pandas as pd

from src import amenities as am


def base(n, tipo="Departamento", **valores):
    datos = pd.DataFrame({"Tipo_Propiedad": [tipo] * n})
    datos[am.VARIABLES] = 0
    datos[am.CAMPOS_COMPLETITUD] = np.nan
    datos["Superficie_Balcon_m2"] = np.nan
    return datos.assign(**valores)


def test_completitud_y_poco_informados_por_tipo():
    datos = base(10)
    for i, columna in enumerate(am.CAMPOS_COMPLETITUD):
        datos.loc[datos.index >= i % 10, columna] = 1
    poco = am.aviso_poco_informado(datos)
    assert poco.sum() == 2 and poco.iloc[:2].all()
    assert am.completitud(datos).is_monotonic_increasing


def test_regla_balcon():
    datos = base(4, Balcon=[0, 0, 0, 1], Superficie_Balcon_m2=[6, 80, np.nan, 5])
    assert am.regla_balcon(datos).tolist() == [True, False, False, False]


def test_regla_ascensor_solo_departamentos_en_piso_alto():
    datos = pd.concat([base(3, Piso=[7, 2, 301]), base(1, tipo="PH", Piso=[7])], ignore_index=True)
    assert am.regla_ascensor(datos).tolist() == [True, False, False, False]


def test_tratar_aplica_reglas_y_decisiones():
    deptos = base(50, Piso=np.r_[[8] * 5, [np.nan] * 45])
    deptos["Superficie_Balcon_m2"] = np.r_[[6.0] * 3, [np.nan] * 47]
    deptos.loc[10:, am.CAMPOS_COMPLETITUD] = 1
    deptos.loc[:25, "Calefaccion"] = 1
    deptos.loc[1:9, "Calefaccion"] = 0
    deptos["Pileta"] = (deptos.index % 5 == 0).astype(int)
    ph = base(10, tipo="PH")
    ph.loc[:4, "Apto_Credito"] = 1
    datos = pd.concat([deptos, ph], ignore_index=True)

    salida, diagnostico = am.tratar(datos)
    decision = diagnostico.set_index(["Tipo_Propiedad", "Variable"]).Decision
    assert decision[("Departamento", "Calefaccion")] == am.DECISION_SENSIBLE
    assert decision[("Departamento", "Pileta")] == am.DECISION_ESTABLE
    assert decision[("PH", "Admite_Mascotas")] == am.DECISION_SIN_CAMPO
    assert salida.Calefaccion_Tratada.iloc[1:10].isna().all()
    assert salida.Calefaccion_Tratada.iloc[0] == 1
    assert salida.Calefaccion_Tratada.iloc[10:].notna().all()
    assert salida.Pileta_Tratada.notna().all()
    assert salida.Balcon_Tratada.iloc[:3].eq(1).all() and salida.Flag_Balcon_Por_Superficie.sum() == 3
    assert salida.Ascensor_Tratada.iloc[:5].eq(1).all() and salida.Flag_Ascensor_Por_Piso.sum() == 5
    assert salida.loc[50:, "Admite_Mascotas_Tratada"].isna().all()
    assert salida.loc[50:, "Apto_Credito_Tratada"].notna().all()


def test_no_modifica_la_entrada_y_tasa_confort():
    datos = base(5, Pileta=[1, 0, 0, 0, 0])
    copia = datos.copy()
    salida, _ = am.tratar(datos)
    pd.testing.assert_frame_equal(datos, copia)
    assert np.isclose(salida.Tasa_Confort_Tratada.iloc[0], 1 / 15)
