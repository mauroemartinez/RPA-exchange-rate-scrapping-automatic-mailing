"""Fase 3: descarga, validación, cálculos, gráfico y SQL de las series monetarias."""

import json
from datetime import date, timedelta

import httpx
import pandas as pd
import pytest
from sqlalchemy.dialects import postgresql

import charts
import data_access
import transformations as t
from conftest import HOY
from scrapers import agregados
from scrapers.utils import ScraperError, run_async

BASE = agregados.POR_CLAVE["base_monetaria"]
INFLACION = agregados.POR_CLAVE["inflacion_mensual"]


def _api_falsa(puntos_por_id: dict[int, list[tuple[str, float]]], llamadas: list):
    """Transporte que imita la API v4 del BCRA: más nuevo primero, con limit/offset/desde."""

    def responder(request: httpx.Request) -> httpx.Response:
        id_variable = int(request.url.path.rsplit("/", 1)[-1])
        params = dict(request.url.params)
        llamadas.append((id_variable, params))
        puntos = sorted(puntos_por_id[id_variable], reverse=True)
        if "desde" in params:
            puntos = [p for p in puntos if p[0] >= params["desde"]]
        offset, limit = int(params.get("offset", 0)), int(params.get("limit", 1000))
        pagina = puntos[offset:offset + limit]
        cuerpo = {
            "metadata": {"resultset": {"count": len(puntos), "offset": offset, "limit": limit}},
            "results": [{"idVariable": id_variable, "detalle": [{"fecha": f, "valor": v} for f, v in pagina]}],
        }
        return httpx.Response(200, content=json.dumps(cuerpo))

    return httpx.MockTransport(responder)


def _diaria(n: int, desde=date(2015, 1, 1)) -> list[tuple[str, float]]:
    return [((desde + timedelta(days=i)).isoformat(), 1000.0 + i) for i in range(n)]


def test_pagina_hasta_traer_la_historia_completa(monkeypatch):
    monkeypatch.setattr(agregados, "PAGINA", 300)
    llamadas = []
    cliente = httpx.AsyncClient(transport=_api_falsa({15: _diaria(1000)}, llamadas))

    puntos = run_async(agregados.fetch(BASE, cliente))

    assert len(puntos) == 1000
    assert puntos[0] == (date(2015, 1, 1), 1000.0)
    assert [f for f, _ in puntos] == sorted(f for f, _ in puntos)
    assert [p["offset"] for _, p in llamadas] == ["0", "300", "600", "900"]


def test_con_desde_trae_solo_lo_reciente():
    llamadas = []
    cliente = httpx.AsyncClient(transport=_api_falsa({15: _diaria(1000)}, llamadas))
    puntos = run_async(agregados.fetch(BASE, cliente, desde=date(2017, 9, 1)))
    assert puntos[0][0] == date(2017, 9, 1)
    assert llamadas[0][1]["desde"] == "2017-09-01"


def test_fetch_todas_devuelve_cada_serie_por_clave():
    llamadas = []
    datos = {s.id_bcra: _diaria(5) for s in agregados.SERIES}
    cliente = httpx.AsyncClient(transport=_api_falsa(datos, llamadas))
    series = run_async(agregados.fetch_todas(cliente, claves=["base_monetaria", "m3"]))
    assert set(series) == {"base_monetaria", "m3"}
    assert {i for i, _ in llamadas} == {15, 1624}


def test_un_error_de_la_api_es_un_scraper_error():
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(404)))
    with pytest.raises(ScraperError):
        run_async(agregados.fetch_todas(cliente, claves=["base_monetaria"]))


def test_validar_serie():
    sana = [(HOY - timedelta(days=5), 10.0), (HOY - timedelta(days=4), 11.0)]
    assert t.validar_serie(BASE, sana, HOY) == []

    atrasada = [(HOY - timedelta(days=30), 10.0)]
    assert "30 días" in t.validar_serie(BASE, atrasada, HOY)[0]
    # La misma antigüedad es normal para una serie mensual
    assert t.validar_serie(INFLACION, atrasada, HOY) == []

    with pytest.raises(ValueError, match="no devolvió"):
        t.validar_serie(BASE, [], HOY)
    with pytest.raises(ValueError, match="desordenadas"):
        t.validar_serie(BASE, list(reversed(sana)), HOY)
    with pytest.raises(ValueError, match="no positivo"):
        t.validar_serie(BASE, [(HOY, 0.0)], HOY)
    with pytest.raises(ValueError, match="no finito"):
        t.validar_serie(BASE, [(HOY, float("nan"))], HOY)
    # Una inflación negativa es posible: la serie no exige valores positivos
    assert t.validar_serie(INFLACION, [(HOY, -0.3)], HOY) == []


def test_variacion_interanual():
    puntos = [(date(2025, 10, 1), 100.0), (date(2025, 10, 3), 105.0), (date(2026, 10, 2), 120.0)]
    # Contra el último dato de un año antes o más (01/10/2025), no contra el 03/10
    assert t.variacion_interanual(puntos) == pytest.approx(20.0)
    assert t.variacion_interanual(puntos[-1:]) is None
    assert t.variacion_interanual([]) is None


def test_interanual_por_fecha_tolera_huecos():
    puntos = [(date(2025, 1, 3), 100.0), (date(2025, 1, 6), 110.0), (date(2026, 1, 5), 150.0)]
    df = t.interanual_por_fecha(puntos)
    # 05/01/2026 no tiene dato exacto un año antes: toma el 03/01/2025
    assert df["interanual"].iloc[-1] == pytest.approx(50.0)
    assert df["interanual"].iloc[:2].isna().all()


