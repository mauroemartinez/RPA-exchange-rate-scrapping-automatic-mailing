"""Cotización diaria de BTC/USD desde Yahoo Finance, vía yfinance.

Estaba adentro de la celda del gráfico y sin manejo de errores: si Yahoo limitaba
las consultas, el notebook se cortaba ahí, cuatro celdas antes de mandar el mail.
Ahora falla con un ScraperError y el pipeline sigue sin el gráfico de BTC.
"""

from datetime import datetime

import pandas as pd
import yfinance as yf

from scrapers.utils import ScraperError

TICKER = "BTC-USD"


def descargar(desde: datetime, hasta: datetime) -> pd.DataFrame:
    """Velas diarias entre `desde` y `hasta`, tal cual las devuelve yf.download."""
    try:
        df = yf.download(TICKER, start=desde, end=hasta, interval="1d", progress=False)
    except Exception as exc:
        raise ScraperError("Yahoo Finance", f"descargar {TICKER}", exc) from exc

    # yfinance no siempre levanta: ante un rate limit suele loguear el error y
    # devolver un DataFrame vacío.
    if df is None or df.empty:
        raise ScraperError("Yahoo Finance", f"descargar {TICKER}", ValueError("respuesta vacía"))
    return df
