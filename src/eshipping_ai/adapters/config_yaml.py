"""Loading of the versioned configuration files (``config/*.yaml``)."""

from pathlib import Path

import yaml

from eshipping_ai.domain.policy import ReconciliationConfig


def load_reconciliation_config(path: Path) -> ReconciliationConfig:
    """Read and validate the discrepancy policy.

    Args:
        path: YAML file, normally ``config/reconciliation.yaml``.

    Returns:
        The validated configuration; an unknown or mistyped key is an error.
    """
    return ReconciliationConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
