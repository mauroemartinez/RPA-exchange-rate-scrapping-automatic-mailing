from contextlib import contextmanager
from datetime import date

import pandas as pd
import pytest

import ia_generator


def _historial(filas=30, blue_hoy=1555.0, tea_hoy=25.0, tea_ayer=25.0):
    fechas = pd.bdate_range(end="2026-10-06", periods=filas)
    df = pd.DataFrame({
        "Fecha": fechas,
        "TCV_MEP": 1530.0,
        "TCV_Blue": 1500.0,
        "TCV_Billete": 1500.0,
        "riesgo_pais": 600.0,
        "bcra_tea": 25.0,
        "fed_tea": 3.88,
    })
    df.loc[df.index[-1], "TCV_Blue"] = blue_hoy
    df.loc[df.index[-1], "bcra_tea"] = tea_hoy
    df.loc[df.index[-2], "bcra_tea"] = tea_ayer
    return df


class EngineFalso:
    def __init__(self):
        self.updates = []

    @contextmanager
    def begin(self):
        engine = self

        class Conn:
            def execute(self, sql, params):
                engine.updates.append(params)
                return type("R", (), {"rowcount": 1})()

        yield Conn()


def test_prompt_con_brecha_y_mas_barato():
    prompt = ia_generator.armar_prompt(_historial(blue_hoy=1555.0))
    assert "DATOS REALES AL 06/10/2026" in prompt
    assert "Más barato: MEP" in prompt
    assert "- Brecha: 1.63%" in prompt
    assert "TEA BCRA" not in prompt  # sin cambio de tasa, la línea no va


def test_prompt_menciona_la_tea_cuando_se_movio():
    prompt = ia_generator.armar_prompt(_historial(tea_hoy=26.0, tea_ayer=25.0))
    assert "- TEA BCRA: 26.00%" in prompt


@pytest.fixture
def con_historial(monkeypatch):
    def _usar(df):
        monkeypatch.setattr(ia_generator.pd, "read_sql", lambda sql, con: df.copy())
    return _usar


def test_guarda_el_parrafo_en_la_fila_de_hoy(monkeypatch, con_historial):
    con_historial(_historial())
    monkeypatch.setattr(ia_generator, "generar_con_failover", lambda p, config=None: ("Párrafo", "gemini-x", 1))
    engine = EngineFalso()

    texto = ia_generator.procesar_y_guardar_parrafo(engine, fecha_esperada=date(2026, 10, 6))

    assert texto == "Párrafo"
    assert engine.updates == [{"p": "Párrafo", "m": "gemini-x", "f": date(2026, 10, 6)}]


def test_no_pisa_el_parrafo_de_otro_dia(monkeypatch, con_historial):
    con_historial(_historial())  # la última fila es del 06/10
    monkeypatch.setattr(ia_generator, "generar_con_failover", lambda p, config=None: ("Párrafo", "gemini-x", 1))
    engine = EngineFalso()

    texto = ia_generator.procesar_y_guardar_parrafo(engine, fecha_esperada=date(2026, 10, 7))

    assert texto == ia_generator.MENSAJE_FALLA
    assert engine.updates == []


def test_historial_insuficiente(con_historial):
    con_historial(_historial(filas=10))
    assert ia_generator.procesar_y_guardar_parrafo(EngineFalso()) == ia_generator.MENSAJE_FALLA


def test_sin_respuesta_de_gemini_guarda_vacio(monkeypatch, con_historial):
    # Comportamiento heredado del notebook: se guarda "" y se devuelve ""
    con_historial(_historial())
    monkeypatch.setattr(ia_generator, "generar_con_failover", lambda p, config=None: (None, None, 1))
    engine = EngineFalso()
    assert ia_generator.procesar_y_guardar_parrafo(engine) == ""
    assert engine.updates[0]["p"] == "" and engine.updates[0]["m"] is None


class _ClienteFalso:
    """genai.Client falso: cada (key, modelo) responde según el guion."""

    guion: dict = {}
    llamadas: list = []

    def __init__(self, api_key):
        self.api_key = api_key
        self.models = self

    def generate_content(self, model, contents, config=None):
        _ClienteFalso.llamadas.append((self.api_key, model))
        respuesta = _ClienteFalso.guion.get((self.api_key, model), "ok")
        if isinstance(respuesta, Exception):
            raise respuesta
        return type("R", (), {"text": f"texto de {model}"})()


@pytest.fixture
def cliente_falso(monkeypatch):
    _ClienteFalso.guion, _ClienteFalso.llamadas = {}, []
    monkeypatch.setattr(ia_generator.genai, "Client", _ClienteFalso)
    return _ClienteFalso


def test_failover_429_pasa_a_la_segunda_key(cliente_falso):
    cliente_falso.guion = {("gemini-falsa-1", "gemini-3.5-flash"): Exception("429 RESOURCE_EXHAUSTED")}
    texto, modelo, intentos = ia_generator.generar_con_failover("prompt")
    assert (texto, modelo, intentos) == ("texto de gemini-3.5-flash", "gemini-3.5-flash", 2)
    assert cliente_falso.llamadas[-1] == ("gemini-falsa-2", "gemini-3.5-flash")


def test_failover_503_pasa_al_modelo_siguiente(cliente_falso):
    cliente_falso.guion = {("gemini-falsa-1", "gemini-3.5-flash"): Exception("503 UNAVAILABLE")}
    texto, modelo, _ = ia_generator.generar_con_failover("prompt")
    assert modelo == "gemini-2.5-flash"


def test_error_tecnico_corta(cliente_falso):
    cliente_falso.guion = {("gemini-falsa-1", "gemini-3.5-flash"): Exception("400 INVALID_ARGUMENT")}
    assert ia_generator.generar_con_failover("prompt")[:2] == (None, None)


def test_generar_parrafo_respeta_el_maximo_de_intentos(monkeypatch):
    llamadas = []
    monkeypatch.setattr(ia_generator, "generar_con_failover", lambda p, config=None: llamadas.append(1) or (None, None, 1))
    assert ia_generator.generar_parrafo("prompt") == (None, None)
    assert len(llamadas) == ia_generator.MAX_INTENTOS
