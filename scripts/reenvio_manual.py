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

El mail sale idéntico al de la corrida diaria: mismo template, mismas tablas de 25
días, mismos forwards de Fisher. Los destinatarios van en Cco, así que no se ven
entre ellos.

Uso:
    python scripts/reenvio_manual.py alguien@mail.com
    python scripts/reenvio_manual.py uno@mail.com otro@mail.com
    python scripts/reenvio_manual.py alguien@mail.com --csv       # adjunta el CSV
    python scripts/reenvio_manual.py alguien@mail.com --dry-run   # arma y no envía
"""

import argparse
import datetime as dt
import smtplib
import ssl
import sys
import tempfile
import time
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Este script vive en scripts/ pero importa del proyecto, que está un nivel
# arriba. Sin esto, 'from config import settings' solo funcionaría si se lo
# ejecuta parado justo en la raíz del repo.
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import numpy as np
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import create_engine, text
from tabulate import tabulate

from config import settings
from scrapers import ambito, bcra, bna, dolarhoy, fed, riesgo_pais
from scrapers.utils import run_async

TABLA = "Fact_Mercado_Macro"

# Las mismas 25 filas que muestra el mail diario (celda 40 del notebook).
COTIZACIONES_A_MOSTRAR = 25

# Los nombres de archivo los fijan las celdas 41-44 del notebook. El orden importa:
# el template los referencia como cid:image1 .. cid:image4, en este orden.
ARCHIVOS_IMG = [
    "Gráficos Tipos de Cambios y Riesgo País.jpg",
    "Gráficos Inflación.jpg",
    "Variaciones.jpg",
    "Gráfico BTC.jpg",
]

# Tolerancia para avisar que los gráficos quedaron de una corrida vieja.
HORAS_IMAGEN_VIEJA = 24


def leer_historico(engine) -> pd.DataFrame:
    """Todo Fact_Mercado_Macro, más nuevo primero. Igual que la celda 19."""
    query = text(f'SELECT * FROM "{TABLA}" ORDER BY "Fecha" DESC;')
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.date.astype(str)
    return df.dropna(subset=["Fecha"])


def armar_inflacion() -> tuple[pd.DataFrame, str]:
    """Tabla de inflación de los últimos 12 meses y la interanual, como la celda 22."""
    resultado = run_async(bcra.run())

    inflacion = pd.DataFrame(
        resultado["inflacion_mensual"], columns=["Fecha", "Inflación Mensual"]
    )
    inflacion["Fecha"] = pd.to_datetime(inflacion["Fecha"])

    factor = inflacion["Inflación Mensual"] / 100 + 1
    inflacion["Inflación Bimestral"] = (factor.rolling(2).apply(np.prod, raw=True) - 1) * 100
    inflacion["Inflación Trimestral"] = (factor.rolling(3).apply(np.prod, raw=True) - 1) * 100
    inflacion["Inflación Anual"] = (
        factor.rolling(12, min_periods=12).apply(np.prod, raw=True) - 1
    ) * 100
    inflacion["bcra_tea"] = resultado["bcra_tea"]

    inflacion = inflacion.iloc[::-1].head(12)
    inflacion["Fecha"] = inflacion["Fecha"].dt.strftime("%d-%m-%Y")

    # Celda 46: la interanual se toma antes de pasar las columnas a proporción.
    interanual = "{0:,.2f}%".format(inflacion["Inflación Anual"].iloc[-1])
    cols_pct = [
        "Inflación Mensual",
        "Inflación Bimestral",
        "Inflación Trimestral",
        "Inflación Anual",
        "bcra_tea",
    ]
    inflacion[cols_pct] = inflacion[cols_pct] / 100

    return inflacion, interanual


def pintar_variacion(valor):
    """Verde si sube, rojo si baja. #1e8449 y no #27ae60: el segundo da 2.87:1
    sobre blanco y no llega al 4.5:1 que pide WCAG AA."""
    try:
        val_num = float(valor)
        color = "#1e8449" if val_num > 0 else "#c0392b"
        return f'<span style="color: {color}; font-weight: bold;">{val_num:.2%}</span>'
    except (TypeError, ValueError):
        return valor


def renderizar(df: pd.DataFrame, inflacion: pd.DataFrame, interanual: str, comienzo: float) -> str:
    """El HTML del reporte, con los mismos cálculos que las celdas 34-48."""
    parrafo_ia = df["ai_paragraph"].iloc[0]

    # Fisher a 3 meses (celda 34). Va antes de formatear las TEA a string.
    division = (1 + float(df["bcra_tea"].iloc[0]) / 100) / (
        1 + float(df["fed_tea"].iloc[0]) / 100
    )
    fwd_oficial = float(df["TCV_Billete"].iloc[0]) * division
    fwd_blue = float(df["TCV_Blue"].iloc[0]) * division

    # Brechas y variación del día (celda 35).
    df["Solidario / TCV Blue"] = df["Solidario"] / df["TCV_Blue"] - 1
    df["TCV MEP / TCV Blue"] = df["TCV_MEP"] / df["TCV_Blue"] - 1
    df["TCV Euro / TCC Blue %"] = df["TCV_Euro"] / df["TCV_Blue"] - 1

    df["Solidario"] = df["Solidario"].ffill()
    df["TCV_Blue"] = df["TCV_Blue"].ffill()
    df["TCV_Euro"] = df["TCV_Euro"].ffill()

    df["Variación Solidario"] = df["Solidario"].pct_change(periods=-1).fillna(0)
    df["Variación TCV Blue"] = df["TCV_Blue"].pct_change(periods=-1).fillna(0)
    df["Variación TCV Euro"] = df["TCV_Euro"].pct_change(periods=-1).fillna(0)

    # Resumen ejecutivo: se calcula con las TEA todavía numéricas.
    cantidad_usd = 100
    costo_blue = float(df["TCV_Blue"].iloc[0] * cantidad_usd)
    costo_oficial = float(df["Solidario"].iloc[0] * cantidad_usd)
    ahorro_valor = costo_blue - costo_oficial
    color_ahorro = "#1e8449" if ahorro_valor > 0 else "#c0392b"
    label_ahorro = "Ahorro estimado" if ahorro_valor > 0 else "Sobrecosto estimado"

    var_blue = float((df["TCV_Blue"].iloc[0] / df["TCV_Blue"].iloc[1] - 1) * 100)
    brecha_solidario = float((1 - df["Solidario"].iloc[0] / df["TCV_Blue"].iloc[0]) * 100)
    var_divisas = float((df["TCV_Divisas"].iloc[0] / df["TCV_Divisas"].iloc[1] - 1) * 100)
    var_euro = float((df["TCV_Euro"].iloc[0] / df["TCV_Euro"].iloc[1] - 1) * 100)
    brecha_euro_blue = float((1 - df["TCV_Blue"].iloc[0] / df["TCV_Euro"].iloc[0]) * 100)
    riesgo_pts = float(df["riesgo_pais"].iloc[0])
    sobretasa = riesgo_pts / 100

    # Celda 47: recién acá las TEA pasan a string con formato de porcentaje.
    df["fed_tea"] = df["fed_tea"].apply(lambda x: f"{x/100:.2%}" if pd.notnull(x) else "")
    df["bcra_tea"] = df["bcra_tea"].apply(lambda x: f"{x/100:.2%}" if pd.notnull(x) else "")
    df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.strftime("%d/%m/%y")

    # Tabla de cotizaciones: las primeras 14 columnas, sin las de variación.
    cotizaciones = [
        "Fecha", "tccblue", "tcvblue", "tccBillete", "tcvBillete", "tccDivisas",
        "tcvDivisas", "Solidario", "MEP", "RiesgoPaís", "tccEuros", "tcvEuros",
        "FEDtea", "BCRAtea",
    ]
    tabla_cotizaciones = tabulate(
        df.iloc[:COTIZACIONES_A_MOSTRAR, :14].values.tolist(),
        headers=cotizaciones,
        tablefmt="html",
        numalign="center",
        floatfmt=".2f",
    )

    # Tabla de variaciones: las últimas 3 columnas van pintadas.
    columnas_var = [
        "Fecha", "Solidario / TCV Blue", "TCV MEP / TCV Blue", "TCV Euro / TCC Blue %",
        "Variación Solidario", "Variación TCV Blue", "Variación TCV Euro",
    ]
    datos_formateados = []
    for fila in df[columnas_var].iloc[:COTIZACIONES_A_MOSTRAR].values.tolist():
        fila_nueva = list(fila)
        fila_nueva[-3] = pintar_variacion(fila[-3])
        fila_nueva[-2] = pintar_variacion(fila[-2])
        fila_nueva[-1] = pintar_variacion(fila[-1])
        datos_formateados.append(fila_nueva)

    tabla_variaciones = tabulate(
        datos_formateados,
        headers=columnas_var,
        tablefmt="unsafehtml",
        numalign="center",
        floatfmt=".2%",
    )

    tabla_inflacion = tabulate(
        inflacion[
            ["Fecha", "Inflación Mensual", "Inflación Bimestral", "Inflación Trimestral"]
        ].values.tolist(),
        headers=["Fecha", "I. Mensual", "I. Bimestral", "I. Trimestral"],
        tablefmt="html",
        numalign="center",
        floatfmt=".2%",
    )

    jinja_env = Environment(loader=FileSystemLoader(RAIZ / "templates"))
    return jinja_env.get_template("report_email.html").render(
        cantidad_usd=cantidad_usd,
        costo_blue=costo_blue,
        costo_oficial=costo_oficial,
        label_ahorro=label_ahorro,
        color_ahorro=color_ahorro,
        ahorro_valor=ahorro_valor,
        var_blue=var_blue,
        brecha_solidario=brecha_solidario,
        var_divisas=var_divisas,
        var_euro=var_euro,
        brecha_euro_blue=brecha_euro_blue,
        fwd_oficial=fwd_oficial,
        fwd_blue=fwd_blue,
        riesgo_pts=riesgo_pts,
        sobretasa=sobretasa,
        parrafo_ia=parrafo_ia,
        cotizaciones_a_mostrar=COTIZACIONES_A_MOSTRAR,
        tabla_cotizaciones=tabla_cotizaciones,
        tabla_variaciones=tabla_variaciones,
        tabla_inflacion=tabla_inflacion,
        inflacion_interanual=interanual,
        web_bna=bna.WEB_BNA,
        web_dolarhoy=dolarhoy.WEB_DOLARHOY,
        web_mep=ambito.WEB_MEP,
        web_euro=ambito.WEB_EURO,
        api_riesgo_pais=riesgo_pais.API_BASE,
        bcra_api_url=bcra.API_BASE,
        fed_api_url=fed.API_URL,
        performance_segundos=time.perf_counter() - comienzo,
    )


def leer_imagenes() -> dict[str, bytes]:
    """Los gráficos de Previews/, con aviso si quedaron de una corrida vieja."""
    imagenes = {}
    ahora = dt.datetime.now()

    for archivo in ARCHIVOS_IMG:
        ruta = RAIZ / "Previews" / archivo
        if not ruta.exists():
            raise SystemExit(
                f"❌ Falta {ruta}. Corré el notebook para regenerar los gráficos."
            )

        imagenes[archivo] = ruta.read_bytes()
        modificado = dt.datetime.fromtimestamp(ruta.stat().st_mtime)
        horas = (ahora - modificado).total_seconds() / 3600
        aviso = f"  ⚠️ {horas:.0f}h de antigüedad" if horas > HORAS_IMAGEN_VIEJA else ""
        print(f"  {archivo}: {len(imagenes[archivo]):,} bytes, {modificado:%d/%m/%Y %H:%M}{aviso}")

    return imagenes


def armar_mail(html: str, imagenes: dict[str, bytes], destinatarios: list[str], csv: bool):
    """El MIME completo. Los destinatarios van en Cco para que no se vean entre ellos."""
    em = MIMEMultipart("related")
    em["From"] = settings.email_sender
    em["To"] = settings.email_sender
    em["Bcc"] = ", ".join(destinatarios)
    em["Subject"] = f"📈 Reporte Macroeconómico - {dt.datetime.today():%d-%m-%Y}"
    em.attach(MIMEText(html, "html"))

    for i, archivo in enumerate(ARCHIVOS_IMG):
        img = MIMEImage(imagenes[archivo])
        img.add_header("Content-ID", f"<image{i + 1}>")
        img.add_header("Content-Disposition", "inline", filename=archivo)
        em.attach(img)

    if csv:
        try:
            contenido = Path(settings.ruta_bbdd).read_text(encoding="latin-1")
            adjunto = MIMEText(contenido, "csv")
            adjunto.add_header(
                "Content-Disposition", "attachment", filename="Seguimiento Macroeconómico"
            )
            em.attach(adjunto)
        except OSError as exc:
            print(f"⚠️ No se pudo adjuntar el CSV: {exc}")

    return em


def enviar(em, destinatarios: list[str]) -> None:
    """Un solo sendmail. A diferencia del notebook, acá un fallo corta el script:
    un reenvío manual que falla en silencio es peor que uno que grita."""
    context = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(settings.email_sender, settings.email_password.get_secret_value())
        rechazados = smtp.sendmail(settings.email_sender, destinatarios, em.as_string())

    if rechazados:
        raise SystemExit(f"❌ Destinatarios rechazados: {rechazados}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("destinatarios", nargs="+", help="Uno o más mails, separados por espacio")
    parser.add_argument("--csv", action="store_true", help="Adjunta el CSV de seguimiento")
    parser.add_argument("--dry-run", action="store_true", help="Arma el mail y no lo envía")
    args = parser.parse_args()

    comienzo = time.perf_counter()

    engine = create_engine(
        settings.supabase_db_url.get_secret_value(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 30},
    )

    df = leer_historico(engine)
    ultima = df["Fecha"].iloc[0]
    print(f"Supabase: {len(df)} filas. Última fecha: {ultima}")

    if ultima != str(dt.date.today()):
        print(f"⚠️ La última fila es del {ultima}, no de hoy. Se reenvía ese reporte igual.")

    parrafo = df["ai_paragraph"].iloc[0]
    if not parrafo or not str(parrafo).strip():
        raise SystemExit(
            f"❌ La fila del {ultima} no tiene ai_paragraph. Corré el notebook antes de reenviar."
        )
    print(f"Párrafo IA del {ultima}: {len(parrafo)} caracteres")

    inflacion, interanual = armar_inflacion()
    html = renderizar(df, inflacion, interanual, comienzo)
    imagenes = leer_imagenes()
    em = armar_mail(html, imagenes, args.destinatarios, args.csv)

    if args.dry_run:
        # En el temp del sistema y no en Previews/: la última celda del notebook
        # commitea y pushea todo lo que cambie en esa carpeta, así que un preview
        # dejado ahí termina en GitHub.
        salida = Path(tempfile.gettempdir()) / "reenvio_preview.html"
        salida.write_text(html, encoding="utf-8")
        print(
            f"\n[DRY-RUN] Sin enviar. Preview en {salida}\n"
            f"          Mail de {len(em.as_string()):,} bytes para: "
            f"{', '.join(args.destinatarios)}"
        )
        return

    enviar(em, args.destinatarios)
    csv_txt = "CON CSV" if args.csv else "sin CSV"
    print(f"\n🚀 Reporte del {ultima} ({csv_txt}) enviado a: {', '.join(args.destinatarios)}")


if __name__ == "__main__":
    main()
