"""Limpia y normaliza el dataset de paradas de colectivo de CABA.

El programa es independiente, usa solamente la biblioteca estandar y nunca
modifica el CSV original. La salida se escribe primero en un archivo temporal,
se valida y luego se publica de manera atomica.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import tempfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Mapping


NO_INFORMADO = "No informado"
TIPO_TRANSPORTE = "Colectivo"

LATITUD_MIN = Decimal("-34.71")
LATITUD_MAX = Decimal("-34.52")
LONGITUD_MIN = Decimal("-58.54")
LONGITUD_MAX = Decimal("-58.33")

COLUMNAS_LINEA = tuple(f"L{numero}" for numero in range(1, 7))
COLUMNAS_SENTIDO = tuple(f"l{numero}_sen" for numero in range(1, 7))

COLUMNAS_REQUERIDAS = (
    "fid",
    "CALLE",
    "ALT PLANO",
    "DIRECCION",
    "coord_X",
    "coord_Y",
    "COMUNA",
    "BARRIO",
    *COLUMNAS_LINEA,
    *COLUMNAS_SENTIDO,
)

COLUMNAS_SALIDA = (
    "ID",
    "Tipo_Transporte",
    "Nombre",
    "Lineas",
    "Cantidad_Lineas",
    "Lineas_Sentido",
    "Direccion",
    "Barrio",
    "Comuna",
    "Latitud",
    "Longitud",
    "Flag_Coordenada_Anomala",
    "Flag_Duplicado",
)

PATRON_ESPACIOS = re.compile(r"\s+")
PATRON_LINEA = re.compile(r"\d+")
VALORES_FALTANTES = {
    "",
    "nan",
    "none",
    "null",
    "n/a",
    "na",
    "s/d",
    "sin dato",
    "no informado",
}


def texto_basico(valor: object) -> str:
    """Quita espacios exteriores y colapsa espacios internos."""

    if valor is None:
        return ""
    return PATRON_ESPACIOS.sub(" ", str(valor)).strip()


def limpiar_texto(valor: object) -> str:
    """Normaliza texto y unifica faltantes sin alterar tildes ni caracteres."""

    texto = texto_basico(valor)
    if texto.casefold() in VALORES_FALTANTES:
        return NO_INFORMADO
    return texto


def normalizar_comuna(valor: object) -> str:
    """Devuelve el formato 'Comuna N' sin inferir ni corregir su numero."""

    comuna = limpiar_texto(valor)
    if comuna == NO_INFORMADO:
        return comuna

    coincidencia = re.fullmatch(r"comuna\s+(.+)", comuna, flags=re.IGNORECASE)
    numero_o_texto = coincidencia.group(1) if coincidencia else comuna
    return f"Comuna {numero_o_texto}"


def normalizar_coordenada(valor: object) -> tuple[str, Decimal | None]:
    """Convierte una coordenada con coma decimal a texto decimal y Decimal."""

    texto = texto_basico(valor)
    if texto.casefold() in VALORES_FALTANTES:
        return NO_INFORMADO, None

    texto_decimal = texto.replace(",", ".")
    try:
        numero = Decimal(texto_decimal)
    except InvalidOperation:
        return NO_INFORMADO, None

    if not numero.is_finite():
        return NO_INFORMADO, None
    return format(numero, "f"), numero


def validar_coordenadas(
    latitud: Decimal | None, longitud: Decimal | None
) -> int:
    """Marca coordenadas faltantes, invalidas o fuera de la caja de CABA."""

    if latitud is None or longitud is None:
        return 1
    dentro_de_rango = (
        LATITUD_MIN <= latitud <= LATITUD_MAX
        and LONGITUD_MIN <= longitud <= LONGITUD_MAX
    )
    return 0 if dentro_de_rango else 1


def combinar_lineas(fila: Mapping[str, str]) -> tuple[str, int, str]:
    """Combina lineas numericas distintas y conserva sus sentidos.

    `Lineas` no repite numeros. `Lineas_Sentido` conserva pares distintos,
    por lo que una misma linea puede aparecer con I y V si la fuente informa
    ambos sentidos en la misma parada.
    """

    lineas: list[str] = []
    lineas_vistas: set[str] = set()
    pares_sentido: list[str] = []
    pares_vistos: set[tuple[str, str]] = set()

    for columna_linea, columna_sentido in zip(
        COLUMNAS_LINEA, COLUMNAS_SENTIDO, strict=True
    ):
        linea_original = texto_basico(fila.get(columna_linea, ""))
        if not PATRON_LINEA.fullmatch(linea_original):
            # Por ejemplo, la fuente contiene un valor aislado "V" en L3.
            continue

        linea = str(int(linea_original))
        if linea not in lineas_vistas:
            lineas.append(linea)
            lineas_vistas.add(linea)

        sentido = limpiar_texto(fila.get(columna_sentido, ""))
        if sentido != NO_INFORMADO:
            sentido = sentido.upper()

        clave_par = (linea, sentido)
        if clave_par not in pares_vistos:
            pares_sentido.append(f"{linea}:{sentido}")
            pares_vistos.add(clave_par)

    if not lineas:
        return NO_INFORMADO, 0, NO_INFORMADO

    return "|".join(lineas), len(lineas), "|".join(pares_sentido)


def construir_direccion(fila: Mapping[str, str]) -> str:
    """Usa DIRECCION y, si falta, combina ALT PLANO y CALLE."""

    direccion = limpiar_texto(fila.get("DIRECCION", ""))
    if direccion != NO_INFORMADO:
        return direccion

    altura = limpiar_texto(fila.get("ALT PLANO", ""))
    calle = limpiar_texto(fila.get("CALLE", ""))
    partes = [valor for valor in (altura, calle) if valor != NO_INFORMADO]
    return " ".join(partes) if partes else NO_INFORMADO


def transformar_fila(fila: Mapping[str, str]) -> dict[str, str]:
    """Transforma una fila fuente al esquema normalizado."""

    latitud_texto, latitud_numero = normalizar_coordenada(fila.get("coord_Y"))
    longitud_texto, longitud_numero = normalizar_coordenada(fila.get("coord_X"))
    lineas, cantidad_lineas, lineas_sentido = combinar_lineas(fila)

    return {
        "ID": limpiar_texto(fila.get("fid", "")),
        "Tipo_Transporte": TIPO_TRANSPORTE,
        # La fuente no contiene un nombre oficial de la parada.
        "Nombre": NO_INFORMADO,
        "Lineas": lineas,
        "Cantidad_Lineas": str(cantidad_lineas),
        "Lineas_Sentido": lineas_sentido,
        "Direccion": construir_direccion(fila),
        "Barrio": limpiar_texto(fila.get("BARRIO", "")),
        "Comuna": normalizar_comuna(fila.get("COMUNA", "")),
        "Latitud": latitud_texto,
        "Longitud": longitud_texto,
        "Flag_Coordenada_Anomala": str(
            validar_coordenadas(latitud_numero, longitud_numero)
        ),
        "Flag_Duplicado": "0",
    }


def clave_coordenadas(fila: Mapping[str, str]) -> tuple[Decimal, Decimal] | None:
    """Crea una clave numerica para comparar coordenadas equivalentes."""

    try:
        latitud = Decimal(fila["Latitud"])
        longitud = Decimal(fila["Longitud"])
    except (InvalidOperation, KeyError):
        return None
    if not latitud.is_finite() or not longitud.is_finite():
        return None
    return latitud, longitud


def detectar_duplicados(filas: list[dict[str, str]]) -> None:
    """Marca IDs repetidos o Nombre+Latitud+Longitud repetidos."""

    ids = Counter(
        fila["ID"] for fila in filas if fila["ID"] != NO_INFORMADO
    )

    claves: list[tuple[str, Decimal, Decimal] | None] = []
    for fila in filas:
        coordenadas = clave_coordenadas(fila)
        if coordenadas is None:
            claves.append(None)
        else:
            claves.append((fila["Nombre"].casefold(), *coordenadas))

    conteo_claves = Counter(clave for clave in claves if clave is not None)
    for fila, clave in zip(filas, claves, strict=True):
        id_repetido = fila["ID"] != NO_INFORMADO and ids[fila["ID"]] > 1
        ubicacion_repetida = clave is not None and conteo_claves[clave] > 1
        fila["Flag_Duplicado"] = "1" if id_repetido or ubicacion_repetida else "0"


def leer_fuente(ruta: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Lee el CSV fuente como UTF-8 y valida sus columnas requeridas."""

    with ruta.open("r", encoding="utf-8", newline="") as archivo:
        lector = csv.DictReader(archivo)
        columnas = lector.fieldnames or []
        faltantes = [columna for columna in COLUMNAS_REQUERIDAS if columna not in columnas]
        if faltantes:
            raise ValueError(
                "Faltan columnas requeridas en el archivo fuente: "
                + ", ".join(faltantes)
            )
        filas = [dict(fila) for fila in lector]
    return columnas, filas


