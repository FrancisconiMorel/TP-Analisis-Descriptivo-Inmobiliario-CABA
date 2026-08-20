"""Unifica los delitos 2023-2025 y excluye coordenadas inválidas.

El script conserva todos los campos analíticos originales, normaliza sus
nombres y genera dos archivos:

* delitos_2023_2025_unificado_limpio.csv: registros aptos para análisis.
* delitos_coordenadas_descartadas.csv: registros excluidos y su motivo.

No intenta corregir, geocodificar ni inventar coordenadas, barrios o comunas.
Tampoco elimina coincidencias entre hechos distintos cuando sus ID son únicos.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sys
import tempfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable


SOURCE_COLUMNS = [
    "id-mapa",
    "anio",
    "mes",
    "dia",
    "fecha",
    "franja",
    "tipo",
    "subtipo",
    "uso_arma",
    "uso_moto",
    "barrio",
    "comuna",
    "latitud",
    "longitud",
    "cantidad",
]

OUTPUT_COLUMNS = [
    "Fuente_Archivo",
    "ID_Delito",
    "Anio",
    "Mes",
    "Dia_Semana",
    "Fecha",
    "Franja_Horaria",
    "Tipo_Delito",
    "Subtipo_Delito",
    "Uso_Arma",
    "Uso_Moto",
    "Barrio",
    "Comuna",
    "Latitud",
    "Longitud",
    "Cantidad",
]

REJECTED_COLUMNS = OUTPUT_COLUMNS + ["Motivo_Descarte"]

COLUMN_MAP = {
    "ID_Delito": "id-mapa",
    "Anio": "anio",
    "Mes": "mes",
    "Dia_Semana": "dia",
    "Fecha": "fecha",
    "Franja_Horaria": "franja",
    "Tipo_Delito": "tipo",
    "Subtipo_Delito": "subtipo",
    "Uso_Arma": "uso_arma",
    "Uso_Moto": "uso_moto",
    "Barrio": "barrio",
    "Comuna": "comuna",
    "Latitud": "latitud",
    "Longitud": "longitud",
    "Cantidad": "cantidad",
}

MISSING_TOKENS = {"", "NULL", "N/A", "NA", "NAN", "NONE"}

# Sobre geográfico conservador de CABA. Es un control de calidad, no un
# sustituto de los polígonos oficiales de barrios o comunas.
DEFAULT_LAT_MIN = Decimal("-34.71")
DEFAULT_LAT_MAX = Decimal("-34.52")
DEFAULT_LON_MIN = Decimal("-58.532")
DEFAULT_LON_MAX = Decimal("-58.33")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_missing(value: object) -> bool:
    return str(value if value is not None else "").strip().upper() in MISSING_TOKENS


def clean_text(value: object) -> str:
    text = str(value if value is not None else "").strip()
    return "No informado" if text.upper() in MISSING_TOKENS else text


def parse_decimal(value: object) -> Decimal | None:
    text = str(value if value is not None else "").strip()
    if text.upper() in MISSING_TOKENS:
        return None
    try:
        number = Decimal(text.replace(",", "."))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def decimal_as_plain_text(number: Decimal) -> str:
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def coordinate_result(
    row: dict[str, str],
    lat_min: Decimal,
    lat_max: Decimal,
    lon_min: Decimal,
    lon_max: Decimal,
) -> tuple[str | None, Decimal | None, Decimal | None]:
    raw_lat = row.get("latitud", "")
    raw_lon = row.get("longitud", "")

    if is_missing(raw_lat) or is_missing(raw_lon):
        return "Coordenadas no informadas", None, None

    lat = parse_decimal(raw_lat)
    lon = parse_decimal(raw_lon)
    if lat is None or lon is None:
        return "Coordenadas no numéricas o no finitas", None, None
    if lat == 0 or lon == 0:
        return "Coordenadas cero", lat, lon
    if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
        return "Coordenadas fuera de los límites de CABA", lat, lon
    return None, lat, lon


def normalized_row(
    row: dict[str, str],
    source_name: str,
    lat: Decimal | None,
    lon: Decimal | None,
    preserve_raw: bool = False,
) -> dict[str, str]:
    result = {"Fuente_Archivo": source_name}
    for output_name, source_name_column in COLUMN_MAP.items():
        value = row.get(source_name_column, "")
        result[output_name] = str(value if value is not None else "") if preserve_raw else clean_text(value)

    # En el archivo de descartados se conservan las coordenadas exactamente
    # como aparecían en la fuente para mantener la trazabilidad del error.
    if not preserve_raw and lat is not None:
        result["Latitud"] = decimal_as_plain_text(lat)
    if not preserve_raw and lon is not None:
        result["Longitud"] = decimal_as_plain_text(lon)
    return result


def create_temp_path(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    return Path(temp_name)


def validate_source(reader: csv.DictReader, source: Path) -> None:
    if reader.fieldnames != SOURCE_COLUMNS:
        raise ValueError(
            f"{source.name}: columnas inesperadas. "
            f"Esperadas={SOURCE_COLUMNS}; encontradas={reader.fieldnames}"
        )


def validate_output(
    path: Path,
    expected_rows: int,
    lat_min: Decimal,
    lat_max: Decimal,
    lon_min: Decimal,
    lon_max: Decimal,
) -> set[str]:
    seen_ids: set[str] = set()
    rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != OUTPUT_COLUMNS:
            raise ValueError("La salida limpia no tiene el esquema esperado")

        for row in reader:
            rows += 1
            item_id = row["ID_Delito"]
            if item_id in seen_ids:
                raise ValueError(f"ID_Delito duplicado en la salida: {item_id}")
            seen_ids.add(item_id)

            lat = parse_decimal(row["Latitud"])
            lon = parse_decimal(row["Longitud"])
            if lat is None or lon is None:
                raise ValueError(f"Coordenada no numérica en ID {item_id}")
            if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
                raise ValueError(f"Coordenada fuera de CABA en ID {item_id}")
            if row["Tipo_Delito"] == "No informado" or row["Subtipo_Delito"] == "No informado":
                raise ValueError(f"Tipo o subtipo ausente en ID {item_id}")

    if rows != expected_rows:
        raise ValueError(f"Filas finales: se esperaban {expected_rows} y se encontraron {rows}")
    return seen_ids


def validate_rejected_output(path: Path, expected_rows: int) -> set[str]:
    valid_reasons = {
        "Coordenadas no informadas",
        "Coordenadas no numéricas o no finitas",
        "Coordenadas cero",
        "Coordenadas fuera de los límites de CABA",
    }
    seen_ids: set[str] = set()
    rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != REJECTED_COLUMNS:
            raise ValueError(f"{path.name}: esquema inesperado")
        for row in reader:
            rows += 1
            item_id = row["ID_Delito"]
            if not item_id or item_id in seen_ids:
                raise ValueError(f"ID vacío o duplicado en descartados: {item_id!r}")
            seen_ids.add(item_id)
            if row["Motivo_Descarte"] not in valid_reasons:
                raise ValueError(
                    f"Motivo de descarte inesperado en ID {item_id}: {row['Motivo_Descarte']!r}"
                )

    if rows != expected_rows:
        raise ValueError(
            f"Filas descartadas: se esperaban {expected_rows} y se encontraron {rows}"
        )
    return seen_ids


def process(
    sources: Iterable[tuple[int, Path]],
    output: Path,
    rejected_output: Path,
    lat_min: Decimal,
    lat_max: Decimal,
    lon_min: Decimal,
    lon_max: Decimal,
) -> tuple[dict[int, Counter[str]], int, int]:
    sources = list(sources)
    if output.resolve() == rejected_output.resolve():
        raise ValueError("La salida limpia y la salida de descartados deben ser distintas")

    for destination in (output, rejected_output):
        if destination.exists() and not destination.is_file():
            raise ValueError(f"El destino existe y no es un archivo: {destination}")

    input_paths = {path.resolve() for _, path in sources}
    if output.resolve() in input_paths or rejected_output.resolve() in input_paths:
        raise ValueError("Una salida no puede sobrescribir un archivo de entrada")

    for expected_year, source in sources:
        if not source.is_file():
            raise FileNotFoundError(f"No se encontró {source}")
        if expected_year not in (2023, 2024, 2025):
            raise ValueError(f"Año no admitido: {expected_year}")

    original_hashes = {path: sha256(path) for _, path in sources}
    stats: dict[int, Counter[str]] = {year: Counter() for year, _ in sources}
    seen_ids: set[str] = set()
    temp_output: Path | None = None
    temp_rejected: Path | None = None

    try:
        temp_output = create_temp_path(output)
        temp_rejected = create_temp_path(rejected_output)
        with (
            temp_output.open("w", encoding="utf-8-sig", newline="") as clean_file,
            temp_rejected.open("w", encoding="utf-8-sig", newline="") as rejected_file,
        ):
            clean_writer = csv.DictWriter(clean_file, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
            rejected_writer = csv.DictWriter(
                rejected_file, fieldnames=REJECTED_COLUMNS, lineterminator="\n"
            )
            clean_writer.writeheader()
            rejected_writer.writeheader()

            for expected_year, source in sources:
                with source.open("r", encoding="utf-8-sig", newline="") as source_file:
                    reader = csv.DictReader(source_file)
                    validate_source(reader, source)

                    for line_number, row in enumerate(reader, start=2):
                        stats[expected_year]["originales"] += 1
                        if None in row or any(value is None for value in row.values()):
                            raise ValueError(f"{source.name}:{line_number}: fila CSV malformada")

                        if clean_text(row["anio"]) != str(expected_year):
                            raise ValueError(
                                f"{source.name}:{line_number}: año {row['anio']!r} no coincide con {expected_year}"
                            )

                        item_id = clean_text(row["id-mapa"])
                        if item_id == "No informado":
                            raise ValueError(f"{source.name}:{line_number}: ID no informado")
                        if item_id in seen_ids:
                            raise ValueError(f"ID duplicado entre archivos: {item_id}")
                        seen_ids.add(item_id)

                        reason, lat, lon = coordinate_result(
                            row, lat_min, lat_max, lon_min, lon_max
                        )
                        if reason is not None:
                            rejected = normalized_row(
                                row, source.name, lat, lon, preserve_raw=True
                            )
                            rejected["Motivo_Descarte"] = reason
                            rejected_writer.writerow(rejected)
                            stats[expected_year]["descartadas"] += 1
                            stats[expected_year][reason] += 1
                            continue

                        clean_writer.writerow(normalized_row(row, source.name, lat, lon))
                        stats[expected_year]["conservadas"] += 1

            clean_file.flush()
            rejected_file.flush()
            os.fsync(clean_file.fileno())
            os.fsync(rejected_file.fileno())

        total_clean = sum(counter["conservadas"] for counter in stats.values())
        total_rejected = sum(counter["descartadas"] for counter in stats.values())
        clean_ids = validate_output(
            temp_output, total_clean, lat_min, lat_max, lon_min, lon_max
        )
        rejected_ids = validate_rejected_output(temp_rejected, total_rejected)
        if clean_ids & rejected_ids:
            raise ValueError("Hay ID presentes tanto en el limpio como en descartados")
        if clean_ids | rejected_ids != seen_ids:
            raise ValueError("La unión de las salidas no coincide con los ID de las fuentes")

        for path, original_hash in original_hashes.items():
            if sha256(path) != original_hash:
                raise RuntimeError(f"El archivo original cambió durante el procesamiento: {path}")

        os.chmod(temp_output, 0o644)
        os.chmod(temp_rejected, 0o644)
        os.replace(temp_rejected, rejected_output)
        os.replace(temp_output, output)
        return stats, total_clean, total_rejected
    except Exception:
        if temp_output is not None:
            temp_output.unlink(missing_ok=True)
        if temp_rejected is not None:
            temp_rejected.unlink(missing_ok=True)
        raise


def positive_bounds(args: argparse.Namespace) -> None:
    if not args.lat_min < args.lat_max:
        raise ValueError("lat-min debe ser menor que lat-max")
    if not args.lon_min < args.lon_max:
        raise ValueError("lon-min debe ser menor que lon-max")
    if not (Decimal("-90") <= args.lat_min < args.lat_max <= Decimal("90")):
        raise ValueError("Los límites de latitud deben estar entre -90 y 90")
    if not (Decimal("-180") <= args.lon_min < args.lon_max <= Decimal("180")):
        raise ValueError("Los límites de longitud deben estar entre -180 y 180")


def build_parser(base_dir: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unifica delitos 2023-2025 y excluye coordenadas inválidas."
    )
    parser.add_argument("--entrada-2023", type=Path, default=base_dir / "delitos_2023.csv")
    parser.add_argument("--entrada-2024", type=Path, default=base_dir / "delitos_2024.csv")
    parser.add_argument("--entrada-2025", type=Path, default=base_dir / "delitos_2025.csv")
    parser.add_argument(
        "--salida",
        type=Path,
        default=base_dir / "delitos_2023_2025_unificado_limpio.csv",
    )
    parser.add_argument(
        "--descartados",
        type=Path,
        default=base_dir / "delitos_coordenadas_descartadas.csv",
    )
    parser.add_argument("--lat-min", type=Decimal, default=DEFAULT_LAT_MIN)
    parser.add_argument("--lat-max", type=Decimal, default=DEFAULT_LAT_MAX)
    parser.add_argument("--lon-min", type=Decimal, default=DEFAULT_LON_MIN)
    parser.add_argument("--lon-max", type=Decimal, default=DEFAULT_LON_MAX)
    return parser


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    args = build_parser(base_dir).parse_args()
    try:
        positive_bounds(args)
        sources = [
            (2023, args.entrada_2023.resolve()),
            (2024, args.entrada_2024.resolve()),
            (2025, args.entrada_2025.resolve()),
        ]
        stats, total_clean, total_rejected = process(
            sources,
            args.salida.resolve(),
            args.descartados.resolve(),
            args.lat_min,
            args.lat_max,
            args.lon_min,
            args.lon_max,
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("\n=== Reporte de limpieza y unificación de delitos ===")
    for year in (2023, 2024, 2025):
        counter = stats[year]
        print(
            f"{year}: originales={counter['originales']:,} | "
            f"conservadas={counter['conservadas']:,} | "
            f"descartadas={counter['descartadas']:,}"
        )
        for reason in sorted(
            key for key in counter if key not in {"originales", "conservadas", "descartadas"}
        ):
            print(f"  - {reason}: {counter[reason]:,}")

    print(f"Total limpio: {total_clean:,}")
    print(f"Total descartado: {total_rejected:,}")
    print(f"CSV limpio: {args.salida.resolve()}")
    print(f"Auditoría de descartados: {args.descartados.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