def test_grafico_de_agregados(tmp_path):
    hoy = date(2026, 10, 6)
    dias = pd.bdate_range(end=hoy, periods=600)
    meses = pd.date_range(end=hoy, periods=30, freq="ME")
    series = {
        clave: [(d.date(), 1e6 * (1 + i / 300)) for i, d in enumerate(dias)]
        for clave in ("base_monetaria", "circulacion_monetaria", "m2")
    }
    series["m3"] = [(m.date(), 1e9 * (1 + i / 20)) for i, m in enumerate(meses)]
    series["inflacion_interanual"] = [(m.date(), 30.0 - i / 10) for i, m in enumerate(meses)]

    niveles, interanual = charts.preparar_agregados(series, hoy)
    assert set(niveles["serie"]) == set(charts.NIVELES.values())
    assert niveles["Fecha"].min() >= pd.Timestamp(hoy) - pd.DateOffset(years=1)
    assert "Inflación interanual" in set(interanual["serie"])

    ruta = charts.grafico_agregados(niveles, interanual, tmp_path)
    assert ruta.name == charts.AGREGADOS and ruta.stat().st_size > 10_000


def test_upsert_de_series_en_sql_de_postgres():
    sql = str(data_access.sentencia_series().compile(dialect=postgresql.dialect()))
    assert 'INSERT INTO "Fact_Series_Macro"' in sql
    assert 'ON CONFLICT (serie, "Fecha") DO UPDATE SET valor = excluded.valor' in sql
    # Solo se reescriben los valores que cambiaron
    assert 'WHERE "Fact_Series_Macro".valor != excluded.valor' in sql


# ── Deuda (endeudamiento C, D y A) ───────────────────────────────────────────

def test_el_catalogo_trae_la_deuda_y_el_tipo_de_cambio():
    ids = {s.clave: s.id_bcra for s in agregados.SERIES}
    assert ids["letras_bcra_pesos"] == 1258 and ids["letras_bcra_moneda_extranjera"] == 1259
    assert ids["adelantos_transitorios"] == 1268 and ids["prestamos_sector_privado"] == 26
    assert ids["tipo_cambio_mayorista"] == 5
    # La posición neta de pases (1261) quedó afuera: está en cero desde 2024
    assert 1261 not in ids.values()
    assert set(agregados.CATALOGO) == {*agregados.POR_CLAVE, "deuda_bruta_tesoro"}


def test_a_dolares_usa_el_tipo_de_cambio_vigente_cada_dia():
    pesos = [(date(2026, 10, 1), 1500.0), (date(2026, 10, 2), 3000.0), (date(2026, 10, 5), 1500.0)]
    cambio = [(date(2026, 9, 30), 1000.0), (date(2026, 10, 2), 1500.0)]
    df = t.a_dolares(pesos, cambio)
    # El 1/10 no hubo cotización: vale la del 30/9. El 5/10, la del 2/10
    assert df["usd"].round(2).tolist() == [1.5, 2.0, 1.0]
    # Antes del primer tipo de cambio no hay conversión posible
    assert t.a_dolares([(date(2026, 9, 1), 10.0)], cambio).empty


def test_preparar_deuda_pasa_todo_a_miles_de_millones_de_dolares(series_indicadores):
    series, provisorios = series_indicadores
    datos = charts.preparar_deuda(series, HOY, provisorios)

    tesoro = datos["tesoro"]
    assert len(tesoro) == charts.MESES_DEUDA_BRUTA
    assert tesoro["miles_de_millones"].iloc[-1] == pytest.approx(484.917)
    assert tesoro["provisorio"].tolist()[-2:] == [True, True] and not tesoro["provisorio"].iloc[0]
    # Se dibuja al principio del mes: el saldo al 31/8 queda sobre el rótulo de agosto
    assert tesoro["Mes"].iloc[-1] == pd.Timestamp("2026-08-01")

    prestamos = datos["prestamos"]
    assert prestamos["Fecha"].min() >= pd.Timestamp(HOY) - pd.DateOffset(years=1)
    assert prestamos["miles_de_millones"].iloc[-1] == pytest.approx(148.7e6 / 1520 / 1e3)

    bcra = datos["bcra"]
    assert list(bcra["serie"].unique()) == [charts.LETRAS, charts.ADELANTOS]
    letras = bcra[bcra["serie"] == charts.LETRAS]["miles_de_millones"].iloc[-1]
    assert letras == pytest.approx((2.3e5 + 7.4e6) / 1520 / 1e3)


def test_preparar_deuda_sin_tipo_de_cambio_deja_solo_el_tesoro(series_indicadores):
    series, provisorios = series_indicadores
    datos = charts.preparar_deuda({"deuda_bruta_tesoro": series["deuda_bruta_tesoro"]}, HOY, provisorios)
    assert datos["tesoro"] is not None and datos["prestamos"] is None and datos["bcra"] is None


@pytest.mark.parametrize("quitar", [[], ["deuda_bruta_tesoro"], ["tipo_cambio_mayorista"]])
def test_grafico_de_deuda_con_lo_que_haya(series_indicadores, tmp_path, quitar):
    series, provisorios = series_indicadores
    series = {k: v for k, v in series.items() if k not in quitar}
    ruta = charts.grafico_deuda(charts.preparar_deuda(series, HOY, provisorios), tmp_path)
    assert ruta.name == charts.DEUDA and ruta.read_bytes()[:2] == b"\xff\xd8"


def test_grafico_de_agregados_con_las_series_del_pipeline(series_indicadores, tmp_path):
    series, _ = series_indicadores
    ruta = charts.grafico_agregados(*charts.preparar_agregados(series, HOY), tmp_path)
    assert ruta.name == charts.AGREGADOS and ruta.stat().st_size > 10_000
