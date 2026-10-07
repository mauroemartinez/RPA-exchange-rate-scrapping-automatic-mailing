"""Deuda bruta de la Administración Central: el Excel mensual de la Secretaría de Finanzas.

Opción A del endeudamiento (docs/fase-3-agregados-y-deuda.md). La Secretaría no
tiene API: publica una planilla por mes ("Serie mensual 2019 - Agosto 2026") en
una página fija, y el nombre del archivo cambia con cada publicación
(boletin_mensual_31_08_2026_1.xlsx). Por eso primero se lee la página, se toma el
link de esa fila y recién después se baja el Excel.

La planilla se lee por rótulos y no por posiciones de celda, porque su armado
puede cambiar sin aviso: se busca la fila "A- DEUDA BRUTA" y, arriba de ella, la
fila de los meses. Los meses confirmados vienen como fechas; los últimos, como
texto con un asterisco ("jul-26 (*)"): son provisorios y la Secretaría los revisa
al mes siguiente. Si algo no está donde se espera (el rótulo, los meses, la unidad
en millones de U$S, valores en un rango razonable), levanta en vez de devolver un
número mal leído.

Los valores quedan en millones de USD, como los publica la fuente, fechados el
último día de cada mes: son saldos a fin de mes. La descripción de la serie para
Fact_Series_Macro es scrapers.agregados.DEUDA_BRUTA.
"""

import calendar
import io
import re
import unicodedata
from datetime import date, datetime
from urllib.parse import urljoin

import httpx

from scrapers.utils import ScraperError, retry_http

PAGINA = "https://www.argentina.gob.ar/economia/finanzas/datos-mensuales-de-la-deuda/datos"
TIMEOUT = httpx.Timeout(60.0, connect=15.0)
ENCABEZADOS = {"User-Agent": "Mozilla/5.0 (compatible; SeguimientoMacro/1.0)"}

MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}
_MES_TEXTO = re.compile(r"^(ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic)[a-z]*\.?\s*[-/ ]\s*(\d{2}|\d{4})\b(.*)$")
_TOTAL = re.compile(r"^A\s*-\s*DEUDA BRUTA\b")

# Una deuda bruta de entre 100 mil y 2 millones de millones de USD: fuera de eso, la
# planilla cambió de unidad o se leyó la fila equivocada
RANGO_PLAUSIBLE = (100_000, 2_000_000)
# La serie arranca en enero de 2019: menos de dos años de meses es una planilla rara
MINIMO_MESES = 24


