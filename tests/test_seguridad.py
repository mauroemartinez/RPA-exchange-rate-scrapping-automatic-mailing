"""Arreglos de la auditoría de seguridad de la rama."""

import json
import smtplib

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import app
import config
import email_report
import mailer
import pipeline
from scrapers import fed
from scrapers.utils import ScraperError, run_async


def test_una_key_vacia_cuenta_como_no_configurada():
    assert config.Settings(api_key_easy_panel="").api_key_easy_panel is None
    assert config.Settings(api_key_easy_panel="   ").api_key_easy_panel is None
    assert config.Settings(api_key_easy_panel="una-key").api_key_easy_panel.get_secret_value() == "una-key"


def test_run_con_key_vacia_no_se_habilita(monkeypatch):
    monkeypatch.setattr(app.settings, "api_key_easy_panel", SecretStr(""))
    respuesta = TestClient(app.app).post("/run", headers={"x-api-key": ""})
    assert respuesta.status_code == 503


def test_sin_documentacion_publica():
    cliente = TestClient(app.app)
    assert cliente.get("/docs").status_code == 404
    assert cliente.get("/openapi.json").status_code == 404


def test_el_error_de_fred_no_lleva_la_api_key():
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(400)))
    with pytest.raises(ScraperError) as error:
        run_async(fed.run(cliente, api_key="clave-secreta-de-fred"))
    # El traceback de la alerta recorre la cadena de causas: la excepción de httpx,
    # que trae la URL con la key, no tiene que quedar encadenada
    assert error.value.__cause__ is None and error.value.__suppress_context__
    mensajes = [str(error.value), str(error.value.cause)]
    assert all("clave-secreta-de-fred" not in m for m in mensajes)
    assert "HTTP 400" in str(error.value)


def test_las_alertas_salen_redactadas_y_a_la_lista_de_alertas(monkeypatch):
    enviados = []

    class SMTPFalso:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def ehlo(self):
            pass

        def starttls(self, context=None):
            pass

        def login(self, usuario, clave):
            pass

        def sendmail(self, de, para, mensaje):
            enviados.append((para, mensaje))

    monkeypatch.setattr(smtplib, "SMTP", SMTPFalso)
    monkeypatch.setattr(mailer.settings, "email_alertas", ["dev@example.com"])

    assert mailer.enviar_alerta("Falla", "url ...?api_key=fred-falsa&x=1, rebotó uno@example.com") is True

    para, mensaje = enviados[0]
    assert para == ["dev@example.com"]
    assert "fred-falsa" not in mensaje and "uno@example.com" not in mensaje


def test_sin_lista_de_alertas_van_a_la_del_csv(monkeypatch):
    monkeypatch.setattr(mailer.settings, "email_alertas", [])
    assert mailer.settings.destinatarios_alertas == ["csv@example.com"]


def test_el_csv_no_deja_formulas_en_el_texto(historico):
    historico = historico.copy()
    historico.loc[0, "ai_paragraph"] = "=HYPERLINK(\"http://x\")"
    historico.loc[1, "ai_paragraph"] = "-3% en el día"
    lineas = email_report.csv_historico(historico).splitlines()
    assert lineas[1].endswith(",\"'=HYPERLINK(\"\"http://x\"\")\"")
    assert lineas[2].endswith(",'-3% en el día")


def test_el_parrafo_de_ia_se_escapa_en_el_mail(resultados, historico):
    import transformations as t

    df = t.agregar_brechas_y_variaciones(t.sumar_al_historico(t.armar_fila_nueva(resultados, historico["Fecha"].iloc[0]), historico))
    inflacion = t.ultimos_meses(t.serie_inflacion(resultados.bcra["inflacion_mensual"]))
    html = email_report.renderizar(df, inflacion, 1.0, 1.0, '<a href="http://phishing">clic</a>', 1.0)
    assert '<a href="http://phishing">' not in html
    assert "&lt;a href=" in html


def test_dry_run_no_puede_escribir_en_previews():
    with pytest.raises(SystemExit):
        pipeline.main(["--dry-run", "--salida", str(pipeline.PREVIEWS)])


def test_el_json_de_la_corrida_sale_redactado(tmp_path, monkeypatch):
    fallida = pipeline.ResultadoCorrida(fecha=__import__("datetime").date(2026, 10, 6), estado="error")
    fallida.etapas.append(pipeline.Etapa("scraping", "error", "falló con no-es-una-clave para uno@example.com"))
    monkeypatch.setattr(pipeline, "correr", lambda opciones: fallida)
    monkeypatch.setattr(pipeline, "configurar_logging", lambda archivo: None)
    salida = tmp_path / "resultado.json"

    pipeline.main(["--dry-run", "--json", str(salida)])

    texto = salida.read_text(encoding="utf-8")
    assert "no-es-una-clave" not in texto and "uno@example.com" not in texto
    assert json.loads(texto)["etapas"][0]["detalle"] == "falló con *** para [destinatario]"


def test_la_direccion_de_alertas_tambien_se_tapa(monkeypatch):
    import config

    monkeypatch.setattr(config.settings, "email_alertas", ["dev@example.com"])
    assert config.redactar("535 rechazado: dev@example.com") == "535 rechazado: [destinatario]"


def test_una_segunda_key_de_gemini_vacia_no_entra_a_la_rotacion():
    assert config.Settings(gemini_api_key_2="").gemini_keys == ["gemini-falsa-1"]


def test_se_tapan_el_usuario_y_el_host_de_la_base(monkeypatch):
    from pydantic import SecretStr

    url = "postgresql://postgres.abcdefproyecto:clave-db@aws-0-sa-east-1.pooler.supabase.com:5432/postgres"
    monkeypatch.setattr(config.settings, "supabase_db_url", SecretStr(url))
    texto = config.redactar("no conecta postgres.abcdefproyecto en aws-0-sa-east-1.pooler.supabase.com")
    assert "abcdefproyecto" not in texto and "pooler.supabase.com" not in texto
    assert config.redactar("PostgreSQL y postgres siguen legibles") == "PostgreSQL y postgres siguen legibles"
