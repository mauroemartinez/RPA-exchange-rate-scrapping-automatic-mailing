"""Variables monetarias del BCRA, vía httpx asíncrono.

Ojo con el orden: la API devuelve el detalle de más NUEVO a más VIEJO. El código
que estaba en el notebook tomaba .iloc[-1] sobre ese detalle sin invertirlo, o sea
el registro más viejo de la ventana de 1000 puntos, guardaba la BADLAR de junio
de 2022 como si fuera la de hoy. Acá las series se devuelven siempre ascendentes
y el último valor es, efectivamente, el último.
"""

import asyncio
from datetime import date

import httpx

from reporte.scrapers.utils import ScraperError, cliente_http, retry_http

API_BASE = "https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias"

VAR_TEA = 140       # BADLAR bancos privados, en porcentaje EFECTIVO anual
VAR_INFLACION = 27  # Inflación mensual, en porcentaje

# El BCRA tenía la cadena de certificados rota y el notebook usaba verify=False.
# Ya está arreglada, así que se valida TLS como corresponde.
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


@retry_http
async def _get_detalle(client: httpx.AsyncClient, id_variable: int) -> list[dict]:
    response = await client.get(f"{API_BASE}/{id_variable}")
    response.raise_for_status()
    return response.json()["results"][0]["detalle"]


async def fetch_serie(id_variable: int, client: httpx.AsyncClient) -> list[tuple[date, float]]:
    """Serie (fecha, valor) de una variable, ordenada ascendente."""
    detalle = await _get_detalle(client, id_variable)
    serie = [(date.fromisoformat(d["fecha"]), float(d["valor"])) for d in detalle]
    serie.sort(key=lambda par: par[0])
    return serie


async def run(client: httpx.AsyncClient | None = None) -> dict:
    """Último BADLAR efectivo anual y la serie de inflación mensual.

    Claves: bcra_tea (float), bcra_tea_fecha (date) e inflacion_mensual, que es
    la lista (fecha, valor) ascendente que el notebook usa para los acumulados.
    """
    try:
        async with cliente_http(client, TIMEOUT) as c:
            # Las dos variables en paralelo: son dos requests independientes
            tea, inflacion = await asyncio.gather(fetch_serie(VAR_TEA, c), fetch_serie(VAR_INFLACION, c))

        fecha, valor = tea[-1]
        if valor <= 0:
            raise ValueError(f"TEA no positiva: {valor}")
        return {"bcra_tea": valor, "bcra_tea_fecha": fecha, "inflacion_mensual": inflacion}

    except Exception as exc:
        raise ScraperError("BCRA", "leer variables monetarias", exc) from exc

