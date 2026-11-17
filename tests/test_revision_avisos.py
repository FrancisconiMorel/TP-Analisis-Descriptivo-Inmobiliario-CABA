"""Regresiones del orden de revisión y la lectura textual de avisos."""

import unittest

import pandas as pd

from src import revision_avisos as rev


class RevisionAvisosTest(unittest.TestCase):
    def test_senales_contextuales(self):
        texto = pd.DataFrame({
            "Titulo": ["Departamento amoblado", "Departamento", "Departamento"],
            "Descripcion": [
                "Contrato por dos años. Cada oficina inmobiliaria independiente.",
                "Alquiler por semana, incluye wifi.",
                "El importe publicado es un anticipo.",
            ],
        })
        senales = rev.senales_textuales(texto)
        self.assertEqual(senales.Temporario_Fuerte.tolist(), [False, True, False])
        self.assertEqual(senales.Temporario_Debil.tolist(), [False, True, False])
        self.assertEqual(senales.Senal_Revision.tolist(), ["", "", "anticipo"])

    def test_orden_y_presupuesto_de_capital(self):
        avisos = pd.DataFrame({
            "Item_ID": ["A", "B", "C", "D"],
            "Precio_USD": [100_000, 235_000, 100_000, 100_000],
            "Indice_Subvaluacion_Modelo": [-.20, -.60, -.20, -.60],
            "Rentabilidad_Neta_Aviso": [.05, .09, .05, .09],
            "En_Soporte_Alquiler": [1, 1, 1, 1],
            "Flag_Precio_m2_Muy_Bajo": [0, 1, 0, 0],
            "Flag_Expensas_Imputada": [0, 0, 0, 0],
            "Expensas_Validas_USD": [100] * 4,
            "Alquiler_Estimado_USD": [600] * 4,
            "Barrio_Normalizado": ["Flores"] * 4,
            "Tipo_Propiedad": ["Departamento"] * 4,
            "Estado_Inmueble_Limpio": ["Usado"] * 4,
        })
        texto = pd.DataFrame({
            "Titulo": ["Departamento", "Departamento", "Departamento", "Departamento"],
            "Descripcion": ["Vivienda", "Vivienda", "Actualmente configurado como hostel", "Vivienda"],
        }, index=["A", "B", "C", "D"])
        auditoria = pd.DataFrame({"Decision": ["Excluir"], "Motivo": ["Hostel"]}, index=["C"])
        final = rev.clasificar(avisos, texto, auditoria, (80_000, 250_000))
        self.assertEqual(final.Lista_Revision.tolist(), ["Principal", "Excluidos", "Excluidos", "Validar antes"])
        self.assertEqual(final.loc[2, "Motivo_Exclusion"], "Hostel")
        self.assertEqual(final.Orden_Revision.count(), 1)
        self.assertEqual(final.loc[0, "Orden_Revision"], 1)
        self.assertGreater(final.loc[1, "Inversion_Inicial_USD"], 250_000)
