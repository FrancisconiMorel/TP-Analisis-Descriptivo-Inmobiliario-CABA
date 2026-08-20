"""Procesa el dataset completo de Mercado Libre sin alterar el scraping original.

El programa:

1. Lee ``output_mercadolibre/mercadolibre_caba_scraping_completo.csv``.
2. Conserva todas las filas y 56 variables originales seleccionadas.
3. Calcula nueve flags tematicos, un flag general y ``Motivo_Anomalia``.
4. Genera ``mercadolibre_caba_procesado.csv`` con 67 columnas.
5. Genera ``reporte_anomalias.csv`` con un resumen auditable.

No corrige, convierte monedas, elimina outliers ni deduplica filas. Por regla
explicita de procesamiento, solamente completa con ``0`` los amenities y
caracteristicas binarias que no fueron informados; el resto de los valores se
copia textualmente desde el archivo de entrada. Las conversiones numericas se
realizan solo en variables temporales para evaluar reglas de calidad.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "output_mercadolibre" / "mercadolibre_caba_scraping_completo.csv"
DEFAULT_OUTPUT = BASE_DIR / "output_mercadolibre" / "mercadolibre_caba_procesado.csv"
DEFAULT_REPORT = BASE_DIR / "output_mercadolibre" / "reporte_anomalias.csv"

# Umbrales aprobados. Pueden cambiarse por argumentos de terminal sin tocar el codigo.
DEFAULT_VENTA_ARS_MIN = 10_000_000.0
VENTA_USD_MIN = 10_000.0
VENTA_USD_MAX = 15_000_000.0
DEFAULT_EXPENSAS_ARS_MAX = 50_000_000.0
DEFAULT_EXPENSAS_USD_MAX = 10_000.0

LATITUD_MIN = -34.71
LATITUD_MAX = -34.52
LONGITUD_MIN = -58.54
LONGITUD_MAX = -58.33

SIN_ANOMALIAS = "Sin anomalías detectadas"


BASE_COLUMNS = [
    "Fuente",
    "Item_ID",
    "Tipo_Operacion",
    "Tipo_Alquiler",
    "Tipo_Propiedad",
    "Subtipo_Propiedad",
    "Titulo",
    "Tipo_Vendedor",
    "Precio_Raw",
    "Precio",
    "Moneda",
    "Expensas_Raw",
    "Expensas",
    "Moneda_Expensas",
    "Direccion_Publicada",
    "Calle",
    "Altura",
    "Barrio_Publicado",
    "Latitud",
    "Longitud",
    "Piso",
    "Ambientes",
    "Dormitorios",
    "Baños",
    "Cocheras",
    "Bauleras",
    "Superficie_Total_m2",
    "Superficie_Cubierta_m2",
    "Superficie_No_Cubierta_m2",
    "Superficie_Balcon_m2",
    "Antiguedad",
    "Cantidad_Pisos_Edificio",
    "Departamentos_Por_Piso",
    "Disposicion",
    "Orientacion",
    "Estado_Inmueble",
    "Admite_Mascotas",
    "Apto_Credito",
    "Apto_Profesional",
    "Amoblado",
    "Ascensor",
    "Balcon",
    "Terraza",
    "Patio",
    "Pileta",
    "Parrilla",
    "SUM",
    "Gimnasio",
    "Laundry",
    "Seguridad",
    "Aire_Acondicionado",
    "Calefaccion",
    "Lavadero",
    "Dormitorio_Suite",
    "Link",
    "Fecha_Scraping",
]

FLAG_COLUMNS = [
    "Flag_Precio_Anomalo",
    "Flag_Operacion_Anomala",
    "Flag_Tipo_Propiedad_Anomalo",
    "Flag_Superficie_Anomala",
    "Flag_Ambientes_Anomalo",
    "Flag_Coordenadas_Anomalas",
    "Flag_Expensas_Anomalas",
    "Flag_Amenities_Anomalos",
    "Flag_Faltantes_Criticos",
]

OUTPUT_COLUMNS = [
    *BASE_COLUMNS,
    *FLAG_COLUMNS,
    "Flag_Anomalia_General",
    "Motivo_Anomalia",
]

AMENITY_NAMES = [
    "Admite_Mascotas",
    "Apto_Credito",
    "Apto_Profesional",
    "Amoblado",
    "Ascensor",
    "Balcon",
    "Terraza",
    "Patio",
    "Pileta",
    "Parrilla",
    "SUM",
    "Gimnasio",
    "Laundry",
    "Seguridad",
    "Aire_Acondicionado",
    "Calefaccion",
    "Lavadero",
    "Dormitorio_Suite",
]

AMENITY_CONFLICT_COLUMNS = {
    name: f"Flag_Conflicto_{name}" for name in AMENITY_NAMES
}

SURFACE_COLUMNS_FOR_VALIDATION = [
    "Superficie_Total_m2",
    "Superficie_Cubierta_m2",
    "Superficie_Semicubierta_m2",
    "Superficie_Descubierta_m2",
    "Superficie_No_Cubierta_m2",
    "Superficie_Balcon_m2",
]

HELPER_COLUMNS = [
    "Tipo_Propiedad_ML",
    "Tipo_Propiedad_Inferido",
    "Descripcion",
    "Flag_Expensas_Cero_Sospechoso",
    "Superficie_Semicubierta_m2",
    "Superficie_Descubierta_m2",
    *AMENITY_CONFLICT_COLUMNS.values(),
]

REQUIRED_INPUT_COLUMNS = list(dict.fromkeys([*BASE_COLUMNS, *HELPER_COLUMNS]))

MISSING_TOKENS = {
    "",
    "n/a",
    "na",
    "nan",
    "null",
    "none",
    "no informado",
    "desconocido",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reduce el dataset inmobiliario, completa con 0 las caracteristicas "
            "binarias vacias y agrega flags de calidad sin alterar el CSV fuente."
        )
    )
    parser.add_argument("--entrada", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--salida", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reporte", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--venta-ars-min",
        type=float,
        default=DEFAULT_VENTA_ARS_MIN,
        help="Umbral inferior sospechoso para ventas en ARS.",
    )
    parser.add_argument(
        "--expensas-ars-max",
        type=float,
        default=DEFAULT_EXPENSAS_ARS_MAX,
        help="Umbral superior sospechoso para expensas en ARS.",
    )
    parser.add_argument(
        "--expensas-usd-max",
        type=float,
        default=DEFAULT_EXPENSAS_USD_MAX,
        help="Umbral superior sospechoso para expensas en USD.",
    )
    parser.add_argument(
        "--solo-validar",
        action="store_true",
        help="Calcula y valida todo, pero no escribe los CSV de salida.",
    )
    return parser.parse_args()


def normalize_text(value: object) -> str:
    """Normaliza texto solo para comparaciones; nunca reemplaza el dato fuente."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value).casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def normalized_series(series: pd.Series) -> pd.Series:
    return series.map(normalize_text)


