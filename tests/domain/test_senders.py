from pathlib import Path

from eshipping_ai.adapters.config_yaml import load_sender_directory
from eshipping_ai.domain.vocabulary import SourceRole

DIRECTORY = load_sender_directory(Path(__file__).parents[2] / "config" / "senders.yaml")


def test_a_known_domain_gives_its_role_and_date_order() -> None:
    profile = DIRECTORY.profile_for("Customer Service <bookings@naviera-ficticia.example>")
    assert profile.role is SourceRole.CARRIER and profile.month_first is False


def test_a_subdomain_belongs_to_its_parent_domain() -> None:
    assert DIRECTORY.profile_for("a@mail.naviera-ficticia.example").role is SourceRole.CARRIER


def test_an_unknown_sender_is_a_customer_with_ambiguous_dates() -> None:
    for address in ("someone@nowhere.example", "no address at all"):
        profile = DIRECTORY.profile_for(address)
        assert profile.role is SourceRole.CUSTOMER and profile.month_first is None
