import os
import pandas as pd
from dotenv import load_dotenv
from google import genai
from sqlalchemy import text

# Configuración Inicial (Solo variables de entorno)
load_dotenv()
API_KEYS = [os.getenv("GEMINI_API_KEY_1"), os.getenv("GEMINI_API_KEY_2")]

def generar_con_failover(prompt):
    """
    Intenta generar el reporte. Si recibe un error 429, rota a la siguiente Key.
    Si el error es de otro tipo o se agotan las Keys, detiene la ejecución.
    """
    for i, key in enumerate(API_KEYS):
        if not key: 
            continue
        
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text 

        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower() or "resource exhausted" in str(e).lower():
                print(f"⚠️ Key {i+1} agotada (Cuota excedida).")
                if i == len(API_KEYS) - 1:
                    raise Exception("❌ Se agotaron todas las API Keys por límite de cuota (429).")
                print("🔄 Reintentando con la siguiente API Key...")
                continue
            else:
                print(f"❌ Error técnico inesperado en Gemini: {e}")
                raise e

def procesar_y_guardar_parrafo(engine):
    """
    Extrae el historial de SQL Server, calcula variaciones, llama a Gemini 
    con control de failover, guarda el resultado en la base de datos 
    y retorna el texto final para el orquestador principal.
    """
    try:
        query = """
            SELECT 
                Fecha, TCV_MEP, TCV_Blue, TCV_Billete, riesgo_pais, bcra_tea, fed_tea 
            FROM Fact_Mercado_Macro 
            ORDER BY Fecha ASC;
        """
        
        print("🔌 [IA Subprocess] Conectando a SQL Server para extraer historial...")
        df = pd.read_sql(query, con=engine)
        
        # Limpieza estándar
        df.columns = df.columns.str.strip()
        df['Fecha'] = pd.to_datetime(df['Fecha']) 

        # Validación única de historial mínimo (25 ruedas = 1 mes hábil)
        if len(df) < 26:
            raise Exception(f"Historial insuficiente en base de datos. La tabla solo tiene {len(df)} registros.")

        # Definición de puntos de control
        hoy = df.iloc[-1]       
        ayer = df.iloc[-2]      
        hace_25 = df.iloc[-26]  
        
        # Variables clave
        mep_hoy = hoy['TCV_MEP']
        blue_hoy = hoy['TCV_Blue']
        tea_hoy = hoy['bcra_tea']
        fed_tea_hoy = hoy['fed_tea']
     
        brecha_valor = abs(((blue_hoy / mep_hoy) - 1) * 100)
        mas_bajo = "Blue" if blue_hoy < mep_hoy else "MEP"
        
        def calc_var(actual, previo):
            return ((actual / previo) - 1) * 100

        contexto_masticado = {
            "fecha": hoy['Fecha'].strftime('%d/%m/%Y'),
            "blue_val": f"${blue_hoy}",
            "blue_stats": f"(Día: {calc_var(blue_hoy, ayer['TCV_Blue']):+.2f}% | Mes: {calc_var(blue_hoy, hace_25['TCV_Blue']):+.2f}%)",
            "mep_val": f"${mep_hoy}",
            "brecha_porc": f"{brecha_valor:.2f}%",
            "opcion_barata": mas_bajo,
            "riesgo_pais": {
                "actual": f"{hoy['riesgo_pais']} pts",
                "dif_diaria": f"{hoy['riesgo_pais'] - ayer['riesgo_pais']:+} pts",
                "dif_25_ruedas": f"{hoy['riesgo_pais'] - hace_25['riesgo_pais']:+} pts"
            },
            "billete": {
                "actual": f"${hoy['TCV_Billete']}",
                "var_diaria": f"{calc_var(hoy['TCV_Billete'], ayer['TCV_Billete']):+.2f}%",
                "var_25_ruedas": f"{calc_var(hoy['TCV_Billete'], hace_25['TCV_Billete']):+.2f}%"
            },
            "tea": {
                "actual": f"{tea_hoy:.2f}%",
                "var_diaria": f"{calc_var(tea_hoy, ayer['bcra_tea']):+.2f}%",
                "var_25_ruedas": f"{calc_var(tea_hoy, hace_25['bcra_tea']):+.2f}%"
            },
            "fed_tea": {
                "actual": f"{fed_tea_hoy:.2f}%",
                "var_diaria": f"{calc_var(fed_tea_hoy, ayer['fed_tea']):+.2f}%"
            }
        }

        # Validaciones de cambios significativos para composición dinámica del prompt
        tea_var_diaria = calc_var(tea_hoy, ayer['bcra_tea'])
        tea_strong_change = abs(tea_var_diaria) > 0.2    
        fed_var_diaria = calc_var(fed_tea_hoy, ayer['fed_tea'])
        fed_any_change = abs(fed_var_diaria) > 0
        
        prompt_final = f"""
        Actuá como analista financiero Senior. Redactá un párrafo de 3-4 líneas.
        DATOS REALES AL {contexto_masticado['fecha']}:
        - Blue: {contexto_masticado['blue_val']} {contexto_masticado['blue_stats']}
        - MEP: {contexto_masticado['mep_val']}
        - Brecha: {contexto_masticado['brecha_porc']}
        - Más barato hoy: {contexto_masticado['opcion_barata']}
        - Billete: {contexto_masticado['billete']['actual']} (Día: {contexto_masticado['billete']['var_diaria']} | Mes: {contexto_masticado['billete']['var_25_ruedas']})
        - Riesgo País: {contexto_masticado['riesgo_pais']['actual']} (Día: {contexto_masticado['riesgo_pais']['dif_diaria']} | Mes: {contexto_masticado['riesgo_pais']['dif_25_ruedas']})
    {f"- TEA BCRA: {contexto_masticado['tea']['actual']} (Día: {contexto_masticado['tea']['var_diaria']} | Mes: {contexto_masticado['tea']['var_25_ruedas']})" if tea_strong_change else ""}
    {f"- TEA FED: {contexto_masticado['fed_tea']['actual']} (Día: {contexto_masticado['fed_tea']['var_diaria']})" if fed_any_change else ""}

        Instrucciones obligatorias:
        1. Al mencionar la brecha, escribí explícitamente los valores de ambos, ejemplo: "entre el Blue ({contexto_masticado['blue_val']}) y el MEP ({contexto_masticado['mep_val']})".
        2. Para la comparativa de precios, usá la frase "siendo la opción más económica de las dos".
        3. Mantené el análisis de tendencia de 25 ruedas para Blue, Billete y Riesgo País{f", y Tasa Efectiva del BCRA" if tea_strong_change else ""} cuando sea significativo{f". Para la Tasa Efectiva de la FED, mencionála únicamente si cambió, sin requerir análisis de tendencia mensual" if fed_any_change else ""}.
        4. Tono seco, profesional y recordá que no somos asesores financieros.
        """
        
        print(f"🤖 Analizando datos del {contexto_masticado['fecha']}...")
        reporte = generar_con_failover(prompt_final)
        
        # Guardado en SQL Server apuntando a la fecha actual recuperada
        print(f"💾 Guardando reporte en SQL Server para la fecha {hoy['Fecha'].date()}...")
        update_query = text("""
            UPDATE Fact_Mercado_Macro 
            SET ai_paragraph = :parrafo 
            WHERE Fecha = :fecha
        """)
        
        with engine.begin() as conexion:
            conexion.execute(update_query, {"parrafo": reporte, "fecha": hoy['Fecha'].date()})
        
        print("✅ Base de datos actualizada con el párrafo de IA.")
        return reporte # Retorno clave para interceptar el string desde el .ipynb

    except Exception as e:
        print(f"\n❌ Proceso de IA interrumpido: {e}")
        return "No se pudo generar el análisis automatizado de mercado."