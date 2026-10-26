"""The `choose_actions` tool (M36.5, SPEC 6.2): the model's only answer to a typed line.

`choice_tool(menu, strict=False) -> ToolDef` builds the tool for ONE menu. Its JSON schema is made
per call: `steps` is at most 4 items `{do, to, qty}` where `do` is an enum of exactly the menu's
entry ids and `to` an array of the menu's target ids (an enum; no targets = an empty array), and
`other` is null or `{text, first}` (the off-menu part in the player's words; `first` = it happens
before the steps). M36.9: `colour` is a string ("" when none) holding the words that only describe
how the hero does the chosen steps; narration only, it never makes an act. Its meaning is said
once, in the CHOOSE rules (`chooser_prompt`), not in the per-menu schema (prompt budget). Every
property is required and no extra property is allowed, so the same schema is valid for DeepSeek
strict function calling (`strict`, off by default).

The schema only guides; the args model validates. `ChooseActionsArgs` (bound to the menu by
`choice_tool`) rejects an id not on the menu, a target that does not fit its entry (its
`target_ids`, plus the area a push sends the foe to; far targets are listed and allowed, the
rules answer "out of reach"), too many targets, a qty over the entry's `qty_max` (M36.10a: not a
said count, `menu_steps_scene.said_count`: a give or gold, the rules answer it) and an empty
answer, with short repair lines naming the allowed values ("give:block-of-incense takes one of:
widow-cabrelle, peddler"). The ONE LLM client feeds those lines back and retries
(`llm_client.call_tools`, `llm_validate`), so a bad pick is repaired, never executed.
M38.4: a step at a target its entry cannot act on (`rules.menu_unoffered.off_targets`: a
not-offered target, an unlisted id, a listed person or hero the entry does not take) is NOT
repaired (the repair was how a swapped target got in: "talk takes one of: reeve-hallick"):
it passes, and `to_choice` turns it into `other` (the storyteller's, in the player's words),
so the engine never acts on someone the player did not name. The `to` enum lists the
not-offered targets too (`ActionMenu.unoffered`).

Public API: `CHOOSE_TOOL`, `ChosenStep`, `OtherPart`, `ChooseActionsArgs` (`to_choice()`),
`menu_schema(menu)`, `menu_problems(menu, args)`, `choice_tool(menu, strict=False)`.
"""

from difflib import get_close_matches
from typing import Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.dm.llm_types import ToolDef
from aidm.models.action_menu import MAX_STEPS, ActionMenu, MenuChoice, MenuEntry, MenuStep
from aidm.rules.menu_steps_scene import said_count
from aidm.rules.menu_unoffered import off_targets

CHOOSE_TOOL = "choose_actions"
TOOL_TEXT = "The hero's MENU steps in the order said, other, colour."
_SUGGEST = 8


def menu_schema(menu: ActionMenu | None) -> dict[str, Any]:
    entries = [e.id for e in menu.entries] if menu is not None else []
    targets = [t.id for t in (*menu.targets, *menu.unoffered)] if menu is not None else []
    to: dict[str, Any] = {"type": "array", "items": {"type": "string"}}
    if targets:
        to["items"] = {"type": "string", "enum": targets}
    else:
        to["maxItems"] = 0
    do: dict[str, Any] = {"type": "string", "enum": entries} if entries else {"type": "string"}
    qty = {"anyOf": [{"type": "integer"}, {"type": "null"}]}
    step = _object({"do": do, "to": to, "qty": qty})
    steps: dict[str, Any] = {
        "type": "array",
        "items": step,
        "maxItems": MAX_STEPS if entries else 0,
    }
    part = _object({"text": {"type": "string"}, "first": {"type": "boolean"}})
    other = {"anyOf": [part, {"type": "null"}]}
    return _object({"steps": steps, "other": other, "colour": {"type": "string"}})


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _schema_from_menu(schema: dict[str, Any], cls: type[Any]) -> None:
    """Pydantic hook: the tool parameters are the per-menu schema, nothing generated."""
    schema.clear()
    schema.update(menu_schema(getattr(cls, "menu", None)))


class ChosenStep(BaseModel):
    do: str
    to: list[str] = Field(default_factory=list[str])
    qty: int | None = None


