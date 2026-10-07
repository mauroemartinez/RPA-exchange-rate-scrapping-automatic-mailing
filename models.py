from datetime import date

from pydantic import BaseModel, Field


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
    bloque de gráficos. Se usa como response_schema de la llamada y para validar
    la respuesta: si un campo falta, está vacío o se desborda, la respuesta no
    se usa y el pipeline vuelve al párrafo único.
    """

    resumen: str = Field(min_length=80, max_length=1500)
    paralelas: str = Field(min_length=40, max_length=1000)
    oficiales: str = Field(min_length=40, max_length=1000)
    riesgo_pais: str = Field(min_length=40, max_length=1000)
    # Sin datos de BTC (Yahoo no respondió) la sección viene vacía
    btc: str | None = Field(default=None, max_length=1000)
