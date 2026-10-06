from datetime import datetime

import matplotlib as mpl
import matplotlib.dates as mdates
import pandas as pd
import pytest
from PIL import Image

import charts
import transformations as t
from conftest import HOY

AHORA = datetime(2026, 10, 6, 16, 43)


@pytest.fixture
def df(resultados, historico):
    base = t.sumar_al_historico(t.armar_fila_nueva(resultados, HOY), historico)
    return t.agregar_brechas_y_variaciones(base)


@pytest.fixture
def inflacion_12(resultados):
    return t.ultimos_meses(t.serie_inflacion(resultados.bcra["inflacion_mensual"], 23.66))


def test_formato_de_meses_en_espanol_sin_locale():
    x = mdates.date2num(datetime(2026, 10, 1))
    assert charts._formato_mes("%b/%y")(x) == "oct./26"
    assert charts._formato_mes("%b %Y")(x) == "oct. 2026"


def test_preparar_datos_invierte_y_formatea_fechas(df):
    data = charts.preparar_datos(df)
    assert data["Fecha"].iloc[-1] == HOY.strftime("%d/%m/%y")
    assert data["Fecha"].iloc[0] == pd.Timestamp(df["Fecha"].iloc[-1]).strftime("%d/%m/%y")


def test_los_cuatro_graficos_se_generan(df, inflacion_12, btc_crudo, tmp_path):
    data = charts.preparar_datos(df)
    rutas = [
        charts.grafico_tipos_de_cambio(data, tmp_path),
        charts.grafico_variaciones(charts.preparar_variaciones(data, inflacion_12, "2026-08-01"), tmp_path),
        charts.grafico_inflacion(charts.preparar_inflacion(inflacion_12), tmp_path),
        charts.grafico_btc(charts.preparar_btc(btc_crudo, AHORA), tmp_path),
    ]
    assert [r.name for r in rutas] == [charts.TIPOS_DE_CAMBIO, charts.VARIACIONES, charts.INFLACION, charts.BTC]

    tamanios = {r.name: Image.open(r).size for r in rutas}
    assert tamanios[charts.TIPOS_DE_CAMBIO] == (1000, 1400)
    assert tamanios[charts.VARIACIONES] == (1000, 500)
    assert tamanios[charts.INFLACION] == (1000, 700)
    assert all(Image.open(r).format == "JPEG" for r in rutas)


def test_el_estilo_de_un_grafico_no_se_filtra_al_siguiente(df, btc_crudo, tmp_path):
    data = charts.preparar_datos(df)
    antes = dict(mpl.rcParams)
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()

    primero = charts.grafico_tipos_de_cambio(data, a).read_bytes()
    charts.grafico_btc(charts.preparar_btc(btc_crudo, AHORA), tmp_path)  # estilo oscuro
    segundo = charts.grafico_tipos_de_cambio(data, b).read_bytes()

    assert primero == segundo
    assert dict(mpl.rcParams) == antes


def test_preparar_btc_aplana_columnas_y_recorta_a_un_anio(btc_crudo):
    btc = charts.preparar_btc(btc_crudo, AHORA)
    assert {"Close", "MA7", "MA30", "Volatility"} <= set(btc.columns)
    assert btc.index.min() >= pd.Timestamp(AHORA) - pd.Timedelta(days=365)
    # Con el margen de descarga, las medias ya tienen valor desde el primer día visible
    assert btc["MA30"].notna().all()


def test_rango_de_descarga_de_btc_incluye_el_margen():
    desde, hasta = charts.rango_btc(AHORA)
    assert hasta == AHORA
    assert (hasta - desde).days == charts.DIAS_BTC + charts.MARGEN_BTC


def test_la_inflacion_acumulada_arranca_con_el_periodo(df, resultados):
    # Regresión: con solo los últimos 12 meses, la inflación acumulada arrancaba
    # meses después que las cotizaciones
    inflacion = t.serie_inflacion(resultados.bcra["inflacion_mensual"], 23.66)
    va = charts.preparar_variaciones(charts.preparar_datos(df), inflacion, "2026-08-01")

    primera_inflacion = va.dropna(subset=["Inflación Mensual"])["Fecha"].min()
    assert primera_inflacion == pd.Timestamp("2026-08-31")
    assert va["Inflación Mensual Acumulada"].dropna().iloc[0] == pytest.approx(va["Inflación Mensual"].dropna().iloc[0])
    assert list(va.index[:3]) == [0, 1, 2]
