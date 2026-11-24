from pathlib import Path

import pytest

from eshipping_ai.adapters.object_store import LocalObjectStore
from eshipping_ai.adapters.pdf_text import PdfTextParser


def make_pdf(lines: list[str]) -> bytes:
    """Smallest valid PDF with one page of text; offsets are computed, not guessed."""
    stream = "BT /F1 12 Tf 72 720 Td " + " ".join(f"({line}) Tj 0 -16 Td" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out


def test_pdf_with_text_layer() -> None:
    result = PdfTextParser().parse(
        make_pdf(["LEVANTE concedido", "Contenedor SYNU1000019"]), "levante.PDF"
    )
    assert result.has_text_layer
    assert result.pages == 1
    assert result.text is not None
    assert "SYNU1000019" in result.text


def test_pdf_without_text_is_reported_as_scan() -> None:
    result = PdfTextParser().parse(make_pdf([]), "escaneo.pdf")
    assert not result.has_text_layer
    assert result.text is None
    assert result.pages == 1


@pytest.mark.parametrize(("content", "name"), [(b"not a pdf", "roto.pdf"), (b"x", "datos.xlsx")])
def test_unreadable_or_non_pdf_files_have_no_text(content: bytes, name: str) -> None:
    result = PdfTextParser().parse(content, name)
    assert result.text is None
    assert not result.has_text_layer


def test_object_store_is_content_addressed(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path)
    key = store.put(b"hola")
    assert key == store.put(b"hola")
    assert key.startswith("sha256/") and len(key.split("/")) == 4
    assert store.get(key) == b"hola"
    assert len(list(tmp_path.rglob("*"))) == 4  # three folders and one file


@pytest.mark.parametrize("key", ["sha256/aa/bb/missing", "../etc/passwd", "sha256/../../x/y", "x"])
def test_object_store_rejects_unknown_or_unsafe_keys(tmp_path: Path, key: str) -> None:
    with pytest.raises(KeyError):
        LocalObjectStore(tmp_path).get(key)
