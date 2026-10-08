"""Párrafo de análisis de mercado con Gemini.

Lee el historial de Supabase, calcula variaciones de 1 y 25 ruedas, arma el prompt,
llama a Gemini rotando keys y modelos, y guarda el texto en la fila del día.
"""

import json
import logging
from datetime import date

import pandas as pd
from google import genai
from google.genai import types
from pydantic import ValidationError
from sqlalchemy import text

from reporte import charts
from reporte.config import settings
from reporte.models import SeccionesIA

log = logging.getLogger(__name__)

TABLA = "Fact_Mercado_Macro"
MODELOS = ["gemini-3.5-flash", "gemini-2.5-flash"]
MAX_INTENTOS = 3
MENSAJE_FALLA = "No se pudo generar el análisis automatizado de mercado."

# Por defecto google-genai espera sin límite: un Gemini colgado dejaba la corrida
# esperando hasta que app.py la mataba a la hora, con la fila guardada y sin mail.
TIMEOUT_MS = 120_000

# 25 ruedas hacia atrás más la de hoy
FILAS_MINIMAS = 26


def generar_con_failover(prompt, config=None):
    """
    Rota a la siguiente key si recibe error 429.

    Las keys vienen de config.py, que las lee una sola vez al importarse. Antes
    esta función hacía su propio load_dotenv(override=True) en cada llamada, lo
    que permitía rotar keys sin reiniciar; a cambio había dos lugares leyendo el
    .env. Como el pipeline corre una vez por día en un proceso nuevo, la lectura
    única alcanza y deja una sola fuente de verdad.

    Devuelve (texto, modelo, intentos). Si no hubo respuesta, (None, None, intentos).
    `config` se pasa tal cual a generate_content (por ejemplo, un esquema de salida).
    """
    api_keys = settings.gemini_keys

    if not api_keys:
        raise Exception("No hay API keys de Gemini en el .env (GEMINI_API_KEY_1 / GEMINI_API_KEY_2).")

    attempts = 0
    for i, key in enumerate(api_keys):
        for model in MODELOS:
            attempts += 1
            try:
                client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=TIMEOUT_MS))
                response = client.models.generate_content(model=model, contents=prompt, config=config)
                return response.text, model, attempts

            except Exception as e:
                error_text = str(e).lower()
                if "429" in error_text or "quota" in error_text or "resource exhausted" in error_text:
                    log.warning("Gemini: key %d agotada (cuota excedida)", i + 1)
                    # No se prueban más modelos con esta key: se pasa a la siguiente
                    break

                if "503" in error_text or "unavailable" in error_text:
                    if model == MODELOS[0]:
                        log.warning("Gemini: %s saturado, se intenta %s", MODELOS[0], MODELOS[1])
                        continue
                    log.error("Gemini: %s también está indisponible", model)
                    return None, None, attempts

                log.error("Gemini: error técnico con %s: %s", model, e)
                return None, None, attempts

        if i == len(api_keys) - 1:
            log.error("Gemini: se agotaron todas las API keys (429)")
            return None, None, attempts
        log.info("Gemini: se reintenta con la siguiente API key")


def leer_historial(engine) -> pd.DataFrame:
    """Las últimas FILAS_MINIMAS filas con las columnas que usa el prompt, de más vieja a más nueva.

    El prompt solo mira la última, la anterior y la de 25 ruedas atrás: no hace
    falta traer las siete mil filas de la tabla.
    """
    df = pd.read_sql(
        text(
            'SELECT "Fecha", "TCV_MEP", "TCV_Blue", "TCV_Billete", "riesgo_pais", "bcra_tea", "fed_tea" '
            f'FROM "{TABLA}" ORDER BY "Fecha" DESC LIMIT :n'
        ),
        con=engine,
        params={"n": FILAS_MINIMAS},
    ).iloc[::-1].reset_index(drop=True)
    df.columns = df.columns.str.strip()
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    if len(df) < FILAS_MINIMAS:
        raise ValueError(f"Historial insuficiente: {len(df)} registros.")
    return df


