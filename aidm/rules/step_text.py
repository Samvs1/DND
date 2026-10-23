"""The engine writes the text of every quest step it checks (M29.9b T3 T14 T2). Pure.

Round 3: the model wrote step texts that promised deeds the step kind never checks ("Walk the
Fogward Gallows road at dusk and mark it with a lit brand" was a plain visit; "Bring Piper to her
mother" a plain meet), so earlier visits paid for deeds nobody did. Now the visible text of a
step comes from its CHECKED fields only (places, person, item, tag, band, gold); the model's
words stay in the quest's objective. A `free` step is the storyteller's own judgement
(`rules.quest_free`), so it keeps the model's text. A `clear` step never names foes (T2): who is
there is told only by the actual offer.

- `step_text(step, names)`: the imperative line players read ("Go to Weeping Bastion",
  "Give the lockbox to Renn", "Learn about blackpine").
- `step_deed(step, names)`: the same deed in the past tense, for the ending ("won the fight at
  The Slag Warren").
- `StepNames(places, people)`: display names by id (an unknown id reads as its words);
  `plan_names(plan)` from a campaign plan, `state_names(state)` from the world.

Public API: `StepNames`, `plan_names`, `state_names`, `step_text`, `step_deed`, `the_item`.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from aidm.models.campaign import CampaignPlan
from aidm.models.dm_tiers import AttitudeBand
from aidm.models.quests import MAX_STEP_TEXT, QuestStep, StepKind
from aidm.models.state import GameState
from aidm.rules.plan_ids import boss_npc_id

ELLIPSIS = "..."


def _words(ref: str) -> str:
    return ref.replace("-", " ").replace("_", " ").title()


@dataclass(frozen=True)
class StepNames:
    places: Mapping[str, str] = field(default_factory=dict[str, str])
    people: Mapping[str, str] = field(default_factory=dict[str, str])

    def place(self, node_id: str) -> str:
        return self.places.get(node_id) or _words(node_id)

    def person(self, npc_id: str | None) -> str:
        return self.people.get(npc_id or "") or _words(npc_id or "someone")


def plan_names(plan: CampaignPlan) -> StepNames:
    places = {n.id: n.name for n in plan.all_nodes()}
    people = {n.id: n.name for n in plan.npcs}
    people |= {boss_npc_id(r): r.boss.name for r in plan.all_regions()}
    return StepNames(places, people)


def state_names(state: GameState) -> StepNames:
    base = plan_names(state.campaign.plan) if state.campaign is not None else StepNames()
    places = {**base.places, **{k: v for k, v in state.world.node_names.items() if v}}
    people = {**base.people, **{n.id: n.name for n in state.world.npcs.values()}}
    return StepNames(places, people)


def _cut(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= MAX_STEP_TEXT:
        return text
    cut = text[: MAX_STEP_TEXT - len(ELLIPSIS)].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-") + ELLIPSIS


def _listed(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def the_item(item: str | None) -> str:
    """ "the <item>", except for a name that already holds its article or an owner."""
    name = (item or "thing").strip()
    first = name.split(" ", 1)[0].lower()
    if first in {"the", "a", "an"} or first.endswith(("'s", "s'")):
        return name
    return f"the {name}"


def _places(step: QuestStep, names: StepNames) -> str:
    return _listed([names.place(n) for n in step.nodes])


_BAND_TEXT = {AttitudeBand.ALLY: "Make {npc} an ally", AttitudeBand.FRIENDLY: "Make {npc} friendly"}
_BAND_DEED = {AttitudeBand.ALLY: "made {npc} an ally", AttitudeBand.FRIENDLY: "made {npc} friendly"}


def _obtain(step: QuestStep, names: StepNames, past: bool) -> str:
    verb = "found" if past else "Find"
    what = the_item(step.item) if step.count == 1 else f"{step.count} x {step.item}"
    return f"{verb} {what} at {_places(step, names)}"


def _learn(step: QuestStep, names: StepNames, past: bool) -> str:
    verb = "learned" if past else "Learn"
    clue = f" from {the_item(step.item)}" if step.item else ""
    return f"{verb} about {step.tag}{clue}"


def _win_over(step: QuestStep, names: StepNames, past: bool) -> str:
    band = step.band or AttitudeBand.FRIENDLY
    table = _BAND_DEED if past else _BAND_TEXT
    return table.get(band, table[AttitudeBand.FRIENDLY]).format(npc=names.person(step.npc))


type _Writer = Callable[[QuestStep, StepNames, bool], str]


def _simple(text: str, deed: str) -> _Writer:
    def write(step: QuestStep, names: StepNames, past: bool) -> str:
        fields = {
            "places": _places(step, names),
            "npc": names.person(step.npc),
            "item": the_item(step.item),
            "gold": step.gold,
        }
        return (deed if past else text).format(**fields)

    return write


_WRITERS: dict[StepKind, _Writer] = {
    StepKind.VISIT: _simple("Go to {places}", "went to {places}"),
    StepKind.CLEAR: _simple("Win the fight at {places}", "won the fight at {places}"),
    StepKind.DEFEAT: _simple("Defeat {npc}", "defeated {npc}"),
    StepKind.OBTAIN: _obtain,
    StepKind.DELIVER: _simple("Give {item} to {npc}", "gave {item} to {npc}"),
    StepKind.MEET: _simple("Meet {npc}", "met {npc}"),
    StepKind.WIN_OVER: _win_over,
    StepKind.LEARN: _learn,
    StepKind.PAY: _simple("Pay {npc} {gold} gold", "paid {npc} {gold} gold"),
}


def step_text(step: QuestStep, names: StepNames) -> str:
    writer = _WRITERS.get(step.kind)
    return step.text if writer is None else _cut(writer(step, names, False))


def step_deed(step: QuestStep, names: StepNames) -> str:
    writer = _WRITERS.get(step.kind)
    return step.text.rstrip(". ") if writer is None else _cut(writer(step, names, True))
