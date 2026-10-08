"""Control diario: avisa si la corrida de hoy no dejó su fila (fase 6 del roadmap).

Las alertas del pipeline cubren las corridas que fallan, pero no la que nunca
arrancó: el programador caído, la PC apagada, un día que se pasó por alto (pasó
el 19/08, el 24/09 y el 02/10 de 2026). Este script se corre un rato después del
horario de la corrida, idealmente desde otro programador, y si hoy es hábil y
Fact_Mercado_Macro no tiene la fila de hoy, sale con código 1 y manda una alerta.

Solo lee: la consulta va en una transacción READ ONLY. Lo único que puede
mandar es la alerta, y con --sin-alerta no la manda: así se lo prueba a
cualquier hora sin que salga un mail (antes de la corrida del día, la fila
todavía no existe y el control da falla, como corresponde).

Uso:
    python scripts/control_diario.py               # controla y, si falta la fila, alerta por mail
    python scripts/control_diario.py --sin-alerta  # controla y solo informa en consola
"""

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from sqlalchemy import text

from reporte import data_access, fechas, mailer
from reporte.scrapers import feriados


def fila_de_hoy(engine, hoy) -> tuple[bool, bool]:
    """(hay fila de hoy, tiene párrafo de IA)."""
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        fila = conn.execute(
            text(f'SELECT COALESCE(ai_paragraph, \'\') <> \'\' FROM "{data_access.TABLA}" WHERE "Fecha" = :f'),
            {"f": hoy},
        ).first()
    return fila is not None, bool(fila and fila[0])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sin-alerta", action="store_true", help="No manda el mail de alerta, solo informa")
    args = parser.parse_args(argv)

    hoy = fechas.hoy()
    if hoy.weekday() >= 5:
        print(f"{hoy}: fin de semana, no corresponde corrida")
        return 0
    try:
        feriado = feriados.nombre_feriado(hoy)
    except Exception as exc:
        print(f"No se pudo consultar el calendario de feriados ({exc}); se controla igual")
        feriado = None
    if feriado:
        print(f"{hoy}: feriado ({feriado}), no corresponde corrida")
        return 0

    engine = data_access.crear_engine()
    try:
        existe, con_parrafo = fila_de_hoy(engine, hoy)
    finally:
        engine.dispose()

    if existe:
        nota = "" if con_parrafo else " (sin párrafo de IA: Gemini falló o la corrida se cortó antes)"
        print(f"OK: la fila del {hoy} está guardada{nota}")
        return 0

    problema = (
        f"No hay fila del {hoy} en {data_access.TABLA}: la corrida de hoy no se hizo o falló antes de guardar.\n"
        "Si la corrida no arrancó (no llegó ninguna alerta de ella): python pipeline.py, o en GitHub, "
        "Actions > Corrida diaria > Run workflow, modo real.\n"
        "Si arrancó y su alerta muestra la etapa persistencia en error, el mail YA SALIÓ: para cargar solo la "
        "fila, python pipeline.py --sin-mail, o en GitHub el modo sin-mail. La corrida completa mandaría el mail otra vez."
    )
    print(problema)
    if args.sin_alerta:
        print("(--sin-alerta: no se manda el mail)")
    else:
        mailer.enviar_alerta(f"⚠️ Control diario: falta la corrida del {hoy}", problema)
    return 1


if __name__ == "__main__":
    sys.exit(main())
