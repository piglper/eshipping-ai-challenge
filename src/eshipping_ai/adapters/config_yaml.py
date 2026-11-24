"""Loading of the versioned configuration files (``config/*.yaml``)."""

from pathlib import Path

import yaml

from eshipping_ai.domain.policy import ReconciliationConfig
from eshipping_ai.domain.senders import SenderDirectory


def load_reconciliation_config(path: Path) -> ReconciliationConfig:
    """Read and validate the discrepancy policy.

    Args:
        path: YAML file, normally ``config/reconciliation.yaml``.

    Returns:
        The validated configuration; an unknown or mistyped key is an error.
    """
    return ReconciliationConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_sender_directory(path: Path) -> SenderDirectory:
    """Read and validate the directory of senders.

    Args:
        path: YAML file, normally ``config/senders.yaml``.

    Returns:
        The validated directory; an unknown or mistyped key is an error.
    """
    return SenderDirectory.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
