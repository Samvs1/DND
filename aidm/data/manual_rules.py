"""Generated player-manual tables for the rules: conditions, surfaces, spells, prices (M14.1)."""

from aidm.data.condition_defs import ConditionDef, condition_defs
from aidm.data.consumable_defs import consumable_defs
from aidm.data.dm_tiers import dm_tiers
from aidm.data.manual_md import join, table, words
from aidm.data.scribe_defs import scribe_table
from aidm.data.shop_defs import shop_table
from aidm.data.spell_defs import SpellDef, spell_defs
from aidm.data.srd import srd
from aidm.data.surface_defs import SurfaceDef, SurfaceHarm, surface_data

_SAYS_NOTHING = "No numbers of its own: the Dungeon Master plays it out."
_CASTERS = ("wizard", "cleric", "ranger", "warlock")


def _attack_lines(c: ConditionDef) -> list[str]:
    out: list[str] = []
    if c.own_attacks:
        out.append(f"its attacks have {c.own_attacks}")
    melee, ranged = c.attacks_against_melee, c.attacks_against_ranged
    if melee and melee == ranged:
        out.append(f"attacks against it have {melee}")
    else:
        if melee:
            out.append(f"melee attacks against it have {melee}")
        if ranged:
            out.append(f"ranged attacks against it have {ranged}")
    if c.auto_crit_melee:
        out.append("melee hits against it are critical hits")
    if c.attack_dice:
        out.append(f"{c.attack_dice} on attack rolls")
    return out


def _check_lines(c: ConditionDef) -> list[str]:
    out: list[str] = []
    if c.own_checks:
        out.append(f"its ability checks have {c.own_checks}")
    if c.check_dice:
        out.append(f"{c.check_dice} on ability checks")
    if c.auto_fail_saves:
        out.append(
            "automatically fails " + "/".join(a.upper() for a in c.auto_fail_saves) + " saves"
        )
    if c.save_advantage:
        out.append("advantage on " + "/".join(a.upper() for a in c.save_advantage) + " saves")
    if c.save_disadvantage:
        out.append("disadvantage on " + "/".join(a.upper() for a in c.save_disadvantage) + " saves")
    if c.save_dice:
        out.append(f"{c.save_dice} on saving throws")
    return out


def _body_lines(c: ConditionDef) -> list[str]:
    out: list[str] = []
    if c.speed_factor == 0:
        out.append("cannot move")
    elif c.speed_factor < 1:
        out.append(f"speed is {round(c.speed_factor * 100)}%")
    if c.speed_bonus:
        out.append(f"+{c.speed_bonus} ft speed")
    if not c.can_act:
        out.append("cannot take actions")
    if not c.can_react:
        out.append("cannot take reactions")
    if c.cannot_attack_source:
        out.append("cannot attack whoever charmed it")
    if c.ac_bonus:
        out.append(f"{c.ac_bonus:+d} AC")
    if c.ac_floor:
        out.append(f"AC is at least {c.ac_floor}")
    if c.resist_all_damage:
        out.append("resists all damage")
    if c.damage_resistances:
        out.append("resists " + join(c.damage_resistances) + " damage")
    if c.damage_immunities:
        out.append("immune to " + join(c.damage_immunities) + " damage")
    if c.source_rider_dice:
        out.append(f"the caster's weapon hits on it add {c.source_rider_dice}")
    if c.bonus_actions:
        out.append("can " + "/".join(c.bonus_actions) + " as a bonus action")
    if c.blocks_verbal:
        out.append("cannot cast spells with spoken parts")
    if c.unseen:
        out.append("others cannot see it")
    if c.sightless:
        out.append("cannot see")
    if c.turn_start_damage:
        out.append(
            f"takes {c.turn_start_damage} {c.turn_start_damage_type} damage at the start of its turns"
        )
    if c.turn_end_damage:
        out.append(
            f"takes {c.turn_end_damage} {c.turn_end_damage_type} damage at the end of its turn"
        )
    if c.end_check:
        out.append(
            f"an action and a DC {c.end_check.dc} {c.end_check.ability.upper()} check end it"
        )
    return out


def _tail_lines(c: ConditionDef) -> list[str]:
    out: list[str] = []
    if c.consumed_by_attack:
        out.append("ends after its next attack")
    if c.consumed_by_attack_against:
        out.append("ends after the next attack against it")
    if c.ends_on_damage:
        out.append("ends when it takes damage")
    if c.ends_on_source_side_harm:
        out.append("ends when whoever caused it, or one of their companions, harms it")
    if c.implies:
        out.append("also counts as " + join(c.implies))
    d = c.duration
    if d.kind == "rounds":
        out.append(f"lasts {d.rounds} round{'s' if d.rounds != 1 else ''}")
    elif d.kind == "until_long_rest":
        out.append("lasts until a long rest")
    return out


def condition_summary(c: ConditionDef) -> str:
    parts = [*_attack_lines(c), *_check_lines(c), *_body_lines(c), *_tail_lines(c)]
    if not parts:
        return _SAYS_NOTHING
    text = "; ".join(parts)
    return text[0].upper() + text[1:] + "."


def conditions_table() -> str:
    rows = [[c.name, condition_summary(c)] for c in condition_defs().all()]
    return table(["Condition", "What it does"], rows)


def _moment(harm: SurfaceHarm) -> str:
    names = {
        "create": "when it appears",
        "enter": "on entering",
        "turn_start": "at the start of a turn",
    }
    return ", ".join(names.get(m, words(m)) for m in harm.when)


