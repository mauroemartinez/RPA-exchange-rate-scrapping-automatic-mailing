"""Fixtures compartidas. Los tests no tocan ningún servicio real.

Las credenciales falsas se cargan antes de importar config: las variables de
entorno le ganan al .env, así que aunque haya uno con las claves verdaderas, los
tests no las ven. Además cualquier intento de abrir una conexión SMTP falla.
"""

import os
from datetime import date, timedelta

_FALSAS = {
    "EMAIL_SENDER": "remitente@example.com",
    "EMAIL_PASSWORD": "no-es-una-clave",
    "EMAIL_RECEIVER": "uno@example.com,dos@example.com",
    "EMAIL_RECEIVER_CSV": "csv@example.com",
    "GEMINI_API_KEY_1": "gemini-falsa-1",
    "GEMINI_API_KEY_2": "gemini-falsa-2",
    "FED_API_KEY": "fred-falsa",
    "SUPABASE_DB_URL": "postgresql://usuario:clave@127.0.0.1:1/inexistente",
    "RUTA_BBDD": "tests/no-existe.csv",
    "RUTA_REPO": ".",
    "API_KEY_EASY_PANEL": "clave-de-test",
    "SERVICE_ROUTE": "",
}
os.environ.update(_FALSAS)
os.environ.setdefault("MPLBACKEND", "Agg")

import numpy as np
import pandas as pd
import pytest

from data_access import COLUMNAS_TABLA
from transformations import ResultadosScraping

HOY = date(2026, 10, 6)


def jpeg_minimo() -> bytes:
    """Un JPEG de verdad de 1x1: MIMEImage mira los bytes mágicos para elegir el subtipo."""
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (1, 1)).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def sin_smtp_real(monkeypatch):
    import smtplib

    def _prohibido(*args, **kwargs):
        raise AssertionError("un test intentó abrir una conexión SMTP real")

    monkeypatch.setattr(smtplib, "SMTP", _prohibido)


@pytest.fixture(autouse=True)
def sin_red_real(monkeypatch):
    """Cualquier request HTTP real falla; los httpx.MockTransport de los tests siguen andando."""
    import httpx

    def _prohibido(self, request):
        raise AssertionError(f"un test intentó salir a la red: {request.url.host}")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _prohibido)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _prohibido)


def _dias_habiles_hacia_atras(desde: date, cantidad: int) -> list[date]:
    dias, actual = [], desde
    while len(dias) < cantidad:
        if actual.weekday() < 5:
            dias.append(actual)
        actual -= timedelta(days=1)
    return dias


@pytest.fixture
def historico() -> pd.DataFrame:
    """60 ruedas sintéticas, más nueva primero, con la forma que devuelve data_access."""
    fechas = _dias_habiles_hacia_atras(HOY - timedelta(days=1), 60)
    i = np.arange(len(fechas))[::-1]  # crece hacia el presente
    base = {
        "TCC_Blue": 1500.0, "TCV_Blue": 1520.0, "TCC_Billete": 1450.0, "TCV_Billete": 1500.0,
        "TCC_Divisas": 1470.0, "TCV_Divisas": 1480.0, "TCV_MEP": 1510.0, "riesgo_pais": 600.0,
        "TCC_Euro": 1700.0, "TCV_Euro": 1720.0, "fed_tea": 3.88, "bcra_tea": 25.0,
    }
    datos = {"Fecha": [str(f) for f in fechas]}
    for col, valor in base.items():
        datos[col] = valor * (1 + 0.001 * i) + (i % 3) * 0.5
    datos["Solidario"] = datos["TCV_Billete"] * 1.3
    datos["ai_paragraph"] = [f"Párrafo del {f}" for f in fechas]
    datos["ai_model"] = "gemini-2.5-flash"
    return pd.DataFrame(datos)[COLUMNAS_TABLA]


@pytest.fixture
def inflacion_mensual() -> list[tuple[date, float]]:
    """30 meses de inflación (fecha de fin de mes, %), ascendente como la da el BCRA."""
    meses = pd.date_range("2024-04-30", periods=30, freq="ME")
    return [(m.date(), round(2.0 + 0.1 * (k % 7), 1)) for k, m in enumerate(meses)]


@pytest.fixture
def resultados(inflacion_mensual) -> ResultadosScraping:
    return ResultadosScraping(
        bna={"TCC_Billete": 1480.0, "TCV_Billete": 1530.0, "TCC_Divisas": 1498.5, "TCV_Divisas": 1507.5,
             "Solidario": 1530.0 * 1.3},
        dolarhoy={"TCC_Blue": 1535.0, "TCV_Blue": 1555.0},
        ambito={"TCV_MEP": 1534.1, "TCC_Euro": 1771.72, "TCV_Euro": 1794.81},
        riesgo_pais={"riesgo_pais": 590.0, "riesgo_pais_fecha": HOY - timedelta(days=1)},
        bcra={"bcra_tea": 23.66, "bcra_tea_fecha": HOY - timedelta(days=2), "inflacion_mensual": inflacion_mensual},
        fed={"fed_tea": 3.88, "fed_tea_fecha": HOY - timedelta(days=1)},
    )


@pytest.fixture
def btc_crudo() -> pd.DataFrame:
    """Lo que devuelve yf.download: columnas MultiIndex y un índice de fechas sin nombre."""
    indice = pd.date_range("2025-08-27", "2026-10-06", freq="D")
    precio = 60000 + np.sin(np.arange(len(indice)) / 15) * 5000 + np.arange(len(indice)) * 20
    columnas = pd.MultiIndex.from_tuples([(c, "BTC-USD") for c in ["Close", "High", "Low", "Open", "Volume"]])
    datos = np.column_stack([precio, precio * 1.01, precio * 0.99, precio, np.full(len(indice), 1e9)])
    return pd.DataFrame(datos, index=pd.DatetimeIndex(indice, name=None), columns=columnas)
