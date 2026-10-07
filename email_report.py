"""Armado y envío del mail del reporte (celdas 45 a 47 del notebook).

Lo usan el pipeline diario y scripts/reenvio_manual.py, así el mail sale igual por
los dos caminos. Antes el script tenía su propia copia de estos cálculos y se había
desincronizado: mostraba la tabla de inflación invertida y la interanual de hace
doce meses.

A diferencia de la celda 47, un envío fallido no se imprime y se olvida: enviar()
levanta, y enviar_reporte_diario() devuelve el error de cada variante para que el
pipeline ponga la corrida en rojo. Un 535 de Gmail no puede pasar como éxito.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader
from tabulate import tabulate

import mailer
from charts import COTIZACIONES_A_MOSTRAR, ORDEN_EN_MAIL
from config import settings
from models import COLUMNAS_FILA
from scrapers import ambito, bcra, bna, dolarhoy, fed, riesgo_pais
from transformations import etiqueta_mes

log = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent

# Cupo de dólares del resumen ejecutivo (costo blue contra oficial)
CANTIDAD_USD = 100

ENCABEZADOS_COTIZACIONES = [
    "Fecha", "tccblue", "tcvblue", "tccBillete", "tcvBillete", "tccDivisas", "tcvDivisas",
    "Solidario", "MEP", "RiesgoPaís", "tccEuros", "tcvEuros", "FEDtea", "BCRAtea",
]
COLUMNAS_VARIACIONES = [
    "Fecha", "Solidario / TCV Blue", "TCV MEP / TCV Blue", "TCV Euro / TCC Blue %",
    "Variación Solidario", "Variación TCV Blue", "Variación TCV Euro",
]
NOMBRE_ADJUNTO_CSV = "Seguimiento Macroeconómico"


def pintar_variacion(valor):
    """Verde si sube, rojo si baja. #1e8449 y no #27ae60: el segundo da 2.87:1 sobre
    blanco y no llega al 4.5:1 que pide WCAG AA. Es el mismo verde del gráfico de
    riesgo país."""
    try:
        val_num = float(valor)
        color = "#1e8449" if val_num > 0 else "#c0392b"
        return f'<span style="color: {color}; font-weight: bold;">{val_num:.2%}</span>'
    except (TypeError, ValueError):
        return valor


def preparar_df_mail(df: pd.DataFrame) -> pd.DataFrame:
    """TEA como porcentaje en texto y Fecha 'dd/mm/yy' (celdas 46 y 47).

    Recibe el DataFrame con brechas y variaciones y devuelve una copia: las TEA
    numéricas siguen haciendo falta para los forwards de Fisher, que van antes.
    """
    df = df.copy()
    df["fed_tea"] = df["fed_tea"].apply(lambda x: f"{x/100:.2%}" if pd.notnull(x) else "")
    df["bcra_tea"] = df["bcra_tea"].apply(lambda x: f"{x/100:.2%}" if pd.notnull(x) else "")
    df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.strftime("%d/%m/%y")
    return df


def tabla_cotizaciones(df_mail: pd.DataFrame) -> str:
    """Las primeras 14 columnas: depende del orden de columnas que viene de Supabase."""
    return tabulate(
        df_mail.iloc[:COTIZACIONES_A_MOSTRAR, :14].values.tolist(),
        headers=ENCABEZADOS_COTIZACIONES,
        tablefmt="html",
        numalign="center",
        floatfmt=".2f",
    )


def tabla_variaciones(df_mail: pd.DataFrame) -> str:
    """Brechas y variaciones; las tres últimas columnas van pintadas."""
    filas = []
    for fila in df_mail[COLUMNAS_VARIACIONES].iloc[:COTIZACIONES_A_MOSTRAR].values.tolist():
        fila_nueva = list(fila)
        fila_nueva[-3:] = [pintar_variacion(v) for v in fila[-3:]]
        filas.append(fila_nueva)

    return tabulate(
        filas, headers=COLUMNAS_VARIACIONES, tablefmt="unsafehtml", numalign="center", floatfmt=".2%"
    )


def tabla_inflacion(inflacion_12: pd.DataFrame) -> tuple[str, str]:
    """(tabla HTML, interanual). Los meses de más viejo a más nuevo, como en el gráfico.

    La interanual es la del mes más reciente y se toma antes de pasar las columnas
    a proporción (celda 45).
    """
    inflacion = inflacion_12.copy()
    interanual = f"{inflacion['Inflación Anual'].iloc[-1]:,.2f}%"

    inflacion["Fecha"] = [etiqueta_mes(f) for f in inflacion["Fecha"]]
    cols_pct = ["Inflación Mensual", "Inflación Bimestral", "Inflación Trimestral", "Inflación Anual"]
    inflacion[cols_pct] = inflacion[cols_pct] / 100

    tabla = tabulate(
        inflacion[["Fecha", "Inflación Mensual", "Inflación Bimestral", "Inflación Trimestral"]].values.tolist(),
        headers=["Fecha", "I. Mensual", "I. Bimestral", "I. Trimestral"],
        tablefmt="html",
        numalign="center",
        floatfmt=".2%",
    )
    return tabla, interanual


def resumen_ejecutivo(df: pd.DataFrame) -> dict:
    """Costo blue contra oficial, variaciones del día y riesgo país (celda 47)."""
    costo_blue = float(df["TCV_Blue"].iloc[0] * CANTIDAD_USD)
    costo_oficial = float(df["Solidario"].iloc[0] * CANTIDAD_USD)
    ahorro_valor = costo_blue - costo_oficial
    riesgo_pts = float(df["riesgo_pais"].iloc[0])
    return {
        "cantidad_usd": CANTIDAD_USD,
        "costo_blue": costo_blue,
        "costo_oficial": costo_oficial,
        "ahorro_valor": ahorro_valor,
        "color_ahorro": "#1e8449" if ahorro_valor > 0 else "#c0392b",
        "label_ahorro": "Ahorro estimado" if ahorro_valor > 0 else "Sobrecosto estimado",
        "var_blue": float((df["TCV_Blue"].iloc[0] / df["TCV_Blue"].iloc[1] - 1) * 100),
        "brecha_solidario": float((1 - df["Solidario"].iloc[0] / df["TCV_Blue"].iloc[0]) * 100),
        "var_divisas": float((df["TCV_Divisas"].iloc[0] / df["TCV_Divisas"].iloc[1] - 1) * 100),
        "var_euro": float((df["TCV_Euro"].iloc[0] / df["TCV_Euro"].iloc[1] - 1) * 100),
        "brecha_euro_blue": float((1 - df["TCV_Blue"].iloc[0] / df["TCV_Euro"].iloc[0]) * 100),
        "riesgo_pts": riesgo_pts,
        "sobretasa": riesgo_pts / 100,
    }


def cids_disponibles(imagenes: dict[str, bytes]) -> list[str]:
    """'image1'..'image4' de los gráficos que efectivamente están, en orden fijo."""
    return [f"image{i + 1}" for i, nombre in enumerate(ORDEN_EN_MAIL) if nombre in imagenes]


def template():
    return Environment(loader=FileSystemLoader(RAIZ / "templates")).get_template("report_email.html")


def renderizar(
    df: pd.DataFrame,
    inflacion_12: pd.DataFrame,
    fwd_oficial: float,
    fwd_blue: float,
    parrafo_ia: str,
    performance_segundos: float,
    graficos: list[str] | None = None,
    comentarios: dict[str, list[tuple[str, str]]] | None = None,
) -> str:
    """El HTML del reporte desde templates/report_email.html.

    `df` es el histórico con brechas y variaciones, todavía con las TEA numéricas.
    `graficos` son los cid presentes; si falta uno (por ejemplo, Yahoo no respondió
    y no hay gráfico de BTC) el template no deja la imagen rota. `comentarios` son
    los textos de Gemini por gráfico ({cid: [(título, texto)]}); sin ellos, el
    mail sale exactamente como antes de la fase 4.
    """
    contexto = contexto_template(
        df, inflacion_12, fwd_oficial, fwd_blue, parrafo_ia, performance_segundos, graficos, comentarios
    )
    return template().render(**contexto)


def contexto_template(
    df: pd.DataFrame,
    inflacion_12: pd.DataFrame,
    fwd_oficial: float,
    fwd_blue: float,
    parrafo_ia: str,
    performance_segundos: float,
    graficos: list[str] | None = None,
    comentarios: dict[str, list[tuple[str, str]]] | None = None,
) -> dict:
    """Las variables que recibe el template (celda 47)."""
    df_mail = preparar_df_mail(df)
    tabla_infl, interanual = tabla_inflacion(inflacion_12)
    return dict(
        **resumen_ejecutivo(df_mail),
        fwd_oficial=fwd_oficial,
        fwd_blue=fwd_blue,
        parrafo_ia=parrafo_ia,
        cotizaciones_a_mostrar=COTIZACIONES_A_MOSTRAR,
        tabla_cotizaciones=tabla_cotizaciones(df_mail),
        tabla_variaciones=tabla_variaciones(df_mail),
        tabla_inflacion=tabla_infl,
        inflacion_interanual=interanual,
        web_bna=bna.WEB_BNA,
        web_dolarhoy=dolarhoy.WEB_DOLARHOY,
        web_mep=ambito.WEB_MEP,
        api_riesgo_pais=riesgo_pais.API_BASE,
        web_euro=ambito.WEB_EURO,
        fed_api_url=fed.API_URL,
        bcra_api_url=bcra.API_BASE,
        performance_segundos=performance_segundos,
        graficos=graficos if graficos is not None else [f"image{i + 1}" for i in range(len(ORDEN_EN_MAIL))],
        comentarios=comentarios or {},
    )


def asunto(fecha: date) -> str:
    return f"📈 Reporte Macroeconómico - {fecha:%d-%m-%Y}"


def armar_mensaje(
    html: str,
    imagenes: dict[str, bytes],
    asunto_mail: str,
    para: str,
    cco: list[str] | None = None,
    csv: str | None = None,
) -> MIMEMultipart:
    """El MIME completo: HTML, gráficos inline (cid:imageN) y el CSV opcional."""
    em = MIMEMultipart("related")
    em["From"] = settings.email_sender
    em["To"] = para
    if cco:
        em["Bcc"] = ", ".join(cco)
    em["Subject"] = asunto_mail
    em.attach(MIMEText(html, "html"))

    for i, nombre in enumerate(ORDEN_EN_MAIL):
        if nombre not in imagenes:
            continue
        img = MIMEImage(imagenes[nombre])
        img.add_header("Content-ID", f"<image{i + 1}>")
        img.add_header("Content-Disposition", "inline", filename=nombre)
        em.attach(img)

    if csv is not None:
        adjunto = MIMEText(csv, "csv")
        adjunto.add_header("Content-Disposition", "attachment", filename=NOMBRE_ADJUNTO_CSV)
        em.attach(adjunto)

    return em


def enviar(mensaje: MIMEMultipart, destinatarios: list[str]) -> None:
    """Un sendmail por Gmail. Levanta ante cualquier fallo, incluidos los rechazos parciales."""
    mailer.enviar_smtp(mensaje, destinatarios)


def csv_historico(df: pd.DataFrame) -> str:
    """El histórico completo como CSV, para la variante del mail con adjunto.

    Se arma en el momento desde los datos de Supabase, más nuevo primero y con las
    mismas columnas que tenía el archivo de RUTA_BBDD. La celda 47 adjuntaba ese
    archivo tal cual, pero nadie lo actualizaba desde junio de 2026: los
    destinatarios recibían una foto vieja, con los párrafos de IA mal decodificados
    (se leía en latin-1 un archivo con texto UTF-8), y en el contenedor ni siquiera
    existía. `df` es el histórico sin las columnas calculadas, con la fila del día.
    """
    columnas = [*COLUMNAS_FILA, "ai_paragraph"]
    salida = df.reindex(columns=columnas).copy()
    salida["Fecha"] = pd.to_datetime(salida["Fecha"]).dt.strftime("%Y-%m-%d")
    salida["ai_paragraph"] = salida["ai_paragraph"].map(_sin_formula)
    return salida.to_csv(index=False, lineterminator="\n")


def _sin_formula(valor):
    """Un texto que empieza con =, +, - o @ se antepone con ' para que Excel no lo ejecute."""
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + valor
    return valor


