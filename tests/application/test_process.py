"""The pipeline on the synthetic set: ingest, seed the index, process and reconcile."""

import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine

from eshipping_ai.adapters.config_yaml import load_sender_directory
from eshipping_ai.adapters.erp_csv import CsvErpGateway
from eshipping_ai.adapters.mail_files import FolderMailSource, MailFileParser
from eshipping_ai.adapters.object_store import LocalObjectStore
from eshipping_ai.adapters.pdf_text import PdfTextParser
from eshipping_ai.adapters.sql_repository import SqlRepository, create_schema
from eshipping_ai.application.ingest import IngestMail
from eshipping_ai.application.process import ProcessMessages, ProcessReport
from eshipping_ai.application.reconcile import ReconcileReport, ReconcileShipments
from eshipping_ai.application.seed import seed_aliases
from eshipping_ai.domain.vocabulary import AliasType, AssociationStatus, Zone
from tests.builders import CONFIG, NOW
from tests.conftest import FixedClock

ROOT = Path(__file__).parents[2]
MADRID = ZoneInfo("Europe/Madrid")


class SilentNotifier:
    def notify(self, shipment_id: str, verdicts: object) -> None:
        return None


class Pipeline:
    def __init__(self, synthetic_dir: Path, tmp_path: Path) -> None:
        self.engine = engine = create_engine(f"sqlite:///{tmp_path / 'pipeline.db'}")
        create_schema(engine)
        self.repo = SqlRepository(engine)
        self.objects = LocalObjectStore(tmp_path / "objects")
        self.clock = FixedClock()
        self.erp = CsvErpGateway(synthetic_dir / "erp.csv", NOW)
        IngestMail(
            FolderMailSource(synthetic_dir / "mails", "operaciones"),
            MailFileParser(),
            PdfTextParser(),
            self.repo,
            self.objects,
            self.clock,
            MADRID,
        ).run()
        snapshot, records = self.erp.read()
        self.shipments = seed_aliases(records, self.repo, snapshot.read_at)
        self.senders = load_sender_directory(ROOT / "config" / "senders.yaml")

    def process(self) -> ProcessReport:
        return ProcessMessages(
            self.repo,
            self.objects,
            self.repo,
            self.repo,
            self.repo,
            self.clock,
            CONFIG,
            self.senders,
            MADRID,
        ).run()

    def reconcile(self) -> ReconcileReport:
        return ReconcileShipments(
            self.erp, self.repo, self.repo, self.repo, SilentNotifier(), self.clock, CONFIG
        ).run(self.shipments)


@pytest.fixture
def pipeline(synthetic_dir: Path, tmp_path: Path) -> Iterator[Pipeline]:
    pipeline = Pipeline(synthetic_dir, tmp_path)
    yield pipeline
    pipeline.engine.dispose()


GOLD_TO_FIELDS = {
    "booking": ["booking"],
    "vessel": ["vessel"],
    "vessel_departure": ["vessel_departure"],
    "vessel_arrival_pod": ["vessel_arrival_pod"],
    "stuffing": ["stuffing"],
    "customs_release": ["customs_release"],
    "cutoff": ["cutoff_document", "cutoff_vgm", "cutoff_full"],
    "equipment": ["equipment_count"],
}


def test_the_rules_reproduce_the_verdicts_of_the_gold(
    pipeline: Pipeline, synthetic_dir: Path
) -> None:
    pipeline.process()
    pipeline.reconcile()
    gold = json.loads((synthetic_dir / "gold.json").read_text(encoding="utf-8"))["expedientes"]
    for operation, fields in gold.items():
        got = {v.field: v.code.value for v in pipeline.repo.verdicts_for(operation)}
        for name, expected in fields.items():
            codes = {got[f] for f in GOLD_TO_FIELDS[name] if f in got}
            assert codes == {expected["verdict"]}, (operation, name, codes)


def test_the_run_counts_what_it_found(pipeline: Pipeline) -> None:
    report = pipeline.process()
    assert report.threads == 14 and report.messages == 14
    assert report.noise == 1 and report.unassociated == 0 and report.in_review == 0
    assert report.zones[Zone.AUTO.value] > 0
    assert sum(report.classes.values()) == report.messages


def test_processing_twice_adds_nothing(pipeline: Pipeline) -> None:
    first = pipeline.process()
    second = pipeline.process()
    assert first.observations > 0
    assert second.messages == 0 and second.observations == 0


def test_a_rollover_teaches_the_new_booking_and_the_containers(pipeline: Pipeline) -> None:
    pipeline.process()
    new = pipeline.repo.find_aliases(AliasType.BOOKING, "990000203")
    assert [alias.shipment_id for alias in new] == ["ES26900002"]
    container = pipeline.repo.find_aliases(AliasType.CONTAINER, "SYNU1000019")
    assert [alias.shipment_id for alias in container] == ["ES26900001"]


def test_the_replaced_booking_is_not_a_value_of_the_shipment(pipeline: Pipeline) -> None:
    pipeline.process()
    bookings = {
        (o.value, o.message_id)
        for o in pipeline.repo.observations_for("ES26900002")
        if o.field == "booking"
    }
    assert {value for value, _ in bookings} == {"990000202", "990000203"}
    forward = next(
        m for m in pipeline.repo.associations_for("ES26900002") if m.method.value == "booking"
    )
    assert forward.status is AssociationStatus.AUTO


def test_noise_is_classified_but_neither_associated_nor_extracted(pipeline: Pipeline) -> None:
    pipeline.process()
    associated = {
        a.message_id
        for operation in pipeline.shipments
        for a in pipeline.repo.associations_for(operation)
    }
    observed = {
        o.message_id
        for operation in pipeline.shipments
        for o in pipeline.repo.observations_for(operation)
    }
    assert len(associated) == 13  # the noise mail has no shipment
    assert observed <= associated
    assert (
        Counter(
            o.source_role.value
            for operation in pipeline.shipments
            for o in pipeline.repo.observations_for(operation)
        )["customer"]
        > 0
    )
