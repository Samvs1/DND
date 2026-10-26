"""What the line hands over that the acting hero does not carry (M40.5, round 7 Z13)."""

from aidm.models.character import InventoryItem
from aidm.models.state import GameState
from aidm.rules.not_carried import HeldElsewhere, held_elsewhere, named_heroes
from tests.unit.rules.encounter_fixtures import make_pc


def _party() -> GameState:
    brienne, rook, tamsin = make_pc("pc-b"), make_pc("pc-r"), make_pc("pc-t")
    for hero, name in ((brienne, "Brienne"), (rook, "Rook"), (tamsin, "Tamsin")):
        hero.name = name
        assert hero.pc is not None
        hero.pc.inventory = []
    assert brienne.pc is not None and tamsin.pc is not None and rook.pc is not None
    brienne.pc.inventory = [InventoryItem(item="torch", qty=8)]
    tamsin.pc.inventory = [InventoryItem(item="blanket", qty=1), InventoryItem(item="torch")]
    rook.pc.inventory = [InventoryItem(item="blanket", qty=1)]
    return GameState(campaign_id="t", seed=1, creatures={c.id: c for c in (brienne, rook, tamsin)})


def test_a_thing_another_hero_carries_names_its_holders() -> None:
    found = held_elsewhere(_party(), "pc-b", "Brienne hands Rook the blanket")
    assert found == (HeldElsewhere("Blanket", ("Rook", "Tamsin")),)


def test_a_thing_the_hero_carries_is_not_named() -> None:
    assert held_elsewhere(_party(), "pc-b", "Brienne hands Rook two torches") == ()


def test_the_other_heroes_the_line_names() -> None:
    assert named_heroes(_party(), "pc-b", "Brienne hands Rook the blanket") == ("Rook",)
    assert named_heroes(_party(), "pc-b", "I wave at the bridge") == ()
