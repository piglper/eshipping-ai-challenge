"""Command line of the PoC: ``eshipping ingest | process | reconcile | run | report | evaluate``.

This is the composition root: it builds the adapters and hands them to the use cases. Every
run works on one directory (``--workdir``, ``data/output`` by default, ignored by git) that
holds the SQLite database and the object store; ``ESHIPPING_DATABASE_URL`` points it to
another database. Output is counts, verdicts and quotes; logs never carry mail content.
"""

import argparse
import json
import logging
import os
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path
from typing import TextIO
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine

from eshipping_ai.adapters.clock import FixedClock, SystemClock
from eshipping_ai.adapters.config_yaml import load_reconciliation_config, load_sender_directory
from eshipping_ai.adapters.erp_csv import CsvErpGateway
from eshipping_ai.adapters.log_notifier import LogNotifier
from eshipping_ai.adapters.mail_files import FolderMailSource, MailFileParser
from eshipping_ai.adapters.object_store import LocalObjectStore
from eshipping_ai.adapters.ollama_client import DEFAULT_URL as OLLAMA_URL
from eshipping_ai.adapters.ollama_client import OllamaClient
from eshipping_ai.adapters.pdf_text import PdfTextParser
from eshipping_ai.adapters.sql_repository import SqlRepository, create_schema
from eshipping_ai.application.evaluate import EvaluateRun
from eshipping_ai.application.ingest import IngestMail
from eshipping_ai.application.process import ProcessMessages
from eshipping_ai.application.reconcile import ReconcileShipments
from eshipping_ai.application.report import ShipmentReport, shipment_report
from eshipping_ai.application.seed import seed_aliases
from eshipping_ai.domain.ports import Clock, LLMClient
from eshipping_ai.entrypoints.evaluation_report import render_markdown, report_to_json

DEFAULT_WORKDIR = Path("data/output")
DEFAULT_CONFIG = Path("config")
DEFAULT_TZ = "Europe/Madrid"
DEFAULT_MODEL = "llama3.2:3b"  # provisional: the model of the PoC is chosen in F4 (D9, #43)


class Context:
    """The adapters of one run, built from the command-line options."""

    def __init__(self, args: argparse.Namespace) -> None:
        """Open the database (creating missing tables) and the object store."""
        workdir: Path = args.workdir
        workdir.mkdir(parents=True, exist_ok=True)
        url = os.environ.get("ESHIPPING_DATABASE_URL") or f"sqlite:///{workdir / 'eshipping.db'}"
        self.engine = create_engine(url)
        create_schema(self.engine)  # throw-away databases; production uses `make migrate`
        self.repo = SqlRepository(self.engine)
        self.objects = LocalObjectStore(workdir / "objects")
        self.now: datetime | None = args.now
        self.clock: Clock = FixedClock(args.now) if args.now else SystemClock()
        self.tz = ZoneInfo(args.tz)
        self.config_dir: Path = args.config

    def erp(self, path: Path) -> CsvErpGateway:
        """The ERP export, read as of ``--now`` when given."""
        return CsvErpGateway(path, self.now)

    def close(self) -> None:
        """Release the database."""
        self.engine.dispose()


def _summary(report: object) -> str:
    """One line with the counts of a run report (dataclass), counters included."""
    parts = []
    for item in fields(report):  # type: ignore[arg-type]
        value = getattr(report, item.name)
        if isinstance(value, Counter):
            value = ", ".join(f"{key} {count}" for key, count in value.most_common()) or "-"
        parts.append(f"{item.name}={value}")
    return " ".join(parts)


def _ingest(ctx: Context, args: argparse.Namespace, out: TextIO) -> None:
    report = IngestMail(
        FolderMailSource(args.mails, args.mailbox),
        MailFileParser(),
        PdfTextParser(),
        ctx.repo,
        ctx.objects,
        ctx.clock,
        ctx.tz,
    ).run()
    print(f"ingesta: {_summary(report)}", file=out)


class UsageError(Exception):
    """A run that cannot start as asked; the message says what to change."""


def _llm(args: argparse.Namespace) -> LLMClient | None:
    """The model of the LLM tier, or None with ``--no-llm``."""
    if args.no_llm:
        return None
    client = OllamaClient(args.model, args.ollama_url)
    if not client.available():
        msg = (
            f"Ollama no responde en {args.ollama_url} o no tiene el modelo {args.model}; "
            "arráncalo (`ollama serve`, `ollama pull <modelo>`) o usa --no-llm"
        )
        raise UsageError(msg)
    return client


def _process(ctx: Context, args: argparse.Namespace, out: TextIO) -> None:
    llm = _llm(args)
    snapshot, records = ctx.erp(args.erp).read()
    seed_aliases(records, ctx.repo, snapshot.read_at)
    senders = load_sender_directory(args.senders or ctx.config_dir / "senders.yaml")
    report = ProcessMessages(
        ctx.repo,
        ctx.objects,
        ctx.repo,
        ctx.repo,
        ctx.repo,
        ctx.clock,
        load_reconciliation_config(ctx.config_dir / "reconciliation.yaml"),
        senders,
        ctx.tz,
        llm,
        senders.parties_of(records),
    ).run()
    print(f"procesado: {_summary(report)}", file=out)


def _reconcile(ctx: Context, args: argparse.Namespace, out: TextIO) -> None:
    erp = ctx.erp(args.erp)
    snapshot, records = erp.read()
    shipments = seed_aliases(records, ctx.repo, snapshot.read_at)
    notifier = LogNotifier()
    report = ReconcileShipments(
        erp,
        ctx.repo,
        ctx.repo,
        ctx.repo,
        notifier,
        ctx.clock,
        load_reconciliation_config(ctx.config_dir / "reconciliation.yaml"),
    ).run(shipments)
    print(f"reconciliación: {_summary(report)}", file=out)
    for shipment_id, verdicts in notifier.notices:
        fields = ", ".join(f"{v.field} {v.code.value}" for v in verdicts)
        print(f"URGENTE {shipment_id}: {fields}", file=out)


