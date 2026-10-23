"""Arriving at a campaign node: the established description, then the world's encounter (SPEC 9).

- Lazy descriptions: the first arrival generates the place's description ONCE (FAST, short,
  guarded by THE guard) and stores it with `NodeDescribed`; a revisit never regenerates it
  (the description is part of the manifest, "established place"). Fallback (no key, outage,
  guard rejection): a deterministic description from the node plan's flavour.
- World-pulled encounters: `aidm.rules.encounter_offer.arrival_offer_events` (the warning beat).

Session order after an applied `PartyMoved` (M6): `await on_arrival(state, llm, regs,
retreat_node=moved.from_node, apply=apply)`; the returned events are already applied.

Public API: `place_description_messages(state, node_id)`, `fallback_place_description(state,
node_id) -> str`, `async describe_place(state, llm, node_id=None) -> list[AnyEvent]`,
`offer_data(regs) -> OfferData`, `async on_arrival(state, llm, regs, *, retreat_node, apply)`.
"""

from collections.abc import Callable

from aidm.dm.guard import guarded_narration, prose_checker
from aidm.dm.llm_backend import Message
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_types import LlmRole
from aidm.dm.narration_stream import NarrationSource
from aidm.dm.tool_context import ToolRegistries
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.models.world_events import NodeDescribed
from aidm.rules.encounter_offer import OfferData, arrival_offer_events
from aidm.rules.progression import node_plan, region_of

DESCRIPTION_MAX_TOKENS = 220
DESCRIPTION_MAX_SENTENCES = 3

DESCRIBE_RULES = """Describe this place for the players in 2 or 3 sentences (under 70 words),
second person plural, present tense: sights, sounds, smells, the lie of the land.
Describe ONLY the place: no people, creatures, items, doors, levers, traps or hidden things,
and no names except the place's own name. Plain prose, no lists, no game numbers."""


def place_description_messages(state: GameState, node_id: str) -> list[Message]:
    node, region = node_plan(state, node_id), region_of(state, node_id)
    if node is None or region is None:
        raise ValueError(f"{node_id!r} is not a campaign node")
    user = (
        f"PLACE: {node.name}\nWHAT IT IS: {node.flavour}\n"
        f"TERRAIN: {', '.join(node.terrain_tags)}\nREGION: {region.name}: {region.flavour}"
    )
    return [{"role": "system", "content": DESCRIBE_RULES}, {"role": "user", "content": user}]


def fallback_place_description(state: GameState, node_id: str) -> str:
    node = node_plan(state, node_id)
    if node is None:
        return f"You arrive at {state.world.node_names.get(node_id, node_id)}."
    text = node.flavour.strip()
    return text if text.endswith((".", "!", "?")) else f"{text}."


async def describe_place(
    state: GameState, llm: LlmClient, node_id: str | None = None
) -> list[AnyEvent]:
    target = node_id or state.world.current_node
    if target is None or target in state.world.descriptions or node_plan(state, target) is None:
        return []
    fallback = fallback_place_description(state, target)
    text = fallback
    if llm.available:
        sentences = guarded_narration(
            llm,
            place_description_messages(state, target),
            prose_checker(state),
            [fallback],
            role=LlmRole.FAST,
            max_tokens=DESCRIPTION_MAX_TOKENS,
            max_sentences=DESCRIPTION_MAX_SENTENCES,
        )
        told = await sentences.collect()
        if sentences.source is NarrationSource.MODEL and told.strip():
            text = told.strip()
    return [NodeDescribed(node_id=target, text=text)]


def offer_data(regs: ToolRegistries) -> OfferData:
    return OfferData(
        monsters=regs.combat.monsters,
        tables=regs.encounter_tables,
        terrains=regs.terrains,
        tiers=regs.tiers,
        encounter=regs.encounter_monsters,
    )


async def on_arrival(
    state: GameState,
    llm: LlmClient,
    regs: ToolRegistries,
    *,
    retreat_node: str | None,
    apply: Callable[[AnyEvent], object],
) -> list[AnyEvent]:
    events = await describe_place(state, llm)
    for event in events:
        apply(event)
    offered = arrival_offer_events(state, offer_data(regs), retreat_node)
    for event in offered:
        apply(event)
    return [*events, *offered]
