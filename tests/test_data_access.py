from contextlib import contextmanager

import pandas as pd
import pytest

import data_access
from conftest import HOY
from transformations import armar_fila_nueva


class _Resultado:
    def __init__(self, rowcount=1, scalar=None):
        self.rowcount = rowcount
        self._scalar = scalar

    def scalar(self):
        return self._scalar


class ConexionFalsa:
    def __init__(self, respuestas=None):
        self.ejecutado = []
        self.respuestas = respuestas or {}

    def execute(self, sql, params=None):
        texto = str(sql)
        self.ejecutado.append((texto, params))
        for clave, respuesta in self.respuestas.items():
            if clave in texto:
                return respuesta
        return _Resultado()


class EngineFalso:
    def __init__(self, conexion=None, falla=None):
        self.conexion = conexion or ConexionFalsa()
        self.falla = falla

    @contextmanager
    def begin(self):
        yield self.conexion

    @contextmanager
    def connect(self):
        if self.falla:
            raise self.falla
        yield self.conexion


def test_insert_sin_pisar_la_fila_existente(resultados):
    engine = EngineFalso()
    assert data_access.guardar_fila(engine, armar_fila_nueva(resultados, HOY)) is True

    sql, params = engine.conexion.ejecutado[0]
    assert 'ON CONFLICT ("Fecha") DO NOTHING' in sql
    assert list(params) == data_access.COLUMNAS_FILA
    assert params["Fecha"] == HOY
    assert all(type(params[c]) is float for c in data_access.COLUMNAS_VALORES)


def test_insert_que_pisa_con_forzar(resultados):
    engine = EngineFalso()
    data_access.guardar_fila(engine, armar_fila_nueva(resultados, HOY), sobrescribir=True)
    sql, _ = engine.conexion.ejecutado[0]
    assert 'DO UPDATE SET "TCC_Blue" = EXCLUDED."TCC_Blue"' in sql
    assert '"ai_paragraph"' not in sql  # el párrafo lo escribe la etapa de IA


def test_insert_informa_si_la_fecha_ya_estaba(resultados):
    engine = EngineFalso(ConexionFalsa({"INSERT": _Resultado(rowcount=0)}))
    assert data_access.guardar_fila(engine, armar_fila_nueva(resultados, HOY)) is False


def test_si_supabase_no_responde_se_usa_el_csv(monkeypatch, tmp_path, historico):
    csv = tmp_path / "respaldo.csv"
    historico.to_csv(csv, index=False, encoding="latin1", errors="replace")
    monkeypatch.setattr(data_access.settings, "ruta_bbdd", csv)

    df, origen = data_access.leer_historico(EngineFalso(falla=ConnectionError("caída")))
    assert origen == "csv"
    assert df["Fecha"].iloc[0] == historico["Fecha"].iloc[0]


def test_sin_respaldo_el_error_de_la_base_se_propaga():
    with pytest.raises(ConnectionError):
        data_access.leer_historico(EngineFalso(falla=ConnectionError("caída")), respaldo_csv=False)


def test_lectura_normal(monkeypatch, historico):
    monkeypatch.setattr(pd, "read_sql_query", lambda sql, conn: historico.copy())
    df, origen = data_access.leer_historico(EngineFalso())
    assert origen == "supabase"
    assert len(df) == len(historico)


@pytest.mark.parametrize("obtenido", [True, False])
def test_candado_de_corrida(obtenido):
    conexion = ConexionFalsa({"pg_try_advisory_lock": _Resultado(scalar=obtenido)})
    with data_access.candado_corrida(EngineFalso(conexion)) as tomado:
        assert tomado is obtenido
    liberado = any("pg_advisory_unlock" in sql for sql, _ in conexion.ejecutado)
    assert liberado is obtenido