def missing_mask(series: pd.Series) -> pd.Series:
    normalized = series.fillna("").astype(str).str.strip().str.casefold()
    return normalized.isin(MISSING_TOKENS)


def fill_missing_binary_features(frame: pd.DataFrame) -> int:
    """Completa con 0 solo los amenities/caracteristicas binarias faltantes.

    Los valores ya informados no se normalizan ni se reemplazan. De esta forma,
    cualquier valor inesperado queda visible y es rechazado por la validacion en
    lugar de ser modificado silenciosamente.
    """
    filled_cells = 0
    for column in AMENITY_NAMES:
        missing = missing_mask(frame[column])
        filled_cells += int(missing.sum())
        frame.loc[missing, column] = "0"
    return filled_cells


def numeric_series(series: pd.Series) -> pd.Series:
    """Convierte una copia temporal; la columna original permanece como texto."""
    cleaned = series.fillna("").astype(str).str.strip()
    cleaned = cleaned.mask(cleaned.str.casefold().isin(MISSING_TOKENS))
    return pd.to_numeric(cleaned, errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    )


def parse_argentine_number(value: object) -> float:
    """Interpreta un importe argentino para validacion, no para correccion.

    Ejemplos: ``$1.200.000`` -> 1200000 y ``1.200,50 ARS`` -> 1200.50.
    """
    if value is None:
        return math.nan
    text = str(value).strip()
    if normalize_text(text) in MISSING_TOKENS:
        return math.nan

    match = re.search(r"[-+]?\d[\d\s\u00a0.,]*", text)
    if not match:
        return math.nan

    number = re.sub(r"[\s\u00a0]", "", match.group(0))
    sign = ""
    if number[:1] in {"-", "+"}:
        sign, number = number[0], number[1:]

    if not number:
        return math.nan

    if "." in number and "," in number:
        # Convencion argentina: punto para miles y coma para decimales.
        number = number.replace(".", "").replace(",", ".")
    elif "," in number:
        groups = number.split(",")
        if len(groups) > 2 and all(len(group) == 3 for group in groups[1:]):
            number = "".join(groups)
        else:
            number = number.replace(",", ".")
    elif "." in number:
        groups = number.split(".")
        if all(len(group) == 3 for group in groups[1:]):
            number = "".join(groups)
        elif len(groups) > 2:
            return math.nan

    try:
        return float(f"{sign}{number}")
    except ValueError:
        return math.nan


def detect_currency(value: object) -> str | None:
    """Detecta moneda solo cuando el texto raw contiene evidencia explicita."""
    if value is None:
        return None
    compact = re.sub(r"\s+", "", str(value).upper())
    if any(marker in compact for marker in ("USD", "US$", "U$S", "U$")):
        return "USD"
    if "ARS" in compact or "$" in compact:
        return "ARS"
    return None


def canonical_category(value: object) -> str:
    raw = "" if value is None else str(value).strip().casefold()
    if raw in MISSING_TOKENS:
        return ""
    normalized = normalize_text(value)
    if normalized in {"", "n a", "na", "nan", "null", "none", "no informado", "desconocido"}:
        return ""
    return normalized


def read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            return next(reader)
        except StopIteration as exc:
            raise ValueError(f"El archivo de entrada esta vacio: {path}") from exc


def validate_paths(input_path: Path, output_path: Path, report_path: Path) -> None:
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontro el archivo de entrada: {input_path}")
    if not input_path.is_file():
        raise ValueError(f"La entrada no es un archivo: {input_path}")

    resolved = [
        input_path.resolve(),
        output_path.resolve(),
        report_path.resolve(),
    ]
    if len(set(resolved)) != len(resolved):
        raise ValueError("Entrada, salida y reporte deben ser tres archivos distintos.")


def validate_thresholds(
    venta_ars_min: float, expensas_ars_max: float, expensas_usd_max: float
) -> None:
    values = {
        "--venta-ars-min": venta_ars_min,
        "--expensas-ars-max": expensas_ars_max,
        "--expensas-usd-max": expensas_usd_max,
    }
    invalid = [
        name for name, value in values.items() if not math.isfinite(value) or value <= 0
    ]
    if invalid:
        raise ValueError(
            "Los umbrales deben ser números finitos mayores que cero: "
            + ", ".join(invalid)
        )


