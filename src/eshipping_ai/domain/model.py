"""Domain entities (docs/05_modelo_datos.md).

Three layers: inputs stored as received (mail, message, document, ERP reads), immutable
observations (what a source said about a fact, with its quote) and recomputable conclusions
(current value of each field and verdicts against the ERP). All entities are immutable; a
change is a new entity or a new status, never an update in place.
"""

import hashlib
from typing import Annotated, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    model_validator,
)

from eshipping_ai.domain.identifiers import ContainerNumber, Reference, Sha256, UnLocode
from eshipping_ai.domain.vocabulary import (
    AliasType,
    AssociationMethod,
    AssociationStatus,
    CorrectionAction,
    EventClassifier,
    EventType,
    ExtractionTier,
    MailClass,
    ObservationStatus,
    Priority,
    SourceRank,
    SourceRole,
    TimePrecision,
    VerdictCode,
    VerdictStatus,
    Zone,
)

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
"""Calibrated probability that a value is correct (docs/07_fiabilidad.md §3)."""

EVIDENCE_MAX_CHARS = 500
"""Quotes are short on purpose: just the fragment that supports the value (minimisation)."""


class DomainModel(BaseModel):
    """Base of every entity: immutable, strict about unknown fields, trimmed strings."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


# --- Input layer --------------------------------------------------------------


class Mail(DomainModel):
    """A mail as received from the mailbox, or a mail embedded in another one.

    ``source_ref`` says where the mail came from (a file name, or the identifier of the
    message in the mailbox) and ``position`` the order of an embedded mail among those of
    its parent, from 0. Both trace a mail back to its source and let the evaluation pair
    it with its labelled counterpart.
    """

    mail_id: str
    rfc_message_id: str | None
    sha256: Sha256
    mailbox: str
    received_at: AwareDatetime
    raw_object_key: str
    size_bytes: NonNegativeInt
    parent_mail_id: str | None = None
    source_ref: str | None = None
    position: NonNegativeInt | None = None


class Message(DomainModel):
    """One message of a thread; a quoted message is stored once, identified by its hash."""

    message_id: str
    content_hash: Sha256
    sender_address: str
    sent_at: AwareDatetime
    subject: str
    language: str | None = None
    clean_body_key: str
    first_seen_mail_id: str


class Document(DomainModel):
    """An attachment, stored once per content."""

    document_id: str
    sha256: Sha256
    filename: str
    mime_type: str
    object_key: str
    text_key: str | None
    has_text_layer: bool
    ocr_applied: bool = False
    doc_type: str | None = None
    pages: PositiveInt | None = None


class ErpSnapshot(DomainModel):
    """A full or incremental read of the ERP."""

    snapshot_id: str
    read_at: AwareDatetime
    source: str
    sha256: Sha256
    row_count: NonNegativeInt


class ErpRecord(DomainModel):
    """The row of one shipment in an ERP read: original columns and normalised fields."""

    snapshot_id: str
    operation: Reference
    raw: dict[str, str]
    normalized: dict[str, str | None]
    field_updated_at: dict[str, AwareDatetime] = Field(default_factory=dict)


# --- Observation layer --------------------------------------------------------


class Shipment(DomainModel):
    """A shipment (expediente)."""

    shipment_id: str
    erp_operation: Reference | None = None
    created_at: AwareDatetime


class ShipmentAlias(DomainModel):
    """An identifier under which a shipment is recognised; the association index."""

    shipment_id: str
    alias_type: AliasType
    value: Reference
    valid_from: AwareDatetime
    valid_to: AwareDatetime | None = None
    source_observation_id: str | None = None


class Classification(DomainModel):
    """A class assigned to a message."""

    message_id: str
    mail_class: MailClass
    is_primary: bool
    confidence: Confidence
    tier: ExtractionTier
    extractor_version: str


class Association(DomainModel):
    """A message associated with a shipment; a message may belong to several shipments."""

    message_id: str
    shipment_id: str
    method: AssociationMethod
    matched_value: str
    confidence: Confidence
    status: AssociationStatus


class Evidence(DomainModel):
    """Literal quote supporting a value and its position in the stored clean text."""

    text: str = Field(min_length=1, max_length=EVIDENCE_MAX_CHARS)
    start: NonNegativeInt
    end: PositiveInt

    @model_validator(mode="after")
    def _check_span(self) -> Self:
        if self.end <= self.start:
            msg = "evidence end must be after its start"
            raise ValueError(msg)
        return self


class Provenance(DomainModel):
    """Which tier and which versions produced a value (RNF-41)."""

    tier: ExtractionTier
    extractor_version: str
    config_version: str
    llm_call_id: str | None = None


class Observation(DomainModel):
    """What one source said about one fact, with its quote. Never updated in place."""

    observation_id: str
    shipment_id: str | None
    message_id: str | None = None
    document_id: str | None = None
    event_type: EventType
    classifier: EventClassifier
    field: str = Field(pattern=r"^[a-z_]+(\.[a-z_]+)*$")
    value: str
    value_raw: str
    event_time: AwareDatetime | None = None
    event_time_end: AwareDatetime | None = None
    time_precision: TimePrecision | None = None
    location_unlocode: UnLocode | None = None
    location_raw: str | None = None
    vessel: str | None = None
    voyage: str | None = None
    equipment: tuple[ContainerNumber, ...] = ()
    source_role: SourceRole
    source_rank: SourceRank
    evidence: Evidence
    known_at: AwareDatetime
    recorded_at: AwareDatetime
    provenance: Provenance
    confidence: Confidence
    zone: Zone
    status: ObservationStatus = ObservationStatus.ACTIVE
    superseded_by: str | None = None
    superseded_at: AwareDatetime | None = None
    discard_reason: str | None = None

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        self._check_single_source()
        self._check_time()
        self._check_human_source()
        self._check_status()
        return self

    def _check_single_source(self) -> None:
        if (self.message_id is None) == (self.document_id is None):
            msg = "an observation comes from exactly one message or one document"
            raise ValueError(msg)

    def _check_time(self) -> None:
        if (self.event_time is None) != (self.time_precision is None):
            msg = "event_time and time_precision go together"
            raise ValueError(msg)
        is_range = self.time_precision is TimePrecision.RANGE
        if is_range != (self.event_time_end is not None):
            msg = "event_time_end is required for ranges and only for ranges"
            raise ValueError(msg)
        start, end = self.event_time, self.event_time_end
        if is_range and start is not None and end is not None and end <= start:
            msg = "a range must end after it starts"
            raise ValueError(msg)

    def _check_human_source(self) -> None:
        is_human_tier = self.provenance.tier is ExtractionTier.HUMAN
        if is_human_tier != (self.source_role is SourceRole.HUMAN_REVIEW):
            msg = "human corrections use the human tier and the human_review role together"
            raise ValueError(msg)

    def _check_status(self) -> None:
        superseded = self.status is ObservationStatus.SUPERSEDED
        if superseded != (self.superseded_by is not None and self.superseded_at is not None):
            msg = "a superseded observation records what superseded it and when"
            raise ValueError(msg)
        if self.status is ObservationStatus.REJECTED and not self.discard_reason:
            msg = "a rejected observation records why"
            raise ValueError(msg)

    @property
    def idempotency_key(self) -> str:
        """Key that makes re-processing with the same extractor version a no-op.

        It includes the shipment because one message can speak about several (A-19).
        """
        source = self.message_id or self.document_id
        parts = (
            source,
            self.shipment_id,
            self.field,
            self.value,
            self.provenance.extractor_version,
        )
        return hashlib.sha256("\x1f".join(str(part) for part in parts).encode()).hexdigest()


# --- Conclusion layer ---------------------------------------------------------


class FieldState(DomainModel):
    """Current value of a shipment field according to the mails (a projection)."""

    shipment_id: str
    field: str
    value: str | None
    winning_observation_id: str | None
    rule: str
    in_conflict: bool = False
    pending_confirmation: tuple[str, ...] = ()
    computed_at: AwareDatetime
    config_version: str

    @model_validator(mode="after")
    def _check_winner(self) -> Self:
        if (self.value is None) != (self.winning_observation_id is None):
            msg = "a current value always points to the observation it comes from"
            raise ValueError(msg)
        return self


class ErpRecordRef(DomainModel):
    """Reference to the ERP row a verdict was computed against."""

    snapshot_id: str
    operation: Reference


class Verdict(DomainModel):
    """Comparison of one field with one ERP read."""

    verdict_id: str
    shipment_id: str
    field: str
    code: VerdictCode
    mail_value: str | None
    erp_value: str | None
    erp_record: ErpRecordRef | None
    rule: str
    priority: Priority | None = None
    status: VerdictStatus = VerdictStatus.OPEN
    computed_at: AwareDatetime
    config_version: str


class Correction(DomainModel):
    """Decision of an operator on a review task (RF-70)."""

    correction_id: str
    task_id: str
    user_id: str
    action: CorrectionAction
    new_value: str | None = None
    reason: str | None = None
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _check_action(self) -> Self:
        if (self.action is CorrectionAction.CORRECT) != (self.new_value is not None):
            msg = "only a correction carries a new value, and it always does"
            raise ValueError(msg)
        if self.action is CorrectionAction.REJECT and not self.reason:
            msg = "a rejection records its reason"
            raise ValueError(msg)
        return self
