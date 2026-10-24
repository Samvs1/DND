"""M29.7d round-2 rules and data: charms the party's harm ends (R20), level-up slots (R27), shop
wording and sub-gold prices (R6). Evidence from the round-2 saves (tests/fixtures/saves/m29-r2-*).
"""

from __future__ import annotations

import random

import pytest

from aidm.data.character_data import character_registries
from aidm.data.spell_defs import ApplyConditionEffect, SaveEffect
from aidm.models.commands import CastCommand, RefusalCode
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.encounter import EncounterStatus, Side
from aidm.models.events import (
    ConditionRemoved,
    CreatureAdded,
    DamageTaken,
    InventoryChanged,
    LevelGained,
    ResourceSet,
)
from aidm.models.state import GameState
from aidm.rules.attacks import deal_damage
from aidm.rules.command_checks import CommandRefused
from aidm.rules.condition_timing import apply_condition, new_condition
from aidm.rules.creation import build_character
from aidm.rules.encounter import encounter_outcome, kill_xp
from aidm.rules.harm_ends import harm_ended_events
from aidm.rules.leveling import gain_xp, level_up
from aidm.rules.shop import ShopRefusal, ShopRefused, bulk_note, buy_price, sell_events, shop_stock
from aidm.session.reducer import apply
from tests.session.playtest_saves import events_of, replay_until
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng, do, fight
from tests.unit.rules.creation_fixtures import default_choices
from tests.unit.rules.economy_fixtures import CAT, TABLE, apply_events, shop_state
from tests.unit.rules.encounter_fixtures import make_pc
from tests.unit.rules.leveling_fixtures import script_choices
from tests.unit.rules.monster_fixtures import srd_monster
from tests.unit.rules.spell_fixtures import caster, conditions_of

CHARS = character_registries()
FEATS = CHARS.features


def _befriended_wolf(*extra: str) -> GameState:
    ranger = caster("r", "ranger", spells=["animal-friendship"], level=2, slots={1: 2})
    placements = [
        (ranger, Side.PARTY, "gate"),
        (make_pc("ally"), Side.PARTY, "yard"),
        (srd_monster("wolf", "wolf-1"), Side.HOSTILE, "yard"),
        *((srd_monster("goblin", g), Side.HOSTILE, "wall") for g in extra),
    ]
    state = fight(placements)
    cmd = CastCommand(actor_id="r", spell_id="animal-friendship", target_ids=("wolf-1",))
    do(state, cmd, ScriptedRng(5))
    assert conditions_of(state, "wolf-1") == ["befriended"]
    return state


def test_m29_animal_friendship_ends_when_the_party_harms_the_beast() -> None:
    # SRD 5.1 Animal Friendship: "If you or one of your companions harms the target, the spell
    # ends." p4 1374-1378: a longbow hit left the charm in place.
    state = _befriended_wolf()
    arrow = DamagePacket(amount=9, damage_type=DamageType.PIERCING)
    events = deal_damage(ScriptedRng(10), state, "ally", "wolf-1", [arrow], crit=False, feats=FEATS)
    for event in events:
        apply(state, event)
    ended = [e for e in events if isinstance(e, ConditionRemoved)]
    assert [(e.name, e.source_id) for e in ended] == [("befriended", "r")]
    assert conditions_of(state, "wolf-1") == []


def test_m29_harm_from_the_other_side_keeps_the_charm() -> None:
    state = _befriended_wolf("goblin-1")
    bite = DamageTaken(creature_id="wolf-1", parts=(), total=4, hp_lost=4, source_id="goblin-1")
    assert harm_ended_events(state, bite) == []
    own = bite.model_copy(update={"source_id": "r"})
    assert len(harm_ended_events(state, own)) == 1


def test_m29_charm_person_ends_on_harm_too() -> None:
    # SRD 5.1 Charm Person: "until the spell ends or until you or your companions do anything
    # harmful to it". The two shipped spells with that clause use "befriended".
    for spell in ("animal-friendship", "charm-person"):
        saves = [e for e in REGS.spells.get(spell).effects if isinstance(e, SaveEffect)]
        applied = [e for e in saves[0].on_fail if isinstance(e, ApplyConditionEffect)]
        assert [e.condition for e in applied] == ["befriended"], spell


