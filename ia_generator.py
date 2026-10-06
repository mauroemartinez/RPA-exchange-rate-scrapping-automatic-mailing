"""Párrafo de análisis de mercado con Gemini.

Lee el historial de Supabase, calcula variaciones de 1 y 25 ruedas, arma el prompt,
llama a Gemini rotando keys y modelos, y guarda el texto en la fila del día.
"""

import logging
from datetime import date

import pandas as pd
from google import genai
from sqlalchemy import text

from config import settings

log = logging.getLogger(__name__)

TABLA = "Fact_Mercado_Macro"
MODELOS = ["gemini-3.5-flash", "gemini-2.5-flash"]
MAX_INTENTOS = 3
MENSAJE_FALLA = "No se pudo generar el análisis automatizado de mercado."

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
                client = genai.Client(api_key=key)
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
    """Las columnas que usa el prompt, de más viejo a más nuevo."""
    df = pd.read_sql(
        f"""
        SELECT "Fecha", "TCV_MEP", "TCV_Blue", "TCV_Billete",
               "riesgo_pais", "bcra_tea", "fed_tea"
        FROM "{TABLA}"
        ORDER BY "Fecha" ASC
        """,
        con=engine,
    )
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
    """(texto, modelo) con hasta MAX_INTENTOS llamadas en total. (None, None) si no hubo caso."""
    total = 0
    while total < MAX_INTENTOS:
        respuesta, modelo, usados = generar_con_failover(prompt, config=config)
        total += usados if usados is not None else 1
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
