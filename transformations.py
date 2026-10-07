"""Armado de la fila del día, validación y cálculos sobre el histórico.

Son las celdas 21 a 34 del notebook, convertidas en funciones puras: reciben
DataFrames y devuelven DataFrames nuevos, sin red, sin base y sin archivos.
"""

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from fechas import mes_abreviado
from models import COLUMNAS_FILA, FilaMacro


@dataclass(frozen=True)
class ResultadosScraping:
    """Lo que devuelve scrapers.run_all_sync(), con nombre en vez de posición."""

    bna: dict
    dolarhoy: dict
    ambito: dict
    riesgo_pais: dict
    bcra: dict
    fed: dict


def armar_fila_nueva(res: ResultadosScraping, fecha: date) -> pd.DataFrame:
    """La fila del día, con las columnas en el orden de la tabla (celdas 24 a 29)."""
    fila = {
        "Fecha": fecha,
        "TCC_Blue": res.dolarhoy["TCC_Blue"],
        "TCV_Blue": res.dolarhoy["TCV_Blue"],
        "TCC_Billete": res.bna["TCC_Billete"],
        "TCV_Billete": res.bna["TCV_Billete"],
        "TCC_Divisas": res.bna["TCC_Divisas"],
        "TCV_Divisas": res.bna["TCV_Divisas"],
        "Solidario": res.bna["Solidario"],
        "TCV_MEP": res.ambito["TCV_MEP"],
        "riesgo_pais": res.riesgo_pais["riesgo_pais"],
        "TCC_Euro": res.ambito["TCC_Euro"],
        "TCV_Euro": res.ambito["TCV_Euro"],
        "fed_tea": res.fed["fed_tea"],
        "bcra_tea": res.bcra["bcra_tea"],
    }
    return pd.DataFrame([fila], columns=COLUMNAS_FILA)


def validar_fila(fila: pd.DataFrame) -> FilaMacro:
    """El contrato de models.FilaMacro. Levanta pydantic.ValidationError si no se cumple."""
    return FilaMacro(**fila.iloc[0].to_dict())


def avisos_de_frescura(res: ResultadosScraping, fecha: date) -> list[str]:
    """Fuentes cuyo último dato publicado no es de hoy (celdas 21 y 28).

    No es un error: el riesgo país sale con un día hábil de rezago y la BADLAR con
    dos. Se informa para que el desfase quede a la vista y no se repita en silencio.
    """
    avisos = []
    if res.bcra["bcra_tea_fecha"] != fecha:
        avisos.append(f"BCRA: la última TEA publicada es del {res.bcra['bcra_tea_fecha']}, no de hoy")
    if res.riesgo_pais["riesgo_pais_fecha"] != fecha:
        avisos.append(f"Riesgo país: el último dato publicado es del {res.riesgo_pais['riesgo_pais_fecha']}, no de hoy")
    return avisos


def sumar_al_historico(fila: pd.DataFrame, historico: pd.DataFrame) -> pd.DataFrame:
    """La fila nueva arriba del histórico, que viene más nuevo primero (celda 32)."""
    return pd.concat([fila, historico]).reset_index(drop=True)


def forwards_fisher(df: pd.DataFrame) -> tuple[float, float]:
    """Paridad de tasas de Irving Fisher a 3 meses: (forward oficial, forward blue).

    Celda 33. Toma la fila más nueva y tiene que correr antes de que las TEA se
    pasen a texto para el mail.
    """
    division = (1 + float(df["bcra_tea"].iloc[0]) / 100) / (1 + float(df["fed_tea"].iloc[0]) / 100)
    return float(df["TCV_Billete"].iloc[0]) * division, float(df["TCV_Blue"].iloc[0]) * division


def agregar_brechas_y_variaciones(df: pd.DataFrame) -> pd.DataFrame:
    """Brechas contra el blue y variación diaria de solidario, blue y euro (celda 34).

    pct_change(periods=-1) compara cada fila con la siguiente, que es el día
    anterior porque el DataFrame viene más nuevo primero.
    """
    df = df.copy()
    df["Solidario / TCV Blue"] = df["Solidario"] / df["TCV_Blue"] - 1
    df["TCV MEP / TCV Blue"] = df["TCV_MEP"] / df["TCV_Blue"] - 1
    df["TCV Euro / TCC Blue %"] = df["TCV_Euro"] / df["TCV_Blue"] - 1

    # Forward fill para los huecos de las series más viejas
    for col in ["Solidario", "TCV_Blue", "TCV_Euro"]:
        df[col] = df[col].ffill()

    df["Variación Solidario"] = df["Solidario"].pct_change(periods=-1).fillna(0)
    df["Variación TCV Blue"] = df["TCV_Blue"].pct_change(periods=-1).fillna(0)
    df["Variación TCV Euro"] = df["TCV_Euro"].pct_change(periods=-1).fillna(0)
    return df


