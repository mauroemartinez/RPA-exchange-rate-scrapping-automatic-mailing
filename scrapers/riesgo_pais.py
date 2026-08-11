"""Riesgo país desde la API de ArgentinaDatos, vía httpx asíncrono.

Reemplaza al scraping con Playwright de ambito.com/contenidos/riesgo-pais-historico.html.
La fuente de fondo sigue siendo Ámbito — ArgentinaDatos la expone como JSON — pero
sin levantar un Chromium ni depender de que no cambien las clases CSS de la tabla.

Además devuelve la FECHA a la que corresponde el valor. El scraper viejo no la
miraba: leía la primera fila de la tabla histórica (el último cierre publicado) y
la guardaba contra la fecha de hoy, lo que corrió toda la serie un día hábil.
"""

from datetime import date

import httpx

from scrapers.utils import ScraperError, retry_http

API_BASE = "https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais"
API_ULTIMO = f"{API_BASE}/ultimo"

# connect corto (si el DNS o el TCP no responden en 10s, no va a mejorar),
# read más largo: el endpoint del histórico devuelve ~7700 registros.
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


@retry_http
async def _get_json(client: httpx.AsyncClient, url: str):
    """Un GET con reintentos. Separado en su propia función para que el retry
    envuelva solo la llamada de red y no el parseo posterior."""
    response = await client.get(url)
    response.raise_for_status()
    return response.json()


def _parse(registro: dict) -> tuple[date, float]:
    return date.fromisoformat(registro["fecha"]), float(registro["valor"])


async def run(client: httpx.AsyncClient | None = None) -> dict:
    """Devuelve el último riesgo país publicado, con su fecha real.

    Claves: riesgo_pais (float) y riesgo_pais_fecha (date).

    Si se le pasa un AsyncClient lo reutiliza — así varias llamadas comparten el
    pool de conexiones. Si no, abre y cierra uno propio.
    """
    try:
        if client is not None:
            payload = await _get_json(client, API_ULTIMO)
        else:
            async with httpx.AsyncClient(timeout=TIMEOUT) as own_client:
                payload = await _get_json(own_client, API_ULTIMO)

        fecha, valor = _parse(payload)
        if valor <= 0:
            raise ValueError(f"valor no positivo: {valor}")
        return {"riesgo_pais": valor, "riesgo_pais_fecha": fecha}

    except Exception as exc:
        raise ScraperError("ArgentinaDatos", "leer último riesgo país", exc) from exc


async def fetch_historico(client: httpx.AsyncClient | None = None) -> list[tuple[date, float]]:
    """Serie completa (fecha, valor) ordenada ascendente. Para backfill."""
    try:
        if client is not None:
            payload = await _get_json(client, API_BASE)
        else:
            async with httpx.AsyncClient(timeout=TIMEOUT) as own_client:
                payload = await _get_json(own_client, API_BASE)

        serie = [_parse(r) for r in payload]
        serie.sort(key=lambda par: par[0])
        return serie

    except Exception as exc:
        raise ScraperError("ArgentinaDatos", "leer histórico de riesgo país", exc) from exc
