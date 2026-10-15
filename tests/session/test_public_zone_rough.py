"""The public zone projection flags rough ground (terrain or a difficult surface)."""

from aidm.models.zones import Zone, ZoneSurface
from aidm.rules.hex_layout import touching
from aidm.session.views import _public_zone, public_combat
from tests.unit.rules.encounter_fixtures import make_pc, started


def test_grease_makes_a_zone_rough_while_the_terrain_flag_stays_false() -> None:
    zone = Zone(id="bridge", name="Bridge", surfaces=[ZoneSurface(kind="grease", rounds_left=2)])
    view = _public_zone(zone, (0, 0))
    assert view.rough is True
    assert view.difficult is False


def test_plain_and_terrain_zones_project_rough_from_the_effective_value() -> None:
    assert _public_zone(Zone(id="a", name="A"), (0, 0)).rough is False
    assert _public_zone(Zone(id="b", name="B", difficult=True), (0, 0)).rough is True
    fire = Zone(id="c", name="C", surfaces=[ZoneSurface(kind="fire", rounds_left=1)])
    assert _public_zone(fire, (0, 0)).rough is False


def test_public_combat_places_every_zone_on_a_hex() -> None:
    """M21: the screen's hex map comes from q, r; a map without stored hexes gets a fit."""
    state, _ = started(1, [make_pc("ana")], ["goblin"])
    combat = public_combat(state)
    assert combat is not None
    cells = {z.id: (z.q, z.r) for z in combat.zones}
    assert len(set(cells.values())) == len(cells)
    assert all(touching(cells[e.a], cells[e.b]) for e in combat.edges)
