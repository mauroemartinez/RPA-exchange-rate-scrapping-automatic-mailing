"""Gráficos nativos de PowerPoint para la presentación ejecutiva.

El mail lleva imágenes de matplotlib (reporte/charts.py). En la presentación, los
cuatro gráficos simples van como gráficos de PowerPoint, con los mismos datos y
los mismos colores (salvo las variaciones acumuladas, más oscuras para que se lean
sobre blanco): se ven nítidos a cualquier tamaño, se les puede cambiar el estilo y
"Editar datos" abre la planilla con los números del día. Los de agregados, deuda y
BTC siguen como imagen: su detalle (paneles, anotaciones, medias móviles) no se
replica bien con un gráfico nativo.

Cada función recibe la diapositiva, la caja (x, y, ancho, alto) y los datos como
los tiene presentacion.armar. Si algo falla, levanta: presentacion.armar pone la
imagen del mail en su lugar.
"""

import math

import pandas as pd
import seaborn as sns
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_MARKER_STYLE
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.util import Pt

from reporte import charts, transformations

TEXTO = RGBColor(0x2C, 0x3E, 0x50)
GRILLA = RGBColor(0xDC, 0xE6, 0xEF)
# Los mismos del gráfico de riesgo país del mail, y el rojo y el verde del resto del reporte
BARRA = RGBColor(0xC0, 0xC0, 0xC0)
ROJO = RGBColor(0xC0, 0x39, 0x2B)
VERDE = RGBColor(0x1E, 0x84, 0x49)
# Los del gráfico de inflación del mail: barras gris oscuro e interanual en rojo oscuro
BARRA_INFLACION = RGBColor(0xA9, 0xA9, 0xA9)
ROJO_OSCURO = RGBColor(0x8B, 0x00, 0x00)

# Ids de los ejes secundarios del gráfico de inflación: cualquier número que no usen los primarios
EJE_X2, EJE_Y2 = "50020001", "50020002"


def _rgb(color) -> RGBColor:
    """Un color de seaborn (r, g, b entre 0 y 1) como RGBColor."""
    return RGBColor(*(round(c * 255) for c in color[:3]))


def _paleta(nombre: str, n: int) -> list[RGBColor]:
    """La paleta de seaborn que usa el gráfico del mail, así el nativo tiene los mismos colores."""
    return [_rgb(c) for c in sns.color_palette(nombre)[:n]]


def _valores(serie) -> list[float | None]:
    """Los vacíos van como None: PowerPoint no acepta 'nan' en los datos del gráfico y pide repararlo."""
    return [None if pd.isna(v) else float(v) for v in serie]


def _es(valor: float, decimales: int = 1) -> str:
    """Formato argentino para las etiquetas escritas a mano: 1234.5 da '1.234,5'."""
    return f"{valor:,.{decimales}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _escala(valores, divisiones: int = 5) -> tuple[float, float, float]:
    """(mínimo, máximo, paso) redondos para el eje.

    PowerPoint arranca el eje en cero cuando el mínimo no está cerca del máximo, y
    cotizaciones de 1.500 a 2.000 quedarían como líneas planas arriba de todo.
    """
    limpios = [v for v in valores if v is not None]
    bajo, alto = min(limpios), max(limpios)
    if alto == bajo:
        bajo, alto = bajo - 1, alto + 1
    crudo = (alto - bajo) / divisiones
    potencia = 10 ** math.floor(math.log10(crudo))
    paso = next(m * potencia for m in (1, 2, 2.5, 5, 10) if m * potencia >= crudo)
    return math.floor(bajo / paso) * paso, math.ceil(alto / paso) * paso, paso


def _base(grafico, titulo: str, leyenda: bool = True) -> None:
    """Título, leyenda abajo, grilla suave y letra del reporte: lo común a los cuatro."""
    grafico.font.size = Pt(10)
    grafico.font.color.rgb = TEXTO
    grafico.has_title = True
    grafico.chart_title.text_frame.text = titulo
    parrafo = grafico.chart_title.text_frame.paragraphs[0]
    parrafo.font.size, parrafo.font.bold, parrafo.font.color.rgb = Pt(13), True, TEXTO
    grafico.has_legend = leyenda
    if leyenda:
        grafico.legend.position = XL_LEGEND_POSITION.BOTTOM
        grafico.legend.include_in_layout = False
        grafico.legend.font.size = Pt(9)
    eje = grafico.value_axis
    eje.has_major_gridlines = True
    eje.major_gridlines.format.line.color.rgb = GRILLA
    eje.major_gridlines.format.line.width = Pt(0.75)
    eje.format.line.fill.background()
    grafico.category_axis.format.line.color.rgb = GRILLA


