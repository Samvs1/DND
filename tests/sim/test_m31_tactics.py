"""M31.1f careful-table tactics of the campaign bots (pure, `scripts.sim.tactics`).

Foes are read from their SRD stat block (the token's `monster_index`), never from a name:
the mage (SRD 5.1, Fireball on its list with 3rd-level slots) and a young black dragon (Acid
Breath) are area threats, a wight resists necrotic and nonmagical bludgeoning, piercing and
slashing, a fire elemental is immune to fire, a skeleton is vulnerable to bludgeoning.
"""

import random

from scripts.sim.client import Msg
from scripts.sim.combat import Plan, choose_command
from scripts.sim.tactics import (
    attack_option,
    best_damage_spell,
    cantrip_for,
    resist_gear,
    spread_command,
    weapons_resisted,
)

ECO = {"action": True, "bonus_action": True, "movement_left": 30}


def _token(cid: str, side: str, zone: str, monster: str | None = None) -> Msg:
    return {
        "creature_id": cid,
        "side": side,
        "zone_id": zone,
        "hp": 10,
        "max_hp": 10,
        "dead": False,
        "monster_index": monster,
    }


def _combat(foe_zone: str, monster: str, *, ally_zone: str = "a") -> Msg:
    zones = [{"id": z, "surfaces": []} for z in ("a", "b", "c", "d")]
    edges = [{"a": "a", "b": "b"}, {"a": "a", "b": "c"}, {"a": "b", "b": "c"}, {"a": "c", "b": "d"}]
    tokens = [
        _token("pc-1", "party", "a"),
        _token("pc-2", "party", ally_zone),
        _token("m-1", "foes", foe_zone, monster),
    ]
    return {"tokens": tokens, "zones": zones, "edges": edges, "economy": dict(ECO)}


def _plan(role: str = "caster", cantrip: str | None = "fire-bolt") -> Plan:
    return Plan(role=role, hero_id="pc-1", rng=random.Random(1), cantrip=cantrip, smart=True)


def _foes(combat: Msg) -> list[Msg]:
    return [t for t in combat["tokens"] if t["side"] == "foes"]


def _attack(hand: str, damage: str, damage_type: str, band: str = "melee") -> Msg:
    return {"hand": hand, "damage": damage, "damage_type": damage_type, "range_band": band}


def _sheet(*attacks: Msg, cantrips: tuple[str, ...] = ()) -> Msg:
    casting = {"cantrips": [{"index": c} for c in cantrips], "levels": []}
    return {"attacks": list(attacks), "spellcasting": casting if cantrips else None}


FIGHTER = _sheet(
    _attack("main_hand", "1d8+3", "slashing"),
    _attack("ranged", "1d8+1", "piercing", "ranged"),
)


def test_m31_heroes_spread_out_against_an_area_blast() -> None:
    combat = _combat("c", "mage")
    plan = _plan()
    step = spread_command(plan, combat, _foes(combat), None)
    # b touches a and holds nobody; c holds the mage.
    assert step == {"type": "move", "actor_id": "pc-1", "zone_id": "b"}
    assert spread_command(plan, combat, _foes(combat), None) is None  # one step a turn
    dragon = _combat("d", "young-black-dragon")
    assert spread_command(_plan(), dragon, _foes(dragon), None) is not None


def test_m31_no_spread_without_a_blast_or_when_it_would_break_positioning() -> None:
    wight = _combat("c", "wight")
    assert spread_command(_plan(), wight, _foes(wight), None) is None  # no area: stay together
    engaged = _combat("a", "mage")
    assert spread_command(_plan(), engaged, _foes(engaged), None) is None  # melee stays put
    alone = _combat("c", "mage", ally_zone="d")
    assert spread_command(_plan(), alone, _foes(alone), None) is None  # nobody to spread from
    combat = _combat("c", "mage")
    melee_only = _sheet(_attack("main_hand", "1d8+3", "slashing"))
    fighter = _plan("fighter", None)
    assert spread_command(fighter, combat, _foes(combat), melee_only) is None
    assert spread_command(fighter, combat, _foes(combat), FIGHTER) is not None  # a crossbow


def test_m31_attack_prefers_the_damage_type_the_foe_takes_most() -> None:
    sheet = _sheet(
        _attack("main_hand", "1d6+3", "bludgeoning"),
        _attack("ranged", "1d8+1", "piercing", "ranged"),
    )
    chances = [
        {"option": "main_hand", "probability": 0.6, "in_range": True},
        {"option": "ranged", "probability": 0.7, "in_range": True},
    ]
    skeleton = _token("m-1", "foes", "a", "skeleton")
    assert attack_option(chances, sheet, skeleton) == "main_hand"  # 0.6 x 6.5 x 2 > 0.7 x 5.5
    goblin = _token("m-1", "foes", "a", "goblin")
    assert attack_option(chances, sheet, goblin) is None  # no defences: the best hit chance
    combat = _combat("a", "skeleton")
    cmd = choose_command(_plan("fighter", None), combat, chances, skeleton, option="main_hand")
    assert cmd["option"] == "main_hand"


def test_m31_casters_and_fighters_answer_resistance_with_spells() -> None:
    elemental = _token("m-1", "foes", "c", "fire-elemental")
    known = ("fire-bolt", "ray-of-frost", "acid-splash")
    caster_sheet = _sheet(cantrips=known)
    assert cantrip_for(_plan(), caster_sheet, elemental) == "ray-of-frost"
    goblin = _token("m-1", "foes", "c", "goblin")
    assert cantrip_for(_plan(), caster_sheet, goblin) is None
    wight = _token("m-1", "foes", "c", "wight")
    high_elf = _sheet(*FIGHTER["attacks"], cantrips=("fire-bolt",))
    assert weapons_resisted(high_elf, wight)
    assert cantrip_for(_plan("fighter", None), high_elf, wight) == "fire-bolt"
    assert cantrip_for(_plan("fighter", None), high_elf, goblin) is None
    assert best_damage_spell(["inflict-wounds", "guiding-bolt"], wight) == "guiding-bolt"
    assert best_damage_spell(["inflict-wounds", "guiding-bolt"], goblin) == "inflict-wounds"
    assert best_damage_spell(["scorching-ray"], elemental) is None  # immune: never picked


def test_m31_resisted_weapons_reach_for_carried_gear() -> None:
    combat = _combat("b", "wight")
    wight = _foes(combat)[0]
    holy = {"item": "holy-water-flask", "use_id": "holy-water-throw", "target": "creature"}
    cmd = resist_gear(_plan("fighter", None), combat, [holy], FIGHTER, wight)
    # Holy water 2d6 radiant (7) on an undead beats a longsword 1d8+3 halved (3.75).
    assert cmd == {
        "type": "use_item",
        "actor_id": "pc-1",
        "item": "holy-water-flask",
        "use_id": "holy-water-throw",
        "target_id": "m-1",
    }
    goblin_fight = _combat("b", "goblin")
    goblin = _foes(goblin_fight)[0]
    assert resist_gear(_plan("fighter", None), goblin_fight, [holy], FIGHTER, goblin) is None
