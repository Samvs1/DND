"""M35.2 round-6 Y4, Y6 and Y9 (docs/playtests/M34_round6.md) on the real round-6 states
(fixtures m35-r6-full, m35-r6-quests, m35-r6-typed; tests/session/playtest_saves.py)."""

import random
from pathlib import Path

from aidm.data.combat_data import combat_registries
from aidm.dm.intent_router import explore_intent, fight_intent
from aidm.models.campaign_events import OfferResolved
from aidm.models.campaign_state import OfferChoice
from aidm.models.combat_events import SpellCast
from aidm.models.commands import CastCommand
from aidm.models.encounter_events import EncounterStarted
from aidm.models.events import AnyEvent, LongRestTaken, ResourceSet
from aidm.models.quest_events import QuestStepDone
from aidm.models.world import QuestState
from aidm.rules.acts import OfferStrikeIntent
from aidm.rules.command_checks import CommandRefused
from aidm.rules.offer_answer import answer_offer
from aidm.rules.spells import scene_cast
from aidm.rules.waiting_foe import FOE_WAITS, cast_starts_fight, rest_ambush_events, waiting_foe
from aidm.session.offer_strike import WAITS
from aidm.session.quest_flow import settle_after
from aidm.session.reducer import apply
from aidm.session.rest_ambush import REST_AMBUSHED
from tests.session.m32_play import play
from tests.session.playtest_saves import replay_until
from tests.session.progression_fixtures import DATA, REGS, apply_all

FULL, QUESTS, TYPED = "m35-r6-full", "m35-r6-quests", "m35-r6-typed"
SLEEP = "I cast Sleep on the kobolds behind the spur"


async def test_v1_m35_long_rest_with_a_master_waiting_starts_the_fight(tmp_path: Path) -> None:
    """Y4, full 519-534: "we make camp and take a long rest" in front of Gorran Hookhand's
    waiting offer rested the party while he "had not moved". The rest is not taken: he takes the
    opening, the offer is answered as a fight and the party starts it surprised."""
    played = await play(tmp_path, FULL, 526)
    assert not played.of(LongRestTaken)
    resolved = played.of(OfferResolved)
    assert [(r.offer_id, r.choice) for r in resolved] == [("offer-519", OfferChoice.FIGHT)]
    started = played.of(EncounterStarted)
    assert started
    heroes = {"pc-p2", "pc-p4", "pc-p6", "pc-p8"}
    surprised = {c.creature_id for c in started[0].encounter.combatants.values() if c.surprised}
    assert surprised == heroes
    line = REST_AMBUSHED.format(foes="Gorran Hookhand")
    assert line in played.notices()
    assert played.state.camp_supplies == replay_until(FULL, 526).camp_supplies


def test_v1_m35_short_rest_with_a_foe_waiting_is_the_same_rule() -> None:
    """Y4: the rule is the engine's, for every rest path: no foe waiting, no ambush."""
    state = replay_until(FULL, 526)
    assert waiting_foe(state) is not None
    events = rest_ambush_events(state, DATA, random.Random(3))
    assert isinstance(events[0], OfferResolved) and events[0].choice is OfferChoice.FIGHT
    before = replay_until(FULL, 519)  # the vestry before the master's offer
    assert waiting_foe(before) is None
    assert rest_ambush_events(before, DATA, random.Random(3)) == []


def test_v1_m35_settled_master_never_ambushes_a_rest() -> None:
    """Y4: a master whose region is settled (quests 1099-1109, the offer still waiting for the
    answer) is no threat: the party may rest."""
    state = replay_until(QUESTS, 1100)
    campaign = state.campaign
    assert campaign is not None and campaign.offer is not None
    assert waiting_foe(state) is None


def test_v1_m35_clear_step_closes_when_its_region_is_settled() -> None:
    """Y6, quests 782 and 1092-1112: The Wailing Cage's "Win the fight at The Wailing Keep" could
    never close once Vesper was won over (alliance, 1099). The gateway's threat is over by any
    route, so the step is done and the side quest completes."""
    state = replay_until(QUESTS, 1113)
    quest = state.world.quests["the-wailing-cage"]
    assert (quest.state, quest.steps_done) == (QuestState.ACTIVE, 1)
    log: list[AnyEvent] = []
    settle_after(state, REGS, [], lambda events: apply_all(state, events, log))
    done = [e for e in log if isinstance(e, QuestStepDone) and e.quest_id == quest.id]
    assert [e.step for e in done] == [1]
    assert state.world.quests[quest.id].state is QuestState.COMPLETED


def test_v1_m35_hostile_spell_at_a_waiting_offer_is_never_cast_at_the_scene() -> None:
    """Y9, typed 378-380: Sleep at the waiting kobolds spent a slot "at the scene". The rules
    refuse such a scene cast before any event; a spell that harms no one still may be."""
    state = replay_until(TYPED, 378)
    regs = combat_registries()
    sleep = regs.spells.get("sleep")
    assert cast_starts_fight(state, sleep)
    try:
        scene_cast(state, "pc-p6", sleep, regs)
    except CommandRefused as refused:
        assert refused.reason == FOE_WAITS
    else:
        raise AssertionError("Sleep was cast at the scene with the kobolds waiting")
    assert not cast_starts_fight(state, regs.spells.get("mage-armor"))
    assert not cast_starts_fight(replay_until(TYPED, 360), sleep)  # before the offer


async def test_v1_m35_sleep_at_a_waiting_offer_starts_the_fight(tmp_path: Path) -> None:
    """Y9: the typed cast answers the offer as Fight, no slot is spent at the scene, and the
    words wait for Rook's turn."""
    played = await play(tmp_path, TYPED, 378)
    assert [r.choice for r in played.of(OfferResolved)] == [OfferChoice.FIGHT]
    assert played.of(EncounterStarted)
    assert not [e for e in played.of(SpellCast) if e.at_scene]
    start = played.events.index(played.of(EncounterStarted)[0])
    spent = [
        e
        for e in played.events[:start]
        if isinstance(e, ResourceSet) and e.key.startswith("spell-slot")
    ]
    assert spent == []
    assert WAITS.format(name="Rook") in played.notices()


def test_v1_m35_sleep_named_at_one_foe_is_a_strike() -> None:
    """Y9: Sleep (an HP pool, no save or damage) aimed at a foe of the offer is a strike too."""
    state = replay_until(TYPED, 378)
    assert explore_intent(state, "pc-p6", "I cast Sleep on the kobold") == OfferStrikeIntent(
        "pc-p6"
    )


def test_v1_m35_sleep_waits_as_a_cast_at_the_kobolds() -> None:
    """Y9: on Rook's turn the same words are the hotbar's cast at the kobolds' zone."""
    state = replay_until(TYPED, 378)
    for event in answer_offer(state, OfferChoice.FIGHT, DATA, random.Random(1), actor_id="pc-p6"):
        apply(state, event)
    command = fight_intent(state, "pc-p6", SLEEP)
    assert isinstance(command, CastCommand) and command.spell_id == "sleep"
    enc = state.encounter
    assert enc is not None
    kobolds = {c.zone_id for c in enc.combatants.values() if c.creature_id.startswith("kobold")}
    assert command.target_zone in kobolds