def _eje_valores(grafico, valores, formato: str, desde_cero: bool = False) -> None:
    bajo, alto, paso = _escala(valores)
    eje = grafico.value_axis
    eje.minimum_scale, eje.maximum_scale, eje.major_unit = (0 if desde_cero else bajo), alto, paso
    eje.tick_labels.number_format = formato
    eje.tick_labels.number_format_is_linked = False


def _etiqueta_final(serie, valores, texto: str, color: RGBColor) -> None:
    """El valor del último punto, arriba de él: a la derecha chocaría con el eje derecho."""
    ultimo = max(i for i, v in enumerate(valores) if v is not None)
    etiqueta = serie.points[ultimo].data_label
    etiqueta.has_text_frame = True
    etiqueta.text_frame.text = texto
    etiqueta.position = XL_LABEL_POSITION.ABOVE
    fuente = etiqueta.text_frame.paragraphs[0].font
    fuente.size, fuente.bold, fuente.color.rgb = Pt(9), True, color


def _lineas(slide, x, y, ancho, alto, titulo: str, categorias, series, formato: str, marcadores: bool = True):
    """Un gráfico de líneas: `series` es [(nombre, valores, color)]."""
    datos = CategoryChartData(number_format=formato)
    datos.categories = categorias
    for nombre, valores, _ in series:
        datos.add_series(nombre, valores)
    tipo = XL_CHART_TYPE.LINE_MARKERS if marcadores else XL_CHART_TYPE.LINE
    grafico = slide.shapes.add_chart(tipo, x, y, ancho, alto, datos).chart
    _base(grafico, titulo)
    for serie, (_, _, color) in zip(grafico.plots[0].series, series):
        serie.smooth = False
        serie.format.line.color.rgb = color
        serie.format.line.width = Pt(2)
        if marcadores:
            serie.marker.style = XL_MARKER_STYLE.CIRCLE
            serie.marker.size = 5
            serie.marker.format.fill.solid()
            serie.marker.format.fill.fore_color.rgb = color
            serie.marker.format.line.color.rgb = color
    _eje_valores(grafico, [v for _, valores, _ in series for v in valores], formato)
    return grafico


def _ultimas_ruedas(df, n: int = charts.COTIZACIONES_A_MOSTRAR) -> pd.DataFrame:
    """Las últimas n ruedas, de la más vieja a la más nueva, con la fecha como 'dd/mm/yy' (como el mail)."""
    return charts.preparar_datos(df).tail(n)


def paralelas(slide, x, y, ancho, alto, df):
    """Euro blue, blue (venta y compra), MEP y solidario de las últimas ruedas, con la paleta del mail."""
    ultimos = _ultimas_ruedas(df)
    columnas = [("Euro blue", "TCV_Euro"), ("Blue venta", "TCV_Blue"), ("Blue compra", "TCC_Blue"),
                ("MEP", "TCV_MEP"), ("Solidario", "Solidario")]
    colores = _paleta("dark", len(columnas))
    series = [(nombre, _valores(ultimos[col]), color) for (nombre, col), color in zip(columnas, colores)]
    return _lineas(slide, x, y, ancho, alto, "Cotizaciones paralelas (ARS por USD)",
                   [f[:5] for f in ultimos["Fecha"]], series, "#,##0")


def oficiales(slide, x, y, ancho, alto, df):
    """Billete y divisas del BNA, a la venta y a la compra, con la paleta del mail."""
    ultimos = _ultimas_ruedas(df)
    columnas = [("Billete venta", "TCV_Billete"), ("Divisas venta", "TCV_Divisas"),
                ("Divisas compra", "TCC_Divisas"), ("Billete compra", "TCC_Billete")]
    colores = _paleta("bright", len(columnas))
    series = [(nombre, _valores(ultimos[col]), color) for (nombre, col), color in zip(columnas, colores)]
    return _lineas(slide, x, y, ancho, alto, "Cotizaciones oficiales del BNA (ARS por USD)",
                   [f[:5] for f in ultimos["Fecha"]], series, "#,##0")


