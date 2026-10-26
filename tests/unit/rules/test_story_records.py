"""Story records are past records (M40.4): the reducer's stamps and change marks, the ONE rule
that shows a record dated or leaves it out (`rules.story_records`), and the write-time claim
check (`rules.story_claims`)."""

from aidm.models.events import CreatureAdded, CreatureDied, HpChanged, InventoryChanged
from aidm.models.item_events import HandedOver
from aidm.models.memory import SceneSummary
from aidm.models.quest_events import QuestAsked
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.models.story import StoryStamp
from aidm.models.world import Fact, Quest, QuestAsk, QuestState, WorldNpc
from aidm.models.world_events import (
    FactRecorded,
    NarrationRecorded,
    NodeDescribed,
    NpcIntroduced,
    PartyMoved,
    QuestUpdated,
    SceneSummarised,
)
from aidm.rules.story_claims import ClaimKind, claim_kinds, unsupported_claims
from aidm.rules.story_records import (
    dated_facts,
    description_shown,
    fact_record,
    live_facts,
    narration_records,
    superseded,
    when_label,
)
from aidm.session.reducer import apply, replay
from tests.unit.rules.encounter_fixtures import make_pc, party_state

FENN = "fenn"
LIES = "Brienne gave Rook two torches; her offers of three gold were not taken up."


def _state() -> GameState:
    brienne, rook = make_pc("pc-b"), make_pc("pc-r")
    brienne.name, rook.name = "Brienne", "Rook"
    state = party_state(brienne, rook)
    state.world.current_node = FENN
    state.world.neighbours = {FENN: ["mill"], "mill": [FENN]}
    return state


def _stirge(cid: str) -> Creature:
    return Creature(id=cid, name=f"Stirge {cid[-1]}", kind=CreatureKind.MONSTER, max_hp=5, hp=5)


def _fact(state: GameState, text: str, *ids: str) -> Fact:
    apply(
        state,
        FactRecorded(fact=Fact(id=f"fact-{len(state.world.facts) + 1}", text=text, entity_ids=ids)),
    )
    return state.world.facts[-1]


def test_the_reducer_stamps_records_when_their_event_is_applied() -> None:
    state = _state()
    seq = state.event_count
    fact = _fact(state, "The mill wheel is still.", FENN)
    apply(state, NarrationRecorded(text="The wheel creaks.", scene_turn=1))
    apply(state, NodeDescribed(node_id=FENN, text="Reeds and black water."))
    apply(state, SceneSummarised(summary=SceneSummary(text="The party waited.")))
    assert fact.made == StoryStamp(seq=seq, scene=0)
    assert state.memory.narration_made == [StoryStamp(seq=seq + 1, scene=0)]
    assert state.world.described[FENN] == StoryStamp(seq=seq + 2, scene=0)
    summary = state.memory.summaries[-1]
    assert summary.made == StoryStamp(seq=seq + 3, scene=0)


def test_stamps_and_marks_are_replay_safe() -> None:
    initial = _state()
    events = [
        CreatureAdded(creature=_stirge("st-1")),
        FactRecorded(fact=Fact(id="fact-1", text="A stirge hovers.", entity_ids=(FENN,))),
        HpChanged(creature_id="st-1", delta=-5, new_hp=0),
        CreatureDied(creature_id="st-1"),
    ]
    live = initial.model_copy(deep=True)
    for event in events:
        apply(live, event)
    assert replay(initial, events) == live
    assert live.world.changed["status:st-1"] == initial.event_count + 3
    assert live.world.changed["kill:name:stirge"] == initial.event_count + 3


def test_a_fact_naming_a_creature_that_died_since_is_left_out() -> None:
    state = _state()
    for cid in ("st-1", "st-2"):
        apply(state, CreatureAdded(creature=_stirge(cid)))
    hover = _fact(state, "Two stirges hover before the party; no blow struck.", FENN)
    apply(state, CreatureDied(creature_id="st-1"))
    later = _fact(state, "One stirge fell to Rook's blade.", "pc-r")
    assert superseded(state, fact_record(hover)) and not superseded(state, fact_record(later))
    assert [f.id for f in live_facts(state)] == [later.id]
    assert dated_facts(state, [hover, later]) == [f"Earlier this scene: {later.text}"]


