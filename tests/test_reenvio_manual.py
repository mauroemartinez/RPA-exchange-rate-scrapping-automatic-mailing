import sys

import pytest

import charts
import email_report
import indicadores
import reenvio_manual
from conftest import jpeg_minimo


@pytest.fixture
def entorno(monkeypatch, historico, resultados, tmp_path, series_indicadores):
    con_hoy = historico.copy()
    series, provisorios = series_indicadores
    monkeypatch.setattr(reenvio_manual.data_access, "crear_engine", lambda: None)
    monkeypatch.setattr(reenvio_manual.data_access, "leer_historico", lambda engine, respaldo_csv=True: (con_hoy, "supabase"))

    def descargar(claves=None, desde=None):
        if claves == ["inflacion_mensual"]:
            return {"inflacion_mensual": resultados.bcra["inflacion_mensual"]}
        return {clave: series[clave] for clave in claves}

    monkeypatch.setattr(reenvio_manual.agregados, "descargar", descargar)
    monkeypatch.setattr(reenvio_manual.finanzas, "descargar", lambda: (series["deuda_bruta_tesoro"], provisorios))

    previews = tmp_path / "Previews"
    previews.mkdir()
    for nombre in charts.ORDEN_EN_MAIL:
        (previews / nombre).write_bytes(jpeg_minimo())
    monkeypatch.setattr(reenvio_manual, "RAIZ", tmp_path)

    enviados = []
    monkeypatch.setattr(email_report, "enviar", lambda mensaje, destinatarios: enviados.append((mensaje, destinatarios)))
    return con_hoy, enviados


def _correr(monkeypatch, *argumentos):
    monkeypatch.setattr(sys, "argv", ["reenvio_manual.py", *argumentos])
    reenvio_manual.main()


def test_un_destinatario_va_en_para(monkeypatch, entorno):
    _, enviados = entorno
    _correr(monkeypatch, "nuevo@example.com")
    mensaje, destinatarios = enviados[0]
    assert mensaje["To"] == "nuevo@example.com" and mensaje["Bcc"] is None
    assert destinatarios == ["nuevo@example.com"]


def test_varios_destinatarios_van_en_cco(monkeypatch, entorno):
    _, enviados = entorno
    _correr(monkeypatch, "a@example.com", "b@example.com")
    mensaje, _ = enviados[0]
    assert mensaje["To"] == "remitente@example.com"
    assert mensaje["Bcc"] == "a@example.com, b@example.com"


def test_dry_run_no_envia(monkeypatch, entorno, tmp_path):
    _, enviados = entorno
    monkeypatch.setattr(reenvio_manual.tempfile, "gettempdir", lambda: str(tmp_path))
    _correr(monkeypatch, "a@example.com", "--dry-run")
    assert enviados == []
    assert (tmp_path / "reenvio_preview.html").exists()


def test_sin_parrafo_no_reenvia(monkeypatch, entorno):
    con_hoy, enviados = entorno
    con_hoy.loc[0, "ai_paragraph"] = ""
    with pytest.raises(SystemExit):
        _correr(monkeypatch, "a@example.com")
    assert enviados == []


def test_con_csv_adjunta_el_historico(monkeypatch, entorno):
    _, enviados = entorno
    _correr(monkeypatch, "a@example.com", "--csv")
    mensaje, _ = enviados[0]
    adjunto = next(p for p in mensaje.walk() if p.get_content_type() == "text/csv")
    assert adjunto.get_payload(decode=True).decode("utf-8").startswith("Fecha,TCC_Blue")


def test_el_html_es_el_mismo_que_el_del_mail_diario(monkeypatch, entorno, historico, resultados, series_indicadores):
    """La afirmación central del reenvío: mismo HTML que el pipeline, salvo la línea de performance."""
    import re

    import transformations as t

    con_hoy, enviados = entorno
    _correr(monkeypatch, "a@example.com")
    html_reenvio = enviados[0][0].get_payload()[0].get_payload(decode=True).decode()

    df = t.agregar_brechas_y_variaciones(con_hoy)
    fwd_oficial, fwd_blue = t.forwards_fisher(con_hoy)
    inflacion_12 = t.ultimos_meses(t.serie_inflacion(resultados.bcra["inflacion_mensual"]))
    # Las mismas explicaciones que arma el pipeline con esas series, con la frase de datos incluida
    series, provisorios = series_indicadores
    explicaciones = indicadores.explicaciones(series, provisorios)
    assert all(e["dato"] for e in explicaciones.values())
    html_diario = email_report.renderizar(
        df, inflacion_12, fwd_oficial, fwd_blue, con_hoy["ai_paragraph"].iloc[0], 1.0, explicaciones=explicaciones,
    )

    sin_tiempo = lambda h: re.sub(r"en [0-9.]+ segundos", "en X segundos", h)  # noqa: E731
    assert sin_tiempo(html_reenvio) == sin_tiempo(html_diario)


def test_sin_las_fuentes_de_las_frases_los_graficos_van_con_su_texto_fijo(monkeypatch, entorno):
    _, enviados = entorno

    def caida(*args, **kwargs):
        raise TimeoutError("sin respuesta")

    monkeypatch.setattr(reenvio_manual.finanzas, "descargar", caida)
    _correr(monkeypatch, "a@example.com")
    html = enviados[0][0].get_payload()[0].get_payload(decode=True).decode()
    assert indicadores.TEXTO_DEUDA in html and "deuda bruta del Tesoro era de" not in html
    assert "contra una inflación interanual de" in html  # la de agregados sí tiene sus series