def validar_filas(filas: list[dict[str, str]], cantidad_fuente: int) -> None:
    """Comprueba esquema, cantidad de filas e invariantes del resultado."""

    if len(filas) != cantidad_fuente:
        raise ValueError("La limpieza altero la cantidad de filas.")

    ids: set[str] = set()
    for numero_fila, fila in enumerate(filas, start=2):
        if tuple(fila.keys()) != COLUMNAS_SALIDA:
            raise ValueError(f"Esquema incorrecto en la fila {numero_fila}.")
        if any(valor == "" for valor in fila.values()):
            raise ValueError(f"Quedo un valor vacio en la fila {numero_fila}.")
        if fila["Tipo_Transporte"] != TIPO_TRANSPORTE:
            raise ValueError(f"Tipo de transporte invalido en fila {numero_fila}.")
        if fila["Nombre"] != NO_INFORMADO:
            raise ValueError(f"Nombre inferido indebidamente en fila {numero_fila}.")
        if fila["Flag_Coordenada_Anomala"] not in {"0", "1"}:
            raise ValueError(f"Flag de coordenada invalido en fila {numero_fila}.")
        if fila["Flag_Duplicado"] not in {"0", "1"}:
            raise ValueError(f"Flag de duplicado invalido en fila {numero_fila}.")

        identificador = fila["ID"]
        if identificador in ids:
            # Se permite en la salida, pero debe quedar marcado como duplicado.
            if fila["Flag_Duplicado"] != "1":
                raise ValueError(f"ID repetido sin flag en fila {numero_fila}.")
        ids.add(identificador)

        if fila["Lineas"] == NO_INFORMADO:
            if fila["Cantidad_Lineas"] != "0":
                raise ValueError(f"Cantidad de lineas invalida en fila {numero_fila}.")
        else:
            lineas = fila["Lineas"].split("|")
            if any(not PATRON_LINEA.fullmatch(linea) for linea in lineas):
                raise ValueError(f"Linea no numerica en fila {numero_fila}.")
            if len(lineas) != len(set(lineas)):
                raise ValueError(f"Linea repetida en fila {numero_fila}.")
            if int(fila["Cantidad_Lineas"]) != len(lineas):
                raise ValueError(f"Cantidad de lineas invalida en fila {numero_fila}.")

        coordenadas = clave_coordenadas(fila)
        flag_calculado = validar_coordenadas(
            coordenadas[0] if coordenadas else None,
            coordenadas[1] if coordenadas else None,
        )
        if fila["Flag_Coordenada_Anomala"] != str(flag_calculado):
            raise ValueError(f"Flag de coordenada inconsistente en fila {numero_fila}.")

    # Recalcula los duplicados y comprueba que los flags escritos coincidan.
    copia = [dict(fila) for fila in filas]
    detectar_duplicados(copia)
    for numero_fila, (original, recalculada) in enumerate(
        zip(filas, copia, strict=True), start=2
    ):
        if original["Flag_Duplicado"] != recalculada["Flag_Duplicado"]:
            raise ValueError(f"Flag de duplicado inconsistente en fila {numero_fila}.")


