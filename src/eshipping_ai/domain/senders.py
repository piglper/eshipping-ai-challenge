"""Role of a sender and how it writes dates (RF-73, ADR-0013).

The role of the original author decides how much a value weighs (ADR-0009 §1), and the
date order of a sender settles ``09/10`` (day first or month first) without guessing.
Registering every domain by hand does not scale, so the role is resolved in a cascade,
from the surest signal to the weakest:

1. **Directory**: a short, curated list of domains that are known for sure, EShipping's own
   and a public register of carriers.
2. **Parties of the shipment in the ERP**: the ERP already says which carrier, customs agent
   and haulier handle each shipment; a sender whose domain or display name is one of them
   takes that role.
3. **Default**: an unknown sender is informative (a customer), the role with the least
   authority, so that a wrong guess can only send a value to review.

A profile learned from the history of each domain (what kind of mails it sends) is the
fourth signal of the design (ADR-0013); the PoC leaves it out, because its sample is too
small to learn from without learning from the evaluation set.
"""

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from pydantic import Field

from eshipping_ai.domain.model import DomainModel, ErpRecord
from eshipping_ai.domain.vocabulary import SourceRole

_DOMAIN_RE = re.compile(r"@([A-Za-z0-9.-]+)")
_SECOND_LEVEL = frozenset({"co", "com", "org", "net", "gob", "gov", "ac", "edu"})
_LEGAL_FORMS = frozenset(
    {
        "sl",
        "sa",
        "slu",
        "sau",
        "sll",
        "scoop",
        "sc",
        "cb",
        "ltd",
        "limited",
        "inc",
        "gmbh",
        "bv",
        "spa",
        "srl",
        "sarl",
        "llc",
        "co",
        "corp",
    }
)
_CONNECTORS = frozenset({"de", "del", "la", "las", "los", "el", "y", "and", "the", "of"})
_MIN_LABEL = 4
_MIN_NAME = 6
# When a sender is several parties of a shipment, the one with most authority is kept.
_ROLE_ORDER = (
    SourceRole.CARRIER,
    SourceRole.CUSTOMS_AGENT,
    SourceRole.HAULIER,
    SourceRole.CUSTOMER,
)


class SenderProfile(DomainModel):
    """What is known about the senders of a domain."""

    role: SourceRole
    month_first: bool | None = None


class PartyColumns(DomainModel):
    """ERP columns that name the parties of one role, and how those parties write dates."""

    columns: tuple[str, ...]
    month_first: bool | None = None


class SenderDirectory(DomainModel):
    """Curated profiles by mail domain, the ERP columns of each party and the default."""

    version: str
    default: SenderProfile
    domains: dict[str, SenderProfile] = Field(default_factory=dict)
    erp_parties: dict[SourceRole, PartyColumns] = Field(default_factory=dict)

    def profile_for(self, address: str) -> SenderProfile | None:
        """Find the curated profile of a sender.

        Args:
            address: Sender as written in the header, with or without a display name.

        Returns:
            The profile of the most specific matching domain (a subdomain matches its
            parent), or None if the domain is not in the directory.
        """
        domain = _domain(address)
        if domain is None:
            return None
        candidates = [
            known for known in self.domains if domain == known or domain.endswith(f".{known}")
        ]
        if not candidates:
            return None
        return self.domains[max(candidates, key=len)]

    def resolve(
        self, address: str, parties: Mapping[SourceRole, Sequence[str]] | None = None
    ) -> ResolvedSender:
        """Resolve the role of a sender with the cascade of the module.

        Args:
            address: Sender as written in the header.
            parties: Names of the parties of the shipments the message belongs to, by role.

        Returns:
            The role, the date order and the signal that decided them.
        """
        profile = self.profile_for(address)
        if profile is not None:
            return ResolvedSender(profile.role, profile.month_first, "directory")
        for role in _ROLE_ORDER:
            names = (parties or {}).get(role, ())
            if any(names_sender(name, address) for name in names):
                columns = self.erp_parties.get(role)
                month_first = columns.month_first if columns else self.default.month_first
                return ResolvedSender(role, month_first, "erp")
        return ResolvedSender(self.default.role, self.default.month_first, "default")

    def parties_of(self, records: Iterable[ErpRecord]) -> dict[str, dict[SourceRole, list[str]]]:
        """Read the parties of each shipment from an ERP read.

        Args:
            records: Rows of an ERP read.

        Returns:
            Operation number to role to party names; a cell may hold several names
            separated by commas, semicolons or slashes.
        """
        result: dict[str, dict[SourceRole, list[str]]] = {}
        for record in records:
            parties: dict[SourceRole, list[str]] = {}
            for role, party in self.erp_parties.items():
                names = [
                    name.strip()
                    for column in party.columns
                    for name in re.split(r"[,;/]", record.raw.get(column, "") or "")
                    if name.strip()
                ]
                if names:
                    parties[role] = names
            result[record.operation] = parties
        return result


@dataclass(frozen=True, slots=True)
class ResolvedSender:
    """The role of a sender, its date order and which signal of the cascade decided."""

    role: SourceRole
    month_first: bool | None
    basis: str


def _domain(address: str) -> str | None:
    match = _DOMAIN_RE.search(address)
    return match[1].lower().rstrip(".") if match else None


def _compact(text: str) -> str:
    """Lower case letters and digits only, without accents, legal forms or connectors."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    tokens = re.split(r"[^a-z0-9]+", plain.replace(".", ""))
    ignored = _LEGAL_FORMS | _CONNECTORS
    return "".join(t for t in tokens if t and t not in ignored and len(t) > 1)


def _label(domain: str) -> str:
    """The name part of a domain: ``transgarcia`` in ``mail.transgarcia.co.uk``."""
    parts = domain.split(".")
    if len(parts) >= 3 and parts[-2] in _SECOND_LEVEL:  # noqa: PLR2004 - name.co.uk
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else parts[0]  # noqa: PLR2004 - name.tld


def names_sender(party: str, address: str) -> bool:
    """Tell whether a party of the ERP is the sender of a mail.

    The comparison is deliberately strict, because a false match gives authority to a
    sender that has none: the name of the party, without accents, spaces or legal form,
    must contain the name part of the domain (or the other way round), or appear whole in
    the display name.

    Args:
        party: Name of the party as written in the ERP.
        address: Sender as written in the header.

    Returns:
        True if the sender is that party.
    """
    name = _compact(party)
    if len(name) < _MIN_NAME:
        return False
    domain = _domain(address)
    if domain is not None:
        label = _compact(_label(domain))
        if len(label) >= _MIN_LABEL and (label in name or name in label):
            return True
    display = _compact(address.split("<", 1)[0]) if "<" in address else ""
    return bool(display) and name in display
