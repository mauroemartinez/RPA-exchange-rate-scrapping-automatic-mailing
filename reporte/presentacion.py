"""Presentación ejecutiva en PowerPoint: nueve diapositivas con lo que deja la corrida del día.

1. Portada, con los links del autor y de Globalaize.
2. Tablero: blue, MEP, billete, riesgo país, BADLAR y el forward de Fisher.
3. Tipos de cambio: el análisis de IA del día y los paneles de paralelas y oficiales.
4. Riesgo país.
5. Inflación y variaciones acumuladas.
6. Bitcoin, en fondo negro.
7 y 8. Agregados monetarios y deuda, con el resumen del día y lo ideal.
9. Fuentes y contacto, como el pie del mail.

Cada gráfico lleva su frase: la de Gemini cuando la hay y, si no, un resumen
calculado acá con los datos del día. Los colores siguen el criterio del mail,
mirado desde la macro: que el dólar o el riesgo país bajen es una buena noticia
(verde) y que suban, una mala (rojo).

La arma todos los días la etapa `presentacion` de pipeline.py, con los datos y
los textos de esa misma corrida, y queda en Previews/ con un nombre fijo
(ARCHIVO), que git ignora: la etapa previews la publica sola en la rama
reporte-ejecutivo, que se reemplaza entera cada día, así GitHub tiene siempre la
del último reporte sin acumular versiones. Para rearmarla a mano desde Supabase
está scripts/presentacion_ejecutiva.py.
"""

import os
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.opc.constants import RELATIONSHIP_TYPE
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

from reporte import charts, email_report, ia_generator, indicadores, transformations
from reporte.scrapers import ambito, bcra, bna, dolarhoy, fed, finanzas, riesgo_pais

ARCHIVO = "Reporte Ejecutivo.pptx"

# Metadatos del archivo. La plantilla de python-pptx trae los de su autor
# (last_modified_by, un comentario y fechas de 2013): se reemplazan todos.
AUTOR = "Seguimiento Macroeconómico"

# Los colores del mail
OSCURO = RGBColor(0x1A, 0x25, 0x2F)
AZUL = RGBColor(0x2C, 0x3E, 0x50)
NARANJA = RGBColor(0xF3, 0x9C, 0x12)
NARANJA_TEXTO = RGBColor(0xC0, 0x56, 0x0E)  # el naranja de los títulos sobre fondo claro, legible
GRIS = RGBColor(0x5D, 0x6D, 0x7E)
CLARO = RGBColor(0xEC, 0xF0, 0xF1)
FONDO_TARJETA = RGBColor(0xEE, 0xF1, 0xF4)
VERDE = RGBColor(0x1E, 0x84, 0x49)
ROJO = RGBColor(0xC0, 0x39, 0x2B)
BLANCO = RGBColor(0xFF, 0xFF, 0xFF)
NEGRO = RGBColor(0x00, 0x00, 0x00)
CELESTE = RGBColor(0x29, 0x80, 0xB9)

ANCHO, ALTO = Inches(13.333), Inches(7.5)  # 16:9

SIN_ANALISIS = "Sin análisis para este día."

RECURSOS = Path(__file__).resolve().parent / "recursos"
ALIAS = "mauroemartinezmp"
MAIL = "martinezmauroezequiel@gmail.com"


def _icono_globalaize() -> Path:
    """El logo de Globalaize si está en recursos/; si no, el ícono provisorio."""
    logo = RECURSOS / "globalaize_logo.png"
    return logo if logo.exists() else RECURSOS / "globalaize.png"


# (ícono, rótulo, link): los mismos del cierre del mail
LINKS = [
    ("linkedin.png", "LinkedIn", "https://linkedin.com/in/mauroemartinez/"),
    ("github.png", "GitHub", "https://github.com/mauroemartinez/"),
    (None, "Globalaize", "https://www.globalaize.com"),
    ("linkedin.png", "Globalaize en LinkedIn", "https://www.linkedin.com/company/globalaize"),
]