def enviar_reporte_diario(
    html: str,
    imagenes: dict[str, bytes],
    fecha: date,
    csv: str | None,
    receptores: list[str] | None = None,
    receptores_csv: list[str] | None = None,
    enviar_fn=enviar,
) -> dict[str, str | None]:
    """Las dos variantes del mail diario en paralelo. Devuelve el error de cada una.

    'sin_csv' va a EMAIL_RECEIVER y 'con_csv' a EMAIL_RECEIVER_CSV, todos en Cco y
    con el remitente en Para, igual que la celda 47. Un valor None es un envío OK.
    No se reintenta: si un envío falló después de entregarse a medias, reintentar
    duplicaría el mail a los que sí lo recibieron.
    """
    receptores = list(settings.email_receiver) if receptores is None else receptores
    receptores_csv = list(settings.email_receiver_csv) if receptores_csv is None else receptores_csv
    titulo = asunto(fecha)
    remitente = settings.email_sender

    variantes = {"sin_csv": (receptores, None), "con_csv": (receptores_csv, csv)}

    def _enviar(nombre: str) -> str | None:
        destinatarios, adjunto = variantes[nombre]
        if not destinatarios:
            log.info("Mail %s: sin destinatarios, se omite", nombre)
            return None
        mensaje = armar_mensaje(html, imagenes, titulo, para=remitente, cco=destinatarios, csv=adjunto)
        try:
            # El remitente va también en el sobre para que le llegue la copia del Para
            enviar_fn(mensaje, destinatarios + [remitente])
        except Exception as exc:
            log.error("Mail %s: falló el envío a %d destinatarios: %s: %s", nombre, len(destinatarios), type(exc).__name__, exc)
            return f"{type(exc).__name__}: {exc}"
        log.info("Mail %s: enviado a %d destinatarios", nombre, len(destinatarios))
        return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = dict(zip(variantes, pool.map(_enviar, variantes)))
    return resultados
