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
    """read_sql falso que se comporta como el SELECT: más nuevo primero y con LIMIT."""
    def _usar(df):
        monkeypatch.setattr(
            ia_generator.pd, "read_sql", lambda sql, con, params: df.iloc[::-1].head(params["n"]).copy()
        )
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
    timeouts: list = []

    def __init__(self, api_key, http_options=None):
        self.api_key = api_key
        self.http_options = http_options
        self.models = self
        _ClienteFalso.timeouts.append(http_options.timeout if http_options else None)

    def generate_content(self, model, contents, config=None):
        _ClienteFalso.llamadas.append((self.api_key, model))
        respuesta = _ClienteFalso.guion.get((self.api_key, model), "ok")
        if isinstance(respuesta, Exception):
            raise respuesta
        return type("R", (), {"text": f"texto de {model}"})()


@pytest.fixture
def cliente_falso(monkeypatch):
    _ClienteFalso.guion, _ClienteFalso.llamadas, _ClienteFalso.timeouts = {}, [], []
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


def test_cada_llamada_a_gemini_tiene_timeout(cliente_falso):
    ia_generator.generar_con_failover("prompt")
    assert cliente_falso.timeouts and all(t == ia_generator.TIMEOUT_MS for t in cliente_falso.timeouts)


def test_limpiar_secciones():
    ejecutado = []

    class Engine:
        @contextmanager
        def begin(self):
            class Conn:
                def execute(self, sql, params):
                    ejecutado.append((str(sql), params))
                    return type("R", (), {"rowcount": 1})()

            yield Conn()

    assert ia_generator.limpiar_secciones(Engine(), date(2026, 10, 6)) == 1
    assert '"ai_secciones" = NULL' in ejecutado[0][0] and ejecutado[0][1] == {"f": date(2026, 10, 6)}


def test_con_todas_las_keys_agotadas_no_hay_parrafo(cliente_falso):
    agotada = Exception("429 RESOURCE_EXHAUSTED")
    cliente_falso.guion = {("gemini-falsa-1", "gemini-3.5-flash"): agotada, ("gemini-falsa-2", "gemini-3.5-flash"): agotada}

    assert ia_generator.generar_con_failover("prompt") == (None, None, 2)

    cliente_falso.llamadas.clear()
    assert ia_generator.generar_parrafo("prompt") == (None, None)
    # Dos vueltas de dos intentos: la segunda arranca con 2 consumidos, que es menos de MAX_INTENTOS
    assert len(cliente_falso.llamadas) == 4


def test_el_peor_caso_son_cinco_llamadas(cliente_falso):
    cliente_falso.guion = {
        ("gemini-falsa-1", "gemini-3.5-flash"): Exception("429 RESOURCE_EXHAUSTED"),
        ("gemini-falsa-2", "gemini-3.5-flash"): Exception("503 UNAVAILABLE"),
        ("gemini-falsa-2", "gemini-2.5-flash"): Exception("429 RESOURCE_EXHAUSTED"),
    }
    assert ia_generator.generar_con_failover("prompt") == (None, None, 3)

    cliente_falso.llamadas.clear()
    cliente_falso.guion[("gemini-falsa-1", "gemini-3.5-flash")] = Exception("400 INVALID_ARGUMENT")
    assert ia_generator.generar_parrafo("prompt") == (None, None)
    # 1 (error técnico) + 1 + 1, y la tercera vuelta ya no entra: 3 llamadas
    assert len(cliente_falso.llamadas) == 3