def serie_inflacion(inflacion_mensual: list[tuple[date, float]]) -> pd.DataFrame:
    """Serie completa de inflación con los acumulados de 2, 3 y 12 meses (celda 21).

    Ascendente, con Fecha como datetime. inflacion_mensual es la lista (fecha, valor)
    que devuelve scrapers.bcra, ya ordenada de más vieja a más nueva, que es el orden
    que necesitan los rolling.
    """
    inflacion = pd.DataFrame(inflacion_mensual, columns=["Fecha", "Inflación Mensual"])
    inflacion["Fecha"] = pd.to_datetime(inflacion["Fecha"])

    factor = inflacion["Inflación Mensual"] / 100 + 1
    inflacion["Inflación Bimestral"] = (factor.rolling(2).apply(np.prod, raw=True) - 1) * 100
    inflacion["Inflación Trimestral"] = (factor.rolling(3).apply(np.prod, raw=True) - 1) * 100
    inflacion["Inflación Anual"] = (factor.rolling(12, min_periods=12).apply(np.prod, raw=True) - 1) * 100
    return inflacion


def ultimos_meses(inflacion: pd.DataFrame, meses: int = 12) -> pd.DataFrame:
    """Los últimos `meses` de la serie, de más viejo a más nuevo."""
    return inflacion.iloc[-meses:]


def etiqueta_mes(fecha) -> str:
    """'sep/2025': el rótulo de mes del gráfico y de la tabla de inflación."""
    return f"{mes_abreviado(fecha).replace('.', '')}/{fecha.year}"


# ── Series monetarias (fase 3) ───────────────────────────────────────────────

# Días sin dato nuevo a partir de los cuales una serie se considera atrasada. El
# BCRA publica las diarias con dos o tres días hábiles de rezago y el M3 mensual
# con unos dos meses.
MAX_REZAGO_DIAS = {"D": 10, "M": 75}


def validar_serie(serie, puntos: list[tuple[date, float]], hoy: date) -> list[str]:
    """Levanta ValueError si la serie viene rota; devuelve avisos si viene atrasada.

    `serie` es un scrapers.agregados.Serie. Rota es: vacía, con fechas repetidas o
    desordenadas, con valores no finitos, o un stock con valores <= 0.
    """
    if not puntos:
        raise ValueError(f"{serie.clave}: la API no devolvió puntos")

    fechas = [f for f, _ in puntos]
    if any(b <= a for a, b in zip(fechas, fechas[1:])):
        raise ValueError(f"{serie.clave}: fechas repetidas o desordenadas")

    for fecha, valor in puntos:
        if not math.isfinite(valor):
            raise ValueError(f"{serie.clave}: valor no finito el {fecha}")
        if serie.positiva and valor <= 0:
            raise ValueError(f"{serie.clave}: valor no positivo ({valor}) el {fecha}")

    rezago = (hoy - fechas[-1]).days
    if rezago > MAX_REZAGO_DIAS[serie.frecuencia]:
        return [f"{serie.nombre}: el último dato es del {fechas[-1]} ({rezago} días)"]
    return []


def variacion_interanual(puntos: list[tuple[date, float]]) -> float | None:
    """Variación % del último valor contra el último publicado un año antes o más."""
    if not puntos:
        return None
    fecha, valor = puntos[-1]
    hace_un_anio = (pd.Timestamp(fecha) - pd.DateOffset(years=1)).date()
    previos = [v for f, v in puntos if f <= hace_un_anio]
    if not previos or previos[-1] == 0:
        return None
    return (valor / previos[-1] - 1) * 100


def serie_a_frame(puntos: list[tuple[date, float]], nombre: str = "valor") -> pd.DataFrame:
    """(fecha, valor) a DataFrame con Fecha datetime, ascendente."""
    df = pd.DataFrame(puntos, columns=["Fecha", nombre])
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df.sort_values("Fecha").reset_index(drop=True)


def a_dolares(puntos: list[tuple[date, float]], tipo_cambio: list[tuple[date, float]]) -> pd.DataFrame:
    """Una serie en pesos pasada a dólares fecha por fecha, con el tipo de cambio vigente ese día.

    Para cada fecha toma el último tipo de cambio publicado hasta esa fecha
    (merge_asof hacia atrás), así un día sin cotización usa la anterior. Devuelve
    Fecha, valor (en pesos), tipo_cambio y usd, en la misma escala que el valor:
    millones de ARS dan millones de USD. Las fechas anteriores al primer tipo de
    cambio quedan afuera.
    """
    serie = serie_a_frame(puntos)
    cambio = serie_a_frame(tipo_cambio, "tipo_cambio")
    cruce = pd.merge_asof(serie, cambio, on="Fecha", direction="backward").dropna(subset=["tipo_cambio"])
    cruce["usd"] = cruce["valor"] / cruce["tipo_cambio"]
    return cruce.reset_index(drop=True)


def interanual_por_fecha(puntos: list[tuple[date, float]]) -> pd.DataFrame:
    """Para cada fecha, la variación % contra el último dato de un año antes o más.

    Sirve igual para series diarias y mensuales: merge_asof busca, para cada
    fecha, la observación más reciente que no pase de la misma fecha del año
    anterior, así los feriados y fines de semana no dejan huecos.
    """
    df = serie_a_frame(puntos)
    df["Referencia"] = df["Fecha"] - pd.DateOffset(years=1)
    previo = df[["Fecha", "valor"]].rename(columns={"Fecha": "Referencia", "valor": "valor_previo"})
    cruce = pd.merge_asof(df.sort_values("Referencia"), previo, on="Referencia", direction="backward")
    cruce = cruce.sort_values("Fecha").reset_index(drop=True)
    cruce["interanual"] = (cruce["valor"] / cruce["valor_previo"] - 1) * 100
    return cruce[["Fecha", "valor", "interanual"]]
