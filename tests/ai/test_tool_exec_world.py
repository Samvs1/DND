"""World tool executors: attitude, secrets, travel, NPC/feature creation, shop, quests, facts."""

from aidm.models.world import NpcSecret, QuestState
from aidm.models.world_events import (
    FactRecorded,
    FeatureIntroduced,
    NpcIntroduced,
    PartyMoved,
    QuestUpdated,
    SecretRevealed,
    ShopOpened,
)
from aidm.rules.social import ALLY_BAR, SOCIAL_CAP, attitude_score
from aidm.session.reducer import replay
from tests.ai.tool_fixtures import add_npc, apply_result, party_state, run_tool


def test_update_attitude_bounded_and_applied() -> None:
    state = party_state()
    add_npc(state)
    for _ in range(10):
        result = run_tool(state, "update_attitude", npc="npc-mira", delta_tier="improve_major")
        assert result.error is None
        apply_result(state, result)
    assert attitude_score(state.world.npcs["npc-mira"]) == SOCIAL_CAP < ALLY_BAR
    assert (
        "friendly"
        in run_tool(state, "update_attitude", npc="npc-mira", delta_tier="improve").summary
    )


def test_update_attitude_unknown_or_absent_npc() -> None:
    state = party_state()
    assert run_tool(state, "update_attitude", npc="npc-x", delta_tier="worsen").error
    add_npc(state, node_id="forest")
    absent = run_tool(state, "update_attitude", npc="npc-mira", delta_tier="worsen")
    assert absent.error is not None and "not here" in absent.error


def test_reveal_secret_requires_condition() -> None:
    state = party_state()
    secret = NpcSecret(id="s1", text="The mayor hides the key.", min_score=20)
    add_npc(state, secrets=(secret,))
    refused = run_tool(state, "reveal_secret", npc="npc-mira", secret_id="s1")
    assert refused.error is not None and refused.events == ()
    for _ in range(2):
        apply_result(
            state, run_tool(state, "update_attitude", npc="npc-mira", delta_tier="improve_major")
        )
    revealed = run_tool(state, "reveal_secret", npc="npc-mira", secret_id="s1")
    assert isinstance(revealed.events[0], SecretRevealed)
    apply_result(state, revealed)
    assert state.world.npcs["npc-mira"].secrets[0].revealed
    assert run_tool(state, "reveal_secret", npc="npc-mira", secret_id="s1").error


def test_move_party_only_to_unlocked_neighbours() -> None:
    state = party_state()
    bad = run_tool(state, "move_party", node_id="castle")
    assert bad.error is not None and "legal exits: forest" in bad.error
    assert "crypt" not in bad.error  # locked exits are not offered
    locked = run_tool(state, "move_party", node_id="crypt")
    assert locked.error is not None and locked.events == ()
    ok = run_tool(state, "move_party", node_id="forest")
    assert isinstance(ok.events[0], PartyMoved) and ok.events[0].scene_index == 1
    apply_result(state, ok)
    assert state.world.current_node == "forest" and state.world.visited == ["town", "forest"]


def test_introduce_npc_catalogue_and_scene_cap() -> None:
    state = party_state()
    bad = run_tool(state, "introduce_npc", name="Zed", role="king", archetype_id="god-emperor")
    assert bad.error is not None and bad.events == ()
    for name in ("Ana", "Bo", "Cy"):
        result = run_tool(state, "introduce_npc", name=name, role="guard", archetype_id="guard")
        assert isinstance(result.events[0], NpcIntroduced)
        apply_result(state, result)
    assert "npc-ana" in state.world.npcs
    capped = run_tool(state, "introduce_npc", name="Di", role="guard", archetype_id="guard")
    assert capped.error is not None and "most new NPCs" in capped.error
    apply_result(state, run_tool(state, "move_party", node_id="forest"))
    assert run_tool(state, "introduce_npc", name="Di", role="hermit", archetype_id="commoner").ok


