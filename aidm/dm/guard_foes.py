"""Foe-state fight checks of the prose guard (M32.1b, docs/playtests/M31_round5.md X12).

Round 5 told rats at 1 of 24 HP and bats at 22 of 22 "scattering into the dark" (full 139,
371), a cultist under Sleep "tracking Brienne, blade low" and "lifting his blade" (full 400,
424, 450), Scorching Ray's three rays in the wrong order (hit, miss, hit told as hit, hit,
miss: typed 1320) and "His next javelin takes Rook across the ribs" when nobody struck Rook
(typed 682). Each check reads ONE sentence against the turn's `FightLedger`
(`aidm.dm.fight_ledger`); vocabulary is data (data/bg3/guard_lexicon.json):
- `fled_alive`: a `flee_claims` phrase ("turns tail", "flees"), or a `scatter_claims` word
  followed by a `flight_directions` word ("scatter into the dark"; "scatter from his reach" is a
  dodge, "scatters ash" moves a thing), about foes all still standing in the fight (none fled:
  `CombatantWithdrew` FLED);
- `helpless_acting`: an `alert_claims`, `rise_claims`, strike or attempt phrase whose subject
  is helpless (`FightLedger.helpless`: asleep, unconscious, paralyzed ...) and not standing;
- `wrong_order`: with ONE attacker that made two or more attacks (`FightLedger.rolls`), an
  ordinal ("first", "second", "third": `ordinal_words`) tied to a hit phrase (`ray_hit_claims`,
  landing on someone) for an attack that missed, or to a miss phrase (`ray_miss_claims`) for
  one that hit;
- `weapon_hits`: a weapon or attack noun right before an `armed_verbs` verb ("javelin takes")
  whose target lost no hit points in these events (a phantom hit; "his" hides the attacker).
- M31.2b (round 3 items 908): `invented_feats`: a foe told doing a special ability or a
  transformation (a `foe_feats` row's `claims`: "splitting into", "turns invisible", "takes
  wing", "summons") that its stat block and this turn's events do not hold (none of the row's
  `support` stems starts a word of `FightLedger.feats`, `aidm.dm.foe_feats`); the subject must be
  the foe itself ("its growl splits into two notes" is about the growl), and a foe with no stat
  block is not judged.
Who a sentence names: `aidm.dm.guard_mentions`.

Public API: `foe_truth(text, tokens, mentions, scene) -> list[Violation]`.
"""

import re

from aidm.dm.guard_mentions import Mention, attacker, blow, claims, names_of, subject_of, target
from aidm.dm.guard_scene import GuardScene
from aidm.dm.guard_text import Token, find_phrases
from aidm.dm.guard_types import Violation, ViolationKind


def _fled_alive(
    text: str, tokens: list[Token], mentions: list[Mention], scene: GuardScene
) -> list[Violation]:
    ledger, lex = scene.turn.fight, scene.lexicon
    living = ledger.standing & ledger.foes
    told = [*claims(text, tokens, lex.flee_claims, scene, past=False)]
    for m in claims(text, tokens, lex.scatter_claims, scene, past=False):
        after = re.findall(r"[a-z']+", text[m.end() : m.end() + 16].casefold())[:1]
        if after and after[0] in lex.flight_directions:  # "scatter into the dark"; never
            told.append(m)  # "scatter from his reach" (a dodge) or "scatters ash" (a thing)
    for m in told:
        who = subject_of(text, mentions, m.start(), m.end())
        if who is None or not who.ids or not who.ids <= living:
            continue
        detail = f"{names_of(scene, who.ids)} is still in the fight: no engine event made it flee"
        return blow(ViolationKind.FLED_ALIVE, m.group(0), detail)
    return []


def _helpless_acting(
    text: str, tokens: list[Token], mentions: list[Mention], scene: GuardScene
) -> list[Violation]:
    ledger, lex = scene.turn.fight, scene.lexicon
    if not ledger.helpless:
        return []
    phrases = lex.alert_claims | lex.rise_claims | lex.strike_claims | lex.attempt_claims
    for m in claims(text, tokens, phrases, scene):
        who = attacker(text, mentions, m.start())
        if who is None or not who.ids & ledger.helpless or who.ids & ledger.standing:
            continue
        names = names_of(scene, who.ids & ledger.helpless)
        detail = f"{names} is helpless (asleep or senseless): it does not act, watch or rise"
        return blow(ViolationKind.HELPLESS_ACTING, m.group(0), detail)
    return []