def _normalizar(texto: str) -> str:
    """Sin tildes, en mayúsculas y con espacios simples: 'Deuda  Bruta' y 'DEUDA BRUTA' son lo mismo."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes).strip().upper()


def _fin_de_mes(anio: int, mes: int) -> date:
    return date(anio, mes, calendar.monthrange(anio, mes)[1])


def _mes(celda) -> tuple[date, bool] | None:
    """(último día del mes, provisorio) si la celda es un encabezado de mes; None si no lo es."""
    if isinstance(celda, datetime | date):
        return _fin_de_mes(celda.year, celda.month), False
    if isinstance(celda, str):
        coincidencia = _MES_TEXTO.match(celda.strip().lower())
        if coincidencia:
            anio = int(coincidencia.group(2))
            anio += 2000 if anio < 100 else 0
            return _fin_de_mes(anio, MESES[coincidencia.group(1)]), "*" in coincidencia.group(3)
    return None


def _es_fila_total(fila: tuple) -> bool:
    return any(isinstance(celda, str) and _TOTAL.match(_normalizar(celda)) for celda in fila)


def _leer_serie(filas: list[tuple], total: int, hoja: str) -> tuple[list[tuple[date, float]], set[date]]:
    arriba = " ".join(_normalizar(c) for fila in filas[:total] for c in fila if isinstance(c, str))
    if "MILLONES DE U$S" not in arriba and "MILLONES DE USD" not in arriba:
        raise ValueError(f"hoja {hoja}: no dice que los datos están en millones de U$S")

    # Los meses están en la fila de arriba del total que más encabezados de mes tiene
    cantidad, encabezado = max((sum(_mes(c) is not None for c in filas[i]), i) for i in range(total))
    if cantidad < MINIMO_MESES:
        raise ValueError(f"hoja {hoja}: no encontré la fila de los meses arriba de 'A- DEUDA BRUTA'")

    valores = filas[total]
    puntos, provisorios = [], set()
    for columna, celda in enumerate(filas[encabezado]):
        mes = _mes(celda)
        valor = valores[columna] if columna < len(valores) else None
        if mes is None or isinstance(valor, bool) or not isinstance(valor, int | float):
            continue
        fecha, provisorio = mes
        puntos.append((fecha, float(valor)))
        if provisorio:
            provisorios.add(fecha)

    if len(puntos) < MINIMO_MESES:
        raise ValueError(f"hoja {hoja}: solo {len(puntos)} meses con dato en 'A- DEUDA BRUTA'")
    fechas = [f for f, _ in puntos]
    if any(b <= a for a, b in zip(fechas, fechas[1:])):
        raise ValueError(f"hoja {hoja}: meses repetidos o desordenados")
    bajo, alto = RANGO_PLAUSIBLE
    fuera = [(f, v) for f, v in puntos if not bajo < v < alto]
    if fuera:
        raise ValueError(f"hoja {hoja}: valores fuera de rango, por ejemplo {fuera[0][1]:,.0f} en {fuera[0][0]}")
    return puntos, provisorios


def leer_planilla(contenido: bytes) -> tuple[list[tuple[date, float]], set[date]]:
    """(saldos de la deuda bruta total por mes, meses provisorios) desde el Excel de la Secretaría."""
    # Acá y no arriba: pipeline.py y email_report.py importan este módulo al arrancar,
    # y un venv sin openpyxl tiene que poder mandar el mail igual (sin la deuda bruta)
    import openpyxl

    libro = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    try:
        for hoja in libro.worksheets:
            filas = [tuple(fila) for fila in hoja.iter_rows(values_only=True)]
            total = next((i for i, fila in enumerate(filas) if _es_fila_total(fila)), None)
            if total is not None:
                return _leer_serie(filas, total, hoja.title)
    finally:
        libro.close()
    raise ValueError("ninguna hoja tiene la fila 'A- DEUDA BRUTA'")


def url_planilla(html: str, base: str = PAGINA) -> str:
    """El link al .xlsx de la fila "Serie mensual ..." de la página de datos de la Secretaría."""
    for fila in re.findall(r"<tr\b.*?</tr>", html, flags=re.S | re.I):
        texto = _normalizar(re.sub(r"<[^>]+>", " ", fila))
        enlace = re.search(r'href="([^"]+\.xlsx)"', fila, flags=re.I)
        if "SERIE MENSUAL" in texto and enlace:
            return urljoin(base, enlace.group(1))
    raise ValueError("la página de la Secretaría de Finanzas no tiene la fila 'Serie mensual' con un .xlsx")


@retry_http
def _get(client: httpx.Client, url: str) -> httpx.Response:
    respuesta = client.get(url)
    respuesta.raise_for_status()
    return respuesta


def _descargar(client: httpx.Client) -> tuple[list[tuple[date, float]], set[date]]:
    pagina = _get(client, PAGINA)
    excel = _get(client, url_planilla(pagina.text, str(pagina.url)))
    return leer_planilla(excel.content)


def descargar(client: httpx.Client | None = None) -> tuple[list[tuple[date, float]], set[date]]:
    """(puntos, meses provisorios) de la deuda bruta: baja la página, toma el link y baja el Excel."""
    try:
        if client is not None:
            return _descargar(client)
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True, headers=ENCABEZADOS) as propio:
            return _descargar(propio)
    except Exception as exc:
        raise ScraperError("Secretaría de Finanzas", "leer la deuda bruta mensual", exc) from exc
