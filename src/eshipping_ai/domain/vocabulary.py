"""Closed vocabularies of the domain.

Mail classes and event codes follow the taxonomy (docs/03_taxonomia_y_ambiguedades.md),
which uses the DCSA event model with a few extensions (ADR-0006). Source roles, ranks and
verdicts follow the discrepancy policy (ADR-0009).
"""

from enum import StrEnum


class MailClass(StrEnum):
    """Class of a message in the taxonomy (docs/03 §2)."""

    BOOKING = "BKG"
    VESSEL = "VSL"
    TRANSPORT = "TRP"
    DOCUMENTATION = "DOC"
    CUSTOMS = "CUS"
    INSPECTION = "INS"
    COMMERCIAL = "COM"
    FINANCE = "FIN"
    OTHER = "OTR"


class EventType(StrEnum):
    """Event type: DCSA codes plus own extensions for customs, amendments and incidents."""

    DEPARTURE = "DEPA"
    ARRIVAL = "ARRI"
    GATE_OUT = "GTOT"
    STUFFING = "STUF"
    GATE_IN = "GTIN"
    LOADED = "LOAD"
    DISCHARGED = "DISC"
    BOOKING_CONFIRMED = "CONF"
    BOOKING_AMENDED = "AMND"
    SUBMITTED = "SUBM"
    BL_DRAFT = "DRFT"
    BL_ISSUED = "ISSU"
    BL_RELEASED = "RELS"
    CUSTOMS_REQUESTED = "CUS-REQ"
    CUSTOMS_RELEASED = "CUS-REL"
    DOCUMENT_CUTOFF = "DCO"
    VGM_CUTOFF = "VCO"
    FULL_CONTAINER_CUTOFF = "FCO"
    DELAY = "DLAY"
    ROLLED = "ROLL"
    VESSEL_CHANGE = "VCHG"
    INSPECTION = "INSP"


class EventClassifier(StrEnum):
    """State of the information: planned, estimated or actual (DCSA classifier)."""

    PLANNED = "PLN"
    ESTIMATED = "EST"
    ACTUAL = "ACT"


class TimePrecision(StrEnum):
    """How precise an event time is."""

    DATETIME = "datetime"
    DATE = "date"
    RANGE = "range"
    APPROX = "approx"


class SourceRole(StrEnum):
    """Role of the original author of a message (ADR-0009 §1)."""

    CARRIER_API = "carrier_api"
    CARRIER = "carrier"
    CUSTOMS_DOC = "customs_doc"
    CUSTOMS_AGENT = "customs_agent"
    HAULIER = "haulier"
    INTERNAL = "internal"
    CUSTOMER = "customer"
    INSPECTOR = "inspector"
    HUMAN_REVIEW = "human_review"


class SourceRank(StrEnum):
    """Authority of a source for a given field (ADR-0009 §2): A > B > C."""

    A = "A"
    B = "B"
    C = "C"


class ExtractionTier(StrEnum):
    """Cascade tier that produced a value (ADR-0008)."""

    RULE = "rule"
    TEMPLATE = "template"
    ML = "ml"
    LLM = "llm"
    HUMAN = "human"


class Zone(StrEnum):
    """Reliability zone of a value (docs/07_fiabilidad.md §4.3)."""

    AUTO = "auto"
    REVIEW = "review"
    NOT_PROPOSED = "not_proposed"


class ObservationStatus(StrEnum):
    """Life cycle of an observation; observations are never deleted."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class AliasType(StrEnum):
    """Kind of identifier under which a shipment is known."""

    BOOKING = "booking"
    OPERATION = "operation"
    CONTAINER = "container"
    BILL_OF_LADING = "bl"
    CUSTOMER_REFERENCE = "customer_ref"
    CUSTOMS_REFERENCE = "customs_ref"


class AssociationMethod(StrEnum):
    """How a message was associated with a shipment (RF-43)."""

    BOOKING = "booking"
    OPERATION = "operation"
    CONTAINER = "container"
    BILL_OF_LADING = "bl"
    THREAD_REFERENCE = "thread_ref"
    HUMAN = "human"


class AssociationStatus(StrEnum):
    """Review state of an association."""

    AUTO = "auto"
    IN_REVIEW = "in_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class VerdictCode(StrEnum):
    """Result of comparing a field with the ERP (ADR-0009 §4)."""

    MATCH = "MATCH"
    ERP_MISSING = "ERP_MISSING"
    ERP_ERROR = "ERP_ERROR"
    ERP_NEWER = "ERP_NEWER"
    DISCREPANCY = "DISCREPANCY"
    MAIL_MISSING = "MAIL_MISSING"
    NOT_IN_ERP = "NOT_IN_ERP"


class VerdictStatus(StrEnum):
    """Life cycle of a verdict shown to a person."""

    OPEN = "open"
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class Priority(StrEnum):
    """Review priority (ADR-0009 §6): P1 is the most urgent."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class CorrectionAction(StrEnum):
    """Decision of an operator on a review task."""

    ACCEPT = "accept"
    CORRECT = "correct"
    REJECT = "reject"
