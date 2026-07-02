import asyncio

from scrapers import ambito, bna, dolarhoy
from scrapers.utils import run_playwright


async def _run_all():
    return await asyncio.gather(bna.run(), dolarhoy.run(), ambito.run())


def run_all_sync() -> tuple[dict, dict, dict]:
    """Corre BNA, DolarHoy y Ambito en paralelo y devuelve sus resultados en ese
    orden. Pensada para llamarse desde una celda de notebook."""
    return run_playwright(_run_all())
