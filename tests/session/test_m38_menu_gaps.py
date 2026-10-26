"""The menu gap closed in M38.2, played at a real table in menu mode (the chooser scripted with
FakeLLM by_tool, the log replayed equal): Fire Bolt at a person here goes through the
point-of-no-return card and, confirmed, is the fight's opening strike."""

from pathlib import Path

from aidm.models.combat_events import AttackRolled, SpellCast
from aidm.models.encounter_events import EncounterStarted
from aidm.models.protocol_client import ConfirmHostile
from aidm.models.protocol_server import PendingConfirmationMsg
from tests.session.menu_play import menu_play
from tests.session.table_fixtures import pick

RENN = "old-renn-pitwater"


async def test_v1_m38_menu_fire_bolt_at_a_person_asks_then_opens_the_fight(
    tmp_path: Path,
) -> None:
    """Router record "I cast fire bolt at Tobin" (the r3 ferry: Old Renn stands by)."""
    played = await menu_play(
        tmp_path,
        "r3-casters",
        288,
        pick(("cast:fire-bolt", [RENN], None)),
        text="I cast fire bolt at Old Renn",
        actor="pc-p2",
        then=(ConfirmHostile(),),
    )
    assert [m for m in played.msgs if isinstance(m, PendingConfirmationMsg)]
    assert played.of(EncounterStarted)
    cast = [(e.caster_id, e.spell_id) for e in played.of(SpellCast)]
    assert cast[:1] == [("pc-p2", "fire-bolt")]
    assert [a.attacker_id for a in played.of(AttackRolled)][:1] == ["pc-p2"]


async def test_menu_fire_bolt_named_at_no_one_is_the_scene_cast(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path,
        "r3-casters",
        288,
        pick(("cast:fire-bolt", [], None)),
        text="I cast fire bolt at the crates",
        actor="pc-p2",
    )
    assert not played.of(EncounterStarted)
    assert [(e.spell_id, e.at_scene) for e in played.of(SpellCast)] == [("fire-bolt", True)]