def read_source(path: Path) -> tuple[pd.DataFrame, int]:
    header = read_header(path)
    if len(header) != len(set(header)):
        repeated = sorted({name for name in header if header.count(name) > 1})
        raise ValueError(f"Hay nombres de columnas repetidos: {repeated}")

    missing = [column for column in REQUIRED_INPUT_COLUMNS if column not in header]
    if missing:
        raise ValueError(
            "Faltan columnas necesarias en el CSV de entrada: " + ", ".join(missing)
        )

    source = pd.read_csv(
        path,
        usecols=REQUIRED_INPUT_COLUMNS,
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        encoding="utf-8-sig",
        on_bad_lines="error",
        low_memory=False,
    )
    return source, len(header)


def add_reason(
    reasons: list[list[str]], mask: pd.Series | np.ndarray, text: str
) -> None:
    values = np.asarray(mask, dtype=bool)
    for position in np.flatnonzero(values):
        row_reasons = reasons[int(position)]
        if text not in row_reasons:
            row_reasons.append(text)


def price_flag(
    source: pd.DataFrame,
    reasons: list[list[str]],
    venta_ars_min: float,
) -> pd.Series:
    price = numeric_series(source["Precio"])
    operation = source["Tipo_Operacion"].str.strip().str.casefold()
    currency = source["Moneda"].str.strip().str.upper()

    non_positive = price.notna() & price.le(0)
    sale_usd_low = (
        operation.eq("venta")
        & currency.eq("USD")
        & price.notna()
        & price.gt(0)
        & price.lt(VENTA_USD_MIN)
    )
    sale_usd_high = (
        operation.eq("venta")
        & currency.eq("USD")
        & price.notna()
        & price.gt(VENTA_USD_MAX)
    )
    sale_ars_low = (
        operation.eq("venta")
        & currency.eq("ARS")
        & price.notna()
        & price.gt(0)
        & price.lt(venta_ars_min)
    )

    parsed_raw = source["Precio_Raw"].map(parse_argentine_number).astype(float)
    comparable = parsed_raw.notna() & price.notna()
    raw_mismatch = comparable & ~pd.Series(
        np.isclose(parsed_raw, price, rtol=1e-6, atol=0.01), index=source.index
    )

    raw_currency = source["Precio_Raw"].map(detect_currency)
    currency_comparable = raw_currency.notna() & ~missing_mask(source["Moneda"])
    currency_mismatch = currency_comparable & raw_currency.ne(currency)

    add_reason(reasons, non_positive, "Precio no positivo")
    add_reason(reasons, sale_usd_low, "Venta USD menor a 10.000")
    add_reason(reasons, sale_usd_high, "Venta USD mayor a 15.000.000")
    add_reason(
        reasons,
        sale_ars_low,
        f"Venta ARS menor a {venta_ars_min:,.0f}".replace(",", "."),
    )
    add_reason(reasons, raw_mismatch, "Precio_Raw no coincide con Precio")
    add_reason(reasons, currency_mismatch, "Moneda no coincide con Precio_Raw")

    return (
        non_positive
        | sale_usd_low
        | sale_usd_high
        | sale_ars_low
        | raw_mismatch
        | currency_mismatch
    ).astype("int8")


PROPERTY_TITLE_PATTERN = (
    r"(?:departamentos?|deptos?|dptos?|casas?|ph|oficinas?|local(?:es)?|"
    r"inmueble(?:s)?|unidad(?:es)?|propiedad(?:es)?|monoambientes?|"
    r"edificios?|semipisos?|pisos?|duplex|triplex)"
)
PROPERTY_DESCRIPTION_PATTERN = (
    r"(?:departamentos?|deptos?|dptos?|casas?|ph|oficinas?|local(?:es)?|"
    r"inmueble(?:s)?|unidad(?:es)?|propiedad(?:es)?|monoambientes?|"
    r"edificios?|semipisos?|duplex|triplex)"
)
SALE_TOKEN_PATTERN = re.compile(r"\b(?:venta|vende|vendo|vender)\b")
RENT_TOKEN_PATTERN = re.compile(r"\b(?:alquiler|alquila|alquilo|alquilar)\b")
SALE_TITLE_PATTERN = re.compile(
    rf"^\s*(?:venta|vendo)\b"
    rf"|\bse\s+vende\b"
    rf"|\b(?:en|para)\s+venta\b"
    rf"|\bventa\s+de\s+{PROPERTY_TITLE_PATTERN}\b"
)
RENT_TITLE_PATTERN = re.compile(
    rf"^\s*alquiler\b"
    rf"|\bse\s+alquila\b"
    rf"|\balquilo\b"
    rf"|\b(?:en|para)\s+alquiler\b"
    rf"|\balquiler\s+de\s+{PROPERTY_TITLE_PATTERN}\b"
)
SALE_DESCRIPTION_PATTERN = re.compile(
    rf"^\s*(?:venta|vendo)\b"
    rf"|\bse\s+vende\b"
    rf"|\bventa\s+de\s+{PROPERTY_DESCRIPTION_PATTERN}\b"
    rf"|\b{PROPERTY_DESCRIPTION_PATTERN}(?:\s+[a-z0-9]+){{0,4}}\s+en\s+venta\b"
    rf"|\b(?:ofrece|ofrecemos|ofrecido|disponible)"
    rf"(?:\s+[a-z0-9]+){{0,5}}\s+(?:en|para)\s+venta\b"
)
RENT_DESCRIPTION_PATTERN = re.compile(
    rf"^\s*alquiler\b"
    rf"|\bse\s+alquila\b"
    rf"|\balquiler\s+de\s+{PROPERTY_DESCRIPTION_PATTERN}\b"
    rf"|\b{PROPERTY_DESCRIPTION_PATTERN}(?:\s+[a-z0-9]+){{0,4}}\s+en\s+alquiler\b"
    rf"|\b(?:ofrece|ofrecemos|ofrecido|disponible)"
    rf"(?:\s+[a-z0-9]+){{0,5}}\s+(?:en|para)\s+alquiler\b"
)
RENT_INVESTMENT_PATTERN = re.compile(
    r"(?:venta con renta|con renta|rentabilidad|renta asegurada|"
    r"ideal para (?:alquiler|renta)|apto para (?:alquiler|renta)|"
    r"destinad[oa] (?:al|para el) alquiler|actualmente alquilad[oa]|"
    r"contrato de alquiler vigente|dejar de alquilar)"
)
RENT_WITH_PURCHASE_PATTERN = re.compile(
    r"(?:alquiler con opcion (?:a|de) compra|opcion de compra)"
)
RENT_AS_PURPOSE_PATTERN = re.compile(
    r"(?:ideal|apto|destinad[oa]) para (?:el )?alquiler"
)


