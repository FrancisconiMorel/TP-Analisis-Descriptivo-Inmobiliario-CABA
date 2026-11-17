"""Comprueba el contrato del parser sin conexión."""

import unittest

from scrapper import MercadoLibre_scraper as parser


class ScraperOriginalTest(unittest.TestCase):
    def test_tarjeta_de_venta_respeta_esquema(self):
        tarjeta = parser.BeautifulSoup(
            '<article>'
            '<a class="poly-component__title" href="https://inmueble.mercadolibre.com.ar/'
            'MLA-123456789-departamento-_JM">Departamento</a>'
            '<span class="poly-component__headline">Venta</span>'
            '<span class="poly-component__location">Flores, Capital Federal</span>'
            '<span class="poly-price__amount">US$ 100.000</span>'
            '</article>',
            "html.parser",
        )
        aviso = parser.parse_card(tarjeta, "venta", "departamentos", "flores", "consulta")
        self.assertIsNotNone(aviso)
        self.assertEqual(set(aviso), set(parser.LINK_COLUMNS))
        self.assertEqual(aviso["Item_ID"], "MLA123456789")
        self.assertEqual(aviso["Precio_Tarjeta"], 100_000)
        self.assertEqual(aviso["Moneda_Tarjeta"], "USD")
        self.assertEqual(len(set(parser.COLUMNS)), 186)
