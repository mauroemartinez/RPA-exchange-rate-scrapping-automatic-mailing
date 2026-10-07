import sys
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import control_diario  # noqa: E402

MARTES = date(2026, 10, 6)


class EngineFalso:
    def __init__(self, fila):
        self.fila = fila
        self.sql = []

    @contextmanager
    def connect(self):
        engine = self

        class Conn:
            def execute(self, sql, params=None):
                engine.sql.append(str(sql))
                return type("R", (), {"first": lambda _self: engine.fila})()

        yield Conn()

    def dispose(self):
        pass


@pytest.fixture
def entorno(monkeypatch):
    alertas = []
    monkeypatch.setattr(control_diario.fechas, "hoy", lambda: MARTES)
    monkeypatch.setattr(control_diario.feriados, "nombre_feriado", lambda fecha: None)
    monkeypatch.setattr(control_diario.mailer, "enviar_alerta", lambda asunto, cuerpo: alertas.append(asunto))

    def usar(fila):
        engine = EngineFalso(fila)
        monkeypatch.setattr(control_diario.data_access, "crear_engine", lambda: engine)
        return engine

    return usar, alertas


def test_con_la_fila_de_hoy_todo_ok(entorno):
    usar, alertas = entorno
    engine = usar((True,))
    assert control_diario.main([]) == 0
    assert alertas == []
    assert engine.sql[0] == "SET TRANSACTION READ ONLY"


def test_sin_la_fila_de_hoy_alerta_y_falla(entorno):
    usar, alertas = entorno
    usar(None)
    assert control_diario.main([]) == 1
    assert len(alertas) == 1 and "2026-10-06" in alertas[0]


def test_un_feriado_no_se_controla(entorno, monkeypatch):
    usar, alertas = entorno
    usar(None)
    monkeypatch.setattr(control_diario.feriados, "nombre_feriado", lambda fecha: "Día de prueba")
    assert control_diario.main([]) == 0 and alertas == []


def test_un_fin_de_semana_no_se_controla(entorno, monkeypatch):
    usar, alertas = entorno
    usar(None)
    monkeypatch.setattr(control_diario.fechas, "hoy", lambda: date(2026, 10, 10))
    assert control_diario.main([]) == 0 and alertas == []


def test_sin_alerta_no_manda_el_mail(entorno):
    usar, alertas = entorno
    usar(None)
    assert control_diario.main(["--sin-alerta"]) == 1
    assert alertas == []
