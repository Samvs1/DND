"""Typed fight lines read by the menu chooser at a real table (M36.6, SPEC 6.1, 6.2; round 6
Y10, Y11): the menu chooser, the chooser's pick scripted (FakeLLM by_tool), the
acts run through the button paths, every play replayed equal to the snapshot.
"""

from collections.abc import Sequence
from pathlib import Path

from aidm.dm.fake_llm import FakeRaise, fake_tool_call
from aidm.dm.llm_backend import BackendTimeout
from aidm.dm.llm_types import LlmMode
from aidm.models.combat_events import AttackRolled, CombatantMoved, FeatureUsed, SpellCast
from aidm.models.encounter_events import EconomyChanged, TurnEnded
from aidm.models.events import CheckResolved, ResourceSet
from aidm.models.item_events import ItemUsed, LightEnded
from aidm.models.protocol_server import ErrorMsg, NoticeKind
from aidm.models.state import GameState
from aidm.models.world_events import ActionDeclared
from aidm.session.fight_text import NOT_YOUR_TURN
from aidm.session.menu_pick import NOT_DONE, STOPPED
from tests.session.menu_play import TYPED, menu_play
from tests.session.table_fixtures import pick

KOBOLD, SWARM = "kobold-1", "swarm-of-rats-1"
KICK = {"actor": "pc-p2", "ability_or_skill": "athletics", "dc_tier": "easy", "reason": "kick"}
VAULT = "collapsed_vault"


def _hits(played_events: Sequence[object], attacker: str) -> list[AttackRolled]:
    return [e for e in played_events if isinstance(e, AttackRolled) and e.attacker_id == attacker]


async def test_v1_y10_menu_longsword_walks_then_strikes(tmp_path: Path) -> None:
    """typed 435 "I drive my longsword into the nearest kobold": the walk, then the longsword."""
    played = await menu_play(tmp_path, TYPED, 435, pick(("attack:longsword", [KOBOLD], None)))
    moved = [e for e in played.of(CombatantMoved) if e.creature_id == "pc-p2"]
    assert moved and moved[0].to_zone == VAULT
    swings = _hits(played.events, "pc-p2")
    assert swings and swings[0].target_id == KOBOLD and swings[0].attack == "Longsword"
    assert played.choose_calls() == 1
    assert len(played.of(ActionDeclared)) == 1


async def test_v1_y11_menu_arrow_in_its_chest_is_the_bow(tmp_path: Path) -> None:
    """typed 161 "I put an arrow in its chest" (a pronoun, one foe): the shortbow shot."""
    played = await menu_play(tmp_path, TYPED, 161, pick(("attack:shortbow", [SWARM], None)))
    shots = _hits(played.events, "pc-p4")
    assert shots and shots[0].target_id == SWARM and shots[0].attack == "Shortbow"
    assert not played.of(CheckResolved)


async def test_v1_y11_menu_bolt_of_fire_is_fire_bolt(tmp_path: Path) -> None:
    """typed 179 "Rook flings a bolt of fire at the swarm": Fire Bolt, never a creative action."""
    played = await menu_play(tmp_path, TYPED, 179, pick(("cast:fire-bolt", [SWARM], None)))
    casts = played.of(SpellCast)
    assert [(c.caster_id, c.spell_id) for c in casts] == [("pc-p6", "fire-bolt")]


async def test_v1_y11_menu_turn_undead_spends_channel_divinity(tmp_path: Path) -> None:
    """typed 1165 "raise my holy symbol and command the undead cantor to turn away"."""
    played = await menu_play(tmp_path, TYPED, 1165, pick(("feature:turn-undead", [], None)))
    used = [u for u in played.of(FeatureUsed) if u.creature_id == "pc-p8"]
    assert used and used[0].feature == "channel-divinity-turn-undead"
    assert any(r.creature_id == "pc-p8" for r in played.of(ResourceSet))


async def test_menu_fight_item_drinks_the_poultice(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path, TYPED, 435, pick(("item:herbal-poultice", ["pc-p2"], None)), text="poultice"
    )
    assert any(u.creature_id == "pc-p2" for u in played.of(ItemUsed))


async def test_menu_fight_move_then_dodge_then_end_turn(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path,
        TYPED,
        435,
        pick(("move", [VAULT], None), ("dodge", [], None), ("end-turn", [], None)),
        text="I run into the crypt, guard myself and wait",
    )
    moved = [e for e in played.of(CombatantMoved) if e.creature_id == "pc-p2"]
    assert moved[0].to_zone == VAULT
    assert any(e.creature_id == "pc-p2" for e in played.of(TurnEnded))
    assert any(e.creature_id == "pc-p2" for e in played.of(EconomyChanged))


