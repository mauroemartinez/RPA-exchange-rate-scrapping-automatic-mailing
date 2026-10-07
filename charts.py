"""Preparación y generación de los cuatro gráficos del reporte (celdas 39 a 43).

Cada gráfico se dibuja sobre una Figure propia, sin pyplot, y dentro de su propio
rc_context. En el notebook el estilo era estado global: el gráfico de BTC dejaba
activo el fondo oscuro para todo lo que viniera después, y locale.setlocale()
cambiaba el idioma de las fechas de todo el proceso. En una corrida por proceso
no se notaba; en la API o en los tests, que corren varias veces seguidas, sí.

Los meses salen en español sin usar el locale del sistema (ver fechas.MESES_ABREV).
Los gráficos quedan idénticos, byte a byte, a los que generaba el notebook.
"""

import logging
import warnings
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.patheffects as pe
import pandas as pd
import seaborn as sns
from matplotlib.artist import setp
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MultipleLocator

import transformations
from fechas import mes_abreviado
from transformations import etiqueta_mes

log = logging.getLogger(__name__)

# Nombres de archivo y orden en el mail: el template los referencia como
# cid:image1 .. cid:image4, en este orden.
TIPOS_DE_CAMBIO = "Gráficos Tipos de Cambios y Riesgo País.jpg"
INFLACION = "Gráficos Inflación.jpg"
VARIACIONES = "Variaciones.jpg"
BTC = "Gráfico BTC.jpg"
ORDEN_EN_MAIL = (TIPOS_DE_CAMBIO, INFLACION, VARIACIONES, BTC)

COTIZACIONES_A_MOSTRAR = 25

# Inicio del período del gráfico de variaciones acumuladas. Cambiarlo cuando
# cambie el período de referencia.
FECHA_INICIO_VARIACIONES = "2025-07-01"

# Colores de la variación del riesgo país. Rojo = sube el riesgo (malo), verde =
# baja. Medidos sobre blanco: 5.44:1 y 4.72:1, los dos pasan WCAG AA para texto
# chico. El verde del mail (#27ae60) daba 2.87:1 y se descartó por ilegible.
VAR_SUBE = "#c0392b"
VAR_BAJA = "#1e8449"
VAR_IGUAL = "#000000"


@contextmanager
def _estilo_base():
    """Estilo de partida de todos los gráficos: el de matplotlib más sns.set(style='ticks')."""
    with mpl.rc_context():
        mpl.rcdefaults()
        sns.set_theme(style="ticks")
        yield


def _formato_mes(fmt: str) -> FuncFormatter:
    """Equivalente de mdates.DateFormatter(fmt) para '%b/%y' y '%b %Y', con meses en español."""
    separador, anio = {"%b/%y": ("/", "%y"), "%b %Y": (" ", "%Y")}[fmt]

    def formatear(x, pos=None):
        fecha = mdates.num2date(x)
        return f"{mes_abreviado(fecha)}{separador}{fecha.strftime(anio)}"

    return FuncFormatter(formatear)


def _guardar(fig: Figure, carpeta: Path, nombre: str, **kwargs) -> Path:
    ruta = Path(carpeta) / nombre
    fig.savefig(ruta, **kwargs)
    log.info("Gráfico guardado: %s", ruta.name)
    return ruta


# ── Tipos de cambio y riesgo país ────────────────────────────────────────────

def preparar_datos(df: pd.DataFrame) -> pd.DataFrame:
    """El histórico de más viejo a más nuevo, con Fecha como texto 'dd/mm/yy' (celda 39)."""
    data = df.copy().iloc[::-1]
    data["Fecha"] = pd.to_datetime(data["Fecha"], dayfirst=False, errors="coerce")
    data["Fecha"] = data["Fecha"].dt.strftime("%d/%m/%y")
    return data


