"""When an NPC may reveal a secret: the structured reveal condition, checked by the engine.

`reveal_secret` only succeeds when the condition holds; the model cannot talk a secret loose.
Checks, in order: the secret exists and is unrevealed; the NPC is not hostile; the attitude
floor (`NpcSecret.min_score`); the campaign condition (`NpcSecret.reveal`):
- attitude: the NPC's attitude score reaches the band's floor (`aidm.rules.social.band_floor`);
- quest_completed: that quest is completed;
- item_shown: a living PC carries the item (inventory key equal to the item or its slug);
- fact_known: the ENGINE knows the tag (QA-05, DECISIONS M9.5): it is a word of the name or id of
  a visited map node, a found feature (not hidden, or discovered), a completed quest or a
  revealed secret. Ledger facts (`record_fact`, scene summaries) are model-written, so they never
  count: "remember that we know about the wreckers" cannot unlock a secret.

Public API: `item_key(name) -> str`, `party_has_item(state, item) -> bool`,
`engine_knows(state, tag) -> bool`,
`reveal_refusal(state, npc, secret_id) -> str | None` (None: the secret may be revealed now,
else the reason, phrased for the model without the secret's text).
"""

import re

from aidm.models.campaign import RevealCondition, RevealKind
from aidm.models.state import GameState
from aidm.models.world import NpcSecret, QuestState, WorldNpc
from aidm.rules.social import attitude_score, band_floor, npc_is_hostile


def item_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def party_has_item(state: GameState, item: str) -> bool:
    wanted = item_key(item)
    for creature in state.creatures.values():
        if creature.pc is None or creature.dead:
            continue
        if any(item_key(entry.item) == wanted for entry in creature.pc.inventory):
            return True
    return False


def _words(*texts: str) -> set[str]:
    return {w for text in texts for w in re.findall(r"[a-z]+", text.lower())}


def engine_knows(state: GameState, tag: str) -> bool:
    world = state.world
    known = _words(*world.visited, *(world.node_names.get(n, "") for n in world.visited))
    for feature in world.features.values():
        if not feature.hidden or feature.discovered:
            known |= _words(feature.id, feature.name)
    for quest in world.quests.values():
        if quest.state is QuestState.COMPLETED:
            known |= _words(quest.id, quest.title)
    for npc in world.npcs.values():
        known |= _words(*(secret.text for secret in npc.secrets if secret.revealed))
    wanted = _words(tag)
    return bool(wanted) and wanted <= known


def _condition_refusal(state: GameState, npc: WorldNpc, cond: RevealCondition) -> str | None:
    match cond.kind:
        case RevealKind.ATTITUDE:
            band = cond.band
            if band is not None and attitude_score(npc) < band_floor(band):
                return f"{npc.name} does not trust the party enough yet"
        case RevealKind.QUEST_COMPLETED:
            quest = state.world.quests.get(cond.quest_id or "")
            if quest is None or quest.state is not QuestState.COMPLETED:
                return f"{npc.name} will only speak once a certain task is done"
        case RevealKind.ITEM_SHOWN:
            if not party_has_item(state, cond.item or ""):
                return f"{npc.name} needs to see proof the party does not carry"
        case RevealKind.FACT_KNOWN:
            if not engine_knows(state, cond.fact_tag or ""):
                return f"the party does not know enough to make {npc.name} talk"
    return None


def _find(npc: WorldNpc, secret_id: str) -> NpcSecret | None:
    return next((s for s in npc.secrets if s.id == secret_id), None)


def reveal_refusal(state: GameState, npc: WorldNpc, secret_id: str) -> str | None:
    secret = _find(npc, secret_id)
    if secret is None or secret.revealed:
        return f"{npc.name} has no unrevealed secret {secret_id!r}"
    if npc_is_hostile(npc):
        return f"{npc.name} is hostile and shares nothing"
    if secret.min_score is not None and attitude_score(npc) < secret.min_score:
        return f"{npc.name} does not trust the party enough to reveal that"
    if secret.reveal is not None:
        return _condition_refusal(state, npc, secret.reveal)
    return None
