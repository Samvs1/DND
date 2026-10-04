"""Per-class goldens (SPEC 14 M2): six fixed builds levelled 1 -> 5, every number computed by hand.

Builds (tests/unit/rules/golden_builds.py): human (+1 to every ability), standard array
15/14/13/12/10/8 assigned by class priority, first legal option for every pick, ASI to the
class's primary ability at level 4. Average hit-die HP (SRD "Hit Points at Higher Levels").
SRD 5.1 sources: Character Advancement (PB 2 at levels 1-4, 3 at level 5), the class tables
(cantrips, slots, Extra Attack, Pact Magic), Armor table, Weapons table, Spellcasting
(save DC = 8 + PB + ability modifier, attack = PB + ability modifier).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

from aidm.models.abilities import Ability
from aidm.models.sheet import AttackLine, CharacterSheet
from aidm.rules.sheet import build_sheet
from aidm.rules.spellcasting import spell_attack_bonus, spell_save_dc
from tests.unit.rules.golden_builds import GOLDEN_CLASSES, REGS, golden_levels


class Gold(NamedTuple):
    hp: int
    ac: int
    pb: int
    apl: int  # attacks per action
    main: tuple[int, str]  # main-hand weapon: attack bonus, damage expression
    ranged: tuple[int, str] | None  # the ranged weapon, when the build carries one
    dc: int | None  # spell save DC (None = no spellcasting at this level)
    spell_atk: int | None
    cantrips: int
    slots: dict[int, int]  # standard slots: spell level -> maximum
    pact: tuple[int, int] | None = None  # (slot level, number of slots)


# Fighter: human STR 16 (+3) DEX 14 (+2) CON 15 (+2); d10 (avg 6); champion, Archery style.
# Chain mail 16 + shield 2 = AC 18 at every level (heavy armor ignores DEX; ASI at L4 is STR).
# Longsword 1d8 (one-handed, shield): STR mod + PB. Light crossbow: DEX mod + PB + Archery 2.
FIGHTER = {
    # L1: 10 + 2 (CON) = 12; sword 3+2 = +5, 1d8+3; crossbow 2+2+2 = +6, 1d8+2.
    1: Gold(12, 18, 2, 1, (5, "1d8+3"), (6, "1d8+2"), None, None, 0, {}),
    # L2: 12 + (6 + 2) = 20.
    2: Gold(20, 18, 2, 1, (5, "1d8+3"), (6, "1d8+2"), None, None, 0, {}),
    # L3: 20 + 8 = 28 (Champion chosen; Improved Critical does not change these numbers).
    3: Gold(28, 18, 2, 1, (5, "1d8+3"), (6, "1d8+2"), None, None, 0, {}),
    # L4: 28 + 8 = 36; ASI STR 16 -> 18 (+4): sword 4+2 = +6, 1d8+4; crossbow unchanged.
    4: Gold(36, 18, 2, 1, (6, "1d8+4"), (6, "1d8+2"), None, None, 0, {}),
    # L5: 36 + 8 = 44; PB 3: sword 4+3 = +7; crossbow 2+3+2 = +7; Extra Attack = 2 attacks.
    5: Gold(44, 18, 3, 2, (7, "1d8+4"), (7, "1d8+2"), None, None, 0, {}),
}

# Rogue: human DEX 16 (+3) CON 15 (+2); d8 (avg 5); leather 11 + DEX; ASI at L4 is DEX -> 18.
# Daggers are finesse (DEX): main hand 1d4 + DEX; shortbow 1d6 + DEX; proficient: + PB.
ROGUE = {
    # L1: 8 + 2 = 10; AC 11 + 3 = 14; dagger 3+2 = +5, 1d4+3; shortbow +5, 1d6+3.
    1: Gold(10, 14, 2, 1, (5, "1d4+3"), (5, "1d6+3"), None, None, 0, {}),
    # L2: 10 + (5 + 2) = 17.
    2: Gold(17, 14, 2, 1, (5, "1d4+3"), (5, "1d6+3"), None, None, 0, {}),
    # L3: 17 + 7 = 24 (Thief).
    3: Gold(24, 14, 2, 1, (5, "1d4+3"), (5, "1d6+3"), None, None, 0, {}),
    # L4: 24 + 7 = 31; DEX 18 (+4): AC 11 + 4 = 15, dagger 4+2 = +6, 1d4+4; bow +6, 1d6+4.
    4: Gold(31, 15, 2, 1, (6, "1d4+4"), (6, "1d6+4"), None, None, 0, {}),
    # L5: 31 + 7 = 38; PB 3: +7 (rogues get no Extra Attack).
    5: Gold(38, 15, 3, 1, (7, "1d4+4"), (7, "1d6+4"), None, None, 0, {}),
}

# Wizard: human INT 16 (+3) DEX 14 (+2) CON 15 (+2) STR 9 (-1); d6 (avg 4); unarmored AC 10 + 2.
# Quarterstaff (proficient, versatile 1d8 two-handed): STR -1 + PB. ASI at L4 is INT -> 18 (+4).
# Slots and cantrips per the SRD Wizard table.
WIZARD = {
    # L1: 6 + 2 = 8; staff -1+2 = +1, 1d8-1; DC 8+2+3 = 13; atk 2+3 = +5; 3 cantrips; 2 slots.
    1: Gold(8, 12, 2, 1, (1, "1d8-1"), None, 13, 5, 3, {1: 2}),
    # L2: 8 + (4 + 2) = 14; 3 first-level slots.
    2: Gold(14, 12, 2, 1, (1, "1d8-1"), None, 13, 5, 3, {1: 3}),
    # L3: 14 + 6 = 20; slots 4 / 2.
    3: Gold(20, 12, 2, 1, (1, "1d8-1"), None, 13, 5, 3, {1: 4, 2: 2}),
    # L4: 20 + 6 = 26; INT 18 (+4): DC 8+2+4 = 14, atk 2+4 = +6; 4 cantrips; slots 4 / 3.
    4: Gold(26, 12, 2, 1, (1, "1d8-1"), None, 14, 6, 4, {1: 4, 2: 3}),
    # L5: 26 + 6 = 32; PB 3: staff -1+3 = +2, DC 8+3+4 = 15, atk 3+4 = +7; slots 4 / 3 / 2.
    5: Gold(32, 12, 3, 1, (2, "1d8-1"), None, 15, 7, 4, {1: 4, 2: 3, 3: 2}),
}

# Cleric (life): human WIS 16 (+3) CON 15 (+2) STR 14 (+2) DEX 11 (0); d8 (avg 5).
# Scale mail 14 (DEX capped at 2, here 0) + shield 2 = AC 16. Mace 1d6 + STR; light crossbow
# 1d8 + DEX (0), not Archery-trained, so only PB. ASI at L4 is WIS -> 18 (+4).
CLERIC = {
    # L1: 8 + 2 = 10; mace 2+2 = +4, 1d6+2; crossbow 0+2 = +2, 1d8; DC 8+2+3 = 13; atk +5.
    1: Gold(10, 16, 2, 1, (4, "1d6+2"), (2, "1d8"), 13, 5, 3, {1: 2}),
    # L2: 10 + (5 + 2) = 17; 3 slots.
    2: Gold(17, 16, 2, 1, (4, "1d6+2"), (2, "1d8"), 13, 5, 3, {1: 3}),
    # L3: 17 + 7 = 24; slots 4 / 2.
    3: Gold(24, 16, 2, 1, (4, "1d6+2"), (2, "1d8"), 13, 5, 3, {1: 4, 2: 2}),
    # L4: 24 + 7 = 31; WIS 18: DC 8+2+4 = 14, atk +6; 4 cantrips; slots 4 / 3.
    4: Gold(31, 16, 2, 1, (4, "1d6+2"), (2, "1d8"), 14, 6, 4, {1: 4, 2: 3}),
    # L5: 31 + 7 = 38; PB 3: mace 2+3 = +5, crossbow 0+3 = +3, DC 8+3+4 = 15, atk 3+4 = +7.
    5: Gold(38, 16, 3, 1, (5, "1d6+2"), (3, "1d8"), 15, 7, 4, {1: 4, 2: 3, 3: 2}),
}

# Ranger (hunter): human DEX 16 (+3) WIS 15 (+2) CON 14 (+2) STR 13 (+1); d10 (avg 6).
# Scale mail 14 + DEX capped at 2 = AC 16 (the L4 ASI, DEX 18, cannot raise it).
# Shortsword (finesse) 1d6 + DEX; longbow 1d8 + DEX, + Archery 2 from level 2 (fighting style).
# Spellcasting starts at level 2 (WIS 15, +2): no cantrips (SRD Ranger table), half-caster slots.
RANGER = {
    # L1: 10 + 2 = 12; sword 3+2 = +5, 1d6+3; bow 3+2 = +5, 1d8+3; no spellcasting yet.
    1: Gold(12, 16, 2, 1, (5, "1d6+3"), (5, "1d8+3"), None, None, 0, {}),
    # L2: 12 + (6 + 2) = 20; Archery: bow 3+2+2 = +7; DC 8+2+2 = 12, atk 2+2 = +4; 2 slots.
    2: Gold(20, 16, 2, 1, (5, "1d6+3"), (7, "1d8+3"), 12, 4, 0, {1: 2}),
    # L3: 20 + 8 = 28; 3 slots (Hunter).
    3: Gold(28, 16, 2, 1, (5, "1d6+3"), (7, "1d8+3"), 12, 4, 0, {1: 3}),
    # L4: 28 + 8 = 36; DEX 18 (+4): sword 4+2 = +6, 1d6+4; bow 4+2+2 = +8, 1d8+4; 3 slots.
    4: Gold(36, 16, 2, 1, (6, "1d6+4"), (8, "1d8+4"), 12, 4, 0, {1: 3}),
    # L5: 36 + 8 = 44; PB 3: sword +7, bow 4+3+2 = +9; DC 8+3+2 = 13, atk 3+2 = +5;
    # slots 4 / 2; Extra Attack = 2 attacks.
    5: Gold(44, 16, 3, 2, (7, "1d6+4"), (9, "1d8+4"), 13, 5, 0, {1: 4, 2: 2}),
}

# Warlock (fiend): human CHA 16 (+3) CON 15 (+2) DEX 14 (+2); d8 (avg 5); leather 11 + 2 = AC 13.
# Dagger (finesse) 1d4 + DEX; light crossbow 1d8 + DEX; PB only. ASI at L4 is CHA -> 18 (+4).
# Pact Magic (SRD Warlock table): slot count and level, no standard slots.
WARLOCK = {
    # L1: 8 + 2 = 10; dagger 2+2 = +4, 1d4+2; crossbow +4, 1d8+2; DC 8+2+3 = 13; atk +5;
    # 2 cantrips; 1 pact slot of level 1.
    1: Gold(10, 13, 2, 1, (4, "1d4+2"), (4, "1d8+2"), 13, 5, 2, {}, (1, 1)),
    # L2: 10 + (5 + 2) = 17; 2 pact slots of level 1.
    2: Gold(17, 13, 2, 1, (4, "1d4+2"), (4, "1d8+2"), 13, 5, 2, {}, (1, 2)),
    # L3: 17 + 7 = 24; 2 pact slots of level 2.
    3: Gold(24, 13, 2, 1, (4, "1d4+2"), (4, "1d8+2"), 13, 5, 2, {}, (2, 2)),
    # L4: 24 + 7 = 31; CHA 18: DC 8+2+4 = 14, atk +6; 3 cantrips; still 2 slots of level 2.
    4: Gold(31, 13, 2, 1, (4, "1d4+2"), (4, "1d8+2"), 14, 6, 3, {}, (2, 2)),
    # L5: 31 + 7 = 38; PB 3: dagger 2+3 = +5, DC 8+3+4 = 15, atk +7; 2 pact slots of level 3.
    5: Gold(38, 13, 3, 1, (5, "1d4+2"), (5, "1d8+2"), 15, 7, 3, {}, (3, 2)),
}

GOLDENS = {
    "fighter": FIGHTER,
    "rogue": ROGUE,
    "wizard": WIZARD,
    "cleric": CLERIC,
    "ranger": RANGER,
    "warlock": WARLOCK,
}
CASTING_ABILITY = {
    "wizard": Ability.INT,
    "cleric": Ability.WIS,
    "ranger": Ability.WIS,
    "warlock": Ability.CHA,
}


def _attack(sheet: CharacterSheet, hand: str) -> AttackLine | None:
    return next((a for a in sheet.attacks if a.hand == hand), None)


def _check(class_index: str, level: int) -> None:
    want = GOLDENS[class_index][level]
    creature = golden_levels(class_index)[level]
    sheet = build_sheet(creature, REGS)
    assert (sheet.class_index, sheet.level) == (class_index, level)
    assert (sheet.max_hp, creature.max_hp, sheet.hp) == (want.hp, want.hp, want.hp)
    assert (sheet.ac, creature.ac) == (want.ac, want.ac)
    assert (sheet.proficiency_bonus, creature.proficiency_bonus) == (want.pb, want.pb)
    assert sheet.attacks_per_action == want.apl
    main = _attack(sheet, "main_hand")
    assert main is not None and (main.attack_bonus, main.damage) == want.main
    ranged = _attack(sheet, "ranged")
    assert (None if ranged is None else (ranged.attack_bonus, ranged.damage)) == want.ranged
    _check_casting(class_index, sheet, want)


def _check_casting(class_index: str, sheet: CharacterSheet, want: Gold) -> None:
    casting = sheet.spellcasting
    if want.dc is None:
        assert casting is None
        return
    assert casting is not None
    assert casting.ability is CASTING_ABILITY[class_index]
    assert (casting.save_dc, casting.attack_bonus) == (want.dc, want.spell_atk)
    cls = REGS.classes.get(class_index)
    pc = golden_levels(class_index)[sheet.level]
    assert (spell_save_dc(pc, cls), spell_attack_bonus(pc, cls)) == (want.dc, want.spell_atk)
    assert len(casting.cantrips) == want.cantrips
    standard = {g.level: s.maximum for g in casting.levels for s in g.slots if s.kind == "standard"}
    pact = [(g.level, s.maximum) for g in casting.levels for s in g.slots if s.kind == "pact"]
    assert standard == want.slots
    assert pact == ([] if want.pact is None else [want.pact])
    assert all(s.current == s.maximum for g in casting.levels for s in g.slots)


def _make(class_index: str, level: int) -> Callable[[], None]:
    def test() -> None:
        _check(class_index, level)

    test.__name__ = f"test_golden_{class_index}_level_{level}"
    return test


for _cls in GOLDEN_CLASSES:
    for _level in range(1, 6):
        _fn = _make(_cls, _level)
        globals()[_fn.__name__] = _fn


def test_golden_tables_cover_every_class_and_level() -> None:
    assert set(GOLDENS) == set(GOLDEN_CLASSES)
    assert all(sorted(rows) == [1, 2, 3, 4, 5] for rows in GOLDENS.values())
