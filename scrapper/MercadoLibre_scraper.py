"""Scraper académico de Mercado Libre Inmuebles para CABA.

Obtiene propiedades individuales en Venta y Alquiler y clasifica el alquiler.
Etapa 1: descubre ítems desde búsquedas segmentadas.
Etapa 2: visita cada ficha y lee sus tablas de características.

No se incluyen emprendimientos: una tarjeta de emprendimiento puede representar
varias unidades, precios y superficies, por lo que no equivale a una propiedad.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_SEARCH = "https://inmuebles.mercadolibre.com.ar"
OUTPUT_DIR = Path("output_mercadolibre")
LINKS_FILE = OUTPUT_DIR / "mercadolibre_links_v3.csv"
DATA_FILE = OUTPUT_DIR / "mercadolibre_caba_venta_alquiler_v3.csv"
ERRORS_FILE = OUTPUT_DIR / "mercadolibre_errores_v3.csv"

BARRIOS = [
    "agronomia", "almagro", "balvanera", "barracas", "belgrano", "boedo",
    "caballito", "chacarita", "coghlan", "colegiales", "constitucion",
    "flores", "floresta", "la-boca", "liniers", "mataderos", "monserrat",
    "monte-castro", "nueva-pompeya", "nunez", "palermo", "parque-avellaneda",
    "parque-chacabuco", "parque-chas", "parque-patricios", "paternal",
    "puerto-madero", "recoleta", "retiro", "saavedra", "san-cristobal",
    "san-nicolas", "san-telmo", "velez-sarsfield", "versalles",
    "villa-crespo", "villa-del-parque", "villa-devoto", "villa-lugano",
    "villa-luro", "villa-ortuzar", "villa-pueyrredon", "villa-real",
    "villa-riachuelo", "villa-santa-rita", "villa-soldati", "villa-urquiza",
]

PROPERTY_PATHS = {
    "departamentos": "Departamento",
    "casas": "Casa",
    "ph": "PH",
    "oficinas": "Oficina",
    "locales": "Local",
}

BINARY_FEATURES = [
    "Admite_Mascotas", "Apto_Credito", "Apto_Profesional", "Amoblado",
    "Ascensor", "Balcon", "Terraza", "Patio", "Pileta", "Parrilla", "SUM",
    "Gimnasio", "Laundry", "Seguridad", "Aire_Acondicionado", "Calefaccion",
    "Losa_Radiante", "Agua_Corriente", "Gas_Natural", "Internet",
    "Tiene_Toilette", "Cochera_Opcional", "Dependencia_Servicio", "Lavadero",
    "Dormitorio_Suite", "Vestidor", "Cowork", "Recepcion", "Accesibilidad",
]

# El esquema separa datos nativos de Mercado Libre, ubicación, medidas,
# características binarias y trazabilidad. N/A significa "no informado".
COLUMNS = [
    "Fuente", "Item_ID", "Tipo_Operacion", "Tipo_Alquiler",
    "Modalidad_Publicacion", "Tipo_Propiedad_ML", "Tipo_Propiedad_Inferido",
    "Tipo_Propiedad", "Subtipo_Propiedad",
    "Titulo", "Vendedor", "Tipo_Vendedor",
    "Texto_Fecha_Publicacion", "Publicacion_Destacada",
    "Precio_Raw", "Precio", "Moneda", "Precio_Titulo_Raw", "Precio_Titulo",
    "Moneda_Precio_Titulo", "Flag_Precio_Titulo_Difiere",
    "Expensas_Raw", "Expensas", "Moneda_Expensas", "Expensas_Informadas",
    "Flag_Expensas_Cero_Sospechoso", "Direccion_Publicada", "Calle", "Altura",
    "Barrio_Publicado", "Barrio_Oficial", "Ciudad", "Provincia",
    "Latitud", "Longitud", "Coordenadas_Disponibles", "Fuente_Coordenadas",
    "Piso", "Ambientes", "Ambientes_Titulo", "Dormitorios", "Baños", "Toilettes",
    "Tiene_Toilette", "Cocheras",
    "Bauleras", "Superficie_Total_m2", "Superficie_Cubierta_m2",
    "Superficie_Semicubierta_m2", "Superficie_Descubierta_m2",
    "Superficie_No_Cubierta_m2", "Superficie_Balcon_m2",
    "Antiguedad", "Cantidad_Pisos_Edificio", "Departamentos_Por_Piso",
    "Tipo_Departamento_ML", "Disposicion", "Orientacion", "Estado_Inmueble_ML",
    "Estado_Inmueble_Inferido", "Estado_Inmueble",
    "Admite_Mascotas", "Apto_Credito", "Apto_Profesional", "Amoblado",
    "Ascensor", "Balcon", "Terraza", "Patio", "Pileta", "Parrilla", "SUM",
    "Gimnasio", "Laundry", "Seguridad", "Tipo_Seguridad",
    "Aire_Acondicionado", "Calefaccion", "Losa_Radiante",
    "Agua_Corriente", "Gas_Natural", "Internet",
    "Cochera_Opcional", "Dependencia_Servicio", "Lavadero", "Dormitorio_Suite",
    "Vestidor", "Cowork", "Recepcion", "Accesibilidad",
    *[f"{feature}_ML" for feature in BINARY_FEATURES],
    *[f"{feature}_Inferido" for feature in BINARY_FEATURES],
    *[f"Flag_Conflicto_{feature}" for feature in BINARY_FEATURES],
    "Descripcion", "Caracteristicas_JSON", "Imagen_Principal",
    "Cantidad_Imagenes", "Flag_Precio_Anomalo", "Flag_Superficie_Anomala",
    "Flag_Inconsistencia_Ambientes", "Link", "Fecha_Scraping",
]

BINARY_COLUMNS = (
    set(BINARY_FEATURES)
    | {f"{feature}_ML" for feature in BINARY_FEATURES}
    | {f"{feature}_Inferido" for feature in BINARY_FEATURES}
    | {f"Flag_Conflicto_{feature}" for feature in BINARY_FEATURES}
    | {
        "Coordenadas_Disponibles", "Flag_Precio_Anomalo",
        "Flag_Precio_Titulo_Difiere", "Flag_Expensas_Cero_Sospechoso",
        "Flag_Superficie_Anomala", "Flag_Inconsistencia_Ambientes",
    }
)

LINK_COLUMNS = [
    "Item_ID", "Link", "Tipo_Operacion", "Tipo_Propiedad_Busqueda",
    "Barrio_Busqueda", "Query_Origen", "Titulo_Tarjeta", "Vendedor_Tarjeta",
    "Texto_Fecha_Publicacion", "Publicacion_Destacada",
    "Precio_Raw_Tarjeta", "Precio_Tarjeta", "Moneda_Tarjeta", "Direccion_Tarjeta",
    "Ambientes_Tarjeta", "Baños_Tarjeta", "Superficie_Cubierta_Tarjeta",
]


@dataclass
class Settings:
    operations: list[str]
    property_paths: list[str]
    barrios: list[str]
    max_pages_per_query: int = 42
    target_links: int = 20_000
    sale_share: float = 0.70
    max_details: int = 0
    max_links_per_query: int = 0
    delay: float = 1.5
    only_links: bool = False
    only_details: bool = False
    reprocess_all: bool = False


def clean(value: object) -> str:
    if value is None or value is pd.NA:
        return "N/A"
    try:
        if bool(pd.isna(value)):
            return "N/A"
    except (TypeError, ValueError):
        pass
    text = re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()
    return text or "N/A"


def normalized(value: object) -> str:
    text = unicodedata.normalize("NFKD", clean(value).lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def canonical_url(url: str) -> str:
    parts = urlsplit(urljoin(BASE_SEARCH, url))
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def item_id_from_url(url: str) -> str:
    match = re.search(r"\b(MLA)-?(\d{6,})\b", url, re.IGNORECASE)
    return f"MLA{match.group(2)}" if match else "N/A"


def first_text(soup: BeautifulSoup, selectors: Iterable[str]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            value = clean(node.get_text(" ", strip=True))
            if value != "N/A":
                return value
    return "N/A"


def regex_value(text: object, patterns: Iterable[str]) -> str:
    value = clean(text)
    for pattern in patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            return clean(match.group(1))
    return "N/A"


def parse_number(value: object) -> object:
    match = re.search(r"[-+]?\d[\d.,]*", clean(value))
    if not match:
        return "N/A"
    token = match.group().strip(".,")
    if "," in token and "." in token:
        last_separator = max(token.rfind(","), token.rfind("."))
        decimals = len(token) - last_separator - 1
        if decimals in {1, 2}:
            decimal = token[last_separator]
            thousands = "." if decimal == "," else ","
            token = token.replace(thousands, "").replace(decimal, ".")
        else:
            token = token.replace(".", "").replace(",", "")
    elif "." in token or "," in token:
        separator = "." if "." in token else ","
        parts = token.split(separator)
        if len(parts) > 2 or (len(parts) == 2 and len(parts[-1]) == 3):
            token = "".join(parts)
        else:
            token = ".".join(parts)
    try:
        result = float(token)
        return int(result) if result.is_integer() else result
    except ValueError:
        return "N/A"


def parse_money(value: object) -> tuple[object, str]:
    text = clean(value)
    match = re.search(r"USD|US\$|U\$S|ARS|\$", text, re.IGNORECASE)
    if not match:
        return "N/A", "N/A"
    token = match.group().upper()
    currency = "USD" if token in {"USD", "US$", "U$S"} else "ARS"
    amount_match = re.search(r"[-+]?\d[\d.,]*", text)
    amount = amount_match.group() if amount_match else "N/A"
    return parse_number(amount), currency


def yes_no(value: object) -> object:
    text = normalized(value)
    if text in {"si", "sí", "1", "true", "con"}:
        return 1
    if text in {"no", "0", "false", "sin"}:
        return 0
    return pd.NA


def parse_address(value: object) -> tuple[str, str]:
    text = clean(value)
    # Mercado Libre puede ocultar la numeración usando "al 2300".
    match = re.match(r"^(.+?)\s+(?:al\s+)?(\d{1,6})(?:\D.*)?$", text, re.IGNORECASE)
    if not match:
        return "N/A", "N/A"
    return clean(match.group(1)).strip(" ,-"), match.group(2)


def split_location(value: object) -> tuple[str, str, str, str, str]:
    text = clean(value)
    parts = [clean(part) for part in text.split(",") if clean(part) != "N/A"]
    # Mercado Libre permite comas dentro de la dirección (por ejemplo,
    # "Rivadavia, AV. 6000. Entre..."). Por eso los niveles geográficos se
    # retiran desde la derecha, en vez de asumir posiciones fijas.
    caba_names = {"capital federal", "caba", "ciudad autonoma de buenos aires"}
    while parts and normalized(parts[-1]) in caba_names:
        parts.pop()
    known_barrios = {normalized(name.replace("-", " ")) for name in BARRIOS}
    if len(parts) >= 2:
        barrio = parts.pop()
    elif len(parts) == 1 and normalized(parts[0]) in known_barrios:
        barrio = parts.pop()
    else:
        barrio = "N/A"
    address = clean(", ".join(parts)) if parts else "N/A"
    provincia = "Capital Federal"
    street, number = parse_address(address)
    return address, street, number, barrio, clean(provincia)


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4, connect=4, read=4, status=4,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4))
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
        ),
        "Accept-Language": "es-AR,es;q=0.9",
    })
    return session


def get_soup(session: requests.Session, url: str, timeout: int = 45) -> BeautifulSoup:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    if not response.content:
        raise RuntimeError("Respuesta vacía")
    return BeautifulSoup(response.content, "html.parser")


def search_url(property_path: str, operation: str, barrio: str, page_number: int) -> str:
    individual = "propiedades-individuales/" if property_path in {
        "departamentos", "casas", "oficinas",
    } else ""
    base = f"{BASE_SEARCH}/{property_path}/{operation}/{individual}capital-federal/{barrio}/"
    if page_number == 1:
        return base
    offset = 1 + 48 * (page_number - 1)
    return f"{base}_Desde_{offset}_NoIndex_True"


def parse_card(
    card: BeautifulSoup, operation: str, property_path: str, barrio: str, query_url: str,
) -> dict | None:
    link_node = card.select_one("a.poly-component__title[href]")
    if not link_node:
        return None
    url = canonical_url(link_node.get("href", ""))
    item_id = item_id_from_url(url)
    if item_id == "N/A":
        return None
    text = normalized(card.get_text(" ", strip=True))
    if "emprendimiento" in text:
        return None
    headline = first_text(card, [".poly-component__headline"])
    if operation not in normalized(headline):
        return None
    location = first_text(card, [".poly-component__location"])
    if "capital federal" not in normalized(location):
        return None

    price_text = first_text(card, [".poly-price__amount", ".andes-money-amount"])
    price, currency = parse_money(price_text)
    featured_node = card.select_one(".poly-component__featured")
    is_featured = int(
        featured_node is not None
        and normalized(featured_node.get_text(" ", strip=True)) == "destacado"
    )
    attributes = [clean(node.get_text(" ", strip=True)) for node in card.select(".poly-attributes_list__item")]
    attributes_text = " | ".join(attributes)

    return {
        "Item_ID": item_id,
        "Link": url,
        "Tipo_Operacion": operation.title(),
        "Tipo_Propiedad_Busqueda": PROPERTY_PATHS.get(property_path, property_path.title()),
        "Barrio_Busqueda": barrio,
        "Query_Origen": query_url,
        "Titulo_Tarjeta": clean(link_node.get_text(" ", strip=True)),
        "Vendedor_Tarjeta": first_text(card, [".poly-component__seller"]),
        "Texto_Fecha_Publicacion": first_text(card, [".poly-component__float-highlight"]),
        "Publicacion_Destacada": is_featured,
        "Precio_Raw_Tarjeta": price_text,
        "Precio_Tarjeta": price,
        "Moneda_Tarjeta": currency,
        "Direccion_Tarjeta": location,
        "Ambientes_Tarjeta": parse_number(regex_value(attributes_text, [r"(\d+)\s*amb"])),
        "Baños_Tarjeta": parse_number(regex_value(attributes_text, [r"(\d+(?:[.,]\d+)?)\s*ba[nñ]o"])),
        "Superficie_Cubierta_Tarjeta": parse_number(regex_value(attributes_text, [r"(\d+(?:[.,]\d+)?)\s*m[²2]\s*cub"])),
    }


def table_attributes(soup: BeautifulSoup) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in soup.select(".andes-table tr"):
        cells = [clean(cell.get_text(" ", strip=True)) for cell in row.select("th, td")]
        if len(cells) >= 2 and cells[0] != "N/A":
            result.setdefault(cells[0], cells[1])
    return result


def rendering_state(soup: BeautifulSoup) -> dict:
    """Lee el estado JSON público sin ejecutar JavaScript."""
    script = soup.select_one("#__NORDIC_RENDERING_CTX__")
    if not script:
        return {}
    raw = script.string or script.get_text()
    if "=" not in raw:
        return {}
    try:
        payload, _ = json.JSONDecoder().raw_decode(raw.split("=", 1)[1].lstrip())
    except (json.JSONDecodeError, TypeError):
        return {}
    try:
        state = payload["appProps"]["pageProps"]["initialState"]
    except (KeyError, TypeError):
        return {}
    return state if isinstance(state, dict) else {}


def state_component(state: dict, name: str) -> dict:
    components = state.get("components", {})
    component = components.get(name, {}) if isinstance(components, dict) else {}
    return component if isinstance(component, dict) else {}


def structured_attributes(state: dict) -> dict[str, str]:
    """Respaldo para fichas donde la tabla visible llega incompleta."""
    result: dict[str, str] = {}
    component = state_component(state, "highlighted_specs_attrs")
    children = component.get("components", [])
    if not isinstance(children, list):
        return result
    for child in children:
        if not isinstance(child, dict) or child.get("type") != "technical_specifications":
            continue
        for group in child.get("specs", []):
            if not isinstance(group, dict):
                continue
            for attribute in group.get("attributes", []):
                if not isinstance(attribute, dict):
                    continue
                key, value = clean(attribute.get("id")), clean(attribute.get("text"))
                if key != "N/A" and value != "N/A":
                    result.setdefault(key, value)
    return result


def all_attributes(soup: BeautifulSoup, state: dict) -> dict[str, str]:
    attributes = structured_attributes(state)
    # La tabla visible tiene prioridad si ambas fuentes difieren.
    attributes.update(table_attributes(soup))
    return attributes


def structured_coordinates(state: dict) -> tuple[object, object, object, str]:
    component = state_component(state, "location_and_points")
    component_name = "location_and_points"
    if not component:
        component = state_component(state, "location")
        component_name = "location"
    map_info = component.get("map_info", {})
    location = map_info.get("location", {}) if isinstance(map_info, dict) else {}
    try:
        latitude = float(location["latitude"])
        longitude = float(location["longitude"])
    except (KeyError, TypeError, ValueError):
        return "N/A", "N/A", pd.NA, "N/A"
    # Rango amplio de CABA: evita confundir el pin con coordenadas país/sitio.
    if not (-34.80 <= latitude <= -34.40 and -58.70 <= longitude <= -58.25):
        return "N/A", "N/A", pd.NA, "N/A"
    return latitude, longitude, 1, f"Mercado Libre: {component_name}"


def structured_seller(state: dict) -> tuple[str, str]:
    component = state_component(state, "seller_profile")
    seller_name = component.get("seller_name", {})
    title = seller_name.get("title", {}) if isinstance(seller_name, dict) else {}
    name = clean(title.get("text") if isinstance(title, dict) else None)
    track = state.get("track", {})
    try:
        seller_type = track["melidata_event"]["event_data"]["seller_type"]
    except (KeyError, TypeError):
        seller_type = None
    type_map = {
        "real_estate_agency": "Inmobiliaria",
        "private_seller": "Particular",
        "owner": "Particular",
    }
    raw_type = clean(seller_type)
    mapped_type = type_map.get(normalized(raw_type), raw_type)
    return name, mapped_type


def structured_gallery(state: dict) -> tuple[object, str]:
    component = state_component(state, "gallery_mosaic")
    count = component.get("total_count", "N/A")
    primary = component.get("primary", {})
    image = clean(primary.get("src") if isinstance(primary, dict) else None)
    return parse_number(count), image


def attribute_value(attributes: dict[str, str], *names: str) -> str:
    normalized_attributes = {normalized(key): value for key, value in attributes.items()}
    for name in names:
        if normalized(name) in normalized_attributes:
            return normalized_attributes[normalized(name)]
    return "N/A"


def json_ld_data(soup: BeautifulSoup) -> tuple[str, object, str, str]:
    title = "N/A"
    price: object = "N/A"
    currency = "N/A"
    image = "N/A"
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict) or data.get("@type") != "Product":
            continue
        title = clean(data.get("name"))
        image = clean(data.get("image"))
        offers = data.get("offers", {})
        if isinstance(offers, dict):
            price = offers.get("price", "N/A")
            currency = clean(offers.get("priceCurrency"))
        break
    return title, price, currency, image


def location_from_detail(soup: BeautifulSoup, state: dict, fallback: object) -> str:
    component = state_component(state, "location_and_points")
    if not component:
        component = state_component(state, "location")
    rows = component.get("content_rows", [])
    if isinstance(rows, list) and rows:
        try:
            structured = clean(rows[0]["title"]["text"])
            if structured != "N/A":
                return structured
        except (KeyError, TypeError):
            pass
    value = first_text(soup, [
        ".ui-vip-location__subtitle .ui-pdp-media__title",
        ".ui-vip-location__subtitle", ".ui-pdp-media__title",
    ])
    return fallback if value == "N/A" else value


def count_images(soup: BeautifulSoup, state: dict) -> int | str:
    structured_count, _ = structured_gallery(state)
    if structured_count != "N/A":
        return structured_count
    urls = set()
    for image in soup.select(
        ".vis-gallery-mosaic img, .gallery-image img, .ui-pdp-gallery img, "
        "figure.ui-pdp-gallery__figure img"
    ):
        url = image.get("data-zoom") or image.get("data-src") or image.get("src")
        if url:
            urls.add(url.split("?")[0])
    return len(urls) if urls else "N/A"


def ml_property_type(seed: dict, state: dict) -> str:
    try:
        domain = normalized(state["track"]["melidata_event"]["event_data"]["domain_id"])
    except (KeyError, TypeError):
        domain = ""
    mapping = {
        "apartments": "Departamento", "houses": "Casa", "offices": "Oficina",
        "retail_spaces": "Local", "lands": "Terreno", "warehouses": "Depósito/Galpón",
    }
    for token, label in mapping.items():
        if token in domain:
            return label
    return clean(seed.get("Tipo_Propiedad_Busqueda"))


def inferred_property_type(title: str, description: str) -> str:
    title_text = normalized(title)
    description_text = normalized(description)[:800]
    patterns = (
        ("PH", (r"\bph\b", r"propiedad\s+horizontal")),
        ("Departamento", (r"\bdepartamentos?\b", r"\bdeptos?\.?\b")),
        ("Casa", (r"\bcasas?\b", r"\bchalets?\b")),
        ("Oficina", (r"\boficinas?\b",)),
        ("Local", (r"\blocal(?:es)?\b", r"\blocal(?:es)?\s+comerciales?\b", r"\blocal\s+a\s+la\s+calle\b")),
    )
    title_matches: list[tuple[int, int, str]] = []
    for priority, (label, expressions) in enumerate(patterns):
        for expression in expressions:
            match = re.search(expression, title_text)
            if match:
                title_matches.append((match.start(), priority, label))
    if title_matches:
        return min(title_matches)[2]
    contextual_prefix = r"(?:se\s+trata\s+de|venta\s+de|alquiler\s+de|propiedad|inmueble|unidad)"
    for label, expressions in patterns:
        if any(
            re.search(rf"{contextual_prefix}.{{0,35}}{expression}", description_text)
            for expression in expressions
        ):
            return label
    return "N/A"


def property_subtype(attributes: dict[str, str], title: str, description: str, general: str) -> str:
    explicit = attribute_value(
        attributes, "Subtipo de propiedad", "Subtipo de departamento",
        "Tipo de departamento", "Tipo de casa", "Tipo de oficina", "Tipo de local",
    )
    generic = {
        "departamento", "casa", "ph", "oficina", "local", "propiedad", "estandar",
    }
    subtype_labels = {
        "duplex": "Dúplex", "triplex": "Tríplex", "semipiso": "Semipiso",
        "loft": "Loft", "monoambiente": "Monoambiente", "penthouse": "Penthouse",
    }
    if explicit != "N/A" and normalized(explicit) not in generic:
        return subtype_labels.get(normalized(explicit), explicit)
    evidence = normalized(f"{title} {description}")
    for token, label in subtype_labels.items():
        if re.search(rf"\b{re.escape(token)}\b", evidence):
            return label
    if re.search(r"\b(?:departamento\s+)?tipo\s+piso\b", evidence):
        return "Piso"
    return "N/A"


def classify_rental(operation: str, title: str, description: str) -> str:
    if operation != "Alquiler":
        return "N/A"
    text = normalized(f"{title} {description}")
    temporary = (
        r"alquiler\s+temporari", r"contrato\s+temporari", r"temporari[oa]",
        r"alquiler\s+por\s+(?:dia|semana|mes)", r"renta\s+temporaria",
        r"vacacional", r"airbnb", r"estadias?\s+cortas?",
    )
    traditional = (
        r"alquiler\s+tradicional", r"contrato\s+(?:de\s+)?(?:24|36)\s+mes",
        r"contrato\s+(?:de\s+)?(?:2|3)\s+anos", r"locacion\s+permanente",
        r"alquiler\s+para\s+vivienda\s+permanente",
    )
    if any(re.search(pattern, text) for pattern in temporary):
        return "Temporario"
    if any(re.search(pattern, text) for pattern in traditional):
        return "Tradicional"
    return "Desconocido"


BINARY_ATTRIBUTE_NAMES: dict[str, tuple[str, ...]] = {
    "Admite_Mascotas": ("Admite mascotas",), "Apto_Credito": ("Apto crédito",),
    "Apto_Profesional": ("Apto profesional",), "Amoblado": ("Amoblado",),
    "Ascensor": ("Ascensor",), "Balcon": ("Balcón",), "Terraza": ("Terraza",),
    "Patio": ("Patio",), "Pileta": ("Pileta",), "Parrilla": ("Parrilla",),
    "SUM": ("SUM", "Salón de usos múltiples"), "Gimnasio": ("Gimnasio",),
    "Laundry": ("Lavandería", "Laundry"), "Seguridad": ("Seguridad",),
    "Aire_Acondicionado": ("Aire acondicionado",), "Calefaccion": ("Calefacción",),
    "Losa_Radiante": ("Losa radiante", "Piso radiante"),
    "Agua_Corriente": ("Agua corriente",), "Gas_Natural": ("Gas natural",),
    "Internet": ("Acceso a internet", "Internet"),
    "Tiene_Toilette": ("Toilettes", "Toilette"),
    "Cochera_Opcional": ("Cochera opcional", "Cocheras opcionales"),
    "Dependencia_Servicio": ("Dependencia de servicio",), "Lavadero": ("Lavadero",),
    "Dormitorio_Suite": ("Dormitorio en suite", "Suite"), "Vestidor": ("Vestidor",),
    "Cowork": ("Cowork", "Coworking"), "Recepcion": ("Recepción",),
    "Accesibilidad": (
        "Accesibilidad", "Acceso para personas con movilidad reducida",
        "Apto movilidad reducida",
    ),
}


# (patrones positivos, patrones negativos, contextos que no prueban presencia)
BINARY_TEXT_RULES: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "Admite_Mascotas": ((r"se\s+(?:admiten|aceptan)\s+mascotas", r"apto\s+mascotas", r"pet\s*friendly"), (r"no\s+(?:se\s+)?(?:admiten|aceptan)\s+mascotas", r"sin\s+mascotas"), ()),
    "Apto_Credito": ((r"apto\s+(?:a\s+)?credito",), (r"no\s+apto\s+(?:a\s+)?credito",), ()),
    "Apto_Profesional": ((r"apto\s+profesional",), (r"no\s+apto\s+profesional",), ()),
    "Amoblado": ((r"(?:se\s+)?(?:alquila|vende|entrega)\s+amoblad[oa]", r"totalmente\s+amoblad[oa]", r"con\s+muebles"), (r"sin\s+(?:amoblar|muebles)", r"no\s+amoblad[oa]"), ()),
    "Ascensor": ((r"(?:edificio\s+)?con\s+ascensor", r"posee\s+ascensor"), (r"sin\s+ascensor", r"no\s+(?:tiene|posee)\s+ascensor"), ()),
    "Balcon": ((r"con\s+balcon", r"balcon\s+(?:propio|privado|corrido|aterrazado|al\s+frente)"), (r"sin\s+balcon", r"no\s+(?:tiene|posee)\s+balcon"), ()),
    "Terraza": ((r"terraza\s+(?:propia|privada|exclusiva|de\s+uso\s+exclusivo)", r"con\s+terraza(?!\s+de\s+uso\s+comun)"), (r"sin\s+terraza", r"no\s+(?:tiene|posee)\s+terraza"), (r"terraza\s+de\s+uso\s+comun", r"terraza\s+comun")),
    "Patio": ((r"patio\s+(?:propio|privado|exclusivo)", r"con\s+patio(?!\s+comun)"), (r"sin\s+patio", r"no\s+(?:tiene|posee)\s+patio"), (r"patio\s+(?:comun|de\s+uso\s+comun)",)),
    "Pileta": ((r"(?:con|posee)\s+(?:una\s+)?pileta", r"piscina"), (r"sin\s+(?:pileta|piscina)",), ()),
    "Parrilla": ((r"(?:con|posee)\s+parrilla", r"sector\s+de\s+parrillas"), (r"sin\s+parrilla",), ()),
    "SUM": ((r"\bsum\b", r"salon\s+de\s+usos\s+multiples"), (r"sin\s+(?:sum|salon\s+de\s+usos\s+multiples)",), ()),
    "Gimnasio": ((r"\bgimnasio\b", r"\bgym\b"), (r"sin\s+(?:gimnasio|gym)",), ()),
    "Laundry": ((r"\blaundry\b", r"lavanderia\s+comun"), (r"sin\s+(?:laundry|lavanderia\s+comun)",), ()),
    "Seguridad": ((r"seguridad\s+(?:24\s*(?:hs|horas)|permanente)", r"vigilancia"), (r"sin\s+(?:seguridad|vigilancia)",), ()),
    "Aire_Acondicionado": ((r"aire\s+acondicionado", r"equipos?\s+de\s+aire"), (r"sin\s+aire\s+acondicionado",), ()),
    "Calefaccion": ((r"\bcalefaccion\b", r"caldera"), (r"sin\s+calefaccion",), ()),
    "Losa_Radiante": ((r"losa\s+radiante", r"piso\s+radiante"), (r"sin\s+(?:losa|piso)\s+radiante",), ()),
    "Agua_Corriente": ((r"agua\s+corriente",), (r"sin\s+agua\s+corriente",), ()),
    "Gas_Natural": ((r"gas\s+natural",), (r"sin\s+gas(?:\s+natural)?",), ()),
    "Internet": ((r"acceso\s+a\s+internet", r"conexion\s+a\s+internet", r"wifi"), (r"sin\s+(?:internet|wifi)",), ()),
    "Tiene_Toilette": ((r"\btoilettes?\b",), (r"sin\s+toilettes?",), ()),
    "Cochera_Opcional": ((r"cochera\s+opcional", r"cochera\s+(?:disponible|se\s+vende)\s+aparte", r"posibilidad\s+de\s+cochera", r"cochera\s+no\s+incluida"), (r"cochera\s+incluida",), ()),
    "Dependencia_Servicio": ((r"dependencia\s+de\s+servicio",), (r"sin\s+dependencia\s+de\s+servicio",), ()),
    "Lavadero": ((r"lavadero\s+(?:independiente|propio|separado)", r"con\s+lavadero"), (r"sin\s+lavadero",), ()),
    "Dormitorio_Suite": ((r"dormitorio\s+en\s+suite", r"suite\s+principal"), (r"sin\s+(?:dormitorio\s+en\s+)?suite",), ()),
    "Vestidor": ((r"\bvestidor\b",), (r"sin\s+vestidor",), ()),
    "Cowork": ((r"\bcowork(?:ing)?\b",), (r"sin\s+cowork(?:ing)?",), ()),
    "Recepcion": ((r"recepcion\s+(?:24\s*(?:hs|horas)|permanente)", r"hall\s+de\s+recepcion"), (r"sin\s+recepcion",), ()),
    "Accesibilidad": ((r"acces(?:o|ible)\s+(?:para|a)\s+personas\s+con\s+movilidad\s+reducida", r"apto\s+silla\s+de\s+ruedas"), (r"no\s+accesible", r"sin\s+acceso\s+para\s+movilidad\s+reducida"), ()),
}


def binary_known(value: object) -> bool:
    if value is None or value is pd.NA:
        return False
    return str(value) in {"0", "1"}


def infer_binary_from_text(feature: str, title: str, description: str) -> object:
    text = normalized(f"{title}. {description}")
    positive, negative, blocked = BINARY_TEXT_RULES.get(feature, ((), (), ()))
    if any(re.search(pattern, text) for pattern in negative):
        return 0
    if any(re.search(pattern, text) for pattern in blocked):
        return pd.NA
    if any(re.search(pattern, text) for pattern in positive):
        return 1
    return pd.NA


def binary_evidence(attributes: dict[str, str], title: str, description: str) -> dict[str, object]:
    result: dict[str, object] = {}
    for feature in BINARY_FEATURES:
        structured = yes_no(attribute_value(attributes, *BINARY_ATTRIBUTE_NAMES[feature]))
        inferred = infer_binary_from_text(feature, title, description)
        if binary_known(structured) and binary_known(inferred):
            conflict: object = int(int(structured) != int(inferred))
        else:
            conflict = pd.NA
        consolidated = structured if binary_known(structured) else inferred
        result[feature] = consolidated
        result[f"{feature}_ML"] = structured
        result[f"{feature}_Inferido"] = inferred
        result[f"Flag_Conflicto_{feature}"] = conflict
    return result


def rooms_from_title(title: str) -> object:
    text = normalized(title)
    if re.search(r"\bmonoambiente\b", text):
        return 1
    match = re.search(r"\b(\d{1,2})\s*(?:amb(?:\.|ientes?)?)\b", text)
    if match:
        return int(match.group(1))
    words = {"un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5}
    match = re.search(r"\b(un|uno|dos|tres|cuatro|cinco)\s+ambientes?\b", text)
    return words[match.group(1)] if match else "N/A"


def price_from_title(title: str) -> tuple[str, object, str]:
    patterns = (
        r"(?:USD|US\$|U\$S|ARS|\$)\s*\d[\d.,]*",
        r"\d[\d.,]*\s*(?:USD|ARS)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            raw = clean(match.group())
            amount, currency = parse_money(raw)
            return raw, amount, currency
    return "N/A", "N/A", "N/A"


def differing_price_flag(price: object, currency: str, title_price: object, title_currency: str) -> object:
    if price == "N/A" or title_price == "N/A" or currency == "N/A" or title_currency == "N/A":
        return pd.NA
    if currency != title_currency:
        return 1
    return int(float(price) != float(title_price))


def normalized_property_state(value: object) -> str:
    text = normalized(value)
    mapping = {
        "en pozo": "En pozo", "a estrenar": "A estrenar", "nuevo": "A estrenar",
        "usado": "Usado", "reciclado": "Reciclado", "refaccionado": "Reciclado",
        "remodelado": "Reciclado", "a refaccionar": "A refaccionar",
        "a reciclar": "A refaccionar",
    }
    return mapping.get(text, "Desconocido")


def inferred_property_state(title: str, description: str) -> str:
    text = normalized(f"{title}. {description}")
    rules = (
        ("A refaccionar", (r"a\s+refaccionar", r"para\s+(?:refaccionar|reciclar)", r"requiere\s+refaccion")),
        ("En pozo", (r"\ben\s+pozo\b", r"\bpreventa\b", r"en\s+construccion")),
        ("A estrenar", (r"a\s+estrenar", r"sin\s+estrenar", r"primera\s+ocupacion")),
        ("Reciclado", (r"totalmente\s+reciclad[oa]", r"reciclad[oa]\s+a\s+nuev[oa]", r"recientemente\s+(?:reciclad[oa]|refaccionad[oa]|remodelad[oa])")),
        ("Usado", (r"estado\s+usado", r"inmueble\s+usado", r"propiedad\s+usada")),
    )
    for label, patterns in rules:
        if any(re.search(pattern, text) for pattern in patterns):
            return label
    return "Desconocido"


def floor_from_published_location(location: str) -> object:
    value = regex_value(location, [r"\b(\d{1,3})(?:er|ro|do|to|°|º)?\s*piso\b"])
    return parse_number(value)


def price_anomaly(price: object, currency: str, operation: str) -> object:
    if price == "N/A" or currency == "N/A":
        return pd.NA
    try:
        amount = float(price)
    except (TypeError, ValueError):
        return pd.NA
    if amount <= 0:
        return 1
    bounds = {
        ("Venta", "USD"): (5_000, 20_000_000),
        ("Venta", "ARS"): (1_000_000, 30_000_000_000),
        ("Alquiler", "ARS"): (10_000, 100_000_000),
        ("Alquiler", "USD"): (10, 100_000),
    }
    minimum, maximum = bounds.get((operation, currency), (0, float("inf")))
    return int(not minimum <= amount <= maximum)


def surface_anomaly(total: object, covered: object) -> object:
    if total == "N/A" and covered == "N/A":
        return pd.NA
    values = [value for value in (total, covered) if value != "N/A"]
    try:
        numeric_values = [float(value) for value in values]
    except (TypeError, ValueError):
        return pd.NA
    if any(value <= 0 or value > 10_000 for value in numeric_values):
        return 1
    if total != "N/A" and covered != "N/A" and float(covered) > float(total):
        return 1
    return 0


def room_anomaly(structured_rooms: object, title_rooms: object) -> object:
    if structured_rooms == "N/A" or title_rooms == "N/A":
        return pd.NA
    try:
        return int(float(structured_rooms) != float(title_rooms))
    except (TypeError, ValueError):
        return pd.NA


def expenses_quality(raw: str, amount: object) -> tuple[int, object]:
    informed = int(clean(raw) != "N/A")
    if not informed or amount == "N/A":
        return informed, pd.NA
    if float(amount) != 0:
        return informed, 0
    explicit_zero = re.search(r"\b(?:sin\s+expensas|no\s+paga\s+expensas)\b", normalized(raw))
    return informed, 0 if explicit_zero else 1


def uncovered_surface(total: object, covered: object) -> object:
    if total == "N/A" or covered == "N/A":
        return "N/A"
    try:
        difference = float(total) - float(covered)
    except (TypeError, ValueError):
        return "N/A"
    if difference < 0:
        return "N/A"
    return int(difference) if difference.is_integer() else difference


def detail_record(soup: BeautifulSoup, seed: dict) -> dict | None:
    state = rendering_state(soup)
    attributes = all_attributes(soup, state)
    title_json, price_json, currency_json, image = json_ld_data(soup)
    title = first_text(soup, ["h1.ui-pdp-title", "h1"])
    if title == "N/A":
        title = title_json if title_json != "N/A" else seed.get("Titulo_Tarjeta", "N/A")

    operation = clean(seed.get("Tipo_Operacion")).title()
    if operation not in {"Venta", "Alquiler"}:
        return None

    location = location_from_detail(soup, state, seed.get("Direccion_Tarjeta", "N/A"))
    if "capital federal" not in normalized(location):
        return None
    address, street, height, barrio, provincia = split_location(location)
    ciudad = "Capital Federal"
    latitude, longitude, has_coordinates, coordinates_source = structured_coordinates(state)

    price_text = first_text(soup, [".ui-pdp-price__second-line", ".ui-pdp-price"])
    price_raw = price_text if price_text != "N/A" else seed.get("Precio_Raw_Tarjeta", "N/A")
    parsed_price, parsed_currency = parse_money(price_raw)
    # JSON-LD es numérico y evita ambigüedades con separadores de miles.
    price = parse_number(price_json) if price_json != "N/A" else parsed_price
    currency = currency_json if currency_json != "N/A" else parsed_currency
    if price == "N/A":
        price = seed.get("Precio_Tarjeta", "N/A")
    if currency == "N/A":
        currency = seed.get("Moneda_Tarjeta", "N/A")

    expenses_raw = attribute_value(attributes, "Expensas")
    expenses, expenses_currency = parse_money(expenses_raw)
    expenses_informed, expenses_zero_suspicious = expenses_quality(expenses_raw, expenses)

    description = first_text(soup, [".ui-pdp-description__content", ".ui-pdp-description"])
    description = re.sub(r"^Descripci[oó]n\s*", "", description, flags=re.IGNORECASE)

    seller_structured, seller_type = structured_seller(state)
    seller = seller_structured
    if seller == "N/A":
        seller = first_text(soup, ["a[href='#seller_profile']", ".ui-vip-profile-info__title"])
    if seller == "N/A":
        seller = seed.get("Vendedor_Tarjeta", "N/A")

    property_type_ml = ml_property_type(seed, state)
    property_type_inferred = inferred_property_type(title, description)
    general_type = property_type_ml if property_type_ml != "N/A" else property_type_inferred
    subtype = property_subtype(attributes, title, description, general_type)
    rental_type = classify_rental(operation, title, description)
    title_price_raw, title_price, title_currency = price_from_title(title)
    title_price_flag = differing_price_flag(price, currency, title_price, title_currency)

    def numeric(*names: str) -> object:
        return parse_number(attribute_value(attributes, *names))

    floor = numeric("Número de piso de la unidad", "Piso")
    if floor == "N/A":
        floor = floor_from_published_location(location)
    rooms = numeric("Ambientes")
    title_rooms = rooms_from_title(title)
    bedrooms = numeric("Dormitorios")
    total_surface = numeric("Superficie total")
    covered_surface = numeric("Superficie cubierta")
    no_covered_surface = uncovered_surface(total_surface, covered_surface)
    balcony_surface = numeric(
        "Superficie del balcón", "Superficie balcón", "Superficie de balcón"
    )
    toilettes_raw = attribute_value(attributes, "Toilettes", "Toilette")
    toilettes = parse_number(toilettes_raw) if yes_no(toilettes_raw) is pd.NA else "N/A"
    binary_values = binary_evidence(attributes, title, description)
    if not binary_known(binary_values["Tiene_Toilette"]) and toilettes != "N/A":
        inferred_toilette = int(float(toilettes) > 0)
        binary_values["Tiene_Toilette"] = inferred_toilette
        binary_values["Tiene_Toilette_ML"] = inferred_toilette
    state_ml_raw = attribute_value(attributes, "Estado", "Estado del inmueble")
    state_ml = normalized_property_state(state_ml_raw)
    state_inferred = inferred_property_state(title, description)
    final_state = state_ml if state_ml != "Desconocido" else state_inferred
    image_count, structured_image = structured_gallery(state)
    if image == "N/A" and structured_image != "N/A":
        image = structured_image

    return {
        "Fuente": "Mercado Libre",
        "Item_ID": seed.get("Item_ID", "N/A"),
        "Tipo_Operacion": operation,
        "Tipo_Alquiler": rental_type,
        "Modalidad_Publicacion": "Propiedad individual",
        "Tipo_Propiedad_ML": property_type_ml,
        "Tipo_Propiedad_Inferido": property_type_inferred,
        "Tipo_Propiedad": general_type,
        "Subtipo_Propiedad": subtype,
        "Titulo": clean(title),
        "Vendedor": seller,
        "Tipo_Vendedor": seller_type,
        "Texto_Fecha_Publicacion": seed.get("Texto_Fecha_Publicacion", "N/A"),
        "Publicacion_Destacada": seed.get("Publicacion_Destacada", 0),
        "Precio_Raw": clean(price_raw), "Precio": price, "Moneda": currency,
        "Precio_Titulo_Raw": title_price_raw, "Precio_Titulo": title_price,
        "Moneda_Precio_Titulo": title_currency,
        "Flag_Precio_Titulo_Difiere": title_price_flag,
        "Expensas_Raw": clean(expenses_raw), "Expensas": expenses,
        "Moneda_Expensas": expenses_currency,
        "Expensas_Informadas": expenses_informed,
        "Flag_Expensas_Cero_Sospechoso": expenses_zero_suspicious,
        "Direccion_Publicada": address, "Calle": street, "Altura": height,
        "Barrio_Publicado": barrio, "Barrio_Oficial": "N/A",
        "Ciudad": ciudad, "Provincia": provincia,
        "Latitud": latitude, "Longitud": longitude,
        "Coordenadas_Disponibles": has_coordinates,
        "Fuente_Coordenadas": coordinates_source,
        "Piso": floor, "Ambientes": rooms, "Ambientes_Titulo": title_rooms,
        "Dormitorios": bedrooms, "Baños": numeric("Baños"),
        "Toilettes": toilettes,
        "Cocheras": numeric("Cocheras"),
        "Bauleras": numeric("Bauleras"), "Superficie_Total_m2": total_surface,
        "Superficie_Cubierta_m2": covered_surface,
        "Superficie_Semicubierta_m2": numeric("Superficie semicubierta"),
        "Superficie_Descubierta_m2": numeric("Superficie descubierta"),
        "Superficie_No_Cubierta_m2": no_covered_surface,
        "Superficie_Balcon_m2": balcony_surface,
        "Antiguedad": numeric("Antigüedad"),
        "Cantidad_Pisos_Edificio": numeric("Cantidad de pisos"),
        "Departamentos_Por_Piso": numeric("Departamentos por piso"),
        "Tipo_Departamento_ML": attribute_value(attributes, "Tipo de departamento"),
        "Disposicion": attribute_value(attributes, "Disposición"),
        "Orientacion": attribute_value(attributes, "Orientación"),
        "Estado_Inmueble_ML": state_ml_raw,
        "Estado_Inmueble_Inferido": state_inferred,
        "Estado_Inmueble": final_state,
        **binary_values,
        "Tipo_Seguridad": attribute_value(attributes, "Tipo de seguridad"),
        "Descripcion": clean(description),
        "Caracteristicas_JSON": json.dumps(attributes, ensure_ascii=False, sort_keys=True),
        "Imagen_Principal": image,
        "Cantidad_Imagenes": image_count if image_count != "N/A" else count_images(soup, state),
        "Flag_Precio_Anomalo": price_anomaly(price, currency, operation),
        "Flag_Superficie_Anomala": surface_anomaly(total_surface, covered_surface),
        "Flag_Inconsistencia_Ambientes": room_anomaly(rooms, title_rooms),
        "Link": canonical_url(seed.get("Link", "")),
        "Fecha_Scraping": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def read_links() -> pd.DataFrame:
    if not LINKS_FILE.exists():
        return pd.DataFrame(columns=LINK_COLUMNS)
    return pd.read_csv(LINKS_FILE, dtype=str).fillna("N/A").reindex(columns=LINK_COLUMNS, fill_value="N/A")


def save_links(records: dict[str, dict]) -> None:
    frame = pd.DataFrame(records.values()).reindex(columns=LINK_COLUMNS, fill_value="N/A")
    frame = frame.drop_duplicates("Item_ID", keep="last").sort_values("Item_ID")
    frame.to_csv(LINKS_FILE, index=False, encoding="utf-8-sig")


def append_error(url: str, reason: str) -> None:
    pd.DataFrame([{
        "Link": url, "Error": clean(reason),
        "Fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
    }]).to_csv(ERRORS_FILE, mode="a", header=not ERRORS_FILE.exists(), index=False, encoding="utf-8-sig")


def operation_targets(settings: Settings) -> dict[str, int]:
    if set(settings.operations) == {"venta", "alquiler"}:
        sales = round(settings.target_links * settings.sale_share)
        return {"venta": sales, "alquiler": settings.target_links - sales}
    return {operation: settings.target_links for operation in settings.operations}


def stratified_sample(frame: pd.DataFrame, limit: int) -> pd.DataFrame:
    if len(frame) <= limit:
        return frame.copy()
    group_columns = ["Tipo_Propiedad_Busqueda", "Barrio_Busqueda"]
    groups = [
        group.sort_values("Item_ID").reset_index(drop=True)
        for _, group in frame.groupby(group_columns, sort=True, dropna=False)
    ]
    selected_rows: list[pd.Series] = []
    level = 0
    while len(selected_rows) < limit:
        added = False
        for group in groups:
            if level < len(group):
                selected_rows.append(group.iloc[level])
                added = True
                if len(selected_rows) == limit:
                    break
        if not added:
            break
        level += 1
    return pd.DataFrame(selected_rows).reindex(columns=frame.columns)


def operation_sample(frame: pd.DataFrame, limit: int, sale_share: float) -> pd.DataFrame:
    if not limit or len(frame) <= limit:
        return frame.head(limit) if limit else frame
    if not all((frame["Tipo_Operacion"] == name).any() for name in ("Venta", "Alquiler")):
        return frame.head(limit)
    sale_count = round(limit * sale_share)
    selected = pd.concat([
        stratified_sample(frame[frame["Tipo_Operacion"] == "Venta"], sale_count),
        stratified_sample(frame[frame["Tipo_Operacion"] == "Alquiler"], limit - sale_count),
    ])
    if len(selected) < limit:
        selected = pd.concat([selected, frame.drop(index=selected.index).head(limit - len(selected))])
    return selected.reset_index(drop=True)


def output_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.reindex(columns=COLUMNS)
    for column in COLUMNS:
        if column in BINARY_COLUMNS:
            frame[column] = frame[column].replace(
                {"N/A": "", "NaN": "", "nan": "", "<NA>": ""}
            ).fillna("")
        else:
            frame[column] = frame[column].replace({"": "N/A"}).fillna("N/A")
    return frame


def get_complete_detail_soup(
    session: requests.Session, url: str, attempts: int = 3,
) -> BeautifulSoup:
    last_problem = "respuesta incompleta"
    for attempt in range(1, attempts + 1):
        soup = get_soup(session, url)
        state = rendering_state(soup)
        attributes = all_attributes(soup, state)
        title = first_text(soup, ["h1.ui-pdp-title", "h1"])
        price = first_text(soup, [".ui-pdp-price__second-line", ".ui-pdp-price"])
        if title != "N/A" and price != "N/A" and len(attributes) >= 3:
            return soup
        last_problem = (
            f"intento {attempt}: titulo={title != 'N/A'}, precio={price != 'N/A'}, "
            f"atributos={len(attributes)}"
        )
        if attempt < attempts:
            time.sleep(1.0 * attempt)
    raise RuntimeError(f"Ficha incompleta después de {attempts} intentos ({last_problem})")


def collect_links(session: requests.Session, settings: Settings) -> pd.DataFrame:
    existing = read_links()
    records = {row["Item_ID"]: row.to_dict() for _, row in existing.iterrows()}
    targets = operation_targets(settings)

    for operation in settings.operations:
        repeated_by_query: dict[tuple[str, str], set[tuple[str, ...]]] = {}
        for page_number in range(1, settings.max_pages_per_query + 1):
            for barrio in settings.barrios:
                for property_path in settings.property_paths:
                    operation_count = sum(normalized(x.get("Tipo_Operacion")) == operation for x in records.values())
                    if operation_count >= targets[operation]:
                        break
                    query_key = (property_path, barrio)
                    repeated_signatures = repeated_by_query.setdefault(query_key, set())
                    url = search_url(property_path, operation, barrio, page_number)
                    print(f"[Etapa 1] {operation.title()} | {property_path} | {barrio} | página {page_number}")
                    try:
                        soup = get_soup(session, url)
                    except Exception as exc:
                        append_error(url, f"Resultados: {exc!r}")
                        break
                    parsed = []
                    for card in soup.select("li.ui-search-layout__item"):
                        item = parse_card(card, operation, property_path, barrio, url)
                        if item:
                            parsed.append(item)
                    signature = tuple(sorted(item["Item_ID"] for item in parsed))
                    if not signature or signature in repeated_signatures:
                        continue
                    repeated_signatures.add(signature)
                    if settings.max_links_per_query:
                        parsed = parsed[:settings.max_links_per_query]
                    new_count = 0
                    for item in parsed:
                        if item["Item_ID"] not in records:
                            new_count += 1
                        records[item["Item_ID"]] = item
                    save_links(records)
                    operation_count = sum(normalized(x.get("Tipo_Operacion")) == operation for x in records.values())
                    print(f"  válidas={len(parsed)} nuevas={new_count} {operation}={operation_count}/{targets[operation]}")
                    time.sleep(settings.delay + random.uniform(0, 0.4))
                if sum(normalized(x.get("Tipo_Operacion")) == operation for x in records.values()) >= targets[operation]:
                    break
            if sum(normalized(x.get("Tipo_Operacion")) == operation for x in records.values()) >= targets[operation]:
                break
    return read_links()


def scrape_details(session: requests.Session, links: pd.DataFrame, settings: Settings) -> None:
    done: set[str] = set()
    if DATA_FILE.exists() and not settings.reprocess_all:
        previous = pd.read_csv(DATA_FILE, dtype=str, keep_default_na=False)
        done = set(previous.get("Item_ID", []))
    pending = links[~links["Item_ID"].isin(done)].copy()
    if settings.max_details:
        pending = operation_sample(pending, settings.max_details, settings.sale_share)
    print(f"Publicaciones pendientes: {len(pending)}")

    for position, (_, row) in enumerate(pending.iterrows(), start=1):
        url = row["Link"]
        print(f"[Etapa 2] {position}/{len(pending)} {row['Tipo_Operacion']}: {row['Item_ID']}")
        try:
            soup = get_complete_detail_soup(session, url)
            record = detail_record(soup, row.to_dict())
            if record is None:
                append_error(url, "Descartado: no es CABA o la operación no es válida")
            else:
                output_frame(pd.DataFrame([record])).to_csv(
                    DATA_FILE, mode="a", header=not DATA_FILE.exists(),
                    index=False, encoding="utf-8-sig",
                )
                done.add(row["Item_ID"])
        except Exception as exc:
            append_error(url, f"Detalle: {exc!r}")
        time.sleep(settings.delay + random.uniform(0, 0.4))

    if DATA_FILE.exists():
        final = pd.read_csv(DATA_FILE, dtype=str, keep_default_na=False)
        final = final.drop_duplicates("Item_ID", keep="last")
        final = output_frame(final)
        final.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")
        print(f"Dataset final: {DATA_FILE} ({len(final)} filas únicas)")


def run(settings: Settings) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    session = build_session()
    if settings.only_details:
        links = read_links()
        print(f"Reutilizando {len(links)} links guardados.")
    else:
        links = collect_links(session, settings)
    print(f"Links únicos disponibles: {len(links)}")
    if not settings.only_links and not links.empty:
        scrape_details(session, links, settings)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mercado Libre Inmuebles: Venta y Alquiler clasificado en CABA")
    parser.add_argument("--operaciones", nargs="+", choices=["venta", "alquiler"], default=["venta", "alquiler"])
    parser.add_argument("--tipos", nargs="+", choices=list(PROPERTY_PATHS), default=["departamentos"])
    parser.add_argument("--barrios", nargs="+", default=BARRIOS)
    parser.add_argument("--max-pages-per-query", type=int, default=42)
    parser.add_argument("--target-links", type=int, default=20_000)
    parser.add_argument("--proporcion-venta", type=float, default=0.70)
    parser.add_argument("--max-details", type=int, default=0, help="0 procesa todos")
    parser.add_argument(
        "--max-links-por-consulta", type=int, default=0,
        help="0 conserva todos; usar un límite pequeño produce muestras más diversas",
    )
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--solo-links", action="store_true")
    parser.add_argument("--solo-detalles", action="store_true")
    parser.add_argument(
        "--reprocesar", action="store_true",
        help="vuelve a leer detalles aunque el Item_ID ya exista en el CSV",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(Settings(
        operations=args.operaciones, property_paths=args.tipos, barrios=args.barrios,
        max_pages_per_query=args.max_pages_per_query, target_links=args.target_links,
        sale_share=args.proporcion_venta, max_details=args.max_details,
        max_links_per_query=args.max_links_por_consulta,
        delay=args.delay, only_links=args.solo_links, only_details=args.solo_detalles,
        reprocess_all=args.reprocesar,
    ))
