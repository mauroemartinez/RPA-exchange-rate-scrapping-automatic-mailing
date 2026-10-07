"""Prototipo de dashboard: corre la app sin navegador, desde un CSV (sin base)."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit", reason="el dashboard tiene sus propias dependencias: dashboard/requirements.txt")
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent.parent / "dashboard" / "app.py"


def test_el_dashboard_arranca_desde_el_csv(tmp_path, historico, monkeypatch):
    csv = tmp_path / "historico.csv"
    historico.to_csv(csv, index=False)
    monkeypatch.setenv("DASHBOARD_CSV", str(csv))

    app = AppTest.from_file(str(APP), default_timeout=60).run()

    assert not app.exception
    assert app.title[0].value.startswith("📈")
    assert [m.label for m in app.metric] == ["Blue", "MEP", "Billete BNA", "Riesgo país", "BADLAR (TEA)"]
    assert len(app.tabs) == 6
