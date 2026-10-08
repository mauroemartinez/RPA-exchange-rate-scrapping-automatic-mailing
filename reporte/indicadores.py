"""Explicaciones de los gráficos de agregados monetarios y de deuda, para quien no es economista.

Cada una tiene un texto fijo (qué es cada cosa y cómo leer el gráfico) y una
frase calculada acá, en Python, con los últimos datos y sus fechas. Gemini no
escribe nada de esto: los números salen de las series, como en las tablas del
mail. El mail las pone debajo de su gráfico y la presentación, al costado.
"""

from datetime import date

import pandas as pd

from reporte import charts, transformations
from reporte.scrapers import agregados

# Cuánta historia bajar para los dos gráficos: el panel de variación interanual
# muestra un año, y cada punto se compara con el mismo día del año anterior
ANIOS_DE_SERIES = 2
# La frase de deuda compara contra la misma fecha de hace 4, 8 y 12 años. Esa historia
# larga se baja aparte y solo para las series que la usan
COMPARACIONES_ANIOS = (4, 8, 12)
CLAVES_COMPARACIONES = ("prestamos_sector_privado", "tipo_cambio_mayorista")
MARGEN_DIAS = 15

CID_AGREGADOS = charts.cid(charts.AGREGADOS)
CID_DEUDA = charts.cid(charts.DEUDA)

TITULO_AGREGADOS = "Agregados monetarios, en simple"
# Los textos fijos van en párrafos separados por "\n": el mail y la presentación
# muestran cada uno en su renglón.
TEXTO_AGREGADOS = (
    "Los agregados monetarios miden cuánta plata hay en la economía. La circulación monetaria son los billetes "
    "y monedas; la base monetaria es el dinero que crea el Banco Central: esos billetes y monedas más lo que los "
    "bancos tienen depositado en él. El M2 suma los billetes en manos de la gente y lo que hay en cuentas "
    "corrientes y cajas de ahorro, y el M3 agrega los plazos fijos. Arriba se ve cuánto hay, en billones de pesos. "
    "Abajo, cuánto creció cada uno en un año comparado con la inflación (la línea roja): si una línea queda por "
    "debajo de la roja, esa plata alcanza para comprar menos cosas que hace un año.\n"
    "¿Qué sería lo ideal? Que la cantidad de pesos crezca al ritmo de los que la gente quiere tener: más o menos lo "
    "que crece la economía más una inflación baja. Si crece mucho más rápido, hay más pesos persiguiendo las mismas "
    "cosas y eso suele anticipar más inflación y un dólar más caro. Si crece mucho más lento, la inflación tiende a "
    "bajar, pero hay menos plata para consumir y menos crédito, y la actividad se enfría."
)

TITULO_DEUDA = "Endeudamiento, en simple"
TEXTO_DEUDA = (
    "Todo está en dólares: lo que se publica en pesos se convierte con el tipo de cambio oficial mayorista de cada "
    "día.\n"
    "Arriba, la deuda bruta del Tesoro nacional: lo que debe el Estado por bonos, letras y préstamos de organismos "
    "como el FMI. Te importa porque se paga con impuestos o con más deuda: cuanto más pesa, menos margen hay para "
    "bajar impuestos y más caro le sale al país (y a sus empresas) conseguir crédito, algo que se ve en el riesgo "
    "país. Se publica una vez por mes, con unas cinco semanas de atraso, y los últimos meses son provisorios (los círculos naranjas): "
    "pueden corregirse.\n"
    "En el medio, lo que familias y empresas les deben a los bancos: tarjetas, préstamos personales, hipotecas y "
    "créditos a empresas. Si sube, hay más crédito para consumir, comprar una casa o invertir; si sube demasiado "
    "rápido, crece el riesgo de que mucha gente no pueda pagar.\n"
    "Abajo, dos deudas que pasan por el Banco Central. Las letras en pesos son la forma en que el BCRA retira pesos "
    "de la calle pagando un interés (las en dólares son deuda en esa moneda). Te importa porque esos intereses se "
    "pagan con pesos nuevos: si el stock crece mucho, es inflación a futuro; y la tasa que pagan influye en lo que "
    "te dan por un plazo fijo. Los adelantos transitorios son pesos que el BCRA emite y le presta al Tesoro: es "
    "financiar al Estado con emisión, y cuanto más se usa ese atajo, más presión hay sobre los precios y el dólar.\n"
    "¿Qué sería lo ideal? Que la deuda del Estado crezca más despacio que la economía (o baje), que el crédito a "
    "familias y empresas crezca de forma sostenida, y que los adelantos al Tesoro no aumenten."
)

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
# Diferencias menores que esto (en puntos porcentuales) cuentan como "igual que la inflación"
# Puntos porcentuales dentro de los cuales una variación se considera igual a la inflación
TOLERANCIA_REAL = 0.5


