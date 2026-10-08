"""Feriados nacionales de Argentina, desde la API de ArgentinaDatos.

Hoy la corrida se dispara a mano y nadie la lanza un feriado. Con un programador
automático de lunes a viernes no sería así: un feriado las fuentes repiten el
último dato y el mail saldría con una fila duplicada. El pipeline consulta este
calendario antes de empezar. Incluye los días puente, en los que tampoco opera
el mercado cambiario.
"""

from datetime import date

import httpx

from reporte.scrapers.utils import ScraperError, retry_http, run_async

API = "https://api.argentinadatos.com/v1/feriados"
TIMEOUT = httpx.Timeout(20.0, connect=10.0)


@retry_http
async def _get(client: httpx.AsyncClient, anio: int) -> list[dict]:
    response = await client.get(f"{API}/{anio}")
    response.raise_for_status()
    return response.json()


async def fetch(anio: int, client: httpx.AsyncClient | None = None) -> dict[date, str]:
    """{fecha: nombre} de los feriados del año (inamovibles, trasladables y puentes)."""
    try:
        if client is not None:
            datos = await _get(client, anio)
        else:
            async with httpx.AsyncClient(timeout=TIMEOUT) as propio:
                datos = await _get(propio, anio)
        return {date.fromisoformat(d["fecha"]): d["nombre"] for d in datos}
    except Exception as exc:
        raise ScraperError("ArgentinaDatos", f"leer feriados de {anio}", exc) from exc


def nombre_feriado(fecha: date) -> str | None:
    """El nombre del feriado si `fecha` lo es; None si es un día hábil."""
    return run_async(fetch(fecha.year)).get(fecha)