def _step_riesgo_pais(valor_max: float) -> tuple[float, float]:
    """Paso de ticks del riesgo país según el máximo de la ventana mostrada.

    Antes estaba fijo en 500, pensado para cuando el riesgo país superaba los 2000
    puntos. Con valores por debajo de 1000 ese paso escondía la variación diaria.
    """
    if valor_max <= 300:
        return 25, 12.5
    elif valor_max <= 1000:
        return 100, 50
    elif valor_max <= 2000:
        return 250, 100
    else:
        return 500, 200


def grafico_tipos_de_cambio(data: pd.DataFrame, carpeta: Path, n: int = COTIZACIONES_A_MOSTRAR) -> Path:
    """Cotizaciones paralelas, oficiales y riesgo país de las últimas n ruedas (celda 40)."""
    with _estilo_base():
        fig = Figure(figsize=(10, 14))
        ax = fig.subplots(3, 1, sharex=False)
        ultimos = data.tail(n)

        titulos = ["Cotizaciones Paralelas", "Cotizaciones Oficiales", "Evolución del Riesgo País"]
        fig.suptitle(f"Tipos de cambio y riesgo país - últimas {n} cotizaciones", fontweight="bold", fontsize=18)
        for i, titulo in enumerate(titulos):
            ax[i].set_title(titulo, fontweight="bold", fontsize=12)

        # Cotizaciones paralelas
        ax0_palette = sns.color_palette("dark")
        ax0_columns = ["TCV_Euro", "TCV_Blue", "TCC_Blue", "TCV_MEP", "Solidario"]
        ax0_labels = ["TCV Euro Blue", "TCV Blue", "TCC Blue", "MEP", "Solidario"]
        for i, column in enumerate(ax0_columns):
            sns.lineplot(x="Fecha", y=column, data=ultimos, label=ax0_labels[i], color=ax0_palette[i], marker="o", ax=ax[0])

        # Etiqueta de datos cada 5 valores y en el último
        for i, column in enumerate(ax0_columns):
            for j, (x, y) in enumerate(zip(ultimos["Fecha"], ultimos[column])):
                if j % 5 == 0 or j == len(ultimos[column]) - 1:
                    ax[0].annotate(
                        f"{y:,.2f}", xy=(x, y), xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontproperties=fm.FontProperties(weight="bold", size=9),
                        bbox=dict(boxstyle="round", edgecolor=ax0_palette[i], facecolor="white"),
                    )

        # Cotizaciones oficiales
        ax1_palette = sns.color_palette("bright")
        ax1_columns = ["TCV_Billete", "TCV_Divisas", "TCC_Divisas", "TCC_Billete"]
        ax1_labels = ["TCV Billete", "TCV Divisas", "TCC Divisas", "TCC Billete"]
        for i, column in enumerate(ax1_columns):
            sns.lineplot(x="Fecha", y=column, data=ultimos, label=ax1_labels[i], color=ax1_palette[i], marker="D", ax=ax[1])

        for i, column in enumerate(ax1_columns):
            for j, (x, y) in enumerate(zip(ultimos["Fecha"], ultimos[column])):
                if j % 5 == 0 or j == len(ultimos[column]) - 1:
                    ax[1].annotate(
                        f"{y:,.2f}", xy=(x, y), xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontproperties=fm.FontProperties(weight="bold", size=9),
                        bbox=dict(boxstyle="round", alpha=0.4, edgecolor=ax1_palette[i], facecolor="white"),
                    )

        # Riesgo país: barras con el máximo y el mínimo de la ventana resaltados
        df_riesgo = ultimos.copy()
        max_riesgo = df_riesgo["riesgo_pais"].max()
        min_riesgo = df_riesgo["riesgo_pais"].min()

        def categorizar_riesgo(valor):
            if abs(valor - max_riesgo) < 1e-2:
                return "Máximo"
            if abs(valor - min_riesgo) < 1e-2:
                return "Mínimo"
            return "Normal"

        df_riesgo["Categoria"] = df_riesgo["riesgo_pais"].apply(categorizar_riesgo)

        # Variación contra el día anterior. Se calcula sobre la serie COMPLETA y
        # recién después se recorta: así la primera barra compara contra su día
        # previo real en vez de quedarse sin dato.
        df_riesgo["var_pct"] = (data["riesgo_pais"].pct_change() * 100).tail(n).values

        sns.barplot(
            x="Fecha", y="riesgo_pais", data=df_riesgo, hue="Categoria",
            palette={"Máximo": "red", "Mínimo": "green", "Normal": "silver"},
            legend=False, width=0.8, edgecolor="none", linewidth=0, ax=ax[2],
        )

        valores_riesgo = df_riesgo["riesgo_pais"].tolist()
        variaciones_riesgo = df_riesgo["var_pct"].tolist()
        for bar in ax[2].patches:
            height = bar.get_height()
            if not height:
                continue

            # La posición en X identifica la barra: seaborn, al agrupar por hue, no
            # garantiza que patches venga en el mismo orden que las filas.
            centro = bar.get_x() + bar.get_width() / 2
            idx = int(round(centro))
            if not (0 <= idx < len(valores_riesgo)):
                continue

            font_size = 12 if height in [max_riesgo, min_riesgo] else 9
            annotation_color = "red" if height == max_riesgo else "green" if height == min_riesgo else "black"

            # Recuadro sin borde: un fondo blanco translúcido para leer el número
            # por encima de la grilla.
            ax[2].annotate(
                f"{height:,.0f}", xy=(centro, height + 2.25), xytext=(0, 22), textcoords="offset points",
                ha="center", va="bottom", fontproperties=fm.FontProperties(weight="bold", size=font_size),
                bbox=dict(boxstyle="round", alpha=0.4, edgecolor="none", facecolor="white"),
                color=annotation_color,
            )

            # Variación diaria debajo del valor. La flecha repite la información del
            # color, así el dato se lee aunque no se distinga rojo de verde. Es un
            # carácter y no un emoji porque matplotlib no renderiza emoji a color.
            variacion = variaciones_riesgo[idx]
            if pd.isna(variacion):
                continue
            if round(variacion, 1) == 0:
                etiqueta_var, color_var = "0%", VAR_IGUAL
            elif variacion > 0:
                etiqueta_var, color_var = f"▲{variacion:.1f}%", VAR_SUBE
            else:
                etiqueta_var, color_var = f"▼{abs(variacion):.1f}%", VAR_BAJA

            ax[2].annotate(
                etiqueta_var, xy=(centro, height), xytext=(0, 8), textcoords="offset points",
                ha="center", va="bottom", fontproperties=fm.FontProperties(weight="bold", size=7.5),
                color=color_var,
            )

        for axis in ax:
            axis.set_xlabel("")
            axis.xaxis.set_major_locator(MultipleLocator(2))
            axis.xaxis.set_minor_locator(MultipleLocator(1))

        for i in range(2):
            ax[i].yaxis.set_major_formatter(FuncFormatter("{:,.2f}".format))

        rp_major_step, rp_minor_step = _step_riesgo_pais(max_riesgo)
        y_labels = ["ARS / USD", "ARS / USD", "Puntos Base"]
        y_major_locators = [MultipleLocator(50), MultipleLocator(10), MultipleLocator(rp_major_step)]
        y_minor_locators = [MultipleLocator(250), MultipleLocator(25), MultipleLocator(rp_minor_step)]
        for i in range(3):
            ax[i].set_ylabel(y_labels[i], fontsize=12, fontweight="bold")
            ax[i].yaxis.set_major_locator(y_major_locators[i])
            ax[i].yaxis.set_minor_locator(y_minor_locators[i])

        # 1.22 y no 1.1: hay dos renglones de etiqueta sobre cada barra
        ax[2].set_ylim([0, ultimos.riesgo_pais.max() * 1.22])

        for axis in ax:
            axis.grid(color="silver", linestyle="--", linewidth=0.5)

        ax[0].legend(prop={"size": 8}, loc="upper left", shadow=True)
        ax[1].legend(prop={"size": 8}, loc="upper left", shadow=True)

        fig.tight_layout(pad=1)
        return _guardar(fig, carpeta, TIPOS_DE_CAMBIO)


