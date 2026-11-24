"""Classification and triage of a message with keyword rules (RF-10, RF-12).

This is the first tier of the classifier (ADR-0008): cheap, explainable and with no model.
Keywords come from the taxonomy (docs/03_taxonomia_y_ambiguedades.md §2). A hit in the
subject weighs more than a hit in the body. A message with no signal is ``OTR``, and a
message that carries no identifier at all is noise: it cannot belong to a shipment.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from eshipping_ai.domain.vocabulary import MailClass
from eshipping_ai.extraction.locations import strip_accents
from eshipping_ai.extraction.references import find_references

SUBJECT_WEIGHT = 3
BODY_WEIGHT = 1

_KEYWORDS: dict[MailClass, tuple[str, ...]] = {
    MailClass.BOOKING: ("booking", "amendment", "aviso booking", "confirmation", "reserva"),
    MailClass.VESSEL: (
        "retras",
        "delay",
        "omite",
        "omit",
        "rolled",
        "rollover",
        "roleo",
        "nuevo barco",
        "new vessel",
        "cambio de buque",
        "change of vessel",
        "vessel change",
    ),
    MailClass.TRANSPORT: (
        "orden de transporte",
        "transport order",
        "ventana de carga",
        "programacion",
        "reserva transporte",
        "carga en almacen",
        "cargado",
        "recogida",
    ),
    MailClass.DOCUMENTATION: (
        "shipping instruction",
        "vgm",
        "bl draft",
        "telex",
        "swb",
        "instrucciones de embarque",
        "bill of lading",
        "b/l",
    ),
    MailClass.CUSTOMS: ("levante", "despacho", "dua", "customs", "aduana"),
    MailClass.INSPECTION: ("inspection", "inspeccion", "certificado", "certificate"),
    MailClass.COMMERCIAL: ("cotizacion", "tarifa", "oferta", "quotation", "quote", "pricing"),
    MailClass.FINANCE: ("invoice", "factura", "demurrage", "estadia", "debit note"),
}
_URGENT = (
    "cut-off",
    "cutoff",
    "cut off",
    "closing",
    "retras",
    "delay",
    "rolled",
    "rollover",
    "roleo",
    "cambio de buque",
    "omite escala",
    "nuevo barco",
    "new vessel",
    "urgente",
    "urgent",
    "asap",
)
_OPTIONS_RE = re.compile(r"\b(?:opcion|option)\s*\d", re.IGNORECASE)
_CONFIRMATION_RE = re.compile(
    r"\b(?:confirm|booking confirmado|tomad nota|please note|we are pleased)", re.IGNORECASE
)


class Priority(StrEnum):
    """Processing lane (ADR-0007): urgent messages are taken first."""

    URGENT = "urgent"
    NORMAL = "normal"


@dataclass(frozen=True, slots=True)
class ClassMatch:
    """A class assigned to a message, with the score that earned it."""

    mail_class: MailClass
    score: int
    is_primary: bool


@dataclass(frozen=True, slots=True)
class Triage:
    """Result of the triage: lane, noise filter and the reason, for the audit trail."""

    priority: Priority
    is_noise: bool
    reason: str


def _hits(text: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def classify(subject: str, body: str) -> list[ClassMatch]:
    """Assign the classes of the taxonomy to a message.

    Args:
        subject: Subject of the message.
        body: Clean body of the message.

    Returns:
        The matching classes by decreasing score, the first one marked as primary; ``OTR``
        alone if no rule matches.
    """
    head, text = strip_accents(subject), strip_accents(body)
    scores = {
        mail_class: SUBJECT_WEIGHT * _hits(head, words) + BODY_WEIGHT * _hits(text, words)
        for mail_class, words in _KEYWORDS.items()
    }
    ranked = sorted(
        ((cls, score) for cls, score in scores.items() if score > 0),
        key=lambda item: -item[1],
    )
    if not ranked:
        return [ClassMatch(MailClass.OTHER, 0, is_primary=True)]
    return [
        ClassMatch(cls, score, is_primary=index == 0) for index, (cls, score) in enumerate(ranked)
    ]


def triage(subject: str, body: str) -> Triage:
    """Decide the lane of a message and whether it can be dropped as noise (RF-12).

    Args:
        subject: Subject of the message.
        body: Clean body of the message.

    Returns:
        ``urgent`` if it talks about cut-offs, delays or rollovers; noise if it has no
        identifier of any kind, because then it cannot be associated with a shipment.
    """
    text = strip_accents(f"{subject}\n{body}")
    if not find_references(f"{subject}\n{body}"):
        return Triage(Priority.NORMAL, is_noise=True, reason="no_identifiers")
    urgent = next((word for word in _URGENT if word in text), None)
    if urgent is not None:
        return Triage(Priority.URGENT, is_noise=False, reason=f"keyword:{urgent}")
    return Triage(Priority.NORMAL, is_noise=False, reason="default")


def lists_offered_options(text: str) -> bool:
    """Tell whether a message offers vessel options instead of confirming one (A-25).

    Args:
        text: Text of the message.

    Returns:
        True if it lists numbered options and says nothing that confirms a booking.
    """
    plain = strip_accents(text)
    return bool(_OPTIONS_RE.search(plain)) and not _CONFIRMATION_RE.search(plain)