def textual_operation_signal(text: str, target: str) -> bool:
    """Busca evidencia explicita de una operacion en texto normalizado."""
    has_sale_token = bool(SALE_TOKEN_PATTERN.search(text))
    has_rent_token = bool(RENT_TOKEN_PATTERN.search(text))

    # Una publicacion que ofrece ambas modalidades no se considera contradiccion.
    if has_sale_token and has_rent_token:
        return False

    if target == "Alquiler":
        if (
            RENT_INVESTMENT_PATTERN.search(text)
            or RENT_WITH_PURCHASE_PATTERN.search(text)
            or RENT_AS_PURPOSE_PATTERN.search(text)
        ):
            return False
        return bool(RENT_TITLE_PATTERN.search(text))

    if target == "Venta":
        if RENT_WITH_PURCHASE_PATTERN.search(text):
            return False
        return bool(SALE_TITLE_PATTERN.search(text))

    return False


def operation_flag(source: pd.DataFrame, reasons: list[list[str]]) -> pd.Series:
    operations = source["Tipo_Operacion"].str.strip().str.casefold()
    titles = normalized_series(source["Titulo"])
    # Se limita el texto bruto antes y despues de normalizar para evitar avisos legales.
    descriptions = source["Descripcion"].str.slice(0, 1_000).map(normalize_text).str.slice(0, 350)

    result = np.zeros(len(source), dtype=np.int8)
    for position, (operation, title, description) in enumerate(
        zip(operations, titles, descriptions)
    ):
        title_has_sale = bool(SALE_TOKEN_PATTERN.search(title))
        title_has_rent = bool(RENT_TOKEN_PATTERN.search(title))
        title_sale_evidence = False
        title_rent_evidence = False

        # Los titulos que ofrecen ambas modalidades son validos y no se marcan.
        if not (title_has_sale and title_has_rent):
            title_sale_evidence = bool(SALE_TITLE_PATTERN.search(title))
            title_rent_evidence = bool(RENT_TITLE_PATTERN.search(title))

        title_flag = (
            operation == "venta"
            and title_rent_evidence
            and not title_sale_evidence
            and not RENT_WITH_PURCHASE_PATTERN.search(title)
            and not RENT_AS_PURPOSE_PATTERN.search(title)
        ) or (
            operation == "alquiler"
            and title_sale_evidence
            and not title_rent_evidence
        )

        description_flag = False
        # La descripcion se consulta solo cuando el titulo es totalmente neutral.
        if not title_has_sale and not title_has_rent:
            description_has_sale = bool(SALE_TOKEN_PATTERN.search(description))
            description_has_rent = bool(RENT_TOKEN_PATTERN.search(description))
            if not (description_has_sale and description_has_rent):
                description_sale_evidence = bool(
                    SALE_DESCRIPTION_PATTERN.search(description)
                )
                description_rent_evidence = bool(
                    RENT_DESCRIPTION_PATTERN.search(description)
                )
                description_flag = (
                    operation == "venta"
                    and description_rent_evidence
                    and not description_sale_evidence
                    and not RENT_WITH_PURCHASE_PATTERN.search(description)
                    and not RENT_AS_PURPOSE_PATTERN.search(description)
                ) or (
                    operation == "alquiler"
                    and description_sale_evidence
                    and not description_rent_evidence
                )

        if title_flag or description_flag:
            result[position] = 1
            source_label = "Título" if title_flag else "Descripción"
            if operation == "venta":
                reasons[position].append(
                    f"{source_label} indica Alquiler pero Tipo_Operacion es Venta"
                )
            elif operation == "alquiler":
                reasons[position].append(
                    f"{source_label} indica Venta pero Tipo_Operacion es Alquiler"
                )

    return pd.Series(result, index=source.index, dtype="int8")


def property_type_flag(source: pd.DataFrame, reasons: list[list[str]]) -> pd.Series:
    ml = source["Tipo_Propiedad_ML"].map(canonical_category)
    inferred = source["Tipo_Propiedad_Inferido"].map(canonical_category)
    comparable = ml.ne("") & inferred.ne("")
    mismatch = comparable & ml.ne(inferred)
    add_reason(
        reasons,
        mismatch,
        "Tipo_Propiedad_ML difiere de Tipo_Propiedad_Inferido",
    )
    return mismatch.astype("int8")