# ── Variaciones acumuladas ───────────────────────────────────────────────────

def preparar_variaciones(
    data: pd.DataFrame, inflacion: pd.DataFrame, fecha_inicio: str = FECHA_INICIO_VARIACIONES
) -> pd.DataFrame:
    """Solidario, blue e inflación acumulados desde fecha_inicio (celda 41).

    `data` es la salida de preparar_datos() e `inflacion` la serie mensual que se
    cruza por fecha con las cotizaciones. Tiene que ser la serie completa, o al
    menos cubrir desde fecha_inicio: el notebook cruzaba solo los últimos 12 meses
    y, pasado un año desde fecha_inicio, la inflación acumulada empezaba meses
    después que el dólar (en octubre de 2026 arrancaba en septiembre de 2025
    contra julio de 2025), así que el gráfico comparaba períodos distintos.
    """
    data = data.copy()
    # preparar_datos() dejó las fechas como 'dd/mm/yy'; con el formato explícito
    # pandas no tiene que adivinarlo fila por fila (y no avisa que lo está haciendo)
    data["Fecha"] = pd.to_datetime(data["Fecha"], format="%d/%m/%y", errors="coerce")

    va = data.merge(inflacion[["Fecha", "Inflación Mensual"]], on=["Fecha"], how="outer")
    # Después del merge, las fechas con inflación pero sin cotización quedan al final
    va.sort_values("Fecha", inplace=True)
    # Índice desde cero: las etiquetas "cada 25 filas" del gráfico arrancan en el
    # inicio del período y no dependen de cuánta historia vino antes
    va = va[va["Fecha"] >= pd.to_datetime(fecha_inicio)].reset_index(drop=True)

    for column in ["Variación Solidario", "Variación TCV Blue", "Inflación Mensual"]:
        if column == "Inflación Mensual":
            va[f"{column} Acumulada"] = ((1 + va[column] / 100).cumprod() - 1) * 100
        else:
            va[f"{column} Acumulada"] = ((1 + va[column]).cumprod() - 1) * 100
    return va


