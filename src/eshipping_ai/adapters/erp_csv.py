"""Read-only access to the ERP through its CSV export (``ERPGateway``, RF-50).

The export is UTF-8 with a BOM, ``;`` as separator, decimal comma and ``dd/mm/yyyy`` dates,
with stray spaces in some values (A-21). Each row keeps its columns, trimmed, and gets a
normalised view with the fields the policy compares. The ERP is never written to (RF-55).
"""

import csv
import hashlib
import io
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from eshipping_ai.domain.model import ErpRecord, ErpSnapshot

_DATE_COLUMNS = {
    "Salida": "vessel_departure",
    "Llegada": "vessel_arrival_pod",
    "F. Carga": "stuffing",
    "Despacho": "customs_release",
}
_FLAG_COLUMNS = {"SalidaOK": "vessel_departure_actual", "LlegadaOK": "vessel_arrival_actual"}
_TEXT_COLUMNS = {
    "Operación": "operation",
    "Booking": "booking",
    "Buque": "vessel",
    "Cont": "equipment_count",
    "Locode Origen": "pol",
    "Locode Destino": "pod",
    "Lugar Recogida": "stuffing_place",
}


def _blank_to_none(value: str | None) -> str | None:
    stripped = (value or "").strip()
    return stripped or None


def _iso_date(value: str | None) -> str | None:
    text = _blank_to_none(value)
    if text is None:
        return None
    try:
        day, month, year = text.split("/")
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def normalize_row(row: dict[str, str]) -> dict[str, str | None]:
    """Normalise the columns the policy compares: trim, ISO dates and ``true``/``false`` flags.

    Args:
        row: Original columns of one ERP row.

    Returns:
        Normalised fields; an empty or unreadable value is None.
    """
    normalized: dict[str, str | None] = {
        key: _blank_to_none(row.get(column)) for column, key in _TEXT_COLUMNS.items()
    }
    normalized |= {key: _iso_date(row.get(column)) for column, key in _DATE_COLUMNS.items()}
    for column, key in _FLAG_COLUMNS.items():
        flag = (_blank_to_none(row.get(column)) or "").upper()
        normalized[key] = {"SI": "true", "SÍ": "true", "NO": "false"}.get(flag)
    return normalized


class CsvErpGateway:
    """Reads the ERP export from a CSV file."""

    def __init__(self, path: Path, read_at: datetime | None = None) -> None:
        """Create a gateway.

        Args:
            path: The CSV export.
            read_at: When the export was taken; the modification time of the file if omitted.
        """
        self._path = path
        self._read_at = read_at

    def read(self) -> tuple[ErpSnapshot, Sequence[ErpRecord]]:
        """Read the export.

        Returns:
            The snapshot, identified by the hash of the file, and one record per row.
        """
        content = self._path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        read_at = self._read_at or datetime.fromtimestamp(self._path.stat().st_mtime, tz=UTC)
        snapshot_id = f"erp-{digest[:16]}"
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), delimiter=";")
        records = []
        for row in reader:
            cleaned = {column: value or "" for column, value in row.items() if column}
            operation = _blank_to_none(cleaned.get("Operación"))
            if operation is None:
                continue
            records.append(
                ErpRecord(
                    snapshot_id=snapshot_id,
                    operation=operation,
                    raw=cleaned,
                    normalized=normalize_row(cleaned),
                )
            )
        snapshot = ErpSnapshot(
            snapshot_id=snapshot_id,
            read_at=read_at,
            source=self._path.name,
            sha256=digest,
            row_count=len(records),
        )
        return snapshot, records
