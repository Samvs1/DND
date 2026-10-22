"""Substance weaknesses and the improvised throw through THE item interpreter (M27.6 part B)."""

from aidm.data.srd import srd
from aidm.models.combat_events import ZoneSurfaceAdded
from aidm.models.dice import RollKind
from aidm.models.encounter import Side
from aidm.models.events import AnyEvent, DiceRolled
from aidm.models.item_events import ItemUsed
from aidm.models.state import Creature, GameState
from aidm.rules.monster_stats import creature_from_monster
from aidm.rules.weaknesses import weak_to
from tests.unit.rules.combat_fixtures import ScriptedRng, monster
from tests.unit.rules.item_fixtures import DOCKS, gear_fight, hero, qty, refusal, run, use


def _elemental() -> Creature:
    return creature_from_monster(srd().monsters.get("fire-elemental"), "fe")


def _fight_with(target: Creature, *gear: str) -> GameState:
    return gear_fight(DOCKS, hero(gear=list(gear)), (target, Side.HOSTILE, "b"))


def _used(events: list[AnyEvent]) -> ItemUsed:
    return next(e for e in events if isinstance(e, ItemUsed))


def test_golden_water_on_fire_elemental() -> None:
    state = _fight_with(_elemental(), "waterskin")
    # d20 15 + STR 3 = 18 hits AC 13 (SRD 5.1 Fire Elemental). The waterskin is an improvised
    # weapon (SRD 5.1 Improvised Weapons): 1d4 rolls 2, + STR 3 = 5 bludgeoning, halved by the
    # elemental's resistance to nonmagical bludgeoning -> 2. SRD 5.1 Water Susceptibility: "for
    # every gallon of water splashed on it, it takes 1 cold damage" -> 1 cold (one container is
    # one gallon, docs/RULES_DECISIONS.md M27.6). 102 - 2 - 1 = 99.
    events = use(state, "waterskin", "fe", rng=ScriptedRng(15, 2))
    run(state, events)
    weak = [e for e in events if isinstance(e, DiceRolled) and e.label == "Water Susceptibility"]
    assert [(e.roll.total, e.kind) for e in weak] == [(1, RollKind.DAMAGE)]
    assert state.creatures["fe"].hp == 99
    assert _used(events).use_id == "improvised-throw"
    assert qty(state, "hero", "waterskin") == 0


def test_a_missed_splash_does_not_reach_the_weakness() -> None:
    state = _fight_with(_elemental(), "waterskin")
    events = use(state, "waterskin", "fe", rng=ScriptedRng(2))  # 2 + 3 = 5 misses AC 13
    run(state, events)
    assert state.creatures["fe"].hp == 102
    assert qty(state, "hero", "waterskin") == 0  # thrown all the same


def test_weak_to_reads_the_table_only() -> None:
    state = _fight_with(_elemental())
    assert [s for s, _ in weak_to(state, "fe", ("water", "fire"))] == ["water"]
    goblin = _fight_with(monster("gob"))
    assert weak_to(goblin, "gob", ("water",)) == []


def test_untagged_item_thrown_is_improvised_1d4_and_leaves_inventory() -> None:
    state = _fight_with(monster("gob", ac=12), "rope-hempen-50-feet")
    # SRD 5.1 Improvised Weapons: d20 10 + STR 3 = 13 hits AC 12; 1d4 rolls 2 + STR 3 = 5
    events = use(state, "rope-hempen-50-feet", "gob", rng=ScriptedRng(10, 2))
    run(state, events)
    assert _used(events).use_id == "improvised-throw"
    assert state.creatures["gob"].hp == 10 - 5
    assert qty(state, "hero", "rope-hempen-50-feet") == 0


def test_a_weapon_is_not_improvised_through_the_interpreter() -> None:
    state = _fight_with(monster("gob"), "dagger")
    assert "fight menu" in refusal(use(state, "dagger", "gob"))
    assert qty(state, "hero", "dagger") == 1


def test_oil_thrown_at_a_creature_splashes_its_zone() -> None:
    state = _fight_with(monster("gob"), "oil-flask")
    events = use(state, "oil-flask", "gob", rng=ScriptedRng())
    added = [e for e in events if isinstance(e, ZoneSurfaceAdded)]
    assert [(a.zone_id, a.surface.kind) for a in added] == [("b", "oil")]
