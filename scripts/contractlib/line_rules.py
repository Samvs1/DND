"""Contract rule B1 (every typed line ends in an outcome), read from the `line_read` record
(M43.1). A save from before the record reports B1 as skipped."""

from aidm.data.spell_defs import spell_defs
from aidm.models.events import AnyEvent
from aidm.models.impossible import LineRead
from aidm.models.state import GameState
from aidm.rules.menu_unoffered import GOLD_SUM
from aidm.rules.story_names import mentions, text_slug
from scripts.contractlib.save import Finding, Visitor

# events that are the line's own bookkeeping or the storyteller's words, not an engine outcome
QUIET = frozenset(
    {
        "narration_recorded",
        "action_declared",
        "line_read",
        "fact_recorded",
        "scene_summarised",
        "node_described",
        "economy_changed",
    }
)


def named_things(state: GameState, actor_id: str, text: str) -> list[str]:
    """Game things a line names: a spell the hero knows, a pack item, a place, a gold amount."""
    slugged = text_slug(text)
    hero = state.creatures.get(actor_id)
    names: list[str] = list(state.world.node_names.values())
    if hero is not None and hero.pc is not None:
        pc = hero.pc
        known = [*pc.cantrips, *pc.race_cantrips, *pc.spells_known, *pc.spellbook]
        names += [s for s in known if s in spell_defs()]
        names += [i.item for i in pc.inventory]
    found = [n for n in names if len(n) > 2 and mentions(slugged, text_slug(n).strip("-"))]
    return found + [m.group(0) for m in GOLD_SUM.finditer(text.lower())][:1]


class LineOutcomes(Visitor):
    """B1: after a `line_read`, the events up to the next one hold an outcome or a refusal."""

    def __init__(self) -> None:
        self.records = 0
        self.open: tuple[int, LineRead, list[str], list[str]] | None = None

    def see(self, seq: int, state: GameState, event: AnyEvent) -> list[Finding]:
        if event.type != "line_read":
            if self.open is not None:
                self.open[3].append(event.type)
            return []
        found = self._close()
        self.records += 1
        self.open = (seq, event, named_things(state, event.creature_id, event.text), [])
        return found

    def _close(self) -> list[Finding]:
        if self.open is None:
            return []
        seq, line, things, types = self.open
        self.open = None
        # a line the chooser read as a talk step was answered by talk, whatever place it names
        asked = any(step.startswith("talk>") for step in line.steps)
        if things and not asked and not any(t not in QUIET for t in types):
            return [
                Finding("B1", seq, f"names {things[:2]}, only talk answered: {line.text[:50]!r}")
            ]
        return []

    def end(self, state: GameState) -> list[Finding]:
        return self._close()
