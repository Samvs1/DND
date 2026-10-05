"""Context pack properties (M4.3, SPEC 6.4 section 7): over random worlds, private NPC data
(motives and unrevealed secrets) never reaches a non-NPC-voice context, and building is
deterministic."""

from hypothesis import given, settings
from hypothesis import strategies as st

from aidm.dm.context import build_context, to_messages
from aidm.dm.context_text import ContextPurpose
from aidm.models.state import GameState
from aidm.models.world import Fact, NpcSecret, WorldNpc
from aidm.models.world_events import NpcIntroduced
from aidm.session.reducer import apply
from tests.ai.tool_fixtures import party_state

NODES = ("town", "forest", "crypt")
PUBLIC = (ContextPurpose.ADJUDICATE, ContextPurpose.NARRATE, ContextPurpose.SUMMARIZE)


@st.composite
def worlds(draw: st.DrawFn) -> tuple[GameState, list[str], list[str]]:
    state = party_state()
    hidden: list[str] = []
    revealed: list[str] = []
    for n in range(draw(st.integers(0, 5))):
        secrets: list[NpcSecret] = []
        for k in range(draw(st.integers(0, 3))):
            text = f"SECRET{n}X{k}{draw(st.from_regex(r'[A-Z]{5}', fullmatch=True))}"
            is_open = draw(st.booleans())
            secrets.append(NpcSecret(id=f"s{k}", text=text, revealed=is_open))
            (revealed if is_open else hidden).append(text)
        motive = f"MOTIVE{n}{draw(st.from_regex(r'[A-Z]{5}', fullmatch=True))}"
        hidden.append(motive)
        npc = WorldNpc(
            id=f"npc-{n}",
            name=f"Npc{n}",
            role=draw(st.sampled_from(["", "smith", "guard"])),
            archetype_id="commoner",
            node_id=draw(st.sampled_from(NODES)),
            social=draw(st.integers(-25, 40)),
            motive=motive,
            secrets=secrets,
        )
        apply(state, NpcIntroduced(npc=npc))
    tags = [f"npc-{i}" for i in range(5)]
    state.world.facts = [
        Fact(id=f"fact-{i}", text=f"fact {i}", entity_ids=(draw(st.sampled_from(tags)),))
        for i in range(draw(st.integers(0, 4)))
    ]
    return state, hidden, revealed


@settings(max_examples=60, deadline=None)
@given(world=worlds(), purpose=st.sampled_from(PUBLIC), pick=st.integers(0, 5))
def test_private_npc_data_never_in_public_contexts(
    world: tuple[GameState, list[str], list[str]], purpose: ContextPurpose, pick: int
) -> None:
    state, hidden, _ = world
    text = str(to_messages(build_context(state, purpose, "fighter", "hello", f"npc-{pick}")))
    for secret in hidden:
        assert secret not in text


@settings(max_examples=40, deadline=None)
@given(world=worlds(), pick=st.integers(0, 4))
def test_npc_voice_sees_only_its_own_private_data(
    world: tuple[GameState, list[str], list[str]], pick: int
) -> None:
    state, hidden, _ = world
    npc = state.world.npcs.get(f"npc-{pick}")
    text = str(to_messages(build_context(state, ContextPurpose.NPC_VOICE, npc_id=f"npc-{pick}")))
    own = set() if npc is None else {npc.motive, *(s.text for s in npc.secrets)}
    for secret in hidden:
        assert (secret in text) == (secret in own)


@settings(max_examples=30, deadline=None)
@given(world=worlds(), purpose=st.sampled_from(list(ContextPurpose)))
def test_build_is_deterministic(
    world: tuple[GameState, list[str], list[str]], purpose: ContextPurpose
) -> None:
    state = world[0]
    first = to_messages(build_context(state, purpose, "fighter", "x", "npc-0"))
    again = to_messages(
        build_context(state.model_copy(deep=True), purpose, "fighter", "x", "npc-0")
    )
    assert first == again
