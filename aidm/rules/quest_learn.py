"""Where a `learn` step is learned (M29.7c R1). Pure.

A learn step needs a fact the party learned for it, never any older fact with the tag (p5 244: a
"learn ashmede" step completed from a visit to Ashmede Mill long before). Steps are checked only
while current (`aidm.rules.quest_steps.steps_met`), so a source that is true NOW is learned for
the step: (M31.1b V13c: a place whose name holds the tag no longer teaches on arrival; a look
around or a search there records it, `rules.lore.place_lore_events`) a
discovered feature here holds it, a revealed secret of someone here holds it, or a finished
quest's title holds it (a deed done once, named in the step's line), or (M29.9b T13) a living
hero carries a clue keepsake that teaches the tag. A visit long ago no longer
counts. Secrets revealed by a known fact still use `secrets.engine_knows` (any time).

Public API: `learn_source(state, tag, *, here_counts=True) -> str | None` (what teaches it now,
as a short line; None when nothing does; `here_counts=False` leaves out the sources bound to the
party's place, M29.9b: those count only after an arrival made while the quest is active).
"""

from aidm.models.state import GameState
from aidm.models.world import QuestState
from aidm.rules.secrets import fact_words


def _holds(wanted: set[str], *texts: str) -> bool:
    return wanted <= fact_words(*texts)


def learn_source(state: GameState, tag: str, *, here_counts: bool = True) -> str | None:
    wanted = fact_words(tag)
    if not wanted:
        return None
    found = _here_source(state, wanted) if here_counts else None
    if found is not None:
        return found
    for quest in state.world.quests.values():
        if quest.state is QuestState.COMPLETED and _holds(wanted, quest.id, quest.title):
            return f"the party finished {quest.title}"
    return _clue_held(state, tag)


def _here_source(state: GameState, wanted: set[str]) -> str | None:
    """The sources bound to the party's place: a feature or a told secret here."""
    world = state.world
    here = world.current_node
    for feature in world.features.values():
        seen = not feature.hidden or feature.discovered
        if feature.node_id == here and seen and _holds(wanted, feature.id, feature.name):
            return f"the party found the {feature.name}"
    for npc in world.npcs.values():
        told = [s.text for s in npc.secrets if s.revealed]
        if npc.node_id == here and not npc.dead and told and _holds(wanted, *told):
            return f"{npc.name} told the party"
    return None


def _clue_held(state: GameState, tag: str) -> str | None:
    """M29.9b T13: a living hero carries a keepsake that teaches the tag (the clue in hand)."""
    for creature in state.creatures.values():
        pc = creature.pc
        if pc is None or creature.dead:
            continue
        clue = next((k for k in pc.keepsakes if k.teaches == tag), None)
        if clue is not None:
            return f"{creature.name} carries the {clue.name}"
    return None