def test_heroes_going_down_do_not_supersede_but_their_death_does() -> None:
    state = _state()
    fact = _fact(state, "Rook guards the door.", "pc-r")
    apply(state, HpChanged(creature_id="pc-r", delta=-50, new_hp=0))
    assert not superseded(state, fact_record(fact))
    apply(state, CreatureDied(creature_id="pc-r"))
    assert superseded(state, fact_record(fact))


def test_an_offer_note_is_superseded_when_the_givers_quest_changes() -> None:
    state = _state()
    npc = WorldNpc(id="sable", name="Sable Marowe", archetype_id="commoner", node_id=FENN)
    apply(state, NpcIntroduced(npc=npc))
    quest = Quest(id="q-relic", title="The Relic", giver_npc_id="sable")
    apply(state, QuestUpdated(quest=quest.model_copy(update={"state": QuestState.OFFERED})))
    apply(state, QuestAsked(ask=QuestAsk(quest_id="q-relic", npc_id="sable", node_id=FENN)))
    pending = _fact(state, "The party has not yet accepted Sable Marowe's request.", "sable")
    other = _fact(state, "Sable Marowe keeps a lamp lit.", "sable")
    apply(state, QuestUpdated(quest=quest))
    assert superseded(state, fact_record(pending))
    assert not superseded(state, fact_record(other))


def test_dates_say_this_scene_an_earlier_scene_or_earlier() -> None:
    state = _state()
    assert when_label(state, 0) == "Earlier this scene"
    apply(state, PartyMoved(from_node=FENN, to_node="mill", scene_index=3))
    assert when_label(state, 0) == "Earlier, scene 0" and when_label(state, None) == "Earlier"


def test_narration_stamps_line_up_from_the_end() -> None:
    state = _state()
    state.memory.narration = ["unstamped"]
    apply(state, NarrationRecorded(text="stamped", scene_turn=1))
    records = narration_records(state)
    assert [r.made is None for r in records] == [True, False]


def test_a_place_description_naming_a_dead_foe_is_left_out() -> None:
    state = _state()
    apply(state, CreatureAdded(creature=_stirge("st-1")))
    apply(state, NodeDescribed(node_id=FENN, text="A stirge clings to the torches on the wall."))
    apply(state, InventoryChanged(creature_id="pc-b", item="torch", delta=1, qty=1))
    assert description_shown(state, FENN).startswith("A stirge")  # a pack is not the place
    apply(state, CreatureDied(creature_id="st-1"))
    assert description_shown(state, FENN) == ""


def test_claim_kinds_are_classified_by_their_verbs_only() -> None:
    assert claim_kinds(LIES) == {ClaimKind.HANDOVER, ClaimKind.REFUSAL, ClaimKind.OFFER}
    assert claim_kinds("Cofferlight Sink lies half drowned.") == frozenset()


def test_a_claimed_deed_needs_an_engine_event_on_a_thing_it_names() -> None:
    state = _state()
    apply(state, HandedOver(creature_id="pc-b", to_id="pc-r", item="torch", qty=2))
    ids = ("pc-b", "pc-r")
    assert unsupported_claims(state, LIES, ids) == (ClaimKind.REFUSAL,)
    assert unsupported_claims(state, "Brienne gave Rook two torches.", ids) == ()
    assert unsupported_claims(state, "Brienne killed Rook.", ids) == (ClaimKind.KILL,)
    assert unsupported_claims(state, "Bandits once slew a miller here.", (FENN,)) == ()
    later = state.event_count + 1
    assert unsupported_claims(state, "Brienne gave Rook two torches.", ids, since=later) == (
        ClaimKind.HANDOVER,
    )
