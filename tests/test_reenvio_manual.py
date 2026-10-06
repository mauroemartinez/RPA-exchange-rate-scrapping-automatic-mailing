import sys
from pathlib import Path

import pytest

import charts
import email_report
from conftest import jpeg_minimo

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import reenvio_manual  # noqa: E402


@pytest.fixture
def entorno(monkeypatch, historico, resultados, tmp_path):
    con_hoy = historico.copy()
    monkeypatch.setattr(reenvio_manual.data_access, "crear_engine", lambda: None)
    monkeypatch.setattr(reenvio_manual.data_access, "leer_historico", lambda engine, respaldo_csv=True: (con_hoy, "supabase"))
    monkeypatch.setattr(reenvio_manual, "run_async", lambda coro: (coro.close(), resultados.bcra)[1])

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


def test_dry_run_no_envia(monkeypatch, entorno):
    _, enviados = entorno
    _correr(monkeypatch, "a@example.com", "--dry-run")
    assert enviados == []


def test_sin_parrafo_no_reenvia(monkeypatch, entorno):
    con_hoy, enviados = entorno
    con_hoy.loc[0, "ai_paragraph"] = ""
    with pytest.raises(SystemExit):
        _correr(monkeypatch, "a@example.com")
    assert enviados == []
