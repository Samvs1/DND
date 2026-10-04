"""Encounter XP budget: thresholds by party level, the group multiplier, picking and validating
monster lists (SPEC 9: encounters use the CR budget from party level).

The numbers are data (`aidm.data.encounter_tables.EncounterTables`, passed as an argument);
monster XP values come from the SRD stat blocks (`SrdMonster.xp`), also passed in.

Public API:
- `party_thresholds(levels, tables) -> dict[Difficulty, int]`: each tier summed over the party.
- `party_budget(levels, difficulty, tables) -> int`: one tier (4 level-1 PCs, medium: 200).
- `group_multiplier(monster_count, party_size, tables) -> float`: the step for the monster count,
  one step up for a small party, one step down for a large one.
- `adjusted_xp(monster_xps, party_size, tables) -> int`: summed XP x multiplier, rounded down.
- `rate_encounter(monster_xps, levels, tables) -> Difficulty | None`: the highest tier whose
  threshold the adjusted XP reaches (None: below easy, trivial).
- `check_encounter_budget(monster_xps, levels, tables) -> BudgetCheck`: `allowed` is False when the
  adjusted XP exceeds the party's deadly threshold (the DM tool rejects such a list).
- `pick_monsters(rng, budget, candidates, party_size, tables) -> list[str]`: repeatedly adds a
  random candidate (id -> XP; XP 0 entries ignored) among those that keep the adjusted XP within
  `budget`, until none fits or `tables.max_monsters` is reached. Deterministic for a seed
  (candidates are considered in sorted id order).
Errors: a level missing from the table or an empty party raises `ValueError` (caller bug).
"""

from collections.abc import Mapping, Sequence

from aidm.data.encounter_tables import EncounterTables
from aidm.models.encounter import BudgetCheck, Difficulty
from aidm.rules.dice import Rng


def party_thresholds(levels: Sequence[int], tables: EncounterTables) -> dict[Difficulty, int]:
    if not levels:
        raise ValueError("an encounter budget needs at least one party member")
    totals = dict.fromkeys(Difficulty, 0)
    for level in levels:
        row = tables.thresholds.get(level)
        if row is None:
            raise ValueError(f"no XP thresholds for level {level}")
        for tier in Difficulty:
            totals[tier] += row[tier.value]
    return totals


def party_budget(levels: Sequence[int], difficulty: Difficulty, tables: EncounterTables) -> int:
    return party_thresholds(levels, tables)[difficulty]


def group_multiplier(monster_count: int, party_size: int, tables: EncounterTables) -> float:
    if monster_count <= 0:
        return 1.0
    steps = tables.multiplier_steps
    index = max(i for i, s in enumerate(steps) if s.min_monsters <= monster_count)
    if party_size <= tables.small_party_max:
        index += 1
    elif party_size >= tables.large_party_min:
        index -= 1
    if index < 0:
        return tables.large_party_multiplier
    if index >= len(steps):
        return tables.small_party_top_multiplier
    return steps[index].multiplier


def adjusted_xp(monster_xps: Sequence[int], party_size: int, tables: EncounterTables) -> int:
    return int(sum(monster_xps) * group_multiplier(len(monster_xps), party_size, tables))


def rate_encounter(
    monster_xps: Sequence[int], levels: Sequence[int], tables: EncounterTables
) -> Difficulty | None:
    adjusted = adjusted_xp(monster_xps, len(levels), tables)
    reached = [t for t, xp in party_thresholds(levels, tables).items() if adjusted >= xp]
    return reached[-1] if reached else None


def check_encounter_budget(
    monster_xps: Sequence[int], levels: Sequence[int], tables: EncounterTables
) -> BudgetCheck:
    adjusted = adjusted_xp(monster_xps, len(levels), tables)
    deadly = party_budget(levels, Difficulty.DEADLY, tables)
    return BudgetCheck(
        adjusted_xp=adjusted,
        deadly_budget=deadly,
        difficulty=rate_encounter(monster_xps, levels, tables),
        allowed=adjusted <= deadly,
    )


def pick_monsters(
    rng: Rng,
    budget: int,
    candidates: Mapping[str, int],
    party_size: int,
    tables: EncounterTables,
) -> list[str]:
    pool = sorted((cid, xp) for cid, xp in candidates.items() if xp > 0)
    picked: list[str] = []
    xps: list[int] = []
    while len(picked) < tables.max_monsters:
        fits = [
            (cid, xp) for cid, xp in pool if adjusted_xp([*xps, xp], party_size, tables) <= budget
        ]
        if not fits:
            break
        cid, xp = fits[rng.randint(0, len(fits) - 1)]
        picked.append(cid)
        xps.append(xp)
    return picked
