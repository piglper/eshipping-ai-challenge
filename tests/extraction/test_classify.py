import pytest

from eshipping_ai.domain.vocabulary import MailClass
from eshipping_ai.extraction.classify import Priority, classify, lists_offered_options, triage


@pytest.mark.parametrize(
    ("subject", "body", "expected"),
    [
        ("BOOKING CONFIRMATION 990000101", "Dear Customer", MailClass.BOOKING),
        ("ROLLOVER NOTICE - BKG 990000202", "your cargo has been rolled", MailClass.VESSEL),
        ("ORDEN DE TRANSPORTE ES26900001", "Carga en almacén", MailClass.TRANSPORT),
        ("SHIPPING INSTRUCTION 990000101", "VGM enviado", MailClass.DOCUMENTATION),
        ("LEVANTE ES26900001", "se ha concedido el levante", MailClass.CUSTOMS),
        ("Certificado de inspección", "adjunto", MailClass.INSPECTION),
        ("Cotización flete", "tarifa válida hasta", MailClass.COMMERCIAL),
        ("Factura demurrage", "invoice adjunta", MailClass.FINANCE),
        ("Boletín semanal", "nuevas grúas en la terminal", MailClass.OTHER),
        # The booking in the subject of a thread names it; the reply is about transport.
        (
            "RE: BKG 990000101 / ES26900001",
            "Orden de transporte para la recogida",
            MailClass.TRANSPORT,
        ),
        ("RE: Booking nº 990000101", "se ha concedido el levante", MailClass.CUSTOMS),
    ],
)
def test_primary_class(subject: str, body: str, expected: MailClass) -> None:
    matches = classify(subject, body)
    assert matches[0].mail_class is expected
    assert matches[0].is_primary and not any(m.is_primary for m in matches[1:])


def test_a_subject_hit_weighs_more_than_a_body_hit() -> None:
    matches = classify("LEVANTE ES26900001", "booking 990000101 booking confirmation")
    assert [m.mail_class for m in matches] == [MailClass.CUSTOMS, MailClass.BOOKING]
    assert matches[0].score > matches[1].score


def test_triage_noise_needs_no_identifier_at_all() -> None:
    noise = triage("Boletín semanal", "Esta semana: nuevas grúas")
    assert (noise.is_noise, noise.reason) == (True, "no_identifiers")
    assert not triage("Booking 990000101", "ETD 22/09").is_noise


def test_triage_urgency() -> None:
    urgent = triage("ROLLOVER NOTICE BKG 990000202", "rolled to the next vessel")
    assert (urgent.priority, urgent.reason) == (Priority.URGENT, "keyword:rolled")
    assert triage("BKG 990000202", "closing 16/09").priority is Priority.URGENT
    assert triage("BKG 990000202", "todo correcto").priority is Priority.NORMAL


def test_offered_options_are_not_a_confirmation() -> None:
    options = "Opción 1: NORDIC STAR ETD 04/09\nOpción 2: BLUE HORIZON ETD 07/09"
    assert lists_offered_options(options)
    assert not lists_offered_options(options + "\nBooking confirmado, tomad nota")
    assert not lists_offered_options("ETD 04/09")
