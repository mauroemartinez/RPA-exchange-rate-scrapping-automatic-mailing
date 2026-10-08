from datetime import UTC, date, datetime

from reporte import fechas


def _reloj_utc(monkeypatch, instante_utc: datetime):
    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return instante_utc.astimezone(tz)

    monkeypatch.setattr(fechas, "datetime", Reloj)


def test_despues_de_las_21_sigue_siendo_hoy_en_argentina(monkeypatch):
    # 01:30 UTC del 7 son las 22:30 del 6 en Buenos Aires: el bug del contenedor en UTC
    _reloj_utc(monkeypatch, datetime(2026, 10, 7, 1, 30, tzinfo=UTC))
    assert fechas.hoy() == date(2026, 10, 6)


def test_ahora_devuelve_hora_argentina_sin_tzinfo(monkeypatch):
    _reloj_utc(monkeypatch, datetime(2026, 10, 6, 12, 0, tzinfo=UTC))
    ahora = fechas.ahora()
    assert ahora.tzinfo is None
    assert (ahora.hour, ahora.minute) == (9, 0)


def test_meses_abreviados_como_el_locale_es_es_de_windows():
    meses = [fechas.mes_abreviado(date(2026, m, 1)) for m in range(1, 13)]
    assert meses == ["ene.", "feb.", "mar.", "abr.", "may.", "jun.",
                     "jul.", "ago.", "sep.", "oct.", "nov.", "dic."]
