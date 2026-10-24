"""Result checks of the prose guard: a result told other than the engine resolved it (M31.1c,
docs/playtests/M31_round4.md V17). Round 4 told the mimic "twisting aside" from a Sacred Flame
that burned it (full 1321) and an Acid Arrow that missed but still burned the grick for half
damage as a clean miss "spattering against the black stone" (full 1404). Each check reads ONE
sentence against the turn's `FightLedger` (`aidm.dm.fight_ledger`); vocabulary is data
(data/bg3/guard_lexicon.json):
- `hit_told_missed`: an `evade_claims` phrase ("twists aside", "dodges") whose subject lost hit
  points in these events and evaded nothing (no missed attack at it, no harmless save);
- `miss_harm_untold`: a `miss_claims` phrase for an attacker whose missed attack still dealt
  damage, in a sentence that tells no harm at all (`partial_harm_claims`, `harm_claims`,
  `hit_claims`: "still splashes", "burns").
Harm told on a creature immune to it is `aidm.dm.guard_blows` (IMMUNE_HARMED).

Public API: `result_truth(text, tokens, found, scene) -> list[Violation]`.
"""

from aidm.dm.guard_mentions import Mention, attacker, blow, claims, names_of
from aidm.dm.guard_scene import GuardScene
from aidm.dm.guard_text import Token, find_phrases
from aidm.dm.guard_types import Violation, ViolationKind


def _hit_told_missed(
    text: str, tokens: list[Token], found: list[Mention], scene: GuardScene
) -> list[Violation]:
    ledger = scene.turn.fight
    for m in claims(text, tokens, scene.lexicon.evade_claims, scene):
        who = attacker(text, found, m.start())
        if who is None or not who.ids or not who.ids <= ledger.struck:
            continue
        if who.ids & ledger.dodged:
            continue
        detail = f"{names_of(scene, who.ids)} was hit and hurt in these events: tell the hit"
        return blow(ViolationKind.HIT_TOLD_MISSED, m.group(0), detail)
    return []


def _miss_harm_untold(
    text: str, tokens: list[Token], found: list[Mention], scene: GuardScene
) -> list[Violation]:
    ledger, lex = scene.turn.fight, scene.lexicon
    if not ledger.grazed or find_phrases(
        text, lex.partial_harm_claims | lex.harm_claims | lex.hit_claims
    ):
        return []
    for m in claims(text, tokens, lex.miss_claims, scene):
        who = attacker(text, found, m.start())
        if who is not None and who.ids & ledger.grazed:
            detail = (
                f"{names_of(scene, who.ids)} missed, but the miss still dealt half damage:"
                " tell the splash or graze that hurt the target"
            )
            return blow(ViolationKind.MISS_HARM_UNTOLD, m.group(0), detail)
    return []


def result_truth(
    text: str, tokens: list[Token], found: list[Mention], scene: GuardScene
) -> list[Violation]:
    return [
        *_hit_told_missed(text, tokens, found, scene),
        *_miss_harm_untold(text, tokens, found, scene),
    ]
