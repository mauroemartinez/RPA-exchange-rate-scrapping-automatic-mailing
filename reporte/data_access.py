"""Lectura y escritura de Fact_Mercado_Macro en Supabase.

Es lo que hacían las celdas 14, 18 y 36 del notebook: crear el engine, leer el
histórico completo y guardar la fila del día sin duplicar la fecha.
"""

import logging
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    create_engine,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from reporte.config import settings
from reporte.models import COLUMNAS_FILA, COLUMNAS_VALORES

log = logging.getLogger(__name__)

TABLA = "Fact_Mercado_Macro"

# Identificador del advisory lock de Postgres que impide dos corridas a la vez.
# Es un número cualquiera; solo tiene que ser el mismo en todos los disparadores.
CLAVE_CANDADO = 7_041_998


def crear_engine() -> Engine:
    """Engine con la misma configuración que tenía el notebook (celda 14)."""
    return create_engine(
        settings.supabase_db_url.get_secret_value(),
        pool_size=3,
        max_overflow=0,
        pool_recycle=300,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 30},
    )


def _normalizar_fecha(df: pd.DataFrame) -> pd.DataFrame:
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.date.astype(str)
    return df


def leer_historico(engine: Engine, respaldo_csv: bool = True) -> tuple[pd.DataFrame, str]:
    """Toda la tabla, más nuevo primero, con Fecha como texto 'YYYY-MM-DD'.

    Devuelve también de dónde salió: "supabase" o, si la base no responde, "csv"
    (el respaldo local de RUTA_BBDD, como el plan B de la celda 18). Ojo que ese
    CSV no lo actualiza nadie: es una foto vieja y solo sirve para no frenar en seco.
    Con respaldo_csv=False el error de la base se propaga.
    """
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(text(f'SELECT * FROM "{TABLA}" ORDER BY "Fecha" DESC;'), conn)
        if "Fecha" not in df.columns:
            raise KeyError(f"La tabla {TABLA} no tiene la columna 'Fecha'")
        return _normalizar_fecha(df).dropna(subset=["Fecha"]), "supabase"

    except Exception:
        # Sin respaldo (en GitHub Actions el CSV no existe), el error que importa es el de la base
        if not respaldo_csv or not Path(settings.ruta_bbdd).exists():
            raise
        log.exception("No se pudo leer Supabase; se usa el CSV de contingencia %s", settings.ruta_bbdd)
        # UTF-8 y no latin1: leerlo como latin1 era lo que rompía las tildes de los párrafos
        df = pd.read_csv(settings.ruta_bbdd, encoding="utf-8", encoding_errors="replace")
        if "Fecha" in df.columns:
            df = _normalizar_fecha(df)
        return df, "csv"


def guardar_fila(engine: Engine, fila: pd.DataFrame, sobrescribir: bool = False) -> bool:
    """Guarda la fila del día. Devuelve True si escribió, False si la fecha ya estaba.

    Un solo INSERT ... ON CONFLICT, atómico, en vez de traer todas las fechas y
    filtrar en pandas como hacía la celda 36. Con sobrescribir=False la fila
    existente no se toca (el comportamiento de siempre); con True se pisan sus
    valores, que es lo que pide una corrida repetida a propósito (--forzar).
    """
    registro = fila.iloc[0]
    valores = {"Fecha": registro["Fecha"]}
    valores.update({col: float(registro[col]) for col in COLUMNAS_VALORES})

    columnas = ", ".join(f'"{c}"' for c in COLUMNAS_FILA)
    parametros = ", ".join(f":{c}" for c in COLUMNAS_FILA)
    if sobrescribir:
        asignaciones = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in COLUMNAS_VALORES)
        conflicto = f"DO UPDATE SET {asignaciones}"
    else:
        conflicto = "DO NOTHING"

    sql = text(f'INSERT INTO "{TABLA}" ({columnas}) VALUES ({parametros}) ON CONFLICT ("Fecha") {conflicto}')
    with engine.begin() as conn:
        escritas = conn.execute(sql, valores).rowcount

    if escritas:
        log.info("Supabase: fila del %s %s", valores["Fecha"], "actualizada" if sobrescribir else "insertada")
    else:
        log.info("Supabase: la fila del %s ya existía, no se modificó", valores["Fecha"])
    return bool(escritas)