async def test_menu_fight_surrender_demand_is_one_check(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path, TYPED, 435, pick(("surrender:intimidation", [], None)), text="Yield, vermin!"
    )
    checks = [c for c in played.of(CheckResolved) if c.creature_id == "pc-p2"]
    assert len(checks) == 1


async def test_menu_fight_other_is_the_creative_action(tmp_path: Path) -> None:
    """A stunt ruled with a mechanic (here a check) takes the action (DECISIONS M36.6)."""
    line = "I kick the brazier over onto the kobolds"
    check = fake_tool_call("request_check", KICK)
    played = await menu_play(tmp_path, TYPED, 435, pick(other=line), text=line, script=[check])
    assert [c.creature_id for c in played.of(CheckResolved)] == ["pc-p2"]
    spent = [e for e in played.of(EconomyChanged) if e.creature_id == "pc-p2"]
    assert spent and not spent[-1].economy.action  # a stunt takes the action (DECISIONS M36.6)
    assert [d.text for d in played.of(ActionDeclared)] == [line]


async def test_menu_fight_stunt_first_then_attack_meets_no_action_left(tmp_path: Path) -> None:
    """DECISIONS M36.6: the stunt takes the action; the attack after it is refused plainly."""
    line = "I kick the brazier over and stab the kobold"
    choice = pick(("attack:longsword", [KOBOLD], None), other="kick the brazier over", first=True)
    check = fake_tool_call("request_check", KICK)
    played = await menu_play(tmp_path, TYPED, 435, choice, text=line, script=[check])
    assert not _hits(played.events, "pc-p2")
    refusals = [m for m in played.msgs if isinstance(m, ErrorMsg)]
    assert refusals, played.notices()


async def test_menu_fight_refused_step_stops_the_rest(tmp_path: Path) -> None:
    def spent(state: GameState) -> None:
        enc = state.encounter
        assert enc is not None
        me = enc.combatants["pc-p2"]
        econ = me.economy.model_copy(update={"action": False})
        enc.combatants["pc-p2"] = me.model_copy(update={"economy": econ})

    played = await menu_play(
        tmp_path,
        TYPED,
        435,
        pick(("dodge", [], None), ("move", [VAULT], None)),
        text="I dodge and then run into the crypt",
        prep=spent,
    )
    assert STOPPED.format(why=NOT_DONE) in played.notices()
    assert not [e for e in played.of(CombatantMoved) if e.creature_id == "pc-p2"]


async def test_menu_fight_flee_ends_the_line_and_its_refusal_is_plain(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path, TYPED, 435, pick(("flee", [], None), ("dodge", [], None)), text="I run for it"
    )
    assert played.notices() == [  # M41.3: the dodge it cut off is told, never dropped
        "Enemies are in your zone: Disengage first, then flee.",
        STOPPED.format(why=NOT_DONE),
    ]
    assert not [e for e in played.of(EconomyChanged) if e.creature_id == "pc-p2"]


async def test_menu_fight_chooser_failure_keeps_the_turn(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path, TYPED, 435, FakeRaise(BackendTimeout()), text="I do something clever"
    )
    assert NoticeKind.FALLBACK in played.kinds()
    assert not played.of(ActionDeclared) and not played.of(TurnEnded)
    enc = played.state.encounter
    assert enc is not None and enc.active_id() == "pc-p2"
    assert enc.combatants["pc-p2"].economy.action


async def test_menu_fight_off_turn_line_makes_no_call(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path, TYPED, 435, text="I shoot the kobold", actor="pc-p4", also=("pc-p2",)
    )
    assert NOT_YOUR_TURN in played.notices()
    assert played.choose_calls() == 0 and not played.fake.requests
    assert not played.of(ActionDeclared)


async def test_menu_fight_off_turn_exact_free_entry_plays(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path,
        TYPED,
        435,
        text="Check what you carry",
        actor="pc-p4",
        mode=LlmMode.DISABLED,
        also=("pc-p2",),
    )
    assert any(" carries" in n for n in played.notices())
    assert not played.fake.requests and not played.of(ActionDeclared)


async def test_menu_fight_put_out_and_what_now_on_the_turn(tmp_path: Path) -> None:
    played = await menu_play(tmp_path, TYPED, 435, text="Put out your light", mode=LlmMode.DISABLED)
    assert any(e.creature_id == "pc-p2" for e in played.of(LightEnded))
    asked = await menu_play(tmp_path, TYPED, 435, text="What now?")
    assert asked.choose_calls() == 0 and not asked.of(ActionDeclared)
