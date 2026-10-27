"""M43.3 contract rule D1 (docs/next/M43_CONTRACT.md): the storyteller is told the turn's outcome in
plain words: what did not happen and why, and who did what. Real round-8 lines and events on
fixture m42-r8-typed (the r8-typed save, seq < 620); FakeLLM only, never the network. The asserts
read the prompt the storyteller receives, never model prose."""

from pathlib import Path

from aidm.dm.fake_llm import FakeLLM
from aidm.dm.narrator import narrate, narrate_round_segment
from aidm.models.impossible import ActionImpossible
from aidm.models.protocol_client import SubmitAction
from aidm.models.world_events import ActionDeclared
from scripts.contractlib.save import Finding
from scripts.contractlib.story_rules import TurnOutcomes
from tests.ai.chooser_fixtures import chooser_client, state_at
from tests.session.menu_play import menu_play
from tests.session.playtest_saves import events_of
from tests.session.table_fixtures import pick

R8 = "m42-r8-typed"
NO_SLOT = "Magic Missile: Rook has no 1st-level slot left"
NOTHING_CHANGED = "No rule applied and nothing in the world changed."


def _told(fake: FakeLLM) -> list[str]:
    """The storyteller's prompts (every call but the chooser's)."""
    return [
        "\n".join(str(m["content"]) for m in r.messages)
        for r in fake.requests
        if r.tool_choice != "choose_actions"
    ]


async def test_v1_m43_a_refused_cast_reaches_the_next_telling(tmp_path: Path) -> None:
    """round 8 AA3: r8-typed 261 "Rook casts magic missile at Bandit B" with no slot left; the
    storyteller then told the bandit killed (262). The refusal now reaches the next telling."""
    played = await menu_play(
        tmp_path,
        R8,
        261,
        pick(("cast:magic-missile", ["bandit-2"], None)),
        pick(other="Rook mutters a curse"),
        then=(SubmitAction(text="Rook mutters a curse"),),
    )
    assert [e.reason for e in played.of(ActionImpossible)] == [f"{NO_SLOT}."]
    tried = 'Rook tried "Rook casts magic missile at Bandit B"'
    line = f"{tried}: nothing happened, because {NO_SLOT}."
    assert any(line in prompt for prompt in _told(played.fake))


async def test_v1_m43_a_refused_payment_reaches_the_next_telling(tmp_path: Path) -> None:
    """round 8 AA6: r8-typed 52 "I pay the peddler 100 gold for a healing potion" (Elowen 20 gp)
    is refused with no telling of its own; the next line (55 "I look at what the peddler has for
    sale") is told with the reason, so its story cannot answer the 100-gold line (63)."""
    look = "I look at what the peddler has for sale"
    played = await menu_play(
        tmp_path,
        R8,
        52,
        pick(other="pay the peddler 100 gold"),
        pick(other=look),
        then=(SubmitAction(text=look),),
    )
    why = "nothing happened, because 100 gold: Elowen has only 20 gold."
    prompts = _told(played.fake)
    assert prompts and why in prompts[-1]
    assert played.state.memory.untold == []  # told once, then cleared by the narration


async def test_v1_m43_the_skiff_no_op_turn_is_told_nothing_changed(tmp_path: Path) -> None:
    """round 8 skiff: r8-typed 335 "Brienne ties the skiff to her pack and carries it" (Elowen
    holds it, 333) made no event; the telling (336) is told nothing changed. Not a refusal:
    the line names no thing of Brienne's, so it stays a stunt (B2)."""
    line = "Brienne ties the skiff to her pack and carries it"
    played = await menu_play(tmp_path, R8, 335, pick(other=line))
    assert not played.of(ActionImpossible)
    assert any(NOTHING_CHANGED in prompt for prompt in _told(played.fake))


async def test_v1_m43_whose_fire_burned_whom_reaches_the_telling(tmp_path: Path) -> None:
    """round 8 AA10 who-did-it: r8-typed 463-481 Rook's Burning Hands hurt Brienne, Elowen and
    Tamsin, the surprised rats did nothing; the telling at 482 had the rats bite the party."""
    state = state_at(R8, 482)
    segment = [e.event for e in events_of(R8) if 463 <= e.seq < 482]
    segment = [e for e in segment if not isinstance(e, ActionDeclared)]
    llm, fake = chooser_client(tmp_path)
    await narrate_round_segment(state, segment, llm).collect()
    prompt = _told(fake)[0]
    assert "Rook cast Burning Hands." in prompt
    for hero in ("Brienne", "Elowen", "Tamsin"):
        assert f"Rook dealt 6 fire damage to {hero}." in prompt
    assert "Giant Rat A dealt" not in prompt


async def test_v1_m43_a_logged_refusal_is_told_whatever_events_the_telling_gets(
    tmp_path: Path,
) -> None:
    """round 8 r8-typed 93-95: "I slide Brenn 300 gold ..." refused (94, Brienne 10 gp); the
    telling at 95 is built from the state even when it is handed no events."""
    state = state_at(R8, 95)
    assert [e.reason for e in state.memory.untold] == ["Brienne has only 10 gold."]
    llm, fake = chooser_client(tmp_path)
    await narrate(state, [], llm, actor_id="pc-p2").collect()
    assert "nothing happened, because Brienne has only 10 gold." in _told(fake)[0]


def test_v1_m43_the_d1_check_finds_a_refusal_the_prompt_does_not_carry() -> None:
    """The contract's D1 check on the real r8-typed 93-95 events: 0 findings with the builder;
    one when the refusal is not kept for the telling (the builder before M43.3)."""
    events = [e for e in events_of(R8) if 93 <= e.seq <= 95]
    for keep, expected in ((True, 0), (False, 1)):
        check, state = TurnOutcomes(), state_at(R8, 93).model_copy(deep=True)
        found: list[Finding] = []
        for entry in events:
            if entry.event.type == "narration_recorded" and not keep:
                state.memory.untold = []
            found += check.see(entry.seq, state, entry.event)
            if isinstance(entry.event, ActionImpossible):
                state.memory.untold = [*state.memory.untold, entry.event]
        assert len(found) == expected
