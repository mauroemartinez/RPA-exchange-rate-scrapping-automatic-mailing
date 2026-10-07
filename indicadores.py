"""Explicaciones de los gráficos de agregados monetarios y de deuda, para quien no es economista.

Cada una tiene un texto fijo (qué es cada cosa y cómo leer el gráfico) y una
frase calculada acá, en Python, con los últimos datos y sus fechas. Gemini no
escribe nada de esto: los números salen de las series, como en las tablas del
mail. El mail las pone debajo de su gráfico y la presentación, al costado.
"""

from datetime import date

import pandas as pd

import charts
import transformations
from scrapers import agregados

# Cuánta historia bajar para los dos gráficos: el panel de variación interanual
# muestra un año, y cada punto se compara con el mismo día del año anterior
ANIOS_DE_SERIES = 2
MARGEN_DIAS = 15

CID_AGREGADOS = f"image{charts.ORDEN_EN_MAIL.index(charts.AGREGADOS) + 1}"
CID_DEUDA = f"image{charts.ORDEN_EN_MAIL.index(charts.DEUDA) + 1}"

TITULO_AGREGADOS = "Agregados monetarios, en simple"
TEXTO_AGREGADOS = (
    "Los agregados monetarios miden cuánta plata hay en la economía. La circulación monetaria son los billetes "
    "y monedas; la base monetaria es el dinero que crea el Banco Central: esos billetes y monedas más lo que los "
    "bancos tienen depositado en él. El M2 suma los billetes en manos de la gente y lo que hay en cuentas "
    "corrientes y cajas de ahorro, y el M3 agrega los plazos fijos. Arriba se ve cuánto hay, en billones de pesos. "
    "Abajo, cuánto creció cada uno en un año comparado con la inflación (la línea roja): si una línea queda por "
    "debajo de la roja, esa plata alcanza para comprar menos cosas que hace un año."
)

TITULO_DEUDA = "Endeudamiento, en simple"
TEXTO_DEUDA = (
    "Todo está en dólares: lo que se publica en pesos se convierte con el tipo de cambio oficial mayorista de cada "
    "día. Arriba, la deuda bruta del Tesoro nacional: lo que debe el Estado por bonos, letras y préstamos de "
    "organismos como el FMI. Se publica una vez por mes, con unas cinco semanas de atraso, y los últimos meses son "
    "provisorios (los puntos huecos). En el medio, lo que familias y empresas les deben a los bancos. Abajo, dos "
    "deudas que pasan por el Banco Central: las letras que emitió, en pesos y en dólares, y los adelantos "
    "transitorios, que son préstamos del BCRA al Tesoro."
)

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
# Diferencias menores que esto (en puntos porcentuales) cuentan como "igual que la inflación"
TOLERANCIA_REAL = 0.05


def desde(hoy: date) -> date:
    """La primera fecha a bajar para que los gráficos tengan su año completo de variación interanual."""
    return (pd.Timestamp(hoy) - pd.DateOffset(years=ANIOS_DE_SERIES, days=MARGEN_DIAS)).date()


def numero(valor: float, decimales: int = 1) -> str:
    """Formato argentino: 1234567.891 da '1.234.567,9'."""
    return f"{valor:,.{decimales}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def mes_y_anio(fecha: date) -> str:
    return f"{MESES[fecha.month - 1]} de {fecha.year}"


