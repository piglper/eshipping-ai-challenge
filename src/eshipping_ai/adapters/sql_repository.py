"""Persistence of the domain entities with SQLAlchemy (``Repository``).

It runs on SQLite in the PoC and on PostgreSQL in production: only the connection URL
changes. Every write is idempotent (RF-06): storing the same thing twice does nothing.
Observations and the input layer are insert-only; the one update allowed to an observation
is being marked as superseded, which keeps the history (RF-60, RF-61).
"""

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Connection, Engine, Table, delete, insert, select, update
from sqlalchemy.engine import RowMapping

from eshipping_ai.adapters import sql_schema as t
from eshipping_ai.domain.model import (
    Association,
    Classification,
    Document,
    ErpRecord,
    ErpSnapshot,
    FieldState,
    Mail,
    Message,
    Observation,
    ShipmentAlias,
    Verdict,
)
from eshipping_ai.domain.ports import MailOutcome, ThreadMessage, ThreadView
from eshipping_ai.domain.vocabulary import (
    AliasType,
    AssociationStatus,
    MailClass,
    ObservationStatus,
    VerdictStatus,
)

_OPEN_VERDICTS = (VerdictStatus.OPEN.value, VerdictStatus.PROPOSED.value)


def _payload(entity: BaseModel) -> dict[str, Any]:
    """JSON-ready form of an entity (times as ISO strings with their zone)."""
    return dict(entity.model_dump(mode="json"))


def _exists(connection: Connection, table: Table, **keys: object) -> bool:
    condition = [table.c[name] == value for name, value in keys.items()]
    return connection.execute(select(1).where(*condition).limit(1)).first() is not None


