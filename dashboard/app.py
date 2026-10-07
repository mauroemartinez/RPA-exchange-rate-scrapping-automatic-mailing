"""Prototipo de dashboard en Streamlit sobre el histórico (fase 5 del roadmap: evaluación).

Solo lee Fact_Mercado_Macro, dentro de una transacción READ ONLY, o el CSV que
llega adjunto en el mail. No importa config.py a propósito: config exige todas
las credenciales del pipeline (mail, Gemini, FRED) y un dashboard publicado no
tiene por qué tenerlas. Le alcanza con DASHBOARD_DB_URL, la URL de un usuario de
solo lectura (ver docs/evaluacion-powerpoint-y-streamlit.md).

Uso:
    pip install -r dashboard/requirements.txt
    streamlit run dashboard/app.py                       # DASHBOARD_DB_URL, o SUPABASE_DB_URL con aviso
    DASHBOARD_CSV="Seguimiento Macroeconómico.csv" streamlit run dashboard/app.py   # sin base, desde el CSV
"""

import logging
import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import dotenv_values
from sqlalchemy import create_engine, text

RAIZ = Path(__file__).resolve().parent.parent
TABLA = "Fact_Mercado_Macro"

COTIZACIONES = {
    "Blue (venta)": "TCV_Blue",
    "MEP": "TCV_MEP",
    "Billete BNA (venta)": "TCV_Billete",
    "Divisas BNA (venta)": "TCV_Divisas",
    "Solidario": "Solidario",
    "Euro blue (venta)": "TCV_Euro",
}

st.set_page_config(page_title="Seguimiento Macroeconómico", page_icon="📈", layout="wide")


def _secreto(nombre: str) -> str | None:
    """Un valor de los secrets de Streamlit o del entorno."""
    try:
        if nombre in st.secrets:
            return st.secrets[nombre]
    except Exception:
        pass  # sin secrets.toml
    return os.environ.get(nombre)


def _url_base() -> tuple[str | None, bool]:
    """(URL, es la del pipeline). DASHBOARD_DB_URL primero; si no está, SUPABASE_DB_URL.

    La del pipeline es el usuario postgres, que puede escribir y borrar todo: sirve
    para correrlo en la PC propia, pero el dashboard avisa en pantalla.
    """
    propia = _secreto("DASHBOARD_DB_URL")
    if propia:
        return propia, False
    return _secreto("SUPABASE_DB_URL") or dotenv_values(RAIZ / ".env").get("SUPABASE_DB_URL"), True