def grafico_variaciones(variacion_acumulada: pd.DataFrame, carpeta: Path) -> Path:
    """Variaciones acumuladas de solidario y blue contra la inflación (celda 41)."""
    va = variacion_acumulada
    with _estilo_base():
        fig = Figure(figsize=(10, 5))
        ax = fig.subplots()

        palette = sns.color_palette("pastel")
        ax2_columns = ["Variación Solidario Acumulada", "Variación TCV Blue Acumulada", "Inflación Mensual Acumulada"]
        ax2_labels = ["Δ Solidario Acumulada", "Δ TCV Blue Acumulada", "Inflación Mensual Acumulada"]

        for i, column in enumerate(ax2_columns):
            if column == "Inflación Mensual Acumulada":
                sns.lineplot(
                    x="Fecha", y=column, data=va, label=ax2_labels[i], color=palette[i], linewidth=2,
                    marker="D", markersize=7, drawstyle="steps-pre", ax=ax,
                )
            else:
                # El rótulo de la leyenda es el nombre de la columna, como en el notebook
                sns.lineplot(x="Fecha", y=column, data=va, label=ax2_columns[i], color=palette[i], linewidth=2, ax=ax)

            # Etiquetas de datos: cada 25 filas para las cotizaciones, todas para la inflación
            bbox = dict(facecolor=palette[i], edgecolor=palette[i], boxstyle="square,pad=0.2")
            label_frequency = 25 if column != "Inflación Mensual Acumulada" else 1
            for idx, row in va.iterrows():
                if not pd.isna(row[column]):
                    if idx % label_frequency == 0:
                        ax.text(
                            row["Fecha"], row[column] * 1.05, f"{row[column]:,.1f}",
                            fontsize=9, color="black", ha="center", va="center", bbox=bbox,
                        )

                    # El valor máximo de cada línea, resaltado
                    bbox_max = dict(facecolor=palette[i], edgecolor="black", boxstyle="square,pad=0.2")
                    if row[column] == va[column].max() and idx == va[column].idxmax():
                        ax.text(
                            row["Fecha"], row[column] * 1.05, f"{row[column]:,.2f}",
                            fontsize=10, color="darkred", fontweight="bold", ha="center", va="center", bbox=bbox_max,
                        )

        ax.set_title("Variaciones acumuladas", fontsize=14, fontweight="bold")

        # Mismo orden de llamadas que el notebook: los rótulos fijos se reemplazan
        # enseguida por el formateador de meses, pero dejan la rotación de 45°.
        # matplotlib avisa que set_ticklabels sin ticks fijos es raro; acá es a propósito.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            ax.set_xticklabels(va.Fecha[::3], rotation=45)
        ax.xaxis.set_major_formatter(_formato_mes("%b/%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        ax.set_xlabel("")

        ax.yaxis.set_major_formatter(FuncFormatter("{:,.1f} %".format))
        ax.set_ylabel("Variación Acumulada", fontsize=12, fontweight="bold")

        ax.grid(True)
        sns.despine(fig=fig)
        return _guardar(fig, carpeta, VARIACIONES)


# ── Inflación ────────────────────────────────────────────────────────────────

def preparar_inflacion(inflacion_12: pd.DataFrame) -> pd.DataFrame:
    """Los meses del gráfico, de más viejo a más nuevo, rotulados 'sep/2025' (celda 42)."""
    datos = inflacion_12.copy()
    datos["Fecha"] = [etiqueta_mes(f) for f in datos["Fecha"]]
    return datos


def grafico_inflacion(inflacion: pd.DataFrame, carpeta: Path) -> Path:
    """Inflación mensual en barras e interanual en línea, en dos ejes (celda 42)."""
    with _estilo_base():
        fig = Figure(figsize=(10, 7))
        ax = fig.subplots(sharex=True)
        ax2 = ax.twinx()  # comparten eje X con ejes Y diferentes

        largo_fecha = len(inflacion["Fecha"])
        fig.suptitle(
            f"Evolución de la Inflación Argentina en los últimos {largo_fecha} meses", fontweight="bold", fontsize=18
        )

        sns.barplot(
            x="Fecha", y="Inflación Mensual", data=inflacion, edgecolor="black", facecolor="darkgrey",
            label="Inflación Mensual", ax=ax, legend=False,
        )
        sns.lineplot(
            x="Fecha", y="Inflación Anual", data=inflacion, linewidth=2.5, color="darkred", marker="o",
            markersize=8, label="Inflación Anual", ax=ax2,
        )

        bbox = dict(boxstyle="round,pad=0.3", edgecolor="darkred", facecolor="white")
        path_effects = [pe.withStroke(linewidth=0.5, foreground="black")]

        # Etiquetas de la inflación mensual, con el máximo resaltado aparte
        max_y = inflacion["Inflación Mensual"].max()
        max_x = inflacion["Fecha"][inflacion["Inflación Mensual"].idxmax()]
        for x, y in zip(inflacion["Fecha"], inflacion["Inflación Mensual"]):
            if y != max_y:
                ax.annotate(f"{y:.1f}%", (x, y), textcoords="offset points", xytext=(0, 12), ha="center", bbox=bbox)
        ax.annotate(
            f"{max_y:.1f}%", (max_x, max_y), textcoords="offset points", xytext=(0, 12), ha="center",
            fontsize=12, fontweight="bold", color="darkred", bbox=bbox, path_effects=path_effects,
        )

        # Máximo de la inflación interanual
        max_y = inflacion["Inflación Anual"].max()
        max_x = inflacion["Fecha"][inflacion["Inflación Anual"].idxmax()]
        ax2.annotate(
            f"{max_y:.1f}%", (max_x, max_y), textcoords="offset points", xytext=(0, 12), ha="center",
            fontsize=12, fontweight="bold", color="darkred", bbox=bbox, path_effects=path_effects,
        )

        ax.set_xlabel("")
        ax.set_xticks(range(0, largo_fecha, 1))
        ax.set_xticklabels(inflacion.Fecha[::1], rotation=45)
        ax.set_xlim(-0.5, largo_fecha - 0.5)

        ax.set_ylim([0, inflacion["Inflación Mensual"].max() * 1.2])
        ax.set_ylabel("Inflación Mensual", fontweight="bold", fontsize=12)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.1f} %"))

        ax2.set_ylabel("Inflación Anual", fontweight="bold", fontsize=12, rotation=270, labelpad=15)
        ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f} %"))

        # Con twinx la leyenda hay que armarla a mano con los dos ejes
        handles1, labels1 = ax.get_legend_handles_labels()
        handles2, labels2 = ax2.get_legend_handles_labels()
        ax2.legend(handles1 + handles2, labels1 + labels2, prop={"size": 8}, shadow=True)

        return _guardar(fig, carpeta, INFLACION)


