from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, select
from sqlalchemy.exc import StatementError

from eshipping_ai.adapters import sql_schema as t
from eshipping_ai.adapters.erp_csv import CsvErpGateway
from eshipping_ai.adapters.mail_files import FolderMailSource, MailFileParser
from eshipping_ai.adapters.object_store import LocalObjectStore
from eshipping_ai.adapters.pdf_text import PdfTextParser
from eshipping_ai.adapters.sql_repository import SqlRepository, create_schema
from eshipping_ai.application.ingest import IngestMail
from eshipping_ai.application.reconcile import ReconcileShipments
from eshipping_ai.domain.model import (
    Document,
    ErpRecord,
    ErpSnapshot,
    FieldState,
    Mail,
    Message,
    ShipmentAlias,
    Verdict,
)
from eshipping_ai.domain.policy import project_field
from eshipping_ai.domain.vocabulary import (
    AliasType,
    ObservationStatus,
    Priority,
    VerdictCode,
    VerdictStatus,
)
from tests.application.test_reconcile import RecordingNotifier, gold_observations
from tests.builders import CONFIG, NOW, at, erp_row, observation

ROOT = Path(__file__).parents[2]
HASH = "a" * 64


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    create_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def repo(engine: Engine) -> SqlRepository:
    return SqlRepository(engine)


def mail(mail_id: str = "mail-1", parent: str | None = None) -> Mail:
    return Mail(
        mail_id=mail_id,
        rfc_message_id="<id@x.example>",
        sha256=HASH,
        mailbox="ops",
        received_at=NOW,
        raw_object_key="sha256/aa/aa/x",
        size_bytes=10,
        parent_mail_id=parent,
    )


def message(content_hash: str = HASH, message_id: str = "msg-1") -> Message:
    return Message(
        message_id=message_id,
        content_hash=content_hash,
        sender_address="a@b.example",
        sent_at=NOW,
        subject="ETD",
        clean_body_key="sha256/bb/bb/y",
        first_seen_mail_id="mail-1",
    )


def test_input_layer_is_stored_once_and_linked(repo: SqlRepository, engine: Engine) -> None:
    assert repo.add_mail(mail()) and not repo.add_mail(mail())
    assert repo.add_mail(mail("mail-2", parent="mail-1"))
    assert repo.add_message(message(), "mail-1", 0)
    # The same content quoted in another mail: not new, but linked there too.
    assert not repo.add_message(message(message_id="msg-other-id"), "mail-2", 1)
    assert not repo.add_message(message(), "mail-2", 1)
    with engine.connect() as connection:
        assert len(connection.execute(select(t.message)).all()) == 1
        links = connection.execute(select(t.mail_message)).mappings().all()
    assert {(row["mail_id"], row["message_id"], row["depth"]) for row in links} == {
        ("mail-1", "msg-1", 0),
        ("mail-2", "msg-1", 1),
    }


def test_documents_are_stored_once_per_content(repo: SqlRepository, engine: Engine) -> None:
    repo.add_mail(mail())
    repo.add_message(message(), "mail-1", 0)
    document = Document(
        document_id="doc-1",
        sha256="b" * 64,
        filename="a.pdf",
        mime_type="application/pdf",
        object_key="k",
        text_key="k2",
        has_text_layer=True,
        pages=2,
    )
    assert repo.add_document(document, "msg-1") and not repo.add_document(document, "msg-1")
    with engine.connect() as connection:
        assert len(connection.execute(select(t.document)).all()) == 1
        assert len(connection.execute(select(t.message_document)).all()) == 1


def test_observations_round_trip_and_are_idempotent(repo: SqlRepository) -> None:
    first = observation("vessel_departure", "2026-10-08", known="2026-09-20")
    assert repo.add_observations([first]) == 1
    assert repo.add_observations([first]) == 0
    assert repo.observations_for("shp-1") == [first]
    assert repo.observations_for("another") == []


