"""Who did what to whom in this turn's fight events (M29.7b, docs/playtests/M29_round2.md R19).

Round 2 showed fight prose inventing blows per creature: a foe's charge and claw hit when no foe
acted, shafts that "find their mark" in heroes nobody shot, a kill credited to the wrong hero, a
bolt that "skips off" when the engine said hit. `fight_ledger(state, events)` freezes, from the
events already applied to `state`:
- `acted`: creature ids that made a blow (an attack, a spell, a monster action, damage dealt);
- `struck`: ids that lost hit points; `hit_by` / `missed_by`: attackers with a hit (or damage
  dealt) / with a missed attack; `downed`: ids that fell to 0 HP or died; `killers`: the sources of
  the damage that dropped them;
- `terms`: every word the prose may use for a creature in this fight (names, their distinctive
  words, the monster kind; generic foe words such as "creature" mean every foe), longest first;
- `foes`: the ids of the non-hero creatures in the fight;
- M29.9c (round 3 T4): `saved` (id -> spell: a save against that spell succeeded), `fled` (ids
  that fled the fight, alive), `standing` (ids alive above 0 HP, in the fight, with no
  `down_conditions` condition: they may not be told fallen).
- M31.1c (round 4 V17): `immune` (id -> the damage types it took nothing from, though rolled:
  Acid Arrow on the acid-immune mimic), `grazed` (attackers whose MISSED attack still dealt
  damage: half damage on a miss), `dodged` (ids that evaded something: the target of a missed
  attack, or a save that took no harm), `kinds` (each foe kind's head noun -> how many of it the
  fight holds, dead or alive, with the present NPCs whose name or role holds that word).
- M32.1b (round 5 X12): `helpless` (ids alive with a `helpless_conditions` condition: asleep,
  unconscious, paralyzed...), `rolls` (attacker -> hit flags of its attacks in order, for
  attackers with two or more: Scorching Ray's three rays).
- M31.2b (items 908): `feats` (foe id -> the text of what its stat block and this turn's events
  let it do, `aidm.dm.foe_feats`: a mephit may breathe frost, never split into shards).
Generic foe words (lexicon `foe_words`: "creature", "corpse") mean every foe.
M41.3 (round 7 Z6: "Elowen calls out and the party flees" removed only Elowen): when a hero
fled, `fight_lines` also names the heroes still in the fight (a hero flees only on their own
turn), so the telling never moves the whole party out (`_left_behind`).
`FightLedger()` (empty `terms`) switches the per-creature checks off.

Public API: `FightLedger`, `fight_ledger(state, events) -> FightLedger`,
`fight_lines(state, ledger, events) -> list[str]`.
"""

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from aidm.data.guard_lexicon import GuardLexicon, guard_lexicon
from aidm.dm.foe_feats import feat_texts
from aidm.dm.guard_text import plain
from aidm.dm.wording import attack_label
from aidm.models import events as ev
from aidm.models.checks import CheckKind
from aidm.models.combat_events import AttackRolled, MonsterActionUsed, SpellCast
from aidm.models.encounter import WithdrawReason
from aidm.models.encounter_events import CombatantWithdrew
from aidm.models.state import Creature, GameState

_MIN_WORD = 4


@dataclass(frozen=True)
class FightLedger:
    acted: frozenset[str] = frozenset()
    struck: frozenset[str] = frozenset()
    hit_by: frozenset[str] = frozenset()
    missed_by: frozenset[str] = frozenset()
    downed: frozenset[str] = frozenset()
    killers: frozenset[str] = frozenset()
    killed_by: tuple[tuple[str, str], ...] = ()  # (fallen id, source id of the killing damage)
    terms: tuple[tuple[str, frozenset[str]], ...] = ()
    foes: frozenset[str] = frozenset()
    names: dict[str, str] = field(default_factory=dict[str, str])
    saved: dict[str, str] = field(default_factory=dict[str, str])  # id -> spell id
    fled: frozenset[str] = frozenset()
    standing: frozenset[str] = frozenset()
    immune: dict[str, str] = field(default_factory=dict[str, str])
    grazed: frozenset[str] = frozenset()
    dodged: frozenset[str] = frozenset()
    kinds: dict[str, int] = field(default_factory=dict[str, int])
    helpless: frozenset[str] = frozenset()  # M32.1b X12: alive, asleep or otherwise helpless
    rolls: dict[str, tuple[bool, ...]] = field(default_factory=dict[str, tuple[bool, ...]])
    feats: dict[str, str] = field(default_factory=dict[str, str])  # M31.2b: foe id -> abilities

    @property
    def active(self) -> bool:
        return bool(self.terms)


