"""Generate the synthetic mails, ERP export and gold standard from a specification.

The output mirrors the shape of the real sample without any of its content: one container
mail per shipment with the thread mails embedded as ``message/rfc822`` parts, an ERP export
in CSV with a BOM, ``;`` as separator and ``dd/mm/yyyy`` dates, and a gold standard with
the same structure as the real one. The output is deterministic: the same specification
always produces the same bytes.
"""

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import timedelta
from email.message import EmailMessage
from email.utils import format_datetime, formataddr
from pathlib import Path

from eshipping_ai.synthetic.spec import Party, Spec, SpecMail, SpecShipment

NOISE_KEY = "_noise"
"""Key of the gold ``mails`` section for mails that belong to no shipment."""


@dataclass(frozen=True, slots=True)
class BuildResult:
    """Paths of the generated files."""

    mail_files: tuple[Path, ...]
    erp_file: Path
    gold_file: Path


def _address(party: Party) -> str:
    return formataddr((party.name, party.address))


def _quoted_block(mail: SpecMail, parties: dict[str, Party]) -> str:
    """Render a previous mail as Outlook quotes it in a reply or a forward."""
    sender, recipient = parties[mail.sender], parties[mail.to]
    header = (
        f"De: {_address(sender)}\n"
        f"Enviado: {mail.date:%d/%m/%Y %H:%M}\n"
        f"Para: {_address(recipient)}\n"
        f"Asunto: {mail.subject}\n"
    )
    return f"\n\n{header}\n{mail.body}{_signature(sender)}"


def _signature(party: Party) -> str:
    return f"\n{party.signature}" if party.signature else ""


def _render_mail(
    mail: SpecMail, parties: dict[str, Party], message_id: str, quoted: SpecMail | None
) -> EmailMessage:
    sender = parties[mail.sender]
    body = mail.body + _signature(sender)
    if quoted is not None:
        body += _quoted_block(quoted, parties)
    message = EmailMessage()
    message["From"] = _address(sender)
    message["To"] = _address(parties[mail.to])
    message["Date"] = format_datetime(mail.date)
    message["Subject"] = mail.subject
    message["Message-ID"] = message_id
    message.set_content(body, cte="quoted-printable")
    return message


def _container_mail(shipment: SpecShipment, spec: Spec) -> EmailMessage:
    """One mail per shipment with every thread mail embedded, like the real sample."""
    by_id = {mail.id: mail for mail in shipment.mails}
    archive = Party(name="Archivo de expedientes", address=spec.mailbox)
    container = EmailMessage()
    container["From"] = _address(archive)
    container["To"] = _address(archive)
    container["Date"] = format_datetime(max(m.date for m in shipment.mails) + timedelta(hours=1))
    container["Subject"] = f"Expediente {shipment.operation}"
    container["Message-ID"] = f"<{shipment.operation}@synthetic.example>"
    container.set_content("--\nArchivo de expedientes\n")
    for mail in shipment.mails:
        quoted = by_id[mail.quote] if mail.quote else None
        message_id = f"<{shipment.operation}.{mail.id}@synthetic.example>"
        embedded = _render_mail(mail, spec.parties, message_id, quoted)
        container.add_attachment(embedded, filename=f"{mail.id}.eml")
    _fix_boundaries(container, shipment.operation)
    return container


def _fix_boundaries(message: EmailMessage, seed: str) -> None:
    """Replace the random MIME boundaries with stable ones so the output is reproducible."""
    for position, part in enumerate(message.walk()):
        if part.is_multipart():
            digest = hashlib.sha256(f"{seed}/{position}".encode()).hexdigest()[:24]
            part.set_boundary(f"=_synthetic_{digest}")


def _write_erp(spec: Spec, path: Path) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(spec.shipments[0].erp.keys())
    for shipment in spec.shipments:
        writer.writerow(shipment.erp.values())
    path.write_bytes(buffer.getvalue().encode("utf-8-sig"))


def _gold(spec: Spec) -> dict[str, object]:
    mails: dict[str, list[list[str]]] = {
        shipment.operation: [list(mail.classes) for mail in shipment.mails]
        for shipment in spec.shipments
    }
    if spec.noise:
        mails[NOISE_KEY] = [list(mail.classes) for mail in spec.noise]
    return {
        "meta": {
            "version": str(spec.version),
            "date": spec.erp.read_at.date().isoformat(),
            "author": "synthetic",
            "review": "not applicable (synthetic)",
            "unit_mail": "Correo incrustado M<n> dentro del .eml contenedor del expediente",
            "date_tolerance_days": {
                "vessel_departure": 0,
                "vessel_arrival_pod": 0,
                "stuffing": 0,
                "customs_release": 0,
            },
        },
        "mails": mails,
        "expedientes": {
            shipment.operation: {
                field: expected.model_dump(mode="json", exclude_none=True)
                | {"value": expected.value, "source": expected.source}
                for field, expected in shipment.gold.items()
            }
            for shipment in spec.shipments
        },
    }


def build(spec: Spec, out_dir: Path) -> BuildResult:
    """Write the synthetic mails, ERP export and gold standard.

    Args:
        spec: Validated specification.
        out_dir: Destination folder; created if needed.

    Returns:
        The paths of the generated files.
    """
    mail_dir = out_dir / "mails"
    mail_dir.mkdir(parents=True, exist_ok=True)
    mail_files: list[Path] = []
    for shipment in spec.shipments:
        path = mail_dir / f"{shipment.operation}.eml"
        path.write_bytes(_container_mail(shipment, spec).as_bytes())
        mail_files.append(path)
    for mail in spec.noise:
        path = mail_dir / f"{mail.id}.eml"
        message = _render_mail(mail, spec.parties, f"<{mail.id}@synthetic.example>", None)
        path.write_bytes(message.as_bytes())
        mail_files.append(path)
    erp_file = out_dir / "erp.csv"
    _write_erp(spec, erp_file)
    gold_file = out_dir / "gold.json"
    gold_file.write_text(
        json.dumps(_gold(spec), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return BuildResult(tuple(mail_files), erp_file, gold_file)
