"""The facts the narrator may tell about a turn, beyond the event lines (M29.5c honest storyteller).

M29 round 1 showed the storyteller telling what the engine never did: a sale and payment no
shop made, a potion the hero never had, a hand-over that did not happen, a foe "lying still"
at 8 of 32 HP, "rat-bites" on heroes at full health, a wolf springing before any roll, the
wrong weapon. `turn_facts(state, events, actor_id=..., player_text=...)` states, from the
events already applied to `state`, what the engine resolved and what it did not, phrased so the
model tells attempts as attempts:
- the weapons of these attacks, and that no other weapon was used;
- who was hurt but still stands, who is down but alive, which foes still fight, who is unhurt;
- in a fight with no blow resolved: that nobody struck or was hurt;
- a thing the player used as the hero's own that the hero does not carry
  (`aidm.dm.guard_turn.claimed_things`): told as reached for and not found;
- a payment, sale, hand-over or lighting the player's words asked for that no event made;
- travel to a place the map does not know (G10): nobody goes anywhere, no other place stands in;
- M29.7b: who acted at whom with what outcome and who did nothing (`aidm.dm.fight_ledger`), and
  the world facts of `aidm.dm.turn_facts_world` (the place really reached, lights, pick-ups, the
  party's size and who is still hurt).
The same truth is enforced by THE guard (`aidm.dm.guard_turn`, `guard_truth`, `guard_goods`).

Public API: `turn_facts(state, events, *, actor_id, player_text) -> list[str]`.
"""

from collections import Counter
from collections.abc import Sequence

from aidm.data.guard_lexicon import guard_lexicon
from aidm.dm.fight_ledger import fight_lines
from aidm.dm.guard_text import find_phrases, plain
from aidm.dm.guard_turn import TurnTruth, turn_truth
from aidm.dm.turn_facts_world import world_facts
from aidm.dm.turn_world import TRAVEL
from aidm.dm.wording import attack_label, counted
from aidm.models import events as ev
from aidm.models.combat_events import AttackRolled
from aidm.models.encounter import EncounterStatus, Side
from aidm.models.state import GameState


def _weapon_facts(state: GameState, events: Sequence[ev.AnyEvent]) -> list[str]:
    used: dict[str, list[str]] = {}
    for e in events:
        if isinstance(e, AttackRolled) and e.attacker_id in state.creatures:
            name = state.creatures[e.attacker_id].name
            label = attack_label(e.attack)
            if label not in used.setdefault(name, []):
                used[name].append(label)
    if not used:
        return []
    told = "; ".join(f"{who}: {', '.join(labels)}" for who, labels in used.items())
    return [f"Weapons of these attacks (name only these, no other weapon): {told}."]


def _hurt_facts(state: GameState, events: Sequence[ev.AnyEvent], fled: frozenset[str]) -> list[str]:
    touched = list(  # M31.1c V17: a hit that did no harm (immune) hurts nobody
        dict.fromkeys(
            e.creature_id
            for e in events
            if (isinstance(e, ev.HpChanged) and e.delta < 0)
            or (isinstance(e, ev.DamageTaken) and e.hp_lost > 0)
        )
    )
    alive = [state.creatures[c] for c in touched if c in state.creatures and c not in fled]
    standing = [c.name for c in alive if not c.dead and c.hp > 0]
    down = [c.name for c in alive if not c.dead and c.hp <= 0 and c.pc is not None]
    out: list[str] = []
    if standing:
        out.append(
            f"Hurt but still standing and fighting (not down, not dead, not fled): "
            f"{', '.join(standing)}."
        )
    if down:
        out.append(f"Down at 0 HP but alive (not dead): {', '.join(down)}.")
    return out


def _foes_left(state: GameState) -> list[str]:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return []
    names = Counter(
        state.creatures[c.creature_id].name.lower()
        for c in enc.combatants.values()
        if c.side is Side.HOSTILE
        and c.withdrawn is None
        and c.creature_id in state.creatures
        and not state.creatures[c.creature_id].dead
        and state.creatures[c.creature_id].hp > 0
    )
    if not names:
        return []
    told = ", ".join(counted(name, n, digits=True) for name, n in sorted(names.items()))
    return [  # M31.1c V17: exactly these; round 4 told "robed cultists" beside one cultist
        f"Foes still standing in this fight (each is up and fighting): {told}; no other foe of"
        " any kind is here."
    ]


