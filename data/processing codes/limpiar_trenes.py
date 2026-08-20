"""Limpia y normaliza el dataset de estaciones ferroviarias.

El script procesa exclusivamente el archivo ferroviario y genera una copia
normalizada. Nunca modifica el CSV original ni elimina filas.

Entrada predeterminada:
    estaciones_ferroviarias.csv

Salida predeterminada:
    tren_limpio.csv

Uso alternativo:
    python limpiar_tren.py --entrada origen.csv --salida destino.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import unicodedata
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "estaciones_ferroviarias.csv"
DEFAULT_OUTPUT = BASE_DIR / "tren_limpio.csv"

NO_INFORMADO = "No informado"
TIPO_TRANSPORTE = "Tren"

LATITUD_MIN = Decimal("-34.71")
LATITUD_MAX = Decimal("-34.52")
LONGITUD_MIN = Decimal("-58.54")
LONGITUD_MAX = Decimal("-58.33")

NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
POINT_PATTERN = re.compile(
    rf"^\s*POINT\s*\(\s*(?P<longitud>{NUMBER})\s+"
    rf"(?P<latitud>{NUMBER})\s*\)\s*$",
    re.IGNORECASE,
)

MISSING_TOKENS = {
    "",
    "nan",
    "none",
    "n/a",
    "na",
    "null",
}

REQUIRED_INPUT_COLUMNS = {
    "id",
    "idecaba",
    "nombre",
    "linea",
    "ramal",
    "barrio",
    "comuna",
    "localidad",
    "partido",
    "geometry",
}

OUTPUT_COLUMNS = [
    "ID",
    "ID_IDECABA",
    "Tipo_Transporte",
    "Nombre",
    "Linea",
    "Ramal",
    "Direccion",
    "Barrio",
    "Comuna",
    "Localidad",
    "Latitud",
    "Longitud",
    "Flag_Coordenada_Anomala",
    "Flag_Fuera_CABA",
    "Flag_Duplicado",
]

LINEAS_CANONICAS = {
    "mitre , f.c.g.b.m.": "Mitre",
    "urquiza , f.c.g.u.": "Urquiza",
    "belgrano sur , f.c.g.b.": "Belgrano Sur",
    "sarmiento , f.c.d.f.s.": "Sarmiento",
    "belgrano norte , f.c.g.b.": "Belgrano Norte",
    "roca , f.c.g.r.": "Roca",
    "san martin , f.c.g.s.m.": "San Martín",
    "tren de la costa , t.d.l.c.": "Tren de la Costa",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Limpia estaciones ferroviarias, extrae POINT (longitud latitud), "
            "normaliza columnas y agrega controles de calidad."
        )
    )
    parser.add_argument(
        "--entrada",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"CSV original (predeterminado: {DEFAULT_INPUT.name}).",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV limpio (predeterminado: {DEFAULT_OUTPUT.name}).",
    )
    return parser.parse_args()


def limpiar_texto(value: object) -> str:
    """Limpia espacios sin quitar tildes ni modificar el contenido real."""
    if value is None:
        return NO_INFORMADO

    text = unicodedata.normalize("NFC", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    if text.casefold() in MISSING_TOKENS:
        return NO_INFORMADO
    return text


def normalizar_linea(value: object) -> str:
    """Convierte las ocho etiquetas conocidas a nombres de línea canónicos."""
    cleaned = limpiar_texto(value)
    if cleaned == NO_INFORMADO:
        return cleaned
    return LINEAS_CANONICAS.get(cleaned.casefold(), cleaned)


def normalizar_decimal(value: Decimal) -> str:
    """Devuelve notación decimal, sin notación científica ni redondeos."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", "+0", ""} else text


def extraer_coordenadas(geometry: object) -> tuple[str, str, Decimal, Decimal] | None:
    """Extrae Latitud/Longitud desde WKT POINT (longitud latitud)."""
    raw = "" if geometry is None else str(geometry)
    match = POINT_PATTERN.fullmatch(raw)
    if not match:
        return None

    try:
        longitud_num = Decimal(match.group("longitud"))
        latitud_num = Decimal(match.group("latitud"))
    except InvalidOperation:
        return None

    if not longitud_num.is_finite() or not latitud_num.is_finite():
        return None

    return (
        normalizar_decimal(latitud_num),
        normalizar_decimal(longitud_num),
        latitud_num,
        longitud_num,
    )


