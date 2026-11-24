"""The operators' page, run headless with Streamlit's AppTest on a processed synthetic set."""

import io
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from eshipping_ai.entrypoints.cli import main

APP = Path(__file__).parents[2] / "src" / "eshipping_ai" / "entrypoints" / "streamlit_app.py"
NOW = "2026-10-07T08:00:00+02:00"


@pytest.fixture
def app(synthetic_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppTest:
    erp = str(synthetic_dir / "erp.csv")
    args = ["--workdir", str(tmp_path), "--now", NOW, "run", str(synthetic_dir / "mails")]
    assert main([*args, "--erp", erp, "--no-llm"], io.StringIO()) == 0
    monkeypatch.setenv("ESHIPPING_WORKDIR", str(tmp_path))
    monkeypatch.setenv("ESHIPPING_ERP", erp)
    monkeypatch.setenv("ESHIPPING_NOW", NOW)
    monkeypatch.delenv("ESHIPPING_DATABASE_URL", raising=False)
    page = AppTest.from_file(str(APP), default_timeout=30)
    page.run()
    assert not page.exception
    return page


def test_the_discrepancies_are_listed_by_priority(app: AppTest) -> None:
    rows = app.dataframe[0].value
    assert app.metric[0].value == str(len(rows))
    assert rows["Prioridad"].iloc[0] == "P1"
    assert "MATCH" not in set(rows["Veredicto"])


def test_the_shipment_shows_its_fields_and_timeline(app: AppTest) -> None:
    app.sidebar.selectbox[0].set_value("ES26900002").run()
    fields, timeline = app.dataframe[1].value, app.dataframe[2].value
    assert "vessel" in set(fields["Campo"])
    assert list(timeline["Conocido"]) == sorted(timeline["Conocido"])
    assert any("CELESTE FICTICIA" in str(quote) for quote in timeline["Cita"])


def test_a_correction_is_saved_and_the_shipment_reconciled(app: AppTest) -> None:
    app.sidebar.selectbox[0].set_value("ES26900002").run()
    form_field = next(s for s in app.selectbox if s.label == "Campo")
    form_field.set_value("vessel_departure")
    next(r for r in app.radio if r.label == "Decisión").set_value("Corregir el valor")
    next(t for t in app.text_input if t.label.startswith("Valor nuevo")).input("2026-10-01")
    next(t for t in app.text_input if t.label == "Motivo").input("confirmado")
    app.button[0].click().run()
    assert not app.exception
    assert "reconciliado" in app.success[0].value
    rows = app.dataframe[0].value
    departure = rows[(rows["Expediente"] == "ES26900002") & (rows["Campo"] == "vessel_departure")]
    assert departure.empty  # the corrected departure now matches the ERP


def test_an_invalid_correction_shows_an_error(app: AppTest) -> None:
    next(r for r in app.radio if r.label == "Decisión").set_value("Rechazar el valor")
    app.button[0].click().run()
    assert "reason" in app.error[0].value
