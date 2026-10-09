"""The public zone projection flags rough ground (terrain or a difficult surface)."""

from aidm.models.zones import Zone, ZoneSurface
from aidm.session.views import _public_zone


def test_grease_makes_a_zone_rough_while_the_terrain_flag_stays_false() -> None:
    zone = Zone(id="bridge", name="Bridge", surfaces=[ZoneSurface(kind="grease", rounds_left=2)])
    view = _public_zone(zone)
    assert view.rough is True
    assert view.difficult is False


def test_plain_and_terrain_zones_project_rough_from_the_effective_value() -> None:
    assert _public_zone(Zone(id="a", name="A")).rough is False
    assert _public_zone(Zone(id="b", name="B", difficult=True)).rough is True
    fire = Zone(id="c", name="C", surfaces=[ZoneSurface(kind="fire", rounds_left=1)])
    assert _public_zone(fire).rough is False
