"""Section builders of the context pack (SPEC 6.4 sections 2 to 7); `aidm.dm.context` orders them.

Every builder is deterministic (ids sorted, ledger order kept) and returns plain ASCII-safe
lines. Private NPC data (motive, unrevealed secrets) is rendered ONLY by `npc_private_lines`;
the other builders never read it.

Public API:
- `manifest_lines(state, scene, show_ids) -> list[str]` (ends with `CLOSED_WORLD`).
- `party_lines(state, short) -> list[str]`: one compact sheet line per living PC.
- `quest_lines(state) -> list[str]`; `fact_lines(state, focus, k) -> list[str]` (top-k facts by
  entity overlap with `focus`, then the most recent).
- `memory_lines(state, last_n) -> list[str]`: scene summaries then the last narration turns.
- `npc_private_lines(state, npc_id) -> list[str]`.
- `scene_focus(state, scene, actor_id, npc_id) -> frozenset[str]`: entity ids of the scene.
"""

from aidm.dm.context_text import CLOSED_WORLD
from aidm.dm.entities import display_name
from aidm.models.state import Creature, GameState
from aidm.models.world import QuestState, WorldNpc
from aidm.rules.scene import SceneView, node_display_name
from aidm.rules.social import attitude_band, attitude_score

_BACKSTORY_CHARS = 120


def _tag(show_ids: bool, ident: str) -> str:
    return f" [{ident}]" if show_ids else ""


def _npc_line(npc: WorldNpc, show_ids: bool) -> str:
    parts = [npc.name + _tag(show_ids, npc.id)]
    if npc.role:
        parts.append(npc.role)
    if npc.demeanor:
        parts.append(f"demeanor {npc.demeanor}")
    band = "hostile" if npc.hostile else attitude_band(attitude_score(npc)).value
    parts.append(f"attitude {band}")
    known = [s.text for s in npc.secrets if s.revealed]
    if known:
        parts.append("has revealed: " + " / ".join(known))
    return ", ".join(parts)


def _creature_line(state: GameState, cid: str, show_ids: bool) -> str:
    c = state.creatures[cid]
    return f"{c.name}{_tag(show_ids, cid)} ({c.hp}/{c.max_hp} HP)"


def _joined(items: list[str]) -> str:
    return "; ".join(items) if items else "none"


def _place_lines(state: GameState, scene: SceneView, show_ids: bool) -> list[str]:
    node_tag = _tag(show_ids, scene.node_id) if scene.node_id is not None else ""
    lines = [f"Place: {scene.node_name}{node_tag}"]
    if scene.description:
        lines.append(f"Established description: {scene.description}")
    exits = [
        node_display_name(state, e)
        + _tag(show_ids, e)
        + (" (locked)" if e in scene.locked_exits else "")
        for e in scene.exits
    ]
    lines.append(f"Exits: {_joined(exits)}")
    return lines


def manifest_lines(state: GameState, scene: SceneView, show_ids: bool) -> list[str]:
    world = state.world
    lines = _place_lines(state, scene, show_ids)
    party = [_creature_line(state, cid, show_ids) for cid in scene.party_ids]
    lines.append(f"Party present: {_joined(party)}")
    npcs = [_npc_line(world.npcs[nid], show_ids) for nid in scene.npc_ids]
    lines.append(f"NPCs present ({len(npcs)}): {_joined(npcs)}")
    foes = [_creature_line(state, cid, show_ids) for cid in scene.monster_ids]
    lines.append(f"Hostile creatures: {_joined(foes)}")
    if scene.fallen_ids:
        fallen = [state.creatures[cid].name + _tag(show_ids, cid) for cid in scene.fallen_ids]
        lines.append(f"Dead (they cannot act): {_joined(fallen)}")
    feats: list[str] = []
    for fid in scene.feature_ids:
        f = world.features[fid]
        desc = f": {f.description}" if f.description else ""
        feats.append(f"{f.name}{_tag(show_ids, fid)} ({f.kind.value}){desc}")
    lines.append(f"Features: {_joined(feats)}")
    items = [
        f"{world.items[i].name}{_tag(show_ids, i)} x{world.items[i].qty}" for i in scene.item_ids
    ]
    lines.append(f"Visible items: {_joined(items)}")
    lines.append(CLOSED_WORLD)
    return lines