class SqlRepository:
    """All the stores of the domain, on one relational database."""

    def __init__(self, engine: Engine) -> None:
        """Create a repository.

        Args:
            engine: A SQLAlchemy engine; the schema must already exist (see
                :func:`create_schema` and the Alembic migrations).
        """
        self._engine = engine

    # --- input layer --------------------------------------------------------------------

    def add_mail(self, mail: Mail) -> bool:
        """Store a mail; return False if it was already stored."""
        with self._engine.begin() as connection:
            if _exists(connection, t.mail, mail_id=mail.mail_id):
                return False
            connection.execute(insert(t.mail).values(**mail.model_dump()))
            return True

    def add_message(self, message: Message, mail_id: str, depth: int) -> bool:
        """Store a message once per content and link it to the mail it appears in."""
        with self._engine.begin() as connection:
            known = connection.execute(
                select(t.message.c.message_id).where(
                    t.message.c.content_hash == message.content_hash
                )
            ).scalar()
            stored_id = known or message.message_id
            if known is None:
                connection.execute(insert(t.message).values(**message.model_dump()))
            if not _exists(connection, t.mail_message, mail_id=mail_id, message_id=stored_id):
                connection.execute(
                    insert(t.mail_message).values(
                        mail_id=mail_id, message_id=stored_id, depth=depth
                    )
                )
            return known is None

    def add_document(self, document: Document, message_id: str) -> bool:
        """Store an attachment once per content and link it to a message."""
        with self._engine.begin() as connection:
            known = connection.execute(
                select(t.document.c.document_id).where(t.document.c.sha256 == document.sha256)
            ).scalar()
            stored_id = known or document.document_id
            if known is None:
                connection.execute(insert(t.document).values(**document.model_dump()))
            if not _exists(
                connection, t.message_document, message_id=message_id, document_id=stored_id
            ):
                connection.execute(
                    insert(t.message_document).values(message_id=message_id, document_id=stored_id)
                )
            return known is None

    # --- reading the input layer ----------------------------------------------------------

    def unprocessed_mail_ids(self) -> Sequence[str]:
        """Return the mails with a message that has not been classified, oldest first."""
        classified = select(t.classification.c.message_id)
        query = (
            select(t.mail.c.mail_id)
            .join(t.mail_message, t.mail_message.c.mail_id == t.mail.c.mail_id)
            .where(t.mail_message.c.message_id.not_in(classified))
            .group_by(t.mail.c.mail_id, t.mail.c.received_at)
            .order_by(t.mail.c.received_at, t.mail.c.mail_id)
        )
        with self._engine.connect() as connection:
            return list(connection.execute(query).scalars())

    def thread(self, mail_id: str) -> ThreadView:
        """Return the messages of a mail, newest first, with their attachments and state."""
        with self._engine.connect() as connection:
            mail = (
                connection.execute(select(t.mail).where(t.mail.c.mail_id == mail_id))
                .mappings()
                .first()
            )
            if mail is None:
                msg = f"unknown mail: {mail_id}"
                raise KeyError(msg)
            rows = (
                connection.execute(
                    select(t.message, t.mail_message.c.depth)
                    .join(t.mail_message, t.mail_message.c.message_id == t.message.c.message_id)
                    .where(t.mail_message.c.mail_id == mail_id)
                    .order_by(t.mail_message.c.depth)
                )
                .mappings()
                .all()
            )
            classified = set(
                connection.execute(select(t.classification.c.message_id).distinct()).scalars()
            )
            documents = self._documents(connection, [row["message_id"] for row in rows])
        messages = tuple(
            ThreadMessage(
                message=Message.model_validate({name: row[name] for name in Message.model_fields}),
                depth=row["depth"],
                documents=documents.get(row["message_id"], ()),
                processed=row["message_id"] in classified,
            )
            for row in rows
        )
        return ThreadView(mail=Mail.model_validate(dict(mail)), messages=messages)

    @staticmethod
    def _documents(
        connection: Connection, message_ids: Sequence[str]
    ) -> dict[str, tuple[Document, ...]]:
        rows = (
            connection.execute(
                select(t.message_document.c.message_id, t.document)
                .join(t.document, t.document.c.document_id == t.message_document.c.document_id)
                .where(t.message_document.c.message_id.in_(message_ids))
                .order_by(t.document.c.document_id)
            )
            .mappings()
            .all()
        )
        found: dict[str, list[Document]] = {}
        for row in rows:
            document = Document.model_validate({name: row[name] for name in Document.model_fields})
            found.setdefault(row["message_id"], []).append(document)
        return {message_id: tuple(items) for message_id, items in found.items()}

    # --- classification and association ---------------------------------------------------

    def add_classifications(self, classifications: Iterable[Classification]) -> int:
        """Insert classifications, skipping those already stored; return how many were new."""
        added = 0
        with self._engine.begin() as connection:
            for item in classifications:
                keys = {
                    "message_id": item.message_id,
                    "mail_class": item.mail_class.value,
                    "extractor_version": item.extractor_version,
                }
                if _exists(connection, t.classification, **keys):
                    continue
                connection.execute(
                    insert(t.classification).values(
                        **keys, is_primary=item.is_primary, payload=_payload(item)
                    )
                )
                added += 1
        return added

    def add_associations(self, associations: Iterable[Association]) -> int:
        """Insert associations, skipping those already stored; return how many were new."""
        added = 0
        with self._engine.begin() as connection:
            for item in associations:
                keys = {"message_id": item.message_id, "shipment_id": item.shipment_id}
                if _exists(connection, t.association, **keys):
                    continue
                connection.execute(
                    insert(t.association).values(
                        **keys,
                        method=item.method.value,
                        status=item.status.value,
                        payload=_payload(item),
                    )
                )
                added += 1
        return added

    def associations_for(self, shipment_id: str) -> Sequence[Association]:
        """Return the messages associated with a shipment."""
        query = select(t.association.c.payload).where(t.association.c.shipment_id == shipment_id)
        with self._engine.connect() as connection:
            return [Association.model_validate(p) for p in connection.execute(query).scalars()]

    def mail_outcomes(self) -> Sequence[MailOutcome]:
        """Return what the processing made of every mail, by source and position.

        The message of a mail is the one at depth 0 of its thread, the one it wrote itself.
        """
        parent = t.mail.alias("parent")
        holders = select(parent.c.parent_mail_id).where(parent.c.parent_mail_id.is_not(None))
        own = (
            select(t.mail_message.c.mail_id, t.mail_message.c.message_id)
            .where(t.mail_message.c.depth == 0)
            .subquery()
        )
        with self._engine.connect() as connection:
            mails = connection.execute(
                select(t.mail.c.mail_id, t.mail.c.source_ref, t.mail.c.position, own.c.message_id)
                .outerjoin(own, own.c.mail_id == t.mail.c.mail_id)
                .where(t.mail.c.mail_id.not_in(holders))
                .order_by(t.mail.c.source_ref, t.mail.c.position, t.mail.c.mail_id)
            ).all()
            classes: dict[str, list[tuple[bool, str]]] = {}
            for row in connection.execute(
                select(
                    t.classification.c.message_id,
                    t.classification.c.is_primary,
                    t.classification.c.mail_class,
                )
            ):
                classes.setdefault(row.message_id, []).append((row.is_primary, row.mail_class))
            shipments: dict[str, list[tuple[str, AssociationStatus]]] = {}
            for row in connection.execute(
                select(
                    t.association.c.message_id,
                    t.association.c.shipment_id,
                    t.association.c.status,
                ).order_by(t.association.c.shipment_id)
            ):
                shipments.setdefault(row.message_id, []).append(
                    (row.shipment_id, AssociationStatus(row.status))
                )
        return [
            MailOutcome(
                mail_id=row.mail_id,
                source_ref=row.source_ref,
                position=row.position,
                classes=tuple(
                    MailClass(name)
                    for _, name in sorted(classes.get(row.message_id, []), key=lambda c: not c[0])
                ),
                shipments=tuple(shipments.get(row.message_id, [])),
            )
            for row in mails
        ]

    # --- observations -------------------------------------------------------------------

    def add_observations(self, observations: Iterable[Observation]) -> int:
        """Insert observations, skipping those already stored; return how many were new."""
        added = 0
        with self._engine.begin() as connection:
            for item in observations:
                if _exists(connection, t.observation, idempotency_key=item.idempotency_key):
                    continue
                connection.execute(
                    insert(t.observation).values(
                        observation_id=item.observation_id,
                        idempotency_key=item.idempotency_key,
                        shipment_id=item.shipment_id,
                        field=item.field,
                        known_at=item.known_at,
                        recorded_at=item.recorded_at,
                        status=item.status.value,
                        superseded_at=item.superseded_at,
                        payload=_payload(item),
                    )
                )
                added += 1
        return added

    def observations_for(
        self, shipment_id: str, as_of: datetime | None = None
    ) -> Sequence[Observation]:
        """Return the observations of a shipment, as they were known at ``as_of``."""
        query = select(t.observation.c.payload).where(t.observation.c.shipment_id == shipment_id)
        if as_of is not None:
            query = query.where(
                t.observation.c.known_at <= as_of, t.observation.c.recorded_at <= as_of
            )
        query = query.order_by(t.observation.c.known_at, t.observation.c.observation_id)
        with self._engine.connect() as connection:
            rows = connection.execute(query).scalars().all()
        found = [Observation.model_validate(row) for row in rows]
        if as_of is None:
            return found
        return [self._as_active_at(item, as_of) for item in found]

    @staticmethod
    def _as_active_at(item: Observation, as_of: datetime) -> Observation:
        """An observation superseded after ``as_of`` was still the current one then."""
        if (
            item.status is ObservationStatus.SUPERSEDED
            and item.superseded_at is not None
            and item.superseded_at > as_of
        ):
            return item.model_copy(
                update={
                    "status": ObservationStatus.ACTIVE,
                    "superseded_by": None,
                    "superseded_at": None,
                }
            )
        return item

    def mark_superseded(self, observation_id: str, superseded_by: str, at: datetime) -> None:
        """Mark an observation as superseded; nothing else about it can change."""
        with self._engine.begin() as connection:
            row = connection.execute(
                select(t.observation.c.payload).where(
                    t.observation.c.observation_id == observation_id
                )
            ).scalar()
            if row is None:
                msg = f"unknown observation: {observation_id}"
                raise KeyError(msg)
            current = Observation.model_validate(row)
            changed = current.model_copy(
                update={
                    "status": ObservationStatus.SUPERSEDED,
                    "superseded_by": superseded_by,
                    "superseded_at": at,
                }
            )
            connection.execute(
                update(t.observation)
                .where(t.observation.c.observation_id == observation_id)
                .values(
                    status=ObservationStatus.SUPERSEDED.value,
                    superseded_at=at,
                    payload=_payload(changed),
                )
            )

    # --- association index ----------------------------------------------------------------

    def find_aliases(self, alias_type: AliasType, value: str) -> Sequence[ShipmentAlias]:
        """Return the shipments known under an identifier."""
        query = select(t.shipment_alias).where(
            t.shipment_alias.c.alias_type == alias_type.value,
            t.shipment_alias.c.value == value,
        )
        with self._engine.connect() as connection:
            rows = connection.execute(query).mappings().all()
        return [self._alias(row) for row in rows]

    @staticmethod
    def _alias(row: RowMapping) -> ShipmentAlias:
        return ShipmentAlias(
            shipment_id=row["shipment_id"],
            alias_type=AliasType(row["alias_type"]),
            value=row["value"],
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
            source_observation_id=row["source_observation_id"],
        )

    def add_alias(self, alias: ShipmentAlias) -> None:
        """Register a new identifier for a shipment; registering it again does nothing."""
        with self._engine.begin() as connection:
            if _exists(
                connection,
                t.shipment_alias,
                alias_type=alias.alias_type.value,
                value=alias.value,
                shipment_id=alias.shipment_id,
            ):
                return
            connection.execute(
                insert(t.shipment_alias).values(
                    shipment_id=alias.shipment_id,
                    alias_type=alias.alias_type.value,
                    value=alias.value,
                    valid_from=alias.valid_from,
                    valid_to=alias.valid_to,
                    source_observation_id=alias.source_observation_id,
                )
            )

    # --- ERP ------------------------------------------------------------------------------

    def add_erp_snapshot(self, snapshot: ErpSnapshot, records: Iterable[ErpRecord]) -> None:
        """Store an ERP read with its rows; storing the same read again does nothing."""
        with self._engine.begin() as connection:
            if _exists(connection, t.erp_snapshot, snapshot_id=snapshot.snapshot_id):
                return
            connection.execute(insert(t.erp_snapshot).values(**snapshot.model_dump()))
            for record in records:
                connection.execute(
                    insert(t.erp_record).values(
                        snapshot_id=record.snapshot_id,
                        operation=record.operation,
                        payload=_payload(record),
                    )
                )

    # --- projections ----------------------------------------------------------------------

    def save_field_states(self, states: Iterable[FieldState]) -> None:
        """Replace the projection of the given fields."""
        with self._engine.begin() as connection:
            for state in states:
                connection.execute(
                    delete(t.field_state).where(
                        t.field_state.c.shipment_id == state.shipment_id,
                        t.field_state.c.field == state.field,
                    )
                )
                connection.execute(
                    insert(t.field_state).values(
                        shipment_id=state.shipment_id,
                        field=state.field,
                        computed_at=state.computed_at,
                        payload=_payload(state),
                    )
                )

    def save_verdicts(self, verdicts: Iterable[Verdict]) -> None:
        """Store verdicts; the previous open verdict of the same field becomes superseded."""
        with self._engine.begin() as connection:
            for item in verdicts:
                if _exists(connection, t.verdict, verdict_id=item.verdict_id):
                    continue
                self._supersede_previous(connection, item)
                connection.execute(
                    insert(t.verdict).values(
                        verdict_id=item.verdict_id,
                        shipment_id=item.shipment_id,
                        field=item.field,
                        code=item.code.value,
                        status=item.status.value,
                        computed_at=item.computed_at,
                        payload=_payload(item),
                    )
                )

    @staticmethod
    def _supersede_previous(connection: Connection, item: Verdict) -> None:
        previous = connection.execute(
            select(t.verdict.c.verdict_id, t.verdict.c.payload).where(
                t.verdict.c.shipment_id == item.shipment_id,
                t.verdict.c.field == item.field,
                t.verdict.c.status.in_(_OPEN_VERDICTS),
            )
        ).all()
        for verdict_id, payload in previous:
            changed = Verdict.model_validate(payload).model_copy(
                update={"status": VerdictStatus.SUPERSEDED}
            )
            connection.execute(
                update(t.verdict)
                .where(t.verdict.c.verdict_id == verdict_id)
                .values(status=VerdictStatus.SUPERSEDED.value, payload=_payload(changed))
            )

    def field_states_for(self, shipment_id: str) -> Sequence[FieldState]:
        """Return the current projection of a shipment."""
        query = (
            select(t.field_state.c.payload)
            .where(t.field_state.c.shipment_id == shipment_id)
            .order_by(t.field_state.c.field)
        )
        with self._engine.connect() as connection:
            return [FieldState.model_validate(p) for p in connection.execute(query).scalars()]

    def verdicts_for(self, shipment_id: str) -> Sequence[Verdict]:
        """Return the verdicts of a shipment that are not superseded."""
        query = (
            select(t.verdict.c.payload)
            .where(
                t.verdict.c.shipment_id == shipment_id,
                t.verdict.c.status != VerdictStatus.SUPERSEDED.value,
            )
            .order_by(t.verdict.c.field)
        )
        with self._engine.connect() as connection:
            return [Verdict.model_validate(p) for p in connection.execute(query).scalars()]

    def shipment_ids(self) -> Sequence[str]:
        """Return the shipments that have a projection, in order."""
        query = select(t.field_state.c.shipment_id).distinct().order_by(t.field_state.c.shipment_id)
        with self._engine.connect() as connection:
            return list(connection.execute(query).scalars())


def create_schema(engine: Engine) -> None:
    """Create every table; for tests and throw-away databases (production uses Alembic).

    Args:
        engine: Engine of an empty database.
    """
    t.metadata.create_all(engine)
