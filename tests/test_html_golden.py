"""El HTML del mail, fijado byte a byte.

La regla de la rama es que el reporte salga igual que antes de cada cambio que no
lo busque. Este test la deja escrita: renderiza con los datos sintéticos del
conftest y compara contra los archivos de tests/datos/. Si un cambio en el HTML es
a propósito, se regeneran con:

    ACTUALIZAR_GOLDEN=1 pytest tests/test_html_golden.py

y el diff de los .html entra en el mismo commit, para que se vea qué cambió.
"""

import os
from pathlib import Path

import pytest

import email_report
import ia_generator
import indicadores
import transformations as t
from conftest import HOY, series_sinteticas

DATOS = Path(__file__).resolve().parent / "datos"

COMENTARIOS = {
    "resumen": "No se usa: el resumen va como párrafo.",
    "paralelas": "Comentario de paralelas con <etiquetas> & \"comillas\".",
    "oficiales": "Comentario de oficiales.",
    "riesgo_pais": "Comentario de riesgo país.",
    "btc": "Comentario de BTC.",
}


def _html(resultados, historico, comentarios) -> str:
    base = t.sumar_al_historico(t.armar_fila_nueva(resultados, HOY), historico)
    fwd_oficial, fwd_blue = t.forwards_fisher(base)
    df = t.agregar_brechas_y_variaciones(base)
    inflacion_12 = t.ultimos_meses(t.serie_inflacion(resultados.bcra["inflacion_mensual"]))
    # Con comentarios va el mail completo de hoy: también las explicaciones de agregados y deuda
    explicaciones = indicadores.explicaciones(*series_sinteticas()) if comentarios else None
    return email_report.renderizar(
        df, inflacion_12, fwd_oficial, fwd_blue, "Párrafo de prueba con <, & y \"comillas\".", 1.0,
        comentarios=ia_generator.comentarios_por_grafico(comentarios), explicaciones=explicaciones,
    )


@pytest.mark.parametrize("archivo, comentarios", [("reporte.html", None), ("reporte_con_comentarios.html", COMENTARIOS)])
def test_el_html_del_mail_no_cambia(resultados, historico, archivo, comentarios):
    html = _html(resultados, historico, comentarios)
    referencia = DATOS / archivo
    if os.environ.get("ACTUALIZAR_GOLDEN"):
        DATOS.mkdir(exist_ok=True)
        referencia.write_text(html, encoding="utf-8", newline="\n")
    assert html == referencia.read_text(encoding="utf-8")
