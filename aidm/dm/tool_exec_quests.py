"""Executors for `update_quest` and `offer_favour` (M23.5, GOAL "Lifecycle"): the AI proposes.

Quests are engine-owned. `update_quest` only records the CURRENT step of an active quest when it
is a `free` step (`aidm.rules.quest_free`); the settle after the batch completes the quest or the
route. It never creates or closes a quest. `offer_favour` registers the one kind of quest the
model may make up: a present NPC's favour with one typed step (`aidm.rules.favours`), asked on
the players' phones through the same Accept / Not now card as a side quest. Every refusal is a
tool error in words the model can act on.

Public API: `favour_step(args) -> QuestStep` (raises `ToolRefused`), `run_update_quest`,
`run_offer_favour` -> `ToolResult`.
"""

from pydantic import ValidationError

from aidm.dm.tool_context import ToolContext, ToolRefused, ToolRegistries, ToolResult
from aidm.dm.tools import OfferFavourArgs, UpdateQuestArgs
from aidm.models.quests import QuestStep, StepKind
from aidm.models.state import GameState
from aidm.rules.dice import Rng
from aidm.rules.favours import FavourRefused, favour_events
from aidm.rules.quest_free import FreeStepRefused, free_step_events

_NEEDS = {
    StepKind.VISIT: "place",
    StepKind.CLEAR: "place",
    StepKind.DEFEAT: "target_npc",
    StepKind.DELIVER: "item and target_npc",
    StepKind.MEET: "target_npc",
    StepKind.WIN_OVER: "target_npc and band",
    StepKind.LEARN: "tag",
    StepKind.PAY: "target_npc and gold",
}


def favour_step(args: OfferFavourArgs) -> QuestStep:
    kind = StepKind(args.kind.value)
    fields: dict[str, object] = {"kind": kind, "text": args.text.strip()}
    if args.place:
        fields["nodes"] = (args.place,)
    for name, value in (
        ("npc", args.target_npc),
        ("item", args.item),
        ("band", args.band),
        ("tag", args.tag),
        ("gold", args.gold),
    ):
        if value:
            fields[name] = value
    try:
        return QuestStep.model_validate(fields)
    except ValidationError:
        raise ToolRefused(f"a {kind.value} favour needs exactly: {_NEEDS[kind]}") from None


def run_update_quest(
    state: GameState, args: UpdateQuestArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    try:
        events = free_step_events(state, args.quest_id, args.route_id)
    except FreeStepRefused as exc:
        raise ToolRefused(exc.message) from None
    return ToolResult(events=tuple(events), summary=f"quest {args.quest_id}: free step done")


def run_offer_favour(
    state: GameState, args: OfferFavourArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    step = favour_step(args)
    try:
        events = favour_events(state, args.npc, args.title, step)
    except FavourRefused as exc:
        raise ToolRefused(exc.message) from None
    summary = f"favour asked: {args.title.strip()} (the players answer Accept or Not now)"
    return ToolResult(events=tuple(events), summary=summary)