def armar_prompt(df: pd.DataFrame) -> str:
    """El prompt del párrafo diario, con las variaciones de la última fila."""
    hoy = df.iloc[-1]
    ayer = df.iloc[-2]
    mes = df.iloc[-FILAS_MINIMAS]

    blue = hoy["TCV_Blue"]
    mep = hoy["TCV_MEP"]
    billete = hoy["TCV_Billete"]
    rp = hoy["riesgo_pais"]
    tea = hoy["bcra_tea"]
    fed = hoy["fed_tea"]
    brecha = abs(((blue / mep) - 1) * 100)
    barato = "Blue" if blue < mep else "MEP"

    def var(a, b):
        return ((a / b) - 1) * 100

    tea_cambio = abs(var(tea, ayer["bcra_tea"])) > 0.2
    fed_cambio = abs(var(fed, ayer["fed_tea"])) > 0

    return f"""
Actuá como analista financiero Senior. Redactá un párrafo de 3-4 líneas.
DATOS REALES AL {hoy['Fecha'].strftime('%d/%m/%Y')}:
- Blue: ${blue} (Día: {var(blue, ayer['TCV_Blue']):+.2f}% | Mes: {var(blue, mes['TCV_Blue']):+.2f}%)
- MEP: ${mep}
- Brecha: {brecha:.2f}% entre el Blue (${blue}) y el MEP (${mep})
- Más barato: {barato}, siendo la opción más económica de las dos
- Billete: ${billete} (Día: {var(billete, ayer['TCV_Billete']):+.2f}% | Mes: {var(billete, mes['TCV_Billete']):+.2f}%)
- Riesgo País: {rp:.0f} pts (Día: {rp - ayer['riesgo_pais']:+.0f} pts | Mes: {rp - mes['riesgo_pais']:+.0f} pts)
{f"- TEA BCRA: {tea:.2f}% (Día: {var(tea, ayer['bcra_tea']):+.2f}% | Mes: {var(tea, mes['bcra_tea']):+.2f}%)" if tea_cambio else ""}
{f"- TEA FED: {fed:.2f}% (Día: {var(fed, ayer['fed_tea']):+.2f}%)" if fed_cambio else ""}

Instrucciones:
1. Mencioná la brecha con los valores explícitos de Blue y MEP.
2. Usá la frase "siendo la opción más económica de las dos" al comparar.
3. Analizá tendencia mensual para Blue, Billete y Riesgo País cuando sea relevante.
4. Tono seco, profesional. No somos asesores financieros.
"""


def generar_parrafo(prompt: str, config=None) -> tuple[str | None, str | None]:
    """(texto, modelo), o (None, None) si no hubo caso.

    Reintenta mientras se hayan consumido menos de MAX_INTENTOS intentos. Cada
    vuelta de generar_con_failover puede gastar hasta tres (una key agotada pasa a
    la siguiente, un modelo saturado al otro), así que en el peor caso son cinco
    llamadas, no tres. Los 429 y 503 vuelven al instante; lo que acota el tiempo
    es el TIMEOUT_MS de cada llamada. Es la lógica que tenía el notebook.
    """
    total = 0
    while total < MAX_INTENTOS:
        respuesta, modelo, usados = generar_con_failover(prompt, config=config)
        total += usados
        if respuesta is not None:
            return respuesta, modelo
        if total >= MAX_INTENTOS:
            log.error("Gemini: se alcanzó el máximo de %d intentos; se sigue sin párrafo", MAX_INTENTOS)
            break
        log.warning("Gemini: intentos consumidos %d de %d, se reintenta", total, MAX_INTENTOS)
    return None, None


def guardar_parrafo(engine, fecha: date, texto: str, modelo: str | None) -> int:
    """UPDATE de ai_paragraph y ai_model en la fila de `fecha`. Devuelve las filas afectadas."""
    with engine.begin() as conn:
        result = conn.execute(
            text(f'UPDATE "{TABLA}" SET "ai_paragraph" = :p, "ai_model" = :m WHERE "Fecha" = :f'),
            {"p": texto, "m": modelo, "f": fecha},
        )
    log.info("Gemini: párrafo del %s guardado con %s (filas afectadas: %d)", fecha, modelo, result.rowcount)
    return result.rowcount


