"""Use case: process the stored messages (RF-10 to RF-14, RF-20 to RF-23, RF-40 to RF-44).

Every mail is read as a thread. Its identifiers are gathered from all its messages and
attachments, because the booking is usually in the subject of the newest message and the
replies do not repeat it. A thread with no identifier at all is noise (RF-12); one with
identifiers is associated with the shipments of the index (see ``associate``). Each
message is classified and its candidates become observations, one per associated shipment,
with the zone that its confidence earns (docs/07_fiabilidad.md §4). What the rules cannot
read is asked to the LLM, only for the fields still pending and with its quote checked
(``llm_extractor``); without a model it is left for an operator.

The evidence of an observation points into the text the rules read: ``Asunto: <subject>``,
a line break and the clean body for a message, or the text of the attachment for a document.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, tzinfo

from eshipping_ai.application.associate import Match, find_shipments, learn_aliases
from eshipping_ai.domain.model import (
    EVIDENCE_MAX_CHARS,
    Association,
    Classification,
    Evidence,
    Observation,
    Provenance,
)
from eshipping_ai.domain.policy import ReconciliationConfig, rank_for
from eshipping_ai.domain.ports import (
    AliasStore,
    Clock,
    InboxReader,
    LLMClient,
    LLMError,
    ObjectStore,
    ObservationStore,
    ProcessingStore,
    ThreadMessage,
    ThreadView,
)
from eshipping_ai.domain.senders import ResolvedSender, SenderDirectory
from eshipping_ai.domain.vocabulary import (
    AssociationStatus,
    ExtractionTier,
    MailClass,
    SourceRole,
    Zone,
)
from eshipping_ai.extraction.classify import classify
from eshipping_ai.extraction.events import (
    Candidate,
    Identifiers,
    extract_candidates,
    find_identifiers,
)
from eshipping_ai.extraction.llm_extractor import (
    PROMPT_VERSION,
    build_request,
    parse_response,
    pending_fields,
)
from eshipping_ai.extraction.thread import clean_body

EXTRACTOR_VERSION = "rules-1"
AUTO_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.50
_OFFERED_FACTOR = 0.5
_MAX_LEARNING_PASSES = 3
_MAX_CLASS_CONFIDENCE = 0.95
_SUBJECT_PREFIX = "Asunto: "


@dataclass(slots=True)
class ProcessReport:
    """What a processing run did; counts only, never content."""

    threads: int = 0
    messages: int = 0
    noise: int = 0
    unassociated: int = 0
    in_review: int = 0
    aliases_learned: int = 0
    observations: int = 0
    zones: Counter[str] = field(default_factory=Counter)
    classes: Counter[str] = field(default_factory=Counter)
    tiers: Counter[str] = field(default_factory=Counter)
    llm_calls: int = 0
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    llm_rejected: Counter[str] = field(default_factory=Counter)
    roles: Counter[str] = field(default_factory=Counter)


@dataclass(frozen=True, slots=True)
class _Texts:
    """What the extractors read of a message: its text and the text of its attachments."""

    subject: str
    body: str
    documents: tuple[tuple[str, str], ...]  # (document_id, text)

    @property
    def message(self) -> str:
        return f"{_SUBJECT_PREFIX}{self.subject}\n{self.body}"


def _zone(confidence: float) -> Zone:
    if confidence >= AUTO_THRESHOLD:
        return Zone.AUTO
    if confidence >= REVIEW_THRESHOLD:
        return Zone.REVIEW
    return Zone.NOT_PROPOSED


class ProcessMessages:
    """Classifies, associates and extracts the observations of every pending message."""

    def __init__(  # noqa: PLR0913, PLR0917 - one collaborator per port
        self,
        inbox: InboxReader,
        objects: ObjectStore,
        aliases: AliasStore,
        processing: ProcessingStore,
        observations: ObservationStore,
        clock: Clock,
        config: ReconciliationConfig,
        senders: SenderDirectory,
        local_tz: tzinfo,
        llm: LLMClient | None = None,
        parties: Mapping[str, Mapping[SourceRole, Sequence[str]]] | None = None,
    ) -> None:
        """Create the use case.

        Args:
            inbox: Where the stored threads are read from.
            objects: Store of the clean bodies and the text of the attachments.
            aliases: The association index, which grows as aliases are learned.
            processing: Where classifications and associations are kept.
            observations: Where the observations are kept.
            clock: Current time.
            config: Discrepancy policy, for the authority of each source.
            senders: Roles and date order of the senders.
            local_tz: Time zone of the places of the events (A-11).
            llm: Model for what the rules leave pending; without it the cascade stops at
                the rules and what is pending is left for an operator (``--no-llm``).
            parties: Shipment to role to the names of its parties in the ERP, which give
                the role of the senders the directory does not know (ADR-0013).
        """
        self._inbox = inbox
        self._objects = objects
        self._aliases = aliases
        self._processing = processing
        self._observations = observations
        self._clock = clock
        self._config = config
        self._senders = senders
        self._llm = llm
        self._tz = local_tz
        self._parties = parties or {}

    def run(self) -> ProcessReport:
        """Process every message that has not been classified yet."""
        report = ProcessReport()
        threads = [self._inbox.thread(mail_id) for mail_id in self._inbox.unprocessed_mail_ids()]
        texts = [self._texts(thread) for thread in threads]
        identifiers = [self._identifiers(thread_texts) for thread_texts in texts]
        report.aliases_learned = self._learn(threads, identifiers)
        seen: set[str] = set()  # a quoted message appears in several threads, once is enough
        for thread, thread_texts, found in zip(threads, texts, identifiers, strict=True):
            self._process(thread, thread_texts, found, seen, report)
        return report

    def _learn(self, threads: list[ThreadView], identifiers: list[Identifiers]) -> int:
        """Learn aliases from every thread until a pass learns nothing (chained rollovers)."""
        total = 0
        for _ in range(_MAX_LEARNING_PASSES):
            learned = 0
            for thread, found in zip(threads, identifiers, strict=True):
                matches = find_shipments(found, self._aliases)
                at = max(item.message.sent_at for item in thread.messages)
                learned += learn_aliases(matches, found, self._aliases, at)
            total += learned
            if not learned:
                break
        return total

    def _texts(self, thread: ThreadView) -> dict[str, _Texts]:
        result: dict[str, _Texts] = {}
        for item in thread.messages:
            body = self._objects.get(item.message.clean_body_key).decode()
            documents = tuple(
                (document.document_id, self._objects.get(document.text_key).decode())
                for document in item.documents
                if document.text_key
            )
            result[item.message.message_id] = _Texts(
                subject=item.message.subject, body=clean_body(body) or body, documents=documents
            )
        return result

    @staticmethod
    def _identifiers(texts: dict[str, _Texts]) -> Identifiers:
        found = Identifiers(bookings=(), previous_bookings=(), containers=())
        for item in texts.values():
            for part in (item.message, *(text for _, text in item.documents)):
                found = found.merged(find_identifiers(part))
        return found

    def _process(
        self,
        thread: ThreadView,
        texts: dict[str, _Texts],
        identifiers: Identifiers,
        seen: set[str],
        report: ProcessReport,
    ) -> None:
        report.threads += 1
        matches = [] if identifiers.is_empty else find_shipments(identifiers, self._aliases)
        for item in thread.messages:
            if item.processed or item.message.message_id in seen:
                continue
            seen.add(item.message.message_id)
            read = texts[item.message.message_id]
            report.messages += 1
            mail_class = self._classify(item, read, report)
            if identifiers.is_empty:
                report.noise += 1
            elif not matches:
                report.unassociated += 1
            else:
                self._extract(item, read, mail_class, matches, identifiers, report)

    def _classify(self, item: ThreadMessage, read: _Texts, report: ProcessReport) -> MailClass:
        classifications = [
            Classification(
                message_id=item.message.message_id,
                mail_class=match.mail_class,
                is_primary=match.is_primary,
                confidence=min(_MAX_CLASS_CONFIDENCE, 0.5 + 0.1 * match.score),
                tier=ExtractionTier.RULE,
                extractor_version=EXTRACTOR_VERSION,
            )
            for match in classify(read.subject, read.body)
        ]
        self._processing.add_classifications(classifications)
        primary = next(c.mail_class for c in classifications if c.is_primary)
        report.classes[primary.value] += 1
        return primary

    def _extract(  # noqa: PLR0913, PLR0917 - the message and the context it is read in
        self,
        item: ThreadMessage,
        read: _Texts,
        mail_class: MailClass,
        matches: list[Match],
        identifiers: Identifiers,
        report: ProcessReport,
    ) -> None:
        message = item.message
        self._processing.add_associations(
            Association(
                message_id=message.message_id,
                shipment_id=match.shipment_id,
                method=match.method,
                matched_value=match.matched_value,
                confidence=match.confidence,
                status=match.status,
            )
            for match in matches
        )
        report.in_review += sum(match.status is AssociationStatus.IN_REVIEW for match in matches)
        profile = self._sender(message.sender_address, matches)
        report.roles[f"{profile.role.value}:{profile.basis}"] += 1
        sources = [(read.message, None), *((text, doc_id) for doc_id, text in read.documents)]
        for text, document_id in sources:
            candidates = extract_candidates(
                text, message.sent_at.date(), self._tz, month_first=profile.month_first
            )
            versioned = [(candidate, EXTRACTOR_VERSION) for candidate in candidates]
            if document_id is None:
                versioned += self._ask_llm(
                    text, message.sent_at.date(), mail_class, candidates, report
                )
            for candidate, version in versioned:
                if (
                    candidate.field == "booking"
                    and candidate.value in identifiers.previous_bookings
                ):
                    continue  # the thread says it was replaced (A-20): an alias, not a value
                for match in matches:
                    observation = self._observation(
                        candidate, text, item, document_id, match, profile.role, version
                    )
                    new = self._observations.add_observations([observation])
                    report.observations += new
                    report.zones[observation.zone.value] += new
                    report.tiers[candidate.tier.value] += new

    def _sender(self, address: str, matches: list[Match]) -> ResolvedSender:
        """Resolve the sender against the parties of every shipment the message is about."""
        parties: dict[SourceRole, list[str]] = {}
        for match in matches:
            for role, names in self._parties.get(match.shipment_id, {}).items():
                parties.setdefault(role, []).extend(names)
        return self._senders.resolve(address, parties)

    def _ask_llm(
        self,
        text: str,
        sent_on: date,
        mail_class: MailClass,
        found: list[Candidate],
        report: ProcessReport,
    ) -> list[tuple[Candidate, str]]:
        """Ask the model only for the fields the rules left pending (ADR-0008)."""
        fields = pending_fields(mail_class, found, text)
        if self._llm is None or not fields:
            return []
        request = build_request(text, fields, sent_on)
        report.llm_calls += 1
        try:
            response = self._llm.complete(request)
        except LLMError:
            report.llm_rejected["call_failed"] += 1
            return []
        report.llm_input_tokens += response.input_tokens
        report.llm_output_tokens += response.output_tokens
        outcome = parse_response(response, text, fields, sent_on, self._tz)
        report.llm_rejected.update(outcome.rejected)
        version = f"{PROMPT_VERSION}:{response.model}"
        return [(candidate, version) for candidate in outcome.candidates]

    def _observation(  # noqa: PLR0913, PLR0917 - everything the observation records
        self,
        candidate: Candidate,
        text: str,
        item: ThreadMessage,
        document_id: str | None,
        match: Match,
        role: SourceRole,
        extractor_version: str,
    ) -> Observation:
        message = item.message
        confidence = min(candidate.confidence, match.confidence)
        if candidate.offered:
            confidence *= _OFFERED_FACTOR
        quote = text[candidate.start : candidate.end][:EVIDENCE_MAX_CHARS]
        draft = Observation(
            observation_id="pending",
            shipment_id=match.shipment_id,
            message_id=None if document_id else message.message_id,
            document_id=document_id,
            event_type=candidate.event_type,
            classifier=candidate.classifier,
            field=candidate.field,
            value=candidate.value,
            value_raw=candidate.value_raw,
            event_time=candidate.event_time,
            event_time_end=candidate.event_time_end,
            time_precision=candidate.precision,
            vessel=candidate.value if candidate.field == "vessel" else None,
            voyage=candidate.voyage,
            source_role=role,
            source_rank=rank_for(self._config, candidate.field, role),
            evidence=Evidence(text=quote, start=candidate.start, end=candidate.start + len(quote)),
            known_at=message.sent_at,
            recorded_at=self._clock.now(),
            provenance=Provenance(
                tier=candidate.tier,
                extractor_version=extractor_version,
                config_version=self._config.version,
            ),
            confidence=confidence,
            zone=_zone(confidence),
        )
        return draft.model_copy(update={"observation_id": f"obs-{draft.idempotency_key[:20]}"})
