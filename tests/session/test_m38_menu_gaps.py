"""The menu gap closed in M38.2, played at a real table in menu mode (the chooser scripted with
FakeLLM by_tool, the log replayed equal): Fire Bolt at a person here goes through the
point-of-no-return card and, confirmed, is the fight's opening strike. M38.4 (cause B): so do a
save spell and Magic Missile."""

from pathlib import Path

from aidm.models.combat_events import AttackRolled, SpellCast
from aidm.models.encounter_events import EncounterStarted
from aidm.models.events import DamageTaken
from aidm.models.protocol_client import ConfirmHostile
from aidm.models.protocol_server import PendingConfirmationMsg
from tests.session.menu_play import MenuPlayed, menu_play
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


async def _strike(tmp_path: Path, spell: str, actor: str, text: str) -> MenuPlayed:
    return await menu_play(
        tmp_path,
        "r3-casters",
        288,
        pick((f"cast:{spell}", [RENN], None)),
        text=text,
        actor=actor,
        then=(ConfirmHostile(),),
    )


def _renn(played: MenuPlayed) -> str:
    (creature,) = (c for c in played.state.creatures.values() if c.npc_id == RENN)
    return creature.id


async def test_v1_m38_burning_hands_at_a_person_asks_then_opens_the_fight(
    tmp_path: Path,
) -> None:
    """M38.4 cause B, router record "I cast burning hands at Merre": a save spell at a person
    here asks first and, confirmed, is the fight's opening strike, aimed at the zone Renn
    stands in (an area hits whoever stands there)."""
    played = await _strike(tmp_path, "burning-hands", "pc-p2", "I cast burning hands at Old Renn")
    assert [m for m in played.msgs if isinstance(m, PendingConfirmationMsg)]
    assert played.of(EncounterStarted)
    (cast, *_) = played.of(SpellCast)
    assert (cast.caster_id, cast.spell_id, cast.at_scene) == ("pc-p2", "burning-hands", False)
    assert cast.target_zone is not None
    assert any(d.creature_id == _renn(played) for d in played.of(DamageTaken))


async def test_v1_m38_magic_missile_at_a_person_is_the_opening_strike(tmp_path: Path) -> None:
    """M38.4 cause B, router record "Brienne casts magic missile at the ferryman"."""
    played = await _strike(
        tmp_path, "magic-missile", "pc-p2", "Brienne casts magic missile at the ferryman"
    )
    assert played.of(EncounterStarted)
    (cast, *_) = played.of(SpellCast)
    assert (cast.caster_id, cast.spell_id) == ("pc-p2", "magic-missile")
    assert set(cast.target_ids) == {_renn(played)}
    assert any(d.creature_id == _renn(played) for d in played.of(DamageTaken))
    assert not [a for a in played.of(AttackRolled) if a.attacker_id == "pc-p2"]  # no weapon