# ── BTC ──────────────────────────────────────────────────────────────────────

DIAS_BTC = 365
# Margen extra de descarga para que las medias móviles y la volatilidad ya
# tengan valor desde el primer día que se muestra.
MARGEN_BTC = 40


def rango_btc(ahora: datetime) -> tuple[datetime, datetime]:
    """(desde, hasta) para descargar BTC, con el margen de los rolling incluido."""
    return ahora - timedelta(days=DIAS_BTC) - timedelta(days=MARGEN_BTC), ahora


def preparar_btc(crudo: pd.DataFrame, ahora: datetime) -> pd.DataFrame:
    """Medias móviles y volatilidad sobre lo que devuelve yfinance, recortado a 12 meses."""
    btc_df = crudo.reset_index()
    if isinstance(btc_df.columns, pd.MultiIndex):
        btc_df.columns = btc_df.columns.get_level_values(0)

    btc_df["index"] = pd.to_datetime(btc_df["index"])
    btc_df = btc_df.set_index("index")
    btc_df.index.name = "Date"

    btc_df["MA7"] = btc_df["Close"].rolling(window=7).mean()
    btc_df["MA30"] = btc_df["Close"].rolling(window=30).mean()
    btc_df["Volatility"] = btc_df["Close"].pct_change().rolling(window=20).std() * 100

    # Recorte a los 12 meses visibles, con las medias ya completas
    return btc_df[btc_df.index >= ahora - timedelta(days=DIAS_BTC)]