def surface_flag(source: pd.DataFrame, reasons: list[list[str]]) -> pd.Series:
    surfaces = {
        column: numeric_series(source[column])
        for column in SURFACE_COLUMNS_FOR_VALIDATION
    }
    total = surfaces["Superficie_Total_m2"]
    covered = surfaces["Superficie_Cubierta_m2"]

    total_non_positive = total.notna() & total.le(0)
    total_small = total.notna() & total.gt(0) & total.lt(10)
    total_large = total.notna() & total.gt(5_000)
    covered_over_total = (
        covered.notna() & total.notna() & covered.gt(total)
    )

    add_reason(reasons, total_non_positive, "Superficie total no positiva")
    add_reason(reasons, total_small, "Superficie total menor a 10 m²")
    add_reason(reasons, total_large, "Superficie total mayor a 5.000 m²")
    add_reason(
        reasons,
        covered_over_total,
        "Superficie cubierta mayor a superficie total",
    )

    negative_masks: list[pd.Series] = []
    negative_labels = {
        "Superficie_Cubierta_m2": "Superficie cubierta negativa",
        "Superficie_Semicubierta_m2": "Superficie semicubierta negativa",
        "Superficie_Descubierta_m2": "Superficie descubierta negativa",
        "Superficie_No_Cubierta_m2": "Superficie no cubierta negativa",
        "Superficie_Balcon_m2": "Superficie de balcón negativa",
    }
    for column, label in negative_labels.items():
        mask = surfaces[column].notna() & surfaces[column].lt(0)
        negative_masks.append(mask)
        add_reason(reasons, mask, label)

    result = total_non_positive | total_small | total_large | covered_over_total
    for mask in negative_masks:
        result = result | mask
    return result.astype("int8")


def rooms_flag(source: pd.DataFrame, reasons: list[list[str]]) -> pd.Series:
    rooms = numeric_series(source["Ambientes"])
    bedrooms = numeric_series(source["Dormitorios"])
    bathrooms = numeric_series(source["Baños"])

    bedrooms_over_rooms = (
        bedrooms.notna() & rooms.notna() & bedrooms.gt(rooms)
    )
    rooms_negative = rooms.notna() & rooms.lt(0)
    bedrooms_negative = bedrooms.notna() & bedrooms.lt(0)
    bathrooms_negative = bathrooms.notna() & bathrooms.lt(0)

    property_type = source["Tipo_Propiedad"].map(canonical_category)
    residential = property_type.isin({"departamento", "ph", "casa"})
    residential_zero = residential & rooms.notna() & rooms.eq(0)

    add_reason(reasons, bedrooms_over_rooms, "Dormitorios mayores a ambientes")
    add_reason(reasons, rooms_negative, "Ambientes negativos")
    add_reason(reasons, bedrooms_negative, "Dormitorios negativos")
    add_reason(reasons, bathrooms_negative, "Baños negativos")
    add_reason(reasons, residential_zero, "Ambientes cero en propiedad residencial")

    return (
        bedrooms_over_rooms
        | rooms_negative
        | bedrooms_negative
        | bathrooms_negative
        | residential_zero
    ).astype("int8")


def coordinates_flag(source: pd.DataFrame, reasons: list[list[str]]) -> pd.Series:
    latitude = numeric_series(source["Latitud"])
    longitude = numeric_series(source["Longitud"])
    complete = latitude.notna() & longitude.notna()
    outside = complete & (
        ~latitude.between(LATITUD_MIN, LATITUD_MAX, inclusive="both")
        | ~longitude.between(LONGITUD_MIN, LONGITUD_MAX, inclusive="both")
    )
    add_reason(reasons, outside, "Coordenadas fuera del área aproximada de CABA")
    return outside.astype("int8")


def expenses_flag(
    source: pd.DataFrame,
    reasons: list[list[str]],
    ars_max: float,
    usd_max: float,
) -> pd.Series:
    expenses = numeric_series(source["Expensas"])
    currency = source["Moneda_Expensas"].str.strip().str.upper()
    zero_suspicious = numeric_series(
        source["Flag_Expensas_Cero_Sospechoso"]
    ).eq(1)
    negative = expenses.notna() & expenses.lt(0)
    high_ars = currency.eq("ARS") & expenses.notna() & expenses.gt(ars_max)
    high_usd = currency.eq("USD") & expenses.notna() & expenses.gt(usd_max)

    add_reason(reasons, zero_suspicious, "Expensas cero sospechosas")
    add_reason(reasons, negative, "Expensas negativas")
    add_reason(
        reasons,
        high_ars,
        f"Expensas ARS mayores a {ars_max:,.0f}".replace(",", "."),
    )
    add_reason(
        reasons,
        high_usd,
        f"Expensas USD mayores a {usd_max:,.0f}".replace(",", "."),
    )

    return (zero_suspicious | negative | high_ars | high_usd).astype("int8")


def amenities_flag(source: pd.DataFrame, reasons: list[list[str]]) -> pd.Series:
    conflicts: list[list[str]] = [[] for _ in range(len(source))]
    result = np.zeros(len(source), dtype=bool)

    for amenity, column in AMENITY_CONFLICT_COLUMNS.items():
        mask = numeric_series(source[column]).eq(1).to_numpy(dtype=bool)
        result |= mask
        for position in np.flatnonzero(mask):
            conflicts[int(position)].append(amenity)

    for position in np.flatnonzero(result):
        names = ", ".join(conflicts[int(position)])
        reasons[int(position)].append(
            f"Conflicto ML/texto en amenities: {names}"
        )

    return pd.Series(result.astype(np.int8), index=source.index, dtype="int8")