def escribir_atomico(ruta: Path, filas: Iterable[Mapping[str, str]]) -> None:
    """Escribe UTF-8-SIG en un temporal y reemplaza la salida al finalizar."""

    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal_texto = tempfile.mkstemp(
        prefix=f".{ruta.name}.", suffix=".tmp", dir=ruta.parent
    )
    os.close(descriptor)
    temporal = Path(temporal_texto)

    try:
        with temporal.open("w", encoding="utf-8-sig", newline="") as archivo:
            escritor = csv.DictWriter(
                archivo,
                fieldnames=COLUMNAS_SALIDA,
                extrasaction="raise",
                lineterminator="\n",
            )
            escritor.writeheader()
            escritor.writerows(filas)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.chmod(temporal, 0o644)
        os.replace(temporal, ruta)
    except Exception:
        temporal.unlink(missing_ok=True)
        raise


def porcentaje_faltantes(filas: list[dict[str, str]], columna: str) -> float:
    """Calcula faltantes segun el marcador estandar de la salida."""

    if not filas:
        return 0.0
    faltantes = sum(fila[columna] == NO_INFORMADO for fila in filas)
    return faltantes * 100.0 / len(filas)


def imprimir_reporte(
    columnas_fuente: list[str],
    filas_fuente: list[dict[str, str]],
    filas_salida: list[dict[str, str]],
    ruta_salida: Path,
) -> None:
    """Muestra el resumen de calidad solicitado."""

    con_latitud = sum(fila["Latitud"] != NO_INFORMADO for fila in filas_salida)
    con_longitud = sum(fila["Longitud"] != NO_INFORMADO for fila in filas_salida)
    anomalas = sum(fila["Flag_Coordenada_Anomala"] == "1" for fila in filas_salida)
    duplicadas = sum(fila["Flag_Duplicado"] == "1" for fila in filas_salida)

    print("\n=== Reporte de calidad: Colectivos ===")
    print(f"Archivo generado: {ruta_salida}")
    print(f"Filas originales: {len(filas_fuente)}")
    print(f"Filas finales: {len(filas_salida)}")
    print(f"Columnas originales: {len(columnas_fuente)}")
    print(f"Columnas finales: {len(COLUMNAS_SALIDA)}")
    print(f"Filas con Latitud: {con_latitud}")
    print(f"Filas con Longitud: {con_longitud}")
    print(f"Coordenadas anomalas: {anomalas}")
    print(f"Posibles duplicados: {duplicadas}")
    print("Porcentaje de faltantes por columna:")
    for columna in COLUMNAS_SALIDA:
        print(f"  - {columna}: {porcentaje_faltantes(filas_salida, columna):.2f}%")


