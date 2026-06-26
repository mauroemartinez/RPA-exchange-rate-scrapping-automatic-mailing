from datetime import date

import pytest

from models import FilaMacro


def test_fila_macro_rechaza_valores_no_positivos():
    with pytest.raises(ValueError, match="Validación Pydantic fallida"):
        FilaMacro.validar(
            {
                "Fecha": date(2026, 6, 26),
                "TCC_Blue": 0,
                "TCV_Blue": 1.0,
                "TCC_Billete": 1.0,
                "TCV_Billete": 1.0,
                "TCC_Divisas": 1.0,
                "TCV_Divisas": 1.0,
                "Solidario": 1.0,
                "TCV_MEP": 1.0,
                "riesgo_pais": 1.0,
                "TCC_Euro": 1.0,
                "TCV_Euro": 1.0,
                "fed_tea": 1.0,
                "bcra_tea": 1.0,
            }
        )


def test_fila_macro_valida_fila_correcta():
    fila = FilaMacro.validar(
        {
            "Fecha": date(2026, 6, 26),
            "TCC_Blue": 1.23,
            "TCV_Blue": 1.24,
            "TCC_Billete": 1.25,
            "TCV_Billete": 1.26,
            "TCC_Divisas": 1.27,
            "TCV_Divisas": 1.28,
            "Solidario": 1.29,
            "TCV_MEP": 1.30,
            "riesgo_pais": 1.31,
            "TCC_Euro": 1.32,
            "TCV_Euro": 1.33,
            "fed_tea": 1.34,
            "bcra_tea": 1.35,
        }
    )

    assert fila.Fecha == date(2026, 6, 26)
    assert fila.TCC_Blue == 1.23
