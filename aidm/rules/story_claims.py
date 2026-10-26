"""The write-time claim check for model-written facts (M40.4, SPEC 6.6). Pure.

Round 7 (r7b-typed 62): a narration lie became a fact ("her offers of three gold ... were not
taken up": the engine never refused anything). A fact the summariser or the `record_fact`
tool writes that CLAIMS a deed (something was handed over, paid, refused, picked up, killed,
fled) is kept only when an engine event in the covered turns did that deed to a thing the
fact names. The check is structural: the deed keys the reducer marked (`World.changed`,
`aidm.rules.story_keys`) for the fact's entity ids and the registered names its text spells
out (`aidm.rules.story_names`), at or after `claim_window(state)` (the seq of the last scene
summary: the turns a new summary covers). The words below only CLASSIFY the claim kind (the
verbs of each deed); they never decide truth. A model may also state the kinds itself
(`SummaryFact.claims`); both are checked. A claim that names no registered being or thing
cannot contradict the registry and is kept. `OFFER` (accepted, refused, requested, promised)
is not a deed: `aidm.rules.story_records` uses it to tie a record to the quests its giver gives.

Public API: `ClaimKind`, `DEED_KINDS`, `claim_kinds(text) -> frozenset[ClaimKind]`,
`claim_window(state) -> int`, `unsupported_claims(state, text, entity_ids, stated=(),
since=None) -> tuple[ClaimKind, ...]`.
"""

import re
from collections.abc import Iterable
from enum import StrEnum

from aidm.models.state import GameState
from aidm.rules.story_names import named_slugs


class ClaimKind(StrEnum):
    KILL = "kill"  # the values are the deed kinds of `aidm.rules.story_keys`
    FLIGHT = "flight"
    HANDOVER = "handover"
    PAYMENT = "payment"
    PICKUP = "pickup"
    REFUSAL = "refusal"
    OFFER = "offer"


DEED_KINDS = frozenset(k for k in ClaimKind if k is not ClaimKind.OFFER)
_VERBS: dict[ClaimKind, str] = {
    ClaimKind.KILL: r"killed|kills|slain|slew|slays|died|dies",
    ClaimKind.FLIGHT: r"fled|flees|escaped|retreated|withdrew|ran off",
    ClaimKind.HANDOVER: r"gave|gives|given|handed|hands over|handing",
    ClaimKind.PAYMENT: r"paid|pays|paying|bribed|bought|buys|sold|sells",
    ClaimKind.PICKUP: r"picked up|picks up|pocketed|pockets|looted|loots|grabbed|grabs",
    ClaimKind.REFUSAL: r"refused|refuses|declined|declines|rejected|turned down|not taken up"
    r"|(?:did|would|will) not take|(?:didn|wouldn|won)'t take",
    ClaimKind.OFFER: r"(?:accept|refus|request|promis|offer|ask)\w*",
}
_PATTERNS = {k: re.compile(rf"\b(?:{v})\b", re.IGNORECASE) for k, v in _VERBS.items()}


def claim_kinds(text: str) -> frozenset[ClaimKind]:
    return frozenset(k for k, p in _PATTERNS.items() if p.search(text))


def claim_window(state: GameState) -> int:
    """The first seq the next summary covers: the last summary's seq (0 without one)."""
    for summary in reversed(state.memory.summaries):
        if summary.made is not None:
            return summary.made.seq
    return 0


def _targets(state: GameState, text: str, entity_ids: Iterable[str]) -> set[str]:
    world = state.world
    places = set(world.neighbours) | set(world.node_names) | set(world.descriptions)
    places.update(n for ns in world.neighbours.values() for n in ns)
    ids = {i for i in entity_ids if i not in places}
    return ids | named_slugs(state, text)


def unsupported_claims(
    state: GameState,
    text: str,
    entity_ids: Iterable[str],
    stated: Iterable[ClaimKind] = (),
    since: int | None = None,
) -> tuple[ClaimKind, ...]:
    """The deed kinds the fact claims that no engine event since `since` did to what it names."""
    kinds = (claim_kinds(text) | frozenset(stated)) & DEED_KINDS
    if not kinds:
        return ()
    targets = _targets(state, text, entity_ids)
    if not targets:
        return ()
    start = claim_window(state) if since is None else since
    changed = state.world.changed
    return tuple(
        sorted(k for k in kinds if not any(changed.get(f"{k}:{t}", -1) >= start for t in targets))
    )