def procesar_colectivos(entrada: Path, salida: Path) -> None:
    """Ejecuta la lectura, transformacion, validacion y escritura."""

    entrada = entrada.expanduser().resolve()
    salida = salida.expanduser().resolve()
    if entrada == salida:
        raise ValueError("La salida no puede sobrescribir el archivo original.")
    if not entrada.is_file():
        raise FileNotFoundError(f"No existe el archivo de entrada: {entrada}")

    columnas_fuente, filas_fuente = leer_fuente(entrada)
    filas_salida = [transformar_fila(fila) for fila in filas_fuente]
    detectar_duplicados(filas_salida)
    validar_filas(filas_salida, len(filas_fuente))
    escribir_atomico(salida, filas_salida)

    # Relectura compacta para confirmar que el archivo publicado es valido.
    columnas_escritas, filas_escritas = leer_salida(salida)
    if tuple(columnas_escritas) != COLUMNAS_SALIDA:
        raise ValueError("El encabezado escrito no coincide con el esquema final.")
    validar_filas(filas_escritas, len(filas_fuente))
    imprimir_reporte(columnas_fuente, filas_fuente, filas_escritas, salida)


def leer_salida(ruta: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Relee la salida UTF-8-SIG para su validacion final."""

    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        columnas = lector.fieldnames or []
        return columnas, [dict(fila) for fila in lector]


def construir_parser() -> argparse.ArgumentParser:
    """Define la interfaz de linea de comandos."""

    directorio = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Limpia y normaliza paradas de colectivo de CABA."
    )
    parser.add_argument(
        "--entrada",
        type=Path,
        default=directorio / "paradas-de-colectivo.csv",
        help="CSV original (predeterminado: paradas-de-colectivo.csv).",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=directorio / "colectivos_limpio.csv",
        help="Nuevo CSV limpio (predeterminado: colectivos_limpio.csv).",
    )
    return parser


def main() -> int:
    """Punto de entrada del programa."""

    argumentos = construir_parser().parse_args()
    try:
        procesar_colectivos(argumentos.entrada, argumentos.salida)
    except Exception as error:
        print(f"ERROR: {error}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