def _fighters(state: GameState, events: Sequence[ev.AnyEvent]) -> list[Creature]:
    ids = {c.id for c in state.creatures.values() if c.pc is not None}
    if state.encounter is not None:
        ids |= {c.creature_id for c in state.encounter.combatants.values()}
    for e in events:
        for key in ("creature_id", "attacker_id", "target_id", "caster_id", "source_id"):
            value = getattr(e, key, None)
            if isinstance(value, str):
                ids.add(value)
    return [state.creatures[i] for i in sorted(ids) if i in state.creatures]


def _words(creature: Creature, lex: GuardLexicon) -> set[str]:
    name = plain(creature.name).casefold()
    words = {name}
    skip = lex.titles | lex.sentence_starters
    words |= {w for w in re.findall(r"[a-z]+", name) if len(w) >= _MIN_WORD and w not in skip}
    if creature.pc is None and creature.monster_index:
        kind = creature.monster_index.replace("-", " ")
        words |= {kind} | {w for w in kind.split() if len(w) >= _MIN_WORD and w not in skip}
    return words


def _terms(fighters: list[Creature], lex: GuardLexicon) -> tuple[tuple[str, frozenset[str]], ...]:
    found: dict[str, set[str]] = {}
    for creature in fighters:
        for word in _words(creature, lex):
            found.setdefault(word, set()).add(creature.id)
    foes = {c.id for c in fighters if c.pc is None}
    if foes:
        for word in lex.foe_words:
            found.setdefault(word, set()).update(foes)
    ordered = sorted(found.items(), key=lambda p: (-len(p[0]), p[0]))
    return tuple((term, frozenset(ids)) for term, ids in ordered)


def _blows(events: Sequence[ev.AnyEvent]) -> tuple[set[str], set[str], set[str]]:
    acted: set[str] = set()
    hit: set[str] = set()
    missed: set[str] = set()
    for e in events:
        if isinstance(e, AttackRolled):
            acted.add(e.attacker_id)
            (hit if e.hit else missed).add(e.attacker_id)
        elif isinstance(e, SpellCast):
            acted.add(e.caster_id)
        elif isinstance(e, MonsterActionUsed):
            acted.add(e.creature_id)
        elif isinstance(e, ev.DamageTaken) and e.source_id is not None and e.hp_lost > 0:
            acted.add(e.source_id)
            hit.add(e.source_id)
    return acted, hit, missed


def _falls(events: Sequence[ev.AnyEvent]) -> tuple[set[str], set[str], dict[str, str]]:
    struck: set[str] = set()
    downed: set[str] = set()
    killers: dict[str, str] = {}
    source: dict[str, str] = {}
    for e in events:
        if isinstance(e, ev.DamageTaken) and e.hp_lost > 0:
            struck.add(e.creature_id)
            if e.source_id is not None:
                source[e.creature_id] = e.source_id
        elif isinstance(e, ev.HpChanged) and e.delta < 0:
            struck.add(e.creature_id)
            if e.new_hp == 0:
                downed.add(e.creature_id)
                if e.creature_id in source:
                    killers[e.creature_id] = source[e.creature_id]
        elif isinstance(e, ev.CreatureDied):
            downed.add(e.creature_id)
    return struck, downed, killers


