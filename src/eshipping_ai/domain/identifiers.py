"""Validation and normalisation of shipping identifiers.

Container numbers follow ISO 6346: three letters for the owner, one category letter
(U, J, Z or R), six digits for the serial number and a check digit. The check digit is the
weighted sum of the first ten characters, modulo 11 and then modulo 10.
"""

import re
from typing import Annotated

from pydantic import AfterValidator, StringConstraints

_CONTAINER_RE = re.compile(r"[A-Z]{3}[UJZR]\d{7}")
_SEPARATORS_RE = re.compile(r"[\s\-./]+")
_CHECKED_CHARS = 10


def _letter_values() -> dict[str, int]:
    """Values of the letters in ISO 6346: from 10, skipping the multiples of 11."""
    values: dict[str, int] = {}
    value = 10
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if value % 11 == 0:
            value += 1
        values[letter] = value
        value += 1
    return values


_LETTER_VALUES = _letter_values()


def normalize_reference(raw: str) -> str:
    """Normalise a booking, B/L, operation or container reference for comparison.

    Args:
        raw: Reference as written in the source.

    Returns:
        The reference in upper case without spaces, hyphens, dots or slashes.
    """
    return _SEPARATORS_RE.sub("", raw).upper()


def iso6346_check_digit(prefix: str) -> int:
    """Compute the ISO 6346 check digit of the first ten characters of a container number.

    Args:
        prefix: Owner code, category letter and serial number (ten characters).

    Returns:
        The check digit, from 0 to 9.

    Raises:
        ValueError: If the prefix does not have the ISO 6346 shape.
    """
    if not re.fullmatch(r"[A-Z]{3}[UJZR]\d{6}", prefix):
        msg = f"not an ISO 6346 prefix: {prefix!r}"
        raise ValueError(msg)
    total = sum(
        (_LETTER_VALUES[char] if char.isalpha() else int(char)) << position
        for position, char in enumerate(prefix)
    )
    return total % 11 % 10


def is_valid_container_number(candidate: str) -> bool:
    """Tell whether a string is a container number with a correct check digit.

    Args:
        candidate: Text to check, already normalised or not.

    Returns:
        True if it has the ISO 6346 shape and its check digit is correct.
    """
    number = normalize_reference(candidate)
    if not _CONTAINER_RE.fullmatch(number):
        return False
    return iso6346_check_digit(number[:_CHECKED_CHARS]) == int(number[_CHECKED_CHARS])


def _validate_container_number(raw: str) -> str:
    number = normalize_reference(raw)
    if not is_valid_container_number(number):
        msg = f"invalid ISO 6346 container number: {raw!r}"
        raise ValueError(msg)
    return number


ContainerNumber = Annotated[str, AfterValidator(_validate_container_number)]
"""Container number validated with its ISO 6346 check digit and normalised."""

Reference = Annotated[str, AfterValidator(normalize_reference), StringConstraints(min_length=1)]
"""Booking, B/L or operation reference, normalised for comparison."""

UnLocode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}[A-Z2-9]{3}$")]
"""UN/LOCODE: country code and three-character location code (for example, ESVLC)."""

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
"""Hex-encoded SHA-256 digest."""
