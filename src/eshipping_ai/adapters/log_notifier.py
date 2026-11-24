"""Notifier of the PoC (``Notifier``): urgent notices go to the log and to the report.

Only identifiers and codes are logged, never the content of a mail (docs/09_seguridad.md).
"""

import logging
from collections.abc import Sequence

from eshipping_ai.domain.model import Verdict

logger = logging.getLogger(__name__)


class LogNotifier:
    """Keeps the urgent notices of a run and writes one log line per shipment."""

    def __init__(self) -> None:
        """Create a notifier with no notices."""
        self.notices: list[tuple[str, list[Verdict]]] = []

    def notify(self, shipment_id: str, verdicts: Sequence[Verdict]) -> None:
        """Record one notice about the urgent verdicts of a shipment."""
        self.notices.append((shipment_id, list(verdicts)))
        fields = ", ".join(f"{v.field}={v.code.value}" for v in verdicts)
        logger.warning("urgent: shipment %s: %s", shipment_id, fields)
