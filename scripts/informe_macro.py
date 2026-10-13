"""Informe macro de Argentina en PDF: la historia y el presente de los indicadores del reporte.

Un documento de varias páginas, con el estilo de GlobalAIze, que analiza con toda
la historia disponible los tipos de cambio y su brecha, el dólar real, la
inflación, las tasas, el riesgo país, el dinero, la deuda y, aparte, Bitcoin.
Pensado para hacerse una vez y repetirse cada tanto (por ejemplo, cada trimestre).

Uso:
    python scripts/informe_macro.py --salida DIR             # baja todo y arma el PDF
    python scripts/informe_macro.py --bajar DIR               # solo baja los datos a DIR
    python scripts/informe_macro.py --datos DIR --salida DIR  # arma el PDF con datos ya bajados

Fuentes: Fact_Mercado_Macro y Fact_Series_Macro (Supabase, solo lectura), Bluelytics
(historia del blue desde 2011: en la tabla, antes de octubre de 2022, el blue es un
valor de relleno), la FRED (inflación de Estados Unidos, para el dólar real) y
Yahoo Finance (Bitcoin). Solo lee: no escribe en la base ni manda nada.

Los números salen de las series; los textos del análisis están en la plantilla
(reporte/templates/informe_macro.html) y conviene releerlos en cada edición.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from reporte import indicadores  # noqa: E402

# ── Estilo GlobalAIze ─────────────────────────────────────────────────────────
MARINO = "#081E40"
AZUL = "#1F6391"
GRIS = "#697E91"
CELESTE = "#8FB3D9"
CLARO = "#E7F2F8"
ROJO = "#C0392B"
VERDE = "#1E8449"
NARANJA_BTC = "#F7931A"  # el único naranja: el color de marca de Bitcoin

URL_BLUELYTICS = "https://api.bluelytics.com.ar/v2/evolution.json"
INICIO_GOBIERNO = pd.Timestamp("2023-12-10")
# El dólar real se compara desde 2016: entre 2007 y 2015 el IPC oficial (INDEC intervenido)
# subestimaba la inflación y deprime artificialmente el índice de esos años
INICIO_TCR = "2016"
# Los días del blue propio que no coinciden con Bluelytics por más de esto se toman de Bluelytics
TOLERANCIA_BLUE = 0.05

# Comercio exterior (INDEC, por la API de series de tiempo del Estado), en millones de USD:
# bienes mensual (exportaciones FOB, importaciones y saldo) y servicios trimestral del balance de pagos
URL_SERIES = "https://apis.datos.gob.ar/series/api/series/"
SERIES_BIENES = {"expo": "77.3_IET_0_A_25", "impo": "78.3_IIT_0_A_25", "saldo": "79.3_ISCT_0_A_27"}
SERIES_SERVICIOS = {"ingresos": "160.2_CTA_CORIOS_0_T_52", "egresos": "160.2_CTA_CORIOS_0_T_51", "saldo": "160.2_CTA_CORIOS_0_T_49"}

# Bitcoin: los halvings (cada 210.000 bloques la recompensa por bloque se reduce a la mitad)
HALVINGS = [("2012-11-28", 210_000), ("2016-07-09", 420_000), ("2020-05-11", 630_000), ("2024-04-20", 840_000)]
URL_ALTURA = "https://mempool.space/api/blocks/tip/height"
MINUTOS_POR_BLOQUE = 10

COMPARACIONES_ANIOS = (4, 8, 12)


def num(valor: float, decimales: int = 1) -> str:
    return indicadores.numero(valor, decimales)


def signo(valor: float, decimales: int = 1) -> str:
    return ("+" if valor >= 0 else "-") + num(abs(valor), decimales)


def mes_anio(fecha) -> str:
    return indicadores.mes_y_anio(pd.Timestamp(fecha).date())


# ── Datos ─────────────────────────────────────────────────────────────────────

def bajar(destino: Path) -> None:
    """Baja todas las fuentes a `destino`. Supabase en una transacción de solo lectura."""
    import httpx
    import yfinance as yf
    from sqlalchemy import text

    from reporte import data_access
    from reporte.config import settings
    from reporte.scrapers import fed

    destino.mkdir(parents=True, exist_ok=True)
    with data_access.crear_engine().connect() as con:
        con.execute(text("SET TRANSACTION READ ONLY"))
        pd.read_sql(text('SELECT * FROM "Fact_Mercado_Macro" ORDER BY "Fecha"'), con).to_pickle(destino / "diario.pkl")
        pd.read_sql(text('SELECT serie, "Fecha", valor, frecuencia, unidad FROM "Fact_Series_Macro" '
                         'ORDER BY serie, "Fecha"'), con).to_pickle(destino / "series.pkl")
    (destino / "bluelytics.json").write_bytes(httpx.get(URL_BLUELYTICS, timeout=60).content)
    clave = settings.fed_api_key
    clave = clave.get_secret_value() if hasattr(clave, "get_secret_value") else clave
    r = httpx.get(fed.API_URL, params={"series_id": "CPIAUCSL", "api_key": clave, "file_type": "json",
                                       "observation_start": "2000-01-01"}, timeout=60)
    r.raise_for_status()
    obs = pd.DataFrame(r.json()["observations"])
    obs = obs[obs["value"] != "."]
    pd.Series(obs["value"].astype(float).values, index=pd.to_datetime(obs["date"])).to_pickle(destino / "cpi_usa.pkl")
    btc = yf.download("BTC-USD", start="2014-01-01", progress=False, auto_adjust=True)
    if isinstance(btc.columns, pd.MultiIndex):
        btc.columns = btc.columns.get_level_values(0)
    btc[["Close"]].to_pickle(destino / "btc.pkl")
    for nombre, ids in (("bienes", SERIES_BIENES), ("servicios", SERIES_SERVICIOS)):
        r = httpx.get(URL_SERIES, params={"ids": ",".join(ids.values()), "limit": 5000, "format": "json"}, timeout=60)
        r.raise_for_status()
        pd.DataFrame(r.json()["data"], columns=["Fecha", *ids]).to_pickle(destino / f"{nombre}.pkl")
    altura = int(httpx.get(URL_ALTURA, timeout=30).text)
    (destino / "bloque.json").write_text(json.dumps({"altura": altura}), encoding="utf-8")


def _por_fecha(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df.set_index("Fecha").sort_index().astype(float)


def cargar(carpeta: Path) -> dict:
    """Las series limpias, listas para el análisis."""
    diario = pd.read_pickle(carpeta / "diario.pkl")
    diario["Fecha"] = pd.to_datetime(diario["Fecha"])
    diario = diario.set_index("Fecha").sort_index()
    largas = pd.read_pickle(carpeta / "series.pkl")
    largas["Fecha"] = pd.to_datetime(largas["Fecha"])
    S = {k: g.set_index("Fecha")["valor"].sort_index() for k, g in largas.groupby("serie")}

    # Blue: Bluelytics hasta que la tabla tiene datos reales (antes es un valor fijo de relleno)
    bl = pd.DataFrame(json.loads((carpeta / "bluelytics.json").read_text(encoding="utf-8")))
    bl["date"] = pd.to_datetime(bl["date"])
    blue_bl = bl[bl["source"] == "Blue"].set_index("date")["value_sell"].sort_index()
    propio = diario["TCV_Blue"].dropna()
    real_desde = propio[propio.ne(propio.shift())].index[1]  # el primer cambio: antes, relleno
    propio = propio.loc[real_desde:]
    cruce = propio.to_frame("p").join(blue_bl.rename("b"), how="left")
    distinto = (cruce["p"] / cruce["b"] - 1).abs() > TOLERANCIA_BLUE
    superpuestos = int(cruce["b"].notna().sum())
    propio = propio.where(~distinto, cruce["b"])
    blue = pd.concat([blue_bl.loc[: real_desde - pd.Timedelta(days=1)], propio]).sort_index()

    # MEP: fuera los valores que se alejan más de 50% de la mediana de la semana (errores de carga)
    mep = diario["TCV_MEP"].dropna()
    mediana = mep.rolling(7, center=True, min_periods=3).median()
    mep_malos = mep[(mep / mediana - 1).abs() > 0.5]
    mep = mep.drop(mep_malos.index)

    return {
        "diario": diario, "S": S, "blue": blue, "blue_real_desde": real_desde, "blue_corregidos": int(distinto.sum()), "blue_superpuestos": superpuestos,
        "mep": mep, "mep_malos": mep_malos, "mayorista": S["tipo_cambio_mayorista"],
        "riesgo": diario["riesgo_pais"].dropna(), "badlar": diario["bcra_tea"].dropna(), "fed": diario["fed_tea"].dropna(),
        "cpi_usa": pd.read_pickle(carpeta / "cpi_usa.pkl"), "btc": pd.read_pickle(carpeta / "btc.pkl")["Close"].dropna(),
        "bienes": _por_fecha(pd.read_pickle(carpeta / "bienes.pkl")),
        "servicios": _por_fecha(pd.read_pickle(carpeta / "servicios.pkl")),
        "altura": json.loads((carpeta / "bloque.json").read_text(encoding="utf-8"))["altura"],
    }


# ── Métricas ──────────────────────────────────────────────────────────────────

def _valor_al(serie: pd.Series, fecha) -> float:
    previos = serie.loc[:fecha]
    return float(previos.iloc[-1]) if len(previos) else float("nan")


def _var(serie: pd.Series, desde, hasta=None) -> float:
    fin = serie.iloc[-1] if hasta is None else _valor_al(serie, hasta)
    return (fin / _valor_al(serie, desde) - 1) * 100


def ipc_mensual(S: dict) -> pd.Series:
    """Índice de precios a fin de cada mes, desde la inflación mensual."""
    im = S["inflacion_mensual"]
    indice = (1 + im / 100).cumprod()
    indice.index = indice.index.to_period("M")
    return indice


def calcular(d: dict) -> dict:
    S, hoy = d["S"], d["diario"].index[-1]
    m: dict = {"hoy": hoy, "fecha": f"{hoy:%d/%m/%Y}", "mes_anio": mes_anio(hoy)}
    blue, may, mep, rp = d["blue"], d["mayorista"], d["mep"], d["riesgo"]

    # Tipos de cambio y variaciones
    filas = []
    inicio_anio = pd.Timestamp(year=hoy.year, month=1, day=1) - pd.Timedelta(days=1)
    for nombre, serie in [("Dólar blue", blue), ("Mayorista (A3500)", may), ("Dólar MEP", mep),
                          ("Billete BNA", d["diario"]["TCV_Billete"].dropna())]:
        filas.append({
            "nombre": nombre, "valor": num(serie.iloc[-1], 2),
            "m1": _var(serie, hoy - pd.DateOffset(months=1)), "m3": _var(serie, hoy - pd.DateOffset(months=3)),
            "anio": _var(serie, inicio_anio), "m12": _var(serie, hoy - pd.DateOffset(years=1)),
            "gob": _var(serie, INICIO_GOBIERNO),
        })
    m["variaciones"] = filas
    m["m12_min"], m["m12_max"] = min(f["m12"] for f in filas), max(f["m12"] for f in filas)

    brecha = (blue.to_frame("b").join(may.rename("m"), how="inner").eval("b / m - 1") * 100).dropna()
    m["brecha_serie"] = brecha
    m["brecha_hoy"] = brecha.iloc[-1]
    m["brecha_max"], m["brecha_max_fecha"] = brecha.loc["2011":].max(), brecha.loc["2011":].idxmax()
    m["brecha_oct23"] = _valor_al(brecha, "2023-10-31")
    m["brecha_prom_cepo"] = brecha.loc["2019-09-01":"2023-12-10"].mean()

    # Inflación
    im, ia = S["inflacion_mensual"], S["inflacion_interanual"]
    m["inf_mensual"], m["inf_mensual_mes"] = im.iloc[-1], mes_anio(im.index[-1])
    m["inf_mensual_previa"] = im.iloc[-2]
    m["inf_anual"], m["inf_anual_mes"] = ia.iloc[-1], mes_anio(ia.index[-1])
    pico = ia.loc["2020":]
    m["inf_pico"], m["inf_pico_mes"] = pico.max(), mes_anio(pico.idxmax())
    m["inf_hiper"], m["inf_hiper_mes"] = ia.max(), mes_anio(ia.idxmax())
    anual = ((1 + im / 100).groupby(im.index.year).prod() - 1) * 100
    m["inf_por_anio"] = [(int(a), v, a == im.index[-1].year) for a, v in anual.loc[2016:].items()]
    m["inf_anio_en_curso_meses"] = int(im.index[-1].month)
    ult12 = im.iloc[-12:]
    m["inf_prom_12"] = ((1 + ult12 / 100).prod() ** (1 / 12) - 1) * 100
    m["inf_6m"] = ((1 + im.iloc[-6:] / 100).prod() ** (1 / 6) - 1) * 100

    # Carrera desde el cambio de gobierno: precios contra dólares
    ipc = ipc_mensual(S)
    base_ipc = ipc[pd.Period("2023-11", "M")]
    m["carrera_ipc"] = (ipc.iloc[-1] / base_ipc - 1) * 100
    m["carrera_ipc_hasta"] = mes_anio(im.index[-1])
    m["carrera_may"] = _var(may, "2023-11-30", im.index[-1])
    m["carrera_blue"] = _var(blue, "2023-11-30", im.index[-1])
    m["poder_blue"] = ((1 + m["carrera_blue"] / 100) / (1 + m["carrera_ipc"] / 100) - 1) * 100
    m["poder_may"] = ((1 + m["carrera_may"] / 100) / (1 + m["carrera_ipc"] / 100) - 1) * 100
    m["carrera_hasta"] = im.index[-1]

    # Dólar real: A3500 por inflación de EEUU sobre inflación argentina, mes contra mes
    usa = d["cpi_usa"].copy()
    usa.index = usa.index.to_period("M")
    may_m = may.resample("ME").mean()
    may_m.index = may_m.index.to_period("M")
    tcr = (may_m * usa / ipc).dropna()
    tcr = tcr / tcr.iloc[-1] * 100
    m["tcr_serie"], m["tcr_ultimo_mes"] = tcr, mes_anio(tcr.index[-1].to_timestamp())
    m["tcr_mediana"] = tcr.loc[INICIO_TCR:].median()
    m["tcr_dic23"] = tcr[pd.Period("2023-12", "M")]
    m["tcr_nov23"] = tcr[pd.Period("2023-11", "M")]
    m["tcr_2017"] = tcr.loc["2017"].mean()
    m["tcr_max"], m["tcr_max_mes"] = tcr.loc[INICIO_TCR:].max(), mes_anio(tcr.loc[INICIO_TCR:].idxmax().to_timestamp())
    m["tcr_min"], m["tcr_min_mes"] = tcr.loc[INICIO_TCR:].min(), mes_anio(tcr.loc[INICIO_TCR:].idxmin().to_timestamp())
    m["tcr_percentil"] = (tcr.loc[INICIO_TCR:] < 100).mean() * 100
    rebote = tcr.loc["2025":]
    m["tcr_rebote"], m["tcr_rebote_mes"] = rebote.max(), mes_anio(rebote.idxmax().to_timestamp())

    # Tasas
    bad = d["badlar"]
    badm = bad.resample("ME").mean().to_frame("badlar").join(ia.rename("inf"), how="inner")
    badm["real"] = ((1 + badm.badlar / 100) / (1 + badm.inf / 100) - 1) * 100
    m["tasas_serie"] = badm
    m["badlar"], m["badlar_mensual"] = bad.iloc[-1], ((1 + bad.iloc[-1] / 100) ** (1 / 12) - 1) * 100
    m["tasa_real"], m["tasa_real_mes"] = badm["real"].iloc[-1], mes_anio(badm.index[-1])
    m["tasa_real_min"], m["tasa_real_min_mes"] = badm["real"].min(), mes_anio(badm["real"].idxmin())
    m["tasa_real_hoy"] = ((1 + bad.iloc[-1] / 100) / (1 + ia.iloc[-1] / 100) - 1) * 100
    m["inf_6m_anual"] = ((1 + m["inf_6m"] / 100) ** 12 - 1) * 100
    m["tasa_real_adelante"] = ((1 + bad.iloc[-1] / 100) / (1 + m["inf_6m_anual"] / 100) - 1) * 100
    m["fed"] = d["fed"].iloc[-1]
    m["badlar_desde"] = mes_anio(bad.index[0])

    # Riesgo país
    m["rp"], m["rp_max"], m["rp_max_fecha"] = rp.iloc[-1], rp.max(), rp.idxmax()
    m["rp_min"], m["rp_min_fecha"] = rp.min(), rp.idxmin()
    m["rp_min_reciente"], m["rp_min_reciente_fecha"] = rp.loc["2019":].min(), rp.loc["2019":].idxmin()
    m["rp_nov23"] = _valor_al(rp, "2023-11-17")
    m["rp_hace_1"] = _valor_al(rp, hoy - pd.DateOffset(years=1))
    m["rp_30d_min"], m["rp_30d_max"] = rp.loc[hoy - pd.Timedelta(days=30):].min(), rp.loc[hoy - pd.Timedelta(days=30):].max()

    # Dinero real (contra la inflación, mes contra mismo mes del año anterior)
    def real_yoy(serie):
        x = serie.resample("ME").last()
        x.index = x.index.to_period("M")
        r = (x / ipc).dropna()
        return ((r / r.shift(12) - 1) * 100).dropna()
    m["base_real"], m["m2_real"], m["prest_real"] = real_yoy(S["base_monetaria"]), real_yoy(S["m2"]), real_yoy(S["prestamos_sector_privado"])

    # En dólares, con el mayorista de cada día
    def en_usd(clave):
        x = S[clave].to_frame("v").join(may.rename("tc"), how="inner")
        return (x["v"] / x["tc"] / 1e3).dropna()  # millones de pesos / tc / 1e3 = miles de millones de USD
    m["prest_usd"] = en_usd("prestamos_sector_privado")
    m["base_usd"] = en_usd("base_monetaria")
    m["letras_usd"] = (en_usd("letras_bcra_pesos").add(en_usd("letras_bcra_moneda_extranjera"), fill_value=0))
    m["adelantos_usd"] = en_usd("adelantos_transitorios")
    pu = m["prest_usd"]
    m["prest_hoy"], m["prest_dic23"] = pu.iloc[-1], _valor_al(pu, "2023-12-31")
    m["prest_max_previo"] = pu.loc[:"2023-12-31"].max()
    m["prest_max_previo_fecha"] = pu.loc[:"2023-12-31"].idxmax()
    m["letras_max"], m["letras_max_fecha"], m["letras_hoy"] = m["letras_usd"].max(), m["letras_usd"].idxmax(), m["letras_usd"].iloc[-1]
    m["adelantos_max"], m["adelantos_max_fecha"], m["adelantos_hoy"] = m["adelantos_usd"].max(), m["adelantos_usd"].idxmax(), m["adelantos_usd"].iloc[-1]
    prest_m = S["prestamos_sector_privado"].resample("ME").last()
    prest_m.index = prest_m.index.to_period("M")
    prest_real = (prest_m / ipc).dropna()
    m["prest_real_vs_dic23"] = prest_real.iloc[-1] / prest_real[pd.Period("2023-12", "M")]
    m["prest_real_vs_2017"] = (prest_real.iloc[-1] / prest_real[pd.Period("2017-12", "M")] - 1) * 100
    m["base_real_ult"], m["m2_real_ult"], m["prest_real_ult"] = m["base_real"].iloc[-1], m["m2_real"].iloc[-1], m["prest_real"].iloc[-1]
    m["dinero_mes"] = mes_anio(m["m2_real"].index[-1].to_timestamp())

    # Deuda bruta del Tesoro (millones de USD a fin de mes)
    db = S["deuda_bruta_tesoro"] / 1e3
    m["deuda_serie"] = db
    m["deuda"], m["deuda_mes"] = db.iloc[-1], mes_anio(db.index[-1])
    m["deuda_dic23"], m["deuda_dic19"] = _valor_al(db, "2023-12-31"), _valor_al(db, "2019-12-31")
    m["deuda_hace_1"] = _valor_al(db, db.index[-1] - pd.DateOffset(years=1))

    # Bitcoin
    btc = d["btc"]
    m["btc"], m["btc_fecha"] = btc.iloc[-1], btc.index[-1]
    m["btc_ath"], m["btc_ath_fecha"] = btc.max(), btc.idxmax()
    m["btc_dd"] = (btc.iloc[-1] / btc.max() - 1) * 100
    m["btc_12m"] = _var(btc, btc.index[-1] - pd.DateOffset(years=1))
    m["btc_anio"] = _var(btc, pd.Timestamp(year=btc.index[-1].year, month=1, day=1) - pd.Timedelta(days=1))
    retornos = btc.pct_change().dropna()
    m["btc_vol"] = retornos.iloc[-365:].std() * np.sqrt(365) * 100
    anual_btc = btc.resample("YE").last().pct_change().dropna() * 100
    anual_btc.iloc[-1] = m["btc_anio"]
    m["btc_por_anio"] = [(int(a.year), v) for a, v in anual_btc.loc["2015":].items()]
    # Bitcoin en pesos (blue), contra el dólar
    btc_ars = (btc.to_frame("b").join(blue.rename("bl"), how="inner"))
    m["btc_ars_12m"] = _var(btc_ars["b"] * btc_ars["bl"], btc_ars.index[-1] - pd.DateOffset(years=1))
    m["blue_12m"] = _var(blue, hoy - pd.DateOffset(years=1))

    # Comercio exterior: bienes en sumas de 12 meses, servicios en sumas de 4 trimestres (miles de millones de USD)
    bienes, serv = d["bienes"], d["servicios"]
    b12 = bienes.rolling(12).sum().dropna() / 1e3
    s4 = serv.rolling(4).sum().dropna() / 1e3
    m["bienes12"], m["serv4"] = b12, s4
    m["bienes_mes"] = mes_anio(bienes.index[-1])
    m["serv_trim"] = f"{(serv.index[-1].month - 1) // 3 + 1}.º trimestre de {serv.index[-1].year}"
    m["expo12"], m["impo12"], m["saldo_bienes12"] = b12["expo"].iloc[-1], b12["impo"].iloc[-1], b12["saldo"].iloc[-1]
    hace1 = b12.loc[: b12.index[-1] - pd.DateOffset(years=1)].iloc[-1]
    m["expo12_var"] = (m["expo12"] / hace1["expo"] - 1) * 100
    m["impo12_var"] = (m["impo12"] / hace1["impo"] - 1) * 100
    m["saldo_bienes12_previo"] = hace1["saldo"]
    m["serv_ing4"], m["serv_egr4"], m["saldo_serv4"] = s4["ingresos"].iloc[-1], s4["egresos"].iloc[-1], s4["saldo"].iloc[-1]
    m["saldo_total"] = m["saldo_bienes12"] + m["saldo_serv4"]
    m["expo_record"], m["expo_record_fecha"] = b12["expo"].max(), b12["expo"].idxmax()

    # Hoy contra hace 4, 8 y 12 años
    ia, im_ = S["inflacion_interanual"], S["inflacion_mensual"]
    tcr_d = m["tcr_serie"].copy()
    tcr_d.index = tcr_d.index.to_timestamp(how="end")
    def al(serie, f, desde=None):
        if desde is not None and f < pd.Timestamp(desde):
            return None
        v = _valor_al(serie, f)
        return None if np.isnan(v) else v
    fechas = [hoy] + [hoy - pd.DateOffset(years=a) for a in COMPARACIONES_ANIOS]
    m["comp_fechas"] = ["Hoy"] + [f"Hace {a} años ({f:%m/%Y})" for a, f in zip(COMPARACIONES_ANIOS, fechas[1:])]
    filas_c = [
        ("Dólar oficial mayorista ($)", may, None, 2, "$"),
        ("Dólar blue ($)", blue, None, 2, "$"),
        ("Brecha blue contra oficial (%)", brecha, None, 1, "%"),
        ("Dólar real (índice, ago-2026 = 100)", tcr_d, INICIO_TCR, 0, ""),
        ("Inflación interanual (%) *", ia, None, 1, "%"),
        ("Inflación mensual (%)", im_, None, 1, "%"),
        ("Riesgo país (pb)", rp, None, 0, ""),
        ("Crédito privado (USD mil M)", m["prest_usd"], None, 1, ""),
        ("Base monetaria (USD mil M)", m["base_usd"], None, 1, ""),
        ("Deuda bruta del Tesoro (USD mil M)", db, None, 1, ""),
        ("Exportaciones de bienes, 12 meses (USD mil M)", b12["expo"], None, 1, ""),
        ("Importaciones de bienes, 12 meses (USD mil M)", b12["impo"], None, 1, ""),
        ("Saldo de bienes, 12 meses (USD mil M)", b12["saldo"], None, 1, ""),
        ("Bitcoin (USD)", d["btc"], None, 0, ""),
    ]
    m["comparaciones"] = [
        {"nombre": nombre, "valores": [None if (v := al(serie, f, desde)) is None else num(v, dec) for f in fechas]}
        for nombre, serie, desde, dec, _ in filas_c
    ]

    # Bitcoin: ciclos de halving y el próximo
    ciclos = []
    for i, (fecha, bloque) in enumerate(HALVINGS):
        f = pd.Timestamp(fecha)
        siguiente = pd.Timestamp(HALVINGS[i + 1][0]) if i + 1 < len(HALVINGS) else btc.index[-1]
        if f < btc.index[0]:
            ciclos.append({"fecha": f, "bloque": bloque, "con_datos": False})
            continue
        precio = _valor_al(btc, f)
        # El pico del ciclo: el máximo de los 24 meses posteriores (en los ciclos pasados llegó a los 17 o 18 meses)
        tramo = btc.loc[f:min(siguiente, f + pd.DateOffset(months=24))]
        pico, pico_f = tramo.max(), tramo.idxmax()
        un_anio = _valor_al(btc, f + pd.DateOffset(years=1)) if f + pd.DateOffset(years=1) <= btc.index[-1] else None
        ciclos.append({
            "fecha": f, "bloque": bloque, "con_datos": True, "precio": precio, "pico": pico, "pico_fecha": pico_f,
            "suba_pico": (pico / precio - 1) * 100, "meses_pico": (pico_f - f).days / 30.44,
            "suba_1": None if un_anio is None else (un_anio / precio - 1) * 100,
            "en_curso": i + 1 == len(HALVINGS),
        })
    m["halvings"] = ciclos
    ultimo = ciclos[-1]
    m["halving_actual_var"] = (btc.iloc[-1] / ultimo["precio"] - 1) * 100
    proximo_bloque = HALVINGS[-1][1] + 210_000
    faltan = proximo_bloque - d["altura"]
    m["altura"], m["proximo_bloque"], m["bloques_faltan"] = d["altura"], proximo_bloque, faltan
    m["dias_faltan"] = faltan * MINUTOS_POR_BLOQUE / 60 / 24
    m["proximo_halving"] = hoy + pd.Timedelta(days=m["dias_faltan"])

    # Tablero final: cada métrica con su estado, su tendencia a un año y el ideal
    def estado(valor, bien, regular, mayor_es_mejor=False):
        if mayor_es_mejor:
            return "bien" if valor >= bien else "regular" if valor >= regular else "mal"
        return "bien" if valor <= bien else "regular" if valor <= regular else "mal"
    tcr_desvio = (100 / m["tcr_mediana"] - 1) * 100
    deuda_var = (m["deuda"] / m["deuda_hace_1"] - 1) * 100
    hace_un_anio = hoy - pd.DateOffset(years=1)
    def tendencia(actual, previo, mayor_es_mejor=False):
        if previo is None or np.isnan(previo):
            return "="
        mejora = actual > previo if mayor_es_mejor else actual < previo
        return "▲ mejora" if mejora else "▼ empeora"
    m["tablero"] = [
        ("Brecha cambiaria", f"{num(m['brecha_hoy'])}%", estado(m["brecha_hoy"], 10, 30),
         tendencia(m["brecha_hoy"], _valor_al(brecha, hace_un_anio)), "Menos de 10%: un solo precio del dólar"),
        ("Inflación mensual", f"{num(m['inf_mensual'])}%", estado(m["inf_mensual"], 1, 2.5),
         tendencia(m["inf_mensual"], _valor_al(im_, hace_un_anio)), "Menos de 1% por mes (menos de 12% anual)"),
        ("Inflación interanual", f"{num(m['inf_anual'])}%", estado(m["inf_anual"], 15, 40),
         tendencia(m["inf_anual"], _valor_al(ia, hace_un_anio)), "Un dígito, como los países vecinos"),
        ("Tasa real (BADLAR)", f"{signo(m['tasa_real_hoy'])}%", estado(m["tasa_real_hoy"], 0, -5, mayor_es_mejor=True),
         tendencia(m["tasa_real_hoy"], m["tasas_serie"]["real"].iloc[-13] if len(m["tasas_serie"]) > 12 else None, True),
         "Levemente positiva: que ahorrar en pesos no pierda"),
        ("Riesgo país", f"{num(m['rp'], 0)} pb", estado(m["rp"], 500, 1000),
         tendencia(m["rp"], m["rp_hace_1"]), "Menos de 500 puntos"),
        ("Dólar real", f"{signo(tcr_desvio, 0)}% contra su mediana", estado(abs(tcr_desvio), 10, 25),
         "▼ se abarata" if m["tcr_serie"].iloc[-1] < m["tcr_serie"].iloc[-13] else "▲ se encarece", "Estable, cerca de su promedio"),
        ("Dinero real (M2)", f"{signo(m['m2_real_ult'])}% anual", estado(abs(m["m2_real_ult"]), 5, 15),
         tendencia(abs(m["m2_real_ult"]), abs(m["m2_real"].iloc[-13])), "Crecer al ritmo de la economía"),
        ("Crédito privado real", f"{signo(m['prest_real_ult'])}% anual", "bien" if 0 < m["prest_real_ult"] < 30 else "regular",
         tendencia(m["prest_real_ult"], m["prest_real"].iloc[-13], True), "Crecer sin que suba la mora"),
        ("Deuda bruta del Tesoro", f"{signo(deuda_var)}% en un año", estado(deuda_var, 0, 5),
         tendencia(m["deuda"], m["deuda_hace_1"]), "Crecer menos que la economía, o bajar"),
        ("Saldo comercial de bienes", f"USD {signo(m['saldo_bienes12'])} mil M", estado(m["saldo_bienes12"], 5, 0, mayor_es_mejor=True),
         tendencia(m["saldo_bienes12"], m["saldo_bienes12_previo"], True), "Positivo: entran más dólares de los que salen"),
        ("Saldo de servicios", f"USD {signo(m['saldo_serv4'])} mil M", estado(m["saldo_serv4"], 0, -5, mayor_es_mejor=True),
         tendencia(m["saldo_serv4"], s4["saldo"].iloc[-5] if len(s4) > 4 else None, True), "Cerca del equilibrio"),
    ]

    # Calidad de datos
    m["blue_real_desde"] = d["blue_real_desde"]
    m["blue_corregidos"] = d["blue_corregidos"]
    m["blue_superpuestos"] = d["blue_superpuestos"]
    m["mep_malos"] = [(f"{f:%d/%m/%Y}", num(v, 2)) for f, v in d["mep_malos"].items()]
    return m


# ── Gráficos ──────────────────────────────────────────────────────────────────

def _figura(alto: float = 3.4, ancho: float = 7.4, filas: int = 1, **kw):
    fig = Figure(figsize=(ancho, alto), dpi=200)
    ejes = fig.subplots(filas, 1, **kw)
    for ax in np.atleast_1d(ejes):
        ax.set_facecolor("white")
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        for lado in ("left", "bottom"):
            ax.spines[lado].set_color("#B8C4CF")
        ax.tick_params(colors="#3A4A5C", labelsize=8)
        ax.grid(axis="y", color="#E3EAF0", linewidth=0.8)
        ax.set_axisbelow(True)
    return fig, ejes


def _guardar(fig: Figure, ruta: Path) -> str:
    fig.tight_layout()
    fig.savefig(ruta, facecolor="white")
    return ruta.name


def _miles(x, _):
    return num(x, 0)


def _pct(x, _):
    return f"{num(x, 0)}%"


def _sombrear_cepo(ax):
    for desde, hasta in [("2011-10-31", "2015-12-16"), ("2019-09-01", "2025-04-14")]:
        ax.axvspan(pd.Timestamp(desde), pd.Timestamp(hasta), color=CLARO, zorder=0)


def graficos(d: dict, m: dict, carpeta: Path) -> dict:
    carpeta.mkdir(parents=True, exist_ok=True)
    g = {}
    blue, may = d["blue"], d["mayorista"]

    # 1. Blue y oficial, escala logarítmica
    fig, ax = _figura(2.8)
    _sombrear_cepo(ax)
    ax.plot(may.loc["2011":].index, may.loc["2011":], color=AZUL, lw=1.4, label="Oficial mayorista (A3500)")
    ax.plot(blue.index, blue, color=MARINO, lw=1.4, label="Blue")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(_miles))
    ax.set_ylabel("Pesos por dólar (escala log.)", fontsize=8, color="#3A4A5C")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.text(pd.Timestamp("2013-11-01"), ax.get_ylim()[1] * 0.6, "cepo", color=GRIS, fontsize=8, ha="center")
    ax.text(pd.Timestamp("2022-06-01"), ax.get_ylim()[1] * 0.6, "cepo", color=GRIS, fontsize=8, ha="center")
    g["cambio"] = _guardar(fig, carpeta / "cambio.png")

    # 2. Brecha
    b = m["brecha_serie"].loc["2011":]
    fig, ax = _figura(2.2)
    _sombrear_cepo(ax)
    ax.fill_between(b.index, b, 0, color=MARINO, alpha=0.85, lw=0)
    ax.yaxis.set_major_formatter(FuncFormatter(_pct))
    ax.set_ylabel("Brecha blue contra oficial", fontsize=8, color="#3A4A5C")
    ax.annotate(f"{num(m['brecha_max'], 0)}%\n{m['brecha_max_fecha']:%m/%Y}", (m["brecha_max_fecha"], m["brecha_max"]),
                xytext=(10, -5), textcoords="offset points", fontsize=7.5, color=MARINO)
    g["brecha"] = _guardar(fig, carpeta / "brecha.png")

    # 3. Dólar real
    t = m["tcr_serie"].loc[INICIO_TCR:]
    x = t.index.to_timestamp()
    fig, ax = _figura(3.0)
    ax.plot(x, t.values, color=MARINO, lw=1.5)
    ax.axhline(m["tcr_mediana"], color=GRIS, lw=1, ls="--")
    ax.text(x[3], m["tcr_mediana"] * 1.02, f"mediana 2016-hoy: {num(m['tcr_mediana'], 0)}", color=GRIS, fontsize=7.5)
    ax.axhline(100, color=AZUL, lw=0.8, ls=":")
    ax.set_ylabel(f"Dólar real ({m['tcr_ultimo_mes']} = 100)", fontsize=8, color="#3A4A5C")
    ax.annotate("dic-2023", (pd.Timestamp("2023-12-01"), m["tcr_dic23"]), xytext=(-55, 5), textcoords="offset points",
                fontsize=7.5, color=MARINO, arrowprops={"arrowstyle": "-", "color": GRIS, "lw": 0.6})
    g["tcr"] = _guardar(fig, carpeta / "tcr.png")

    # 4. Inflación reciente: mensual en barras, interanual en línea
    S = d["S"]
    im, ia = S["inflacion_mensual"].loc["2018":], S["inflacion_interanual"].loc["2018":]
    fig, ax = _figura(3.2)
    colores = [ROJO if v >= 10 else AZUL if v >= 4 else CELESTE for v in im]
    ax.bar(im.index, im, width=22, color=colores)
    ax.set_ylabel("Mensual (barras)", fontsize=8, color="#3A4A5C")
    ax.yaxis.set_major_formatter(FuncFormatter(_pct))
    ax2 = ax.twinx()
    ax2.plot(ia.index, ia, color=MARINO, lw=1.6)
    ax2.set_ylabel("Interanual (línea)", fontsize=8, color=MARINO)
    ax2.yaxis.set_major_formatter(FuncFormatter(_pct))
    ax2.tick_params(colors=MARINO, labelsize=8)
    for lado in ("top",):
        ax2.spines[lado].set_visible(False)
    g["inflacion"] = _guardar(fig, carpeta / "inflacion.png")

    # 5. Inflación larga, escala logarítmica
    il = S["inflacion_interanual"].loc["1944":]
    il = il.clip(lower=1)  # los meses con deflación (años 90) no entran en escala log.: se muestran en 1%
    fig, ax = _figura(2.6)
    ax.plot(il.index, il, color=MARINO, lw=1.1)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(_pct))
    ax.set_ylabel("Interanual (escala log.)", fontsize=8, color="#3A4A5C")
    for fecha, texto, dx, dy in [("1976-03-01", "Rodrigazo", -30, 14), ("1990-03-01", "Hiperinflación", 42, -2),
                                 ("2002-04-01", "Fin de la\nconvertibilidad", 10, 24), ("2024-04-01", "Pico 2024", -26, 10)]:
        f = pd.Timestamp(fecha)
        ax.annotate(texto, (f, il.loc[:f].max() if texto == "Hiperinflación" else _valor_al(il, f)), xytext=(dx, dy),
                    textcoords="offset points", fontsize=7, color=AZUL, ha="center",
                    arrowprops={"arrowstyle": "-", "color": CELESTE, "lw": 0.6})
    g["inflacion_larga"] = _guardar(fig, carpeta / "inflacion_larga.png")

    # 6. Carrera desde noviembre de 2023: precios, mayorista y blue
    ipc = ipc_mensual(S)
    ipcs = ipc.loc[pd.Period("2023-11", "M"):]
    ipcs = ipcs / ipcs.iloc[0] * 100
    def base100(serie):
        x = serie.resample("ME").last().loc["2023-11": m["carrera_hasta"]]
        return x / x.iloc[0] * 100
    fig, ax = _figura(2.7)
    ax.plot(ipcs.index.to_timestamp(how="end"), ipcs.values, color=ROJO, lw=1.8, label="Precios (IPC)")
    ax.plot(base100(may).index, base100(may), color=AZUL, lw=1.6, label="Dólar oficial mayorista")
    ax.plot(base100(blue).index, base100(blue), color=MARINO, lw=1.6, label="Dólar blue")
    ax.set_ylabel("Noviembre 2023 = 100", fontsize=8, color="#3A4A5C")
    ax.legend(frameon=False, fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"))
    g["carrera"] = _guardar(fig, carpeta / "carrera.png")

    # 7. Tasas: BADLAR contra inflación, y la tasa real
    tasas = m["tasas_serie"]
    fig, ax = _figura(2.6)
    ax.plot(tasas.index, tasas["badlar"], color=AZUL, lw=1.6, label="BADLAR (TEA)")
    ax.plot(tasas.index, tasas["inf"], color=ROJO, lw=1.6, label="Inflación interanual")
    ax.fill_between(tasas.index, tasas["badlar"], tasas["inf"], where=tasas["badlar"] >= tasas["inf"], color=VERDE, alpha=0.15, lw=0)
    ax.fill_between(tasas.index, tasas["badlar"], tasas["inf"], where=tasas["badlar"] < tasas["inf"], color=ROJO, alpha=0.12, lw=0)
    ax.yaxis.set_major_formatter(FuncFormatter(_pct))
    ax.legend(frameon=False, fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"))
    g["tasas"] = _guardar(fig, carpeta / "tasas.png")

    # 8. Riesgo país
    rp = d["riesgo"]
    fig, ax = _figura(3.1)
    ax.fill_between(rp.index, rp, 0, color=MARINO, alpha=0.12, lw=0)
    ax.plot(rp.index, rp, color=MARINO, lw=1)
    ax.yaxis.set_major_formatter(FuncFormatter(_miles))
    ax.set_ylabel("Puntos básicos", fontsize=8, color="#3A4A5C")
    for fecha, texto, dx, dy in [("2002-08-07", "Default 2001-02", 62, -6), ("2008-12-01", "Crisis global", 0, 26),
                                 ("2014-08-01", "Holdouts", 0, 30), ("2018-09-01", "Crisis 2018", -28, 38),
                                 ("2020-03-23", "Pandemia y\nreestructuración", -52, 6), ("2023-11-17", "Elecciones 2023", 30, 30)]:
        f = pd.Timestamp(fecha)
        ax.annotate(texto, (f, _valor_al(rp, f)), xytext=(dx, dy), textcoords="offset points", fontsize=6.8,
                    color=AZUL, ha="center", arrowprops={"arrowstyle": "-", "color": CELESTE, "lw": 0.6})
    g["riesgo"] = _guardar(fig, carpeta / "riesgo.png")

    # 9. Dinero real
    fig, ax = _figura(2.5)
    for serie, color, nombre in [(m["base_real"], AZUL, "Base monetaria"), (m["m2_real"], MARINO, "M2")]:
        s = serie.loc["2016":]
        ax.plot(s.index.to_timestamp(), s.values, color=color, lw=1.5, label=nombre)
    ax.axhline(0, color=GRIS, lw=0.8)
    ax.yaxis.set_major_formatter(FuncFormatter(_pct))
    ax.set_ylabel("Variación real interanual", fontsize=8, color="#3A4A5C")
    ax.legend(frameon=False, fontsize=8)
    g["dinero"] = _guardar(fig, carpeta / "dinero.png")

    # 10. Deuda bruta del Tesoro
    db = m["deuda_serie"]
    fig, ax = _figura(2.3)
    ax.bar(db.index, db, width=24, color=[MARINO if f.month == 12 else CELESTE for f in db.index])
    ax.set_ylim(0, db.max() * 1.08)
    ax.yaxis.set_major_formatter(FuncFormatter(_miles))
    ax.set_ylabel("Miles de millones de USD", fontsize=8, color="#3A4A5C")
    g["deuda"] = _guardar(fig, carpeta / "deuda.png")

    # 11. Crédito privado y deuda del BCRA, en dólares
    fig, ejes = _figura(3.6, filas=2, sharex=True)
    pu = m["prest_usd"].loc["2003":]
    ejes[0].fill_between(pu.index, pu, 0, color=VERDE, alpha=0.15, lw=0)
    ejes[0].plot(pu.index, pu, color=VERDE, lw=1.3)
    ejes[0].set_ylabel("Préstamos al sector\nprivado (miles de mill. USD)", fontsize=7.5, color="#3A4A5C")
    le, ad = m["letras_usd"].loc["2003":], m["adelantos_usd"].loc["2003":]
    ejes[1].plot(le.index, le, color=MARINO, lw=1.3, label="Letras del BCRA")
    ejes[1].plot(ad.index, ad, color=ROJO, lw=1.3, label="Adelantos transitorios al Tesoro")
    ejes[1].set_ylabel("Miles de mill. USD", fontsize=7.5, color="#3A4A5C")
    ejes[1].legend(frameon=False, fontsize=7.5)
    g["credito"] = _guardar(fig, carpeta / "credito.png")

    # 12. Bitcoin: precio en escala log. y caída desde el máximo
    btc = d["btc"]
    fig, ejes = _figura(4.0, filas=2, sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    ejes[0].plot(btc.index, btc, color=NARANJA_BTC, lw=1.1)
    ejes[0].set_yscale("log")
    # Los halvings, marcados en los dos paneles
    for fecha, _ in HALVINGS:
        f = pd.Timestamp(fecha)
        if f >= btc.index[0]:
            for eje in ejes:
                eje.axvline(f, color=MARINO, lw=0.9, ls="--", alpha=0.7)
            ejes[0].text(f, btc.max() * 1.15, f" halving\n {f:%m/%Y}", fontsize=7, color=MARINO, va="top")
    proximo = m["proximo_halving"]
    for eje in ejes:
        eje.axvline(proximo, color=GRIS, lw=0.9, ls=":")
    ejes[0].text(proximo, btc.max() * 1.15, f" próximo\n ~{proximo:%m/%Y}", fontsize=7, color=GRIS, va="top")
    ejes[0].set_xlim(btc.index[0], proximo + pd.Timedelta(days=120))
    ejes[0].yaxis.set_major_formatter(FuncFormatter(_miles))
    ejes[0].set_ylabel("USD (escala log.)", fontsize=8, color="#3A4A5C")
    caida = (btc / btc.cummax() - 1) * 100
    ejes[1].fill_between(caida.index, caida, 0, color=MARINO, alpha=0.8, lw=0)
    ejes[1].yaxis.set_major_formatter(FuncFormatter(_pct))
    ejes[1].set_ylabel("Caída desde\nel máximo", fontsize=8, color="#3A4A5C")
    g["btc"] = _guardar(fig, carpeta / "btc.png")

    # 13. Comercio exterior: bienes (12 meses) y servicios (4 trimestres)
    b12, s4 = m["bienes12"].loc["2004":], m["serv4"]
    fig, ejes = _figura(4.4, filas=2, sharex=True)
    ejes[0].plot(b12.index, b12["expo"], color=VERDE, lw=1.6, label="Exportaciones de bienes")
    ejes[0].plot(b12.index, b12["impo"], color=ROJO, lw=1.6, label="Importaciones de bienes")
    ejes[0].bar(b12.index, b12["saldo"], width=25, color=[AZUL if v >= 0 else GRIS for v in b12["saldo"]], alpha=0.45,
                label="Saldo")
    ejes[0].axhline(0, color=GRIS, lw=0.6)
    ejes[0].set_ylabel("Bienes, suma de 12 meses\n(miles de mill. USD)", fontsize=7.5, color="#3A4A5C")
    ejes[0].legend(frameon=False, fontsize=7.5, loc="upper left", ncol=3)
    ejes[1].plot(s4.index, s4["ingresos"], color=VERDE, lw=1.6, label="Ingresos por servicios")
    ejes[1].plot(s4.index, s4["egresos"], color=ROJO, lw=1.6, label="Egresos por servicios")
    ejes[1].bar(s4.index, s4["saldo"], width=70, color=[AZUL if v >= 0 else GRIS for v in s4["saldo"]], alpha=0.45, label="Saldo")
    ejes[1].axhline(0, color=GRIS, lw=0.6)
    ejes[1].set_ylabel("Servicios, suma de 4 trim.\n(miles de mill. USD)", fontsize=7.5, color="#3A4A5C")
    ejes[1].legend(frameon=False, fontsize=7.5, loc="upper left", ncol=3)
    g["comercio"] = _guardar(fig, carpeta / "comercio.png")
    return g


# ── PDF ───────────────────────────────────────────────────────────────────────

def armar_pdf(m: dict, g: dict, carpeta: Path) -> Path:
    from jinja2 import Environment, FileSystemLoader
    from playwright.sync_api import sync_playwright

    entorno = Environment(loader=FileSystemLoader(RAIZ / "reporte" / "templates"), autoescape=True)
    entorno.filters["num"] = num
    entorno.filters["signo"] = signo
    entorno.filters["mes"] = mes_anio
    recursos = RAIZ / "reporte" / "recursos"
    html = entorno.get_template("informe_macro.html").render(
        m=m, g=g, logo=(recursos / "globalaize_logo.png").as_uri(),
        tecnologias=[(recursos / "tecnologias" / f"{n}.png").as_uri() for n in
                     ("python", "pandas", "matplotlib", "postgresql", "supabase", "githubactions", "gemini")],
        hoy=date.today(),
    )
    pagina_html = carpeta / "informe.html"
    pagina_html.write_text(html, encoding="utf-8")
    pdf = carpeta / f"Argentina macro {m['hoy']:%Y-%m}.pdf"
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        try:
            pagina = navegador.new_page()
            pagina.goto(pagina_html.as_uri(), wait_until="networkidle")
            pagina.evaluate("document.fonts.ready.then(() => true)")
            pagina.pdf(path=str(pdf), format="A4", print_background=True, prefer_css_page_size=True,
                       display_header_footer=True,
                       header_template="<span></span>",
                       footer_template=(
                           '<div style="width:100%;font-family:IBM Plex Sans,Arial;font-size:7.5px;color:#697E91;'
                           'padding:0 14mm;display:flex;justify-content:space-between;">'
                           "<span>Argentina: estado de situación macroeconómica · Mauro E. Martinez · GlobalAIze</span>"
                           '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'),
                       margin={"top": "14mm", "bottom": "16mm", "left": "0mm", "right": "0mm"})
        finally:
            navegador.close()
    return pdf


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--bajar", type=Path, help="Solo bajar los datos a esta carpeta")
    parser.add_argument("--datos", type=Path, help="Usar datos ya bajados en esta carpeta")
    parser.add_argument("--salida", type=Path, default=RAIZ / "informes", help="Carpeta del PDF")
    args = parser.parse_args()
    if args.bajar:
        bajar(args.bajar)
        print(f"Datos en {args.bajar}")
        return
    datos = args.datos
    if datos is None:
        datos = args.salida / "datos"
        bajar(datos)
    d = cargar(datos)
    m = calcular(d)
    g = graficos(d, m, args.salida / "graficos")
    pdf = armar_pdf(m, g, args.salida)
    print(f"Informe: {pdf}")


if __name__ == "__main__":
    main()
