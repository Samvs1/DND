"""NPC voice and the secret-leak guard over FakeLLM (M4.7, SPEC 6.3, 6.4 item 7, 6.5)."""

import random
from pathlib import Path

from aidm.dm.adjudicator import AdjudicationOptions, AdjudicationResult, adjudicate
from aidm.dm.fake_llm import FakeStream, fake_calls, fake_tool_call
from aidm.dm.guard import check_prose
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_types import ViolationKind
from aidm.dm.llm_client import LlmClient
from aidm.dm.narrator import narrate
from aidm.dm.npc_voice import npc_voice, npc_voice_messages, silent_line, voice_target
from aidm.models.events import AnyEvent
from aidm.models.narration import NarrationTone
from aidm.models.state import GameState
from aidm.models.world import NpcSecret
from aidm.models.world_events import SecretRevealed
from aidm.session.reducer import apply
from tests.ai.fake_scripts import fake_client
from tests.ai.guard_fixtures import inn_state
from tests.ai.tool_fixtures import REGS

WELL = "she poisoned the village well with nightshade"
LEDGER = "he forged the tax ledger for the baron"


def _secret_state() -> GameState:
    state = inn_state()
    mira = state.world.npcs["npc-mira"]
    mira.secrets.append(NpcSecret(id="well", text=WELL, min_score=40))
    mira.motive = "pay off a smuggler's debt"
    hobb = state.world.npcs["npc-hobb"]
    hobb.secrets.append(NpcSecret(id="ledger", text=LEDGER))
    return state


def _kinds(text: str, state: GameState) -> set[ViolationKind]:
    return {v.kind for v in check_prose(text, state).violations}


def test_voice_context_holds_only_that_npcs_secrets() -> None:
    state = _secret_state()
    text = str(npc_voice_messages(state, "npc-mira", actor_id="fighter", player_text="Hello"))
    assert WELL in text and "smuggler" in text and "keep it secret" in text
    assert LEDGER not in text and "forged" not in text
    assert "only the engine reveals secrets" in text


def test_secret_leak_guard_flags_unrevealed_secrets() -> None:
    state = _secret_state()
    assert ViolationKind.SECRET_LEAK in _kinds("Mira poisoned the well, they say.", state)
    assert ViolationKind.SECRET_LEAK in _kinds(f'"Fine. {WELL.capitalize()}."', state)
    assert ViolationKind.SECRET_LEAK in _kinds("Hobb forged that ledger himself.", state)
    assert _kinds("Mira wipes the bar and glances at the well rope.", state) == set()
    assert _kinds("Hobb keeps a tax ledger.", state) == set()


def test_revealed_secret_is_not_a_leak() -> None:
    state = _secret_state()
    apply(state, SecretRevealed(npc_id="npc-hobb", secret_id="ledger"))
    assert _kinds("Hobb forged that ledger himself.", state) == set()
    report = check_prose("Mira poisoned the well.", state)
    assert report.violations[0].span == "secret npc-mira/well"
    assert WELL not in report.correction()


def test_voice_target_policy() -> None:
    state = _secret_state()
    none = AdjudicationResult()
    assert voice_target(state, none, 'I ask Mira "how is business?"') == "npc-mira"
    assert voice_target(state, none, "I talk to the guard") == "npc-hobb"
    assert voice_target(state, none, "I climb onto the bar") is None
    assert voice_target(state, none, "I ask about rooms") is None
    state.world.npcs["npc-hobb"].node_id = "forest"
    assert voice_target(state, none, "I ask about rooms") == "npc-mira"
    state.world.npcs["npc-mira"].hostile = True
    assert voice_target(state, none, "I ask Mira about rooms") is None


async def _adjudicate(
    state: GameState, text: str, client: LlmClient
) -> tuple[AdjudicationResult, list[AnyEvent]]:
    applied: list[AnyEvent] = []

    def apply_fn(event: AnyEvent) -> None:
        applied.append(event)
        apply(state, event)

    result = await adjudicate(
        state,
        "fighter",
        text,
        client,
        AdjudicationOptions(),
        random.Random(5),
        REGS,
        apply_fn,
    )
    return result, applied


async def test_npc_conversation_turn_end_to_end(tmp_path: Path) -> None:
    state = _secret_state()
    text = 'I ask Mira "what is wrong with the well?" and buy her a drink'
    calls = fake_calls(
        [
            ("update_attitude", {"npc": "npc-mira", "delta_tier": "improve", "reason": "drink"}),
            ("reveal_secret", {"npc": "npc-mira", "secret_id": "well"}),
        ]
    )
    leak = FakeStream((f'"{WELL.capitalize()}, between us." ',))
    clean = FakeStream(('"The well? Old stones and older rumours, love." ', "Mira smiles."))
    narration = FakeStream(("Mira accepts the drink with a tired smile.",))
    client, fake = fake_client(tmp_path, [calls, fake_tool_call("no_mechanics", {}), narration])
    fake.push(leak, clean)
    result, _ = await _adjudicate(state, text, client)
    refused = [r for r in result.calls if r.call.name == "reveal_secret"]
    assert refused and refused[0].result.error is not None
    assert not state.world.npcs["npc-mira"].secrets[0].revealed
    told = await narrate(state, result, client, actor_id="fighter", player_text=text).collect()
    assert told == "Mira accepts the drink with a tired smile."
    target = voice_target(state, result, text)
    assert target == "npc-mira"
    stream = npc_voice(state, target, client, actor_id="fighter", player_text=text, result=result)
    speech = await stream.collect()
    assert stream.tone is NarrationTone.SOCIAL and stream.retried
    assert "nightshade" not in speech and "poisoned" not in speech
    assert speech == 'Mira: "The well? Old stones and older rumours, love." Mira smiles.'
    voice_requests = fake.requests[-2:]
    assert all(r.model == "deepseek-v4-pro" for r in voice_requests)
    assert "ENGINE GUARD" in str(voice_requests[1].messages)


async def test_npc_voice_without_model_uses_silent_line(tmp_path: Path) -> None:
    state = _secret_state()
    client, _ = fake_client(tmp_path, [FakeStream(())])
    stream = npc_voice(state, "npc-mira", client, player_text="Hello")
    assert await stream.collect() == silent_line(state.world.npcs["npc-mira"])
    assert stream.source is NarrationSource.TEMPLATE