def coordenada_fuera_de_bbox(
    latitud: Decimal | None,
    longitud: Decimal | None,
) -> int:
    """Marca coordenadas ausentes o fuera de la bounding box solicitada."""
    if latitud is None or longitud is None:
        return 1
    dentro = (
        LATITUD_MIN <= latitud <= LATITUD_MAX
        and LONGITUD_MIN <= longitud <= LONGITUD_MAX
    )
    return 0 if dentro else 1


def leer_csv(entrada: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Lee el CSV UTF-8/UTF-8-SIG y valida su estructura."""
    with entrada.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("El CSV de entrada no tiene encabezado.")

        fieldnames = [str(column) for column in reader.fieldnames]
        missing = sorted(REQUIRED_INPUT_COLUMNS.difference(fieldnames))
        if missing:
            raise ValueError(
                "Faltan columnas obligatorias en el CSV: " + ", ".join(missing)
            )

        rows: list[dict[str, str]] = []
        for file_row, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    f"Fila {file_row}: tiene más campos que el encabezado."
                )
            rows.append({column: row.get(column, "") for column in fieldnames})

    return fieldnames, rows


def normalizar_filas(source_rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    """Normaliza todas las filas sin eliminar ninguna."""
    normalized: list[dict[str, str]] = []

    for source in source_rows:
        coordinates = extraer_coordenadas(source.get("geometry"))
        if coordinates is None:
            latitud = NO_INFORMADO
            longitud = NO_INFORMADO
            latitud_num = None
            longitud_num = None
        else:
            latitud, longitud, latitud_num, longitud_num = coordinates

        outside = coordenada_fuera_de_bbox(latitud_num, longitud_num)
        normalized.append(
            {
                "ID": limpiar_texto(source.get("id")),
                "ID_IDECABA": limpiar_texto(source.get("idecaba")),
                "Tipo_Transporte": TIPO_TRANSPORTE,
                "Nombre": limpiar_texto(source.get("nombre")),
                "Linea": normalizar_linea(source.get("linea")),
                "Ramal": limpiar_texto(source.get("ramal")),
                "Direccion": NO_INFORMADO,
                "Barrio": limpiar_texto(source.get("barrio")),
                "Comuna": limpiar_texto(source.get("comuna")),
                "Localidad": limpiar_texto(source.get("localidad")),
                "Latitud": latitud,
                "Longitud": longitud,
                "Flag_Coordenada_Anomala": str(outside),
                "Flag_Fuera_CABA": str(outside),
                "Flag_Duplicado": "0",
            }
        )

    detectar_duplicados(normalized)
    return normalized


def clave_texto(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def detectar_duplicados(rows: list[dict[str, str]]) -> None:
    """Marca ID repetido o coincidencia exacta Nombre+Latitud+Longitud."""
    id_counts = Counter(
        row["ID"] for row in rows if row["ID"] != NO_INFORMADO
    )
    location_keys = [
        (
            clave_texto(row["Nombre"]),
            row["Latitud"],
            row["Longitud"],
        )
        for row in rows
        if row["Nombre"] != NO_INFORMADO
        and row["Latitud"] != NO_INFORMADO
        and row["Longitud"] != NO_INFORMADO
    ]
    location_counts = Counter(location_keys)

    for row in rows:
        key = (
            clave_texto(row["Nombre"]),
            row["Latitud"],
            row["Longitud"],
        )
        duplicated_id = (
            row["ID"] != NO_INFORMADO and id_counts[row["ID"]] > 1
        )
        duplicated_location = (
            row["Nombre"] != NO_INFORMADO
            and row["Latitud"] != NO_INFORMADO
            and row["Longitud"] != NO_INFORMADO
            and location_counts[key] > 1
        )
        row["Flag_Duplicado"] = "1" if duplicated_id or duplicated_location else "0"


def validar_resultado(
    source_rows: list[dict[str, str]],
    output_rows: list[dict[str, str]],
) -> None:
    """Comprueba que no haya pérdida de filas ni errores de esquema."""
    if len(output_rows) != len(source_rows):
        raise ValueError(
            "La cantidad final de filas no coincide con la cantidad original."
        )

    for row_number, (source, output) in enumerate(
        zip(source_rows, output_rows, strict=True),
        start=2,
    ):
        if list(output) != OUTPUT_COLUMNS:
            raise ValueError(f"Fila {row_number}: esquema final inesperado.")
        if output["ID"] != limpiar_texto(source.get("id")):
            raise ValueError(f"Fila {row_number}: se modificó el ID original.")
        if output["ID_IDECABA"] != limpiar_texto(source.get("idecaba")):
            raise ValueError(f"Fila {row_number}: se modificó ID_IDECABA.")
        for flag in (
            "Flag_Coordenada_Anomala",
            "Flag_Fuera_CABA",
            "Flag_Duplicado",
        ):
            if output[flag] not in {"0", "1"}:
                raise ValueError(
                    f"Fila {row_number}: {flag} debe contener solamente 0 o 1."
                )
        if (output["Latitud"] == NO_INFORMADO) != (
            output["Longitud"] == NO_INFORMADO
        ):
            raise ValueError(
                f"Fila {row_number}: Latitud y Longitud no forman un par."
            )


def escribir_csv_atomico(salida: Path, rows: list[dict[str, str]]) -> None:
    """Escribe UTF-8-SIG en temporal y reemplaza la salida al finalizar."""
    salida.parent.mkdir(parents=True, exist_ok=True)
    temporary = salida.with_name(f".{salida.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=OUTPUT_COLUMNS,
                lineterminator="\n",
                extrasaction="raise",
            )
            writer.writeheader()
            writer.writerows(rows)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, salida)
    finally:
        temporary.unlink(missing_ok=True)


def porcentaje_faltantes(rows: list[dict[str, str]], column: str) -> float:
    if not rows:
        return 0.0
    missing = sum(row[column] == NO_INFORMADO for row in rows)
    return 100.0 * missing / len(rows)


def imprimir_reporte(
    entrada: Path,
    salida: Path,
    input_columns: list[str],
    source_rows: list[dict[str, str]],
    output_rows: list[dict[str, str]],
) -> None:
    with_latitude = sum(row["Latitud"] != NO_INFORMADO for row in output_rows)
    with_longitude = sum(row["Longitud"] != NO_INFORMADO for row in output_rows)
    anomalous = sum(row["Flag_Coordenada_Anomala"] == "1" for row in output_rows)
    outside = sum(row["Flag_Fuera_CABA"] == "1" for row in output_rows)
    duplicates = sum(row["Flag_Duplicado"] == "1" for row in output_rows)

    print("\nREPORTE DE CALIDAD - TREN")
    print("=" * 30)
    print(f"Archivo original: {entrada}")
    print(f"Archivo limpio:   {salida}")
    print(f"Filas originales: {len(source_rows)}")
    print(f"Filas finales:    {len(output_rows)}")
    print(f"Columnas originales: {len(input_columns)}")
    print(f"Columnas finales:    {len(OUTPUT_COLUMNS)}")
    print(f"Con Latitud:  {with_latitude}")
    print(f"Con Longitud: {with_longitude}")
    print(f"Coordenadas anómalas: {anomalous}")
    print(f"Fuera de bbox CABA:   {outside}")
    print(f"Posibles duplicados:  {duplicates}")
    print("\nPorcentaje de faltantes por columna:")
    for column in OUTPUT_COLUMNS:
        print(f"  {column}: {porcentaje_faltantes(output_rows, column):.2f}%")


def procesar_tren(entrada: Path, salida: Path) -> list[dict[str, str]]:
    entrada = entrada.expanduser().resolve()
    salida = salida.expanduser().resolve()

    if not entrada.is_file():
        raise FileNotFoundError(f"No se encontró el CSV de entrada: {entrada}")
    if entrada == salida:
        raise ValueError("La salida debe ser distinta del archivo original.")

    input_columns, source_rows = leer_csv(entrada)
    output_rows = normalizar_filas(source_rows)
    validar_resultado(source_rows, output_rows)
    escribir_csv_atomico(salida, output_rows)
    imprimir_reporte(
        entrada,
        salida,
        input_columns,
        source_rows,
        output_rows,
    )
    return output_rows


def main() -> int:
    args = parse_args()
    procesar_tren(args.entrada, args.salida)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
