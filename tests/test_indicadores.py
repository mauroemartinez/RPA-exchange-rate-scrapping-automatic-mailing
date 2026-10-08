"""Las explicaciones de los gráficos de agregados y deuda: texto fijo y frase con los últimos datos."""

from datetime import date, timedelta

import pytest

from conftest import HOY
from reporte import charts, indicadores


def test_numeros_con_formato_argentino():
    assert indicadores.numero(1234567.891) == "1.234.567,9"
    assert indicadores.numero(33.5) == "33,5"
    assert indicadores.numero(0.04, 2) == "0,04"


def test_los_cid_siguen_el_orden_del_mail():
    assert charts.ORDEN_EN_MAIL[int(indicadores.CID_AGREGADOS[5:]) - 1] == charts.AGREGADOS
    assert charts.ORDEN_EN_MAIL[int(indicadores.CID_DEUDA[5:]) - 1] == charts.DEUDA


def test_la_ventana_alcanza_para_un_anio_de_variacion_interanual():
    assert indicadores.desde(HOY) == date(2024, 9, 21)
    # Y aparte, la historia larga para comparar contra hace 12 años
    assert indicadores.desde_comparaciones(HOY) == date(2014, 9, 21)


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
    # Sin la mensual, la frase usa la interanual que publica el BCRA (variable 28)
    series = {k: v for k, v in series.items() if k != "inflacion_mensual"}
    series["inflacion_interanual"] = [(date(2026, 8, 31), inflacion)]
    assert indicadores.frase_agregados(series).endswith(f"descontada la inflación, {veredicto}.")


def test_sin_inflacion_o_sin_historia_no_hay_frase(series_indicadores):
    series, _ = series_indicadores
    sin_inflacion = {k: v for k, v in series.items() if k not in ("inflacion_interanual", "inflacion_mensual")}
    assert indicadores.frase_agregados(sin_inflacion) is None
    corta = {**series, "base_monetaria": series["base_monetaria"][-3:], "m2": series["m2"][-3:]}
    assert indicadores.frase_agregados(corta) is None


def test_frase_de_deuda_en_dolares(series_indicadores):
    series, provisorios = series_indicadores
    frase = indicadores.frase_deuda(series, provisorios)
    tesoro, prestamos = frase.split("\n")
    assert tesoro.startswith("Deuda bruta del Tesoro a fines de agosto de 2026 (dato provisorio): USD 484,9 mil millones")
    assert "mil millones más que un año antes" in tesoro
    # La serie sintética empieza en 2024: no hay con qué comparar a 4, 8 ni 12 años, y se dice
    assert "Sin comparación a 4, 8 y 12 años" in tesoro and "empieza en 2024" in tesoro
    # Préstamos: 148,7 billones de pesos a 1.520 pesos por dólar
    assert prestamos.endswith("les deben a los bancos, al 02/10/2026: USD 97,8 mil millones.")


def test_frase_de_deuda_con_lo_que_haya(series_indicadores):
    series, _ = series_indicadores
    solo_bcra = {k: v for k, v in series.items() if k != "deuda_bruta_tesoro"}
    assert indicadores.frase_deuda(solo_bcra).startswith("Lo que familias y empresas les deben a los bancos, al 02/10/2026")
    solo_tesoro = {"deuda_bruta_tesoro": series["deuda_bruta_tesoro"]}
    assert "(dato provisorio)" not in indicadores.frase_deuda(solo_tesoro)
    assert indicadores.frase_deuda({}) is None


def test_explicaciones_por_cid(series_indicadores):
    series, provisorios = series_indicadores
    todas = indicadores.explicaciones(series, provisorios)
    assert set(todas) == {indicadores.CID_AGREGADOS, indicadores.CID_DEUDA}
    assert todas[indicadores.CID_AGREGADOS]["texto"] == indicadores.TEXTO_AGREGADOS
    assert todas[indicadores.CID_DEUDA]["dato"].startswith("Deuda bruta del Tesoro a fines de agosto")
    # Solo las de los gráficos que viajan
    assert set(indicadores.explicaciones(series, cids=["image1", indicadores.CID_DEUDA])) == {indicadores.CID_DEUDA}
    # Sin series queda el texto fijo, sin la frase
    sin_datos = indicadores.explicaciones(None)
    assert all(e["dato"] is None and e["texto"] for e in sin_datos.values())


def test_la_frase_usa_la_misma_interanual_que_la_tabla_del_mail(series_indicadores):
    """Con la mensual, la interanual se compone como en la tabla de inflación, no se toma la del BCRA."""
    from reporte import transformations

    series, _ = series_indicadores
    series = {**series, "inflacion_interanual": [(date(2026, 8, 31), 40.0)]}  # la publicada, distinta a propósito
    tabla = transformations.serie_inflacion(series["inflacion_mensual"])["Inflación Anual"].iloc[-1]
    frase = indicadores.frase_agregados(series)
    assert f"inflación interanual de {indicadores.numero(tabla)}%" in frase and "40,0" not in frase


def test_cerca_de_la_inflacion_no_afirma_que_cayo_ni_que_crecio(series_indicadores):
    from reporte import transformations

    series, _ = series_indicadores
    series = {k: v for k, v in series.items() if k != "inflacion_mensual"}
    base = transformations.variacion_interanual(series["base_monetaria"])
    m2 = transformations.variacion_interanual(series["m2"])
    # La inflación justo en el medio: ni la base (arriba) ni el M2 (abajo) la cruzan por más del margen
    series["inflacion_interanual"] = [(date(2026, 8, 31), base - 0.2)]
    frase = indicadores.frase_agregados(series)
    assert "la base monetaria se mantuvo" in frase or "las dos se mantuvieron" in frase
    assert m2 < base


def test_compara_contra_la_misma_fecha_de_hace_4_8_y_12_anios():
    """Préstamos en pesos constantes y dólar fijo: en dólares, cada comparación da lo mismo que hoy."""
    dias = [date(2010, 1, 4) + timedelta(days=7 * i) for i in range(900)]
    series = {
        "prestamos_sector_privado": [(d, 1000.0 * (1 + i / 1000)) for i, d in enumerate(dias)],
        "tipo_cambio_mayorista": [(d, 10.0) for d in dias],
    }
    frase = indicadores.frase_deuda(series)
    assert "Contra la misma fecha: hace 4 años, USD" in frase and "hace 8 años" in frase and "hace 12 años" in frase
    assert "(hoy, +" in frase and "Con cepo" in frase


def test_sin_dato_a_la_fecha_no_compara():
    serie = [(date(2020, 1, 31), 1.0), (date(2026, 8, 31), 2.0)]
    assert indicadores._valor_hace(serie, date(2026, 8, 31), 4, 40) is None


def test_los_textos_explican_lo_ideal_y_no_nombran_puntos_huecos():
    assert "¿Qué sería lo ideal?" in indicadores.TEXTO_AGREGADOS
    assert "¿Qué sería lo ideal?" in indicadores.TEXTO_DEUDA and "huecos" not in indicadores.TEXTO_DEUDA
