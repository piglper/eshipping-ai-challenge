import io
import json
import logging
import shutil
from pathlib import Path

import pytest

from eshipping_ai.entrypoints.cli import main

NOW = "2026-10-07T08:00:00+02:00"


@pytest.fixture(autouse=True)
def no_local_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI tests never reach a local Ollama, so they behave as in the CI."""
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")


def cli(workdir: Path, *args: str) -> str:
    out = io.StringIO()
    assert main(["--workdir", str(workdir), "--now", NOW, *args], out) == 0
    return out.getvalue()


@pytest.fixture
def ran(synthetic_dir: Path, tmp_path: Path) -> tuple[Path, str]:
    erp = str(synthetic_dir / "erp.csv")
    return tmp_path, cli(tmp_path, "run", str(synthetic_dir / "mails"), "--erp", erp, "--no-llm")


def test_run_ingests_processes_and_reconciles(ran: tuple[Path, str]) -> None:
    workdir, output = ran
    assert "ingesta:" in output and "procesado:" in output and "reconciliación:" in output
    assert "URGENTE ES26900002: vessel DISCREPANCY" in output
    assert (workdir / "eshipping.db").exists()
    assert "verdicts=MATCH" in output and "zones=auto" in output


def test_running_again_adds_nothing(ran: tuple[Path, str], synthetic_dir: Path) -> None:
    workdir, _ = ran
    output = cli(
        workdir,
        "run",
        str(synthetic_dir / "mails"),
        "--erp",
        str(synthetic_dir / "erp.csv"),
        "--no-llm",
    )
    assert "mails_new=0" in output and "observations=0" in output


def test_report_in_markdown_shows_the_urgent_field_first(ran: tuple[Path, str]) -> None:
    workdir, _ = ran
    output = cli(workdir, "report", "--shipment", "ES26900002")
    rows = [line for line in output.splitlines() if line.startswith(("| P1", "| P2", "| P3"))]
    assert rows[0].startswith("| P1 | vessel | CELESTE FICTICIA | BOREAL FICTICIA | DISCREPANCY")
    assert "no_observations" not in output


def test_report_in_json_has_every_shipment_and_field(ran: tuple[Path, str]) -> None:
    workdir, _ = ran
    reports = json.loads(cli(workdir, "report", "--format", "json"))
    assert [r["shipment_id"] for r in reports] == [f"ES2690000{i}" for i in range(1, 5)]
    vessel = next(line for line in reports[0]["lines"] if line["field"] == "vessel")
    assert vessel["evidence"].startswith("Vessel") and vessel["source_role"] == "carrier"


def test_evaluate_reports_aggregated_metrics_only(
    ran: tuple[Path, str], synthetic_dir: Path
) -> None:
    workdir, _ = ran
    output = cli(workdir, "evaluate", "--gold", str(synthetic_dir / "gold.json"))
    assert "| Veredicto exacto | 28/28 = 100,0 % [87,9 % - 100,0 %] |" in output
    assert "| Precisión de la asociación automática | 13/13 = 100,0 %" in output
    assert "| booking | 4 | 4 | 4 | 100,0 %" in output
    assert "ES2690" not in output


def test_evaluate_lists_the_mismatches_only_when_asked(
    ran: tuple[Path, str], synthetic_dir: Path
) -> None:
    workdir, _ = ran
    gold = str(synthetic_dir / "gold.json")
    output = cli(workdir, "evaluate", "--gold", gold, "--verbose")
    assert "## Fallos (solo para uso local" in output
    assert "| class | ES26900003 | M3 | VSL | OTR |" in output
    report = json.loads(cli(workdir, "evaluate", "--gold", gold, "--format", "json"))
    assert report["verdicts"]["overall"]["rate"] == 1.0 and "mismatches" not in report
    target = workdir / "eval" / "report.md"
    assert "evaluación escrita" in cli(workdir, "evaluate", "--gold", gold, "--out", str(target))
    assert target.read_text(encoding="utf-8").startswith("# Evaluación frente al gold standard")


def test_urgent_notices_are_logged_without_content(
    synthetic_dir: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        cli(
            tmp_path,
            "run",
            str(synthetic_dir / "mails"),
            "--erp",
            str(synthetic_dir / "erp.csv"),
            "--no-llm",
        )
    assert [r.getMessage() for r in caplog.records] == [
        "urgent: shipment ES26900002: vessel=DISCREPANCY"
    ]


def test_a_command_is_required(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["--workdir", str(tmp_path)])


def test_without_ollama_the_run_stops_and_says_how_to_go_on(
    synthetic_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ["--workdir", str(tmp_path), "process", "--erp", str(synthetic_dir / "erp.csv")]
    assert main([*args, "--ollama-url", "http://127.0.0.1:9"], io.StringIO()) == 2
    assert "--no-llm" in capsys.readouterr().err


def test_broken_files_in_the_folder_do_not_change_the_result(
    synthetic_dir: Path, tmp_path: Path
) -> None:
    mails = tmp_path / "mails"
    shutil.copytree(synthetic_dir / "mails", mails)
    (mails / "zz_broken.msg").write_bytes(b"not a mail at all \x00\xff")
    (mails / "zz_empty.eml").write_bytes(b"")
    (mails / "zz_binary.eml").write_bytes(b"\xff\xfe\x00garbage")
    workdir = tmp_path / "work"
    output = cli(workdir, "run", str(mails), "--erp", str(synthetic_dir / "erp.csv"), "--no-llm")
    assert "failures=1" in output
    scored = cli(workdir, "evaluate", "--gold", str(synthetic_dir / "gold.json"))
    assert "| Veredicto exacto | 28/28 = 100,0 %" in scored
