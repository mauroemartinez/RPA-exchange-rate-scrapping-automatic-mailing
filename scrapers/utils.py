import asyncio
import sys
import threading

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed


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


def run_playwright(coro):
    """Corre una corutina de Playwright en un hilo con su propio event loop nuevo.

    El kernel de Jupyter ya corre su propio loop, así que un simple asyncio.run()
    falla ('loop ya corriendo'). En Windows además ese loop es Selector, que no
    soporta subprocesos — y Playwright lanza su driver como subproceso — por eso
    en Windows se fuerza un ProactorEventLoop en el hilo nuevo.
    """
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