def riesgo_pais(slide, x, y, ancho, alto, df):
    """Barras del riesgo país con el máximo de la ventana en rojo y el mínimo en verde, como el mail."""
    ultimos = _ultimas_ruedas(df)
    valores = _valores(ultimos["riesgo_pais"])
    datos = CategoryChartData(number_format="#,##0")
    datos.categories = [f[:5] for f in ultimos["Fecha"]]
    datos.add_series("Riesgo país (puntos básicos)", valores)
    grafico = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, ancho, alto, datos).chart
    _base(grafico, f"Riesgo país, últimas {len(valores)} ruedas (puntos básicos)", leyenda=False)

    barras = grafico.plots[0]
    barras.gap_width = 40
    serie = barras.series[0]
    serie.format.fill.solid()
    serie.format.fill.fore_color.rgb = BARRA
    presentes = [v for v in valores if v is not None]
    maximo, minimo = max(presentes), min(presentes)
    for i, valor in enumerate(valores):
        # Todas las ruedas que tocan el máximo o el mínimo, como en el mail
        if valor in (maximo, minimo):
            punto = serie.points[i].format.fill
            punto.solid()
            punto.fore_color.rgb = ROJO if valor == maximo else VERDE

    barras.has_data_labels = True
    etiquetas = barras.data_labels
    etiquetas.number_format, etiquetas.number_format_is_linked = "#,##0", False
    etiquetas.position = XL_LABEL_POSITION.OUTSIDE_END
    etiquetas.font.size = Pt(8)
    _eje_valores(grafico, [0, maximo * 1.12], "#,##0", desde_cero=True)
    return grafico


def _a_linea_en_eje_secundario(grafico) -> None:
    """Pasa la segunda serie de las barras a una línea con su propio eje, a la derecha.

    python-pptx no arma gráficos combinados: se crean las dos series como barras (así
    la planilla incrustada las tiene a las dos) y la segunda se mueve a un lineChart
    con un par de ejes nuevos, que es como guarda PowerPoint un gráfico combinado.
    """
    area = grafico._chartSpace.chart.plotArea
    barras = area.find(qn("c:barChart"))
    serie = barras.findall(qn("c:ser"))[1]
    barras.remove(serie)
    invertir = serie.find(qn("c:invertIfNegative"))
    if invertir is not None:
        serie.remove(invertir)  # no existe en las series de línea: PowerPoint pediría reparar el archivo
    linea = parse_xml(
        f'<c:lineChart {nsdecls("c")}><c:grouping val="standard"/><c:varyColors val="0"/>'
        f'<c:marker val="1"/><c:axId val="{EJE_X2}"/><c:axId val="{EJE_Y2}"/></c:lineChart>'
    )
    linea.insert(2, serie)
    barras.addnext(linea)
    ejes = parse_xml(
        f'<c:plotArea {nsdecls("c")}>'
        f'<c:catAx><c:axId val="{EJE_X2}"/><c:scaling><c:orientation val="minMax"/></c:scaling>'
        '<c:delete val="1"/><c:axPos val="b"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/>'
        f'<c:tickLblPos val="nextTo"/><c:crossAx val="{EJE_Y2}"/><c:crosses val="autoZero"/>'
        '<c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/><c:noMultiLvlLbl val="0"/></c:catAx>'
        f'<c:valAx><c:axId val="{EJE_Y2}"/><c:scaling><c:orientation val="minMax"/></c:scaling>'
        '<c:delete val="0"/><c:axPos val="r"/><c:numFmt formatCode="0.0&quot;%&quot;" sourceLinked="0"/>'
        '<c:majorTickMark val="out"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'
        f'<c:crossAx val="{EJE_X2}"/><c:crosses val="max"/><c:crossBetween val="between"/></c:valAx>'
        "</c:plotArea>"
    )
    ultimo_eje = area.findall(qn("c:valAx"))[-1]
    for eje in reversed(list(ejes)):
        ultimo_eje.addnext(eje)


def _escala_secundaria(grafico, valores) -> None:
    """Mínimo y máximo del eje derecho, para que la interanual no quede aplastada contra cero."""
    bajo, alto, _ = _escala(valores)
    eje = next(e for e in grafico._chartSpace.chart.plotArea.findall(qn("c:valAx"))
               if e.find(qn("c:axId")).get("val") == EJE_Y2)
    escala = eje.find(qn("c:scaling"))
    escala.append(parse_xml(f'<c:max {nsdecls("c")} val="{alto}"/>'))
    escala.append(parse_xml(f'<c:min {nsdecls("c")} val="{bajo}"/>'))


