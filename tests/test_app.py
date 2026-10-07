import json
import subprocess

import pytest
from fastapi.testclient import TestClient

import app

KEY = {"x-api-key": "clave-de-test"}


@pytest.fixture
def cliente():
    return TestClient(app.app)


@pytest.fixture
def corrida_falsa(monkeypatch):
    """subprocess.run falso: escribe el JSON que escribiría pipeline.py y devuelve el código pedido."""
    llamadas = []

    def _instalar(returncode=0, estado="ok"):
        def run(comando, **kwargs):
            llamadas.append(comando)
            ruta = comando[comando.index("--json") + 1]
            resultado = {
                "fecha": "2026-10-06", "estado": estado, "exitosa": returncode == 0, "segundos": 1.0,
                "etapas": [{"nombre": "mail", "estado": estado, "segundos": 0.5,
                            "detalle": "SMTPAuthenticationError: 535 usuario@dominio clave"}],
            }
            with open(ruta, "w", encoding="utf-8") as fh:
                json.dump(resultado, fh)
            return subprocess.CompletedProcess(comando, returncode)

        monkeypatch.setattr(app.subprocess, "run", run)
        return llamadas

    return _instalar


def test_health(cliente):
    assert cliente.get("/health").json() == {"status": "ok"}


def test_sin_key_configurada_el_endpoint_no_se_habilita(cliente, monkeypatch):
    monkeypatch.setattr(app.settings, "api_key_easy_panel", None)
    assert cliente.post("/run", headers=KEY).status_code == 503


@pytest.mark.parametrize("headers", [{}, {"x-api-key": "otra"}])
def test_key_ausente_o_incorrecta(cliente, headers):
    assert cliente.post("/run", headers=headers).status_code == 401


def test_corrida_ok_devuelve_las_etapas_sin_detalle(cliente, corrida_falsa):
    llamadas = corrida_falsa()
    respuesta = cliente.post("/run", headers=KEY)

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["success"] is True and datos["estado"] == "ok"
    assert datos["etapas"] == [{"nombre": "mail", "estado": "ok", "segundos": 0.5}]
    assert "535" not in respuesta.text  # el detalle del error no viaja en la respuesta
    assert "--dry-run" not in llamadas[0] and "--origen" in llamadas[0]


def test_dry_run_por_query_string(cliente, corrida_falsa):
    llamadas = corrida_falsa()
    cliente.post("/run?dry_run=true", headers=KEY)
    assert "--dry-run" in llamadas[0]


def test_corrida_fallida(cliente, corrida_falsa):
    corrida_falsa(returncode=1, estado="error")
    datos = cliente.post("/run", headers=KEY).json()
    assert datos["success"] is False and datos["returncode"] == 1 and datos["estado"] == "error"


def test_no_admite_dos_corridas_a_la_vez(cliente):
    app._lock.acquire()
    try:
        assert cliente.post("/run", headers=KEY).status_code == 409
    finally:
        app._lock.release()


def test_timeout(cliente, monkeypatch):
    def run(comando, **kwargs):
        raise subprocess.TimeoutExpired(comando, kwargs["timeout"])

    monkeypatch.setattr(app.subprocess, "run", run)
    assert cliente.post("/run", headers=KEY).status_code == 504
    assert not app._lock.locked()


def test_si_el_pipeline_muere_sin_json_la_respuesta_no_tiene_estado(cliente, monkeypatch):
    monkeypatch.setattr(app.subprocess, "run", lambda comando, **k: subprocess.CompletedProcess(comando, -9))
    datos = cliente.post("/run", headers=KEY).json()
    assert datos == {"success": False, "returncode": -9}


def test_un_error_inesperado_da_500_y_libera_el_lock(cliente, monkeypatch):
    def run(comando, **kwargs):
        raise OSError("no se pudo lanzar el proceso")

    monkeypatch.setattr(app.subprocess, "run", run)
    assert cliente.post("/run", headers=KEY).status_code == 500
    assert not app._lock.locked()