def test_what_was_known_on_a_date(repo: SqlRepository) -> None:
    old = observation("vessel_departure", "2026-10-01", known="2026-09-15")
    new = observation("vessel_departure", "2026-10-06", known="2026-09-20")
    repo.add_observations([old, new])
    as_of = at("2026-09-17")
    assert repo.observations_for("shp-1", as_of) == [old]
    state = project_field(
        "shp-1", "vessel_departure", repo.observations_for("shp-1", as_of), CONFIG, as_of
    )
    assert state.value == "2026-10-01"
    assert len(repo.observations_for("shp-1", at("2026-09-21"))) == 2


def test_the_system_may_have_learned_a_fact_later_than_the_source_said_it(
    repo: SqlRepository,
) -> None:
    late = observation(
        "vessel_departure",
        "2026-10-06",
        known="2026-09-15",
        recorded_at=at("2026-10-02"),
    )
    repo.add_observations([late])
    assert repo.observations_for("shp-1", at("2026-09-20")) == []
    assert repo.observations_for("shp-1", at("2026-10-03")) == [late]


def test_superseding_keeps_the_history(repo: SqlRepository) -> None:
    old = observation("vessel_departure", "2026-10-01", known="2026-09-15")
    new = observation("vessel_departure", "2026-10-06", known="2026-09-20")
    repo.add_observations([old, new])
    repo.mark_superseded(old.observation_id, new.observation_id, at("2026-09-20"))
    now_view = {o.observation_id: o for o in repo.observations_for("shp-1")}
    assert now_view[old.observation_id].status is ObservationStatus.SUPERSEDED
    assert now_view[old.observation_id].superseded_by == new.observation_id
    before = {
        o.observation_id: o
        for o in repo.observations_for("shp-1", at("2026-09-21", 0) - timedelta(days=1))
    }
    assert before[old.observation_id].status is ObservationStatus.ACTIVE
    after = {o.observation_id: o for o in repo.observations_for("shp-1", at("2026-09-22"))}
    assert after[old.observation_id].status is ObservationStatus.SUPERSEDED
    with pytest.raises(KeyError):
        repo.mark_superseded("obs-unknown", "x", NOW)


def test_aliases(repo: SqlRepository) -> None:
    alias = ShipmentAlias(
        shipment_id="shp-1", alias_type=AliasType.BOOKING, value="990000202", valid_from=NOW
    )
    repo.add_alias(alias)
    repo.add_alias(alias)
    assert repo.find_aliases(AliasType.BOOKING, "990000202") == [alias]
    assert repo.find_aliases(AliasType.CONTAINER, "990000202") == []


def test_an_erp_read_is_stored_once(repo: SqlRepository, engine: Engine) -> None:
    snapshot = ErpSnapshot(
        snapshot_id="erp-1", read_at=NOW, source="erp.csv", sha256=HASH, row_count=1
    )
    records = [erp_row(booking="990000101")]
    repo.add_erp_snapshot(snapshot, records)
    repo.add_erp_snapshot(snapshot, records)
    with engine.connect() as connection:
        assert len(connection.execute(select(t.erp_snapshot)).all()) == 1
        stored = connection.execute(select(t.erp_record.c.payload)).scalars().all()
    assert ErpRecord.model_validate(stored[0]).normalized["booking"] == "990000101"


def verdict(
    verdict_id: str, code: VerdictCode = VerdictCode.DISCREPANCY, **kwargs: object
) -> Verdict:
    return Verdict(
        verdict_id=verdict_id,
        shipment_id="shp-1",
        field="vessel_departure",
        code=code,
        mail_value="2026-10-06",
        erp_value="2026-10-01",
        erp_record=None,
        rule="unattributable",
        priority=Priority.P2,
        computed_at=NOW,
        config_version="c1",
        **kwargs,  # type: ignore[arg-type]
    )


