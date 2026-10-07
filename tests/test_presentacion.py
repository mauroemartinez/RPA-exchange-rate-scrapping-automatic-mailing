"""Prototipo de presentación ejecutiva: arma el .pptx con datos sintéticos, sin red."""

import pytest

pytest.importorskip("pptx")
from pptx import Presentation

import charts
import presentacion_ejecutiva
from conftest import jpeg_minimo


def _textos(slide) -> str:
    return " ".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)


@pytest.fixture
def imagenes(tmp_path):
    rutas = {}
    for nombre in charts.ORDEN_EN_MAIL:
        rutas[nombre] = tmp_path / nombre
        rutas[nombre].write_bytes(jpeg_minimo())
    return rutas


def test_arma_las_seis_diapositivas(historico, imagenes, tmp_path):
    ruta = presentacion_ejecutiva.armar(historico, imagenes, tmp_path / "salida")
    prs = Presentation(ruta)

    assert len(prs.slides) == 6
    assert ruta.name == f"Reporte Macroeconomico {historico['Fecha'].iloc[0]}.pptx"
    tablero = _textos(prs.slides[1])
    assert "DÓLAR BLUE" in tablero and "RIESGO PAÍS" in tablero and "FORWARD OFICIAL 3 MESES" in tablero
    assert historico["ai_paragraph"].iloc[0] in _textos(prs.slides[2])


def test_con_comentarios_por_grafico(historico, imagenes, tmp_path):
    historico = historico.copy()
    historico["ai_secciones"] = None
    historico.at[0, "ai_secciones"] = {"paralelas": "Comentario de paralelas.", "oficiales": "Comentario de oficiales.",
                                       "riesgo_pais": "Comentario de riesgo.", "btc": "Comentario de BTC."}
    prs = Presentation(presentacion_ejecutiva.armar(historico, imagenes, tmp_path))
    assert "Comentario de paralelas." in _textos(prs.slides[3])
    assert "Comentario de BTC." in _textos(prs.slides[5])


def test_sin_un_grafico_lo_avisa(historico, imagenes, tmp_path):
    del imagenes[charts.BTC]
    prs = Presentation(presentacion_ejecutiva.armar(historico, imagenes, tmp_path))
    assert "Gráfico no disponible" in _textos(prs.slides[5])