def test_introduce_npc_duplicate_name_refused() -> None:
    state = party_state()
    add_npc(state)
    dup = run_tool(state, "introduce_npc", name="mira", role="twin", archetype_id="commoner")
    assert dup.error is not None and "already exists" in dup.error
    pc = run_tool(state, "introduce_npc", name="Fighter", role="x", archetype_id="commoner")
    assert pc.error is not None


def test_introduce_feature_hidden_gets_engine_dc() -> None:
    state = party_state()
    result = run_tool(
        state,
        "introduce_feature",
        kind="door",
        name="Hidden seam",
        hidden=True,
        discover_dc_tier="hard",
    )
    event = result.events[0]
    assert isinstance(event, FeatureIntroduced)
    assert event.feature.hidden and event.feature.discover_dc == 20
    assert event.feature.id == "feat-hidden-seam"


def test_open_shop_needs_friendly_present_npc() -> None:
    state = party_state()
    add_npc(state)
    result = run_tool(state, "open_shop", npc="npc-mira")
    assert isinstance(result.events[0], ShopOpened)
    add_npc(state, "npc-grim", name="Grim", hostile=True)
    assert run_tool(state, "open_shop", npc="npc-grim").error


def test_quest_lifecycle_and_deed() -> None:
    """M23.5: update_quest no longer creates or closes quests; a favour is the one the model may
    register, and finishing it is a deed for the asker (goodwill only)."""
    state = party_state()
    add_npc(state)
    unknown = run_tool(state, "update_quest", quest_id="q1")
    assert unknown.error is not None and "offer_favour" in unknown.error
    asked = run_tool(
        state,
        "offer_favour",
        npc="npc-mira",
        title="Find the cat",
        kind="visit",
        text="Look for the cat in the forest",
        place="forest",
    )
    assert asked.error is None and isinstance(asked.events[0], QuestUpdated)
    apply_result(state, asked)
    favour = state.world.quests["favour-1"]
    assert favour.state is QuestState.OFFERED and favour.giver_npc_id == "npc-mira"
    refused = run_tool(state, "update_quest", quest_id="favour-1")
    assert refused.error is not None and "not accepted" in refused.error


def test_record_fact_known_entities_only() -> None:
    state = party_state()
    add_npc(state)
    bad = run_tool(state, "record_fact", text="Mira owes Vex.", entity_ids=["npc-mira", "npc-vex"])
    assert bad.error is not None and "npc-vex" in bad.error
    ok = run_tool(
        state,
        "record_fact",
        text="Mira runs the inn.",
        entity_ids=["npc-mira", "town"],
        tags=["Inn", "inn", " "],
    )
    event = ok.events[0]
    assert isinstance(event, FactRecorded)
    assert event.fact.id == "fact-1" and event.fact.tags == ("inn",)


def test_world_events_replay_exactly() -> None:
    state = party_state()
    initial = state.model_copy(deep=True)
    log = []
    steps = [
        ("introduce_npc", {"name": "Ana", "role": "smith", "archetype_id": "commoner"}),
        ("update_attitude", {"npc": "npc-ana", "delta_tier": "improve"}),
        ("introduce_feature", {"kind": "lever", "name": "Rusty lever"}),
        (
            "offer_favour",
            {
                "npc": "npc-ana",
                "title": "Fix the forge",
                "kind": "visit",
                "text": "Fetch coal from the crypt",
                "place": "crypt",
            },
        ),
        ("record_fact", {"text": "Ana lost her hammer.", "entity_ids": ["npc-ana"]}),
        ("open_shop", {"npc": "npc-ana"}),
        ("move_party", {"node_id": "forest"}),
    ]
    for name, args in steps:
        result = run_tool(state, name, **args)
        assert result.error is None, (name, result.error)
        apply_result(state, result)
        log.extend(result.events)
    assert replay(initial, log) == state