def _run(ctx: Context, args: argparse.Namespace, out: TextIO) -> None:
    _ingest(ctx, args, out)
    _process(ctx, args, out)
    _reconcile(ctx, args, out)


def _render_markdown(report: ShipmentReport, out: TextIO) -> None:
    print(f"## Expediente {report.shipment_id}\n", file=out)
    print("| Prioridad | Campo | Correos | ERP | Veredicto | Regla | Evidencia |", file=out)
    print("|---|---|---|---|---|---|---|", file=out)
    for line in report.lines:
        if line.mail_value is None and line.verdict is None:
            continue  # nothing said and nothing to compare: the JSON keeps it
        evidence = " ".join((line.evidence or "").split()).replace("|", "\\|")
        conflict = " (conflicto)" if line.in_conflict else ""
        print(
            f"| {line.priority or ''} | {line.field} | {line.mail_value or ''}{conflict} "
            f"| {line.erp_value or ''} | {line.verdict or ''} | {line.rule} "
            f"| {evidence} |",
            file=out,
        )
    print(file=out)


def _report(ctx: Context, args: argparse.Namespace, out: TextIO) -> None:
    ids = [args.shipment] if args.shipment else ctx.repo.shipment_ids()
    reports = [shipment_report(shipment_id, ctx.repo, ctx.repo) for shipment_id in ids]
    if args.format == "json":
        json.dump([asdict(r) for r in reports], out, ensure_ascii=False, indent=2, default=str)
        print(file=out)
        return
    for report in reports:
        _render_markdown(report, out)


def _evaluate(ctx: Context, args: argparse.Namespace, out: TextIO) -> None:
    gold = json.loads(args.gold.read_text(encoding="utf-8"))
    report = EvaluateRun(ctx.repo, ctx.repo, ctx.repo).run(gold)
    if args.format == "json":
        text = json.dumps(report_to_json(report, verbose=args.verbose), indent=2) + "\n"
    else:
        text = render_markdown(report, verbose=args.verbose)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"evaluación escrita en {args.out}", file=out)
    else:
        out.write(text)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eshipping", description="Extracción de eventos de correos y cruce con el ERP."
    )
    parser.add_argument(
        "--workdir", type=Path, default=DEFAULT_WORKDIR, help="base de datos y objetos"
    )
    parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG, help="carpeta de configuración"
    )
    parser.add_argument("--tz", default=DEFAULT_TZ, help="zona horaria de buzón y eventos")
    parser.add_argument(
        "--now", type=datetime.fromisoformat, help="momento fijo (ISO con zona) para repetir un día"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def with_mails(command: argparse.ArgumentParser) -> None:
        command.add_argument("mails", type=Path, help="carpeta de .msg o .eml")
        command.add_argument("--mailbox", default="operaciones", help="nombre del buzón")

    def with_erp(command: argparse.ArgumentParser) -> None:
        command.add_argument("--erp", type=Path, required=True, help="exportación CSV del ERP")

    def with_senders(command: argparse.ArgumentParser) -> None:
        command.add_argument("--senders", type=Path, help="directorio de remitentes (YAML)")
        command.add_argument(
            "--no-llm", action="store_true", help="la cascada se detiene en las reglas"
        )
        command.add_argument("--model", default=DEFAULT_MODEL, help="modelo de Ollama")
        command.add_argument(
            "--ollama-url",
            default=os.environ.get("OLLAMA_HOST", OLLAMA_URL),
            help="dirección del servidor de Ollama",
        )

    ingest = commands.add_parser("ingest", help="ingesta, limpieza y división de los hilos")
    with_mails(ingest)
    ingest.set_defaults(handler=_ingest)
    process = commands.add_parser("process", help="clasificación, asociación y extracción")
    with_erp(process)
    with_senders(process)
    process.set_defaults(handler=_process)
    reconcile = commands.add_parser("reconcile", help="valor vigente y veredictos frente al ERP")
    with_erp(reconcile)
    reconcile.set_defaults(handler=_reconcile)
    run = commands.add_parser("run", help="ingest, process y reconcile en orden")
    with_mails(run)
    with_erp(run)
    with_senders(run)
    run.set_defaults(handler=_run)
    report = commands.add_parser("report", help="expedientes con valores, veredictos y citas")
    report.add_argument("--shipment", help="solo este expediente")
    report.add_argument("--format", choices=("md", "json"), default="md")
    report.set_defaults(handler=_report)
    evaluate = commands.add_parser("evaluate", help="métricas frente a un gold standard")
    evaluate.add_argument("--gold", type=Path, required=True, help="gold standard (JSON)")
    evaluate.add_argument("--format", choices=("md", "json"), default="md")
    evaluate.add_argument("--out", type=Path, help="fichero donde escribir el informe")
    evaluate.add_argument(
        "--verbose", action="store_true", help="añade los fallos, que nombran expedientes"
    )
    evaluate.set_defaults(handler=_evaluate)
    return parser


def main(argv: Sequence[str] | None = None, out: TextIO | None = None) -> int:
    """Run one command.

    Args:
        argv: Arguments; those of the process if omitted.
        out: Where the results are written; standard output if omitted.

    Returns:
        The exit code.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = _parser().parse_args(argv)
    ctx = Context(args)
    try:
        args.handler(ctx, args, out or sys.stdout)
    except UsageError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    finally:
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
