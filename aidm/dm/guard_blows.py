"""Per-creature fight checks of the prose guard (M29.7b, docs/playtests/M29_round2.md R19).

M29.5c's G6 check covered only fights where no blow was resolved. Round 2 told foe charges and
claw hits beside a hero's lone miss, shafts finding their mark in heroes nobody shot, a kill
credited to the wrong hero and a bolt "skipping off" a foe it hit. Each check reads ONE sentence
against the turn's `FightLedger` (`aidm.dm.fight_ledger`); vocabulary is data
(data/bg3/guard_lexicon.json):
- `phantom_blows`: a creature told attacking (the subject of a `strike_claims` phrase, or "X's
  bolt/claws/spell" beside a blow, hit, miss or kill phrase) that made no blow in these events;
- `phantom_hits`: a creature told hit (right after a `hit_claims` phrase: "clubs Elowen", "find
  their mark in Elowen", or "Rook takes a graze") that lost no hit points in these events;
- `false_misses`: a `miss_claims` phrase ("skips off", "goes wide") for an attacker whose every
  attack of these events hit;
- `wrong_killers`: a kill phrase tied to "X's bolt" when someone else dealt the killing damage;
- M29.9c (round 3 T4): attempts and near misses count as blows (`attempt_claims`: "springs at
  Tamsin", "jaws snapping shut a hand's breadth from her wrist");
  a spell's harm (`harm_claims`: "scorching its hide") on a creature that lost no hit points (a
  saved Sacred Flame) is a phantom hit; `phantom_falls`: a `fall_claims` phrase ("slumping into the
  cinders", "sends it crashing") about a creature none of whose possible meanings fell: one that
  fled (FLED_TOLD_DEAD) or one still standing (UNHURT_DECLARED_DOWN).
- M31.1c (round 4 V17): a spell's harm phrase after "X's flame" counts as X attacking ("Tamsin's
  sacred flame sears" when Elowen cast it); an `aimed_claims` phrase ("feints toward", "snaps
  toward") is an attempt only when a creature follows it ("feints toward Rook", never "the head
  snaps toward the sound"); the result checks of `aidm.dm.guard_results` (a hit
  told as a miss, harm on an immune foe, a damaging miss told clean) and the foe count of
  `aidm.dm.guard_counts` run here too.
- M32.1b (round 5 X12): a living foe told fleeing, a helpless foe told acting, blows told in the
  wrong order and a weapon told hitting someone unhurt (`aidm.dm.guard_foes`).
Who a sentence names and which claims it makes: `aidm.dm.guard_mentions`.

Public API: `fight_truth(sentence, tokens, scene, context) -> list[Violation]`.
"""

import re

from aidm.dm.guard_counts import foe_counts
from aidm.dm.guard_foes import foe_truth
from aidm.dm.guard_mentions import (
    AFTER_REACH,
    Mention,
    attacker,
    blow,
    claims,
    names_of,
    read_mentions,
    subject_of,
    target,
)
from aidm.dm.guard_pronoun import PronounContext
from aidm.dm.guard_results import result_truth
from aidm.dm.guard_scene import GuardScene
from aidm.dm.guard_text import Token, find_phrases, plain
from aidm.dm.guard_types import Violation, ViolationKind

_KILL_REACH = 40


def _armed(text: str, tokens, mentions: list[Mention], scene: GuardScene) -> list[Mention]:
    """ "X's bolt" told as attacking: a blow, hit or miss phrase right after it, or a kill phrase
    right before it ("folds around Brienne's bolt")."""
    lex = scene.lexicon
    told = lex.strike_claims | lex.hit_claims | lex.miss_claims | lex.attempt_claims
    after = list(claims(text, tokens, told | lex.harm_claims, scene))
    kills = list(claims(text, tokens, lex.kill_claims | lex.blow_claims, scene))
    out: list[Mention] = []
    for n in mentions:
        if not n.weapon or not n.ids:
            continue
        follows = any(0 <= m.start() - n.end <= AFTER_REACH for m in after)
        preceded = any(not text[m.end() : n.start].strip() for m in kills if m.end() <= n.start)
        if follows or preceded:
            out.append(n)
    return out


def _phantom_blows(text: str, tokens, mentions, scene: GuardScene) -> list[Violation]:
    ledger, lex = scene.turn.fight, scene.lexicon
    told: list[tuple[str, Mention]] = []
    phrases = lex.strike_claims | lex.hit_claims | lex.attempt_claims | lex.aimed_claims
    for m in claims(text, tokens, phrases, scene):
        aimed = m.group(0).casefold() in lex.aimed_claims
        at = target(text, m.end(), mentions) if aimed else None
        if aimed and (at is None or not at.ids):
            continue  # M31.1c: "feints toward Rook" is an attempt, "snaps toward the sound" is not
        who = attacker(text, mentions, m.start())
        if who is not None and who.ids:
            told.append((m.group(0), who))
    told += [(text[n.start : n.end], n) for n in _armed(text, tokens, mentions, scene)]
    for span, who in told:
        if not who.ids & ledger.acted:
            detail = (
                f"{names_of(scene, who.ids)} made no attack in these events: tell no blow by them"
            )
            return blow(ViolationKind.PHANTOM_BLOW, span, detail)
    return []


