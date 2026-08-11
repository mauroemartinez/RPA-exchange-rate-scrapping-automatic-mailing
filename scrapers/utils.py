import asyncio
import sys
import threading

import httpx
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
)


class ScraperError(Exception):
    """Raised when a scraper cannot produce a value, with context on where it failed."""

    def __init__(self, site: str, step: str, cause: Exception):
        super().__init__(f"[{site}] fallo en '{step}': {cause}")
        self.site = site
        self.step = step
        self.cause = cause


def parse_money(text: str) -> float:
    """Convierte a float tanto formato es-AR ('$1.234,56', coma decimal) como
    formato en-US ('1234.5600', punto decimal) — BNA usa uno u otro según la tabla."""
    text = text.strip().lstrip("$")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    return float(text)


def retry_scrape(func):
    """Reintenta hasta 3 veces ante timeouts de Playwright, con espera fija corta."""
    return retry(
        retry=retry_if_exception_type(PlaywrightTimeoutError),
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        reraise=True,
    )(func)


def _es_error_http_transitorio(exc: BaseException) -> bool:
    """True para fallos de red y 5xx (vale reintentar); False para 4xx.

    Un 404 o un 401 no se arreglan reintentando — reintentar solo agrega latencia
    antes de un error inevitable. Un 503 o un timeout de red, en cambio, suelen
    resolverse solos en el segundo intento.
    """
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def retry_http(func):
    """Reintenta hasta 5 veces ante fallos de red o 5xx, con backoff exponencial.

    Backoff (1s, 2s, 4s, 8s = 15s en total) en vez de espera fija: si la API está
    momentáneamente caída, cinco golpes seguidos empeoran las cosas. Se eligieron
    5 intentos y no 3 porque se observó a ArgentinaDatos devolver 502 de forma
    intermitente; en un job que corre una vez por día, esperar 15s es gratis.
    """
    return retry(
        retry=retry_if_exception(_es_error_http_transitorio),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        reraise=True,
    )(func)


def run_playwright(coro):
    # Corre una corutina de Playwright en un hilo con su propio event loop nuevo.
    # El kernel de Jupyter ya corre su propio loop, así que un simple asyncio.run() falla ('loop ya corriendo').
    result: dict = {}

    def _runner():
        loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result["value"] = loop.run_until_complete(coro)
        except BaseException as exc:
            result["error"] = exc
        finally:
            loop.close()

    thread = threading.Thread(target=_runner)
    thread.start()
    thread.join()

    if "error" in result:
        raise result["error"]
    return result["value"]


# run_playwright() no tiene nada de específico de Playwright: corre cualquier
# corutina. Este alias es el nombre honesto, y el viejo queda por compatibilidad.
run_async = run_playwright