def _harm_text(harm: SurfaceHarm, dc: int) -> str:
    what: list[str] = []
    if harm.damage:
        what.append(f"{harm.damage} {harm.damage_type} damage")
    if harm.condition:
        span = f" for {harm.condition_rounds} round" if harm.condition_rounds else ""
        inside = " while inside" if harm.while_inside else span
        what.append(f"{harm.condition}{inside}")
    effect = " and ".join(what)
    if harm.save:
        tail = ", half damage on a success" if harm.half_on_save else " on a failed save"
        return (
            f"{_moment(harm)}: {(harm.save or '').upper()} save DC {harm.dc or dc}, {effect}{tail}"
        )
    return f"{_moment(harm)}: {effect}"


def surface_summary(s: SurfaceDef) -> str:
    notes = []
    if s.difficult:
        notes.append("rough ground (entering costs double movement)")
    if s.affects == "hostile_to_source":
        notes.append("only hurts the caster's enemies")
    if s.follows_source:
        notes.append("moves with the caster")
    notes += [_harm_text(h, s.dc) for h in s.harms]
    return "; ".join(notes) or "no effect of its own"


def surfaces_table() -> str:
    rows = []
    for s in surface_data().surfaces:
        lasts = f"{s.duration_rounds} rounds" if s.duration_rounds else "until removed"
        rows.append([s.name, lasts, surface_summary(s)])
    return table(["Surface", "Lasts", "Effect"], rows)


def surface_mixes_list() -> str:
    names = {s.index: s.name for s in surface_data().surfaces}
    lines = []
    for i in surface_data().interactions:
        if i.surfaces is not None:
            trigger = " meets ".join(names[x] for x in i.surfaces)
        else:
            trigger = f"{names[i.surface or '']} takes {i.damage_type} damage"
        out = []
        if i.creates:
            out.append("becomes " + ", ".join(names[x] for x in i.creates))
        elif i.consumes:
            out.append(", ".join(names[x] for x in i.consumes) + " is used up")
        if i.burst:
            out.append(_harm_text(i.burst, i.burst.dc or 12).split(": ", 1)[1])
        lines.append(f"- {trigger}: " + "; ".join(out))
    return "\n".join(lines)


def _range(spell: SpellDef) -> str:
    r = spell.range
    return f"{r.feet} ft" if r.kind == "feet" else r.kind


def spells_table() -> str:
    rows = []
    for s in sorted(spell_defs().all(), key=lambda x: (x.level, srd().spells.get(x.index).name)):
        name = srd().spells.get(s.index).name
        level = "Cantrip" if s.level == 0 else str(s.level)
        who = join(sorted(c for c in s.classes if c in _CASTERS))
        rows.append(
            [
                name,
                level,
                s.school,
                words(s.casting_time),
                _range(s),
                "yes" if s.concentration else "no",
                who,
            ]
        )
    return table(
        ["Spell", "Level", "School", "Casting time", "Range", "Concentration", "Classes"], rows
    )


def consumables_table() -> str:
    rows = []
    for c in consumable_defs().all():
        effect = (
            f"heals {c.heal}"
            if c.heal
            else f"adds {c.supply} camp supply"
            if c.supply == 1
            else f"adds {c.supply} camp supplies"
        )
        price = f"{c.value_gp:g} gp" if c.value_gp is not None else "-"
        rows.append([c.name, c.category, effect, price])
    return table(["Item", "Kind", "Effect", "Price"], rows)


def shop_rules() -> str:
    s = shop_table()
    kinds = [
        f"- **{words(name).capitalize()}** sells {join(k.categories)} (about {k.size} items)"
        + (f", always with at least one {join(k.one_of_each)}." if k.one_of_each else ".")
        for name, k in s.kinds.items()
    ]
    return "\n".join(
        [
            f"- You buy at {round(s.buy_markup * 100)}% of an item's value, rounded up, never less than 1 gp.",
            f"- A shop buys from you at {round(s.sell_fraction * 100)}% of the value, rounded down.",
            f"- You can trade up to {s.max_qty} of an item at a time.",
            f"- A trader whose trade is unclear counts as a {words(s.default_kind)} shop.",
            f"- Every region has a trader who sells {join(s.basics)}.",
            "",
            "Kinds of shop:",
            "",
            *kinds,
        ]
    )


def milestone_xp() -> str:
    """M29.6b: the experience for places and masters, by region (data/bg3/dm_tiers.json)."""
    t = dm_tiers()
    names = {"1": "First", "2": "Second", "3": "Third"}
    rows = [
        [names[k], str(r.visit), str(r.clear), f"{r.region:,}"]
        for k, r in sorted(t.milestone_xp.items())
    ]
    head = ["Region", "Reaching a new place", "Clearing it", "Dealing with the master"]
    last = f"The last master dealt with adds {t.final_milestone_xp:,} more."
    last += " Each pays every living hero once."
    return f"{table(head, rows)}\n\n{last}"


def check_caps() -> str:
    """M29.6b: the hardest check the storyteller may ask, by region (dm_tiers.json)."""
    names = {"1": "first", "2": "second", "3": "third"}
    lines = [
        f"- In the {names[k]} region a check or a new lock is at most {words(v)}."
        for k, v in sorted(dm_tiers().check_dc_tier_cap.items())
    ]
    return "\n".join(lines)


def gift_rules() -> str:
    """M29.6b: how many gifts earn a person's favour (dm_tiers.json)."""
    n = dm_tiers().gift_deeds_per_npc
    return (
        f"- The first {n} different gifts to a person earn their favour; the same thing given "
        "again, or more gifts after that, earns nothing more (an item from a quest's reward "
        "still counts once)."
    )


def scribe_prices() -> str:
    t = scribe_table()
    rows = [[lv, f"{t.base_gp + t.per_level_gp * lv} gp"] for lv in range(1, 6)]
    return table(["Level of the fallen hero", "Price"], rows)