def grafico_btc(btc_df: pd.DataFrame, carpeta: Path) -> Path:
    """Precio de BTC con medias de 7 y 30 días y volatilidad de 20 días (celda 43)."""
    # .iloc[-1] es la ÚLTIMA vela disponible, no necesariamente la de hoy: yfinance
    # cierra el día según UTC y puede venir con retraso. Por eso dice 'Última cotización'.
    price_last = float(btc_df["Close"].iloc[-1])
    price_last_date = btc_df.index[-1]
    price_max = float(btc_df["Close"].max())
    price_min = float(btc_df["Close"].min())
    volatility_current = float(btc_df["Volatility"].iloc[-1])

    with _estilo_base():
        sns.set_theme(style="darkgrid", palette="husl")
        mpl.style.use("dark_background")

        fig = Figure(figsize=(16, 10), facecolor="#0a0a0a")
        ax1, ax2 = fig.subplots(2, 1, gridspec_kw={"height_ratios": [3, 1]})

        for ax in [ax1, ax2]:
            ax.set_facecolor("#0a0a0a")
            ax.grid(True, alpha=0.2, color="#333333", linestyle="-", linewidth=0.5)

        ax1.fill_between(btc_df.index, btc_df["Close"], alpha=0.1, color="#00ff41")
        ax1.plot(btc_df.index, btc_df["Close"], color="#00ff41", linewidth=2.5, label="Precio BTC", zorder=5)
        ax1.plot(btc_df.index, btc_df["MA7"], color="#FFD700", linewidth=2.2, linestyle="-.", label="Media 7 días", alpha=0.9, zorder=4)
        ax1.plot(btc_df.index, btc_df["MA30"], color="#FF6B6B", linewidth=2.2, linestyle=":", label="Media 30 días", alpha=0.85, zorder=4)

        ax1.xaxis.set_major_locator(mdates.MonthLocator(bymonthday=1))
        ax1.xaxis.set_major_formatter(_formato_mes("%b %Y"))
        ax1.xaxis.set_minor_locator(mdates.MonthLocator(bymonthday=15))
        setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")
        ax1.set_xlim(btc_df.index[0], btc_df.index[-1])
        ax1.set_ylim(bottom=0)

        ax1.set_title("BTC/USD - Últimos 12 Meses con Seaborn Style", fontsize=20, fontweight="bold", color="#00ff41", pad=20)
        ax1.set_ylabel("USD/BTC", fontsize=13, color="#00ff41", fontweight="bold")

        legend1 = ax1.legend(
            loc="upper left", fontsize=12, framealpha=0.95, edgecolor="#00ff41", facecolor="#0a0a0a",
            labelcolor="#ffffff", title="Indicadores", title_fontsize=12,
        )
        legend1.get_title().set_color("#00ff41")

        ax2.fill_between(btc_df.index, btc_df["Volatility"], alpha=0.3, color="#FF6B6B")
        ax2.plot(btc_df.index, btc_df["Volatility"], color="#FF6B6B", linewidth=2, label="Volatilidad (20d)")
        ax2.set_ylabel("Volatilidad (%)", fontsize=12, color="#FF6B6B", fontweight="bold")
        ax2.xaxis.set_major_locator(mdates.MonthLocator(bymonthday=1))
        ax2.xaxis.set_major_formatter(_formato_mes("%b %Y"))
        ax2.xaxis.set_minor_locator(mdates.MonthLocator(bymonthday=15))
        setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha="right")
        ax2.set_xlim(btc_df.index[0], btc_df.index[-1])
        ax2.set_ylim(bottom=0)
        ax2.legend(loc="upper left", fontsize=11, framealpha=0.95, edgecolor="#FF6B6B", facecolor="#0a0a0a", labelcolor="#ffffff")

        for ax in [ax1, ax2]:
            ax.spines["bottom"].set_color("#00ff41")
            ax.spines["left"].set_color("#00ff41")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.minorticks_on()
            ax.tick_params(
                axis="both", which="major", direction="in", length=8, width=1.5, color="#00ff41",
                labelcolor="#ffffff", labelsize=10, bottom=True, left=True,
            )
            ax.tick_params(axis="both", which="minor", direction="in", length=4, width=1.0, color="#00ff41", bottom=True, left=True)

        kpi_text = (
            f"Última cotización: ${price_last:,.0f}  ({price_last_date:%d/%m/%y})\n"
            f"Máximo: ${price_max:,.0f}\n"
            f"Mínimo: ${price_min:,.0f}\n"
            f"Volatilidad: {volatility_current:.2f}%"
        )
        ax1.text(
            0.98, 0.97, kpi_text, transform=ax1.transAxes, fontsize=11, fontweight="bold",
            bbox=dict(boxstyle="round,pad=1", facecolor="#1a1a1a", edgecolor="#00ff41", alpha=0.9, linewidth=2),
            ha="right", va="top", color="#00ff41", family="monospace",
        )

        fig.tight_layout()
        return _guardar(fig, carpeta, BTC, dpi=150, facecolor="#0a0a0a", edgecolor="none", bbox_inches="tight")


