"""M29.5c the honest storyteller: kills, wounds, blows and weapons (docs/playtests/M29_round1.md
G6 G7 G21 G32). Each test replays a live round 1 save to the narration the model wrote and shows
THE guard rejects it, the narrator's facts carry the truth (the weapon, who still stands, who is
unhurt), and a repeated false claim ends in the engine template (FakeLLM only)."""

from pathlib import Path

from aidm.dm.event_text import event_line
from aidm.dm.fake_llm import fake_text
from aidm.dm.guard import prose_checker
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_types import ViolationKind
from aidm.dm.narrator import narrate_round_segment
from aidm.dm.turn_facts import turn_facts
from aidm.models.combat_events import AttackRolled
from tests.ai.fake_scripts import fake_client
from tests.session.playtest_saves import ToldTurn, logged, replay_until, told_turn


def _kinds(turn: ToldTurn, text: str | None = None) -> set[ViolationKind]:
    check = prose_checker(
        turn.state, turn.events, actor_id=turn.actor_id, player_text=turn.player_text
    )
    return {v.kind for v in check(text if text is not None else turn.prose).violations}


def _facts(turn: ToldTurn) -> str:
    return " ".join(turn_facts(turn.state, turn.events))


def _hp(turn: ToldTurn, name: str) -> int:
    return next(c.hp for c in turn.state.creatures.values() if c.name == name and not c.dead)


async def test_m29_foe_told_still_while_standing(tmp_path: Path) -> None:
    """G21 (p2 96): the zombie "drops face-first onto the stones and lies still" at 3 of 22 HP."""
    turn = told_turn("p2", 96)
    assert _hp(turn, "Zombie") == 3
    assert ViolationKind.UNHURT_DECLARED_DOWN in _kinds(turn)
    assert "Hurt but still standing and fighting" in _facts(turn) and "Zombie" in _facts(turn)
    client, fake = fake_client(tmp_path, [fake_text(turn.prose), fake_text(turn.prose)])
    stream = narrate_round_segment(turn.state, list(turn.events), client)
    text = await stream.collect()
    assert stream.source is not NarrationSource.MODEL and "lies still" not in text
    assert len(fake.requests) == 2 and "ENGINE GUARD" in str(fake.requests[1].messages[-1])
    facts = str(fake.requests[0].messages[-1]["content"])
    assert "Hurt but still standing" in facts and "Weapons of these attacks" in facts


def test_m29_pronoun_kill_of_a_standing_thug() -> None:
    """G21 (p2 206): "then he pitches sideways into the weeds and lies still": the thug was at 8
    HP; the pronoun is resolved to him."""
    turn = told_turn("p2", 206)
    assert _hp(turn, "Thug") == 8
    assert ViolationKind.UNHURT_DECLARED_DOWN in _kinds(turn)
    dead = told_turn("p2", 532)  # bandit-3 really died: "he folds" about him is clean
    assert ViolationKind.UNHURT_DECLARED_DOWN not in _kinds(
        dead, "Elowen's arrow takes the bandit between the ribs, and he folds without a word."
    )
    assert "Foes still standing in this fight" in _facts(dead) and "bandit" in _facts(dead)


def test_m29_wrong_weapon_is_flagged_and_the_line_names_it() -> None:
    """G7 (p2 206, 532): Brienne shot a light crossbow ("Brienne's sword bites deep"), Elowen a
    longbow ("Elowen's shortsword slides"); the engine line never named the weapon."""
    turn = told_turn("p2", 206)
    assert ViolationKind.WRONG_WEAPON in _kinds(turn)
    attack = next(e for e in turn.events if isinstance(e, AttackRolled))
    assert attack.attack == "Crossbow, light"
    line = event_line(turn.state, attack) or ""
    assert "with a light crossbow" in line
    assert "Brienne: light crossbow" in _facts(turn)
    honest = "Brienne's bolt bites deep behind the thug's guard, and he staggers."
    assert ViolationKind.WRONG_WEAPON not in _kinds(turn, honest)
    assert ViolationKind.WRONG_WEAPON in _kinds(told_turn("p2", 532))
    arm = "The thug's club finds Brienne's sword arm."  # a body part, not a weapon claim
    assert ViolationKind.WRONG_WEAPON not in _kinds(turn, arm)


def test_m29_rat_bites_on_unhurt_heroes() -> None:
    """G32 (p3 151): "where the rat-bites mark them" about Brienne and Elowen at full HP."""
    turn = told_turn("p3", 151)
    hurt = {c.name: c.hp < c.max_hp for c in turn.state.creatures.values() if c.pc is not None}
    assert hurt["Brienne"] is False and hurt["Elowen"] is False
    assert ViolationKind.UNHURT_WOUNDED in _kinds(turn)
    assert "Unhurt (no wound, bite or blood on them)" in _facts(turn)
    assert ViolationKind.UNHURT_WOUNDED not in _kinds(turn, "Brienne shows no wound at all.")


def test_m29_blows_before_any_roll() -> None:
    """G32/G6 (p3 495): the fight against the lizardfolk had just begun (no attack rolled), yet
    the model told it lunging, gouging Elowen and falling still at 22 of 22 HP (p1 59: a wolf
    "springs at Rook" before any roll is the same class)."""
    turn = told_turn("p3", 495)
    assert not any(isinstance(e, AttackRolled) for e in turn.events)
    kinds = _kinds(turn)
    assert ViolationKind.UNRESOLVED_BLOW in kinds and ViolationKind.UNHURT_DECLARED_DOWN in kinds
    assert "No attack was rolled in these events" in _facts(turn)
    standoff = "The lizardfolk hisses and shifts its weight, ready to lunge at Elowen."
    assert ViolationKind.UNRESOLVED_BLOW not in _kinds(turn, standoff)
    assert ViolationKind.UNRESOLVED_BLOW not in _kinds(turn, "No one has struck yet.")


def test_m29_real_kill_stays_clean() -> None:
    """A creature the events killed may be told as fallen (p2 529: bandit-3 died)."""
    assert logged("p2", 529).event.type == "creature_died"
    turn = told_turn("p2", 532)
    assert "bandit-3" not in {c.id for c in turn.state.creatures.values() if not c.dead}
    clean = "Elowen's arrow drops the bandit, and he lies still in the frost."
    assert ViolationKind.UNHURT_DECLARED_DOWN not in _kinds(turn, clean)
    assert replay_until("p2", 529).creatures["bandit-3"].hp == 0
