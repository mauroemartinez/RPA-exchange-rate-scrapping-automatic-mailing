"""Fecha y hora de Argentina, sin depender de la zona horaria de la máquina.

El notebook estampaba la fila con dt.datetime.today(), que usa el reloj del sistema.
En una PC configurada en Argentina da lo mismo, pero el contenedor corre en UTC: una
corrida después de las 21:00 guardaba la fila con la fecha del día siguiente, sin
ningún error. Todo el proyecto toma "hoy" de acá.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

ZONA_AR = ZoneInfo("America/Argentina/Buenos_Aires")

# Abreviaturas que devuelve strftime("%b") con el locale es_ES de Windows, que es
# donde se generaron siempre los gráficos. Se fijan acá para no depender de
# locale.setlocale(): la imagen python:slim no trae locales en español (la llamada
# revienta con "unsupported locale setting") y además el locale es estado global
# del proceso, compartido entre hilos.
MESES_ABREV = (
    "ene.", "feb.", "mar.", "abr.", "may.", "jun.",
    "jul.", "ago.", "sep.", "oct.", "nov.", "dic.",
)


def ahora() -> datetime:
    """Fecha y hora de Argentina, sin tzinfo, igual que la devolvía datetime.now()."""
    return datetime.now(ZONA_AR).replace(tzinfo=None)


def hoy() -> date:
    """La fecha de Argentina. Es la que lleva la fila del día en Fact_Mercado_Macro."""
    return ahora().date()


def mes_abreviado(fecha: date | datetime) -> str:
    """'ene.', 'feb.', ... para la fecha dada, sin tocar el locale del proceso."""
    return MESES_ABREV[fecha.month - 1]