# ── Agregados monetarios (fase 3, todavía fuera del mail) ────────────────────

AGREGADOS = "Agregados Monetarios.jpg"

# Series del panel de niveles y del de variación interanual, con su rótulo
NIVELES = {"base_monetaria": "Base monetaria", "circulacion_monetaria": "Circulación monetaria", "m2": "M2"}
INTERANUALES = {"base_monetaria": "Base monetaria", "m2": "M2", "m3": "M3 (mensual)"}


def preparar_agregados(series: dict, hoy) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(niveles en billones de ARS, variación interanual), los dos del último año.

    `series` es lo que devuelve scrapers.agregados.descargar(). Los niveles se
    pasan de millones a billones solo para el gráfico: en la base quedan en la
    unidad de la fuente.
    """
    # Un año en los dos paneles: con dos, la variación interanual de fines de 2024
    # (más de 200%) aplastaba la escala justo donde está la comparación que importa
    corte = pd.Timestamp(hoy) - pd.DateOffset(years=1)

    niveles = []
    for clave, rotulo in NIVELES.items():
        df = transformations.serie_a_frame(series[clave])
        df = df[df["Fecha"] >= corte].assign(serie=rotulo, billones=lambda d: d["valor"] / 1e6)
        niveles.append(df)

    interanuales = []
    for clave, rotulo in {**INTERANUALES, "inflacion_interanual": "Inflación interanual"}.items():
        if clave == "inflacion_interanual":
            df = transformations.serie_a_frame(series[clave]).rename(columns={"valor": "interanual"})
        else:
            df = transformations.interanual_por_fecha(series[clave])
        interanuales.append(df[df["Fecha"] >= corte].assign(serie=rotulo))

    return pd.concat(niveles, ignore_index=True), pd.concat(interanuales, ignore_index=True)


def grafico_agregados(niveles: pd.DataFrame, interanual: pd.DataFrame, carpeta: Path) -> Path:
    """Niveles de base monetaria, circulación y M2, y su variación interanual contra la inflación."""
    with _estilo_base():
        fig = Figure(figsize=(10, 10))
        ax = fig.subplots(2, 1)
        fig.suptitle("Agregados monetarios", fontweight="bold", fontsize=18)

        paleta = sns.color_palette("dark")
        for i, (rotulo, datos) in enumerate(niveles.groupby("serie", sort=False)):
            ax[0].plot(datos["Fecha"], datos["billones"], color=paleta[i], linewidth=2, label=rotulo)
            ultimo = datos.iloc[-1]
            ax[0].annotate(
                f"{ultimo['billones']:,.1f}", xy=(ultimo["Fecha"], ultimo["billones"]), xytext=(4, 0),
                textcoords="offset points", va="center", fontproperties=fm.FontProperties(weight="bold", size=9),
                color=paleta[i],
            )
        ax[0].set_title("Niveles del último año", fontweight="bold", fontsize=12)
        ax[0].set_ylabel("Billones de ARS", fontsize=12, fontweight="bold")
        ax[0].yaxis.set_major_formatter(FuncFormatter("{:,.0f}".format))

        colores = {"Base monetaria": paleta[0], "M2": paleta[2], "M3 (mensual)": paleta[4], "Inflación interanual": "darkred"}
        for rotulo, datos in interanual.groupby("serie", sort=False):
            if rotulo == "Inflación interanual":
                ax[1].plot(datos["Fecha"], datos["interanual"], color=colores[rotulo], linewidth=2.5,
                           drawstyle="steps-post", label=rotulo)
            elif rotulo == "M3 (mensual)":
                ax[1].plot(datos["Fecha"], datos["interanual"], color=colores[rotulo], linestyle="none",
                           marker="D", markersize=6, label=rotulo)
            else:
                ax[1].plot(datos["Fecha"], datos["interanual"], color=colores[rotulo], linewidth=1.8, label=rotulo)
        ax[1].axhline(0, color="black", linewidth=0.8)
        ax[1].set_title("Variación interanual contra la inflación", fontweight="bold", fontsize=12)
        ax[1].set_ylabel("Variación interanual", fontsize=12, fontweight="bold")
        ax[1].yaxis.set_major_formatter(FuncFormatter("{:,.0f} %".format))

        for axis, ubicacion in zip(ax, ["upper left", "upper right"]):
            axis.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
            axis.xaxis.set_major_formatter(_formato_mes("%b/%y"))
            axis.grid(color="silver", linestyle="--", linewidth=0.5)
            axis.legend(prop={"size": 8}, loc=ubicacion, shadow=True)
            setp(axis.xaxis.get_majorticklabels(), rotation=45)

        fig.tight_layout(pad=1)
        return _guardar(fig, carpeta, AGREGADOS)