class OtherPart(BaseModel):
    text: str = ""
    first: bool = False


def _suggest(menu: ActionMenu, wrong: str) -> str:
    verb = wrong.split(":", 1)[0]
    same = [e.id for e in menu.entries if e.id.split(":", 1)[0] == verb]
    near = get_close_matches(wrong, same, n=_SUGGEST, cutoff=0.0)
    return f"; {verb} ids here: {', '.join(near)}" if near else ""


def _targets_problem(entry: MenuEntry, to: list[str]) -> str | None:
    allowed = (*entry.target_ids, *entry.zone_ids)
    if to and not allowed:
        return f"{entry.id} takes no target; send to: []"
    if any(t not in allowed for t in to):
        return f"{entry.id} takes one of: {', '.join(entry.target_ids)}" + (
            f" (then an area: {', '.join(entry.zone_ids)})" if entry.zone_ids else ""
        )
    limit = entry.max_targets + (1 if entry.zone_ids else 0)
    if len(to) > limit:
        return f"{entry.id} takes at most {limit} target(s)"
    return None


def _qty_problem(entry: MenuEntry, qty: int | None) -> str | None:
    if qty is None or 1 <= qty <= entry.qty_max or (qty >= 1 and said_count(entry)):
        return None
    if entry.qty_max == 1:
        return f"{entry.id} takes no quantity; send qty: null"
    return f"{entry.id} qty is 1 to {entry.qty_max}"


def _step(step: ChosenStep) -> MenuStep:
    return MenuStep(entry=step.do, targets=tuple(step.to), qty=max(1, step.qty or 1))


def menu_problems(menu: ActionMenu | None, args: "ChooseActionsArgs") -> list[str]:
    if not args.steps and args.other is None:
        return ["pick at least one step, or other"]
    if len(args.steps) > MAX_STEPS:
        return [f"at most {MAX_STEPS} steps"]
    entries = {e.id: e for e in menu.entries} if menu is not None else {}
    problems: list[str] = []
    for i, step in enumerate(args.steps):
        entry = entries.get(step.do)
        if entry is None:
            hint = _suggest(menu, step.do) if menu is not None else ""
            problems.append(f"steps[{i}].do {step.do!r} is not a menu id{hint}")
            continue
        if menu is not None and off_targets(menu, _step(step)):
            continue  # M38.4: the storyteller's (`to_choice`), never repaired into a swap
        for problem in (_targets_problem(entry, step.to), _qty_problem(entry, step.qty)):
            if problem is not None:
                problems.append(problem)
    return problems


class ChooseActionsArgs(BaseModel):
    """The model's pick, checked against the menu it was bound to (`choice_tool`)."""

    model_config = ConfigDict(json_schema_extra=_schema_from_menu)
    menu: ClassVar[ActionMenu | None] = None

    steps: list[ChosenStep] = Field(default_factory=list[ChosenStep])
    other: OtherPart | None = None
    colour: str = ""

    @model_validator(mode="after")
    def _fits_menu(self) -> Self:
        problems = menu_problems(type(self).menu, self)
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def to_choice(self) -> MenuChoice:
        """The pick as a `MenuChoice`; M38.4: a step at a target its entry cannot act on is
        dropped and becomes `other` (first when it came before every kept step), the model's
        own other part kept as it is."""
        menu = type(self).menu
        picked = [_step(s) for s in self.steps]
        off = [i for i, s in enumerate(picked) if menu is not None and off_targets(menu, s)]
        steps = tuple(s for i, s in enumerate(picked) if i not in off)
        other = self.other
        if other is None and off:
            kept = [i for i in range(len(picked)) if i not in off]
            other = OtherPart(first=bool(kept) and off[0] < kept[0])
        return MenuChoice(
            steps=steps,
            other=other is not None,
            other_text=other.text.strip() if other is not None else "",
            other_first=bool(other is not None and other.first and steps),
            colour=self.colour.strip(),
        )


def choice_tool(menu: ActionMenu, strict: bool = False) -> ToolDef:
    bound = menu

    class BoundChoice(ChooseActionsArgs):
        menu = bound

    return ToolDef(CHOOSE_TOOL, TOOL_TEXT, BoundChoice, strict=strict)
