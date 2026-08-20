"""Ejecución completa, incremental y reanudable del scraper v3.

Este archivo NO modifica la lógica de extracción de MercadoLibre_scraper.py:
reutiliza sus buscadores, parsers y sus 186 columnas. Solamente agrega una
orquestación segura para ejecuciones largas.

Uso normal:
    python mercadolibre_scraping_completo.py

Verificación sin iniciar el scraping:
    python mercadolibre_scraping_completo.py --verificar
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

import MercadoLibre_scraper as v3


OUTPUT_DIR = Path("output_mercadolibre")
DATA_FILE = OUTPUT_DIR / "mercadolibre_caba_scraping_completo.csv"
LINKS_FILE = OUTPUT_DIR / "mercadolibre_links_completo.csv"
FAILED_FILE = OUTPUT_DIR / "urls_fallidas.csv"
LOG_FILE = OUTPUT_DIR / "scraping.log"
CHECKPOINT_FILE = OUTPUT_DIR / "checkpoint_scraping_completo.json"
LOCK_FILE = OUTPUT_DIR / "scraping_completo.lock"

SAVE_EVERY = 50
NO_NEW_PAGES_LIMIT = 3
MAX_CONSECUTIVE_ERRORS = 20
DEFAULT_DELAY = 1.8


class SafeStop(RuntimeError):
    """Finalización controlada que obliga a guardar los avances."""


class ProtectionDetected(SafeStop):
    """Mercado Libre parece haber mostrado un bloqueo o captcha."""


@dataclass
class Stats:
    initial_saved: int = 0
    new_saved: int = 0
    duplicates: int = 0
    errors: int = 0
    failed_urls: int = 0
    consecutive_errors: int = 0
    current_page: int = 0
    last_save: str = "Todavía no hubo guardado"

    @property
    def total_saved(self) -> int:
        return self.initial_saved + self.new_saved


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def setup_logger() -> logging.Logger:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("scraping_completo")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


LOGGER = setup_logger()


def log_event(stats: Stats, message: str, item_id: str = "N/A") -> None:
    LOGGER.info(
        "Item_ID=%s | pagina=%s | extraidas=%s | nuevas=%s | "
        "duplicadas=%s | errores=%s | %s",
        item_id,
        stats.current_page or "N/A",
        stats.total_saved,
        stats.new_saved,
        stats.duplicates,
        stats.errors,
        message,
    )


def atomic_csv(frame: pd.DataFrame, destination: Path, columns: list[str]) -> None:
    """Escribe un CSV completo y lo reemplaza atómicamente."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    frame.reindex(columns=columns).to_csv(
        temporary, index=False, encoding="utf-8-sig"
    )
    os.replace(temporary, destination)


def atomic_json(payload: dict[str, Any], destination: Path) -> None:
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, destination)


def load_checkpoint() -> dict[str, Any]:
    defaults = {
        "phase": "links",
        "query_index": 0,
        "next_page": 1,
        "no_new_pages": 0,
        "updated_at": now_iso(),
    }
    if not CHECKPOINT_FILE.exists():
        return defaults
    try:
        with CHECKPOINT_FILE.open(encoding="utf-8") as stream:
            saved = json.load(stream)
        defaults.update(saved)
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeError(f"Checkpoint ilegible: {CHECKPOINT_FILE}: {exc}") from exc
    return defaults


def save_checkpoint(checkpoint: dict[str, Any], stats: Stats) -> None:
    checkpoint["updated_at"] = now_iso()
    checkpoint["total_saved"] = stats.total_saved
    checkpoint["new_saved_current_run"] = stats.new_saved
    checkpoint["errors_current_run"] = stats.errors
    atomic_json(checkpoint, CHECKPOINT_FILE)
    stats.last_save = datetime.now().astimezone().strftime("%H:%M:%S")


def read_csv_checked(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=columns)
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [column for column in columns if column not in frame.columns]
    extra = [column for column in frame.columns if column not in columns]
    if missing or extra:
        raise RuntimeError(
            f"El esquema de {path} no coincide con v3. "
            f"Faltan={missing}; sobran={extra}"
        )
    return frame.reindex(columns=columns)


