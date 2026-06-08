import os
import pandas as pd
from dotenv import load_dotenv
from google import genai
from sqlalchemy import text

def generar_con_failover(prompt):
    """
    Carga las keys en el momento de la llamada (no al importar el módulo).
    Rota a la siguiente key si recibe error 429.
    """
    load_dotenv(override=True)
    api_keys = [k for k in [os.getenv("GEMINI_API_KEY_1"), os.getenv("GEMINI_API_KEY_2")] if k]

    if not api_keys:
        raise Exception("❌ No hay API keys de Gemini en el .env (GEMINI_API_KEY_1 / GEMINI_API_KEY_2).")

    models = ["gemini-3.5-flash", "gemini-2.5-flash"]

    for i, key in enumerate(api_keys):
        for model in models:
            try:
                client = genai.Client(api_key=key)
                response = client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                return response.text, model

            except Exception as e:
                error_text = str(e).lower()
                if "429" in error_text or "quota" in error_text or "resource exhausted" in error_text:
                    print(f"⚠️ Key {i+1} agotada (Cuota excedida).")
                    break

                if "503" in error_text or "unavailable" in error_text:
                    if model == models[0]:
                        print("⚠️ Gemini 3.5 está saturado. Intentando gemini-2.5-flash...")
                        continue
                    print("❌ Gemini 2.5 también está indisponible. Intenta más tarde.")
                    raise Exception(f"❌ Error técnico en Gemini: {e}")

                print(f"❌ Error técnico en Gemini: {e}")
                raise e

        else:
            # No model-specific break, continue to next key only if a key-specific error didn't occur.
            continue

        # If quota/error de key occurred, try next API key.
        if i == len(api_keys) - 1:
            raise Exception("❌ Se agotaron todas las API Keys (429).")
        print("🔄 Reintentando con la siguiente API Key...")


def procesar_y_guardar_parrafo(engine):
    """
    Extrae historial de Supabase, calcula variaciones, genera párrafo con Gemini,
    guarda en la DB y retorna el texto.
    """
    try:
        print("🔌 [IA Subprocess] Conectando a Supabase para extraer historial...")
        df = pd.read_sql("""
            SELECT "Fecha", "TCV_MEP", "TCV_Blue", "TCV_Billete",
                   "riesgo_pais", "bcra_tea", "fed_tea"
            FROM "Fact_Mercado_Macro"
            ORDER BY "Fecha" ASC
        """, con=engine)

        df.columns = df.columns.str.strip()
        df['Fecha'] = pd.to_datetime(df['Fecha'])

        if len(df) < 26:
            raise Exception(f"Historial insuficiente: {len(df)} registros.")

        hoy  = df.iloc[-1]
        ayer = df.iloc[-2]
        mes  = df.iloc[-26]

        blue    = hoy['TCV_Blue']
        mep     = hoy['TCV_MEP']
        billete = hoy['TCV_Billete']
        rp      = hoy['riesgo_pais']
        tea     = hoy['bcra_tea']
        fed     = hoy['fed_tea']
        brecha  = abs(((blue / mep) - 1) * 100)
        barato  = "Blue" if blue < mep else "MEP"

        def var(a, b):
            return ((a / b) - 1) * 100

        tea_cambio = abs(var(tea, ayer['bcra_tea'])) > 0.2
        fed_cambio = abs(var(fed, ayer['fed_tea'])) > 0

        prompt = f"""
Actuá como analista financiero Senior. Redactá un párrafo de 3-4 líneas.
DATOS REALES AL {hoy['Fecha'].strftime('%d/%m/%Y')}:
- Blue: ${blue} (Día: {var(blue, ayer['TCV_Blue']):+.2f}% | Mes: {var(blue, mes['TCV_Blue']):+.2f}%)
- MEP: ${mep}
- Brecha: {brecha:.2f}% entre el Blue (${blue}) y el MEP (${mep})
- Más barato: {barato}, siendo la opción más económica de las dos
- Billete: ${billete} (Día: {var(billete, ayer['TCV_Billete']):+.2f}% | Mes: {var(billete, mes['TCV_Billete']):+.2f}%)
- Riesgo País: {rp} pts (Día: {rp - ayer['riesgo_pais']:+.0f} pts | Mes: {rp - mes['riesgo_pais']:+.0f} pts)
{f"- TEA BCRA: {tea:.2f}% (Día: {var(tea, ayer['bcra_tea']):+.2f}% | Mes: {var(tea, mes['bcra_tea']):+.2f}%)" if tea_cambio else ""}
{f"- TEA FED: {fed:.2f}% (Día: {var(fed, ayer['fed_tea']):+.2f}%)" if fed_cambio else ""}

Instrucciones:
1. Mencioná la brecha con los valores explícitos de Blue y MEP.
2. Usá la frase "siendo la opción más económica de las dos" al comparar.
3. Analizá tendencia mensual para Blue, Billete y Riesgo País cuando sea relevante.
4. Tono seco, profesional. No somos asesores financieros.
"""

        print(f"🤖 Analizando datos del {hoy['Fecha'].strftime('%d/%m/%Y')}...")
        reporte, modelo = generar_con_failover(prompt)

        print(f"💾 Guardando en Supabase para la fecha {hoy['Fecha'].date()}, usando: {modelo}...")
        with engine.begin() as conn:
            result = conn.execute(
                text('UPDATE "Fact_Mercado_Macro" SET "ai_paragraph" = :p, "ai_model" = :m WHERE "Fecha" = :f'),
                {"p": reporte, "m": modelo, "f": hoy['Fecha'].date()}
            )
            print(f"✅ Guardado. Filas afectadas: {result.rowcount}")

        return reporte

    except Exception as e:
        print(f"\n❌ Proceso de IA interrumpido: {e}")
        return "No se pudo generar el análisis automatizado de mercado."