def test_m29_animal_friendship_needs_a_beast() -> None:
    # p4 1355: the death dog (an SRD monstrosity) was charmed by Animal Friendship ("a beast").
    state = replay_until("r2-p4", 1352)  # Rook's turn, the action still free
    cmd = CastCommand(actor_id="pc-p6", spell_id="animal-friendship", target_ids=("death-dog-1",))
    with pytest.raises(CommandRefused) as refused:
        do(state, cmd, ScriptedRng(5))
    assert refused.value.code is RefusalCode.INVALID_TARGET


def test_m29_a_fight_with_only_befriended_foes_left_ends() -> None:
    mixed = _befriended_wolf("goblin-1")
    assert encounter_outcome(mixed) is None
    state = _befriended_wolf()
    assert encounter_outcome(state) is EncounterStatus.VICTORY
    assert kill_xp(state) == 0  # befriended is not defeated


def test_m29_charm_immunity_covers_befriended() -> None:
    wolf = srd_monster("wolf", "wolf-1")
    wolf.condition_immunities.append("charmed")
    assert apply_condition(wolf, new_condition("befriended", source_id="r")) == []


def test_m29_level_up_adds_new_slots_and_keeps_spent_ones() -> None:
    # SRD 5.1 Spellcasting: a level gives the new slots; used ones come back on a long rest only.
    pc = build_character(default_choices("wizard", "elf", "high-elf"), CHARS, "wiz")
    state = apply(GameState(campaign_id="c", seed=1), CreatureAdded(creature=pc))
    pool = state.creatures["wiz"].resources["spell-slot-1"]
    empty = pool.model_copy(update={"current": 0})
    apply(state, ResourceSet(creature_id="wiz", key="spell-slot-1", resource=empty))
    for event in gain_xp(state.creatures["wiz"], 300):
        apply(state, event)
    wizard = state.creatures["wiz"]
    for event in level_up(wizard, script_choices(wizard, CHARS), CHARS):
        apply(state, event)
    after = state.creatures["wiz"].resources["spell-slot-1"]
    assert (after.current, after.maximum) == (1, 3)


def test_m29_round_two_level_ups_never_refilled_slots() -> None:
    # R27: p4 210 set slot 1 to 2/2 for a ranger, whose first slots come at level 2; p8's wizard
    # cast four level-1 spells on three slots because Arcane Recovery gave one back (p8 486-488).
    for run in ("r2-p4", "r2-p8"):
        pools: dict[tuple[str, str], tuple[int, int]] = {}
        leveled: set[str] = set()
        for logged in events_of(run):
            event = logged.event
            if isinstance(event, LevelGained):
                leveled.add(event.creature_id)
            if isinstance(event, ResourceSet) and event.key.startswith("spell-slot"):
                key = (event.creature_id, event.key)
                cur, top = event.resource.current, event.resource.maximum
                if event.creature_id in leveled and key in pools:
                    old_cur, old_top = pools[key]
                    assert cur - old_cur <= top - old_top, (run, logged.seq)
                pools[key] = (cur, top)
                leveled.discard(event.creature_id)


def test_m29_sale_refusal_says_the_true_rule() -> None:
    # p5 720-726, p7 55: a 1 gp hammer was refused as "not worth buying".
    state = shop_state()
    apply_events(state, [InventoryChanged(creature_id="fighter", item="hammer", delta=1, qty=1)])
    with pytest.raises(ShopRefused) as refused:
        sell_events(state, "fighter", "npc-mira", "hammer", 1, CAT, TABLE)
    assert refused.value.reason is ShopRefusal.WORTHLESS
    assert "half an item's value in whole gold" in refused.value.detail
    assert "Hammer (worth 1 gp)" in refused.value.detail
    assert "not worth" not in refused.value.detail


def test_m29_sub_gold_prices_are_shown_as_charged() -> None:
    # p8 703-711 (G28): ten camp rations listed at 1 gp each cost 5 gp in all.
    ration = CAT.get("camp-ration")
    assert (buy_price(ration.value_gp, 1, TABLE), buy_price(ration.value_gp, 10, TABLE)) == (1, 5)
    assert bulk_note(0.5) == "2 for 1 gp" and bulk_note(0.4) == "5 for 2 gp"
    assert (
        bulk_note(0.01) == "100 for 1 gp"
        and bulk_note(1.0) == ""
        and bulk_note(2.5) == "2 for 5 gp"
    )
    assert bulk_note(1.5) == "2 for 3 gp"  # M31.1e: the Hearty Meal Basket
    stock = shop_stock(CAT, TABLE, "general", 1, random.Random(1))
    line = next(e for e in stock if e.item == "camp-ration")
    assert (line.price_gp, line.unit_gp, line.bulk) == (1, 0.5, "2 for 1 gp")
