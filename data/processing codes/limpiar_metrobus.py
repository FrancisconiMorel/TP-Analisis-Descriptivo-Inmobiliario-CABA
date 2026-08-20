"""Limpia y normaliza el dataset de estaciones de Metrobus de CABA.

El script es independiente y utiliza solamente la biblioteca estandar de
Python. Lee ``estaciones-de-metrobus.csv`` y crea ``metrobus_limpio.csv`` sin
modificar el archivo original.

Las coordenadas ``X``/``Y`` son la fuente principal. ``coord_X``/``coord_Y``
se usan solo para validar o recuperar una coordenada primaria ausente. Las
lineas L1...L6 se resumen sin perder los codigos de sentido asociados.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "estaciones-de-metrobus.csv"
DEFAULT_OUTPUT = BASE_DIR / "metrobus_limpio.csv"

NO_INFORMADO = "No informado"
TIPO_TRANSPORTE = "Metrobus"

LATITUD_MIN = Decimal("-34.71")
LATITUD_MAX = Decimal("-34.52")
LONGITUD_MIN = Decimal("-58.54")
LONGITUD_MAX = Decimal("-58.33")

LINEA_COLUMNS = tuple(f"L{numero}" for numero in range(1, 7))
SENTIDO_COLUMNS = tuple(f"l{numero}_sen" for numero in range(1, 7))

REQUIRED_INPUT_COLUMNS = (
    "X",
    "Y",
    "CALLE",
    "ALT PLANO",
    "DIRECCION",
    "coord_X",
    "coord_Y",
    "COMUNA",
    "BARRIO",
    *LINEA_COLUMNS,
    *SENTIDO_COLUMNS,
    "NOMBRE PAR",
)

OUTPUT_COLUMNS = (
    "ID",
    "Tipo_Transporte",
    "Nombre",
    "Corredor",
    "Lineas",
    "Lineas_Sentido",
    "Direccion",
    "Barrio",
    "Comuna",
    "Latitud",
    "Longitud",
    "Flag_Coordenada_Anomala",
    "Flag_Duplicado",
)

MISSING_TOKENS = {"", "nan", "none", "n/a", "na", "null"}
MULTIPLE_SPACES = re.compile(r"\s+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Limpia y normaliza estaciones de Metrobus de CABA."
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


def limpiar_texto(valor: object) -> str:
    """Quita espacios sobrantes y representa un faltante internamente con ''."""
    if valor is None:
        return ""
    texto = MULTIPLE_SPACES.sub(" ", str(valor).strip())
    return "" if texto.casefold() in MISSING_TOKENS else texto


def texto_o_no_informado(valor: object) -> str:
    return limpiar_texto(valor) or NO_INFORMADO


def parsear_decimal(valor: object) -> Decimal | None:
    """Interpreta punto o coma decimal sin convertir a float."""
    texto = limpiar_texto(valor).replace(" ", "")
    if not texto:
        return None
    if "," in texto and "." not in texto:
        texto = texto.replace(",", ".")
    try:
        numero = Decimal(texto)
    except InvalidOperation:
        return None
    return numero if numero.is_finite() else None


def decimal_a_texto(numero: Decimal | None) -> str:
    if numero is None:
        return NO_INFORMADO
    texto = format(numero, "f")
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return "0" if texto in {"-0", "+0"} else texto


def elegir_coordenada(
    primaria: object,
    alternativa: object,
) -> tuple[Decimal | None, bool, bool]:
    """Devuelve coordenada, uso de fallback y discrepancia entre fuentes."""
    principal = parsear_decimal(primaria)
    respaldo = parsear_decimal(alternativa)
    discrepancia = (
        principal is not None
        and respaldo is not None
        and principal != respaldo
    )
    uso_fallback = principal is None and respaldo is not None
    return (principal if principal is not None else respaldo), uso_fallback, discrepancia


def normalizar_comuna(valor: object) -> str:
    texto = limpiar_texto(valor)
    if not texto:
        return NO_INFORMADO
    coincidencia = re.fullmatch(r"(?:comuna\s*)?(\d+)", texto, re.IGNORECASE)
    if coincidencia:
        return f"Comuna {int(coincidencia.group(1))}"
    return texto


def normalizar_sentido(valor: object) -> str:
    sentido = limpiar_texto(valor)
    if not sentido:
        return NO_INFORMADO
    if sentido.upper() in {"I", "V"}:
        return sentido.upper()
    return sentido


def combinar_lineas(fila: dict[str, str]) -> tuple[str, str, int]:
    """Combina lineas distintas y conserva cada par linea:sentido."""
    lineas: list[str] = []
    pares: list[str] = []
    sentidos_no_informados = 0

    for linea_columna, sentido_columna in zip(
        LINEA_COLUMNS,
        SENTIDO_COLUMNS,
    ):
        linea = limpiar_texto(fila.get(linea_columna, ""))
        if not linea:
            continue

        if linea not in lineas:
            lineas.append(linea)

        sentido = normalizar_sentido(fila.get(sentido_columna, ""))
        if sentido == NO_INFORMADO:
            sentidos_no_informados += 1
        par = f"{linea}:{sentido}"
        if par not in pares:
            pares.append(par)

    return (
        "|".join(lineas) if lineas else NO_INFORMADO,
        "|".join(pares) if pares else NO_INFORMADO,
        sentidos_no_informados,
    )


def construir_direccion(fila: dict[str, str]) -> tuple[str, bool]:
    direccion = limpiar_texto(fila.get("DIRECCION", ""))
    if direccion:
        return direccion, False

    altura = limpiar_texto(fila.get("ALT PLANO", ""))
    calle = limpiar_texto(fila.get("CALLE", ""))
    alternativa = " ".join(parte for parte in (altura, calle) if parte)
    return (alternativa or NO_INFORMADO), bool(alternativa)


def coordenada_anomala(
    latitud: Decimal | None,
    longitud: Decimal | None,
) -> int:
    if latitud is None or longitud is None:
        return 1
    if not LATITUD_MIN <= latitud <= LATITUD_MAX:
        return 1
    if not LONGITUD_MIN <= longitud <= LONGITUD_MAX:
        return 1
    return 0


def leer_original(ruta: Path) -> tuple[list[str], list[dict[str, str]]]:
    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        if not lector.fieldnames:
            raise ValueError("El CSV original no tiene encabezado.")
        faltantes = [
            columna
            for columna in REQUIRED_INPUT_COLUMNS
            if columna not in lector.fieldnames
        ]
        if faltantes:
            raise ValueError(
                "Faltan columnas obligatorias: " + ", ".join(faltantes)
            )
        filas = [dict(fila) for fila in lector]
    return list(lector.fieldnames), filas


def transformar(
    originales: list[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, int]]:
    limpias: list[dict[str, str]] = []
    estadisticas = {
        "fallback_latitud": 0,
        "fallback_longitud": 0,
        "discrepancias_latitud": 0,
        "discrepancias_longitud": 0,
        "fallback_direccion": 0,
        "sentidos_no_informados": 0,
    }

    for posicion, original in enumerate(originales, start=1):
        longitud, fallback_lon, discrepancia_lon = elegir_coordenada(
            original.get("X", ""),
            original.get("coord_X", ""),
        )
        latitud, fallback_lat, discrepancia_lat = elegir_coordenada(
            original.get("Y", ""),
            original.get("coord_Y", ""),
        )
        lineas, lineas_sentido, sentidos_faltantes = combinar_lineas(original)
        direccion, fallback_direccion = construir_direccion(original)

        estadisticas["fallback_latitud"] += int(fallback_lat)
        estadisticas["fallback_longitud"] += int(fallback_lon)
        estadisticas["discrepancias_latitud"] += int(discrepancia_lat)
        estadisticas["discrepancias_longitud"] += int(discrepancia_lon)
        estadisticas["fallback_direccion"] += int(fallback_direccion)
        estadisticas["sentidos_no_informados"] += sentidos_faltantes

        limpias.append(
            {
                "ID": f"METROBUS_{posicion:06d}",
                "Tipo_Transporte": TIPO_TRANSPORTE,
                "Nombre": texto_o_no_informado(original.get("NOMBRE PAR", "")),
                "Corredor": NO_INFORMADO,
                "Lineas": lineas,
                "Lineas_Sentido": lineas_sentido,
                "Direccion": direccion,
                "Barrio": texto_o_no_informado(original.get("BARRIO", "")),
                "Comuna": normalizar_comuna(original.get("COMUNA", "")),
                "Latitud": decimal_a_texto(latitud),
                "Longitud": decimal_a_texto(longitud),
                "Flag_Coordenada_Anomala": str(
                    coordenada_anomala(latitud, longitud)
                ),
                "Flag_Duplicado": "0",
            }
        )

    frecuencias = Counter(
        (fila["Latitud"], fila["Longitud"], fila["Nombre"])
        for fila in limpias
        if fila["Latitud"] != NO_INFORMADO
        and fila["Longitud"] != NO_INFORMADO
    )
    for fila in limpias:
        clave = (fila["Latitud"], fila["Longitud"], fila["Nombre"])
        fila["Flag_Duplicado"] = "1" if frecuencias[clave] > 1 else "0"

    return limpias, estadisticas


def validar_resultado(
    originales: list[dict[str, str]],
    limpias: list[dict[str, str]],
) -> None:
    if len(originales) != len(limpias):
        raise ValueError("La limpieza altero la cantidad de filas.")
    if not limpias:
        raise ValueError("El CSV limpio no puede quedar vacio.")

    ids = [fila["ID"] for fila in limpias]
    esperados = [f"METROBUS_{numero:06d}" for numero in range(1, len(limpias) + 1)]
    if ids != esperados or len(ids) != len(set(ids)):
        raise ValueError("Los ID tecnicos no son secuenciales y unicos.")

    for numero, (original, limpia) in enumerate(
        zip(originales, limpias),
        start=2,
    ):
        if tuple(limpia) != OUTPUT_COLUMNS:
            raise ValueError(f"Fila {numero}: estructura final inesperada.")
        if any(limpiar_texto(valor) == "" for valor in limpia.values()):
            raise ValueError(f"Fila {numero}: quedaron valores vacios.")
        if limpia["Tipo_Transporte"] != TIPO_TRANSPORTE:
            raise ValueError(f"Fila {numero}: Tipo_Transporte incorrecto.")
        if limpia["Corredor"] != NO_INFORMADO:
            raise ValueError(f"Fila {numero}: se infirio un corredor sin fuente.")
        if limpia["Flag_Coordenada_Anomala"] not in {"0", "1"}:
            raise ValueError(f"Fila {numero}: flag de coordenada invalido.")
        if limpia["Flag_Duplicado"] not in {"0", "1"}:
            raise ValueError(f"Fila {numero}: flag de duplicado invalido.")

        lineas_esperadas, sentidos_esperados, _ = combinar_lineas(original)
        if limpia["Lineas"] != lineas_esperadas:
            raise ValueError(f"Fila {numero}: se perdieron lineas.")
        if limpia["Lineas_Sentido"] != sentidos_esperados:
            raise ValueError(f"Fila {numero}: se perdieron sentidos.")
        if lineas_esperadas != NO_INFORMADO:
            lista = lineas_esperadas.split("|")
            if len(lista) != len(set(lista)):
                raise ValueError(f"Fila {numero}: hay lineas repetidas.")

        latitud = parsear_decimal(limpia["Latitud"])
        longitud = parsear_decimal(limpia["Longitud"])
        flag_esperado = str(coordenada_anomala(latitud, longitud))
        if limpia["Flag_Coordenada_Anomala"] != flag_esperado:
            raise ValueError(f"Fila {numero}: flag de coordenada inconsistente.")

    frecuencias = Counter(
        (fila["Latitud"], fila["Longitud"], fila["Nombre"])
        for fila in limpias
        if fila["Latitud"] != NO_INFORMADO
        and fila["Longitud"] != NO_INFORMADO
    )
    for numero, fila in enumerate(limpias, start=2):
        clave = (fila["Latitud"], fila["Longitud"], fila["Nombre"])
        esperado = "1" if frecuencias[clave] > 1 else "0"
        if fila["Flag_Duplicado"] != esperado:
            raise ValueError(f"Fila {numero}: flag de duplicado inconsistente.")


def escribir_atomico(ruta: Path, filas: Iterable[dict[str, str]]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f".{ruta.name}.{os.getpid()}.tmp")
    try:
        with temporal.open("w", encoding="utf-8-sig", newline="") as archivo:
            escritor = csv.DictWriter(
                archivo,
                fieldnames=OUTPUT_COLUMNS,
                lineterminator="\n",
            )
            escritor.writeheader()
            escritor.writerows(filas)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, ruta)
    finally:
        temporal.unlink(missing_ok=True)


def validar_archivo_escrito(
    ruta: Path,
    filas_esperadas: list[dict[str, str]],
) -> None:
    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        if tuple(lector.fieldnames or ()) != OUTPUT_COLUMNS:
            raise ValueError("El CSV escrito no conserva las columnas esperadas.")
        filas_leidas = [dict(fila) for fila in lector]
    if filas_leidas != filas_esperadas:
        raise ValueError("El CSV escrito no coincide con el resultado validado.")


def imprimir_reporte(
    entrada: Path,
    salida: Path,
    columnas_originales: list[str],
    filas: list[dict[str, str]],
    estadisticas: dict[str, int],
) -> None:
    total = len(filas)
    con_latitud = sum(fila["Latitud"] != NO_INFORMADO for fila in filas)
    con_longitud = sum(fila["Longitud"] != NO_INFORMADO for fila in filas)
    anomalas = sum(fila["Flag_Coordenada_Anomala"] == "1" for fila in filas)
    duplicadas = sum(fila["Flag_Duplicado"] == "1" for fila in filas)

    print("\n=== REPORTE DE CALIDAD: METROBUS ===")
    print(f"Archivo original: {entrada}")
    print(f"Archivo limpio: {salida}")
    print(f"Filas originales: {total}")
    print(f"Filas finales: {total}")
    print(f"Columnas originales: {len(columnas_originales)}")
    print(f"Columnas finales: {len(OUTPUT_COLUMNS)}")
    print(f"Filas con Latitud: {con_latitud}")
    print(f"Filas con Longitud: {con_longitud}")
    print(f"Coordenadas anomalas: {anomalas}")
    print(f"Posibles duplicados: {duplicadas}")
    print(f"Direcciones recuperadas con ALT PLANO + CALLE: {estadisticas['fallback_direccion']}")
    print(f"Latitudes recuperadas desde coord_Y: {estadisticas['fallback_latitud']}")
    print(f"Longitudes recuperadas desde coord_X: {estadisticas['fallback_longitud']}")
    print(f"Discrepancias Y vs coord_Y: {estadisticas['discrepancias_latitud']}")
    print(f"Discrepancias X vs coord_X: {estadisticas['discrepancias_longitud']}")
    print(f"Lineas sin sentido informado: {estadisticas['sentidos_no_informados']}")
    print("Faltantes por columna:")
    for columna in OUTPUT_COLUMNS:
        faltantes = sum(fila[columna] == NO_INFORMADO for fila in filas)
        porcentaje = (faltantes / total * 100) if total else 0.0
        print(f"  {columna}: {faltantes} ({porcentaje:.2f}%)")


def procesar(entrada: Path, salida: Path) -> int:
    entrada = entrada.expanduser().resolve()
    salida = salida.expanduser().resolve()
    if not entrada.is_file():
        raise FileNotFoundError(f"No se encontro el CSV original: {entrada}")
    if entrada == salida:
        raise ValueError("La salida debe ser distinta del archivo original.")

    columnas_originales, originales = leer_original(entrada)
    limpias, estadisticas = transformar(originales)
    validar_resultado(originales, limpias)
    escribir_atomico(salida, limpias)
    validar_archivo_escrito(salida, limpias)
    imprimir_reporte(
        entrada,
        salida,
        columnas_originales,
        limpias,
        estadisticas,
    )
    return len(limpias)


def main() -> int:
    args = parse_args()
    procesar(args.entrada, args.salida)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