def critical_missing_flag(
    source: pd.DataFrame, reasons: list[list[str]]
) -> pd.Series:
    # El orden determina cómo se enumeran los campos en Motivo_Anomalia.
    missing_by_field = {
        "Precio": numeric_series(source["Precio"]).isna(),
        "Moneda": missing_mask(source["Moneda"]),
        "Tipo_Operacion": missing_mask(source["Tipo_Operacion"]),
        "Tipo_Propiedad": missing_mask(source["Tipo_Propiedad"]),
        "Superficie_Total_m2": numeric_series(source["Superficie_Total_m2"]).isna(),
        "Latitud": numeric_series(source["Latitud"]).isna(),
        "Longitud": numeric_series(source["Longitud"]).isna(),
    }

    result = np.zeros(len(source), dtype=bool)
    fields_per_row: list[list[str]] = [[] for _ in range(len(source))]
    for field, mask_series in missing_by_field.items():
        mask = mask_series.to_numpy(dtype=bool)
        result |= mask
        for position in np.flatnonzero(mask):
            fields_per_row[int(position)].append(field)

    for position in np.flatnonzero(result):
        fields = ", ".join(fields_per_row[int(position)])
        reasons[int(position)].append(f"Faltante crítico: {fields}")

    return pd.Series(result.astype(np.int8), index=source.index, dtype="int8")


def process_data(
    source: pd.DataFrame,
    *,
    venta_ars_min: float,
    expensas_ars_max: float,
    expensas_usd_max: float,
) -> pd.DataFrame:
    reasons: list[list[str]] = [[] for _ in range(len(source))]
    flags = {
        "Flag_Precio_Anomalo": price_flag(source, reasons, venta_ars_min),
        "Flag_Operacion_Anomala": operation_flag(source, reasons),
        "Flag_Tipo_Propiedad_Anomalo": property_type_flag(source, reasons),
        "Flag_Superficie_Anomala": surface_flag(source, reasons),
        "Flag_Ambientes_Anomalo": rooms_flag(source, reasons),
        "Flag_Coordenadas_Anomalas": coordinates_flag(source, reasons),
        "Flag_Expensas_Anomalas": expenses_flag(
            source, reasons, expensas_ars_max, expensas_usd_max
        ),
        "Flag_Amenities_Anomalos": amenities_flag(source, reasons),
        "Flag_Faltantes_Criticos": critical_missing_flag(source, reasons),
    }

    processed = source[BASE_COLUMNS].copy()
    fill_missing_binary_features(processed)
    for column in FLAG_COLUMNS:
        processed[column] = flags[column].astype("int8")

    processed["Flag_Anomalia_General"] = (
        processed[FLAG_COLUMNS].max(axis=1).astype("int8")
    )
    processed["Motivo_Anomalia"] = [
        " | ".join(row_reasons) if row_reasons else SIN_ANOMALIAS
        for row_reasons in reasons
    ]

    return processed[OUTPUT_COLUMNS]


def add_report_row(
    rows: list[dict[str, object]],
    section: str,
    category: str,
    count: int,
    total: int,
) -> None:
    percentage = round((count / total * 100), 2) if total else 0.0
    rows.append(
        {
            "Seccion": section,
            "Categoria": category,
            "Cantidad": int(count),
            "Porcentaje_Total": percentage,
        }
    )


def ordered_counts(series: pd.Series, preferred: Sequence[str]) -> list[tuple[str, int]]:
    labels = series.astype(str).str.strip().copy()
    labels.loc[missing_mask(series)] = "No informado"
    counts = labels.value_counts(dropna=False)
    rows: list[tuple[str, int]] = []
    used: set[str] = set()
    for label in preferred:
        if label in counts.index:
            rows.append((label, int(counts[label])))
            used.add(label)
    for label in sorted(str(value) for value in counts.index if str(value) not in used):
        rows.append((label, int(counts[label])))
    return rows


def build_report(source: pd.DataFrame, processed: pd.DataFrame) -> pd.DataFrame:
    total = len(processed)
    anomalous = int(processed["Flag_Anomalia_General"].sum())
    normal = total - anomalous
    rows: list[dict[str, object]] = []

    add_report_row(rows, "Resumen", "Total de registros", total, total)
    add_report_row(rows, "Resumen", "Registros normales", normal, total)
    add_report_row(rows, "Resumen", "Registros con anomalías", anomalous, total)

    for flag in FLAG_COLUMNS:
        add_report_row(rows, "Flags", flag, int(processed[flag].sum()), total)

    for label, count in ordered_counts(
        source["Tipo_Operacion"], ["Venta", "Alquiler", "No informado"]
    ):
        add_report_row(rows, "Tipo_Operacion", label, count, total)

    for label, count in ordered_counts(
        source["Tipo_Propiedad"],
        ["Departamento", "PH", "Casa", "Oficina", "Local", "No informado"],
    ):
        add_report_row(rows, "Tipo_Propiedad", label, count, total)

    for label, count in ordered_counts(
        source["Moneda"], ["USD", "ARS", "No informado"]
    ):
        add_report_row(rows, "Moneda", label, count, total)

    return pd.DataFrame(
        rows,
        columns=["Seccion", "Categoria", "Cantidad", "Porcentaje_Total"],
    )