def desde(hoy: date) -> date:
    """La primera fecha a bajar para que los gráficos tengan su año completo de variación interanual."""
    return (pd.Timestamp(hoy) - pd.DateOffset(years=ANIOS_DE_SERIES, days=MARGEN_DIAS)).date()


def desde_comparaciones(hoy: date) -> date:
    """La primera fecha a bajar de CLAVES_COMPARACIONES para comparar contra hace 12 años."""
    return (pd.Timestamp(hoy) - pd.DateOffset(years=max(COMPARACIONES_ANIOS), days=MARGEN_DIAS)).date()


def numero(valor: float, decimales: int = 1) -> str:
    """Formato argentino: 1234567.891 da '1.234.567,9'."""
    return f"{valor:,.{decimales}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def mes_y_anio(fecha: date) -> str:
    return f"{MESES[fecha.month - 1]} de {fecha.year}"


def _interanual_al(puntos: list[tuple[date, float]], fecha: date) -> float | None:
    """La variación interanual de la serie en su última fecha que no pase de `fecha`."""
    tabla = transformations.interanual_por_fecha(puntos).dropna(subset=["interanual"])
    previas = tabla[tabla["Fecha"] <= pd.Timestamp(fecha)]
    return float(previas["interanual"].iloc[-1]) if not previas.empty else None


def frase_agregados(series: dict) -> str | None:
    """La variación interanual de la base monetaria y del M2 contra la inflación, con sus fechas.

    None si falta la inflación o no alcanza la historia para ninguna de las dos variaciones.
    """
    inflacion = transformations.inflacion_interanual(series)
    if not inflacion:
        return None
    variaciones = []
    for clave, nombre in (("base_monetaria", "la base monetaria"), ("m2", "el M2")):
        puntos = series.get(clave)
        variacion = transformations.variacion_interanual(puntos) if puntos else None
        if variacion is not None:
            variaciones.append((nombre, variacion, puntos[-1][0], puntos))
    if not variaciones:
        return None

    fecha_inflacion, valor_inflacion = inflacion[-1]
    crecieron = " y ".join(
        f"{nombre} {'creció' if variacion >= 0 else 'cayó'} {numero(abs(variacion))}% (al {fecha:%d/%m/%Y})"
        for nombre, variacion, fecha, _ in variaciones
    )

    def real(variacion: float, puntos) -> str:
        # La variación de hoy contra la última inflación, y la del mismo mes que esa
        # inflación: solo se afirma que creció o cayó si las dos cuentas coinciden.
        # Cerca del cruce, comparar meses distintos podría decir algo falso.
        diferencias = [variacion - valor_inflacion]
        alineada = _interanual_al(puntos, fecha_inflacion)
        if alineada is not None:
            diferencias.append(alineada - valor_inflacion)
        if all(d > TOLERANCIA_REAL for d in diferencias):
            return "creció"
        if all(d < -TOLERANCIA_REAL for d in diferencias):
            return "cayó"
        return "se mantuvo"

    reales = [(nombre, real(variacion, puntos)) for nombre, variacion, _, puntos in variaciones]
    if len(reales) == 2 and reales[0][1] == reales[1][1]:
        plural = {"creció": "crecieron", "cayó": "cayeron", "se mantuvo": "se mantuvieron"}[reales[0][1]]
        veredicto = f"las dos {plural}"
    else:
        veredicto = " y ".join(f"{nombre} {verbo}" for nombre, verbo in reales)
    return (
        f"En el último año {crecieron}, contra una inflación interanual de {numero(valor_inflacion)}% "
        f"en {mes_y_anio(fecha_inflacion)}: descontada la inflación, {veredicto}."
    )