def _saves(events: Sequence[ev.AnyEvent]) -> dict[str, str]:
    """Target id -> spell id for every save that succeeded against a spell of these events."""
    out: dict[str, str] = {}
    spell: SpellCast | None = None
    for e in events:
        if isinstance(e, SpellCast):
            spell = e
        elif isinstance(e, AttackRolled | MonsterActionUsed):
            spell = None
        elif isinstance(e, ev.CheckResolved) and spell is not None:
            result = e.result
            if (
                result.kind is CheckKind.SAVE
                and result.success
                and e.creature_id in spell.target_ids
            ):
                out[e.creature_id] = spell.spell_id
    return out


def _fled(state: GameState, events: Sequence[ev.AnyEvent]) -> set[str]:
    fled = {
        e.creature_id
        for e in events
        if isinstance(e, CombatantWithdrew) and e.reason is WithdrawReason.FLED
    }
    if state.encounter is not None:
        fled |= {
            c.creature_id
            for c in state.encounter.combatants.values()
            if c.withdrawn is WithdrawReason.FLED
        }
    return fled


def _standing(fighters: list[Creature], fled: set[str], lex: GuardLexicon) -> frozenset[str]:
    return frozenset(
        c.id
        for c in fighters
        if not c.dead
        and c.hp > 0
        and c.id not in fled
        and not {k.name for k in c.conditions} & lex.down_conditions
    )


def _helpless(fighters: list[Creature], lex: GuardLexicon) -> frozenset[str]:
    return frozenset(
        c.id
        for c in fighters
        if not c.dead and c.hp > 0 and {k.name for k in c.conditions} & lex.helpless_conditions
    )


def _rolls(events: Sequence[ev.AnyEvent]) -> dict[str, tuple[bool, ...]]:
    """Attacker -> hit or miss of each of its attacks, in order, when it made two or more."""
    out: dict[str, list[bool]] = {}
    for e in events:
        if isinstance(e, AttackRolled):
            out.setdefault(e.attacker_id, []).append(e.hit)
    return {k: tuple(v) for k, v in out.items() if len(v) >= 2}


def _immune(events: Sequence[ev.AnyEvent]) -> dict[str, str]:
    out: dict[str, str] = {}
    for e in events:
        if isinstance(e, ev.DamageTaken) and e.hp_lost == 0 and e.temp_absorbed == 0:
            types = [p.damage_type.value for p in e.parts if p.rolled > 0 and p.taken == 0]
            if types:
                out[e.creature_id] = ", ".join(dict.fromkeys(types))
    return out


def _misses(events: Sequence[ev.AnyEvent], saved: dict[str, str], struck: set[str]):
    """(grazed attackers, dodging targets): a miss that still dealt damage, and who evaded."""
    grazed: set[str] = set()
    dodged = {cid for cid in saved if cid not in struck}
    missed: dict[str, str] = {}  # attacker -> target of its last missed attack
    for e in events:
        if isinstance(e, AttackRolled):
            missed.pop(e.attacker_id, None)
            if not e.hit:
                missed[e.attacker_id] = e.target_id
                dodged.add(e.target_id)
        elif isinstance(e, ev.DamageTaken) and e.source_id in missed and e.hp_lost > 0:
            grazed.add(e.source_id)
    return frozenset(grazed), frozenset(dodged)


def _head(creature: Creature) -> str:
    kind = (creature.monster_index or creature.name).replace("-", " ").casefold()
    return kind.split()[-1] if kind.split() else ""


def _kinds(state: GameState, fighters: list[Creature]) -> dict[str, int]:
    heads = Counter(_head(c) for c in fighters if c.pc is None)
    node = state.world.current_node
    for npc in state.world.npcs.values():
        if npc.node_id == node and not npc.dead:
            words = set(re.findall(r"[a-z]+", f"{npc.name} {npc.role}".casefold()))
            for head in words & set(heads):
                heads[head] += 1
    return {head: n for head, n in heads.items() if len(head) >= _MIN_WORD - 1}


