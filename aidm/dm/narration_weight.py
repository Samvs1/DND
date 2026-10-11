"""How much the narrator says, and what it may claim (M19.1, owner playtest 2026-10-10).

The engine, not the model, sets how important a beat is. `weight_for(events)` is MAJOR for a fight
starting or ending, a death or revival, arriving somewhere, a discovery, a revealed secret, a level,
a quest completed or failed, a long rest or the epilogue; NORMAL for any other change; MINOR when
nothing meaningful changed or the only outcome is a failed check or a miss. `style_for(weight)`
asks for 1-2 / 2-3 / 3-5 sentences with a word ceiling, and `max_tokens_for(weight)` bounds the
stream. Every style forbids reusing what was already narrated (owner: the same images came back
in every line). `truth_notes(events)` adds authoritative lines where the model tends to invent:
nothing changed (describe the attempt only), a fight that has just begun (no blow landed) and
an encounter offer (M20.6: the foes arrive; nobody acts until the party chooses).

Public API: `NarrationWeight`, `weight_for`, `style_for`, `segment_style_for`, `max_tokens_for`,
`truth_notes`, `NOTHING_CHANGED`, `FIGHT_JUST_BEGAN`, `OFFER_STANDOFF`.
"""

from collections.abc import Sequence
from enum import StrEnum

from aidm.models.combat_events import AttackRolled
from aidm.models.events import AnyEvent, CheckResolved
from aidm.models.world_events import QuestUpdated


class NarrationWeight(StrEnum):
    MINOR = "minor"
    NORMAL = "normal"
    MAJOR = "major"


# Engine bookkeeping that is not an outcome the players would notice.
_BOOKKEEPING = frozenset(
    {
        "fact_recorded",
        "dice_rolled",
        "narration_recorded",
        "scene_summarised",
        "node_described",
        "economy_changed",
        "turn_started",
        "turn_ended",
        "hostile_act_pending",
        "level_up_ready",
        "difficulty_set",
    }
)
_MAJOR = frozenset(
    {
        "encounter_started",
        "encounter_ended",
        "creature_died",
        "creature_revived",
        "party_moved",
        "secret_revealed",
        "level_gained",
        "feature_introduced",
        "feature_discovered",
        "long_rest_taken",
        "epilogue_written",
    }
)
_FINAL_QUEST = frozenset({"completed", "failed"})
_BLOWS = frozenset({"attack_rolled", "damage_taken", "spell_cast", "monster_action_used"})

_SIZE = {
    NarrationWeight.MINOR: "Write 1 or 2 short sentences, under 40 words in all.",
    NarrationWeight.NORMAL: "Write 2 or 3 sentences, under 70 words in all.",
    NarrationWeight.MAJOR: "Write 3 to 5 sentences, under 110 words in all.",
}
_TOKENS = {NarrationWeight.MINOR: 250, NarrationWeight.NORMAL: 350, NarrationWeight.MAJOR: 500}
_RULES = (
    "Prose only: no lists, headings or name lists. Address the party in the second person plural"
    " or name the characters. State no mechanics numbers: no dice totals, DCs, damage amounts,"
    " hit points or XP. Describe exactly the resolved outcomes below and nothing more: a failed"
    " attempt is told as a failure; never invent loot, gold, wounds, deaths or movement."
)
NO_REPEAT = (
    "Say something new or say less. Do not reuse images, details or phrases from the lines"
    " marked 'Narrated:' or from the place's established description, and do not describe the"
    " place, its landmarks or a person's mannerisms again unless they change or matter to this"
    " outcome."
)
NOTHING_CHANGED = (
    "No rule applied and nothing in the world changed. Describe only the attempt and how the"
    " scene answers it. Do not say that anyone moved to another place or zone, picked up, took,"
    " gained or lost anything, or that anyone was hurt, fell or died."
)
FIGHT_JUST_BEGAN = (
    "The fight has only just begun: describe the standoff and where everyone stands. No blow has"
    " landed yet; nobody is hurt, down or beaten."
)
OFFER_STANDOFF = (
    "Danger has appeared, but nothing has happened yet: the party has not chosen whether to fight,"
    " strike first, slip away or talk. Describe only the foes arriving (exactly as many as listed)"
    " and the tension. No hero acts, nobody attacks, casts, hits, falls or flees."
)


def _types(events: Sequence[AnyEvent]) -> list[str]:
    return [e.type for e in events if e.type not in _BOOKKEEPING]


def _only_setbacks(events: Sequence[AnyEvent]) -> bool:
    """True when every outcome is a failed check or a missed attack."""
    for event in events:
        if event.type in _BOOKKEEPING:
            continue
        if isinstance(event, CheckResolved) and not event.result.success:
            continue
        if isinstance(event, AttackRolled) and not event.hit:
            continue
        return False
    return True


def weight_for(events: Sequence[AnyEvent]) -> NarrationWeight:
    types = _types(events)
    if not types or _only_setbacks(events):
        return NarrationWeight.MINOR
    if any(t in _MAJOR for t in types):
        return NarrationWeight.MAJOR
    quests = [e for e in events if isinstance(e, QuestUpdated)]
    if any(q.quest.state.value in _FINAL_QUEST for q in quests):
        return NarrationWeight.MAJOR
    return NarrationWeight.NORMAL


def style_for(weight: NarrationWeight) -> str:
    return f"{_SIZE[weight]} {_RULES} {NO_REPEAT}"


def segment_style_for(weight: NarrationWeight) -> str:
    """The style for consecutive enemy turns told as one passage."""
    return (
        f"Describe the consecutive enemy turns below as ONE flowing passage, in order, fast and"
        f" vivid. {_SIZE[weight]} State no mechanics numbers. Fallen creatures stay fallen."
        f" {NO_REPEAT}"
    )


def max_tokens_for(weight: NarrationWeight) -> int:
    return _TOKENS[weight]


def truth_notes(events: Sequence[AnyEvent]) -> list[str]:
    types = _types(events)
    notes: list[str] = []
    if not types:
        notes.append(NOTHING_CHANGED)
    if "encounter_started" in types and not any(t in _BLOWS for t in types):
        notes.append(FIGHT_JUST_BEGAN)
    if "encounter_offered" in types and "encounter_started" not in types:
        notes.append(OFFER_STANDOFF)  # M20.6: the stirge was "blasted" before any choice
    return notes
