"""Fase 4: comentarios de Gemini por gráfico en una sola llamada estructurada."""

import json
from contextlib import contextmanager
from datetime import datetime

import pytest
from pydantic import ValidationError

from conftest import HOY
from reporte import charts, email_report, ia_generator
from reporte import transformations as t
from reporte.models import SeccionesIA

AHORA = datetime(2026, 10, 6, 16, 43)

SECCIONES = {
    "resumen": "Al 06/10/2026 la brecha entre el Blue ($1555) y el MEP ($1534.1) es de 1.36%, siendo el MEP "
               "la opción más económica de las dos.",
    "paralelas": "El blue subió en el día y el MEP acompañó con una suba menor.",
    "oficiales": "El billete y las divisas del BNA se movieron en línea, con el forward por encima.",
    "riesgo_pais": "El riesgo país bajó en el día y quedó cerca del mínimo de la ventana.",
    "btc": "BTC cerró por encima de su media de 30 días, con volatilidad por debajo del promedio.",
}


@pytest.fixture
def df(resultados, historico):
    return t.sumar_al_historico(t.armar_fila_nueva(resultados, HOY), historico)


@pytest.fixture
def btc(btc_crudo):
    return charts.preparar_btc(btc_crudo, AHORA)


def test_esquema_de_secciones():
    assert SeccionesIA(**SECCIONES).btc.startswith("BTC")
    assert SeccionesIA(**{**SECCIONES, "btc": None}).btc is None
    with pytest.raises(ValidationError):
        SeccionesIA(**{**SECCIONES, "paralelas": ""})
    with pytest.raises(ValidationError):
        SeccionesIA(**{k: v for k, v in SECCIONES.items() if k != "riesgo_pais"})


def test_prompt_con_todas_las_secciones(df, btc):
    prompt = ia_generator.armar_prompt_secciones(df, btc, fwd_oficial=1800.0)
    for clave in ("[resumen]", "[paralelas]", "[oficiales]", "[riesgo_pais]", "[btc]"):
        assert clave in prompt
    assert "DATOS AL 06/10/2026" in prompt
    assert "Blue venta: $1555.0" in prompt
    assert "Forward oficial a 3 meses" in prompt and "$1,800.00" in prompt
    assert "Último cierre: USD" in prompt
    assert "siendo la opción más económica de las dos" in prompt


def test_prompt_sin_btc(df):
    prompt = ia_generator.armar_prompt_secciones(df, None, fwd_oficial=1800.0)
    assert "- Sin datos de BTC hoy" in prompt


def _respuestas(*textos):
    pendientes = list(textos)
    configs = []

    def generar_parrafo(prompt, config=None):
        configs.append(config)
        return pendientes.pop(0), "gemini-x"

    return generar_parrafo, configs


def test_generar_secciones_valida_la_respuesta(monkeypatch):
    falso, configs = _respuestas(json.dumps(SECCIONES))
    monkeypatch.setattr(ia_generator, "generar_parrafo", falso)

    secciones, modelo = ia_generator.generar_secciones("prompt")

    assert modelo == "gemini-x" and secciones.riesgo_pais == SECCIONES["riesgo_pais"]
    assert configs[0].response_mime_type == "application/json"
    assert set(configs[0].response_schema.required) == {"resumen", "paralelas", "oficiales", "riesgo_pais"}


def test_una_respuesta_invalida_se_pide_una_vez_mas(monkeypatch):
    falso, configs = _respuestas("no es json", json.dumps(SECCIONES))
    monkeypatch.setattr(ia_generator, "generar_parrafo", falso)
    secciones, _ = ia_generator.generar_secciones("prompt")
    assert secciones is not None and len(configs) == 2


def test_dos_respuestas_invalidas_no_devuelven_nada(monkeypatch):
    falso, _ = _respuestas(json.dumps({"resumen": "corto"}), "{}")
    monkeypatch.setattr(ia_generator, "generar_parrafo", falso)
    assert ia_generator.generar_secciones("prompt") == (None, None)


def test_guardar_secciones():
    ejecutado = []

    class Engine:
        @contextmanager
        def begin(self):
            class Conn:
                def execute(self, sql, params):
                    ejecutado.append((str(sql), params))
                    return type("R", (), {"rowcount": 1})()

            yield Conn()

    filas = ia_generator.guardar_secciones(Engine(), HOY, SeccionesIA(**SECCIONES), "gemini-x")

    sql, params = ejecutado[0]
    assert filas == 1
    assert '"ai_secciones" = CAST(:s AS jsonb)' in sql and 'WHERE "Fecha" = :f' in sql
    assert params["p"] == SECCIONES["resumen"] and params["m"] == "gemini-x" and params["f"] == HOY
    guardado = json.loads(params["s"])
    assert guardado["modelo"] == "gemini-x" and "resumen" not in guardado
    assert guardado["btc"] == SECCIONES["btc"]


def test_comentarios_por_grafico():
    comentarios = ia_generator.comentarios_por_grafico(SeccionesIA(**SECCIONES))
    assert [titulo for titulo, _ in comentarios["image1"]] == ["Cotizaciones paralelas", "Cotizaciones oficiales", "Riesgo país"]
    assert comentarios["image4"] == [("Bitcoin", SECCIONES["btc"])]

    sin_btc = ia_generator.comentarios_por_grafico({**SECCIONES, "btc": None, "modelo": "x"})
    assert "image4" not in sin_btc
    assert ia_generator.comentarios_por_grafico(None) == {}


def test_los_comentarios_van_debajo_de_su_grafico_y_escapados(df, resultados):
    df = t.agregar_brechas_y_variaciones(df)
    inflacion_12 = t.ultimos_meses(t.serie_inflacion(resultados.bcra["inflacion_mensual"]))
    comentarios = ia_generator.comentarios_por_grafico({**SECCIONES, "btc": "BTC <b>sube</b>"})

    html = email_report.renderizar(df, inflacion_12, 1.0, 1.0, "x", 1.0, comentarios=comentarios)

    i1, i2, i4 = html.index("cid:image1"), html.index("cid:image2"), html.index("cid:image4")
    assert i1 < html.index("Cotizaciones paralelas") < html.index("Riesgo país</div>") < i2
    assert html.index("Bitcoin") > i4
    assert "BTC &lt;b&gt;sube&lt;/b&gt;" in html


def test_sin_comentarios_el_html_no_cambia(df, resultados):
    df = t.agregar_brechas_y_variaciones(df)
    inflacion_12 = t.ultimos_meses(t.serie_inflacion(resultados.bcra["inflacion_mensual"]))
    sin = email_report.renderizar(df, inflacion_12, 1.0, 1.0, "x", 1.0)
    vacio = email_report.renderizar(df, inflacion_12, 1.0, 1.0, "x", 1.0, comentarios={})
    assert sin == vacio and "comentario-ia" not in sin
