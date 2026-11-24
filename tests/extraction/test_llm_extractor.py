from datetime import UTC, date

from eshipping_ai.domain.ports import LLMResponse
from eshipping_ai.domain.vocabulary import EventClassifier, ExtractionTier, MailClass
from eshipping_ai.extraction.events import extract_candidates
from eshipping_ai.extraction.llm_extractor import (
    MAX_INPUT_CHARS,
    build_request,
    locate_quote,
    parse_response,
    pending_fields,
)

SENT = date(2026, 9, 29)
TEXT = (
    "Asunto: Cambio de planes BKG 990000101\n"
    "Os confirmamos que el barco finalmente sale el jueves 1 de octubre,\n"
    "a bordo del AURORA FICTICIA, con 2 contenedores."
)
FIELDS = ("vessel", "vessel_departure", "equipment_count")


def answer(*facts: dict[str, str]) -> LLMResponse:
    return LLMResponse(
        output={"facts": list(facts)}, model="m", input_tokens=1, output_tokens=1, latency_ms=0
    )


def fact(field: str, value: str, quote: str, classifier: str = "EST") -> dict[str, str]:
    return {"field": field, "value": value, "quote": quote, "classifier": classifier}


def test_only_the_fields_the_rules_left_pending_are_asked() -> None:
    found = extract_candidates("ETD: 06/10/2026", SENT, UTC)
    assert pending_fields(MailClass.VESSEL, found, "") == ("vessel", "vessel_arrival_pod")
    assert pending_fields(MailClass.OTHER, [], "") == ()


def test_a_field_the_text_has_no_word_about_is_not_asked() -> None:
    assert pending_fields(MailClass.DOCUMENTATION, [], "Adjunto el BL draft") == ()
    assert pending_fields(MailClass.DOCUMENTATION, [], "VGM antes del lunes") == ("cutoff_vgm",)


def test_the_request_has_a_fixed_prefix_and_bounded_input() -> None:
    first = build_request("x" * (MAX_INPUT_CHARS + 50), FIELDS, SENT)
    second = build_request("other", FIELDS, SENT)
    assert first.instructions == second.instructions and first.json_schema == second.json_schema
    assert first.content.count("x") == MAX_INPUT_CHARS
    assert first.json_schema["properties"]["facts"]["items"]["properties"]["field"]["enum"] == [  # type: ignore[index]
        *FIELDS
    ]


def test_a_quote_is_found_despite_spacing_and_case() -> None:
    assert locate_quote(TEXT, "sale el jueves 1 de octubre") is not None
    assert locate_quote(TEXT, "SALE  EL\njueves") is not None
    assert locate_quote(TEXT, "sale el viernes") is None
    assert locate_quote(TEXT, "   ") is None


def test_values_backed_by_their_quote_become_llm_candidates() -> None:
    outcome = parse_response(
        answer(
            fact("vessel_departure", "2026-10-01", "sale el jueves 1 de octubre", "ACT"),
            fact("vessel", "Aurora Ficticia", "a bordo del AURORA FICTICIA"),
            fact("equipment_count", "2", "con 2 contenedores"),
        ),
        TEXT,
        FIELDS,
        SENT,
        UTC,
    )
    assert outcome.rejected == {}
    by_field = {c.field: c for c in outcome.candidates}
    departure = by_field["vessel_departure"]
    assert departure.classifier is EventClassifier.ACTUAL and departure.tier is ExtractionTier.LLM
    assert TEXT[departure.start : departure.end] == "sale el jueves 1 de octubre"
    assert by_field["vessel"].value == "AURORA FICTICIA"
    assert departure.confidence < 0.9


def test_invented_or_unsupported_values_are_dropped() -> None:
    outcome = parse_response(
        answer(
            fact("vessel_departure", "2026-10-02", "sale el jueves 1 de octubre"),  # not in quote
            fact("vessel_departure", "2026-10-01", "sale el 1 de octubre sin falta"),  # invented
            fact("vessel_departure", "2027-12-01", "sale el jueves 1 de octubre"),  # implausible
            fact("vessel_departure", "pronto", "sale el jueves 1 de octubre"),  # not a date
            fact("vessel", "BOREAL FICTICIA", "a bordo del AURORA FICTICIA"),
            fact("equipment_count", "3", "con 2 contenedores"),
            fact("customs_release", "2026-10-01", "sale el jueves 1 de octubre"),  # not asked
        ),
        TEXT,
        FIELDS,
        SENT,
        UTC,
    )
    assert outcome.candidates == ()
    assert outcome.rejected == {
        "value_not_in_quote": 3,
        "quote_not_in_text": 1,
        "implausible_date": 1,
        "bad_value": 1,
        "field_not_requested": 1,
    }


def test_a_date_needs_words_that_do_not_name_another_field() -> None:
    text = "Asunto: Aviso\nETD Valencia: 01/10/2026\nVessel AURORA FICTICIA, 1 de octubre."
    outcome = parse_response(
        answer(
            fact("vessel_arrival_pod", "2026-10-01", "01/10/2026"),
            fact("vessel_arrival_pod", "2026-10-01", "ETD Valencia: 01/10/2026"),
        ),
        text,
        ("vessel_arrival_pod",),
        SENT,
        UTC,
    )
    assert outcome.candidates == ()
    assert outcome.rejected == {"quote_without_context": 1, "field_contradicts_quote": 1}


def test_a_name_or_count_is_an_estimate_and_the_voyage_is_dropped() -> None:
    text = "Asunto: Salida\nThe M/V Aurora Ficticia / 041E has sailed."
    outcome = parse_response(
        answer(fact("vessel", "M/V Aurora Ficticia / 041E", "M/V Aurora Ficticia / 041E", "ACT")),
        text,
        ("vessel",),
        SENT,
        UTC,
    )
    (candidate,) = outcome.candidates
    assert candidate.value == "AURORA FICTICIA"
    assert candidate.classifier is EventClassifier.ESTIMATED


def test_a_malformed_answer_keeps_nothing() -> None:
    weird = LLMResponse(
        output={"facts": ["not an object"]},
        model="m",
        input_tokens=0,
        output_tokens=0,
        latency_ms=0,
    )
    outcome = parse_response(weird, TEXT, FIELDS, SENT, UTC)
    assert outcome.candidates == () and outcome.rejected == {"bad_shape": 1}
    missing = parse_response(answer(), TEXT, FIELDS, SENT, UTC)
    assert missing.candidates == () and missing.rejected == {}


def test_an_unknown_state_is_read_as_an_estimate() -> None:
    outcome = parse_response(
        answer(fact("vessel_departure", "2026-10-01", "sale el jueves 1 de octubre", "MAYBE")),
        TEXT,
        FIELDS,
        SENT,
        UTC,
    )
    assert outcome.candidates[0].classifier is EventClassifier.ESTIMATED
