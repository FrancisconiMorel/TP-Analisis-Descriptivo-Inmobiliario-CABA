#!/usr/bin/env python3
"""Limpia y normaliza el dataset de estaciones de subte de CABA.

No calcula distancias ni modifica el archivo original. Convierte la geometria
WKT ``POINT (longitud latitud)`` en columnas decimales separadas y genera
``subte_limpio.csv``.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "estaciones_de_subte.csv"
DEFAULT_OUTPUT = BASE_DIR / "subte_limpio.csv"

OUTPUT_COLUMNS = [
    "ID",
    "Tipo_Transporte",
    "Nombre",
    "Linea",
    "Direccion",
    "Barrio",
    "Comuna",
    "Latitud",
    "Longitud",
    "Flag_Coordenada_Anomala",
    "Flag_Duplicado",
]

NO_INFORMADO = "No informado"
MISSING_TOKENS = {"", "n/a", "na", "nan", "none", "null", "no informado"}

LATITUD_MIN = -34.71
LATITUD_MAX = -34.52
LONGITUD_MIN = -58.54
LONGITUD_MAX = -58.33

NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
POINT_PATTERN = re.compile(
    rf"^\s*POINT\s*\(\s*(?P<longitud>{NUMBER})\s+"
    rf"(?P<latitud>{NUMBER})\s*\)\s*$",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Limpia estaciones de subte y separa Latitud/Longitud."
    )
    parser.add_argument("--entrada", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--salida", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def limpiar_texto(value: object, faltante: str = NO_INFORMADO) -> str:
    """Recorta y colapsa espacios sin quitar tildes ni cambiar nombres."""
    text = re.sub(r"\s+", " ", "" if value is None else str(value)).strip()
    return faltante if text.casefold() in MISSING_TOKENS else text


def extraer_coordenadas(geometry: str) -> tuple[str, str, int]:
    """Devuelve Latitud, Longitud y flag; WKT usa primero longitud."""
    match = POINT_PATTERN.fullmatch(geometry or "")
    if not match:
        return NO_INFORMADO, NO_INFORMADO, 1

    latitud = match.group("latitud")
    longitud = match.group("longitud")
    try:
        latitud_num = float(latitud)
        longitud_num = float(longitud)
    except ValueError:
        return NO_INFORMADO, NO_INFORMADO, 1

    anomalous = not (
        LATITUD_MIN <= latitud_num <= LATITUD_MAX
        and LONGITUD_MIN <= longitud_num <= LONGITUD_MAX
    )
    return latitud, longitud, int(anomalous)


def normalizar_columnas(row: dict[str, str]) -> dict[str, str | int]:
    latitud, longitud, flag_coordenada = extraer_coordenadas(
        row.get("geometry", "")
    )
    return {
        "ID": limpiar_texto(row.get("id")),
        "Tipo_Transporte": "Subte",
        "Nombre": limpiar_texto(row.get("estacion")),
        "Linea": limpiar_texto(row.get("linea")).upper(),
        "Direccion": NO_INFORMADO,
        "Barrio": NO_INFORMADO,
        "Comuna": NO_INFORMADO,
        "Latitud": latitud,
        "Longitud": longitud,
        "Flag_Coordenada_Anomala": flag_coordenada,
        "Flag_Duplicado": 0,
    }


def detectar_duplicados(rows: list[dict[str, str | int]]) -> None:
    """Marca ID repetido o coincidencia exacta Nombre+Latitud+Longitud."""
    ids = Counter(str(row["ID"]).casefold() for row in rows)
    keys = Counter(
        (
            str(row["Nombre"]).casefold(),
            str(row["Latitud"]),
            str(row["Longitud"]),
        )
        for row in rows
        if row["Latitud"] != NO_INFORMADO and row["Longitud"] != NO_INFORMADO
    )
    for row in rows:
        key = (
            str(row["Nombre"]).casefold(),
            str(row["Latitud"]),
            str(row["Longitud"]),
        )
        repeated_id = row["ID"] != NO_INFORMADO and ids[str(row["ID"]).casefold()] > 1
        repeated_key = key in keys and keys[key] > 1
        row["Flag_Duplicado"] = int(repeated_id or repeated_key)


def leer_y_procesar(path: Path) -> tuple[list[dict[str, str | int]], int]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"id", "estacion", "linea", "geometry"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            missing = sorted(required - set(reader.fieldnames or []))
            raise ValueError(f"Faltan columnas obligatorias: {', '.join(missing)}")
        original_columns = len(reader.fieldnames)
        rows = [normalizar_columnas(row) for row in reader]

    detectar_duplicados(rows)
    return rows, original_columns


def escribir_atomico(
    rows: list[dict[str, str | int]], destination: Path
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=OUTPUT_COLUMNS, lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def validar_salida(path: Path, expected_rows: int) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != OUTPUT_COLUMNS:
            raise AssertionError("El encabezado del CSV limpio es incorrecto.")
        rows = list(reader)
    if len(rows) != expected_rows:
        raise AssertionError("La salida no conserva la cantidad de filas.")
    for row_number, row in enumerate(rows, start=2):
        if any(str(row[column]).strip() == "" for column in OUTPUT_COLUMNS):
            raise AssertionError(f"Fila {row_number}: quedaron celdas vacias.")
        if row["Flag_Coordenada_Anomala"] not in {"0", "1"}:
            raise AssertionError(f"Fila {row_number}: flag de coordenada invalido.")
        if row["Flag_Duplicado"] not in {"0", "1"}:
            raise AssertionError(f"Fila {row_number}: flag de duplicado invalido.")


def imprimir_reporte(
    rows: list[dict[str, str | int]], original_columns: int
) -> None:
    total = len(rows)
    print("\nREPORTE DE CALIDAD - SUBTE")
    print(f"Filas originales/finales: {total}/{total}")
    print(f"Columnas originales/finales: {original_columns}/{len(OUTPUT_COLUMNS)}")
    print(f"Con Latitud: {sum(row['Latitud'] != NO_INFORMADO for row in rows)}")
    print(f"Con Longitud: {sum(row['Longitud'] != NO_INFORMADO for row in rows)}")
    print(
        "Coordenadas anomalas: "
        f"{sum(int(row['Flag_Coordenada_Anomala']) for row in rows)}"
    )
    print(
        "Posibles duplicados: "
        f"{sum(int(row['Flag_Duplicado']) for row in rows)}"
    )
    print("Faltantes por columna (No informado):")
    for column in OUTPUT_COLUMNS:
        missing = sum(row[column] == NO_INFORMADO for row in rows)
        percentage = (missing / total * 100) if total else 0
        print(f"  {column}: {missing} ({percentage:.2f}%)")


def main() -> int:
    args = parse_args()
    source = args.entrada.expanduser().resolve()
    destination = args.salida.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"No se encontro el archivo: {source}")
    if source == destination:
        raise ValueError("La salida debe ser distinta del archivo original.")

    source_stat = source.stat()
    rows, original_columns = leer_y_procesar(source)
    escribir_atomico(rows, destination)
    validar_salida(destination, len(rows))
    if source.stat() != source_stat:
        raise RuntimeError("El archivo original cambio durante el procesamiento.")

    imprimir_reporte(rows, original_columns)
    print(f"\nCSV generado: {destination}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
