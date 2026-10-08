"""Presentación ejecutiva en PowerPoint: ocho diapositivas con lo que deja la corrida del día.

Portada; un tablero con blue, MEP, billete, riesgo país, BADLAR y el forward de
Fisher, cada uno con su variación; el análisis de IA; tres diapositivas de
gráficos (tipos de cambio y riesgo país, inflación con variaciones acumuladas,
BTC), con sus comentarios por gráfico cuando los hay; y las de agregados
monetarios y deuda, con la misma explicación para no especialistas que el mail.
Usa los colores del mail.

La arma todos los días la etapa `presentacion` de pipeline.py, con los datos y
los textos de esa misma corrida, y queda en Previews/ con un nombre fijo
(ARCHIVO), que git ignora: la etapa previews la publica sola en la rama
reporte-ejecutivo, que se reemplaza entera cada día, así GitHub tiene siempre la
del último reporte sin acumular versiones. Para rearmarla a mano desde Supabase
está scripts/presentacion_ejecutiva.py.
"""

import os
from datetime import UTC, date, datetime
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.opc.constants import RELATIONSHIP_TYPE
from pptx.util import Inches, Pt

from reporte import charts, email_report, ia_generator, indicadores, transformations

ARCHIVO = "Reporte Ejecutivo.pptx"

# Metadatos del archivo. La plantilla de python-pptx trae los de su autor
# (last_modified_by, un comentario y fechas de 2013): se reemplazan todos.
AUTOR = "Seguimiento Macroeconómico"

# Los colores del mail
AZUL = RGBColor(0x2C, 0x3E, 0x50)
NARANJA = RGBColor(0xF3, 0x9C, 0x12)
GRIS = RGBColor(0x7F, 0x8C, 0x8D)
VERDE = RGBColor(0x1E, 0x84, 0x49)
ROJO = RGBColor(0xC0, 0x39, 0x2B)
BLANCO = RGBColor(0xFF, 0xFF, 0xFF)

ANCHO, ALTO = Inches(13.333), Inches(7.5)  # 16:9

SIN_ANALISIS = "Sin análisis para este día."


