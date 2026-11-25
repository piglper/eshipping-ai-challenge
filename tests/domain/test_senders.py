from pathlib import Path

import pytest

from eshipping_ai.adapters.config_yaml import load_sender_directory
from eshipping_ai.domain.model import ErpRecord
from eshipping_ai.domain.senders import names_sender
from eshipping_ai.domain.vocabulary import SourceRole

DIRECTORY = load_sender_directory(Path(__file__).parents[2] / "config" / "senders.yaml")
PARTIES = {
    SourceRole.CARRIER: ["NAVIERA FICTICIA"],
    SourceRole.CUSTOMS_AGENT: ["ADUANAS EJEMPLO S.L."],
    SourceRole.HAULIER: ["TRANSPORTES INVENTADOS S.L."],
    SourceRole.CUSTOMER: ["CÍTRICOS DE EJEMPLO S.L."],
}


def test_a_curated_domain_gives_its_role_and_date_order() -> None:
    resolved = DIRECTORY.resolve("Customer Service <bookings@naviera-ficticia.example>")
    assert (resolved.role, resolved.month_first, resolved.basis) == (
        SourceRole.CARRIER,
        False,
        "directory",
    )
    assert DIRECTORY.resolve("noreply@notifications.maersk.com").role is SourceRole.CARRIER


def test_a_subdomain_belongs_to_its_parent_domain() -> None:
    profile = DIRECTORY.profile_for("a@mail.naviera-ficticia.example")
    assert profile is not None and profile.role is SourceRole.CARRIER


@pytest.mark.parametrize(
    ("address", "role"),
    [
        ("trafico@transportes-inventados.example", SourceRole.HAULIER),
        ("Despachos <despachos@aduanasejemplo.example>", SourceRole.CUSTOMS_AGENT),
        ("Transportes Inventados <trafico@gmail.example>", SourceRole.HAULIER),
        ("logistica@citricos-ejemplo.example", SourceRole.CUSTOMER),
    ],
)
def test_a_party_of_the_shipment_in_the_erp_gives_the_role(address: str, role: SourceRole) -> None:
    resolved = DIRECTORY.resolve(address, PARTIES)
    assert (resolved.role, resolved.basis) == (role, "erp")


def test_the_parties_of_the_erp_also_give_the_date_order() -> None:
    assert DIRECTORY.resolve("t@transportes-inventados.example", PARTIES).month_first is False


def test_an_unknown_sender_is_a_customer_with_ambiguous_dates() -> None:
    for address in ("someone@nowhere.example", "no address at all"):
        resolved = DIRECTORY.resolve(address, PARTIES)
        assert (resolved.role, resolved.month_first, resolved.basis) == (
            SourceRole.CUSTOMER,
            None,
            "default",
        )


@pytest.mark.parametrize(
    ("party", "address", "same"),
    [
        ("TRANSPORTES INVENTADOS S.L.", "x@transportes-inventados.example", True),
        ("Transportes Inventados, S.L.U.", "x@mail.transportesinventados.co.uk", True),
        # Sharing one word is not enough: a false match would give authority to a customer.
        ("ADUANAS EJEMPLO S.L.", "x@citricos-ejemplo.example", False),
        # Too short to tell apart.
        ("ABC S.A.", "x@abc.example", False),
        ("NAVIERA FICTICIA", "Naviera Ficticia Lines <x@gmail.example>", True),
    ],
)
def test_a_party_names_a_sender_only_on_a_strict_match(
    party: str, address: str, *, same: bool
) -> None:
    assert names_sender(party, address) is same


def test_the_parties_of_each_shipment_are_read_from_the_erp() -> None:
    record = ErpRecord(
        snapshot_id="s",
        operation="ES26900001",
        raw={
            "Línea Transporte": "NAVIERA FICTICIA",
            "Transportistas": "TRANSPORTES INVENTADOS S.L. / OTRO TRANSPORTE S.A.",
            "Agente Aduana": "",
        },
        normalized={},
    )
    assert DIRECTORY.parties_of([record]) == {
        "ES26900001": {
            SourceRole.CARRIER: ["NAVIERA FICTICIA"],
            SourceRole.HAULIER: ["TRANSPORTES INVENTADOS S.L.", "OTRO TRANSPORTE S.A."],
        }
    }
