"""Orquestación de pipeline.correr() con todos los efectos externos reemplazados."""

import contextlib
import smtplib
from dataclasses import replace
from datetime import datetime

import pytest

import charts
import ia_generator
import pipeline
from conftest import HOY
from scrapers.utils import ScraperError


class EngineFalso:
    def dispose(self):
        pass


@pytest.fixture
def entorno(historico, resultados, btc_crudo, tmp_path):
    """(Dependencias falsas, registro de lo que se hizo, carpeta de salida)."""
    hechos = {"filas": [], "parrafos": [], "mails": [], "alertas": [], "previews": []}

    def guardar_fila(engine, fila, sobrescribir=False):
        hechos["filas"].append((fila, sobrescribir))
        return True

    def generar_parrafo(engine, fecha_esperada=None):
        hechos["parrafos"].append(fecha_esperada)
        return "Párrafo de Gemini"

    deps = pipeline.Dependencias(
        crear_engine=EngineFalso,
        leer_historico=lambda engine: (historico.copy(), "supabase"),
        guardar_fila=guardar_fila,
        candado=lambda engine: contextlib.nullcontext(True),
        scrapear=lambda: (resultados.bna, resultados.dolarhoy, resultados.ambito,
                          resultados.riesgo_pais, resultados.bcra, resultados.fed),
        descargar_btc=lambda desde, hasta: btc_crudo.copy(),
        generar_parrafo=generar_parrafo,
        enviar_mail=lambda mensaje, destinatarios: hechos["mails"].append((mensaje, destinatarios)),
        leer_csv=lambda: "Fecha,TCV_Blue\n",
        actualizar_previews=lambda repo: hechos["previews"].append(repo) or (True, "ok"),
        alertar=lambda asunto, cuerpo: hechos["alertas"].append(asunto) or True,
        alertar_scraper=lambda exc: hechos["alertas"].append("scraper") or True,
        alertar_validacion=lambda exc: hechos["alertas"].append("validacion") or True,
        hoy=lambda: HOY,
        ahora=lambda: datetime(2026, 10, 6, 16, 43),
    )
    return deps, hechos, tmp_path


def _estados(resultado):
    return {e.nombre: e.estado for e in resultado.etapas}


def test_corrida_completa(entorno):
    deps, hechos, salida = entorno
    r = pipeline.correr(pipeline.Opciones(salida=salida), deps)

    assert r.estado == "ok" and r.exitosa
    assert _estados(r) == {
        "historico": "ok", "scraping": "ok", "validacion": "ok", "persistencia": "ok",
        "ia": "ok", "graficos": "ok", "mail": "ok", "previews": "omitida",
    }
    fila, sobrescribir = hechos["filas"][0]
    assert fila["Fecha"].iloc[0] == HOY and sobrescribir is False
    assert hechos["parrafos"] == [HOY]
    assert len(hechos["mails"]) == 2
    assert {p.name for p in salida.glob("*.jpg")} == set(charts.ORDEN_EN_MAIL)
    assert hechos["alertas"] == []
    html = hechos["mails"][0][0].get_payload()[0].get_payload(decode=True).decode()
    assert "Párrafo de Gemini" in html


def test_scraper_caido_alerta_y_corta(entorno):
    deps, hechos, salida = entorno

    def scrapear():
        raise ScraperError("BNA", "leer cotizaciones", TimeoutError("timeout"))

    r = pipeline.correr(pipeline.Opciones(salida=salida), replace(deps, scrapear=scrapear))

    assert r.estado == "error" and not r.exitosa
    assert _estados(r)["scraping"] == "error"
    assert "persistencia" not in _estados(r)
    assert hechos["alertas"] == ["scraper"]  # sin alerta de resumen duplicada
    assert hechos["filas"] == [] and hechos["mails"] == []


def test_fila_invalida_alerta_y_no_persiste(entorno, resultados):
    deps, hechos, salida = entorno
    rota = (resultados.bna, {"TCC_Blue": 0.0, "TCV_Blue": 1555.0}, resultados.ambito,
            resultados.riesgo_pais, resultados.bcra, resultados.fed)

    r = pipeline.correr(pipeline.Opciones(salida=salida), replace(deps, scrapear=lambda: rota))

    assert _estados(r)["validacion"] == "error"
    assert hechos["alertas"] == ["validacion"]
    assert hechos["filas"] == [] and hechos["mails"] == []


def test_si_la_fila_de_hoy_ya_existe_no_se_repite(entorno, historico):
    deps, hechos, salida = entorno
    con_hoy = historico.copy()
    con_hoy.loc[0, "Fecha"] = str(HOY)

    r = pipeline.correr(pipeline.Opciones(salida=salida), replace(deps, leer_historico=lambda e: (con_hoy, "supabase")))

    assert r.estado == "omitida" and r.exitosa
    assert hechos["filas"] == [] and hechos["mails"] == []


def test_forzar_rehace_el_dia_pisando_la_fila(entorno, historico):
    deps, hechos, salida = entorno
    con_hoy = historico.copy()
    con_hoy.loc[0, "Fecha"] = str(HOY)

    r = pipeline.correr(
        pipeline.Opciones(salida=salida, forzar=True), replace(deps, leer_historico=lambda e: (con_hoy, "supabase"))
    )

    assert r.estado == "ok"
    assert hechos["filas"][0][1] is True  # sobrescribir
    assert len(hechos["mails"]) == 2


