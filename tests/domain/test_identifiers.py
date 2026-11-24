import pytest
from pydantic import TypeAdapter, ValidationError

from eshipping_ai.domain.identifiers import (
    ContainerNumber,
    Reference,
    UnLocode,
    is_valid_container_number,
    iso6346_check_digit,
    normalize_reference,
)

# CSQU3054383 is the worked example of the ISO 6346 standard; the others are invented.
VALID = ["CSQU3054383", "ABCU1234560", "ZZZU0000005"]


@pytest.mark.parametrize("number", VALID)
def test_check_digit_of_valid_numbers(number: str) -> None:
    assert iso6346_check_digit(number[:10]) == int(number[10])
    assert is_valid_container_number(number)


def test_letter_values_skip_multiples_of_eleven() -> None:
    # A=10, B=12 (11 skipped): changing A to B changes the weighted sum by 2.
    assert iso6346_check_digit("BBBU0000000"[:10]) != iso6346_check_digit("AAAU0000000"[:10])


@pytest.mark.parametrize(
    "candidate",
    ["CSQU3054384", "CSQX3054383", "CSQU305438", "1SQU3054383", "", "CSQU30543833"],
)
def test_invalid_numbers(candidate: str) -> None:
    assert not is_valid_container_number(candidate)


def test_check_digit_rejects_bad_prefix() -> None:
    with pytest.raises(ValueError, match="ISO 6346"):
        iso6346_check_digit("CSQ3054383")


def test_container_type_normalises_and_validates() -> None:
    adapter = TypeAdapter(ContainerNumber)
    assert adapter.validate_python("csqu 305438-3") == "CSQU3054383"
    with pytest.raises(ValidationError):
        adapter.validate_python("CSQU3054384")


def test_reference_normalisation() -> None:
    assert normalize_reference(" bkg-123 456/7 ") == "BKG1234567"
    assert TypeAdapter(Reference).validate_python("ab.12") == "AB12"
    with pytest.raises(ValidationError):
        TypeAdapter(Reference).validate_python(" - ")


@pytest.mark.parametrize(("code", "valid"), [("ESVLC", True), ("ESBCN", True), ("ES1AB", False)])
def test_unlocode(code: str, *, valid: bool) -> None:
    adapter = TypeAdapter(UnLocode)
    if valid:
        assert adapter.validate_python(code) == code
    else:
        with pytest.raises(ValidationError):
            adapter.validate_python(code)