def fight_ledger(state: GameState, events: Sequence[ev.AnyEvent]) -> FightLedger:
    lex = guard_lexicon()
    fighters = _fighters(state, events)
    if not any(c.pc is None for c in fighters):
        return FightLedger()
    acted, hit, missed = _blows(events)
    struck, downed, killers = _falls(events)
    fled = _fled(state, events)
    saved = _saves(events)
    grazed, dodged = _misses(events, saved, struck)
    return FightLedger(
        acted=frozenset(acted),
        struck=frozenset(struck),
        hit_by=frozenset(hit),
        missed_by=frozenset(missed),
        downed=frozenset(downed),
        killers=frozenset(killers.values()),
        killed_by=tuple(sorted(killers.items())),
        terms=_terms(fighters, lex),
        foes=frozenset(c.id for c in fighters if c.pc is None),
        names={c.id: c.name for c in fighters},
        saved=saved,
        fled=frozenset(fled),
        standing=_standing(fighters, fled, lex),
        immune=_immune(events),
        grazed=grazed,
        dodged=dodged,
        kinds=_kinds(state, fighters),
        helpless=_helpless(fighters, lex),
        rolls=_rolls(events),
        feats=feat_texts(fighters, events),
    )


def _name(state: GameState, cid: str) -> str:
    creature = state.creatures.get(cid)
    return creature.name if creature is not None else cid


def fight_lines(state: GameState, ledger: FightLedger, events: Sequence[ev.AnyEvent]) -> list[str]:
    """One short line per blow, for the narrator's facts: who, with what, at whom, the outcome."""
    out: list[str] = []
    for e in events:
        if isinstance(e, AttackRolled):
            outcome = "hit" if e.hit else "missed"
            if not e.hit and e.attacker_id in ledger.grazed and e.target_id in ledger.struck:
                outcome = "missed, but the miss still dealt half damage: the target is hurt"
            line = f"{_name(state, e.attacker_id)}: {attack_label(e.attack)} at"
            out.append(f"{line} {_name(state, e.target_id)}, {outcome}")
        elif isinstance(e, SpellCast):
            targets = ", ".join(_name(state, t) for t in e.target_ids) or "an area"
            out.append(f"{_name(state, e.caster_id)}: {e.spell_id.replace('-', ' ')} at {targets}")
    for cid, spell in sorted(ledger.saved.items()):
        harm = "partial harm only" if cid in ledger.struck else "no harm: not hit, not burned"
        out.append(f"{_name(state, cid)} saved against {spell.replace('-', ' ')}: {harm}")
    out += [
        f"{_name(state, cid)} is immune to {kinds}: it took no harm, no wound and no burn from it"
        for cid, kinds in sorted(ledger.immune.items())
    ]
    out += [
        f"{_name(state, e.creature_id)} fled the fight alive (not dead, not down)"
        for e in events
        if isinstance(e, CombatantWithdrew) and e.reason is WithdrawReason.FLED
    ]
    out += _left_behind(state, events)
    killers = dict(ledger.killed_by)
    for cid in sorted(ledger.downed):
        by = killers.get(cid)
        tail = f" (the killing blow was {_name(state, by)}'s)" if by is not None else ""
        out.append(f"{_name(state, cid)} fell{tail}")
    return out


def _left_behind(state: GameState, events: Sequence[ev.AnyEvent]) -> list[str]:
    """M41.3: after a hero fled, the heroes still in the fight."""
    enc = state.encounter
    fled = [
        e.creature_id
        for e in events
        if isinstance(e, CombatantWithdrew) and e.reason is WithdrawReason.FLED
    ]
    heroes = [c for cid in fled if (c := state.creatures.get(cid)) is not None and c.pc is not None]
    if not heroes or enc is None:
        return []
    staying = [
        c.name
        for cid, fighter in enc.combatants.items()
        if fighter.withdrawn is None
        and (c := state.creatures.get(cid)) is not None
        and c.pc is not None
        and not c.dead
    ]
    if not staying:
        return []
    verb = "is" if len(staying) == 1 else "are"
    return [f"{', '.join(staying)} {verb} still in the fight (a hero flees only on their own turn)"]
