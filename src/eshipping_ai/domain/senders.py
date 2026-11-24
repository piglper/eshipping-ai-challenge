"""Directory of senders (RF-73): what each sender is and how it writes dates.

The role of the original author decides how much a value weighs (ADR-0009 §1), and the
date order of a sender settles ``09/10`` (day first or month first) without guessing. The
directory is configuration, keyed by mail domain; an unknown sender is a customer, the
role with the least authority.
"""

import re

from pydantic import Field

from eshipping_ai.domain.model import DomainModel
from eshipping_ai.domain.vocabulary import SourceRole

_DOMAIN_RE = re.compile(r"@([A-Za-z0-9.-]+)")


class SenderProfile(DomainModel):
    """What is known about the senders of a domain."""

    role: SourceRole
    month_first: bool | None = None


class SenderDirectory(DomainModel):
    """Profiles by mail domain, with a default for unknown senders."""

    version: str
    default: SenderProfile
    domains: dict[str, SenderProfile] = Field(default_factory=dict)

    def profile_for(self, address: str) -> SenderProfile:
        """Find the profile of a sender.

        Args:
            address: Sender as written in the header, with or without a display name.

        Returns:
            The profile of the most specific matching domain (a subdomain matches its
            parent), or the default one.
        """
        match = _DOMAIN_RE.search(address)
        if match is None:
            return self.default
        domain = match[1].lower().rstrip(".")
        candidates = [
            known for known in self.domains if domain == known or domain.endswith(f".{known}")
        ]
        if not candidates:
            return self.default
        return self.domains[max(candidates, key=len)]
