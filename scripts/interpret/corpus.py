"""The labelled corpus rows and the offline coverage check (M36.7).

A row is `{id, run, seq, actor_id, text, scope, expect, alt, source, note}`; `expect` and each
`alt` is `{steps: [{entry, targets, qty}], other, other_first}`. `gaps(menu, row)` lists why the
menu cannot express a row's expectation (an empty list = covered): scope mismatch, an entry or a
target the menu lacks, a quantity over the entry's, a choice the model's tool would reject.
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

    def choice(self) -> MenuChoice:
        steps = tuple(
            MenuStep(entry=s.entry, targets=tuple(s.targets), qty=s.qty) for s in self.steps
        )
        return MenuChoice(
            steps=steps,
            other=self.other,
            other_first=self.other and self.other_first and bool(steps),
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

    def choices(self) -> list[MenuChoice]:
        return [self.expect.choice(), *(a.choice() for a in self.alt)]


def load_corpus(path: Path) -> list[Row]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Row.model_validate(json.loads(line)) for line in lines if line.strip()]


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
    args = {
        "steps": [{"do": s.entry, "to": list(s.targets), "qty": s.qty} for s in choice.steps],
        "other": {"text": "", "first": choice.other_first} if choice.other else None,
    }
    try:
        built = choice_tool(menu).args_model.model_validate(args)
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


def gaps(menu: ActionMenu, row: Row) -> list[str]:
    found: list[str] = []
    if menu.scope.value != row.scope:
        found.append(f"scope {menu.scope.value} != row scope {row.scope}")
    for choice in row.choices():
        problems = _choice_gaps(menu, choice)
        found += problems or _tool_gaps(menu, choice)
    return found
