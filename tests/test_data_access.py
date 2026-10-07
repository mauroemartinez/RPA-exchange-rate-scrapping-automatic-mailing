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


class _ConexionAbierta:
    """Lo que devuelve engine.connect(): usable con `with` y con execution_options()."""

    def __init__(self, conexion, falla):
        self.conexion, self.falla = conexion, falla
        self.opciones = {}

    def execution_options(self, **opciones):
        self.opciones.update(opciones)
        return self

    def __enter__(self):
        if self.falla:
            raise self.falla
        return self.conexion

    def __exit__(self, *exc):
        return False


class EngineFalso:
    def __init__(self, conexion=None, falla=None):
        self.conexion = conexion or ConexionFalsa()
        self.falla = falla
        self.abiertas = []

    @contextmanager
    def begin(self):
        yield self.conexion

    def connect(self):
        abierta = _ConexionAbierta(self.conexion, self.falla)
        self.abiertas.append(abierta)
        return abierta


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


def test_si_supabase_no_responde_se_usa_el_csv_en_utf8(monkeypatch, tmp_path, historico):
    csv = tmp_path / "respaldo.csv"
    historico.to_csv(csv, index=False, encoding="utf-8")
    monkeypatch.setattr(data_access.settings, "ruta_bbdd", csv)

    df, origen = data_access.leer_historico(EngineFalso(falla=ConnectionError("caída")))
    assert origen == "csv"
    assert df["Fecha"].iloc[0] == historico["Fecha"].iloc[0]
    assert df["ai_paragraph"].iloc[0] == historico["ai_paragraph"].iloc[0]  # "Párrafo", sin mojibake


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
    engine = EngineFalso(conexion)
    with data_access.candado_corrida(engine) as tomado:
        assert tomado is obtenido
    liberado = any("pg_advisory_unlock" in sql for sql, _ in conexion.ejecutado)
    assert liberado is obtenido
    # Sin transacción abierta durante toda la corrida
    assert engine.abiertas[0].opciones == {"isolation_level": "AUTOCOMMIT"}


def test_si_no_se_puede_liberar_el_candado_no_levanta():
    class Conexion(ConexionFalsa):
        def execute(self, sql, params=None):
            if "pg_advisory_unlock" in str(sql):
                raise ConnectionError("la sesión se cortó")
            return super().execute(sql, params)

    conexion = Conexion({"pg_try_advisory_lock": _Resultado(scalar=True)})
    with data_access.candado_corrida(EngineFalso(conexion)) as tomado:
        assert tomado is True


def test_guardar_series_cuenta_las_filas_devueltas():
    from scrapers import agregados

    class Conexion(ConexionFalsa):
        def execute(self, sql, params=None):
            self.ejecutado.append((sql, params))
            return type("R", (), {"all": lambda _self: [("base_monetaria",)] * 2})()

    engine = EngineFalso(Conexion())
    puntos = [(HOY, 10.0), (HOY.replace(day=5), 11.0)]
    assert data_access.guardar_series(engine, agregados.POR_CLAVE["base_monetaria"], puntos) == 2
    _, filas = engine.conexion.ejecutado[0]
    assert filas[0] == {"serie": "base_monetaria", "Fecha": HOY, "valor": 10.0, "frecuencia": "D",
                        "unidad": "millones de ARS", "fuente": "BCRA", "id_fuente": "15"}
    assert data_access.guardar_series(engine, agregados.POR_CLAVE["base_monetaria"], []) == 0


def test_columna_existe_mira_solo_el_schema_public():
    engine = EngineFalso(ConexionFalsa({"information_schema.columns": _Resultado(scalar=1)}))
    assert data_access.columna_existe(engine, "ai_secciones") is True
    sql, params = engine.conexion.ejecutado[0]
    assert "table_schema = 'public'" in sql and params == {"t": "Fact_Mercado_Macro", "c": "ai_secciones"}


def test_sin_csv_de_respaldo_llega_el_error_de_la_base(monkeypatch, tmp_path):
    monkeypatch.setattr(data_access.settings, "ruta_bbdd", tmp_path / "no-existe.csv")
    with pytest.raises(ConnectionError, match="caída"):
        data_access.leer_historico(EngineFalso(falla=ConnectionError("caída")))