def _struck_after(text: str, end: int, mentions: list[Mention]) -> bool:
    """A hit phrase lands on someone: a creature right after it, or "her/his/its" + a word."""
    if target(text, end, mentions) is not None:
        return True
    return re.match(r"\s+(?:her|his|its|their)\s+[a-z-]+", text[end:], re.IGNORECASE) is not None


def _first_claim(
    text: str, start: int, end: int, mentions: list[Mention], scene: GuardScene
) -> tuple[str, bool] | None:
    """The first hit or miss phrase between `start` and `end`: (phrase, told as a hit); a hit
    phrase counts only when it lands on someone ("scorches the water beside it" is no hit)."""
    lex = scene.lexicon
    segment = text[start:end]
    found = [
        (m.start(), m.group(0), True)
        for m in find_phrases(segment, lex.ray_hit_claims)
        if _struck_after(text, start + m.end(), mentions)
    ]
    found += [(m.start(), m.group(0), False) for m in find_phrases(segment, lex.ray_miss_claims)]
    if not found:
        return None
    _, phrase, hit = min(found)
    return phrase, hit


def _wrong_order(text: str, mentions: list[Mention], scene: GuardScene) -> list[Violation]:
    ledger, ordinals = scene.turn.fight, scene.lexicon.ordinal_words
    if len(ledger.rolls) != 1 or not ordinals:
        return []
    ((who, rolls),) = ledger.rolls.items()
    words = "|".join(re.escape(w) for w in sorted(ordinals, key=len, reverse=True))
    marks = list(re.finditer(rf"\b({words})\b", text, re.IGNORECASE))
    for i, mark in enumerate(marks):
        n = ordinals[mark.group(1).casefold()]
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        told = _first_claim(text, mark.end(), end, mentions, scene) if n <= len(rolls) else None
        if told is None or told[1] == rolls[n - 1]:
            continue
        name = ledger.names.get(who, who)
        landed = "hit" if rolls[n - 1] else "missed"
        detail = f"{name}'s {mark.group(1).casefold()} attack {landed}: tell each in its order"
        return blow(ViolationKind.WRONG_ORDER, told[0], detail)
    return []


def _weapon_hits(text: str, mentions: list[Mention], scene: GuardScene) -> list[Violation]:
    ledger, lex = scene.turn.fight, scene.lexicon
    if not lex.armed_verbs:
        return []
    nouns = "|".join(re.escape(n) for n in sorted(lex.attack_nouns | lex.weapon_nouns))
    verbs = "|".join(re.escape(v) for v in sorted(lex.armed_verbs, key=len, reverse=True))
    for m in re.finditer(rf"\b(?:{nouns})s?\s+(?:{verbs})\b", text, re.IGNORECASE):
        who = target(text, m.end(), mentions)
        if who is None or not who.ids or who.ids & ledger.struck:
            continue
        detail = f"{names_of(scene, who.ids)} lost no hit points in these events: no blow landed"
        return blow(ViolationKind.PHANTOM_HIT, m.group(0), detail)
    return []


def _supported(ids: frozenset[str], stems: tuple[str, ...], feats: dict[str, str]) -> bool:
    """Any of the foes `ids` may mean holds the ability (or has no stat block: fail open)."""
    pattern = re.compile("|".join(rf"\b{re.escape(s)}" for s in stems))
    return any(i not in feats or pattern.search(feats[i]) for i in ids)


def _invented_feats(
    text: str, tokens: list[Token], mentions: list[Mention], scene: GuardScene
) -> list[Violation]:
    ledger = scene.turn.fight
    for feat in scene.lexicon.foe_feats.values():
        for m in claims(text, tokens, feat.claims, scene):
            who = subject_of(text, mentions, m.start(), m.end())
            if who is None or not who.ids or not who.ids <= ledger.foes:
                continue
            said = text[who.start : who.end].casefold()
            if said == "its" or said.endswith("'s"):
                continue  # "its growl splits into two notes": the growl, not the foe
            if _supported(who.ids, feat.support, ledger.feats):
                continue
            names = names_of(scene, who.ids)
            detail = f"{names} has no such ability in its stat block or these events"
            return blow(ViolationKind.INVENTED_FEAT, m.group(0), detail)
    return []


def foe_truth(
    text: str, tokens: list[Token], mentions: list[Mention], scene: GuardScene
) -> list[Violation]:
    return [
        *_fled_alive(text, tokens, mentions, scene),
        *_helpless_acting(text, tokens, mentions, scene),
        *_wrong_order(text, mentions, scene),
        *_weapon_hits(text, mentions, scene),
        *_invented_feats(text, tokens, mentions, scene),
    ]