def procesar_y_guardar_parrafo(engine, fecha_esperada: date | None = None) -> str:
    """
    Extrae historial de Supabase, calcula variaciones, genera párrafo con Gemini,
    guarda en la DB y retorna el texto.

    Con `fecha_esperada`, se niega a seguir si la última fila de la base no es de
    esa fecha. Sin ese control, una fila del día que no llegó a insertarse hacía
    que el párrafo de ayer se reescribiera con un análisis de los datos de ayer.
    """
    try:
        log.info("Gemini: leyendo el historial de Supabase")
        df = leer_historial(engine)
        fecha = df["Fecha"].iloc[-1].date()

        if fecha_esperada is not None and fecha != fecha_esperada:
            raise ValueError(
                f"la última fila de {TABLA} es del {fecha} y se esperaba la del {fecha_esperada}; "
                "no se genera el párrafo para no pisar el de otro día"
            )

        log.info("Gemini: analizando los datos del %s", fecha.strftime("%d/%m/%Y"))
        reporte, modelo = generar_parrafo(armar_prompt(df))
        if reporte is None:
            reporte, modelo = "", None

        guardar_parrafo(engine, fecha, reporte, modelo)
        return reporte

    except Exception as e:
        log.error("Gemini: proceso interrumpido: %s", e)
        return MENSAJE_FALLA


# ── Fase 4: un comentario por gráfico en una sola llamada ────────────────────

# Ruedas hacia atrás de la comparación "mensual", igual que el párrafo diario
VENTANA = 25

# Qué sección va debajo de qué gráfico del mail (cid) y con qué título
SECCIONES_POR_GRAFICO = {
    charts.cid(charts.TIPOS_DE_CAMBIO): [("Cotizaciones paralelas", "paralelas"), ("Cotizaciones oficiales", "oficiales"),
                                         ("Riesgo país", "riesgo_pais")],
    charts.cid(charts.BTC): [("Bitcoin", "btc")],
}


def _esquema_respuesta():
    """El esquema que se le pide a Gemini: solo tipos y campos obligatorios.

    Los largos mínimos y máximos los controla models.SeccionesIA al recibir la
    respuesta, así no depende de qué restricciones acepte la API en el esquema.
    """
    texto = types.Schema(type=types.Type.STRING)
    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "resumen": texto, "paralelas": texto, "oficiales": texto, "riesgo_pais": texto,
            "btc": types.Schema(type=types.Type.STRING, nullable=True),
        },
        required=["resumen", "paralelas", "oficiales", "riesgo_pais"],
        property_ordering=["resumen", "paralelas", "oficiales", "riesgo_pais", "btc"],
    )


def _var(a: float, b: float) -> float:
    return (a / b - 1) * 100


def _hechos_btc(btc: pd.DataFrame) -> list[str]:
    """Los datos de BTC a comentar, sobre la salida de charts.preparar_btc()."""
    cierre = btc["Close"]
    ultimo, fecha = float(cierre.iloc[-1]), btc.index[-1]
    ma7, ma30 = float(btc["MA7"].iloc[-1]), float(btc["MA30"].iloc[-1])
    cruce = (btc["MA7"] > btc["MA30"]).astype(int).diff().iloc[-7:]
    vol, vol_media = float(btc["Volatility"].iloc[-1]), float(btc["Volatility"].mean())
    lineas = [
        f"- Último cierre: USD {ultimo:,.0f} ({fecha:%d/%m/%Y})",
        f"- Variación 7 días: {_var(ultimo, float(cierre.iloc[-8])):+.2f}% | 30 días: {_var(ultimo, float(cierre.iloc[-31])):+.2f}%",
        f"- Media móvil de 7 días: USD {ma7:,.0f}, {'por encima' if ma7 > ma30 else 'por debajo'} de la de 30 días (USD {ma30:,.0f})",
        f"- Máximo de 12 meses: USD {cierre.max():,.0f} ({cierre.idxmax():%d/%m/%Y}) | Mínimo: USD {cierre.min():,.0f} ({cierre.idxmin():%d/%m/%Y})",
        f"- Volatilidad de 20 días: {vol:.2f}% (promedio de 12 meses: {vol_media:.2f}%)",
    ]
    if (cruce == 1).any():
        lineas.append("- En la última semana la media de 7 días cruzó hacia arriba a la de 30")
    elif (cruce == -1).any():
        lineas.append("- En la última semana la media de 7 días cruzó hacia abajo a la de 30")
    return lineas