def _valor_hace(puntos: list[tuple[date, float]], fecha: date, anios: int, tolerancia_dias: int) -> float | None:
    """El valor de la serie en la misma fecha de hace `anios` años (el último dato hasta ahí), o None.

    None si el dato más cercano está a más de `tolerancia_dias` de esa fecha: mejor
    no comparar que comparar contra otro momento.
    """
    referencia = (pd.Timestamp(fecha) - pd.DateOffset(years=anios)).date()
    previos = [(f, v) for f, v in puntos if f <= referencia]
    if not previos or (referencia - previos[-1][0]).days > tolerancia_dias:
        return None
    return previos[-1][1]


def _comparaciones(puntos: list[tuple[date, float]], fecha: date, tolerancia_dias: int, escala: float) -> tuple[list[str], list[int]]:
    """(textos "hace N años, USD X mil millones (+Y%)", años sin dato) para COMPARACIONES_ANIOS."""
    actual = puntos[-1][1]
    textos, sin_dato = [], []
    for anios in COMPARACIONES_ANIOS:
        antes = _valor_hace(puntos, fecha, anios, tolerancia_dias)
        if antes is None or antes <= 0:
            sin_dato.append(anios)
            continue
        cambio = (actual / antes - 1) * 100
        textos.append(f"hace {anios} años, USD {numero(antes / escala)} mil millones (hoy, {'+' if cambio >= 0 else '-'}{numero(abs(cambio))}%)")
    return textos, sin_dato


def _enumerar(numeros: list[int]) -> str:
    """[4, 8, 12] da '4, 8 y 12'."""
    textos = [str(n) for n in numeros]
    return textos[0] if len(textos) == 1 else ", ".join(textos[:-1]) + " y " + textos[-1]


def frase_deuda(series: dict, provisorios=frozenset()) -> str | None:
    """Deuda bruta del Tesoro y préstamos al sector privado, en dólares, con su comparación a 4, 8 y 12 años.

    Un renglón por indicador, separados por "\n".
    """
    renglones = []
    tesoro = series.get("deuda_bruta_tesoro")
    if tesoro:
        fecha, valor = tesoro[-1]
        texto = (
            f"Deuda bruta del Tesoro a fines de {mes_y_anio(fecha)}{' (dato provisorio)' if fecha in provisorios else ''}: "
            f"USD {numero(valor / 1e3)} mil millones"
        )
        hace_un_anio = _valor_hace(tesoro, fecha, 1, 40)
        if hace_un_anio is not None:
            diferencia = (valor - hace_un_anio) / 1e3
            texto += f", {numero(abs(diferencia))} mil millones {'más' if diferencia >= 0 else 'menos'} que un año antes"
        comparaciones, sin_dato = _comparaciones(tesoro, fecha, 40, 1e3)
        if comparaciones:
            texto += ". Contra la misma fecha: " + "; ".join(comparaciones)
        if sin_dato:
            texto += f". Sin comparación a {_enumerar(sin_dato)} años"
            # El motivo, solo si es que la serie todavía no llega tan atrás
            if (pd.Timestamp(fecha) - pd.DateOffset(years=max(sin_dato))).date() < tesoro[0][0]:
                texto += f": la serie mensual de la Secretaría de Finanzas empieza en {tesoro[0][0].year}"
        renglones.append(texto + ".")

    prestamos, cambio = series.get("prestamos_sector_privado"), series.get("tipo_cambio_mayorista")
    if prestamos and cambio:
        en_dolares = transformations.a_dolares(prestamos, cambio)
        if not en_dolares.empty:
            ultimo = en_dolares.iloc[-1]
            texto = (f"Lo que familias y empresas les deben a los bancos, al {ultimo['Fecha']:%d/%m/%Y}: "
                     f"USD {numero(ultimo['usd'] / 1e3)} mil millones")
            puntos_usd = [(f.date(), float(v)) for f, v in zip(en_dolares["Fecha"], en_dolares["usd"])]
            comparaciones, _ = _comparaciones(puntos_usd, ultimo["Fecha"].date(), 15, 1e3)
            if comparaciones:
                texto += (". Contra la misma fecha: " + "; ".join(comparaciones)
                          + ". Con cepo, el dólar oficial estaba muy por debajo del paralelo, así que en dólares "
                          "esos años se ven más altos de lo que eran")
            renglones.append(texto + ".")
    return "\n".join(renglones) or None


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
