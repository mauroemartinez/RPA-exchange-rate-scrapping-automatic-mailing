import itertools
from contextlib import contextmanager
from datetime import date

import pytest

from reporte import ia_generator


class _ClienteFalso:
    """genai.Client falso: cada (key, modelo) responde según el guion.

    Una lista en el guion son respuestas sucesivas, una por llamada.
    """

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
        if isinstance(respuesta, list):
            respuesta = respuesta.pop(0) if respuesta else "ok"
        if isinstance(respuesta, Exception):
            raise respuesta
        return type("R", (), {"text": f"texto de {model}"})()


@pytest.fixture
def cliente_falso(monkeypatch):
    _ClienteFalso.guion, _ClienteFalso.llamadas, _ClienteFalso.timeouts = {}, [], []
    monkeypatch.setattr(ia_generator.genai, "Client", _ClienteFalso)
    # Sin esperas reales entre rondas; lo esperado queda anotado
    _ClienteFalso.esperas = []
    monkeypatch.setattr(ia_generator, "_esperar", _ClienteFalso.esperas.append)
    return _ClienteFalso


KEYS = ("gemini-falsa-1", "gemini-falsa-2")
MEJOR, SEGUNDO = ia_generator.MODELOS[0], ia_generator.MODELOS[1]


def test_el_mejor_modelo_responde_a_la_primera(cliente_falso):
    assert ia_generator.generar_parrafo("prompt") == (f"texto de {MEJOR}", MEJOR)
    assert cliente_falso.llamadas == [("gemini-falsa-1", MEJOR)]


def test_429_pasa_a_la_segunda_key_con_el_mismo_modelo(cliente_falso):
    cliente_falso.guion = {("gemini-falsa-1", MEJOR): Exception("429 RESOURCE_EXHAUSTED")}
    assert ia_generator.generar_parrafo("prompt") == (f"texto de {MEJOR}", MEJOR)
    assert cliente_falso.llamadas == [("gemini-falsa-1", MEJOR), ("gemini-falsa-2", MEJOR)]


def test_503_en_las_dos_keys_pasa_al_modelo_siguiente(cliente_falso):
    saturado = Exception("503 UNAVAILABLE")
    cliente_falso.guion = {(k, MEJOR): saturado for k in KEYS}
    assert ia_generator.generar_parrafo("prompt") == (f"texto de {SEGUNDO}", SEGUNDO)
    assert cliente_falso.llamadas[-1] == ("gemini-falsa-1", SEGUNDO)


def test_un_modelo_que_la_cuenta_no_tiene_no_corta(cliente_falso):
    cliente_falso.guion = {(k, MEJOR): Exception("404 NOT_FOUND: model not found") for k in KEYS}
    assert ia_generator.generar_parrafo("prompt")[1] == SEGUNDO


def test_tres_rondas_por_todos_los_modelos_antes_de_rendirse(cliente_falso):
    cliente_falso.guion = {(k, m): Exception("503 UNAVAILABLE") for k in KEYS for m in ia_generator.MODELOS}
    assert ia_generator.generar_parrafo("prompt") == (None, None)
    assert len(cliente_falso.llamadas) == ia_generator.RONDAS * len(ia_generator.MODELOS) * len(KEYS)
    assert cliente_falso.esperas == [ia_generator.ESPERA_ENTRE_RONDAS_S] * (ia_generator.RONDAS - 1)


def test_la_segunda_ronda_puede_salvar_el_dia(cliente_falso):
    saturado = Exception("503 UNAVAILABLE")
    # Primera ronda: todo caído; segunda: el mejor modelo vuelve
    cliente_falso.guion = {(k, m): [saturado] for k in KEYS for m in ia_generator.MODELOS}
    assert ia_generator.generar_parrafo("prompt") == (f"texto de {MEJOR}", MEJOR)
    assert len(cliente_falso.llamadas) == len(ia_generator.MODELOS) * len(KEYS) + 1


def test_el_presupuesto_de_tiempo_corta_la_busqueda(cliente_falso, monkeypatch):
    cliente_falso.guion = {(k, m): Exception("503 UNAVAILABLE") for k in KEYS for m in ia_generator.MODELOS}
    # El reloj: al arrancar y antes de la primera llamada marca 0; después, un tiempo pasado el presupuesto
    tiempos = itertools.chain([0, 0], itertools.repeat(ia_generator.PRESUPUESTO_S + 1))
    monkeypatch.setattr(ia_generator, "_reloj", lambda: next(tiempos))
    assert ia_generator.generar_parrafo("prompt") == (None, None)
    assert len(cliente_falso.llamadas) == 1


def test_cada_llamada_a_gemini_tiene_timeout(cliente_falso):
    ia_generator.generar_parrafo("prompt")
    assert cliente_falso.timeouts and all(t == ia_generator.TIMEOUT_MS for t in cliente_falso.timeouts)


def test_marcar_sin_ia_deja_el_parrafo_vacio_y_sin_comentarios():
    ejecutado = []

    class Engine:
        @contextmanager
        def begin(self):
            class Conn:
                def execute(self, sql, params):
                    ejecutado.append((str(sql), params))
                    return type("R", (), {"rowcount": 1})()

            yield Conn()

    assert ia_generator.marcar_sin_ia(Engine(), date(2026, 10, 6)) == 1
    sql, params = ejecutado[0]
    assert "\"ai_paragraph\" = ''" in sql and '"ai_secciones" = NULL' in sql and params == {"f": date(2026, 10, 6)}
