"""Confidentiality audit (F5.4): look for real values of ``data/`` outside of it.

Run locally only: ``python -m eshipping_ai.entrypoints.audit [--data DIR] [--github]``.
The real values are read from the ERP export, the mails and the gold standard of ``data/``
and searched in the tracked files, in every commit of the history and, with ``--github``,
in the titles and bodies of the issues and pull requests. The report says the category,
the file and line or the commit of each hit, **never the value**, so that it can be shared.
The exit code is 1 if there is any hit.
"""

import argparse
import csv
import io
import json
import re
import subprocess
import sys
import unicodedata
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from eshipping_ai.adapters.mail_files import MailFileParser
from eshipping_ai.domain.ports import ParsedMail

ERP_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "expediente": ("Operación",),
    "booking": ("Booking",),
    "bl": ("Master", "SWB / OBL Evento"),
    "buque": ("Buque",),
    "cliente": ("Cliente Op.", "Cliente Comercial", "Shipper", "Consignee", "Cli. Com."),
    "proveedor": (
        "Línea Transporte",
        "Transportistas",
        "Agente Aduana",
        "Proveedor Expediente",
        "Corresponsal",
        "Corresponsal II",
    ),
    "persona": (
        "Promotor",
        "Promotor Cap.",
        "Usuario Gestión",
        "Usuario Cierre",
        "Customer Service",
        "Operativo Pricing",
        "Usuario Gest.",
    ),
    "referencia": ("Ref. Cliente", "Oferta", "Núm. Contrato", "Contrato Slot"),
    "lugar": ("Lugar Recogida",),
}
# Words that are vocabulary, not data: legal forms, document states, public names.
GENERIC = frozenset(
    {
        "completado",
        "pendiente",
        "s.l.",
        "s.a.",
        "s.l.u.",
        "s.a.u.",
        "transportes",
        "transporte",
        "aduanas",
        "valencia",
        "barcelona",
        "madrid",
        "maersk",
        "hapag-lloyd",
        "evergreen",
    }
)
PUBLIC_DOMAINS = (
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "maersk.com",
    "msc.com",
    "cma-cgm.com",
    "hlag.com",
)
_MIN_LENGTH = 5
_CONTAINER_RE = re.compile(r"\b[A-Z]{4}\s?\d{7}\b")
_ADDRESS_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_GOLD_ID_RE = re.compile(r"\b(?:ES\d{8}|[A-Z]{4}\d{7})\b")


@dataclass(frozen=True, slots=True)
class Hit:
    """Where a real value was found; the value itself is not kept."""

    category: str
    location: str


def _plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def is_specific(value: str) -> bool:
    """Tell whether a value identifies something, or is a generic word worth no search."""
    value = value.strip()
    return len(value) >= _MIN_LENGTH and _plain(value) not in GENERIC


def _add(secrets: dict[str, set[str]], category: str, value: str) -> None:
    if is_specific(value):
        secrets.setdefault(category, set()).add(value.strip())


def _walk(mail: ParsedMail) -> Iterator[ParsedMail]:
    yield mail
    for inner in mail.embedded:
        yield from _walk(inner)


def collect_secrets(data_dir: Path) -> dict[str, set[str]]:
    """Read the real values to look for from the files of ``data/``.

    Args:
        data_dir: The folder with the real data: an ERP export in CSV, the mails and,
            optionally, the gold standard in ``gold/``.

    Returns:
        Category to real values.
    """
    secrets: dict[str, set[str]] = {}
    for path in sorted(data_dir.glob("*.csv")):
        _from_erp(path, secrets)
    parser = MailFileParser()
    for path in sorted(data_dir.rglob("*")):
        if path.suffix.lower() in {".msg", ".eml"}:
            for mail in _walk(parser.parse(path.read_bytes(), path.name)):
                _from_mail(mail, secrets)
    for path in sorted(data_dir.glob("gold/*.json")):
        for identifier in _GOLD_ID_RE.findall(json.dumps(json.loads(path.read_text()))):
            _add(secrets, "gold", identifier)
    return secrets