def armar_prompt_secciones(df: pd.DataFrame, btc: pd.DataFrame | None, fwd_oficial: float) -> str:
    """El prompt de la llamada estructurada. `df` es el histórico más nuevo primero, con la fila de hoy.

    Todas las cifras van calculadas: a Gemini solo se le pide que las redacte.
    """
    hoy, ayer, mes = df.iloc[0], df.iloc[1], df.iloc[VENTANA]
    ventana = df.iloc[: VENTANA + 1]
    fecha = pd.to_datetime(hoy["Fecha"]).strftime("%d/%m/%Y")

    def dia_mes(col: str) -> str:
        return f"Día: {_var(hoy[col], ayer[col]):+.2f}% | {VENTANA} ruedas: {_var(hoy[col], mes[col]):+.2f}%"

    blue, mep = hoy["TCV_Blue"], hoy["TCV_MEP"]
    barato = "Blue" if blue < mep else "MEP"
    fechas_ventana = pd.to_datetime(ventana["Fecha"])
    rp = ventana["riesgo_pais"]
    rp_max, rp_min = rp.idxmax(), rp.idxmin()

    resumen = [
        f"- Blue: ${blue} ({dia_mes('TCV_Blue')})",
        f"- MEP: ${mep}",
        f"- Brecha: {abs(_var(blue, mep)):.2f}% entre el Blue (${blue}) y el MEP (${mep}); más barato: {barato}",
        f"- Billete: ${hoy['TCV_Billete']} ({dia_mes('TCV_Billete')})",
        f"- Riesgo País: {hoy['riesgo_pais']:.0f} pts (Día: {hoy['riesgo_pais'] - ayer['riesgo_pais']:+.0f} pts | "
        f"{VENTANA} ruedas: {hoy['riesgo_pais'] - mes['riesgo_pais']:+.0f} pts)",
        f"- TEA BCRA (BADLAR): {hoy['bcra_tea']:.2f}% | TEA FED: {hoy['fed_tea']:.2f}%",
    ]
    paralelas = [
        f"- Blue venta: ${blue} ({dia_mes('TCV_Blue')}); compra: ${hoy['TCC_Blue']}",
        f"- Blue venta, rango de las últimas {VENTANA} ruedas: máximo ${ventana['TCV_Blue'].max()}, mínimo ${ventana['TCV_Blue'].min()} (no es una banda cambiaria)",
        f"- MEP: ${mep} ({dia_mes('TCV_MEP')})",
        f"- Euro blue venta: ${hoy['TCV_Euro']} ({dia_mes('TCV_Euro')})",
        f"- Solidario: ${hoy['Solidario']:.2f} (Día: {_var(hoy['Solidario'], ayer['Solidario']):+.2f}%)",
        f"- Brecha MEP contra Blue: {_var(mep, blue):+.2f}% | Solidario contra Blue: {_var(hoy['Solidario'], blue):+.2f}%",
    ]
    oficiales = [
        f"- Billete BNA venta: ${hoy['TCV_Billete']} ({dia_mes('TCV_Billete')}); compra: ${hoy['TCC_Billete']}",
        f"- Divisas BNA venta: ${hoy['TCV_Divisas']} ({dia_mes('TCV_Divisas')}); compra: ${hoy['TCC_Divisas']}",
        f"- Diferencia entre billete y divisas (venta): {_var(hoy['TCV_Billete'], hoy['TCV_Divisas']):+.2f}%",
        f"- Forward oficial a 3 meses por paridad de tasas de Fisher (BADLAR contra FED): ${fwd_oficial:,.2f}, "
        f"{_var(fwd_oficial, hoy['TCV_Billete']):+.2f}% sobre el billete",
    ]
    riesgo = [
        f"- Hoy: {hoy['riesgo_pais']:.0f} pts (Día: {hoy['riesgo_pais'] - ayer['riesgo_pais']:+.0f} pts, "
        f"{_var(hoy['riesgo_pais'], ayer['riesgo_pais']):+.2f}%)",
        f"- Hace {VENTANA} ruedas: {mes['riesgo_pais']:.0f} pts ({hoy['riesgo_pais'] - mes['riesgo_pais']:+.0f} pts)",
        f"- Máximo de la ventana: {rp[rp_max]:.0f} pts ({fechas_ventana[rp_max]:%d/%m}) | "
        f"Mínimo: {rp[rp_min]:.0f} pts ({fechas_ventana[rp_min]:%d/%m})",
    ]
    hechos_btc = _hechos_btc(btc) if btc is not None and len(btc) > 31 else ["- Sin datos de BTC hoy"]

    bloques = {
        "resumen": resumen, "paralelas": paralelas, "oficiales": oficiales,
        "riesgo_pais": riesgo, "btc": hechos_btc,
    }
    datos = "\n\n".join(f"[{clave}]\n" + "\n".join(lineas) for clave, lineas in bloques.items())

    return f"""
Actuá como analista financiero Senior. Escribí los comentarios de un reporte diario del mercado argentino,
en castellano rioplatense, con tono seco y profesional. No somos asesores financieros: no recomiendes
comprar ni vender. Usá solo las cifras de abajo, ya calculadas, sin inventar datos.

DATOS AL {fecha}:

{datos}

Devolvé un JSON con estas claves:
- resumen: un párrafo de 3 a 4 líneas. Mencioná la brecha con los valores explícitos de Blue y MEP, usá la
  frase "siendo la opción más económica de las dos" al compararlos y analizá la tendencia de las últimas
  {VENTANA} ruedas para Blue, Billete y Riesgo País cuando sea relevante.
- paralelas: 2 o 3 oraciones sobre blue, MEP, euro blue y solidario.
- oficiales: 2 o 3 oraciones sobre billete y divisas del BNA y el forward de Fisher.
- riesgo_pais: 2 o 3 oraciones sobre el nivel, la variación del día y la de las últimas {VENTANA} ruedas.
- btc: 2 o 3 oraciones sobre precio, medias móviles y volatilidad; null si no hay datos de BTC.
No repitas en una sección lo que ya dijiste en otra.
"""