def test_a_new_verdict_supersedes_the_open_one(repo: SqlRepository) -> None:
    repo.save_verdicts([verdict("vrd-1")])
    repo.save_verdicts([verdict("vrd-1")])
    assert [v.verdict_id for v in repo.verdicts_for("shp-1")] == ["vrd-1"]
    repo.save_verdicts([verdict("vrd-2", VerdictCode.MATCH)])
    current = repo.verdicts_for("shp-1")
    assert [(v.verdict_id, v.code) for v in current] == [("vrd-2", VerdictCode.MATCH)]
    assert current[0].status is VerdictStatus.OPEN


def test_field_states_are_replaced(repo: SqlRepository) -> None:
    def state(value: str) -> FieldState:
        return FieldState(
            shipment_id="shp-1",
            field="vessel",
            value=value,
            winning_observation_id="obs-1",
            rule="freshest_reliable",
            computed_at=NOW,
            config_version="c1",
        )

    repo.save_field_states([state("A")])
    repo.save_field_states([state("B")])
    assert [s.value for s in repo.field_states_for("shp-1")] == ["B"]
    assert repo.field_states_for("other") == []


def test_naive_times_are_rejected(repo: SqlRepository) -> None:
    naive = Mail.model_construct(**{**mail().model_dump(), "received_at": datetime(2026, 1, 1)})  # noqa: DTZ001
    with pytest.raises(StatementError, match="time zone"):
        repo.add_mail(naive)


def test_ingest_runs_on_the_database_and_is_idempotent(
    synthetic_dir: Path, tmp_path: Path, repo: SqlRepository, clock
) -> None:  # type: ignore[no-untyped-def]
    def run():  # type: ignore[no-untyped-def]
        return IngestMail(
            FolderMailSource(synthetic_dir / "mails", "ops"),
            MailFileParser(),
            PdfTextParser(),
            repo,
            LocalObjectStore(tmp_path / "objects"),
            clock,
            ZoneInfo("Europe/Madrid"),
        ).run()

    first = run()
    assert (first.mails_new, first.messages_new, first.messages_known) == (18, 14, 1)
    second = run()
    assert (second.mails_new, second.messages_new) == (0, 0)


def test_reconciliation_runs_on_the_database(
    synthetic_dir: Path, repo: SqlRepository, clock
) -> None:  # type: ignore[no-untyped-def]
    observations, shipments, gold = gold_observations(synthetic_dir)
    assert repo.add_observations(observations) == len(observations)

    def run():  # type: ignore[no-untyped-def]
        return ReconcileShipments(
            CsvErpGateway(synthetic_dir / "erp.csv", NOW),
            repo,
            repo,
            repo,
            RecordingNotifier(),
            clock,
            CONFIG,
        ).run(shipments)

    report = run()
    run()  # idempotent: the same verdicts are not stored twice
    stored = {op: {v.field: v for v in repo.verdicts_for(op)} for op in shipments}
    assert sum(len(v) for v in stored.values()) == sum(report.verdicts.values())
    assert stored["ES26900003"]["vessel_departure"].code is VerdictCode.ERP_ERROR
    assert len(repo.field_states_for("ES26900001")) == len(CONFIG.fields)
    assert gold  # the verdicts themselves are checked against the gold in test_reconcile


def test_migrations_produce_the_schema_of_the_application(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    expected = create_engine(f"sqlite:///{tmp_path / 'created.db'}")
    create_schema(expected)

    def shape(engine: Engine) -> dict[str, list[tuple[str, str, bool]]]:
        inspector = inspect(engine)
        return {
            name: sorted(
                (c["name"], str(c["type"]).split("(")[0], bool(c["nullable"]))
                for c in inspector.get_columns(name)
            )
            for name in inspector.get_table_names()
            if name != "alembic_version"
        }

    migrated = create_engine(url)
    try:
        assert shape(migrated) == shape(expected)
        command.downgrade(config, "base")
        remaining = [n for n in inspect(migrated).get_table_names() if n != "alembic_version"]
        assert remaining == []
    finally:
        migrated.dispose()
        expected.dispose()
