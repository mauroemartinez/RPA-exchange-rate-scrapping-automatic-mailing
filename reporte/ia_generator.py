"""Los textos del reporte con Gemini: el resumen y un comentario por gráfico.

Arma el prompt con cifras ya calculadas, llama a Gemini recorriendo modelos y
keys hasta que uno responde, valida la respuesta con models.SeccionesIA y la
guarda en la fila del día. Si nadie responde, la fila queda marcada sin IA y el
mail lleva el mensaje de reemplazo.
"""

import json
import logging
import time
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
# De mejor a peor. A la hora de la corrida los Flash grandes suelen devolver 503
# (saturados) en el nivel gratuito; por eso la lista sigue con los Lite y los 2.5.
MODELOS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]
# Cuántas veces se recorre la lista entera (todos los modelos con todas las keys)
# antes de seguir sin texto, y cuánto se espera entre una pasada y la siguiente
RONDAS = 3
ESPERA_ENTRE_RONDAS_S = 30
# Tope total de la búsqueda: con 14 combinaciones por ronda, un modelo colgado en
# cada una se comería la hora de la corrida (el workflow la mata a los 30 minutos)
PRESUPUESTO_S = 8 * 60
MENSAJE_FALLA = "No se pudo generar el análisis automatizado de mercado."

# Por defecto google-genai espera sin límite: un Gemini colgado dejaba la corrida
# esperando hasta que el timeout del workflow la mataba, con la fila guardada y sin mail.
TIMEOUT_MS = 120_000

# Para que los tests no esperen de verdad
_esperar = time.sleep
_reloj = time.monotonic


def _resumen_error(exc: Exception) -> str:
    """La primera línea del error, que es la que trae el código (429, 503, 404) y el motivo."""
    return str(exc).strip().splitlines()[0][:160] if str(exc).strip() else type(exc).__name__


def generar_parrafo(prompt: str, config=None) -> tuple[str | None, str | None]:
    """(texto, modelo) del primer modelo que responde, o (None, None) si ninguno lo hizo.

    Recorre MODELOS de mejor a peor y, para cada uno, las keys del .env; cualquier
    error (429 de cuota, 503 de saturación, 404 de un modelo que la cuenta no tiene)
    pasa a la combinación siguiente. Si la lista entera falla, espera
    ESPERA_ENTRE_RONDAS_S y la vuelve a recorrer, hasta RONDAS veces. Lo que acota
    el tiempo es PRESUPUESTO_S: pasado, se sigue sin texto aunque queden intentos.
    `config` se pasa tal cual a generate_content (por ejemplo, un esquema de salida).
    """
    api_keys = settings.gemini_keys
    if not api_keys:
        raise Exception("No hay API keys de Gemini en el .env (GEMINI_API_KEY_1 / GEMINI_API_KEY_2).")

    limite = _reloj() + PRESUPUESTO_S
    for ronda in range(1, RONDAS + 1):
        for model in MODELOS:
            for i, key in enumerate(api_keys):
                if _reloj() > limite:
                    log.error("Gemini: se agotaron los %d s de presupuesto; se sigue sin texto", PRESUPUESTO_S)
                    return None, None
                try:
                    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=TIMEOUT_MS))
                    response = client.models.generate_content(model=model, contents=prompt, config=config)
                except Exception as exc:
                    log.warning("Gemini: %s con la key %d no respondió (ronda %d): %s", model, i + 1, ronda, _resumen_error(exc))
                    continue
                if ronda > 1 or model != MODELOS[0]:
                    log.info("Gemini: respondió %s con la key %d en la ronda %d", model, i + 1, ronda)
                return response.text, model
        if ronda < RONDAS:
            log.warning("Gemini: ningún modelo respondió en la ronda %d de %d; se espera %d s", ronda, RONDAS, ESPERA_ENTRE_RONDAS_S)
            _esperar(ESPERA_ENTRE_RONDAS_S)
    log.error("Gemini: ningún modelo respondió en %d rondas; se sigue sin texto", RONDAS)
    return None, None


# ── Fase 4: un comentario por gráfico en una sola llamada ────────────────────

# Ruedas hacia atrás de la comparación "mensual", igual que el párrafo diario
VENTANA = 25

# Qué sección va debajo de qué gráfico del mail (cid) y con qué título
SECCIONES_POR_GRAFICO = {
    charts.cid(charts.TIPOS_DE_CAMBIO): [("Cotizaciones paralelas", "paralelas"), ("Cotizaciones oficiales", "oficiales")],
    charts.cid(charts.RIESGO_PAIS): [("Riesgo país", "riesgo_pais")],
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


def marcar_sin_ia(engine, fecha: date) -> int:
    """Deja la fila de `fecha` con el párrafo vacío y sin comentarios: el día salió sin IA.

    El párrafo vacío, y no NULL, es lo que distingue "Gemini no respondió" de "la
    corrida murió antes de la IA": una fila con ai_paragraph NULL se lee como un
    día a medio hacer (pipeline, control diario) y pediría rehacerlo con --forzar.
    También borra los comentarios que una corrida anterior del día (--forzar) pudo
    dejar: describirían otros valores.
    """
    with engine.begin() as conn:
        return conn.execute(
            text(f'UPDATE "{TABLA}" SET "ai_paragraph" = \'\', "ai_model" = NULL, "ai_secciones" = NULL WHERE "Fecha" = :f'),
            {"f": fecha},
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