@contextmanager
def candado_corrida(engine: Engine):
    """Advisory lock de Postgres mientras dura la corrida. Cede True si lo obtuvo.

    El lock de app.py solo cubre los POST que llegan al mismo proceso. Este cubre
    cualquier combinación de disparadores (API, cron, GitHub Actions, alguien a mano)
    porque vive en la base. Se libera solo si el proceso muere, ya que es de sesión.
    """
    # AUTOCOMMIT: el lock es de sesión, así que no hace falta una transacción, y una
    # conexión "idle in transaction" durante toda la corrida es candidata a que la corten.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        obtenido = bool(conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": CLAVE_CANDADO}).scalar())
        try:
            yield obtenido
        finally:
            if obtenido:
                try:
                    conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": CLAVE_CANDADO})
                except Exception as exc:
                    # Con la sesión cortada el lock ya se liberó; no vale poner en rojo
                    # una corrida que a esta altura ya mandó el mail
                    log.warning("No se pudo liberar el candado de corrida (%s)", exc)


# ── Series con su frecuencia original (fase 3) ──────────────────────────────

TABLA_SERIES = "Fact_Series_Macro"

# Formato largo: una fila por serie y fecha, con la unidad y la frecuencia de la
# fuente. La crea sql/06_series_macro.sql; mientras no exista, el pipeline omite
# la etapa en vez de fallar.
_metadata = MetaData()
series_macro = Table(
    TABLA_SERIES,
    _metadata,
    Column("serie", Text, primary_key=True),
    Column("Fecha", Date, primary_key=True),
    Column("valor", Numeric, nullable=False),
    Column("frecuencia", String(1), nullable=False),
    Column("unidad", Text, nullable=False),
    Column("fuente", Text, nullable=False),
    Column("id_fuente", Text),
    Column("actualizado_en", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


def tabla_existe(engine: Engine, tabla: str = TABLA_SERIES) -> bool:
    with engine.connect() as conn:
        return conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f'public."{tabla}"'}).scalar()


def columna_existe(engine: Engine, columna: str, tabla: str = TABLA) -> bool:
    """Si la columna ya fue creada. La fase 4 (ai_secciones) se activa sola cuando existe."""
    with engine.connect() as conn:
        return bool(conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
            ),
            {"t": tabla, "c": columna},
        ).scalar())


def sentencia_series():
    """El upsert de series: inserta lo nuevo y pisa solo los valores que cambiaron.

    Los agregados del BCRA se revisan después de publicados; con el WHERE, una
    fila idéntica no se reescribe y actualizado_en marca la última revisión real.
    """
    stmt = pg_insert(series_macro)
    return stmt.on_conflict_do_update(
        index_elements=["serie", "Fecha"],
        set_={"valor": stmt.excluded.valor, "unidad": stmt.excluded.unidad, "actualizado_en": func.now()},
        where=series_macro.c.valor != stmt.excluded.valor,
    ).returning(series_macro.c.serie)


def guardar_series(engine: Engine, serie, puntos: list[tuple[date, float]]) -> int:
    """Upsert de los puntos de una scrapers.agregados.Serie (del BCRA o no). Devuelve cuántos escribió."""
    if not puntos:
        return 0
    filas = [
        {
            "serie": serie.clave, "Fecha": fecha, "valor": valor, "frecuencia": serie.frecuencia,
            "unidad": serie.unidad, "fuente": serie.fuente, "id_fuente": serie.id_fuente,
        }
        for fecha, valor in puntos
    ]
    # Con RETURNING se cuentan las filas de todos los lotes: con executemany, el
    # rowcount quedaba con el del último lote de mil y la carga histórica salía subcontada
    with engine.begin() as conn:
        escritas = len(conn.execute(sentencia_series(), filas).all())
    log.info("Supabase: %s, %d puntos nuevos o revisados de %d", serie.clave, escritas, len(puntos))
    return escritas
