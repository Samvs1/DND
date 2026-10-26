"""The labelled corpus rows and the offline coverage check (M36.7).

A row is `{id, run, seq, actor_id, text, scope, expect, alt, source, note}`; `expect` and each
`alt` is `{steps: [{entry, targets, qty}], other, other_first}`, plus an optional `colour` (M36.9:
the words that only colour the steps; never scored). `gaps(menu, row)` lists why the
menu cannot express a row's expectation (an empty list = covered): scope mismatch, an entry or a
target the menu lacks, a quantity over the entry's, a choice the model's tool would reject.
M38.4 (optional): `not_offered` lists the not-offered target ids the menu must show for the line
(`ActionMenu.unoffered`); `via` holds raw picks a model may send (steps at a target the entry
cannot act on) that the tool must turn into `expect` (`ChooseActionsArgs.to_choice`) or reject
with the repair line that says the part is `other` (M38.5 fix).
"""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from aidm.dm.choice_tool import ChooseActionsArgs, choice_tool
from aidm.models.action_menu import ActionMenu, MenuChoice, MenuStep


class StepRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry: str
    targets: list[str] = Field(default_factory=list[str])
    qty: int = 1


class Expect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    steps: list[StepRow] = Field(default_factory=list[StepRow])
    other: bool = False
    other_first: bool = False
    colour: str = ""  # M36.9: optional, never scored (the words that only colour the steps)

    def choice(self) -> MenuChoice:
        steps = tuple(
            MenuStep(entry=s.entry, targets=tuple(s.targets), qty=s.qty) for s in self.steps
        )
        return MenuChoice(
            steps=steps,
            other=self.other,
            other_first=self.other and self.other_first and bool(steps),
            colour=self.colour,
        )


class Row(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    run: str
    seq: int
    actor_id: str
    text: str
    scope: str
    expect: Expect
    alt: list[Expect] = Field(default_factory=list[Expect])
    source: str = "sample"
    note: str = ""
    not_offered: list[str] = Field(default_factory=list[str])  # M38.4
    via: list[Expect] = Field(default_factory=list[Expect])  # M38.4

    def choices(self) -> list[MenuChoice]:
        return [self.expect.choice(), *(a.choice() for a in self.alt)]


class SceneRow(Row):
    """M38.1: a row on a named synthetic scene (scripts/interpret/synthetic.py) instead of a
    fixture line; `run` and `seq` stay empty."""

    run: str = ""
    seq: int = 0
    scene: str


type Shape = tuple[tuple[tuple[str, tuple[str, ...], int], ...], bool, bool]


def shape(choice: MenuChoice) -> Shape:
    """A choice as the scorer compares it: steps (targets as a set), other, other_first."""
    steps = tuple((s.entry, tuple(sorted(s.targets)), s.qty) for s in choice.steps)
    return steps, choice.other, choice.other and choice.other_first and bool(steps)


def _row(raw: str) -> Row:
    data = json.loads(raw)
    return SceneRow.model_validate(data) if "scene" in data else Row.model_validate(data)


def load_corpus(path: Path) -> list[Row]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [_row(line) for line in lines if line.strip()]


def _choice_gaps(menu: ActionMenu, choice: MenuChoice) -> list[str]:
    entries = {e.id: e for e in menu.entries}
    found: list[str] = []
    for step in choice.steps:
        entry = entries.get(step.entry)
        if entry is None:
            found.append(f"entry {step.entry} not in menu")
            continue
        found += [
            f"{step.entry}: target {t} not offered"
            for t in step.targets
            if t not in entry.target_ids
        ]
        if len(step.targets) > entry.max_targets:
            found.append(f"{step.entry}: {len(step.targets)} targets over {entry.max_targets}")
        if step.qty > entry.qty_max:
            found.append(f"{step.entry}: qty {step.qty} over {entry.qty_max}")
    return found


def _tool_gaps(menu: ActionMenu, choice: MenuChoice) -> list[str]:
    try:
        built = choice_tool(menu).args_model.model_validate(_args(choice))
    except ValueError as exc:
        return [f"tool rejects: {str(exc).splitlines()[0]}"]
    if not isinstance(built, ChooseActionsArgs):
        return ["tool built a wrong model"]
    back = built.to_choice()
    same = (back.steps, back.other, back.other_first) == (
        choice.steps,
        choice.other,
        choice.other_first,
    )
    return [] if same else ["tool round trip differs"]


def _args(choice: MenuChoice) -> dict[str, object]:
    return {
        "steps": [{"do": s.entry, "to": list(s.targets), "qty": s.qty} for s in choice.steps],
        "other": {"text": "", "first": choice.other_first} if choice.other else None,
        "colour": choice.colour,
    }


OFF_REPAIR = "is other, never another target"  # the repair line's words (`choice_tool`)


def _via_gaps(menu: ActionMenu, row: Row) -> list[str]:
    """M38.4: the not-offered targets are shown; each raw pick at a target its entry cannot take
    resolves to `expect`, or (M38.5 fix) is rejected by a repair line that says the part is
    `other`, never another target (never repaired into a stand-in)."""
    shown = {t.id for t in menu.unoffered}
    found = [f"{t} is not shown as not offered" for t in row.not_offered if t not in shown]
    want = shape(row.expect.choice())
    for via in row.via:
        try:
            built = choice_tool(menu).args_model.model_validate(_args(via.choice()))
        except ValueError as exc:
            if OFF_REPAIR not in str(exc):
                found.append(f"via rejected: {str(exc).splitlines()[0]}")
            continue
        if isinstance(built, ChooseActionsArgs) and shape(built.to_choice()) != want:
            found.append(f"via resolves to {built.to_choice()} not the expectation")
    return found


def gaps(menu: ActionMenu, row: Row) -> list[str]:
    found: list[str] = []
    if menu.scope.value != row.scope:
        found.append(f"scope {menu.scope.value} != row scope {row.scope}")
    for choice in row.choices():
        problems = _choice_gaps(menu, choice)
        found += problems or _tool_gaps(menu, choice)
    return found + _via_gaps(menu, row)