def _actor_facts(state: GameState, truth: TurnTruth, events: Sequence[ev.AnyEvent]) -> list[str]:
    """M29.7b (R19): who acted, at whom, with what outcome, and who did nothing this turn."""
    ledger = truth.fight
    if not ledger.active or not (truth.in_fight or ledger.acted):
        return []
    idle = sorted(
        {
            name
            for cid, name in ledger.names.items()
            if cid not in ledger.acted and cid in state.creatures and not state.creatures[cid].dead
        }
    )
    out: list[str] = []
    lines = fight_lines(state, ledger, events)
    if lines:
        out.append(f"Actions of these events, exactly as resolved: {'; '.join(lines)}.")
    if idle and ledger.acted:
        out.append(
            f"Did nothing in these events (no swing, shot, charge, bite, spell or hit from them;"
            f" tell no blow by them): {', '.join(idle)}."
        )
    return out


def _fight_facts(truth: TurnTruth) -> list[str]:
    out: list[str] = []
    if truth.in_fight and not truth.blows:
        out.append(
            "No attack was rolled in these events: nobody strikes, bites, lunges at, hits or"
            " hurts anyone; describe only positions and intent."
        )
    unhurt = sorted(set(truth.unhurt.values()))
    if unhurt:
        out.append(f"Unhurt (no wound, bite or blood on them): {', '.join(unhurt)}.")
    return out


def _asked(text: str, words: frozenset[str]) -> bool:
    return bool(find_phrases(text, words))


def _goods_facts(state: GameState, truth: TurnTruth, actor_id: str | None, text: str) -> list[str]:
    lex = guard_lexicon()
    hero = state.creatures.get(actor_id or "")
    who = hero.name if hero is not None else "The hero"
    out = [
        f"{c.hero} does not carry any {c.phrase}: {c.hero} reaches for it and finds none; it"
        " does not exist, so it cannot be used, drunk, thrown, lost or broken."
        for c in truth.claimed
    ]
    if _asked(text, lex.purchase_words | lex.payment_verbs) and not truth.paid:
        out.append(
            "No coin changed hands and nothing was bought or sold: every hero's gold and pack"
            " are unchanged; a sale happens only when the shop makes it."
        )
    if _asked(text, lex.handover_words) and not truth.handed:
        out.append(
            f"Nothing changed hands: {who} still holds everything they carried, and nobody"
            " took, accepted or now holds anything of theirs."
        )
    kindle = _asked(text, lex.kindle_words) and _asked(text, lex.light_nouns)
    if kindle and not truth.lit:
        out.append("No new light was lit by this action: no torch, lantern or candle caught flame.")
    return out


def _travel_facts(state: GameState, text: str, events: Sequence[ev.AnyEvent]) -> list[str]:
    m = TRAVEL.search(text)
    if m is None or any(e.type == "party_moved" for e in events):
        return []
    dest = m.group("dest").strip()
    known = [plain(n).casefold() for n in state.world.node_names.values()]
    if any(name in dest or dest in name for name in known):
        return []
    return [
        "The place the player named is not on the map: no way there is known, the party stays"
        " where it is, and no other place stands in for it."
    ]


def turn_facts(
    state: GameState,
    events: Sequence[ev.AnyEvent],
    *,
    actor_id: str | None = None,
    player_text: str | None = None,
) -> list[str]:
    truth = turn_truth(state, events, actor_id=actor_id, player_text=player_text)
    text = plain(player_text or "").casefold()
    out = [*_weapon_facts(state, events), *_hurt_facts(state, events, truth.fight.fled)]
    out += _foes_left(state)
    out += _actor_facts(state, truth, events) + _fight_facts(truth)
    if text:
        out += _goods_facts(state, truth, actor_id, text) + _travel_facts(state, text, events)
    out += world_facts(state, truth, text, events)
    return out