def _from_erp(path: Path, secrets: dict[str, set[str]]) -> None:
    text = path.read_bytes().decode("utf-8-sig", errors="replace")
    for row in csv.DictReader(io.StringIO(text), delimiter=";"):
        for category, columns in ERP_COLUMNS.items():
            for column in columns:
                for part in re.split(r"[;,/]| - ", row.get(column) or ""):
                    _add(secrets, category, part)
        for cell in row.values():
            for container in _CONTAINER_RE.findall(cell or ""):
                _add(secrets, "contenedor", container.replace(" ", ""))


def _from_mail(mail: ParsedMail, secrets: dict[str, set[str]]) -> None:
    for address in _ADDRESS_RE.findall(" ".join((mail.sender, *mail.recipients))):
        _add(secrets, "correo", address.lower())
        domain = address.split("@", 1)[1].lower()
        if not domain.endswith(PUBLIC_DOMAINS):
            _add(secrets, "dominio", domain)
    for container in _CONTAINER_RE.findall(f"{mail.subject}\n{mail.text_body}"):
        _add(secrets, "contenedor", container.replace(" ", ""))


def _patterns(secrets: Mapping[str, Iterable[str]]) -> list[tuple[str, re.Pattern[str]]]:
    return [
        (category, re.compile(rf"(?<!\w){re.escape(value)}(?!\w)", re.IGNORECASE))
        for category, values in sorted(secrets.items())
        for value in sorted(values)
    ]


def scan(texts: Mapping[str, str], secrets: Mapping[str, Iterable[str]]) -> list[Hit]:
    """Find the real values in some texts.

    Args:
        texts: Name of each text (a file, a commit) to its content.
        secrets: Category to real values.

    Returns:
        One hit per value and line where it appears.
    """
    patterns = _patterns(secrets)
    hits: list[Hit] = []
    for name, text in texts.items():
        for number, line in enumerate(text.splitlines(), start=1):
            hits.extend(
                Hit(category, f"{name}:{number}")
                for category, pattern in patterns
                if pattern.search(line)
            )
    return hits


def _git(*args: str) -> str:
    return subprocess.run(  # noqa: S603 - fixed git commands
        ["git", *args],  # noqa: S607 - git from the PATH
        capture_output=True,
        text=True,
        errors="replace",
        check=True,
    ).stdout


def _tracked_files(root: Path) -> dict[str, str]:
    files = {}
    for name in _git("-C", str(root), "ls-files").splitlines():
        path = root / name
        if path.is_file():
            files[name] = path.read_text(encoding="utf-8", errors="ignore")
    return files


def _history(root: Path) -> dict[str, str]:
    """Each commit of every branch: its message and the lines it adds."""
    commits: dict[str, str] = {}
    for commit in _git("-C", str(root), "rev-list", "--all").split():
        patch = _git("-C", str(root), "show", "--format=%B", "--unified=0", commit)
        added = "\n".join(
            line for line in patch.splitlines() if not line.startswith(("---", "+++", "-", "@@"))
        )
        commits[f"commit {commit[:9]}"] = added
    return commits


def _github() -> dict[str, str]:
    texts = {}
    for kind in ("issue", "pr"):
        listing = subprocess.run(  # noqa: S603 - fixed gh command
            ["gh", kind, "list", "--state", "all", "--limit", "500", "--json", "number,title,body"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for item in json.loads(listing):
            texts[f"{kind} #{item['number']}"] = f"{item['title']}\n{item['body']}"
    return texts


def main(argv: list[str] | None = None) -> int:
    """Run the audit and print where real values appear, without the values."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--repo", type=Path, default=Path())
    parser.add_argument("--github", action="store_true", help="also issues and pull requests")
    args = parser.parse_args(argv)
    secrets = collect_secrets(args.data)
    counts = ", ".join(f"{category} {len(values)}" for category, values in sorted(secrets.items()))
    print(f"valores reales buscados: {counts}")
    sources = {"ficheros versionados": _tracked_files(args.repo), "historial": _history(args.repo)}
    if args.github:
        sources["GitHub"] = _github()
    total = 0
    for source, texts in sources.items():
        hits = scan(texts, secrets)
        total += len(hits)
        print(f"{source}: {len(texts)} textos, {len(hits)} coincidencias")
        for hit in hits:
            print(f"  {hit.category}: {hit.location}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
