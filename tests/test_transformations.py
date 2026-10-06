import math
from dataclasses import replace
from datetime import date

import pandas as pd
import pytest
from pydantic import ValidationError

import transformations as t
from conftest import HOY
from data_access import COLUMNAS_FILA


def test_fila_nueva_respeta_el_orden_de_la_tabla(resultados):
    fila = t.armar_fila_nueva(resultados, HOY)

    assert list(fila.columns) == COLUMNAS_FILA
    assert len(fila) == 1
    assert fila["Fecha"].iloc[0] == HOY
    assert fila["TCV_MEP"].iloc[0] == 1534.1
    assert fila["riesgo_pais"].iloc[0] == 590.0
    assert fila["bcra_tea"].iloc[0] == 23.66
    assert all(fila[c].dtype == "float64" for c in COLUMNAS_FILA[1:])


def test_validacion_acepta_una_fila_sana(resultados):
    modelo = t.validar_fila(t.armar_fila_nueva(resultados, HOY))
    assert modelo.Fecha == HOY


@pytest.mark.parametrize("valor", [0.0, -5.0, float("nan")])
def test_validacion_rechaza_cotizaciones_no_positivas_o_nan(resultados, valor):
    roto = replace(resultados, dolarhoy={"TCC_Blue": 1535.0, "TCV_Blue": valor})
    with pytest.raises(ValidationError):
        t.validar_fila(t.armar_fila_nueva(roto, HOY))


def test_avisos_de_frescura(resultados):
    avisos = t.avisos_de_frescura(resultados, HOY)
    assert len(avisos) == 2
    assert "BCRA" in avisos[0] and "Riesgo país" in avisos[1]

    al_dia = replace(
        resultados,
        bcra={**resultados.bcra, "bcra_tea_fecha": HOY},
        riesgo_pais={**resultados.riesgo_pais, "riesgo_pais_fecha": HOY},
    )
    assert t.avisos_de_frescura(al_dia, HOY) == []


def test_la_fila_nueva_va_arriba_y_conserva_las_14_primeras_columnas(resultados, historico):
    df = t.sumar_al_historico(t.armar_fila_nueva(resultados, HOY), historico)

    assert len(df) == len(historico) + 1
    assert list(df.index) == list(range(len(df)))
    assert df["Fecha"].iloc[0] == HOY
    assert df["Fecha"].iloc[1] == historico["Fecha"].iloc[0]
    # El mail arma la tabla con df.iloc[:, :14]
    assert list(df.columns[:14]) == COLUMNAS_FILA


def test_forwards_de_fisher():
    df = pd.DataFrame({"bcra_tea": [30.0], "fed_tea": [4.0], "TCV_Billete": [1000.0], "TCV_Blue": [1200.0]})
    fwd_oficial, fwd_blue = t.forwards_fisher(df)
    assert fwd_oficial == pytest.approx(1000 * 1.30 / 1.04)
    assert fwd_blue == pytest.approx(1200 * 1.30 / 1.04)


def test_brechas_y_variaciones(resultados, historico):
    df = t.sumar_al_historico(t.armar_fila_nueva(resultados, HOY), historico)
    original = df.copy()
    out = t.agregar_brechas_y_variaciones(df)

    pd.testing.assert_frame_equal(df, original)  # no muta la entrada
    # Más nuevo primero: la variación compara cada fila con la siguiente (el día anterior)
    assert out["Variación TCV Blue"].iloc[0] == pytest.approx(df["TCV_Blue"].iloc[0] / df["TCV_Blue"].iloc[1] - 1)
    assert out["Variación TCV Blue"].iloc[-1] == 0
    assert out["TCV MEP / TCV Blue"].iloc[0] == pytest.approx(1534.1 / 1555.0 - 1)
    assert out["Solidario / TCV Blue"].iloc[0] == pytest.approx(1530.0 * 1.3 / 1555.0 - 1)


def test_ffill_rellena_huecos_antes_de_variar():
    df = pd.DataFrame({
        "Solidario": [10.0, None, 8.0], "TCV_Blue": [5.0, 5.0, 4.0], "TCV_Euro": [6.0, 6.0, 6.0],
        "TCV_MEP": [5.0, 5.0, 4.0],
    })
    out = t.agregar_brechas_y_variaciones(df)
    assert out["Solidario"].tolist() == [10.0, 10.0, 8.0]


def test_serie_de_inflacion(inflacion_mensual):
    inflacion = t.serie_inflacion(inflacion_mensual, bcra_tea=25.0)

    assert inflacion["Fecha"].is_monotonic_increasing
    a, b, c = (inflacion["Inflación Mensual"].iloc[k] / 100 for k in (-3, -2, -1))
    assert inflacion["Inflación Bimestral"].iloc[-1] == pytest.approx(((1 + b) * (1 + c) - 1) * 100)
    assert inflacion["Inflación Trimestral"].iloc[-1] == pytest.approx(((1 + a) * (1 + b) * (1 + c) - 1) * 100)
    assert inflacion["Inflación Anual"].iloc[:11].isna().all()
    anual = math.prod(1 + v / 100 for v in inflacion["Inflación Mensual"].iloc[-12:])
    assert inflacion["Inflación Anual"].iloc[-1] == pytest.approx((anual - 1) * 100)
    assert (inflacion["bcra_tea"] == 25.0).all()


def test_ultimos_meses_ascendentes(inflacion_mensual):
    ultimos = t.ultimos_meses(t.serie_inflacion(inflacion_mensual, 25.0))
    assert len(ultimos) == 12
    assert ultimos["Fecha"].is_monotonic_increasing
    assert ultimos["Fecha"].iloc[-1].date() == inflacion_mensual[-1][0]


def test_etiqueta_de_mes():
    assert t.etiqueta_mes(date(2025, 9, 30)) == "sep/2025"
    assert t.etiqueta_mes(pd.Timestamp("2026-01-31")) == "ene/2026"
