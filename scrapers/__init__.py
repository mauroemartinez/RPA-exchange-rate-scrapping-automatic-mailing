import asyncio

import httpx

from scrapers import ambito, bcra, bna, dolarhoy, fed, riesgo_pais
from scrapers.utils import run_async


async def _run_all():
    """Corre las tres webs con Playwright y las tres APIs en paralelo.

    El AsyncClient se abre una sola vez y se comparte: las cuatro requests HTTP
    (riesgo país, BCRA x2, FED) reusan el pool en vez de negociar TLS cada una.
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        return await asyncio.gather(
            bna.run(),
            dolarhoy.run(),
            ambito.run(),
            riesgo_pais.run(client),
            bcra.run(client),
            fed.run(client),
        )


def run_all_sync() -> tuple[dict, dict, dict, dict, dict, dict]:
    """Corre BNA, DolarHoy, Ambito, riesgo país, BCRA y FED en paralelo y devuelve
    sus resultados en ese orden. Pensada para llamarse desde una celda de notebook."""
    return run_async(_run_all())
