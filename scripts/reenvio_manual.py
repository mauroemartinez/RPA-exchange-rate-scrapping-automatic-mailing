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

Las únicas fuentes externas que sí se vuelven a pedir (GET, solo lectura) son las
que no están en Fact_Mercado_Macro: la inflación mensual del BCRA, para la tabla, y
las series de las frases de los gráficos de agregados y deuda (BCRA y Secretaría
de Finanzas). Esas frases salen con el último dato publicado al momento del
reenvío; si alguna fuente no responde, el gráfico va con su texto fijo solo.

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
import indicadores
import preview_git
import transformations
from config import settings
from scrapers import agregados, finanzas

# Las series que necesitan las frases de los gráficos de agregados y deuda
# inflacion_mensual también: la frase compone la interanual igual que la tabla del mail
CLAVES_FRASES = [
    "base_monetaria", "m2", "inflacion_mensual", "inflacion_interanual", "prestamos_sector_privado", "tipo_cambio_mayorista",
]


def armar_inflacion() -> pd.DataFrame:
    """Los últimos 12 meses de inflación, como en el mail diario."""
    mensual = agregados.descargar(claves=["inflacion_mensual"])["inflacion_mensual"]
    inflacion = transformations.serie_inflacion(mensual)
    return transformations.ultimos_meses(inflacion)


def armar_explicaciones(fecha_reporte: dt.date, cids: list[str]) -> dict:
    """Las explicaciones de agregados y deuda, si esos gráficos viajan; sin datos, con su texto fijo solo."""
    if indicadores.CID_AGREGADOS not in cids and indicadores.CID_DEUDA not in cids:
        return {}
    series, provisorios = {}, set()
    try:
        series.update(agregados.descargar(desde=indicadores.desde(fecha_reporte), claves=CLAVES_FRASES))
    except Exception as exc:
        print(f"  ⚠️ Sin series del BCRA para las explicaciones: {exc}")
    try:
        series[agregados.DEUDA_BRUTA.clave], provisorios = finanzas.descargar()
    except Exception as exc:
        print(f"  ⚠️ Sin la deuda bruta de la Secretaría de Finanzas: {exc}")
    try:
        return indicadores.explicaciones(series, provisorios, cids=cids)
    except Exception as exc:
        print(f"  ⚠️ No se pudieron armar las frases con los últimos datos ({exc}): van solo los textos fijos")
        return indicadores.textos_fijos(cids)


def leer_imagenes(fecha_reporte: dt.date) -> dict[str, bytes]:
    """Los gráficos de Previews/ generados el día del reporte o después.

    Si ese día un gráfico no se pudo generar (Yahoo caído, por ejemplo), en
    Previews/ quedó el de una corrida anterior: el mail diario no lo llevó, así
    que el reenvío tampoco. El template omite el que falte.
    """
    imagenes, viejos = {}, False
    for archivo in charts.ORDEN_EN_MAIL:
        ruta = RAIZ / "Previews" / archivo
        if not ruta.exists():
            print(f"  ⚠️ Falta {archivo}: el mail sale sin ese gráfico")
            continue
        # La del commit si el archivo llegó con git pull (corrida en GitHub Actions);
        # la de modificación si lo generó una corrida en esta PC
        fecha = preview_git.fecha_del_archivo(RAIZ, ruta)
        if fecha < fecha_reporte:
            print(f"  ⚠️ {archivo} es del {fecha:%d/%m/%Y}, anterior al reporte: no se adjunta")
            viejos = True
            continue
        imagenes[archivo] = ruta.read_bytes()
        print(f"  {archivo}: {len(imagenes[archivo]):,} bytes, del {fecha:%d/%m/%Y}")
    if viejos:
        print("  Si la corrida es en GitHub Actions, hacé git pull para traer los gráficos del día.")
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
    imagenes = leer_imagenes(dt.date.fromisoformat(ultima))

    # Los comentarios por gráfico de la fase 4, si la fila los tiene
    comentarios = ia_generator.comentarios_por_grafico(df.iloc[0].get("ai_secciones"))

    graficos = email_report.cids_disponibles(imagenes)
    explicaciones = armar_explicaciones(dt.date.fromisoformat(ultima), graficos)

    html = email_report.renderizar(
        df, inflacion_12, fwd_oficial, fwd_blue, parrafo,
        performance_segundos=time.perf_counter() - comienzo,
        graficos=graficos,
        comentarios=comentarios,
        explicaciones=explicaciones,
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
