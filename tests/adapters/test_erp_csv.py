from datetime import UTC, datetime
from pathlib import Path

from eshipping_ai.adapters.config_yaml import load_reconciliation_config
from eshipping_ai.adapters.erp_csv import CsvErpGateway, normalize_row
from tests.builders import CONFIG_PATH


def test_reads_the_synthetic_export_and_normalises_it(synthetic_dir: Path) -> None:
    read_at = datetime(2026, 10, 7, 6, 0, tzinfo=UTC)
    snapshot, records = CsvErpGateway(synthetic_dir / "erp.csv", read_at).read()
    assert (snapshot.row_count, snapshot.read_at, snapshot.source) == (4, read_at, "erp.csv")
    assert snapshot.snapshot_id == f"erp-{snapshot.sha256[:16]}"
    first = records[0]
    assert first.operation == "ES26900001"
    assert first.raw["Booking"] == "990000101"  # stray spaces are trimmed (A-21)
    assert first.raw["Tipo Producto"] == "ACEITE DE OLIVA"
    assert first.normalized["booking"] == "990000101"
    assert first.normalized["vessel_departure"] == "2026-10-08"
    assert first.normalized["vessel_departure_actual"] == "false"
    assert first.normalized["customs_release"] is None
    assert first.normalized["equipment_count"] == "1"


def test_flags_dates_and_blanks() -> None:
    row = {
        "Salida": "10/04/2026",
        "SalidaOK": "SI",
        "LlegadaOK": "",
        "Despacho": " ",
        "Llegada": "31/02/2026",
    }
    normalized = normalize_row(row)
    assert normalized["vessel_departure"] == "2026-04-10"
    assert normalized["vessel_departure_actual"] == "true"
    assert normalized["vessel_arrival_actual"] is None
    assert normalized["customs_release"] is None
    assert normalized["vessel_arrival_pod"] is None  # not a real date


def test_read_time_defaults_to_the_file_modification_time(synthetic_dir: Path) -> None:
    snapshot, _ = CsvErpGateway(synthetic_dir / "erp.csv").read()
    assert snapshot.read_at.tzinfo is UTC


def test_rows_without_an_operation_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "erp.csv"
    path.write_bytes("﻿Operación;Booking\r\nES26900001;990000101\r\n;990000999\r\n".encode())
    _, records = CsvErpGateway(path).read()
    assert [r.operation for r in records] == ["ES26900001"]


def test_the_shipped_configuration_is_valid() -> None:
    config = load_reconciliation_config(CONFIG_PATH)
    assert config.fields["vessel_departure"].critical
    assert config.fields["cutoff_full"].erp_key is None
