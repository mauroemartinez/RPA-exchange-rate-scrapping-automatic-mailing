"""Las explicaciones de los gráficos de agregados y deuda: texto fijo y frase con los últimos datos."""

from datetime import date

import pytest

import charts
import indicadores
from conftest import HOY


def test_numeros_con_formato_argentino():
    assert indicadores.numero(1234567.891) == "1.234.567,9"
    assert indicadores.numero(33.5) == "33,5"
    assert indicadores.numero(0.04, 2) == "0,04"


def test_los_cid_siguen_el_orden_del_mail():
    assert charts.ORDEN_EN_MAIL[int(indicadores.CID_AGREGADOS[5:]) - 1] == charts.AGREGADOS
    assert charts.ORDEN_EN_MAIL[int(indicadores.CID_DEUDA[5:]) - 1] == charts.DEUDA


def test_la_ventana_alcanza_para_un_anio_de_variacion_interanual():
    assert indicadores.desde(HOY) == date(2024, 9, 21)


def test_frase_de_agregados_con_sus_fechas(series_indicadores):
    series, _ = series_indicadores
    frase = indicadores.frase_agregados(series)
    assert frase.startswith("En el último año la base monetaria creció ")
    assert "(al 02/10/2026)" in frase and "inflación interanual de 33,5% en agosto de 2026" in frase
    assert frase.endswith("descontada la inflación, las dos cayeron.")


@pytest.mark.parametrize("inflacion, veredicto", [
    (5.0, "las dos crecieron"),
    (25.0, "la base monetaria creció y el M2 cayó"),
])
def test_el_veredicto_real_depende_de_la_inflacion(series_indicadores, inflacion, veredicto):
    series, _ = series_indicadores
    series = {**series, "inflacion_interanual": [(date(2026, 8, 31), inflacion)]}
    assert indicadores.frase_agregados(series).endswith(f"descontada la inflación, {veredicto}.")


def test_sin_inflacion_o_sin_historia_no_hay_frase(series_indicadores):
    series, _ = series_indicadores
    assert indicadores.frase_agregados({k: v for k, v in series.items() if k != "inflacion_interanual"}) is None
    corta = {**series, "base_monetaria": series["base_monetaria"][-3:], "m2": series["m2"][-3:]}
    assert indicadores.frase_agregados(corta) is None


def test_frase_de_deuda_en_dolares(series_indicadores):
    series, provisorios = series_indicadores
    frase = indicadores.frase_deuda(series, provisorios)
    assert frase.startswith("A fines de agosto de 2026 (dato provisorio), la deuda bruta del Tesoro era de USD 484,9 mil millones")
    assert "mil millones más que un año antes" in frase
    # Préstamos: 148,7 billones de pesos a 1.520 pesos por dólar
    assert frase.endswith("familias y empresas les debían a los bancos USD 97,8 mil millones.")


def test_frase_de_deuda_con_lo_que_haya(series_indicadores):
    series, _ = series_indicadores
    solo_bcra = {k: v for k, v in series.items() if k != "deuda_bruta_tesoro"}
    assert indicadores.frase_deuda(solo_bcra).startswith("Al 02/10/2026, familias y empresas")
    solo_tesoro = {"deuda_bruta_tesoro": series["deuda_bruta_tesoro"]}
    assert "(dato provisorio)" not in indicadores.frase_deuda(solo_tesoro)
    assert indicadores.frase_deuda({}) is None


def test_explicaciones_por_cid(series_indicadores):
    series, provisorios = series_indicadores
    todas = indicadores.explicaciones(series, provisorios)
    assert set(todas) == {indicadores.CID_AGREGADOS, indicadores.CID_DEUDA}
    assert todas[indicadores.CID_AGREGADOS]["texto"] == indicadores.TEXTO_AGREGADOS
    assert todas[indicadores.CID_DEUDA]["dato"].startswith("A fines de agosto")
    # Solo las de los gráficos que viajan
    assert set(indicadores.explicaciones(series, cids=["image1", indicadores.CID_DEUDA])) == {indicadores.CID_DEUDA}
    # Sin series queda el texto fijo, sin la frase
    sin_datos = indicadores.explicaciones(None)
    assert all(e["dato"] is None and e["texto"] for e in sin_datos.values())