def validate_report(report: pd.DataFrame, processed: pd.DataFrame) -> None:
    total = len(processed)
    summary = report.loc[report["Seccion"].eq("Resumen")].set_index("Categoria")
    expected_summary = {
        "Total de registros": total,
        "Registros normales": int(processed["Flag_Anomalia_General"].eq(0).sum()),
        "Registros con anomalías": int(processed["Flag_Anomalia_General"].eq(1).sum()),
    }
    for category, expected in expected_summary.items():
        actual = int(summary.loc[category, "Cantidad"])
        if actual != expected:
            raise AssertionError(f"Resumen incorrecto para {category}: {actual}")
    if (
        expected_summary["Registros normales"]
        + expected_summary["Registros con anomalías"]
        != total
    ):
        raise AssertionError("Normales + anómalos no coincide con el total.")

    flag_rows = report.loc[report["Seccion"].eq("Flags")].set_index("Categoria")
    for flag in FLAG_COLUMNS:
        if int(flag_rows.loc[flag, "Cantidad"]) != int(processed[flag].sum()):
            raise AssertionError(f"El reporte no coincide con {flag}.")

    for section in ("Tipo_Operacion", "Tipo_Propiedad", "Moneda"):
        section_total = int(
            report.loc[report["Seccion"].eq(section), "Cantidad"].sum()
        )
        if section_total != total:
            raise AssertionError(
                f"La distribución {section} suma {section_total}, no {total}."
            )


def validate_processed(source: pd.DataFrame, processed: pd.DataFrame) -> None:
    if len(processed) != len(source):
        raise AssertionError(
            f"Se perdieron filas: entrada={len(source)}, salida={len(processed)}"
        )
    if list(processed.columns) != OUTPUT_COLUMNS:
        raise AssertionError("El orden o los nombres de las columnas de salida son incorrectos.")
    if len(processed.columns) != 67:
        raise AssertionError(f"Se esperaban 67 columnas y hay {len(processed.columns)}.")

    for column in BASE_COLUMNS:
        expected = source[column].copy()
        if column in AMENITY_NAMES:
            expected.loc[missing_mask(expected)] = "0"
        if not processed[column].equals(expected):
            raise AssertionError(f"Se modificaron valores no autorizados en {column}.")

    for column in AMENITY_NAMES:
        if missing_mask(processed[column]).any():
            raise AssertionError(f"{column} conserva valores faltantes despues del relleno.")
        values = set(processed[column].astype(str).str.strip().unique())
        if not values.issubset({"0", "1"}):
            raise AssertionError(
                f"{column} contiene valores distintos de 0/1: {sorted(values)}"
            )

    all_flags = [*FLAG_COLUMNS, "Flag_Anomalia_General"]
    for flag in all_flags:
        values = set(processed[flag].dropna().astype(int).unique())
        if not values.issubset({0, 1}):
            raise AssertionError(f"{flag} contiene valores distintos de 0/1: {values}")

    expected_general = processed[FLAG_COLUMNS].max(axis=1).astype("int8")
    if not processed["Flag_Anomalia_General"].equals(expected_general):
        raise AssertionError("Flag_Anomalia_General no coincide con los flags tematicos.")

    normal = processed["Flag_Anomalia_General"].eq(0)
    if not processed.loc[normal, "Motivo_Anomalia"].eq(SIN_ANOMALIAS).all():
        raise AssertionError("Hay registros normales con un motivo incorrecto.")
    if processed.loc[~normal, "Motivo_Anomalia"].eq(SIN_ANOMALIAS).any():
        raise AssertionError("Hay registros anomalos sin motivo.")
    for motive in processed.loc[~normal, "Motivo_Anomalia"]:
        parts = motive.split(" | ")
        if any(not part for part in parts) or len(parts) != len(set(parts)):
            raise AssertionError(f"Motivo vacío o duplicado: {motive}")


def atomic_to_csv(frame: pd.DataFrame, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.tmp"
    )
    try:
        frame.to_csv(temporary, index=False, encoding="utf-8-sig", lineterminator="\n")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def validate_written_csv(path: Path, expected_rows: int, expected_columns: list[str]) -> None:
    header = read_header(path)
    if header != expected_columns:
        raise AssertionError(f"Encabezado inesperado en {path.name}.")
    row_check = pd.read_csv(
        path,
        usecols=[expected_columns[0]],
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        encoding="utf-8-sig",
    )
    if len(row_check) != expected_rows:
        raise AssertionError(
            f"Cantidad de filas inesperada en {path.name}: {len(row_check)}"
        )


def validate_written_processed(
    path: Path, source: pd.DataFrame, processed: pd.DataFrame
) -> None:
    """Relee la salida en bloques y comprueba datos, orden, flags y motivos."""
    header = read_header(path)
    if header != OUTPUT_COLUMNS:
        raise AssertionError(f"Encabezado inesperado en {path.name}.")

    offset = 0
    for chunk in pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        encoding="utf-8-sig",
        on_bad_lines="error",
        chunksize=5_000,
    ):
        end = offset + len(chunk)
        expected_processed = processed.iloc[offset:end]

        for column in BASE_COLUMNS:
            actual = chunk[column].reset_index(drop=True)
            expected = expected_processed[column].reset_index(drop=True)
            if not actual.equals(expected):
                raise AssertionError(
                    f"La escritura alteró valores u orden en {column}, filas {offset}:{end}."
                )

        for flag in [*FLAG_COLUMNS, "Flag_Anomalia_General"]:
            actual = pd.to_numeric(chunk[flag], errors="coerce").astype("int8")
            expected = expected_processed[flag].reset_index(drop=True).astype("int8")
            actual = actual.reset_index(drop=True)
            if not actual.equals(expected):
                raise AssertionError(
                    f"La escritura alteró {flag}, filas {offset}:{end}."
                )

        actual_motive = chunk["Motivo_Anomalia"].reset_index(drop=True)
        expected_motive = expected_processed["Motivo_Anomalia"].reset_index(drop=True)
        if not actual_motive.equals(expected_motive):
            raise AssertionError(
                f"La escritura alteró Motivo_Anomalia, filas {offset}:{end}."
            )
        offset = end

    if offset != len(processed):
        raise AssertionError(
            f"La salida escrita tiene {offset} filas y se esperaban {len(processed)}."
        )