def _grazed(text: str, mentions: list[Mention], scene: GuardScene) -> list[tuple[str, Mention]]:
    nouns = "|".join(sorted(scene.lexicon.graze_nouns))
    out: list[tuple[str, Mention]] = []
    for n in mentions:
        m = re.match(rf"\s+takes\s+an?\s+(?:[a-z-]+\s+){{0,2}}?({nouns})\b", text[n.end :], re.I)
        if m is not None and n.subject:
            out.append((m.group(1), n))
    return out


def _phantom_hits(text: str, tokens, mentions, scene: GuardScene) -> list[Violation]:
    ledger = scene.turn.fight
    hits = [
        (m.group(0), target(text, m.end(), mentions))
        for m in claims(text, tokens, scene.lexicon.hit_claims | scene.lexicon.harm_claims, scene)
    ]
    for span, who in [*hits, *_grazed(text, mentions, scene)]:
        if who is None or not who.ids or who.ids & ledger.struck:
            continue
        immune = sorted({ledger.immune[i] for i in who.ids if i in ledger.immune})
        if immune:  # M31.1c V17: Acid Arrow on the acid-immune mimic told as a wound
            detail = f"{names_of(scene, who.ids)} is immune to {', '.join(immune)}: no harm"
            return blow(ViolationKind.IMMUNE_HARMED, span, detail)
        detail = f"{names_of(scene, who.ids)} lost no hit points in these events: no blow landed"
        return blow(ViolationKind.PHANTOM_HIT, span, detail)
    return []


def _false_misses(text: str, tokens, mentions, scene: GuardScene) -> list[Violation]:
    ledger = scene.turn.fight
    for m in claims(text, tokens, scene.lexicon.miss_claims, scene):
        who = attacker(text, mentions, m.start())
        if who is None or not who.ids or who.ids & ledger.missed_by:
            continue
        if who.ids & ledger.hit_by:
            detail = f"{names_of(scene, who.ids)} hit in these events: tell the hit, not a miss"
            return blow(ViolationKind.FALSE_MISS, m.group(0), detail)
    return []


def _wrong_killers(text: str, mentions: list[Mention], scene: GuardScene) -> list[Violation]:
    ledger, lex = scene.turn.fight, scene.lexicon
    if not ledger.killers:
        return []
    for m in find_phrases(text, lex.kill_claims | lex.blow_claims):
        armed = [n for n in mentions if n.weapon and n.ids]
        near = [
            n for n in armed if min(abs(n.start - m.end()), abs(m.start() - n.end)) <= _KILL_REACH
        ]
        if not near:
            continue
        who = min(near, key=lambda n: min(abs(n.start - m.end()), abs(m.start() - n.end)))
        if who.ids & ledger.acted and not who.ids & ledger.killers:
            killers = names_of(scene, ledger.killers)
            detail = f"the killing blow was {killers}'s, not {names_of(scene, who.ids)}'s"
            return blow(ViolationKind.WRONG_KILLER, text[who.start : who.end], detail)
    return []


def _phantom_falls(text: str, tokens, mentions, scene: GuardScene) -> list[Violation]:
    ledger = scene.turn.fight
    for m in claims(text, tokens, scene.lexicon.fall_claims, scene, past=False):
        who = subject_of(text, mentions, m.start(), m.end())
        if who is None or not who.ids or who.ids & ledger.downed:
            continue
        if not who.ids <= ledger.fled | ledger.standing:
            continue  # it may mean one that is already down
        names = names_of(scene, who.ids)
        if who.ids & ledger.fled:
            detail = f"{names} fled the fight alive: never tell them killed or fallen"
            return blow(ViolationKind.FLED_TOLD_DEAD, m.group(0), detail)
        detail = f"{names} still stands: no engine event dropped them"
        return blow(ViolationKind.UNHURT_DECLARED_DOWN, m.group(0), detail)
    return []


def fight_truth(
    sentence: str, tokens: list[Token], scene: GuardScene, context: PronounContext
) -> list[Violation]:
    truth = scene.turn
    ledger = truth.fight
    if not truth.checked or not ledger.active:
        return []
    if not (truth.in_fight or ledger.acted or ledger.struck):
        return []
    text = plain(sentence)
    found = read_mentions(text, ledger, scene, context)
    counted = foe_counts(text, scene)
    if find_phrases(text, scene.lexicon.attack_hedges):
        return counted
    return [
        *_phantom_blows(text, tokens, found, scene),
        *_phantom_hits(text, tokens, found, scene),
        *_false_misses(text, tokens, found, scene),
        *_wrong_killers(text, found, scene),
        *_phantom_falls(text, tokens, found, scene),
        *result_truth(text, tokens, found, scene),
        *foe_truth(text, tokens, found, scene),
        *counted,
    ]
