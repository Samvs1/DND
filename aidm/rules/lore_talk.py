"""Learning by asking a person (M31.1b V13, round 4: Bramble told what he carries and Sister
Thena was friendly, yet no learn step moved, because only the storyteller could record it). Pure.

When a hero asks a person standing here (alive, not hostile), the engine decides what they tell:
- a secret is revealed (`SecretRevealed`, the existing mechanism, at most one per ask) when it
  may be revealed now (`secrets.reveal_refusal`) and either its reveal is an attitude band the
  person has reached (a friendly person opens up when asked, V13b) or its words hold every word
  of a topic the line asks about;
- a topic the line asks about is the tag of a learn step not done yet of an active quest
  (`lore.open_learn_steps`) whose words the line says at least one of (exact words,
  `secrets.fact_words`; plan tags are slugs, `rules.plan_satisfy`). It is learned (ONE
  `LoreLearned`, `npc_id` the teacher, `item` their name) when this person teaches it: the
  giver of that step's quest (their own task), a person whose name holds every word of the tag
  (their own story), or a person whose secret, told before or told now, holds them.
A lesson already recorded while its quest was active is not recorded again. Facts the model
records (`record_fact` tags) never teach anything.

Public API: `ask_events(state, actor_id, npc_id, words) -> list[AnyEvent]` (empty: the person
has nothing the engine must tell; the storyteller answers as before).
"""

from collections.abc import Collection

from aidm.models.campaign import RevealKind
from aidm.models.events import AnyEvent
from aidm.models.quest_events import LoreLearned
from aidm.models.quests import QuestStep
from aidm.models.state import GameState
from aidm.models.world import NpcSecret, Quest, WorldNpc
from aidm.models.world_events import SecretRevealed
from aidm.rules.lore import learned_for, open_learn_steps
from aidm.rules.secrets import fact_words, reveal_refusal
from aidm.rules.social import npc_is_hostile


def _asked_steps(state: GameState, words: Collection[str]) -> list[tuple[Quest, QuestStep]]:
    said = set(words)
    return [(q, s) for q, s in open_learn_steps(state) if said & fact_words(s.tag or "")]


def _secret_told(state: GameState, npc: WorldNpc, tags: list[str]) -> NpcSecret | None:
    for secret in npc.secrets:
        if secret.revealed or reveal_refusal(state, npc, secret.id) is not None:
            continue
        if secret.reveal is not None and secret.reveal.kind is RevealKind.ATTITUDE:
            return secret
        if any(fact_words(tag) <= fact_words(secret.text) for tag in tags):
            return secret
    return None


def _teaches(npc: WorldNpc, quest: Quest, tag: str, told: list[str]) -> bool:
    wanted = fact_words(tag)
    if not wanted:
        return False
    if quest.giver_npc_id == npc.id:
        return True
    return wanted <= fact_words(npc.name) or (bool(told) and wanted <= fact_words(*told))


def _present(state: GameState, npc_id: str) -> WorldNpc | None:
    npc = state.world.npcs.get(npc_id)
    if npc is None or npc.dead or npc.node_id != state.world.current_node:
        return None
    return None if npc_is_hostile(npc) else npc


def ask_events(
    state: GameState, actor_id: str, npc_id: str, words: Collection[str]
) -> list[AnyEvent]:
    npc = _present(state, npc_id)
    if npc is None:
        return []
    steps = _asked_steps(state, words)
    secret = _secret_told(state, npc, [s.tag or "" for _, s in steps])
    events: list[AnyEvent] = []
    if secret is not None:
        events.append(SecretRevealed(npc_id=npc.id, secret_id=secret.id))
    told = [s.text for s in npc.secrets if s.revealed or (secret is not None and s.id == secret.id)]
    taught: set[str] = set()
    for quest, step in steps:
        tag = step.tag or ""
        if tag in taught or learned_for(state, quest, tag) or not _teaches(npc, quest, tag, told):
            continue
        taught.add(tag)
        events.append(LoreLearned(creature_id=actor_id, item=npc.name, tag=tag, npc_id=npc.id))
    return events
