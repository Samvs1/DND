"""World facts the narrator is told about a turn (M29.7b honest storyteller, M29_round2.md R2 R12
R17 R28): where the party really is, which lights burn, that nothing was picked up, the party's
size and who is still hurt. The same truth is enforced by THE guard (`aidm.dm.guard_light`,
`aidm.dm.guard_party`).

Public API: `PUT_OUT_WORDS`, `world_facts(state, truth, text, events) -> list[str]`,
`light_asked(text) -> bool`.
"""

from collections.abc import Sequence

from aidm.data.guard_lexicon import guard_lexicon
from aidm.dm.guard_text import find_phrases
from aidm.dm.guard_turn import TurnTruth
from aidm.models import events as ev
from aidm.models.item_events import LightEnded, LightLit
from aidm.models.state import GameState

PUT_OUT_WORDS = frozenset(
    {"put out", "puts out", "pinch out", "pinches out", "snuff", "snuffs", "douse", "douses"}
    | {"blow out", "blows out", "extinguish", "extinguishes", "smother", "smothers"}
)


def light_asked(text: str) -> bool:
    lex = guard_lexicon()
    return bool(find_phrases(text, lex.light_nouns | PUT_OUT_WORDS))


def _place_facts(state: GameState, truth: TurnTruth) -> list[str]:
    if not truth.short_of:
        return []
    here = state.world.node_names.get(state.world.current_node or "", "the next place on the way")
    dest = truth.short_of
    return [
        f"The party stopped at {here}, one place short of {dest}: it has NOT reached {dest}."
        f" Tell the stop at {here}; nothing of {dest} is seen, met or found yet."
    ]


def _light_facts(truth: TurnTruth, text: str, events: Sequence[ev.AnyEvent]) -> list[str]:
    changed = any(isinstance(e, LightLit | LightEnded) for e in events)
    if not changed and not light_asked(text):
        return []
    burning = sorted(truth.burning.items())
    if not burning:
        return ["No light burns now: every torch, lantern and candle of the party is dark."]
    told = ", ".join(f"{who}'s {noun}" for noun, who in burning)
    out = [f"Burning now (lit, seen from afar; a hidden hero carrying one is seen): {told}."]
    if find_phrases(text, PUT_OUT_WORDS) and not truth.ended:
        out.append(f"No light went out in these events: {told} still burns.")
    elif find_phrases(text, guard_lexicon().kindle_words) and not truth.lit:
        asked = {m.group(0).casefold() for m in find_phrases(text, guard_lexicon().light_nouns)}
        lit = [f"{who}'s {noun}" for noun, who in burning if noun in asked]
        if lit:
            out.append(f"Already lit before this action, and still burning: {', '.join(lit)}.")
    return out


def _pickup_facts(truth: TurnTruth, text: str) -> list[str]:
    if truth.picked or not find_phrases(text, guard_lexicon().pickup_words):
        return []
    return [
        "Nothing was picked up in these events: nobody lifts, takes or pockets anything; what a"
        " hero carries they already had, and nothing lay here to take."
    ]


def _party_facts(state: GameState) -> list[str]:
    heroes = sorted(c.name for c in state.creatures.values() if c.pc is not None and not c.dead)
    hurt = sorted(
        c.name
        for c in state.creatures.values()
        if c.pc is not None and not c.dead and c.hp < c.max_hp
    )
    out: list[str] = []
    if len(heroes) > 1:
        out.append(f"The party ('you') is {len(heroes)} heroes: {', '.join(heroes)}.")
    if hurt:
        out.append(f"Still hurt (never 'whole' or 'unhurt'): {', '.join(hurt)}.")
    return out


def world_facts(
    state: GameState, truth: TurnTruth, text: str, events: Sequence[ev.AnyEvent]
) -> list[str]:
    return [
        *_place_facts(state, truth),
        *_light_facts(truth, text, events),
        *_pickup_facts(truth, text),
        *_party_facts(state),
    ]
