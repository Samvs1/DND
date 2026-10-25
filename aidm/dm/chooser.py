"""The menu chooser (M36.5, SPEC 6.2): one typed line -> the hero's steps from the engine's menu.

`choose(state, actor_id, text, menu, llm, *, recent=())`:
1. Exact fast path, no model call (`exact_choice`): when the whole line, normalised (case,
   punctuation, whitespace), is a label the game itself shows, that entry is the choice: an
   entry label, the label without its bracketed descriptor ("Dash"), or `<label> <target
   label>` ("Fire Bolt Kobold B", the target label up to its first comma). A key two different
   picks share is dropped (never a guess). No synonyms or phrase lists: only strings the game
   generates (owner rule).
2. A menu with no entries: `other` (the storyteller), no call.
3. One FAST call with ONE forced tool, `choose_actions` (`aidm.dm.choice_tool`, its schema built
   from this menu), on the CHOOSE pack of the ONE context builder (`ContextPurpose.CHOOSE`;
   `recent` = the table's recent events, for the pronoun anchors and the last 2 events). A pick
   that does not fit the menu is repaired by the client's retry-with-feedback loop.
4. The call fails (no key, timeout, transport, validation exhausted): the fast path already
   missed, so `ChooserFailure` (the session shows `notice`, adjudicator.FALLBACK_NOTICE, and the
   turn is not consumed).

Every chooser call is logged in llm.jsonl with kind `choose` (`CHOOSE_KIND`, M36.6).
DeepSeek strict function calling is used when `LlmSettings.strict_tools` is set (off by
default; `AIDM_STRICT_TOOLS=1` also points the client at the beta endpoint). The validator and
the retry stay either way.

Public API: `CHOOSE_KIND`, `ChooserFailure(reason, detail, notice)`, `exact_choice(menu, text)`,
`choose(...)` (`normalise` lives in `aidm.dm.chooser_prompt`).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from aidm.dm.adjudicator import FALLBACK_NOTICE
from aidm.dm.choice_tool import CHOOSE_TOOL, ChooseActionsArgs, choice_tool
from aidm.dm.chooser_prompt import normalise
from aidm.dm.context import build_context, to_messages
from aidm.dm.context_text import ContextPurpose
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_types import LlmFailure, LlmRole
from aidm.models.action_menu import ActionMenu, MenuChoice, MenuStep
from aidm.models.events import AnyEvent
from aidm.models.state import GameState

_BRACKETS = re.compile(r"\([^)]*\)")
CHOOSE_KIND = "choose"  # the llm.jsonl call kind of a chooser call (M36.6; M36.9 counts them)


@dataclass(frozen=True)
class ChooserFailure:
    reason: str
    detail: str = ""
    notice: str = FALLBACK_NOTICE


def _forms(label: str) -> set[str]:
    return {k for k in (normalise(label), normalise(_BRACKETS.sub(" ", label))) if k}


def _target_forms(label: str) -> set[str]:
    return _forms(label) | _forms(label.split(",", 1)[0].replace("(you)", ""))


def _exact_keys(menu: ActionMenu) -> dict[str, MenuStep]:
    labels = {t.id: t.label for t in menu.targets}
    found: dict[str, set[MenuStep]] = {}
    for entry in menu.entries:
        for form in _forms(entry.label):
            found.setdefault(form, set()).add(MenuStep(entry=entry.id))
            for target in entry.target_ids:
                step = MenuStep(entry=entry.id, targets=(target,))
                for tform in _target_forms(labels.get(target, target)):
                    found.setdefault(f"{form} {tform}", set()).add(step)
    return {key: next(iter(steps)) for key, steps in found.items() if len(steps) == 1}


def exact_choice(menu: ActionMenu, text: str) -> MenuChoice | None:
    key = normalise(text)
    step = _exact_keys(menu).get(key) if key else None
    return MenuChoice(steps=(step,)) if step is not None else None


async def choose(
    state: GameState,
    actor_id: str,
    text: str,
    menu: ActionMenu,
    llm: LlmClient,
    *,
    recent: Sequence[AnyEvent] = (),
) -> MenuChoice | ChooserFailure:
    exact = exact_choice(menu, text)
    if exact is not None:
        return exact
    if not menu.entries:
        return MenuChoice(other=True)
    pack = build_context(state, ContextPurpose.CHOOSE, actor_id, text, events=recent, menu=menu)
    tool = choice_tool(menu, strict=llm.settings.strict_tools)
    reply = await llm.call_tools(
        to_messages(pack),
        [tool],
        LlmRole.FAST,
        tool_choice=CHOOSE_TOOL,
        player_text=text,
        require_call=True,
        kind=CHOOSE_KIND,
    )
    if isinstance(reply, LlmFailure):
        return ChooserFailure(reply.reason.value, reply.detail)
    args = reply.calls[0].args
    if not isinstance(args, ChooseActionsArgs):
        return ChooserFailure("validation", "wrong result type")
    return args.to_choice()