def test_otra_corrida_en_curso(entorno):
    deps, hechos, salida = entorno
    r = pipeline.correr(pipeline.Opciones(salida=salida), replace(deps, candado=lambda e: contextlib.nullcontext(False)))
    assert r.estado == "omitida"
    assert _estados(r) == {"control": "omitida"}


def test_mail_fallido_pone_la_corrida_en_rojo_y_alerta(entorno):
    deps, hechos, salida = entorno

    def enviar(mensaje, destinatarios):
        raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")

    r = pipeline.correr(pipeline.Opciones(salida=salida), replace(deps, enviar_mail=enviar))

    assert r.estado == "error" and not r.exitosa
    assert _estados(r)["mail"] == "error"
    assert "535" in next(e.detalle for e in r.etapas if e.nombre == "mail")
    assert len(hechos["alertas"]) == 1 and "errores" in hechos["alertas"][0]


def test_sin_btc_el_mail_sale_igual_sin_ese_grafico(entorno):
    deps, hechos, salida = entorno

    def descargar(desde, hasta):
        raise ScraperError("Yahoo Finance", "descargar BTC-USD", ValueError("respuesta vacía"))

    r = pipeline.correr(pipeline.Opciones(salida=salida), replace(deps, descargar_btc=descargar))

    assert r.estado == "advertencia" and r.exitosa
    assert _estados(r)["graficos"] == "advertencia"
    mensaje = hechos["mails"][0][0]
    cids = [p.get("Content-ID") for p in mensaje.walk() if p.get_content_type() == "image/jpeg"]
    assert cids == ["<image1>", "<image2>", "<image3>"]
    assert "cid:image4" not in mensaje.get_payload()[0].get_payload(decode=True).decode()


def test_si_no_se_guarda_la_fila_no_se_llama_a_gemini(entorno):
    deps, hechos, salida = entorno

    def guardar_fila(engine, fila, sobrescribir=False):
        raise ConnectionError("Supabase no responde")

    r = pipeline.correr(pipeline.Opciones(salida=salida), replace(deps, guardar_fila=guardar_fila))

    assert _estados(r)["persistencia"] == "error"
    assert _estados(r)["ia"] == "omitida"
    assert hechos["parrafos"] == []
    assert len(hechos["mails"]) == 2  # el reporte sale igual, con el mensaje de reemplazo
    html = hechos["mails"][0][0].get_payload()[0].get_payload(decode=True).decode()
    assert ia_generator.MENSAJE_FALLA in html
    assert r.estado == "error"


def test_gemini_sin_parrafo_es_advertencia(entorno):
    deps, hechos, salida = entorno
    r = pipeline.correr(pipeline.Opciones(salida=salida), replace(deps, generar_parrafo=lambda e, fecha_esperada: ""))
    assert _estados(r)["ia"] == "advertencia"
    assert r.estado == "advertencia"


def test_dry_run_no_escribe_ni_manda_nada(entorno):
    deps, hechos, salida = entorno
    r = pipeline.correr(pipeline.Opciones(dry_run=True, salida=salida), deps)

    assert r.estado == "ok"
    assert _estados(r)["persistencia"] == "omitida"
    assert _estados(r)["ia"] == "omitida"
    assert _estados(r)["mail"] == "omitida"
    assert hechos["filas"] == [] and hechos["parrafos"] == [] and hechos["mails"] == [] and hechos["previews"] == []
    assert (salida / "mail.eml").exists() and (salida / "mail_preview.html").exists()


def test_dry_run_con_enviar_a_manda_solo_a_esa_direccion(entorno):
    deps, hechos, salida = entorno
    pipeline.correr(pipeline.Opciones(dry_run=True, salida=salida, enviar_a=["yo@example.com"]), deps)

    assert len(hechos["mails"]) == 1
    _, destinatarios = hechos["mails"][0]
    assert destinatarios == ["yo@example.com", "remitente@example.com"]
    assert hechos["filas"] == []


def test_dry_run_no_manda_alertas(entorno):
    deps, hechos, salida = entorno

    def scrapear():
        raise ScraperError("BNA", "leer cotizaciones", TimeoutError("timeout"))

    r = pipeline.correr(pipeline.Opciones(dry_run=True, salida=salida), replace(deps, scrapear=scrapear))
    assert r.estado == "error"
    assert hechos["alertas"] == []


def test_resultado_serializable_sin_detalle(entorno):
    deps, _, salida = entorno
    r = pipeline.correr(pipeline.Opciones(salida=salida), deps)
    datos = r.como_dict(con_detalle=False)
    assert datos["fecha"] == "2026-10-06" and datos["exitosa"] is True
    assert all("detalle" not in e for e in datos["etapas"])


def test_cli_valida_las_direcciones_de_enviar_a():
    with pytest.raises(SystemExit):
        pipeline.main(["--dry-run", "--enviar-a", "no-es-un-mail"])


def test_cli_devuelve_1_si_la_corrida_falla(monkeypatch):
    fallida = pipeline.ResultadoCorrida(fecha=HOY, estado="error")
    monkeypatch.setattr(pipeline, "correr", lambda opciones: fallida)
    monkeypatch.setattr(pipeline, "configurar_logging", lambda archivo: None)
    assert pipeline.main(["--dry-run"]) == 1