def _gear(c: Creature) -> list[str]:
    if c.pc is None:
        return []
    eq = c.pc.equipped
    worn = [eq.main_hand, eq.off_hand, eq.ranged, eq.armor, eq.shield]
    return [display_name(i) for i in dict.fromkeys(w for w in worn if w)]


def _backstory(c: Creature) -> str:
    text = (c.pc.backstory if c.pc is not None else "").strip().replace("\n", " ")
    first = text.split(". ")[0]
    return first[:_BACKSTORY_CHARS]


def _sheet(c: Creature, short: bool) -> str:
    pc = c.pc
    assert pc is not None
    race = display_name(pc.subrace or pc.race)
    conds = ", ".join(sorted({x.name for x in c.conditions})) or "none"
    line = f"{c.name}: {race} {display_name(pc.class_index)} {pc.level}, HP {c.hp}/{c.max_hp}"
    line += f", conditions: {conds}"
    if short:
        return line
    gear = _gear(c)
    if gear:
        line += f", gear: {', '.join(gear)}"
    story = _backstory(c)
    return line + (f", backstory: {story}" if story else "")


def party_lines(state: GameState, short: bool) -> list[str]:
    pcs = sorted((c for c in state.creatures.values() if c.pc is not None), key=lambda c: c.id)
    return [_sheet(c, short) + (" (dead)" if c.dead else "") for c in pcs]


def quest_lines(state: GameState) -> list[str]:
    open_states = (QuestState.OFFERED, QuestState.ACTIVE)
    out: list[str] = []
    for qid in sorted(state.world.quests):
        quest = state.world.quests[qid]
        if quest.state not in open_states:
            continue
        giver = state.world.npcs.get(quest.giver_npc_id or "")
        by = f", given by {giver.name}" if giver is not None else ""
        out.append(f"{quest.title} [{qid}] ({quest.state.value}){by}")
    return out


def scene_focus(
    state: GameState, scene: SceneView, actor_id: str | None, npc_id: str | None
) -> frozenset[str]:
    ids = {*scene.party_ids, *scene.npc_ids, *scene.feature_ids, *scene.monster_ids}
    ids.update(q for q, v in state.world.quests.items() if v.state is QuestState.ACTIVE)
    ids.update(x for x in (scene.node_id, actor_id, npc_id) if x)
    return frozenset(ids)


def fact_lines(state: GameState, focus: frozenset[str], k: int) -> list[str]:
    facts = state.world.facts
    ranked = sorted(
        range(len(facts)), key=lambda i: (-len(focus.intersection(facts[i].entity_ids)), -i)
    )
    return [facts[i].text for i in ranked[:k]]


def memory_lines(state: GameState, last_n: int) -> list[str]:
    memory = state.memory
    lines = [
        f"Earlier (scene {s.scene_index}, {node_display_name(state, s.node_id)}): {s.text}"
        for s in memory.summaries
    ]
    recent = memory.narration[-last_n:] if last_n > 0 else []
    return lines + [f"Narrated: {text}" for text in recent]


def npc_private_lines(state: GameState, npc_id: str | None) -> list[str]:
    npc = state.world.npcs.get(npc_id or "")
    if npc is None:
        return []
    lines = [f"You are {npc.name} ({npc.role or 'stranger'}), voice {npc.voice_tag or 'plain'}."]
    if npc.motive:
        lines.append(f"Motive (private): {npc.motive}")
    for secret in npc.secrets:
        state_word = "already revealed" if secret.revealed else "keep it secret"
        lines.append(f"Secret [{secret.id}] ({state_word}): {secret.text}")
    return lines
