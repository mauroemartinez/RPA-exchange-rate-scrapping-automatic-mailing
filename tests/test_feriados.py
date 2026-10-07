import json
from datetime import date

import httpx
import pytest

from scrapers import feriados
from scrapers.utils import ScraperError, run_async

RESPUESTA = [
    {"fecha": "2026-10-12", "tipo": "trasladable", "nombre": "Día del Respeto a la Diversidad Cultural"},
    {"fecha": "2026-12-07", "tipo": "puente", "nombre": "Puente turístico no laborable"},
]


def _cliente(status=200):
    return httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, content=json.dumps(RESPUESTA))
    ))


def test_feriados_del_anio_incluye_puentes():
    calendario = run_async(feriados.fetch(2026, _cliente()))
    assert calendario[date(2026, 10, 12)] == "Día del Respeto a la Diversidad Cultural"
    assert date(2026, 12, 7) in calendario
    assert date(2026, 10, 6) not in calendario


def test_un_error_de_la_api_es_un_scraper_error():
    with pytest.raises(ScraperError):
        run_async(feriados.fetch(2026, _cliente(404)))
