"""Entity references in DM tool arguments: ids, with names accepted (SPEC 6.3; M4.8 live finding).

The manifest shows ids in brackets ("Aria [fighter]"), but the real model often passes the name
("Aria", "aria", "[fighter]"), and kept doing so after the error feedback. Before execution
every reference field is normalised: an existing id stays; otherwise brackets and case are
dropped and a UNIQUE display-name match becomes its id (creatures for actors and targets, world
NPCs for NPC fields, both for fact entity ids). Ambiguous or unknown references are left as
they are, so the executors still refuse them; nothing is invented.

Public API: `CREATURE_FIELDS`, `NPC_FIELDS`, `resolve_entity_ref(state, ref, kind)`,
`resolve_tool_refs(state, args) -> args` (a copy with resolved references, or `args` unchanged).
"""

from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel

from aidm.models.state import GameState

CREATURE_FIELDS = ("actor", "actors", "target")
NPC_FIELDS = ("npc", "target_npc", "against_npcs")
ENTITY_FIELDS = ("entity_ids",)

type RefKind = Literal["creature", "npc", "entity"]


def _unique(pairs: Iterable[tuple[str, str]], key: str) -> str | None:
    found = {ident for ident, name in pairs if name.casefold() == key}
    return found.pop() if len(found) == 1 else None


def _creatures(state: GameState) -> list[tuple[str, str]]:
    return [(cid, c.name) for cid, c in state.creatures.items()]


def _npcs(state: GameState) -> list[tuple[str, str]]:
    return [(nid, n.name) for nid, n in state.world.npcs.items()]


def _known(state: GameState, ref: str, kind: RefKind) -> bool:
    if kind == "creature":
        return ref in state.creatures
    if kind == "npc":
        return ref in state.world.npcs
    return ref in state.creatures or ref in state.world.npcs


def resolve_entity_ref(state: GameState, ref: str, kind: RefKind) -> str:
    if _known(state, ref, kind):
        return ref
    bare = ref.strip().strip("[]").strip()
    if bare != ref and _known(state, bare, kind):
        return bare
    key = bare.casefold()
    if kind == "creature":
        return _unique(_creatures(state), key) or ref
    if kind == "npc":
        return _unique(_npcs(state), key) or ref
    return _unique(_creatures(state), key) or _unique(_npcs(state), key) or ref


def _kind(name: str) -> RefKind | None:
    if name in CREATURE_FIELDS:
        return "creature"
    if name in NPC_FIELDS:
        return "npc"
    return "entity" if name in ENTITY_FIELDS else None


def resolve_tool_refs[T: BaseModel](state: GameState, args: T) -> T:
    updates: dict[str, object] = {}
    for name in type(args).model_fields:
        kind = _kind(name)
        value = getattr(args, name)
        if kind is None or value is None:
            continue
        if isinstance(value, str):
            fixed: object = resolve_entity_ref(state, value, kind)
        elif isinstance(value, list):
            fixed = [resolve_entity_ref(state, str(v), kind) for v in value]
        else:
            continue
        if fixed != value:
            updates[name] = fixed
    return args.model_copy(update=updates) if updates else args
