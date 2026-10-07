from datetime import date

from pydantic import BaseModel, Field

# Orden real de las columnas en Supabase. El mail arma la tabla de cotizaciones
# con df.iloc[:, :14], así que este orden no es cosmético. Viven acá y no en
# data_access para que los módulos de cálculo se puedan importar sin un .env.
COLUMNAS_VALORES = [
    "TCC_Blue", "TCV_Blue", "TCC_Billete", "TCV_Billete", "TCC_Divisas", "TCV_Divisas",
    "Solidario", "TCV_MEP", "riesgo_pais", "TCC_Euro", "TCV_Euro", "fed_tea", "bcra_tea",
]
COLUMNAS_FILA = ["Fecha", *COLUMNAS_VALORES]
COLUMNAS_TABLA = [*COLUMNAS_FILA, "ai_paragraph", "ai_model"]


class FilaMacro(BaseModel):
    # Convertir automáticamente strings y datetimes a date
    Fecha: date

    # gt=0 rechaza cualquier valor <= 0 (scraper roto o parseo fallido)
    TCC_Blue: float = Field(gt=0)
    TCV_Blue: float = Field(gt=0)
    TCC_Billete: float = Field(gt=0)
    TCV_Billete: float = Field(gt=0)
    TCC_Divisas: float = Field(gt=0)
    TCV_Divisas: float = Field(gt=0)
    Solidario: float = Field(gt=0)
    TCV_MEP: float = Field(gt=0)
    riesgo_pais: float = Field(gt=0)
    TCC_Euro: float = Field(gt=0)
    TCV_Euro: float = Field(gt=0)

    # Tasas: sin restricción de signo, teóricamente pueden ser muy bajas
    fed_tea: float
    bcra_tea: float

    # Estos campos no existen en fila_nueva todavía, se agregan en Supabase después
    ai_paragraph: str | None = None
    ai_model: str | None = None


class SeccionesIA(BaseModel):
    """Lo que tiene que devolver Gemini en la llamada estructurada (fase 4 del roadmap).

    Un párrafo general, el de la caja de arriba del mail, y un comentario por
    bloque de gráficos. Valida la respuesta: si un campo falta, está vacío o se
    desborda, no se usa y el pipeline vuelve al párrafo único. A la API va
    ia_generator._esquema_respuesta(), que solo lleva tipos y campos obligatorios.
    """

    resumen: str = Field(min_length=80, max_length=1500)
    paralelas: str = Field(min_length=40, max_length=1000)
    oficiales: str = Field(min_length=40, max_length=1000)
    riesgo_pais: str = Field(min_length=40, max_length=1000)
    # Sin datos de BTC (Yahoo no respondió) la sección viene vacía
    btc: str | None = Field(default=None, max_length=1000)