def run_self_tests() -> None:
    monetary_cases = {
        "$1.200.000": 1_200_000.0,
        "US$ 120.000": 120_000.0,
        "USD 1.200.000": 1_200_000.0,
        "US$ 78.162 , 50": 78_162.50,
        "1.200,50 ARS": 1_200.50,
        "$ 57.000": 57_000.0,
        "0 ARS": 0.0,
    }
    for raw, expected in monetary_cases.items():
        parsed = parse_argentine_number(raw)
        if not math.isclose(parsed, expected, rel_tol=1e-9, abs_tol=0.001):
            raise AssertionError(f"Parser monetario: {raw!r} -> {parsed}, no {expected}")

    currency_cases = {
        "US$ 120.000": "USD",
        "U$s 85.000": "USD",
        "$ 900.000": "ARS",
        "150.000 ARS": "ARS",
    }
    for raw, expected in currency_cases.items():
        if detect_currency(raw) != expected:
            raise AssertionError(f"Detector de moneda incorrecto para {raw!r}")

    if not textual_operation_signal("departamento en alquiler palermo", "Alquiler"):
        raise AssertionError("No se detecto una contradiccion clara de alquiler.")
    if textual_operation_signal("venta con renta departamento palermo", "Alquiler"):
        raise AssertionError("Se marco incorrectamente una venta con renta.")
    if textual_operation_signal("venta y alquiler departamento", "Alquiler"):
        raise AssertionError("Se marco incorrectamente una publicacion con ambas modalidades.")
    if textual_operation_signal("alquiler con opcion a compra", "Alquiler"):
        raise AssertionError("Se marco incorrectamente un alquiler con opción a compra.")
    if textual_operation_signal("departamento ideal para alquiler", "Alquiler"):
        raise AssertionError("Se marco incorrectamente un alquiler como destino de inversión.")


def print_summary(
    source_rows: int,
    original_columns: int,
    processed: pd.DataFrame,
    output_path: Path,
    report_path: Path,
    wrote_files: bool,
) -> None:
    anomalous = int(processed["Flag_Anomalia_General"].sum())
    normal = len(processed) - anomalous
    print("\n" + "=" * 64)
    print("PROCESAMIENTO FINALIZADO")
    print("=" * 64)
    print(f"Registros originales: {source_rows:,}".replace(",", "."))
    print(f"Registros procesados: {len(processed):,}".replace(",", "."))
    print(f"Columnas originales: {original_columns}")
    print(f"Columnas procesadas: {len(processed.columns)}")
    print(f"Registros normales: {normal:,}".replace(",", "."))
    print(f"Registros anómalos: {anomalous:,}".replace(",", "."))
    print()
    for flag in FLAG_COLUMNS:
        count = int(processed[flag].sum())
        print(f"{flag}: {count:,}".replace(",", "."))
    if wrote_files:
        print(f"\nDataset procesado: {output_path}")
        print(f"Reporte de anomalías: {report_path}")
    else:
        print("\nModo --solo-validar: no se escribieron archivos.")


def main() -> int:
    args = parse_args()
    input_path = args.entrada.expanduser().resolve()
    output_path = args.salida.expanduser().resolve()
    report_path = args.reporte.expanduser().resolve()

    validate_paths(input_path, output_path, report_path)
    validate_thresholds(
        args.venta_ars_min, args.expensas_ars_max, args.expensas_usd_max
    )
    run_self_tests()

    input_stat_before = input_path.stat()
    print(f"Leyendo: {input_path}")
    source, original_columns = read_source(input_path)
    print(
        f"Entrada cargada: {len(source):,} filas, {original_columns} columnas".replace(
            ",", "."
        )
    )

    processed = process_data(
        source,
        venta_ars_min=args.venta_ars_min,
        expensas_ars_max=args.expensas_ars_max,
        expensas_usd_max=args.expensas_usd_max,
    )
    report = build_report(source, processed)
    validate_processed(source, processed)
    validate_report(report, processed)

    input_stat_after_processing = input_path.stat()
    if (
        input_stat_before.st_size != input_stat_after_processing.st_size
        or input_stat_before.st_mtime_ns != input_stat_after_processing.st_mtime_ns
    ):
        raise RuntimeError(
            "El CSV de entrada cambio durante el procesamiento. No se escribieron salidas."
        )

    if not args.solo_validar:
        print(f"Escribiendo salida atómica: {output_path}")
        atomic_to_csv(processed, output_path)
        print(f"Escribiendo reporte atómico: {report_path}")
        atomic_to_csv(report, report_path)
        validate_written_processed(output_path, source, processed)
        validate_written_csv(report_path, len(report), list(report.columns))

    input_stat_after_write = input_path.stat()
    if (
        input_stat_before.st_size != input_stat_after_write.st_size
        or input_stat_before.st_mtime_ns != input_stat_after_write.st_mtime_ns
    ):
        raise RuntimeError("El archivo original cambio inesperadamente.")

    print_summary(
        len(source),
        original_columns,
        processed,
        output_path,
        report_path,
        not args.solo_validar,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nProcesamiento interrumpido por el usuario.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
