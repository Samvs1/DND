"""Quest plans: steps, routes, the main quest of an act, the finale (M23, docs/next/GOAL_QUESTS.md).

A quest is 1 to 4 ordered steps from one engine-checked vocabulary. The main quest of an act has
routes; the Force route (explore the region, then defeat the boss) is ALWAYS built by code
(`aidm.rules.quest_plan`) and never stored, so `MainQuestPlan` holds only the Peace and Cunning
routes a plan writes. Plans without these fields (old saves) are derived by
`aidm.rules.quest_plan`. Cross-references (nodes, NPCs, the act region) are checked by
`aidm.rules.quest_check`, never here, so saved plans keep validating.

Public API:
- `QuestKind`: main / side / favour. `StepKind`: the 10 step kinds (M29.9a `pay`: give an NPC
  `gold` coins, a favour step). `RouteKind`: force / peace /
  cunning. `RouteEffect`: what a finished Cunning route does to the boss fight.
- `QuestStep(kind, text, nodes, npc, item, count, hidden, band, tag, gold)`: exactly the fields its
  kind needs (`STEP_FIELDS`); `goal()` is the count shown as x/N (visit: its nodes, obtain: its
  count, else 1). `obtain` places `count` copies of `item` over `nodes` (1..count places).
- `RoutePlan(id, kind, title, hint_npc_id, steps, effect)`: `effect` only (and always) on Cunning.
- `MainQuestPlan(routes)`: the stored routes of an act (Peace and/or Cunning, never Force).
- `MainQuest(id, act, title, objective, routes)`: the derived main quest (Force first).
- `FinaleOption(id, title, text)`; `FinalePlan(question, options)`: exactly two endings.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.models.character import MAX_KEEPSAKE_NAME
from aidm.models.dm_tiers import AttitudeBand

MAX_STEP_TEXT = 100
MAX_STEPS = 4
MAX_STEP_COUNT = 5
MAX_STEP_GOLD = 500
MAX_TAG = 24
FORCE_ROUTE_ID = "force"
_REF = r"^[a-z0-9][a-z0-9-]*$"

type RouteEffect = Literal["boss_alone", "boss_surprised"]


class QuestKind(StrEnum):
    MAIN = "main"
    SIDE = "side"
    FAVOUR = "favour"


class StepKind(StrEnum):
    VISIT = "visit"
    CLEAR = "clear"
    DEFEAT = "defeat"
    OBTAIN = "obtain"
    DELIVER = "deliver"
    MEET = "meet"
    WIN_OVER = "win_over"
    LEARN = "learn"
    FREE = "free"
    PAY = "pay"


class RouteKind(StrEnum):
    FORCE = "force"
    PEACE = "peace"
    CUNNING = "cunning"


# (required fields, optional fields) per step kind; any other field must keep its default.
STEP_FIELDS: dict[StepKind, tuple[frozenset[str], frozenset[str]]] = {
    StepKind.VISIT: (frozenset({"nodes"}), frozenset()),
    StepKind.CLEAR: (frozenset({"nodes"}), frozenset()),
    StepKind.DEFEAT: (frozenset({"npc"}), frozenset()),
    StepKind.OBTAIN: (frozenset({"item", "nodes"}), frozenset({"count", "hidden"})),
    StepKind.DELIVER: (frozenset({"item", "npc"}), frozenset()),
    StepKind.MEET: (frozenset({"npc"}), frozenset()),
    StepKind.WIN_OVER: (frozenset({"npc", "band"}), frozenset()),
    StepKind.LEARN: (frozenset({"tag"}), frozenset()),
    StepKind.FREE: (frozenset(), frozenset()),
    StepKind.PAY: (frozenset({"npc", "gold"}), frozenset()),
}


class _Plan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class QuestStep(_Plan):
    kind: StepKind
    text: str = Field(min_length=1, max_length=MAX_STEP_TEXT)
    nodes: tuple[str, ...] = Field(default=(), max_length=MAX_STEP_COUNT)
    npc: str | None = Field(default=None, pattern=_REF, max_length=70)
    item: str | None = Field(default=None, min_length=1, max_length=MAX_KEEPSAKE_NAME)
    count: int = Field(default=1, ge=1, le=MAX_STEP_COUNT)
    hidden: bool = False
    band: AttitudeBand | None = None
    tag: str | None = Field(default=None, min_length=1, max_length=MAX_TAG)
    gold: int = Field(default=0, ge=0, le=MAX_STEP_GOLD)  # M29.9a: a pay step's coins

    def given_fields(self) -> frozenset[str]:
        given = {
            "nodes": bool(self.nodes),
            "npc": self.npc is not None,
            "item": self.item is not None,
            "count": self.count != 1,
            "hidden": self.hidden,
            "band": self.band is not None,
            "tag": self.tag is not None,
            "gold": self.gold != 0,
        }
        return frozenset(name for name, present in given.items() if present)

    def goal(self) -> int:
        if self.kind is StepKind.VISIT:
            return len(self.nodes)
        return self.count

    @model_validator(mode="after")
    def _fields_for_kind(self) -> QuestStep:
        required, optional = STEP_FIELDS[self.kind]
        given = self.given_fields()
        if required - given or given - required - optional:
            raise ValueError(f"a {self.kind.value!r} step needs exactly {sorted(required)}")
        if len(set(self.nodes)) != len(self.nodes):
            raise ValueError(f"a {self.kind.value!r} step names a place twice")
        if self.kind is StepKind.CLEAR and len(self.nodes) != 1:
            raise ValueError("a 'clear' step names exactly one place")
        if self.kind is StepKind.OBTAIN and len(self.nodes) > self.count:
            raise ValueError("an 'obtain' step places at most `count` copies")
        if self.band is AttitudeBand.HOSTILE:
            raise ValueError("a 'win_over' step cannot aim at a hostile attitude")
        return self


class RoutePlan(_Plan):
    id: str = Field(pattern=_REF, max_length=40)
    kind: RouteKind
    title: str = Field(min_length=1, max_length=60)
    hint_npc_id: str | None = Field(default=None, pattern=_REF, max_length=70)
    steps: tuple[QuestStep, ...] = Field(min_length=1, max_length=MAX_STEPS)
    effect: RouteEffect | None = None

    @model_validator(mode="after")
    def _effect_on_cunning(self) -> RoutePlan:
        if (self.effect is not None) != (self.kind is RouteKind.CUNNING):
            raise ValueError(f"route {self.id!r}: a Cunning route has an effect, other routes none")
        return self


def _one_route_per_kind(routes: tuple[RoutePlan, ...]) -> None:
    kinds = [r.kind for r in routes]
    ids = [r.id for r in routes]
    if len(set(kinds)) != len(kinds) or len(set(ids)) != len(ids):
        raise ValueError("a main quest has at most one route of each kind, with unique ids")


class MainQuestPlan(_Plan):
    routes: tuple[RoutePlan, ...] = Field(default=(), max_length=2)

    @model_validator(mode="after")
    def _no_stored_force(self) -> MainQuestPlan:
        _one_route_per_kind(self.routes)
        if any(r.kind is RouteKind.FORCE or r.id == FORCE_ROUTE_ID for r in self.routes):
            raise ValueError("the Force route is built by code and never stored")
        return self


class MainQuest(_Plan):
    id: str = Field(min_length=1)
    act: int = Field(ge=1)
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    routes: tuple[RoutePlan, ...] = Field(min_length=1, max_length=3)

    def route(self, route_id: str) -> RoutePlan | None:
        return next((r for r in self.routes if r.id == route_id), None)

    @model_validator(mode="after")
    def _force_first(self) -> MainQuest:
        _one_route_per_kind(self.routes)
        if self.routes[0].kind is not RouteKind.FORCE:
            raise ValueError("the Force route comes first and is always there")
        return self


class FinaleOption(_Plan):
    id: str = Field(pattern=_REF, max_length=40)
    title: str = Field(min_length=1, max_length=60)
    text: str = Field(min_length=1, max_length=200)


class FinalePlan(_Plan):
    question: str = Field(min_length=1, max_length=200)
    options: tuple[FinaleOption, FinaleOption]

    @model_validator(mode="after")
    def _distinct(self) -> FinalePlan:
        if self.options[0].id == self.options[1].id:
            raise ValueError("the two endings need different ids")
        return self