def frase_agregados(series: dict) -> str | None:
    """La variación interanual de la base monetaria y del M2 contra la inflación, con sus fechas.

    None si falta la inflación o no alcanza la historia para ninguna de las dos variaciones.
    """
    inflacion = series.get("inflacion_interanual")
    if not inflacion:
        return None
    variaciones = []
    for clave, nombre in (("base_monetaria", "la base monetaria"), ("m2", "el M2")):
        puntos = series.get(clave)
        variacion = transformations.variacion_interanual(puntos) if puntos else None
        if variacion is not None:
            variaciones.append((nombre, variacion, puntos[-1][0]))
    if not variaciones:
        return None

    fecha_inflacion, valor_inflacion = inflacion[-1]
    crecieron = " y ".join(
        f"{nombre} {'creció' if variacion >= 0 else 'cayó'} {numero(abs(variacion))}% (al {fecha:%d/%m/%Y})"
        for nombre, variacion, fecha in variaciones
    )

    def real(variacion: float) -> str:
        diferencia = variacion - valor_inflacion
        return "se mantuvo" if abs(diferencia) < TOLERANCIA_REAL else "creció" if diferencia > 0 else "cayó"

    reales = [(nombre, real(variacion)) for nombre, variacion, _ in variaciones]
    if len(reales) == 2 and reales[0][1] == reales[1][1]:
        plural = {"creció": "crecieron", "cayó": "cayeron", "se mantuvo": "se mantuvieron"}[reales[0][1]]
        veredicto = f"las dos {plural}"
    else:
        veredicto = " y ".join(f"{nombre} {verbo}" for nombre, verbo in reales)
    return (
        f"En el último año {crecieron}, contra una inflación interanual de {numero(valor_inflacion)}% "
        f"en {mes_y_anio(fecha_inflacion)}: descontada la inflación, {veredicto}."
    )


def frase_deuda(series: dict, provisorios=frozenset()) -> str | None:
    """El último dato de la deuda bruta del Tesoro y de los préstamos al sector privado, en dólares."""
    partes = []
    tesoro = series.get("deuda_bruta_tesoro")
    if tesoro:
        fecha, valor = tesoro[-1]
        texto = (
            f"a fines de {mes_y_anio(fecha)}{' (dato provisorio)' if fecha in provisorios else ''}, "
            f"la deuda bruta del Tesoro era de USD {numero(valor / 1e3)} mil millones"
        )
        hace_un_anio = (pd.Timestamp(fecha) - pd.DateOffset(years=1)).date()
        previos = [v for f, v in tesoro if f <= hace_un_anio]
        if previos:
            diferencia = (valor - previos[-1]) / 1e3
            texto += f", {numero(abs(diferencia))} mil millones {'más' if diferencia >= 0 else 'menos'} que un año antes"
        partes.append(texto)

    prestamos, cambio = series.get("prestamos_sector_privado"), series.get("tipo_cambio_mayorista")
    if prestamos and cambio:
        en_dolares = transformations.a_dolares(prestamos, cambio)
        if not en_dolares.empty:
            ultimo = en_dolares.iloc[-1]
            partes.append(
                f"al {ultimo['Fecha']:%d/%m/%Y}, familias y empresas les debían a los bancos "
                f"USD {numero(ultimo['usd'] / 1e3)} mil millones"
            )
    if not partes:
        return None
    frase = "; ".join(partes)
    return frase[0].upper() + frase[1:] + "."


def textos_fijos(cids: list[str] | None = None) -> dict[str, dict]:
    """Las explicaciones sin la frase de los últimos datos. Es el plan B si calcularla falla."""
    todas = {
        CID_AGREGADOS: {"titulo": TITULO_AGREGADOS, "texto": TEXTO_AGREGADOS, "dato": None},
        CID_DEUDA: {"titulo": TITULO_DEUDA, "texto": TEXTO_DEUDA, "dato": None, "con_deuda_bruta": False},
    }
    return {cid: explicacion for cid, explicacion in todas.items() if cids is None or cid in cids}


def explicaciones(series: dict | None, provisorios=frozenset(), cids: list[str] | None = None) -> dict[str, dict]:
    """{cid: {"titulo", "texto", "dato"}} de los gráficos de agregados y deuda.

    `dato` es la frase con los últimos números; None si faltan series para armarla,
    y entonces queda solo el texto fijo. `cids` limita a los gráficos que viajan. La
    de deuda dice además si llegó la deuda bruta, para citar o no a la Secretaría.
    """
    series = series or {}
    todas = textos_fijos(cids)
    if CID_AGREGADOS in todas:
        todas[CID_AGREGADOS]["dato"] = frase_agregados(series)
    if CID_DEUDA in todas:
        todas[CID_DEUDA]["dato"] = frase_deuda(series, provisorios)
        todas[CID_DEUDA]["con_deuda_bruta"] = bool(series.get(agregados.DEUDA_BRUTA.clave))
    return todas
