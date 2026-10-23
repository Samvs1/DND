"""Where a `learn` step is learned (M29.7c R1). Pure.

A learn step needs a fact the party learned for it, never any older fact with the tag (p5 244: a
"learn ashmede" step completed from a visit to Ashmede Mill long before). Steps are checked only
while current (`aidm.rules.quest_steps.steps_met`), so a source that is true NOW is learned for
the step: the party stands at a place whose name holds the tag (it went there to learn it), a
discovered feature here holds it, a revealed secret of someone here holds it, or a finished
quest's title holds it (a deed done once, named in the step's line). A visit long ago no longer
counts. Secrets revealed by a known fact still use `secrets.engine_knows` (any time).

Public API: `learn_source(state, tag) -> str | None` (what teaches it now, as a short line; None
when nothing does).
"""

from aidm.models.state import GameState
from aidm.models.world import QuestState
from aidm.rules.scene import node_display_name
from aidm.rules.secrets import fact_words


def _holds(wanted: set[str], *texts: str) -> bool:
    return wanted <= fact_words(*texts)


def learn_source(state: GameState, tag: str) -> str | None:
    wanted = fact_words(tag)
    world = state.world
    here = world.current_node
    if not wanted:
        return None
    if here is not None and _holds(wanted, here, world.node_names.get(here, "")):
        return f"the party is at {node_display_name(state, here)}"
    for feature in world.features.values():
        seen = not feature.hidden or feature.discovered
        if feature.node_id == here and seen and _holds(wanted, feature.id, feature.name):
            return f"the party found the {feature.name}"
    for npc in world.npcs.values():
        told = [s.text for s in npc.secrets if s.revealed]
        if npc.node_id == here and not npc.dead and told and _holds(wanted, *told):
            return f"{npc.name} told the party"
    for quest in world.quests.values():
        if quest.state is QuestState.COMPLETED and _holds(wanted, quest.id, quest.title):
            return f"the party finished {quest.title}"
    return None