FUENTES = [
    ("Cotizaciones oficiales", bna.WEB_BNA),
    ("Cotizaciones paralelas", dolarhoy.WEB_DOLARHOY),
    ("Dólar MEP", ambito.WEB_MEP),
    ("Euro blue", ambito.WEB_EURO),
    ("Riesgo país y feriados", riesgo_pais.API_BASE),
    ("Tasa de la FED (EFFR)", fed.API_URL),
    ("BCRA: tasas, inflación, agregados, deuda y dólar mayorista", bcra.API_BASE),
    ("Deuda bruta del Tesoro (Secretaría de Finanzas)", finanzas.PAGINA),
    ("Bitcoin (Yahoo Finance)", "https://finance.yahoo.com/quote/BTC-USD"),
]


# ── Utilidades ───────────────────────────────────────────────────────────────

def _fecha(valor) -> date:
    """La Fecha de una fila: texto 'YYYY-MM-DD' en el histórico, date en la fila recién armada."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


def _num(valor: float, decimales: int = 2) -> str:
    return indicadores.numero(valor, decimales)


def _signo(valor: float, decimales: int = 2) -> str:
    return f"{'+' if valor >= 0 else '-'}{_num(abs(valor), decimales)}"


def _texto(slide, x, y, ancho, alto, texto, tamanio=14, color=AZUL, negrita=False, alinear=PP_ALIGN.LEFT,
           link: str | None = None):
    caja = slide.shapes.add_textbox(x, y, ancho, alto)
    marco = caja.text_frame
    marco.word_wrap = True
    for i, linea in enumerate(texto.split("\n")):
        parrafo = marco.paragraphs[0] if i == 0 else marco.add_paragraph()
        parrafo.alignment = alinear
        run = parrafo.add_run()
        run.text = linea
        run.font.size = Pt(tamanio)
        run.font.bold = negrita
        run.font.color.rgb = color
    if link:
        # El link va en la caja y no en el texto: en el texto, PowerPoint lo pinta con
        # el azul del tema, que sobre fondo oscuro no se lee
        caja.click_action.hyperlink.address = link
    return caja


def _bloques(slide, x, y, ancho, alto, bloques, tamanio=13, color=AZUL, color_titulo=NARANJA_TEXTO):
    """Una caja con secciones: [(título, texto), ...]. Cada renglón del texto es un párrafo.

    Los títulos van en mayúsculas, en negrita y en naranja, como los rótulos del mail.
    """
    caja = slide.shapes.add_textbox(x, y, ancho, alto)
    marco = caja.text_frame
    marco.word_wrap = True
    primero = True
    for titulo, texto in bloques:
        if not texto:
            continue
        p = marco.paragraphs[0] if primero else marco.add_paragraph()
        if not primero:
            p.space_before = Pt(12)
        primero = False
        run = p.add_run()
        run.text = titulo.upper()
        run.font.size, run.font.bold, run.font.color.rgb = Pt(tamanio + 1), True, color_titulo
        p.space_after = Pt(4)
        for linea in texto.split("\n"):
            p = marco.add_paragraph()
            p.space_after = Pt(5)
            run = p.add_run()
            run.text = linea
            run.font.size, run.font.color.rgb = Pt(tamanio), color
    return caja


def _rectangulo(slide, x, y, ancho, alto, color, forma=1):
    rect = slide.shapes.add_shape(forma, x, y, ancho, alto)
    rect.fill.solid()
    rect.fill.fore_color.rgb = color
    rect.line.fill.background()
    rect.shadow.inherit = False
    return rect


def _opacidad(forma, opacidad: float) -> None:
    """Relleno semitransparente: python-pptx no lo expone, va directo en el XML."""
    color = forma.fill._xPr.find(qn("a:solidFill")).find(qn("a:srgbClr"))
    color.append(color.makeelement(qn("a:alpha"), {"val": str(int(opacidad * 100_000))}))


def _degrade(forma, desde: RGBColor, hasta: RGBColor, angulo: float = 0) -> None:
    forma.fill.gradient()
    forma.fill.gradient_angle = angulo
    paradas = forma.fill.gradient_stops
    paradas[0].color.rgb, paradas[1].color.rgb = desde, hasta


def _imagen(slide, ruta: Path, x, y, ancho_max, alto_max, centrar: bool = True):
    """La imagen lo más grande posible dentro de la caja, sin deformarla."""
    with Image.open(ruta) as im:
        w, h = im.size
    escala = min(ancho_max / w, alto_max / h)
    ancho, alto = int(w * escala), int(h * escala)
    if centrar:
        x, y = x + (ancho_max - ancho) // 2, y + (alto_max - alto) // 2
    return slide.shapes.add_picture(str(ruta), x, y, ancho, alto)


def _con_link(forma, url: str):
    forma.click_action.hyperlink.address = url
    return forma


def _links(slide, x, y, lado, color_rotulo=CLARO, separacion=None):
    """La fila de íconos con link (LinkedIn, GitHub, Globalaize), cada uno con su rótulo abajo."""
    separacion = separacion or Inches(1.55)
    for i, (icono, rotulo, url) in enumerate(LINKS):
        ruta = _icono_globalaize() if icono is None else RECURSOS / icono
        izquierda = x + i * separacion
        _con_link(slide.shapes.add_picture(str(ruta), izquierda + (separacion - lado) // 2 - Inches(0.35), y, lado, lado), url)
        _texto(slide, izquierda - Inches(0.35), y + lado + Inches(0.03), separacion, Inches(0.5), rotulo, 10,
               color_rotulo, alinear=PP_ALIGN.CENTER, link=url)


def _encabezado(prs, titulo: str, fecha: date, numero: int, oscuro: bool = False, icono: Path | None = None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # en blanco
    if oscuro:
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = NEGRO
    franja = _rectangulo(slide, 0, 0, ANCHO, Inches(0.9), OSCURO)
    if not oscuro:
        _degrade(franja, OSCURO, AZUL)
    _rectangulo(slide, 0, Inches(0.9), ANCHO, Inches(0.05), NARANJA)
    izquierda = Inches(0.45)
    if icono is not None:
        slide.shapes.add_picture(str(icono), Inches(0.4), Inches(0.15), Inches(0.6), Inches(0.6))
        izquierda = Inches(1.15)
    _texto(slide, izquierda, Inches(0.14), Inches(9.5), Inches(0.6), titulo, 26, BLANCO, True)
    _texto(slide, Inches(10.4), Inches(0.25), Inches(2.6), Inches(0.5), f"{fecha:%d/%m/%Y}", 16, BLANCO,
           alinear=PP_ALIGN.RIGHT)
    pie = CLARO if oscuro else GRIS
    _texto(slide, Inches(0.45), Inches(7.08), Inches(9), Inches(0.3), "Reporte Macroeconómico · Mauro E. Martinez · Globalaize",
           9, pie)
    _texto(slide, Inches(11.9), Inches(7.08), Inches(1), Inches(0.3), str(numero), 9, pie, alinear=PP_ALIGN.RIGHT)
    return slide


def _caja_ia(slide, x, y, ancho, alto, texto: str, rotulo: str = "Análisis IA del día"):
    """La caja oscura con borde naranja del párrafo de IA del mail."""
    _rectangulo(slide, x, y, ancho, alto, OSCURO)
    _rectangulo(slide, x, y, Inches(0.07), alto, NARANJA)
    tamanio = 12 if len(texto) < 650 else 11 if len(texto) < 900 else 10
    caja = _bloques(slide, x + Inches(0.2), y + Inches(0.08), ancho - Inches(0.35), alto - Inches(0.15),
                    [(f"🤖 {rotulo}", texto)], tamanio, CLARO, NARANJA)
    caja.text_frame.vertical_anchor = MSO_ANCHOR.TOP
    return caja


def _comentario(comentarios: dict, cid: str, palabra: str) -> str | None:
    """El comentario de Gemini de ese gráfico cuyo título menciona `palabra` (paralela, oficial, riesgo...)."""
    return next((texto for titulo, texto in comentarios.get(cid, []) if palabra in titulo.lower()), None)


def _variacion(hoy: float, ayer: float) -> tuple[str, RGBColor]:
    """Variación contra la rueda anterior: subir es rojo y bajar, verde (criterio macro del mail)."""
    var = (hoy / ayer - 1) * 100
    return f"{_signo(var)}% contra la rueda anterior", (ROJO if var > 0 else VERDE if var < 0 else GRIS)


def _tarjeta(slide, x, y, titulo: str, valor: str, detalle: str, color_detalle=GRIS):
    _rectangulo(slide, x, y, Inches(3.9), Inches(1.6), FONDO_TARJETA)
    _rectangulo(slide, x, y, Inches(0.07), Inches(1.6), color_detalle if color_detalle != GRIS else AZUL)
    _texto(slide, x + Inches(0.25), y + Inches(0.1), Inches(3.5), Inches(0.4), titulo.upper(), 11, GRIS, True)
    _texto(slide, x + Inches(0.25), y + Inches(0.45), Inches(3.5), Inches(0.6), valor, 28, AZUL, True)
    _texto(slide, x + Inches(0.25), y + Inches(1.1), Inches(3.5), Inches(0.4), detalle, 12, color_detalle)


# ── Frases calculadas (cuando Gemini no comenta, o no hay comentario para ese gráfico) ──

def frase_paralelas(hoy, ayer) -> str:
    def dato(nombre, col):
        return f"{nombre} $ {_num(hoy[col])} ({_signo((hoy[col] / ayer[col] - 1) * 100)}%)"
    return (f"{dato('Blue', 'TCV_Blue')}, {dato('MEP', 'TCV_MEP')}, {dato('euro blue', 'TCV_Euro')} "
            f"y solidario $ {_num(hoy['Solidario'])}, siempre a la venta y contra la rueda anterior.")


def frase_oficiales(hoy, ayer) -> str:
    def dato(nombre, col):
        return f"{nombre} $ {_num(hoy[col])} ({_signo((hoy[col] / ayer[col] - 1) * 100)}%)"
    return (f"{dato('Billete BNA', 'TCV_Billete')} y {dato('divisas', 'TCV_Divisas')}, a la venta y contra la "
            "rueda anterior. El billete es el que compra la gente en el banco; divisas, el de las empresas.")


def frase_riesgo(df) -> str:
    ultimos = df["riesgo_pais"].head(charts.COTIZACIONES_A_MOSTRAR)
    hoy, ayer = df["riesgo_pais"].iloc[0], df["riesgo_pais"].iloc[1]
    return (f"{_num(hoy, 0)} puntos, {_signo(hoy - ayer, 0)} contra la rueda anterior. En las últimas "
            f"{len(ultimos)} ruedas estuvo entre {_num(ultimos.min(), 0)} y {_num(ultimos.max(), 0)}.\n"
            "Es lo que paga Argentina por encima de los bonos de Estados Unidos: cuanto más bajo, más barato le sale "
            "el crédito al país y a sus empresas.")


def frase_inflacion(inflacion: pd.DataFrame | None, df) -> str | None:
    """La última inflación mensual e interanual, y lo acumulado desde el inicio del gráfico de variaciones."""
    if inflacion is None or inflacion.empty:
        return None
    serie = inflacion.dropna(subset=["Inflación Mensual"])
    ultimo, previo = serie.iloc[-1], serie.iloc[-2] if len(serie) > 1 else None
    texto = f"La inflación de {indicadores.mes_y_anio(ultimo['Fecha'])} fue {_num(ultimo['Inflación Mensual'], 1)}%"
    if previo is not None:
        texto += f" ({indicadores.MESES[previo['Fecha'].month - 1]}: {_num(previo['Inflación Mensual'], 1)}%)"
    if pd.notna(ultimo.get("Inflación Anual")):
        texto += f" y la de los últimos 12 meses, {_num(ultimo['Inflación Anual'], 1)}%"
    texto += "."

    inicio = pd.Timestamp(charts.FECHA_INICIO_VARIACIONES)
    precios = ((serie[serie["Fecha"] >= inicio]["Inflación Mensual"] / 100 + 1).prod() - 1) * 100
    cotizaciones = df[["Fecha", "TCV_Blue", "Solidario"]].assign(Fecha=lambda d: pd.to_datetime(d["Fecha"].astype(str).str[:10]))
    antes = cotizaciones[cotizaciones["Fecha"] < inicio]
    if not antes.empty:
        base, hoy = antes.iloc[0], cotizaciones.iloc[0]
        blue = (hoy["TCV_Blue"] / base["TCV_Blue"] - 1) * 100
        solidario = (hoy["Solidario"] / base["Solidario"] - 1) * 100
        texto += (f"\nDesde {indicadores.mes_y_anio(inicio)}, los precios subieron {_num(precios, 1)}%, el dólar blue "
                  f"{_signo(blue, 1)}% y el solidario {_signo(solidario, 1)}%: el dólar "
                  f"{'subió menos que los precios, así que en pesos de hoy está más barato' if blue < precios else 'subió más que los precios, así que en pesos de hoy está más caro'}.")
    return texto


def frase_btc(btc: pd.DataFrame | None) -> str | None:
    if btc is None or btc.empty or "Close" not in btc:
        return None
    cierre = btc["Close"].dropna()
    if len(cierre) < 2:
        return None
    ultimo, fecha = float(cierre.iloc[-1]), cierre.index[-1]

    def cambio(dias: int) -> str | None:
        previos = cierre[cierre.index <= fecha - pd.Timedelta(days=dias)]
        if previos.empty and (fecha - cierre.index[0]).days >= dias - 10:
            previos = cierre.iloc[:1]  # la serie viene recortada a un año justo: su primer dato
        return None if previos.empty else f"{_signo((ultimo / float(previos.iloc[-1]) - 1) * 100, 1)}%"

    partes = [f"en {t} {c}" for t, c in (("7 días", cambio(7)), ("30 días", cambio(30)), ("el último año", cambio(365))) if c]
    texto = f"Bitcoin cerró en USD {_num(ultimo, 0)} el {fecha:%d/%m/%Y}"
    texto += (": " + ", ".join(partes) + ".") if partes else "."
    if "Volatility" in btc and pd.notna(btc["Volatility"].iloc[-1]):
        texto += f"\nVolatilidad diaria de las últimas 20 ruedas: {_num(float(btc['Volatility'].iloc[-1]), 1)}%."
    return texto


# ── Archivo ──────────────────────────────────────────────────────────────────

def _metadatos(prs, fecha: date) -> None:
    propiedades = prs.core_properties
    propiedades.title = f"Reporte Macroeconómico {fecha:%d/%m/%Y}"
    propiedades.author = AUTOR
    propiedades.last_modified_by = AUTOR
    propiedades.comments = ""
    propiedades.revision = 1
    # python-pptx escribe estas fechas como UTC
    ahora = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    propiedades.created = ahora
    propiedades.modified = ahora


def _propiedades_de_aplicacion(prs) -> None:
    """docProps/app.xml con los datos de este archivo.

    La plantilla de python-pptx trae los de la PowerPoint en que se armó (Microsoft
    Macintosh PowerPoint 14, presentación 4:3, cero diapositivas). python-pptx no
    tiene API para esta parte, así que se reescribe entera; es un XML de propiedades
    opcionales y PowerPoint lo acepta así de corto.
    """
    parte = prs.part.package.part_related_by(RELATIONSHIP_TYPE.EXTENDED_PROPERTIES)
    parte._blob = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        f"<Application>{AUTOR}</Application>"
        "<PresentationFormat>16:9</PresentationFormat>"
        f"<Slides>{len(prs.slides)}</Slides>"
        "</Properties>"
    ).encode()




def armar(
    df, imagenes: dict[str, Path], salida: Path, parrafo: str | None = None, comentarios: dict | None = None,
    explicaciones: dict | None = None, inflacion: pd.DataFrame | None = None, btc: pd.DataFrame | None = None,
) -> Path:
    """Arma la presentación en `salida`/ARCHIVO y devuelve su ruta.

    `df` es Fact_Mercado_Macro más nuevo primero (la fila 0 es el día del reporte),
    como lo devuelve data_access.leer_historico o como lo arma el pipeline.
    `imagenes` son los gráficos disponibles por nombre (charts.ORDEN_EN_MAIL); el que
    falte sale como "Gráfico no disponible".

    `parrafo` y `comentarios` son los textos de IA de esta corrida: el pipeline los
    pasa en memoria porque todavía no están en `df`. Sin ellos se leen de la fila 0
    (ai_paragraph y ai_secciones), que es lo que hace el script manual. `comentarios`
    tiene la forma de ia_generator.comentarios_por_grafico; {} significa "sin comentarios".
    `explicaciones` son las de indicadores.explicaciones; sin ellas, las diapositivas
    de agregados y deuda llevan solo lo ideal, sin el resumen con los últimos datos.
    `inflacion` (transformations.serie_inflacion) y `btc` (charts.preparar_btc) son
    para las frases de esos dos gráficos; sin ellos, esas diapositivas van sin frase.
    """
    hoy, ayer = df.iloc[0], df.iloc[1]
    fecha = _fecha(hoy["Fecha"])
    fwd_oficial, fwd_blue = transformations.forwards_fisher(df)
    resumen = email_report.resumen_ejecutivo(transformations.agregar_brechas_y_variaciones(df))
    if comentarios is None:
        comentarios = ia_generator.comentarios_por_grafico(hoy.get("ai_secciones"))
    if parrafo is None:
        guardado = hoy.get("ai_paragraph")
        parrafo = guardado if isinstance(guardado, str) and guardado else SIN_ANALISIS
    if explicaciones is None:
        explicaciones = indicadores.explicaciones({})

    prs = Presentation()
    prs.slide_width, prs.slide_height = ANCHO, ALTO
    _metadatos(prs, fecha)
    numero = iter(range(2, 100))  # la portada es la 1 y no lleva número

    # 1. Portada
    portada = prs.slides.add_slide(prs.slide_layouts[6])
    _degrade(_rectangulo(portada, 0, 0, ANCHO, ALTO, OSCURO), RGBColor(0x0B, 0x11, 0x18), AZUL, 315)
    for x, y, lado, color, opacidad in [
        (8.4, -1.6, 6.4, CELESTE, 0.16), (10.6, 3.9, 3.6, NARANJA, 0.18), (7.3, 4.6, 2.2, CELESTE, 0.10),
    ]:
        _opacidad(_rectangulo(portada, Inches(x), Inches(y), Inches(lado), Inches(lado), color, forma=9), opacidad)
    portada.shapes.add_picture(str(RECURSOS / "bitcoin.png"), Inches(10.55), Inches(1.45), Inches(1.7), Inches(1.7))
    _rectangulo(portada, Inches(0.8), Inches(1.95), Inches(0.12), Inches(2.45), NARANJA)
    _texto(portada, Inches(1.15), Inches(1.45), Inches(9), Inches(0.5), "ARGENTINA · INFORME DIARIO", 15, NARANJA, True)
    _texto(portada, Inches(1.15), Inches(1.9), Inches(9.5), Inches(1.1), "Reporte Macroeconómico", 54, BLANCO, True)
    _texto(portada, Inches(1.15), Inches(3.05), Inches(9.2), Inches(0.9),
           "Dólar · Riesgo país · Tasas · Inflación · Bitcoin · Agregados monetarios · Deuda", 20, CLARO)
    _texto(portada, Inches(1.15), Inches(3.75), Inches(6), Inches(0.6), f"{fecha:%d/%m/%Y}", 26, NARANJA, True)
    _texto(portada, Inches(1.15), Inches(5.0), Inches(9), Inches(0.4), "por Mauro E. Martinez · Globalaize", 14, CLARO)
    _links(portada, Inches(1.15), Inches(5.55), Inches(0.62))

    # 2. Tablero
    tablero = _encabezado(prs, "Tablero del día", fecha, next(numero))
    tarjetas = [
        ("Dólar blue", f"$ {_num(hoy['TCV_Blue'])}", *_variacion(hoy["TCV_Blue"], ayer["TCV_Blue"])),
        ("Dólar MEP", f"$ {_num(hoy['TCV_MEP'])}", *_variacion(hoy["TCV_MEP"], ayer["TCV_MEP"])),
        ("Billete BNA", f"$ {_num(hoy['TCV_Billete'])}", *_variacion(hoy["TCV_Billete"], ayer["TCV_Billete"])),
        ("Riesgo país", f"{_num(hoy['riesgo_pais'], 0)} pts",
         f"{_signo(hoy['riesgo_pais'] - ayer['riesgo_pais'], 0)} pts contra la rueda anterior",
         ROJO if hoy["riesgo_pais"] > ayer["riesgo_pais"] else VERDE if hoy["riesgo_pais"] < ayer["riesgo_pais"] else GRIS),
        ("BADLAR (TEA)", f"{_num(hoy['bcra_tea'])}%", f"FED (EFFR): {_num(hoy['fed_tea'])}%", GRIS),
        ("Forward oficial 3 meses", f"$ {_num(fwd_oficial)}", f"Forward blue: $ {_num(fwd_blue)}", GRIS),
    ]
    for i, (titulo, valor, detalle, color) in enumerate(tarjetas):
        _tarjeta(tablero, Inches(0.45 + (i % 3) * 4.2), Inches(1.4 + (i // 3) * 2.0), titulo, valor, detalle, color)
    diferencia = abs(resumen["ahorro_valor"])
    sentido = "más barato" if resumen["ahorro_valor"] > 0 else "más caro"
    _texto(tablero, Inches(0.45), Inches(5.6), Inches(12.4), Inches(1.0),
           f"Comprar USD {resumen['cantidad_usd']} al oficial con impuestos (solidario) sale $ {_num(diferencia)} "
           f"{sentido} que en el blue: el solidario está {_num(abs(resumen['brecha_solidario']))}% "
           f"{'por debajo' if resumen['brecha_solidario'] > 0 else 'por encima'} del blue.\n"
           "Verde: bajó contra la rueda anterior; rojo: subió. Desde la macro, que el dólar y el riesgo país bajen "
           "es la buena noticia.", 13, GRIS)

    # 3 y 4. Tipos de cambio y riesgo país, con los paneles por separado
    paneles = []
    with tempfile.TemporaryDirectory() as temporal:
        if charts.TIPOS_DE_CAMBIO in imagenes:
            try:
                paneles = charts.paneles_tipos_de_cambio(charts.preparar_datos(df), Path(temporal))
            except Exception:
                paneles = []  # sin paneles, va el gráfico entero como en el mail

        cambio = _encabezado(prs, "Tipos de cambio", fecha, next(numero))
        _caja_ia(cambio, Inches(0.45), Inches(1.12), Inches(12.43), Inches(1.6), parrafo)
        cambio.notes_slide.notes_text_frame.text = parrafo
        if paneles:
            for j, (ruta, clave, frase) in enumerate([
                (paneles[0], "paralela", frase_paralelas(hoy, ayer)),
                (paneles[1], "oficial", frase_oficiales(hoy, ayer)),
            ]):
                x = Inches(0.45) + j * Inches(6.33)
                _imagen(cambio, ruta, x, Inches(2.85), Inches(6.1), Inches(2.75))
                texto = _comentario(comentarios, "image1", clave)
                _bloques(cambio, x, Inches(5.65), Inches(6.1), Inches(1.4),
                         [("🤖 Análisis IA" if texto else "Resumen del día", texto or frase)], 11)
        elif charts.TIPOS_DE_CAMBIO in imagenes:
            _imagen(cambio, imagenes[charts.TIPOS_DE_CAMBIO], Inches(0.45), Inches(2.85), Inches(12.43), Inches(4.1))
        else:
            _texto(cambio, Inches(0.6), Inches(4), Inches(12), Inches(1), "Gráfico no disponible para este día.", 18, GRIS)

        riesgo = _encabezado(prs, "Riesgo país", fecha, next(numero))
        if paneles:
            _imagen(riesgo, paneles[2], Inches(0.45), Inches(1.25), Inches(8.5), Inches(5.6))
        else:
            _texto(riesgo, Inches(0.6), Inches(3), Inches(8), Inches(1), "Gráfico no disponible para este día.", 18, GRIS)
        _bloques(riesgo, Inches(9.25), Inches(1.3), Inches(3.65), Inches(5.6),
                 [("Resumen del día", frase_riesgo(df)), ("🤖 Análisis IA", _comentario(comentarios, "image1", "riesgo"))], 13)

    # 5. Inflación
    inflacion_slide = _encabezado(prs, "Inflación y variaciones acumuladas", fecha, next(numero))
    for j, nombre in enumerate([charts.INFLACION, charts.VARIACIONES]):
        x = Inches(0.45) + j * Inches(6.33)
        if nombre in imagenes:
            _imagen(inflacion_slide, imagenes[nombre], x, Inches(1.15), Inches(6.1), Inches(4.3))
        else:
            _texto(inflacion_slide, x, Inches(3), Inches(6), Inches(1), "Gráfico no disponible para este día.", 18, GRIS)
    frase = frase_inflacion(inflacion, df)
    if frase:
        _bloques(inflacion_slide, Inches(0.45), Inches(5.6), Inches(12.43), Inches(1.45), [("Resumen del día", frase)], 13)

    # 6. Bitcoin, en negro como su gráfico
    bitcoin = _encabezado(prs, "Bitcoin", fecha, next(numero), oscuro=True, icono=RECURSOS / "bitcoin.png")
    if charts.BTC in imagenes:
        _imagen(bitcoin, imagenes[charts.BTC], Inches(0.45), Inches(1.15), Inches(8.5), Inches(5.8))
    else:
        _texto(bitcoin, Inches(0.6), Inches(3), Inches(8), Inches(1), "Gráfico no disponible para este día.", 18, CLARO)
    _bloques(bitcoin, Inches(9.25), Inches(1.3), Inches(3.65), Inches(5.6),
             [("Resumen del día", frase_btc(btc)), ("🤖 Análisis IA", _comentario(comentarios, "image4", "bitcoin"))], 13, CLARO, NARANJA)

    # 7 y 8. Agregados y deuda: el resumen del día y lo ideal; el texto completo, en las notas
    for titulo, nombre, cid in [("Agregados monetarios", charts.AGREGADOS, indicadores.CID_AGREGADOS),
                                ("Endeudamiento, en dólares", charts.DEUDA, indicadores.CID_DEUDA)]:
        slide = _encabezado(prs, titulo, fecha, next(numero))
        if nombre in imagenes:
            _imagen(slide, imagenes[nombre], Inches(0.45), Inches(1.1), Inches(7.4), Inches(5.9))
        else:
            _texto(slide, Inches(0.6), Inches(3), Inches(7), Inches(1), "Gráfico no disponible para este día.", 18, GRIS)
        explicacion = explicaciones.get(cid)
        if explicacion:
            parrafos = explicacion["texto"].split("\n")
            ideal = parrafos[-1].removeprefix("¿Qué sería lo ideal?").strip()
            _bloques(slide, Inches(8.1), Inches(1.2), Inches(4.8), Inches(5.8),
                     [("Resumen del día", explicacion["dato"]), ("¿Qué sería lo ideal?", ideal)], 12)
            slide.notes_slide.notes_text_frame.text = "\n\n".join(filter(None, [*parrafos, explicacion["dato"]]))

    # 9. Fuentes y contacto
    cierre = _encabezado(prs, "Fuentes y contacto", fecha, next(numero))
    _texto(cierre, Inches(0.45), Inches(1.2), Inches(7.5), Inches(0.4), "FUENTES CONSULTADAS", 14, NARANJA_TEXTO, True)
    caja = cierre.shapes.add_textbox(Inches(0.45), Inches(1.65), Inches(7.6), Inches(5.3))
    marco = caja.text_frame
    marco.word_wrap = True
    for i, (nombre, url) in enumerate(FUENTES):
        p = marco.paragraphs[0] if i == 0 else marco.add_paragraph()
        p.space_after = Pt(6)
        run = p.add_run()
        run.text = f"{nombre}: "
        run.font.size, run.font.bold, run.font.color.rgb = Pt(12), True, AZUL
        run = p.add_run()
        run.text = url
        run.hyperlink.address = url
        run.font.size, run.font.color.rgb = Pt(11), CELESTE
    _rectangulo(cierre, Inches(8.45), Inches(1.2), Inches(4.43), Inches(5.7), OSCURO)
    _texto(cierre, Inches(8.75), Inches(1.4), Inches(4), Inches(0.4), "CONTACTO", 14, NARANJA, True)
    _texto(cierre, Inches(8.75), Inches(1.85), Inches(4), Inches(0.9),
           "Reporte hecho íntegramente en Python por Mauro E. Martinez, de Globalaize (sitio en construcción).", 12, CLARO)
    _links(cierre, Inches(8.85), Inches(3.0), Inches(0.5), separacion=Inches(1.0))
    _texto(cierre, Inches(8.75), Inches(4.45), Inches(4), Inches(0.8),
           f"☕ ¿Te sirvió el reporte? Podés apoyar el proyecto al alias {ALIAS}", 13, BLANCO, True)
    _texto(cierre, Inches(8.75), Inches(5.4), Inches(4), Inches(0.9),
           f"📧 Consultas, desuscripciones o propuestas:\n{MAIL}", 12, CLARO, link=f"mailto:{MAIL}")
    _texto(cierre, Inches(0.45), Inches(6.7), Inches(7.6), Inches(0.35),
           "Análisis generado con Gemini a partir de los datos del día. No es asesoramiento financiero.", 10, GRIS)

    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    _propiedades_de_aplicacion(prs)
    ruta = salida / ARCHIVO
    # Primero a un temporal y después se reemplaza: si el guardado falla a mitad de
    # camino, queda entera la versión anterior y no un archivo roto. El temporal
    # termina en .pptx, así que git lo ignora igual que al definitivo.
    temporal = ruta.with_name(f"~tmp {ARCHIVO}")
    try:
        prs.save(temporal)
        os.replace(temporal, ruta)
    finally:
        temporal.unlink(missing_ok=True)
    return ruta
