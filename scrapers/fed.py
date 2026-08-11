"""Effective Federal Funds Rate (EFFR) de la API FRED, vía httpx asíncrono."""

from datetime import date

import httpx

from scrapers.utils import ScraperError, retry_http

API_URL = "https://api.stlouisfed.org/fred/series/observations"
SERIE_EFFR = "EFFR"

TIMEOUT = httpx.Timeout(20.0, connect=10.0)


@retry_http
async def _get_observaciones(client: httpx.AsyncClient, api_key: str) -> list[dict]:
    response = await client.get(
        API_URL,
        params={
            "series_id": SERIE_EFFR,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 10,  # margen por si los últimos días vienen sin dato
        },
    )
    response.raise_for_status()
    return response.json()["observations"]


async def run(client: httpx.AsyncClient | None = None, api_key: str | None = None) -> dict:
    """Última EFFR publicada, con su fecha. Claves: fed_tea, fed_tea_fecha."""
    if api_key is None:
        # Import diferido: así importar el paquete scrapers no exige un .env válido.
        from config import settings

        api_key = settings.fed_api_key.get_secret_value()

    try:
        if client is not None:
            observaciones = await _get_observaciones(client, api_key)
        else:
            async with httpx.AsyncClient(timeout=TIMEOUT) as own_client:
                observaciones = await _get_observaciones(own_client, api_key)

        # FRED marca los días sin dato (feriados) con "." en vez de un número.
        for obs in observaciones:
            if obs["value"] != ".":
                return {
                    "fed_tea": float(obs["value"]),
                    "fed_tea_fecha": date.fromisoformat(obs["date"]),
                }
        raise ValueError("las últimas 10 observaciones vinieron todas vacías")

    except Exception as exc:
        raise ScraperError("FED", "leer EFFR", exc) from exc
