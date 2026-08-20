"""Filtra espacios verdes familiares y calcula coordenadas centrales.

Genera:

* espacios_verdes_familiares_limpio.csv
* espacios_verdes_excluidos_revision.csv

La geometría original está expresada como WKT en coordenadas longitud/latitud.
Para obtener un centro geométricamente correcto se proyecta temporalmente a
EPSG:32721 (UTM 21S). Si el centroide cae fuera de una geometría cóncava o
multipartita, el pin final se reemplaza por un punto interno del componente
principal. El centroide original también se conserva para trazabilidad.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
import re
import sys
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path

# Algunas geometrías WKT superan ampliamente el límite predeterminado del
# módulo csv (131.072 caracteres).
csv.field_size_limit(min(sys.maxsize, 2_147_483_647))

try:
    from pyproj import Transformer
    from pyproj.exceptions import ProjError
    from shapely import make_valid, wkt
    from shapely.errors import GEOSException
    from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
    from shapely.ops import transform, unary_union
except ImportError as error:  # pragma: no cover - mensaje para ejecución manual
    raise SystemExit(
        "Faltan dependencias geoespaciales. Ejecutá: "
        ".venv-properati/bin/pip install -r requirements_espacios_verdes.txt"
    ) from error


SOURCE_COLUMNS = [
    "id",
    "nombre",
    "nom_mapa",
    "barrio",
    "comuna",
    "ubicacion",
    "clasificac",
    "tiene_pati",
    "apadrinada",
    "decreto",
    "fecha_decr",
    "ordenanza_",
    "fecha_orde",
    "boletin_of",
    "fecha_bole",
    "area",
    "perimetro",
    "observacio",
    "geometry",
]

OUTPUT_COLUMNS = [
    "ID_Espacio_Verde",
    "Nombre",
    "Nombre_Mapa",
    "Tipo_Espacio",
    "Clasificacion_Original",
    "Acceso",
    "Direccion",
    "Barrio",
    "Comuna",
    "Tiene_Patio_Juegos",
    "Superficie_m2",
    "Perimetro_m",
    "Latitud",
    "Longitud",
    "Latitud_Centroide",
    "Longitud_Centroide",
    "Metodo_Coordenada",
    "Flag_Centroide_Fuera_Geometria",
    "Distancia_Centroide_Pin_m",
    "Flag_Geometria_Reparada",
    "Cantidad_Partes_Geometria",
    "Flag_Revision_Manual",
    "Motivo_Revision",
    "Criterio_Inclusion",
    "CRS_Coordenadas",
    "Fuente_Archivo",
]

EXCLUDED_COLUMNS = [
    "ID_Espacio_Verde",
    "Nombre",
    "Nombre_Mapa",
    "Clasificacion_Original",
    "Direccion",
    "Barrio",
    "Comuna",
    "Tiene_Patio_Juegos",
    "Superficie_m2",
    "Perimetro_m",
    "Motivo_Exclusion",
    "Flag_Candidato_Revision",
    "Fuente_Archivo",
]

MISSING_TOKENS = {"", "NULL", "N/A", "NA", "NAN", "NONE"}

TYPE_LABELS = {
    "PLAZA": "Plaza",
    "PARQUE": "Parque",
    "PARQUE SEMIPÚBLICO": "Reserva ecológica",
    "JARDÍN BOTÁNICO": "Jardín botánico",
    "JARDÍN": "Jardín o paseo verde",
}

# Conflictos claros: la clasificación dice PLAZA, pero el nombre describe un
# equipamiento deportivo/duro y no un espacio verde familiar independiente.
PLAZA_CONFLICT_PATTERN = re.compile(
    r"\b(?:canch(?:a|ita)s?|patio|playon|club)\b|"
    r"\b(?:plaza|pza\.?)[ ]+seca\b|\bcentro[ ]+medico\b",
    re.IGNORECASE,
)

EXPLICIT_EXCLUSION_IDS = {
    "1354": "Buenos Aires Polo Circo: predio cultural, no plaza verde independiente",
    "1537": "Lago de Regatas: cuerpo de agua, no espacio verde transitable independiente",
}

AMBIGUOUS_SELECTED_IDS = {
    "6": "Polideportivo Colegiales: confirmar proporción de espacio verde y acceso familiar",
    "664": "Ciudad del Rock: confirmar uso familiar habitual",
    "1341": "Parque Polideportivo Julio A. Roca: confirmar proporción de espacio verde",
    "1444": "Jardín Japonés: confirmar condiciones de acceso",
    "1544": "Centro Recreativo Deportivo Villa 15: confirmar proporción de espacio verde",
    "1313": "Ciudad Universitaria: confirmar acceso y delimitación",
    "2114": "Barrio Cardenal Copello: confirmar si representa una única plaza independiente",
    "2131": "Barrio Los Perales: confirmar si representa una única plaza independiente",
    "2397": "Parque Salguero/Costa Salguero: confirmar acceso y uso",
}

LAT_MIN, LAT_MAX = -34.72, -34.52
LON_MIN, LON_MAX = -58.532, -58.32


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_spaces(value: object) -> str:
    return " ".join(str(value if value is not None else "").split())


def clean_text(value: object) -> str:
    text = normalize_spaces(value)
    return "No informado" if text.upper() in MISSING_TOKENS else text


def normalize_for_match(value: object) -> str:
    text = normalize_spaces(value)
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def parse_positive_float(value: object, field: str, item_id: str) -> float:
    try:
        result = float(str(value).strip().replace(",", "."))
    except ValueError as error:
        raise ValueError(f"ID {item_id}: {field} no es numérico: {value!r}") from error
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"ID {item_id}: {field} no es finito o es negativo")
    return result


def source_name(row: dict[str, str]) -> str:
    primary = clean_text(row["nombre"])
    if primary != "No informado":
        return primary
    return clean_text(row["nom_mapa"])


def combined_name(row: dict[str, str]) -> str:
    return normalize_for_match(f"{row['nombre']} {row['nom_mapa']}")


def inclusion_decision(
    row: dict[str, str], area_m2: float, park_min: float, garden_min: float
) -> tuple[bool, str]:
    category = clean_text(row["clasificac"]).upper()
    name_text = combined_name(row)
    has_name = source_name(row) != "No informado"
    has_playground = clean_text(row["tiene_pati"]).upper() == "SI"
    item_id = clean_text(row["id"])

    if item_id in EXPLICIT_EXCLUSION_IDS:
        return False, EXPLICIT_EXCLUSION_IDS[item_id]

    if category == "PLAZA":
        if PLAZA_CONFLICT_PATTERN.search(name_text):
            return False, "Plaza con evidencia textual de cancha, patio, playón, club o plaza seca"
        return True, "Plaza según clasificación oficial, sin conflicto textual"

    if category == "PARQUE":
        if area_m2 < park_min:
            return False, f"Subcomponente PARQUE menor a {park_min:,.0f} m²"
        return True, f"Parque según clasificación oficial y superficie >= {park_min:,.0f} m²"

    if category == "JARDÍN BOTÁNICO":
        return True, "Jardín botánico de uso recreativo y educativo"

    if category == "JARDÍN":
        if has_name and (area_m2 >= garden_min or has_playground):
            return True, (
                f"Jardín identificado con superficie >= {garden_min:,.0f} m² o patio de juegos"
            )
        return False, "Jardín sin nombre o sin tamaño/patio suficiente para inclusión conservadora"

    if category == "PARQUE SEMIPÚBLICO":
        if "reserva ecologica" in name_text:
            return True, "Reserva ecológica; acceso semipúblico conservado explícitamente"
        return False, "Parque semipúblico sin evidencia suficiente de acceso familiar libre"

    if category == "CANTERO CENTRAL":
        return False, "Cantero central asociado a entorno vial"
    if category == "PLAZOLETA":
        return False, "Plazoleta excluida por criterio conservador de tamaño y uso"
    if category in {"PATIO", "PATIO RECREATIVO", "PATIO DE JUEGOS INCLUSIVO", "PASEO"}:
        return False, "Patio o paseo pequeño: no acredita espacio verde grande"
    if category == "BARRIO/COMPLEJO":
        return False, "Barrio o complejo: no representa un espacio verde independiente"
    return False, f"Clasificación no admitida: {category}"


def candidate_for_review(row: dict[str, str], area_m2: float) -> int:
    category = clean_text(row["clasificac"]).upper()
    has_playground = clean_text(row["tiene_pati"]).upper() == "SI"
    name_text = combined_name(row)
    if category == "PARQUE SEMIPÚBLICO":
        return 1
    if category == "PATIO DE JUEGOS INCLUSIVO":
        return 1
    if area_m2 >= 2000 and has_playground and category in {
        "CANTERO CENTRAL",
        "PLAZOLETA",
        "PATIO RECREATIVO",
    }:
        return 1
    if area_m2 >= 5000 and (
        has_playground or category in {"JARDÍN", "PLAZOLETA"} or "paseo" in name_text
    ):
        return 1
    if category == "PLAZA" and area_m2 >= 5000:
        return 1
    return 0


def polygonal_only(geometry):
    if isinstance(geometry, (Polygon, MultiPolygon)):
        return geometry
    if isinstance(geometry, GeometryCollection):
        polygons = []
        for part in geometry.geoms:
            try:
                polygonal = polygonal_only(part)
            except ValueError:
                # make_valid puede devolver también líneas o puntos residuales;
                # no forman parte de la superficie del espacio verde.
                continue
            if isinstance(polygonal, Polygon):
                polygons.append(polygonal)
            elif isinstance(polygonal, MultiPolygon):
                polygons.extend(polygonal.geoms)
        if polygons:
            return unary_union(polygons)
    raise ValueError("La geometría reparada no contiene polígonos")


def geometry_coordinates(
    raw_wkt: str,
    item_id: str,
    to_utm: Transformer,
    to_wgs84: Transformer,
) -> dict[str, object]:
    try:
        geometry = wkt.loads(raw_wkt)
    except Exception as error:
        raise ValueError(f"ID {item_id}: WKT no parseable") from error
    if geometry.is_empty:
        raise ValueError(f"ID {item_id}: geometría vacía")

    repaired = not geometry.is_valid
    if repaired:
        geometry = make_valid(geometry)
    geometry = polygonal_only(geometry)
    projected = transform(to_utm.transform, geometry)
    if projected.is_empty or projected.area <= 0:
        raise ValueError(f"ID {item_id}: geometría proyectada vacía o sin área")

    centroid = projected.centroid
    centroid_inside = projected.covers(centroid)
    if centroid_inside:
        pin = centroid
        method = "Centroide geométrico"
    else:
        if isinstance(projected, Polygon):
            main_component = projected
        else:
            main_component = max(projected.geoms, key=lambda part: part.area)
        pin = main_component.representative_point()
        method = "Punto representativo interno del componente principal"

    if not projected.covers(pin):
        raise ValueError(f"ID {item_id}: el pin final no está dentro de la geometría")

    centroid_wgs = transform(to_wgs84.transform, centroid)
    pin_wgs = transform(to_wgs84.transform, pin)
    lon, lat = float(pin_wgs.x), float(pin_wgs.y)
    centroid_lon, centroid_lat = float(centroid_wgs.x), float(centroid_wgs.y)
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        raise ValueError(f"ID {item_id}: pin fuera de los límites plausibles de CABA")

    parts = 1 if isinstance(projected, Polygon) else len(projected.geoms)
    return {
        "Latitud": f"{lat:.10f}",
        "Longitud": f"{lon:.10f}",
        "Latitud_Centroide": f"{centroid_lat:.10f}",
        "Longitud_Centroide": f"{centroid_lon:.10f}",
        "Metodo_Coordenada": method,
        "Flag_Centroide_Fuera_Geometria": 0 if centroid_inside else 1,
        "Distancia_Centroide_Pin_m": f"{centroid.distance(pin):.2f}",
        "Flag_Geometria_Reparada": 1 if repaired else 0,
        "Cantidad_Partes_Geometria": parts,
    }


def manual_review(row: dict[str, str], area_m2: float) -> tuple[int, str]:
    reasons: list[str] = []
    item_id = clean_text(row["id"])
    if item_id in AMBIGUOUS_SELECTED_IDS:
        reasons.append(AMBIGUOUS_SELECTED_IDS[item_id])
    if "no oficial" in combined_name(row):
        reasons.append("La fuente indica que la denominación no es oficial")
    if clean_text(row["clasificac"]).upper() == "PARQUE SEMIPÚBLICO":
        reasons.append("La fuente clasifica el acceso como semipúblico")
    if "propiedad particular" in normalize_for_match(row["ubicacion"]):
        reasons.append("La ubicación menciona propiedad particular; confirmar acceso")
    if source_name(row) == "No informado" and area_m2 < 500:
        reasons.append("Plaza sin nombre y menor a 500 m²; confirmar que sea un espacio independiente")
    return (1, " | ".join(reasons)) if reasons else (0, "No aplica")


def included_output(
    row: dict[str, str],
    criterion: str,
    geometry_data: dict[str, object],
    area_m2: float,
) -> dict[str, object]:
    item_id = clean_text(row["id"])
    category = clean_text(row["clasificac"]).upper()
    review_flag, review_reason = manual_review(row, area_m2)
    result: dict[str, object] = {
        "ID_Espacio_Verde": item_id,
        "Nombre": source_name(row),
        "Nombre_Mapa": clean_text(row["nom_mapa"]),
        "Tipo_Espacio": TYPE_LABELS[category],
        "Clasificacion_Original": category,
        "Acceso": (
            "Semipúblico según clasificación original"
            if category == "PARQUE SEMIPÚBLICO"
            else "No informado"
        ),
        "Direccion": clean_text(row["ubicacion"]),
        "Barrio": clean_text(row["barrio"]),
        "Comuna": clean_text(row["comuna"]),
        "Tiene_Patio_Juegos": clean_text(row["tiene_pati"]),
        "Superficie_m2": clean_text(row["area"]),
        "Perimetro_m": clean_text(row["perimetro"]),
        "Flag_Revision_Manual": review_flag,
        "Motivo_Revision": review_reason,
        "Criterio_Inclusion": criterion,
        "CRS_Coordenadas": "EPSG:4326",
        "Fuente_Archivo": "espacio_verde_publico.csv",
    }
    result.update(geometry_data)
    return result


def excluded_output(row: dict[str, str], reason: str, area_m2: float) -> dict[str, object]:
    return {
        "ID_Espacio_Verde": clean_text(row["id"]),
        "Nombre": source_name(row),
        "Nombre_Mapa": clean_text(row["nom_mapa"]),
        "Clasificacion_Original": clean_text(row["clasificac"]).upper(),
        "Direccion": clean_text(row["ubicacion"]),
        "Barrio": clean_text(row["barrio"]),
        "Comuna": clean_text(row["comuna"]),
        "Tiene_Patio_Juegos": clean_text(row["tiene_pati"]),
        "Superficie_m2": clean_text(row["area"]),
        "Perimetro_m": clean_text(row["perimetro"]),
        "Motivo_Exclusion": reason,
        "Flag_Candidato_Revision": candidate_for_review(row, area_m2),
        "Fuente_Archivo": "espacio_verde_publico.csv",
    }


def temporary_path(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    return Path(name)


def validate_outputs(
    clean_path: Path,
    excluded_path: Path,
    source_ids: set[str],
    expected_clean: int,
    expected_excluded: int,
) -> None:
    clean_ids: set[str] = set()
    with clean_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != OUTPUT_COLUMNS:
            raise ValueError("Esquema inesperado en la salida limpia")
        rows = 0
        for row in reader:
            rows += 1
            item_id = row["ID_Espacio_Verde"]
            if item_id in clean_ids:
                raise ValueError(f"ID duplicado en salida limpia: {item_id}")
            clean_ids.add(item_id)
            lat, lon = float(row["Latitud"]), float(row["Longitud"])
            if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
                raise ValueError(f"Coordenada fuera de CABA en ID {item_id}")
            if row["Flag_Centroide_Fuera_Geometria"] not in {"0", "1"}:
                raise ValueError(f"Flag de centroide inválido en ID {item_id}")
            if row["Flag_Geometria_Reparada"] not in {"0", "1"}:
                raise ValueError(f"Flag de geometría inválido en ID {item_id}")
        if rows != expected_clean:
            raise ValueError(f"Se esperaban {expected_clean} filas limpias y se encontraron {rows}")

    excluded_ids: set[str] = set()
    with excluded_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != EXCLUDED_COLUMNS:
            raise ValueError("Esquema inesperado en la salida de excluidos")
        rows = 0
        for row in reader:
            rows += 1
            item_id = row["ID_Espacio_Verde"]
            if item_id in excluded_ids:
                raise ValueError(f"ID duplicado en excluidos: {item_id}")
            excluded_ids.add(item_id)
            if not row["Motivo_Exclusion"]:
                raise ValueError(f"Motivo de exclusión vacío en ID {item_id}")
        if rows != expected_excluded:
            raise ValueError(
                f"Se esperaban {expected_excluded} filas excluidas y se encontraron {rows}"
            )

    if clean_ids & excluded_ids:
        raise ValueError("Hay ID presentes en ambas salidas")
    if clean_ids | excluded_ids != source_ids:
        raise ValueError("La unión de salidas no coincide con todos los ID originales")


def process(
    source: Path,
    output: Path,
    excluded: Path,
    park_min: float,
    garden_min: float,
) -> tuple[Counter[str], Counter[str]]:
    if not source.is_file():
        raise FileNotFoundError(f"No se encontró {source}")
    if output.resolve() == excluded.resolve():
        raise ValueError("Las dos salidas deben tener rutas diferentes")
    if output.resolve() == source.resolve() or excluded.resolve() == source.resolve():
        raise ValueError("Las salidas no pueden sobrescribir el CSV original")
    for destination in (output, excluded):
        if destination.exists() and not destination.is_file():
            raise ValueError(f"El destino existe y no es un archivo: {destination}")
    if park_min <= 0 or garden_min <= 0:
        raise ValueError("Los umbrales de superficie deben ser positivos")

    original_hash = sha256(source)
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32721", always_xy=True)
    to_wgs84 = Transformer.from_crs("EPSG:32721", "EPSG:4326", always_xy=True)
    temp_output: Path | None = None
    temp_excluded: Path | None = None
    source_ids: set[str] = set()
    included_stats: Counter[str] = Counter()
    quality_stats: Counter[str] = Counter()

    try:
        temp_output = temporary_path(output)
        temp_excluded = temporary_path(excluded)
        with (
            source.open("r", encoding="utf-8-sig", newline="") as source_file,
            temp_output.open("w", encoding="utf-8-sig", newline="") as output_file,
            temp_excluded.open("w", encoding="utf-8-sig", newline="") as excluded_file,
        ):
            reader = csv.DictReader(source_file)
            if reader.fieldnames != SOURCE_COLUMNS:
                raise ValueError(f"Columnas inesperadas: {reader.fieldnames}")
            clean_writer = csv.DictWriter(output_file, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
            excluded_writer = csv.DictWriter(
                excluded_file, fieldnames=EXCLUDED_COLUMNS, lineterminator="\n"
            )
            clean_writer.writeheader()
            excluded_writer.writeheader()

            for line_number, row in enumerate(reader, start=2):
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"Fila CSV malformada en línea {line_number}")
                item_id = clean_text(row["id"])
                if item_id == "No informado" or item_id in source_ids:
                    raise ValueError(f"ID vacío o duplicado en línea {line_number}: {item_id}")
                source_ids.add(item_id)
                area_m2 = parse_positive_float(row["area"], "area", item_id)
                parse_positive_float(row["perimetro"], "perimetro", item_id)
                include, reason = inclusion_decision(row, area_m2, park_min, garden_min)

                if include:
                    geometry_data = geometry_coordinates(
                        row["geometry"], item_id, to_utm, to_wgs84
                    )
                    clean_writer.writerow(included_output(row, reason, geometry_data, area_m2))
                    category = clean_text(row["clasificac"]).upper()
                    included_stats[category] += 1
                    quality_stats["incluidas"] += 1
                    quality_stats["centroide_fuera"] += int(
                        geometry_data["Flag_Centroide_Fuera_Geometria"]
                    )
                    quality_stats["geometrias_reparadas"] += int(
                        geometry_data["Flag_Geometria_Reparada"]
                    )
                    review_flag, _ = manual_review(row, area_m2)
                    quality_stats["revision_manual"] += review_flag
                else:
                    excluded_writer.writerow(excluded_output(row, reason, area_m2))
                    quality_stats["excluidas"] += 1
                    quality_stats["candidatas_revision"] += candidate_for_review(row, area_m2)

            output_file.flush()
            excluded_file.flush()
            os.fsync(output_file.fileno())
            os.fsync(excluded_file.fileno())

        validate_outputs(
            temp_output,
            temp_excluded,
            source_ids,
            quality_stats["incluidas"],
            quality_stats["excluidas"],
        )
        if sha256(source) != original_hash:
            raise RuntimeError("El CSV original cambió durante el procesamiento")

        os.chmod(temp_output, 0o644)
        os.chmod(temp_excluded, 0o644)
        os.replace(temp_excluded, excluded)
        os.replace(temp_output, output)
        return included_stats, quality_stats
    except Exception:
        if temp_output is not None:
            temp_output.unlink(missing_ok=True)
        if temp_excluded is not None:
            temp_excluded.unlink(missing_ok=True)
        raise


def build_parser(base_dir: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Filtra espacios verdes familiares y calcula coordenadas centrales."
    )
    parser.add_argument("--entrada", type=Path, default=base_dir / "espacio_verde_publico.csv")
    parser.add_argument(
        "--salida", type=Path, default=base_dir / "espacios_verdes_familiares_limpio.csv"
    )
    parser.add_argument(
        "--excluidos", type=Path, default=base_dir / "espacios_verdes_excluidos_revision.csv"
    )
    parser.add_argument("--area-min-parque", type=float, default=1000.0)
    parser.add_argument("--area-min-jardin", type=float, default=5000.0)
    return parser


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    args = build_parser(base_dir).parse_args()
    try:
        included_stats, quality = process(
            args.entrada.resolve(),
            args.salida.resolve(),
            args.excluidos.resolve(),
            args.area_min_parque,
            args.area_min_jardin,
        )
    except (OSError, ValueError, RuntimeError, GEOSException, ProjError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("\n=== Limpieza de espacios verdes familiares ===")
    print(f"Incluidos: {quality['incluidas']:,}")
    for category, count in included_stats.most_common():
        print(f"  - {category}: {count:,}")
    print(f"Excluidos: {quality['excluidas']:,}")
    print(f"Centroides fuera reemplazados por punto interno: {quality['centroide_fuera']:,}")
    print(f"Geometrías reparadas: {quality['geometrias_reparadas']:,}")
    print(f"Incluidos marcados para revisión: {quality['revision_manual']:,}")
    print(f"Excluidos candidatos a revisión: {quality['candidatas_revision']:,}")
    print(f"CSV limpio: {args.salida.resolve()}")
    print(f"CSV de excluidos/revisión: {args.excluidos.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
