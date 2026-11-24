"""Deterministic extraction of ports and their UN/LOCODE (RF-23, RF-42).

The table below is a small, public sample for the PoC. In production it is replaced by the
full UN/LOCODE list published by UNECE, loaded as data, without changing the extractor.
Names are compared without accents or case. Codes written explicitly (``(ESVLC)``,
``POL=ESVLC``) are taken as they are. A name that is also the name of ports in different
countries is left out of the table on purpose, so that it is never guessed.
"""

import re
import unicodedata
from dataclasses import dataclass

PORTS: dict[str, str] = {
    "valencia": "ESVLC",
    "barcelona": "ESBCN",
    "algeciras": "ESALG",
    "bilbao": "ESBIO",
    "vigo": "ESVGO",
    "sevilla": "ESSVQ",
    "malaga": "ESAGP",
    "tarragona": "ESTAR",
    "alicante": "ESALC",
    "las palmas": "ESLPA",
    "gijon": "ESGIJ",
    "castellon": "ESCAS",
    "santander": "ESSDR",
    "huelva": "ESHUV",
    "palma de mallorca": "ESPMI",
    "new york": "USNYC",
    "los angeles": "USLAX",
    "houston": "USHOU",
    "savannah": "USSAV",
    "miami": "USMIA",
    "santos": "BRSSZ",
    "veracruz": "MXVER",
    "manzanillo": "MXZLO",
    "buenos aires": "ARBUE",
    "montevideo": "UYMVD",
    "valparaiso": "CLVAP",
    "callao": "PECLL",
    "guayaquil": "ECGYE",
    "kingston": "JMKIN",
    "rotterdam": "NLRTM",
    "hamburg": "DEHAM",
    "hamburgo": "DEHAM",
    "antwerp": "BEANR",
    "amberes": "BEANR",
    "le havre": "FRLEH",
    "marseille": "FRMRS",
    "marsella": "FRMRS",
    "genoa": "ITGOA",
    "genova": "ITGOA",
    "la spezia": "ITSPE",
    "gioia tauro": "ITGIT",
    "lisbon": "PTLIS",
    "lisboa": "PTLIS",
    "sines": "PTSIN",
    "leixoes": "PTLEI",
    "felixstowe": "GBFXT",
    "southampton": "GBSOU",
    "piraeus": "GRPIR",
    "pireo": "GRPIR",
    "alexandria": "EGALY",
    "casablanca": "MACAS",
    "tanger med": "MAPTM",
    "jebel ali": "AEJEA",
    "mumbai": "INBOM",
    "nhava sheva": "INNSA",
    "colombo": "LKCMB",
    "singapore": "SGSIN",
    "singapur": "SGSIN",
    "shanghai": "CNSHA",
    "ningbo": "CNNGB",
    "shenzhen": "CNSZX",
    "hong kong": "HKHKG",
    "busan": "KRPUS",
    "tokyo": "JPTYO",
    "yokohama": "JPYOK",
    "durban": "ZADUR",
    "lagos": "NGLOS",
}

ROLE_POL = "POL"
ROLE_POD = "POD"
_ROLE_LOOKBACK = 45
_POL_CONTEXT = re.compile(
    r"(?:loading|carga|origen|origin|\bpol\b|embarque|from|salida)\W[^.\n]*$", re.IGNORECASE
)
_POD_CONTEXT = re.compile(
    r"(?:discharge|descarga|destino|destination|\bpod\b|delivery|to|hacia)\W[^.\n]*$",
    re.IGNORECASE,
)
_NAMES_RE = re.compile(
    r"(?<![a-z])(?:"
    + "|".join(sorted(map(re.escape, PORTS), key=len, reverse=True))
    + r")(?![a-z])"
)
_CODE_RE = re.compile(
    r"(?:\((?P<paren>[A-Z]{2}[A-Z2-9]{3})\)|\b(?:POL|POD|LOCODE)\s*[=:]\s*(?P<tagged>[A-Z]{2}[A-Z2-9]{3})\b)"
)


@dataclass(frozen=True, slots=True)
class LocationMention:
    """A port found in a text, with its role when the context tells it."""

    unlocode: str
    raw: str
    start: int
    end: int
    role: str | None
    from_code: bool


def strip_accents(text: str) -> str:
    """Lower-case a text and remove its accents; the result has the same length.

    Args:
        text: Text to normalise.

    Returns:
        The text without accents, so that positions in it are positions in the original.
    """
    return "".join(
        unicodedata.normalize("NFD", char)[0] if unicodedata.combining(char) == 0 else char
        for char in text.lower()
    )


def _role_before(text: str, start: int) -> str | None:
    context = text[max(0, start - _ROLE_LOOKBACK) : start]
    pol, pod = _POL_CONTEXT.search(context), _POD_CONTEXT.search(context)
    if pol and pod:
        return ROLE_POL if pol.start() > pod.start() else ROLE_POD
    return ROLE_POL if pol else ROLE_POD if pod else None


def find_locations(text: str) -> list[LocationMention]:
    """Find ports by name or by explicit UN/LOCODE.

    Args:
        text: Text to search.

    Returns:
        The mentions in order of appearance; a name followed by its own code in brackets is
        reported once, with the code.
    """
    found: list[LocationMention] = []
    for match in _CODE_RE.finditer(text):
        code = match["paren"] or match["tagged"]
        found.append(
            LocationMention(code, code, *match.span(), _role_before(text, match.start()), True)
        )
    plain = strip_accents(text)
    for match in _NAMES_RE.finditer(plain):
        start, end = match.span()
        if any(code.start - len(code.raw) - 2 <= end <= code.start + 1 for code in found):
            continue
        found.append(
            LocationMention(
                PORTS[match.group(0)], text[start:end], start, end, _role_before(text, start), False
            )
        )
    return sorted(found, key=lambda mention: mention.start)
