from datetime import UTC, datetime

from eshipping_ai.application.associate import find_shipments, learn_aliases
from eshipping_ai.domain.model import ShipmentAlias
from eshipping_ai.domain.vocabulary import AliasType, AssociationMethod, AssociationStatus
from eshipping_ai.extraction.events import Identifiers

AT = datetime(2026, 10, 1, tzinfo=UTC)


class MemoryAliases:
    def __init__(self, *known: tuple[str, AliasType, str]) -> None:
        self.aliases = [
            ShipmentAlias(shipment_id=s, alias_type=t, value=v, valid_from=AT) for s, t, v in known
        ]

    def find_aliases(self, alias_type: AliasType, value: str) -> list[ShipmentAlias]:
        return [a for a in self.aliases if a.alias_type is alias_type and a.value == value]

    def add_alias(self, alias: ShipmentAlias) -> None:
        self.aliases.append(alias)


def ids(**kwargs: tuple[str, ...]) -> Identifiers:
    base: dict[str, tuple[str, ...]] = {"bookings": (), "previous_bookings": (), "containers": ()}
    return Identifiers(**(base | kwargs))


def test_the_strongest_kind_of_identifier_decides() -> None:
    aliases = MemoryAliases(
        ("S1", AliasType.BOOKING, "111"), ("S2", AliasType.CONTAINER, "SYNU1000019")
    )
    matches = find_shipments(ids(bookings=("111",), containers=("SYNU1000019",)), aliases)
    assert [(m.shipment_id, m.method) for m in matches] == [("S1", AssociationMethod.BOOKING)]


def test_a_container_alone_associates_with_less_confidence() -> None:
    aliases = MemoryAliases(("S2", AliasType.CONTAINER, "SYNU1000019"))
    (match,) = find_shipments(ids(containers=("SYNU1000019",)), aliases)
    assert match.method is AssociationMethod.CONTAINER and match.confidence < 0.9


def test_an_identifier_of_two_shipments_goes_to_review() -> None:
    aliases = MemoryAliases(("S1", AliasType.BOOKING, "111"), ("S2", AliasType.BOOKING, "111"))
    matches = find_shipments(ids(bookings=("111",)), aliases)
    assert {m.shipment_id for m in matches} == {"S1", "S2"}
    assert {m.status for m in matches} == {AssociationStatus.IN_REVIEW}


def test_a_thread_can_speak_about_two_shipments() -> None:
    aliases = MemoryAliases(("S1", AliasType.BOOKING, "111"), ("S2", AliasType.BOOKING, "222"))
    matches = find_shipments(ids(bookings=("111", "222")), aliases)
    assert {m.shipment_id for m in matches} == {"S1", "S2"}
    assert {m.status for m in matches} == {AssociationStatus.AUTO}


def test_nothing_is_found_when_the_index_knows_nothing() -> None:
    assert find_shipments(ids(bookings=("999",)), MemoryAliases()) == []


def test_the_replaced_booking_finds_the_shipment_and_the_new_one_is_learned() -> None:
    aliases = MemoryAliases(("S1", AliasType.BOOKING, "111"))
    found = ids(bookings=("222",), previous_bookings=("111",), containers=("SYNU1000019",))
    matches = find_shipments(found, aliases)
    assert learn_aliases(matches, found, aliases, AT) == 2
    assert [a.shipment_id for a in aliases.find_aliases(AliasType.BOOKING, "222")] == ["S1"]
    assert learn_aliases(matches, found, aliases, AT) == 0


def test_nothing_is_learned_from_a_container_or_from_several_shipments() -> None:
    by_container = MemoryAliases(("S1", AliasType.CONTAINER, "SYNU1000019"))
    found = ids(bookings=("333",), containers=("SYNU1000019",))
    assert learn_aliases(find_shipments(found, by_container), found, by_container, AT) == 0
    two = MemoryAliases(("S1", AliasType.BOOKING, "111"), ("S2", AliasType.BOOKING, "222"))
    found = ids(bookings=("111", "222", "333"))
    assert learn_aliases(find_shipments(found, two), found, two, AT) == 0
