from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from eshipping_ai.extraction.thread import (
    clean_body,
    content_hash,
    html_to_text,
    parse_header_date,
    split_thread,
)

MADRID = ZoneInfo("Europe/Madrid")


def test_html_to_text_keeps_blocks_and_drops_styles() -> None:
    markup = (
        "<html><head><style>p{color:red}</style></head><body><p>Hola&nbsp;mundo</p>"
        "<div>ETD&nbsp;22/09</div><table><tr><td>A</td><td>B</td></tr></table>"
        "<script>x()</script></body></html>"
    )
    assert html_to_text(markup) == "Hola mundo\n\nETD 22/09\n\nA B"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("29/09/2026 10:15", datetime(2026, 9, 29, 10, 15, tzinfo=MADRID)),
        ("lunes, 29 de septiembre de 2026 10:15", datetime(2026, 9, 29, 10, 15, tzinfo=MADRID)),
        ("Monday, September 29, 2026 3:05 PM", datetime(2026, 9, 29, 15, 5, tzinfo=MADRID)),
        ("Mon, Sep 29, 2026 at 12:05 AM", datetime(2026, 9, 29, 0, 5, tzinfo=MADRID)),
        (
            "Mon, 29 Sep 2026 10:15:00 +0200",
            datetime(2026, 9, 29, 10, 15, tzinfo=timezone(timedelta(hours=2))),
        ),
    ],
)
def test_header_dates(text: str, expected: datetime) -> None:
    assert parse_header_date(text, MADRID) == expected


@pytest.mark.parametrize("text", ["ayer", "31/02/2026 10:15", "Foo 99, 2026 10:15", ""])
def test_unparseable_header_dates(text: str) -> None:
    assert parse_header_date(text, MADRID) is None


OUTLOOK = """Hola, confirmado.

Un saludo,
Laura

De: Naviera <bookings@naviera.example>
Enviado: 29/09/2026 10:15
Para: Operaciones <ops@x.example>
Asunto: RE: ROLLOVER

Previous vessel: AAA
New ETD: 06/10/2026

-----Original Message-----
From: Cliente <cliente@c.example>
Sent: Monday, September 28, 2026 9:00 AM
To: Naviera <bookings@naviera.example>
Subject: ROLLOVER

> Please roll my cargo
"""


def test_split_thread_with_outlook_headers() -> None:
    segments = split_thread(OUTLOOK, MADRID)
    assert [s.depth for s in segments] == [0, 1, 2]
    assert segments[0].sender is None
    assert "confirmado" in segments[0].body
    assert segments[1].sender == "bookings@naviera.example"
    assert segments[1].sent_at == datetime(2026, 9, 29, 10, 15, tzinfo=MADRID)
    assert segments[1].subject == "RE: ROLLOVER"
    assert "New ETD: 06/10/2026" in segments[1].body
    assert "Original Message" not in segments[1].body
    assert segments[2].sender == "cliente@c.example"
    assert "Please roll my cargo" in segments[2].body


def test_split_thread_with_gmail_attribution_and_quote_marks() -> None:
    body = (
        "Gracias.\n\nOn Mon, Sep 29, 2026 at 10:15 AM, Ana Ejemplo wrote:\n> ETD 22/09\n> ETA 05/10"
    )
    segments = split_thread(body, MADRID)
    assert len(segments) == 2
    assert segments[1].sender == "ana ejemplo"
    assert segments[1].body.splitlines()[-2:] == ["ETD 22/09", "ETA 05/10"]


def test_incomplete_header_block_is_plain_text() -> None:
    body = "De: lo que sea\nesto no es un encabezado\nETD 22/09"
    assert len(split_thread(body, MADRID)) == 1


def test_clean_body_removes_signature_disclaimer_and_images() -> None:
    text = (
        "[cid:image001.png@01D]\nETD 22/09\n\nAVISO LEGAL: este mensaje es confidencial.\n\n"
        "Best regards,\nCustomer Service\nTel. 600 000 000"
    )
    assert clean_body(text) == "ETD 22/09"
    assert clean_body("ETD 22/09\n--\nLaura\nOperaciones") == "ETD 22/09"
    assert clean_body("Un saludo,\nLaura") == ""


def test_content_hash_ignores_case_and_spacing_but_not_time() -> None:
    sent = datetime(2026, 9, 29, 10, 15, 42, tzinfo=UTC)
    same_minute = datetime(2026, 9, 29, 10, 15, 5, tzinfo=UTC)
    later = datetime(2026, 9, 29, 10, 16, tzinfo=UTC)
    assert content_hash("ETD  22/09", sent) == content_hash("etd 22/09", same_minute)
    assert content_hash("ETD 22/09", sent) != content_hash("ETD 22/09", later)
    assert content_hash("ETD 22/09", None) != content_hash("ETD 22/09", sent)