def generar_secciones(prompt: str) -> tuple[SeccionesIA | None, str | None]:
    """(secciones validadas, modelo). Si la respuesta no cumple el esquema, se pide una vez más."""
    config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=_esquema_respuesta())
    for intento in (1, 2):
        texto, modelo = generar_parrafo(prompt, config=config)
        if texto is None:
            return None, None
        try:
            return SeccionesIA.model_validate_json(texto), modelo
        except ValidationError as exc:
            log.warning("Gemini: la respuesta estructurada no cumple el esquema (intento %d): %s", intento, exc)
    return None, None


def guardar_secciones(engine, fecha: date, secciones: SeccionesIA, modelo: str | None) -> int:
    """El resumen va a ai_paragraph, como siempre; los comentarios por gráfico, a ai_secciones (JSON).

    ai_paragraph sigue teniendo el párrafo general, así el reenvío manual, el CSV
    adjunto y el notebook funcionan igual que antes.
    """
    contenido = secciones.model_dump(exclude={"resumen"})
    contenido["modelo"] = modelo
    with engine.begin() as conn:
        result = conn.execute(
            text(
                f'UPDATE "{TABLA}" SET "ai_paragraph" = :p, "ai_model" = :m, '
                '"ai_secciones" = CAST(:s AS jsonb) WHERE "Fecha" = :f'
            ),
            {"p": secciones.resumen, "m": modelo, "s": json.dumps(contenido, ensure_ascii=False), "f": fecha},
        )
    log.info("Gemini: secciones del %s guardadas con %s (filas afectadas: %d)", fecha, modelo, result.rowcount)
    return result.rowcount


def limpiar_secciones(engine, fecha: date) -> int:
    """Borra los comentarios por gráfico de la fila de `fecha`.

    Si una corrida repetida (--forzar) terminó en el párrafo único, los comentarios
    de la corrida anterior describirían otros valores.
    """
    with engine.begin() as conn:
        return conn.execute(
            text(f'UPDATE "{TABLA}" SET "ai_secciones" = NULL WHERE "Fecha" = :f'), {"f": fecha}
        ).rowcount


def comentarios_por_grafico(secciones: dict | SeccionesIA | None) -> dict[str, list[tuple[str, str]]]:
    """{cid: [(título, texto), ...]} para el template, desde las secciones guardadas o recién generadas.

    Acepta lo que venga de la fila (None, NaN de pandas, la columna ausente): todo
    lo que no sea un SeccionesIA o un dict da {}.
    """
    if isinstance(secciones, SeccionesIA):
        datos = secciones.model_dump()
    elif isinstance(secciones, dict):
        datos = secciones
    else:
        return {}
    comentarios = {}
    for cid, items in SECCIONES_POR_GRAFICO.items():
        presentes = [(titulo, datos[clave]) for titulo, clave in items if datos.get(clave)]
        if presentes:
            comentarios[cid] = presentes
    return comentarios