def deduplicate(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Deduplica primero por Item_ID y luego por Link, conservando lo último."""
    if frame.empty:
        return frame, 0
    before = len(frame)
    valid_ids = ~frame["Item_ID"].isin(["", "N/A"])
    with_id = frame[valid_ids].drop_duplicates("Item_ID", keep="last")
    without_id = frame[~valid_ids]
    frame = pd.concat([with_id, without_id], ignore_index=True)
    valid_links = ~frame["Link"].isin(["", "N/A"])
    with_link = frame[valid_links].drop_duplicates("Link", keep="last")
    without_link = frame[~valid_links]
    frame = pd.concat([with_link, without_link], ignore_index=True)
    return frame.reindex(columns=frame.columns), before - len(frame)


def load_and_normalize_data() -> tuple[pd.DataFrame, int]:
    frame = read_csv_checked(DATA_FILE, v3.COLUMNS)
    frame, removed = deduplicate(frame)
    if DATA_FILE.exists() and removed:
        atomic_csv(v3.output_frame(frame), DATA_FILE, v3.COLUMNS)
    return frame, removed


def load_links() -> tuple[pd.DataFrame, int]:
    frame = read_csv_checked(LINKS_FILE, v3.LINK_COLUMNS)
    frame, removed = deduplicate(frame)
    if LINKS_FILE.exists() and removed:
        atomic_csv(frame, LINKS_FILE, v3.LINK_COLUMNS)
    return frame, removed


def append_failed(
    url: str,
    reason: str,
    phase: str,
    stats: Stats,
    item_id: str = "N/A",
) -> None:
    row = {
        "Hora": now_iso(),
        "Fase": phase,
        "Pagina": stats.current_page or "N/A",
        "Item_ID": item_id,
        "Link": url,
        "Error": v3.clean(reason),
    }
    header = not FAILED_FILE.exists() or FAILED_FILE.stat().st_size == 0
    with FAILED_FILE.open("a", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        if header:
            writer.writeheader()
        writer.writerow(row)
        stream.flush()
        os.fsync(stream.fileno())
    stats.errors += 1
    stats.failed_urls += 1
    stats.consecutive_errors += 1
    log_event(stats, f"ERROR fase={phase}: {reason}", item_id)


def ensure_error_limit(stats: Stats) -> None:
    if stats.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
        raise SafeStop(
            f"se alcanzaron {MAX_CONSECUTIVE_ERRORS} errores consecutivos"
        )


def http_status(error: BaseException) -> int | None:
    """Obtiene el código HTTP de una excepción de requests, cuando existe."""
    response = getattr(error, "response", None)
    return getattr(response, "status_code", None)


BLOCK_TEXT_PATTERNS = (
    "captcha",
    "verify you are human",
    "verifica que eres humano",
    "verificá que sos humano",
    "unusual traffic",
    "actividad inusual",
    "acceso denegado",
    "access denied",
    "no soy un robot",
    "i'm not a robot",
)

BLOCK_HTML_PATTERNS = (
    "px-captcha",
    "cf-chl-",
    "challenge-platform",
    "/recaptcha/api2/anchor",
    "class=\"g-recaptcha\"",
)


def protection_marker(soup: Any) -> str | None:
    """Detecta desafíos visibles sin confundir una site key inactiva con captcha."""
    text = soup.get_text(" ", strip=True).lower()
    html = str(soup).lower()
    detected = next((pattern for pattern in BLOCK_TEXT_PATTERNS if pattern in text), None)
    if detected is None:
        detected = next(
            (pattern for pattern in BLOCK_HTML_PATTERNS if pattern in html), None
        )
    return detected


def ensure_not_blocked(soup: Any, url: str) -> None:
    detected = protection_marker(soup)
    if detected:
        raise ProtectionDetected(
            f"posible captcha o bloqueo detectado ({detected}) en {url}"
        )


def get_complete_detail_soup_checked(
    session: Any, url: str, attempts: int = 3
) -> Any:
    """Aplica la validación v3 y detecta una protección antes de reintentar."""
    last_problem = "respuesta incompleta"
    for attempt in range(1, attempts + 1):
        soup = v3.get_soup(session, url)
        ensure_not_blocked(soup, url)
        state = v3.rendering_state(soup)
        attributes = v3.all_attributes(soup, state)
        title = v3.first_text(soup, ["h1.ui-pdp-title", "h1"])
        price = v3.first_text(
            soup, [".ui-pdp-price__second-line", ".ui-pdp-price"]
        )
        if title != "N/A" and price != "N/A" and len(attributes) >= 3:
            return soup
        last_problem = (
            f"intento {attempt}: titulo={title != 'N/A'}, "
            f"precio={price != 'N/A'}, atributos={len(attributes)}"
        )
        if attempt < attempts:
            time.sleep(1.0 * attempt)
    raise RuntimeError(
        f"Ficha incompleta después de {attempts} intentos ({last_problem})"
    )


def sleep_reasonably(delay: float) -> None:
    time.sleep(delay + random.uniform(0.2, 0.8))


def progress(stats: Stats, force: bool = False) -> None:
    if not force and stats.new_saved % 25 != 0:
        return
    print(
        "\n"
        f"Extraídas: {stats.total_saved}\n"
        f"Nuevas: {stats.new_saved}\n"
        f"Duplicadas: {stats.duplicates}\n"
        f"Errores: {stats.errors}\n"
        f"Página actual: {stats.current_page or 'N/A'}\n"
        f"Último guardado: {stats.last_save}\n",
        flush=True,
    )


def query_plan() -> list[tuple[str, str, str]]:
    return [
        (operation, property_path, barrio)
        for operation in ("venta", "alquiler")
        for property_path in v3.PROPERTY_PATHS
        for barrio in v3.BARRIOS
    ]


def records_from_links(frame: pd.DataFrame) -> tuple[dict[str, dict], dict[str, str]]:
    records: dict[str, dict] = {}
    links: dict[str, str] = {}
    for _, row in frame.iterrows():
        item_id = str(row["Item_ID"])
        link = v3.canonical_url(str(row["Link"]))
        if item_id not in ("", "N/A") and link not in ("", "N/A"):
            records[item_id] = row.to_dict()
            links[link] = item_id
    return records, links


def discover_links(
    session: Any,
    checkpoint: dict[str, Any],
    stats: Stats,
    delay: float,
) -> pd.DataFrame:
    existing, removed = load_links()
    stats.duplicates += removed
    records, links_by_url = records_from_links(existing)
    plan = query_plan()
    start_index = int(checkpoint.get("query_index", 0))

    print(
        f"Etapa 1: {len(records)} links recuperados del checkpoint; "
        f"consulta {start_index + 1}/{len(plan)}.",
        flush=True,
    )

    for query_index in range(start_index, len(plan)):
        operation, property_path, barrio = plan[query_index]
        page = int(checkpoint.get("next_page", 1)) if query_index == start_index else 1
        no_new_pages = (
            int(checkpoint.get("no_new_pages", 0)) if query_index == start_index else 0
        )
        seen_signatures: set[tuple[str, ...]] = set()

        while no_new_pages < NO_NEW_PAGES_LIMIT:
            stats.current_page = page
            url = v3.search_url(property_path, operation, barrio, page)
            print(
                f"[Links] {operation.title()} | {property_path} | {barrio} "
                f"| página {page} | únicos={len(records)}",
                flush=True,
            )
            try:
                soup = v3.get_soup(session, url)
                ensure_not_blocked(soup, url)
                parsed = []
                for card in soup.select("li.ui-search-layout__item"):
                    item = v3.parse_card(card, operation, property_path, barrio, url)
                    if item:
                        parsed.append(item)

                signature = tuple(sorted(item["Item_ID"] for item in parsed))
                if signature and signature not in seen_signatures:
                    seen_signatures.add(signature)
                else:
                    parsed = []

                new_on_page = 0
                duplicate_on_page = 0
                for item in parsed:
                    item_id = item["Item_ID"]
                    link = v3.canonical_url(item["Link"])
                    if item_id in records or link in links_by_url:
                        duplicate_on_page += 1
                        continue
                    item["Link"] = link
                    records[item_id] = item
                    links_by_url[link] = item_id
                    new_on_page += 1

                stats.duplicates += duplicate_on_page
                no_new_pages = 0 if new_on_page else no_new_pages + 1
                stats.consecutive_errors = 0
                frame = pd.DataFrame(records.values()).reindex(
                    columns=v3.LINK_COLUMNS, fill_value="N/A"
                )
                atomic_csv(frame, LINKS_FILE, v3.LINK_COLUMNS)
                checkpoint.update(
                    phase="links",
                    query_index=query_index,
                    next_page=page + 1,
                    no_new_pages=no_new_pages,
                )
                save_checkpoint(checkpoint, stats)
                log_event(
                    stats,
                    f"links consulta={operation}/{property_path}/{barrio} "
                    f"nuevos_pagina={new_on_page} sin_nuevos={no_new_pages}",
                )
            except SafeStop:
                raise
            except Exception as exc:
                status = http_status(exc)
                if status in {404, 410}:
                    # Mercado Libre usa estas respuestas cuando el offset ya
                    # quedó fuera de la paginación disponible. No es un fallo
                    # de publicación ni debe consumir los 20 reintentos.
                    stats.consecutive_errors = 0
                    log_event(
                        stats,
                        f"fin de paginación HTTP {status} "
                        f"consulta={operation}/{property_path}/{barrio}",
                    )
                    checkpoint.update(
                        phase="links",
                        query_index=query_index + 1,
                        next_page=1,
                        no_new_pages=0,
                    )
                    save_checkpoint(checkpoint, stats)
                    break
                append_failed(url, repr(exc), "links", stats)
                ensure_error_limit(stats)
                checkpoint.update(
                    phase="links",
                    query_index=query_index,
                    next_page=page,
                    no_new_pages=no_new_pages,
                )
                save_checkpoint(checkpoint, stats)
                sleep_reasonably(delay)
                continue

            page += 1
            sleep_reasonably(delay)

        checkpoint.update(
            phase="links",
            query_index=query_index + 1,
            next_page=1,
            no_new_pages=0,
        )
        save_checkpoint(checkpoint, stats)

    checkpoint.update(
        phase="details", query_index=len(plan), next_page=1, no_new_pages=0
    )
    save_checkpoint(checkpoint, stats)
    return read_csv_checked(LINKS_FILE, v3.LINK_COLUMNS)


def append_detail_batch(batch: list[dict], stats: Stats) -> None:
    if not batch:
        return
    frame = v3.output_frame(pd.DataFrame(batch))
    header = not DATA_FILE.exists() or DATA_FILE.stat().st_size == 0
    frame.to_csv(
        DATA_FILE,
        mode="a",
        header=header,
        index=False,
        encoding="utf-8-sig",
    )
    stats.new_saved += len(frame)
    stats.last_save = datetime.now().astimezone().strftime("%H:%M:%S")
    batch.clear()


def compact_data(stats: Stats) -> None:
    if not DATA_FILE.exists():
        return
    frame = read_csv_checked(DATA_FILE, v3.COLUMNS)
    frame, removed = deduplicate(frame)
    stats.duplicates += removed
    atomic_csv(v3.output_frame(frame), DATA_FILE, v3.COLUMNS)


def scrape_details(
    session: Any,
    links: pd.DataFrame,
    checkpoint: dict[str, Any],
    stats: Stats,
    delay: float,
) -> None:
    existing, removed = load_and_normalize_data()
    stats.duplicates += removed
    stats.initial_saved = len(existing)
    existing_ids = set(existing["Item_ID"])
    existing_links = set(existing["Link"].map(v3.canonical_url))

    duplicate_mask = links["Item_ID"].isin(existing_ids) | links["Link"].map(
        v3.canonical_url
    ).isin(existing_links)
    stats.duplicates += int(duplicate_mask.sum())
    pending = links[~duplicate_mask].copy()
    pending["_operation_order"] = pending["Tipo_Operacion"].map(
        {"Venta": 0, "Alquiler": 1}
    ).fillna(2)
    pending = pending.sort_values("_operation_order", kind="stable").drop(
        columns="_operation_order"
    ).reset_index(drop=True)
    pending_by_operation = pending["Tipo_Operacion"].value_counts().to_dict()
    print(
        f"Etapa 2 sin límite: {len(pending)} fichas nuevas pendientes; "
        f"{stats.initial_saved} ya guardadas; "
        f"Venta={pending_by_operation.get('Venta', 0)}, "
        f"Alquiler={pending_by_operation.get('Alquiler', 0)}.",
        flush=True,
    )

    batch: list[dict] = []
    try:
        for position, row in pending.iterrows():
            item_id = str(row["Item_ID"])
            url = v3.canonical_url(str(row["Link"]))
            print(
                f"[Detalles] {position + 1}/{len(pending)} "
                f"{row['Tipo_Operacion']}: {item_id}",
                flush=True,
            )
            try:
                soup = get_complete_detail_soup_checked(session, url)
                record = v3.detail_record(soup, row.to_dict())
                if record is None:
                    append_failed(
                        url,
                        "Descartado: no es CABA o la operación no es válida",
                        "detalles",
                        stats,
                        item_id,
                    )
                    ensure_error_limit(stats)
                else:
                    record_id = str(record.get("Item_ID", item_id))
                    record_link = v3.canonical_url(str(record.get("Link", url)))
                    if record_id in existing_ids or record_link in existing_links:
                        stats.duplicates += 1
                        stats.consecutive_errors = 0
                    else:
                        batch.append(record)
                        existing_ids.add(record_id)
                        existing_links.add(record_link)
                        stats.consecutive_errors = 0
                        if len(batch) >= SAVE_EVERY:
                            append_detail_batch(batch, stats)
                            save_checkpoint(checkpoint, stats)
                            log_event(stats, "guardado incremental", item_id)
                            progress(stats, force=True)
            except SafeStop:
                raise
            except Exception as exc:
                append_failed(url, repr(exc), "detalles", stats, item_id)
                ensure_error_limit(stats)

            sleep_reasonably(delay)
    finally:
        append_detail_batch(batch, stats)
        compact_data(stats)
        save_checkpoint(checkpoint, stats)
        progress(stats, force=True)


def acquire_lock() -> None:
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
            os.kill(old_pid, 0)
        except (ValueError, OSError):
            LOCK_FILE.unlink(missing_ok=True)
        else:
            raise RuntimeError(
                f"Ya hay una ejecución activa (PID {old_pid}). "
                f"Si no existe, eliminá {LOCK_FILE}."
            )
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")


def release_lock() -> None:
    try:
        if LOCK_FILE.exists() and LOCK_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
            LOCK_FILE.unlink()
    except OSError:
        pass


def install_signal_handlers() -> None:
    def stop_handler(signum: int, _frame: Any) -> None:
        raise SafeStop(f"detención manual recibida (señal {signum})")

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)


def verify(network: bool = True) -> None:
    """Comprueba esquema, rutas, deduplicación y conectividad sin scrapear."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    assert len(v3.COLUMNS) == 186, "El esquema v3 ya no tiene 186 columnas"
    assert len(v3.COLUMNS) == len(set(v3.COLUMNS)), "Hay columnas v3 duplicadas"
    assert "Item_ID" in v3.COLUMNS and "Link" in v3.COLUMNS
    assert DATA_FILE.name not in {
        v3.DATA_FILE.name,
        "mercadolibre_caba_venta_alquiler.csv",
        "mercadolibre_caba_venta_alquiler_v2.csv",
    }

    sample = pd.DataFrame(
        [
            {"Item_ID": "MLA1", "Link": "https://x/MLA1"},
            {"Item_ID": "MLA1", "Link": "https://x/MLA1-duplicado"},
            {"Item_ID": "MLA2", "Link": "https://x/MLA1-duplicado"},
        ]
    )
    unique, removed = deduplicate(sample)
    assert len(unique) == 1 and removed == 2

    class FakeResponse:
        status_code = 404

    class FakeHTTPError(RuntimeError):
        response = FakeResponse()

    assert http_status(FakeHTTPError()) == 404

    class FakeSoup:
        def __init__(self, visible_text: str, html: str):
            self.visible_text = visible_text
            self.html = html

        def get_text(self, *_args: Any, **_kwargs: Any) -> str:
            return self.visible_text

        def __str__(self) -> str:
            return self.html

    normal_with_site_key = FakeSoup(
        "Departamento en venta",
        '<script>{"recaptchaSiteKey":"clave-inactiva"}</script>',
    )
    visible_challenge = FakeSoup("Completa el captcha", "<html></html>")
    assert protection_marker(normal_with_site_key) is None
    assert protection_marker(visible_challenge) == "captcha"

    if DATA_FILE.exists():
        read_csv_checked(DATA_FILE, v3.COLUMNS)
    if LINKS_FILE.exists():
        read_csv_checked(LINKS_FILE, v3.LINK_COLUMNS)
    load_checkpoint()

    if network:
        session = v3.build_session()
        test_url = v3.search_url("departamentos", "venta", "palermo", 1)
        soup = v3.get_soup(session, test_url)
        ensure_not_blocked(soup, test_url)
        cards = soup.select("li.ui-search-layout__item")
        parsed = [
            v3.parse_card(card, "venta", "departamentos", "palermo", test_url)
            for card in cards
        ]
        if not any(parsed):
            raise RuntimeError(
                "Mercado Libre respondió, pero no se detectaron tarjetas válidas; "
                "no es seguro iniciar el scraping."
            )

    print(
        "✓ Verificación superada: 186 columnas v3 intactas, archivos separados, "
        "checkpoint, deduplicación y guardado incremental disponibles"
        + (", conexión y tarjetas válidas." if network else "."),
        flush=True,
    )


def run(delay: float) -> None:
    start = time.monotonic()
    stats = Stats()
    checkpoint: dict[str, Any] = {}
    reason = "todas las publicaciones disponibles fueron recorridas"
    acquire_lock()
    install_signal_handlers()
    try:
        verify(network=True)
        saved_at_start, removed_at_start = load_and_normalize_data()
        stats.initial_saved = len(saved_at_start)
        stats.duplicates += removed_at_start
        checkpoint = load_checkpoint()
        session = v3.build_session()
        if checkpoint.get("phase") == "links":
            links = discover_links(session, checkpoint, stats, delay)
        else:
            links, removed = load_links()
            stats.duplicates += removed
            print(f"Reanudando etapa de detalles con {len(links)} links.", flush=True)

        checkpoint.pop("detail_target", None)
        checkpoint["detail_mode"] = "all"
        save_checkpoint(checkpoint, stats)
        scrape_details(session, links, checkpoint, stats, delay)
        reason = "todos los enlaces disponibles fueron recorridos"
        checkpoint["phase"] = "completed"
        save_checkpoint(checkpoint, stats)
    except ProtectionDetected as exc:
        reason = str(exc)
        if checkpoint:
            save_checkpoint(checkpoint, stats)
        log_event(stats, f"FINALIZACIÓN SEGURA: {reason}")
    except SafeStop as exc:
        reason = str(exc)
        if checkpoint:
            save_checkpoint(checkpoint, stats)
        log_event(stats, f"FINALIZACIÓN SEGURA: {reason}")
    except Exception as exc:
        reason = f"error general no recuperable: {exc!r}"
        if checkpoint:
            save_checkpoint(checkpoint, stats)
        log_event(stats, f"FINALIZACIÓN SEGURA: {reason}")
        LOGGER.exception("Excepción general")
    finally:
        release_lock()
        elapsed = time.monotonic() - start
        hours, remainder = divmod(int(elapsed), 3600)
        minutes, seconds = divmod(remainder, 60)
        print(
            "\nRESUMEN FINAL\n"
            f"Publicaciones totales guardadas: {stats.total_saved}\n"
            f"Publicaciones nuevas: {stats.new_saved}\n"
            f"Duplicados encontrados: {stats.duplicates}\n"
            f"Errores: {stats.errors}\n"
            f"URLs fallidas: {stats.failed_urls}\n"
            f"Tiempo total: {hours:02d}:{minutes:02d}:{seconds:02d}\n"
            f"Motivo de finalización: {reason}\n",
            flush=True,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ejecución completa y reanudable del scraper v3"
    )
    parser.add_argument(
        "--verificar",
        action="store_true",
        help="verifica todo sin iniciar el scraping",
    )
    parser.add_argument(
        "--sin-red",
        action="store_true",
        help="con --verificar, omite la prueba de conectividad",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"pausa base entre solicitudes (predeterminado: {DEFAULT_DELAY}s)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    if arguments.delay < 1.0:
        sys.exit("Por seguridad, --delay no puede ser menor que 1 segundo.")
    if arguments.verificar:
        verify(network=not arguments.sin_red)
    else:
        run(arguments.delay)
