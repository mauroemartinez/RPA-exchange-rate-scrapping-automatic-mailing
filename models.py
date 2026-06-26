from pydantic import BaseModel, Field
from datetime import date
from typing import Optional


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

    # Estos campos no existen en fila_nueva todavía — se agregan en Supabase después
    ai_paragraph: Optional[str] = None
    ai_model: Optional[str] = None