def _sin_markdown(texto: str) -> str:
    """El texto de Gemini tal cual: sin que un link, un encabezado o un par de $ (LaTeX) se interpreten."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|<>~$])", r"\\\1", texto)


@st.cache_data(ttl=3600, show_spinner="Leyendo el histórico...")
def historico() -> pd.DataFrame:
    csv = os.environ.get("DASHBOARD_CSV")
    if csv:
        df = pd.read_csv(csv)
    else:
        url, _ = _url_base()
        if not url:
            st.error("Falta DASHBOARD_DB_URL (secrets de Streamlit o variable de entorno).")
            st.stop()
        try:
            engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 30})
            with engine.connect() as conn:
                conn.execute(text("SET TRANSACTION READ ONLY"))
                df = pd.read_sql_query(text(f'SELECT * FROM "{TABLA}" ORDER BY "Fecha"'), conn)
            engine.dispose()
        except Exception:
            # El detalle (host, usuario) queda en el log del servidor, no en la página
            logging.getLogger(__name__).exception("No se pudo leer la base")
            st.error("No se pudo leer la base de datos. El detalle está en el log del servidor.")
            st.stop()
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df.drop(columns=["ai_secciones"], errors="ignore").sort_values("Fecha").reset_index(drop=True)


df = historico()
if not os.environ.get("DASHBOARD_CSV") and _url_base()[1]:
    st.warning("Conectado con SUPABASE_DB_URL, el usuario del pipeline. Antes de publicar este dashboard, "
               "configurá DASHBOARD_DB_URL con un usuario de solo lectura.")
ultima = df.iloc[-1]
anterior = df.iloc[-2]

st.title("📈 Seguimiento Macroeconómico")
st.caption(f"Último dato: {ultima['Fecha']:%d/%m/%Y} · {len(df):,} ruedas desde {df['Fecha'].min():%d/%m/%Y}")

# ── Indicadores del día ──
columnas = st.columns(5)
for col, (rotulo, campo) in zip(columnas, [("Blue", "TCV_Blue"), ("MEP", "TCV_MEP"), ("Billete BNA", "TCV_Billete")]):
    col.metric(rotulo, f"$ {ultima[campo]:,.2f}", f"{(ultima[campo] / anterior[campo] - 1) * 100:+.2f}%")
columnas[3].metric("Riesgo país", f"{ultima['riesgo_pais']:,.0f} pts",
                   f"{ultima['riesgo_pais'] - anterior['riesgo_pais']:+,.0f} pts", delta_color="inverse")
columnas[4].metric("BADLAR (TEA)", f"{ultima['bcra_tea']:.2f}%", f"FED {ultima['fed_tea']:.2f}%", delta_color="off")

# ── Filtros ──
with st.sidebar:
    st.header("Filtros")
    # Seis meses, o desde el primer dato si el histórico es más corto (un CSV recortado)
    desde_defecto = max((ultima["Fecha"] - pd.DateOffset(months=6)).date(), df["Fecha"].min().date())
    rango = st.date_input(
        "Período", value=(desde_defecto, ultima["Fecha"].date()),
        min_value=df["Fecha"].min().date(), max_value=ultima["Fecha"].date(),
    )
    # Mientras se elige el rango, el widget devuelve una sola fecha
    desde, hasta = (rango[0], rango[-1]) if isinstance(rango, (tuple, list)) else (rango, rango)
    elegidas = st.multiselect("Cotizaciones", list(COTIZACIONES), default=["Blue (venta)", "MEP", "Billete BNA (venta)"])

periodo = df[(df["Fecha"] >= pd.Timestamp(desde)) & (df["Fecha"] <= pd.Timestamp(hasta))].set_index("Fecha")

cotizaciones, brechas, riesgo, tasas, ia, datos = st.tabs(
    ["Cotizaciones", "Brechas", "Riesgo país", "Tasas", "Análisis de IA", "Datos"]
)
with cotizaciones:
    if elegidas:
        st.line_chart(periodo[[COTIZACIONES[e] for e in elegidas]].rename(columns={v: k for k, v in COTIZACIONES.items()}))
    else:
        st.info("Elegí al menos una cotización en el panel de la izquierda.")
with brechas:
    st.line_chart(pd.DataFrame({
        "Blue contra MEP (%)": (periodo["TCV_Blue"] / periodo["TCV_MEP"] - 1) * 100,
        "Solidario contra Blue (%)": (periodo["Solidario"] / periodo["TCV_Blue"] - 1) * 100,
    }))
with riesgo:
    st.line_chart(periodo["riesgo_pais"].rename("Riesgo país (pts)"))
with tasas:
    st.line_chart(periodo[["bcra_tea", "fed_tea"]].rename(columns={"bcra_tea": "BADLAR (TEA)", "fed_tea": "FED (EFFR)"}))
with ia:
    parrafos = periodo["ai_paragraph"].dropna() if "ai_paragraph" in periodo else pd.Series(dtype=str)
    parrafos = parrafos[parrafos.str.strip() != ""].sort_index(ascending=False)
    if parrafos.empty:
        st.info("No hay párrafos de IA en el período.")
    for fecha, parrafo in parrafos.head(10).items():
        st.markdown(f"**{fecha:%d/%m/%Y}**  \n{_sin_markdown(parrafo)}")
with datos:
    st.dataframe(periodo.sort_index(ascending=False), width="stretch")
    st.download_button("Descargar CSV", periodo.to_csv().encode("utf-8"), "seguimiento_macroeconomico.csv", "text/csv")