def _fecha(valor) -> date:
    """La Fecha de una fila: texto 'YYYY-MM-DD' en el histórico, date en la fila recién armada."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


def _texto(slide, x, y, ancho, alto, texto, tamanio=14, color=AZUL, negrita=False, alinear=PP_ALIGN.LEFT):
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
    return caja


def _encabezado(prs, titulo: str, fecha: date):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # en blanco
    franja = slide.shapes.add_shape(1, 0, 0, ANCHO, Inches(0.9))  # 1 = rectángulo
    franja.fill.solid()
    franja.fill.fore_color.rgb = AZUL
    franja.line.fill.background()
    _texto(slide, Inches(0.4), Inches(0.15), Inches(10), Inches(0.6), titulo, 26, BLANCO, True)
    _texto(slide, Inches(10.4), Inches(0.25), Inches(2.6), Inches(0.5), f"{fecha:%d/%m/%Y}", 16, BLANCO,
           alinear=PP_ALIGN.RIGHT)
    return slide


def _tarjeta(slide, x, y, titulo: str, valor: str, detalle: str, color_detalle=GRIS):
    fondo = slide.shapes.add_shape(1, x, y, Inches(3.9), Inches(1.6))
    fondo.fill.solid()
    fondo.fill.fore_color.rgb = RGBColor(0xEE, 0xF1, 0xF4)
    fondo.line.color.rgb = RGBColor(0xDF, 0xE4, 0xEA)
    _texto(slide, x + Inches(0.2), y + Inches(0.1), Inches(3.5), Inches(0.4), titulo.upper(), 11, GRIS, True)
    _texto(slide, x + Inches(0.2), y + Inches(0.45), Inches(3.5), Inches(0.6), valor, 28, AZUL, True)
    _texto(slide, x + Inches(0.2), y + Inches(1.1), Inches(3.5), Inches(0.4), detalle, 12, color_detalle)


def _variacion(hoy: float, ayer: float) -> tuple[str, RGBColor]:
    var = (hoy / ayer - 1) * 100
    return f"{var:+.2f}% contra la rueda anterior", (VERDE if var > 0 else ROJO if var < 0 else GRIS)


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
    explicaciones: dict | None = None,
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
    de agregados y deuda llevan solo el texto fijo, sin la frase con los últimos datos.
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

    # 1. Portada
    portada = prs.slides.add_slide(prs.slide_layouts[6])
    fondo = portada.shapes.add_shape(1, 0, 0, ANCHO, ALTO)
    fondo.fill.solid()
    fondo.fill.fore_color.rgb = AZUL
    fondo.line.fill.background()
    _texto(portada, Inches(0.8), Inches(2.4), Inches(11.7), Inches(1.2), "Reporte Macroeconómico", 48, BLANCO, True)
    _texto(portada, Inches(0.8), Inches(3.6), Inches(11.7), Inches(0.8),
           "Tipos de cambio, riesgo país, tasas e inflación", 22, NARANJA)
    _texto(portada, Inches(0.8), Inches(4.5), Inches(11.7), Inches(0.6), f"{fecha:%d/%m/%Y}", 20, BLANCO)

    # 2. Tablero
    tablero = _encabezado(prs, "Tablero del día", fecha)
    tarjetas = [
        ("Dólar blue", f"$ {hoy['TCV_Blue']:,.2f}", *_variacion(hoy["TCV_Blue"], ayer["TCV_Blue"])),
        ("Dólar MEP", f"$ {hoy['TCV_MEP']:,.2f}", *_variacion(hoy["TCV_MEP"], ayer["TCV_MEP"])),
        ("Billete BNA", f"$ {hoy['TCV_Billete']:,.2f}", *_variacion(hoy["TCV_Billete"], ayer["TCV_Billete"])),
        ("Riesgo país", f"{hoy['riesgo_pais']:,.0f} pts",
         f"{hoy['riesgo_pais'] - ayer['riesgo_pais']:+,.0f} pts contra la rueda anterior",
         ROJO if hoy["riesgo_pais"] > ayer["riesgo_pais"] else VERDE),
        ("BADLAR (TEA)", f"{hoy['bcra_tea']:.2f}%", f"FED (EFFR): {hoy['fed_tea']:.2f}%", GRIS),
        ("Forward oficial 3 meses", f"$ {fwd_oficial:,.2f}", f"Forward blue: $ {fwd_blue:,.2f}", GRIS),
    ]
    for i, (titulo, valor, detalle, color) in enumerate(tarjetas):
        x = Inches(0.45 + (i % 3) * 4.2)
        y = Inches(1.4 + (i // 3) * 2.0)
        _tarjeta(tablero, x, y, titulo, valor, detalle, color)
    diferencia = abs(resumen["ahorro_valor"])
    sentido = "más barato" if resumen["ahorro_valor"] > 0 else "más caro"
    _texto(tablero, Inches(0.45), Inches(5.6), Inches(12.4), Inches(1.2),
           f"Comprar USD {resumen['cantidad_usd']} al oficial con impuestos (solidario) sale $ {diferencia:,.2f} "
           f"{sentido} que en el blue: el solidario está {abs(resumen['brecha_solidario']):.2f}% "
           f"{'por debajo' if resumen['brecha_solidario'] > 0 else 'por encima'} del blue.",
           14, GRIS)

    # 3. Análisis de IA
    analisis = _encabezado(prs, "Análisis", fecha)
    _texto(analisis, Inches(0.6), Inches(1.3), Inches(12.1), Inches(2.4), parrafo, 18, AZUL)
    _texto(analisis, Inches(0.6), Inches(6.8), Inches(12.1), Inches(0.4),
           "Generado con Gemini a partir de los datos del día. No es asesoramiento financiero.", 11, GRIS)

    # 4 a 8. Gráficos, con sus comentarios y explicaciones si los hay
    def diapositiva_grafico(titulo: str, nombres: list[str], cid: str | None):
        slide = _encabezado(prs, titulo, fecha)
        presentes = [imagenes[n] for n in nombres if n in imagenes]
        textos = list(comentarios.get(cid, [])) if cid else []
        explicacion = explicaciones.get(cid) if cid else None
        if explicacion:
            # El texto completo no entra al costado del gráfico: en la diapositiva van los
            # datos del día y "lo ideal" (el último párrafo); todo lo demás, en las notas
            parrafos = explicacion["texto"].split("\n")
            textos.append((explicacion["titulo"], "\n\n".join(filter(None, [explicacion["dato"], parrafos[-1]]))))
            slide.notes_slide.notes_text_frame.text = "\n\n".join(filter(None, [*parrafos, explicacion["dato"]]))
        cuerpo = "\n\n".join(f"{t.upper()}\n{x}" for t, x in textos)

        if len(presentes) > 1:
            # Dos gráficos lado a lado
            for j, ruta in enumerate(presentes):
                slide.shapes.add_picture(str(ruta), Inches(0.45) + j * Inches(6.3), Inches(1.6), width=Inches(6.1))
            return
        if not presentes:
            _texto(slide, Inches(0.6), Inches(3), Inches(12), Inches(1), "Gráfico no disponible para este día.", 18, GRIS)
            return

        foto = slide.shapes.add_picture(str(presentes[0]), Inches(0.45), Inches(1.1), height=Inches(6.2))
        if foto.width > foto.height:
            # Apaisado (BTC): más bajo y centrado, con el comentario abajo
            foto.height, foto.width = int(foto.height * 0.75), int(foto.width * 0.75)
            foto.left = int((ANCHO - foto.width) / 2)
            if textos:
                _texto(slide, Inches(0.6), foto.top + foto.height + Inches(0.15), Inches(12.1), Inches(1.5), cuerpo, 13, AZUL)
        elif textos:
            # Vertical (tipos de cambio): el comentario a la derecha
            izquierda = foto.left + foto.width + Inches(0.4)
            _texto(slide, izquierda, Inches(1.2), ANCHO - izquierda - Inches(0.4), Inches(6), cuerpo, 13, AZUL)
        else:
            foto.left = int((ANCHO - foto.width) / 2)

    diapositiva_grafico("Tipos de cambio y riesgo país", [charts.TIPOS_DE_CAMBIO], "image1")
    diapositiva_grafico("Inflación y variaciones acumuladas", [charts.INFLACION, charts.VARIACIONES], None)
    diapositiva_grafico("Bitcoin", [charts.BTC], "image4")
    diapositiva_grafico("Agregados monetarios", [charts.AGREGADOS], indicadores.CID_AGREGADOS)
    diapositiva_grafico("Endeudamiento, en dólares", [charts.DEUDA], indicadores.CID_DEUDA)

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