def inflacion(slide, x, y, ancho, alto, inflacion):
    """Inflación mensual en barras e interanual en línea, en dos ejes, de los últimos 12 meses, como el mail."""
    ultimos = transformations.ultimos_meses(inflacion)
    mensual, anual = _valores(ultimos["Inflación Mensual"]), _valores(ultimos["Inflación Anual"])
    datos = CategoryChartData(number_format='0.0"%"')
    datos.categories = [transformations.etiqueta_mes(f) for f in ultimos["Fecha"]]
    datos.add_series("Inflación mensual", mensual)
    datos.add_series("Inflación interanual (eje derecho)", anual)
    grafico = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, ancho, alto, datos).chart
    # Todo lo del eje izquierdo va antes de agregar el derecho: con dos ejes de valores,
    # python-pptx devuelve el segundo como value_axis y la escala de las barras caería ahí
    _base(grafico, f"Inflación de los últimos {len(mensual)} meses")
    _eje_valores(grafico, [0, max(v for v in mensual if v is not None) * 1.2], '0.0"%"', desde_cero=True)
    barras = grafico.plots[0]
    barras.gap_width = 60
    columnas = barras.series[0]
    columnas.format.fill.solid()
    columnas.format.fill.fore_color.rgb = BARRA_INFLACION
    barras.has_data_labels = True
    etiquetas = barras.data_labels
    etiquetas.number_format, etiquetas.number_format_is_linked = '0.0"%"', False
    etiquetas.position = XL_LABEL_POSITION.OUTSIDE_END
    etiquetas.font.size = Pt(8)
    _a_linea_en_eje_secundario(grafico)

    linea = grafico.plots[1].series[0]
    linea.smooth = False
    linea.format.line.color.rgb = ROJO_OSCURO
    linea.format.line.width = Pt(2.5)
    linea.marker.style = XL_MARKER_STYLE.CIRCLE
    linea.marker.size = 6
    linea.marker.format.fill.solid()
    linea.marker.format.fill.fore_color.rgb = ROJO_OSCURO
    linea.marker.format.line.color.rgb = ROJO_OSCURO
    if any(v is not None for v in anual):
        _escala_secundaria(grafico, anual)
        _etiqueta_final(linea, anual, f"{_es(next(v for v in reversed(anual) if v is not None))}%", ROJO_OSCURO)
    return grafico


def _meses_en_el_eje(grafico, cada: int) -> None:
    """Un rótulo cada `cada` meses en el eje de fechas: python-pptx no lo expone."""
    eje = grafico._chartSpace.chart.plotArea.find(qn("c:dateAx"))
    for etiqueta in ("c:baseTimeUnit", "c:majorUnit", "c:majorTimeUnit"):
        viejo = eje.find(qn(etiqueta))
        if viejo is not None:
            eje.remove(viejo)
    nuevos = [parse_xml(f'<c:baseTimeUnit {nsdecls("c")} val="days"/>'),
              parse_xml(f'<c:majorUnit {nsdecls("c")} val="{cada}"/>'),
              parse_xml(f'<c:majorTimeUnit {nsdecls("c")} val="months"/>')]
    # Van antes de minorUnit, minorTimeUnit o extLst, si los hay; si no, al final
    siguiente = next((eje.find(qn(e)) for e in ("c:minorUnit", "c:minorTimeUnit", "c:extLst")
                      if eje.find(qn(e)) is not None), None)
    for nuevo in nuevos:
        if siguiente is None:
            eje.append(nuevo)
        else:
            siguiente.addprevious(nuevo)


def variaciones(slide, x, y, ancho, alto, df, inflacion):
    """Solidario, blue e inflación acumulados desde charts.FECHA_INICIO_VARIACIONES, en un eje de fechas."""
    data = charts.preparar_datos(transformations.agregar_brechas_y_variaciones(df))
    va = charts.preparar_variaciones(data, inflacion).dropna(subset=["Fecha"])
    columnas = [("Solidario", "Variación Solidario Acumulada"), ("Blue", "Variación TCV Blue Acumulada"),
                ("Inflación", "Inflación Mensual Acumulada")]
    # La inflación es mensual y las cotizaciones diarias: se completa hacia adelante, como el
    # escalón del mail, y las cotizaciones de los días sin rueda repiten la anterior
    va[[c for _, c in columnas]] = va[[c for _, c in columnas]].ffill()
    colores = _paleta("deep", 4)
    colores = [colores[0], colores[1], ROJO_OSCURO]
    series = [(f"{nombre} acumulado", _valores(va[col]), color) for (nombre, col), color in zip(columnas, colores)]
    if not all(any(v is not None for v in valores) for _, valores, _ in series):
        raise ValueError("faltan datos para alguna de las variaciones acumuladas")

    inicio = pd.Timestamp(charts.FECHA_INICIO_VARIACIONES)
    grafico = _lineas(slide, x, y, ancho, alto, f"Variaciones acumuladas desde {inicio:%m/%Y}",
                      [f.date() for f in va["Fecha"]], series, '0"%"', marcadores=False)
    grafico.category_axis.tick_labels.number_format = "mmm-yy"
    grafico.category_axis.tick_labels.number_format_is_linked = False
    meses = max(1, (va["Fecha"].iloc[-1] - va["Fecha"].iloc[0]).days // 30)
    # Sin etiquetas en los últimos puntos: blue y solidario suelen terminar cerca y se pisan,
    # y el resumen de la diapositiva ya dice cuánto acumuló cada uno
    _meses_en_el_eje(grafico, 1 if meses <= 8 else 2 if meses <= 16 else 3)
    return grafico
