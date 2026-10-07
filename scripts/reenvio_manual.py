"""Reenvía el reporte diario a los destinatarios que se le pasen por línea de comandos.

Sirve para cuando alguien se suma a la lista a mitad de mes y quiere arrancar con
el reporte de hoy sin esperar a la corrida de mañana, o para reenviarle el mail a
alguien que no lo recibió.

NO rehace el pipeline: no scrapea las webs, no valida ni inserta la fila del día,
no le pide un párrafo nuevo a Gemini y no toca el repo. Reusa lo que la corrida
diaria ya dejó hecho:

  - la última fila de Fact_Mercado_Macro (SELECT, solo lectura)
  - el ai_paragraph ya guardado en esa fila
  - los .jpg que quedaron en Previews/

La única fuente externa que sí se vuelve a pedir es la serie de inflación mensual
del BCRA (GET, solo lectura): no se persiste en Fact_Mercado_Macro, así que no hay
de dónde replayearla.

El HTML sale de email_report, el mismo módulo que usa el pipeline diario, así que
es idéntico al del mail del día salvo la línea de performance. Con varios
destinatarios van todos en Cco, para que no se vean entre ellos.

Uso:
    python scripts/reenvio_manual.py alguien@mail.com
    python scripts/reenvio_manual.py uno@mail.com otro@mail.com
    python scripts/reenvio_manual.py alguien@mail.com --csv       # adjunta el CSV
    python scripts/reenvio_manual.py alguien@mail.com --dry-run   # arma y no envía
"""

import argparse
import datetime as dt
import sys
import tempfile
import time
from pathlib import Path

# Este script vive en scripts/ pero importa del proyecto, que está un nivel
# arriba. Sin esto, 'from config import settings' solo funcionaría si se lo
# ejecuta parado justo en la raíz del repo.
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pandas as pd

import charts
import data_access
import email_report
import fechas
import ia_generator
import transformations
from config import settings
from scrapers import bcra
from scrapers.utils import run_async

# Tolerancia para avisar que los gráficos quedaron de una corrida vieja.
HORAS_IMAGEN_VIEJA = 24


def armar_inflacion() -> pd.DataFrame:
    """Los últimos 12 meses de inflación, como en el mail diario."""
    resultado = run_async(bcra.run())
    inflacion = transformations.serie_inflacion(resultado["inflacion_mensual"], resultado["bcra_tea"])
    return transformations.ultimos_meses(inflacion)


def leer_imagenes() -> dict[str, bytes]:
    """Los gráficos de Previews/, con aviso si quedaron de una corrida vieja."""
    imagenes = {}
    ahora = dt.datetime.now()

    for archivo in charts.ORDEN_EN_MAIL:
        ruta = RAIZ / "Previews" / archivo
        if not ruta.exists():
            raise SystemExit(f"❌ Falta {ruta}. Corré el pipeline para regenerar los gráficos.")

        imagenes[archivo] = ruta.read_bytes()
        modificado = dt.datetime.fromtimestamp(ruta.stat().st_mtime)
        horas = (ahora - modificado).total_seconds() / 3600
        aviso = f"  ⚠️ {horas:.0f}h de antigüedad" if horas > HORAS_IMAGEN_VIEJA else ""
        print(f"  {archivo}: {len(imagenes[archivo]):,} bytes, {modificado:%d/%m/%Y %H:%M}{aviso}")

    return imagenes


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("destinatarios", nargs="+", help="Uno o más mails, separados por espacio")
    parser.add_argument("--csv", action="store_true", help="Adjunta el CSV de seguimiento")
    parser.add_argument("--dry-run", action="store_true", help="Arma el mail y no lo envía")
    args = parser.parse_args()

    comienzo = time.perf_counter()
    engine = data_access.crear_engine()

    # Sin respaldo en el CSV: reenviar datos viejos sería peor que no reenviar.
    df, _ = data_access.leer_historico(engine, respaldo_csv=False)
    ultima = df["Fecha"].iloc[0]
    print(f"Supabase: {len(df)} filas. Última fecha: {ultima}")

    if ultima != str(fechas.hoy()):
        print(f"⚠️ La última fila es del {ultima}, no de hoy. Se reenvía ese reporte igual.")

    parrafo = df["ai_paragraph"].iloc[0]
    if not isinstance(parrafo, str) or not parrafo.strip():
        raise SystemExit(
            f"❌ La fila del {ultima} no tiene ai_paragraph. Corré el pipeline antes de reenviar."
        )
    print(f"Párrafo IA del {ultima}: {len(parrafo)} caracteres")

    # Los forwards van antes de agregar las brechas, igual que en el pipeline
    fwd_oficial, fwd_blue = transformations.forwards_fisher(df)
    csv = email_report.csv_historico(df) if args.csv else None
    df = transformations.agregar_brechas_y_variaciones(df)
    inflacion_12 = armar_inflacion()
    imagenes = leer_imagenes()

    # Los comentarios por gráfico de la fase 4, si la fila los tiene
    secciones = df["ai_secciones"].iloc[0] if "ai_secciones" in df.columns else None
    comentarios = ia_generator.comentarios_por_grafico(secciones if isinstance(secciones, dict) else None)

    html = email_report.renderizar(
        df, inflacion_12, fwd_oficial, fwd_blue, parrafo,
        performance_segundos=time.perf_counter() - comienzo,
        graficos=email_report.cids_disponibles(imagenes),
        comentarios=comentarios,
    )

    # Con un solo destinatario va derecho en Para, que es lo habitual en un
    # reenvío manual. No es cosmético: un mail cuyo Para apunta al propio
    # remitente y que llega por Cco es una señal clásica de spam, y pesa todavía
    # más cuando el destinatario nunca recibió nada de esta casilla. Con un único
    # destinatario, Cco no protege la privacidad de nadie.
    if len(args.destinatarios) == 1:
        para, cco = args.destinatarios[0], None
    else:
        para, cco = settings.email_sender, args.destinatarios

    em = email_report.armar_mensaje(
        html, imagenes, email_report.asunto(dt.date.fromisoformat(ultima)), para=para, cco=cco, csv=csv
    )

    if args.dry_run:
        # En el temp del sistema y no en Previews/: el pipeline commitea y pushea
        # todo lo que cambie en esa carpeta, así que un preview dejado ahí
        # termina en GitHub.
        salida = Path(tempfile.gettempdir()) / "reenvio_preview.html"
        salida.write_text(html, encoding="utf-8")
        print(
            f"\n[DRY-RUN] Sin enviar. Preview en {salida}\n"
            f"          Mail de {len(em.as_string()):,} bytes para: "
            f"{', '.join(args.destinatarios)}"
        )
        return

    # A diferencia del mail diario, acá un fallo corta el script: un reenvío
    # manual que falla en silencio es peor que uno que grita.
    try:
        email_report.enviar(em, args.destinatarios)
    except Exception as exc:
        raise SystemExit(f"❌ No se pudo enviar: {type(exc).__name__}: {exc}") from exc

    csv_txt = "CON CSV" if args.csv else "sin CSV"
    print(f"\n🚀 Reporte del {ultima} ({csv_txt}) enviado a: {', '.join(args.destinatarios)}")


if __name__ == "__main__":
    main()
