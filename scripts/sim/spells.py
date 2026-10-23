"""Spells and potions for the M29.2 campaign bots: pick ONE command from the hero's own sheet.

The M9.1 bots only ever cast their first cantrip. A campaign bot (`Plan.smart`) plays its spell
slots and potions like a plain table would, which is what makes rests and shopping matter:
- a potion: my hero is below `POTION_BELOW` of its hit points and carries a healing potion;
- a heal: an ally lies dying (or is badly hurt) and I have a healing spell and a slot for it;
- a damage spell: a single-target damage spell with a slot left, at the bot's target.
`PREFERRED` orders the spell picks at creation and level-up (the healers and the damage first).
Everything is bot knowledge (scripts/, not the engine): the engine still refuses what is not
legal, and a refusal puts the key in `plan.refused` so the turn falls back to the weapon.

Public API: `PREFERRED`, `POTIONS`, `prefer(options)`, `spell_command(plan, combat, party, sheet,
target)`, `castable(sheet)`.
"""

from scripts.sim.client import Msg
from scripts.sim.combat import Plan, token_of

HEALS = ("healing-word", "cure-wounds")
DAMAGE = ("guiding-bolt", "magic-missile", "inflict-wounds", "scorching-ray", "acid-arrow")
PREFERRED = (
    *HEALS,
    *DAMAGE,
    "burning-hands",
    "sleep",
    "bless",
    "shield-of-faith",
    "thunderwave",
    "spirit-guardians",
    "mass-healing-word",
    "fireball",
    "lightning-bolt",
    "shatter",
    "hold-person",
    "aid",
)
POTIONS = (
    "potion-of-healing-superior",
    "potion-of-healing-greater",
    "potion-of-healing",
    "travellers-tonic",
    "herbal-poultice",
)
POTION_BELOW = 0.35
HEAL_BELOW = 0.25


def prefer(options: list[str]) -> list[str]:
    """`options` with the preferred spells first (in `PREFERRED` order), the rest after."""
    rank = {s: i for i, s in enumerate(PREFERRED)}
    return sorted(options, key=lambda s: (rank.get(s, len(rank)), options.index(s)))


def castable(sheet: Msg | None) -> dict[str, int]:
    """Leveled spells my hero can cast now -> the lowest slot level with a slot left."""
    casting = (sheet or {}).get("spellcasting") or {}
    free = sorted(
        g["level"]
        for g in casting.get("levels", [])
        if any(s["current"] > 0 for s in g.get("slots", []))
    )
    out: dict[str, int] = {}
    for group in casting.get("levels", []):
        for spell in group.get("spells", []):
            ready = spell.get("prepared") or spell.get("always_prepared")
            slot = next((lv for lv in free if lv >= spell["level"]), None)
            if ready and slot is not None and spell["level"] > 0:
                out[spell["index"]] = slot
    return out


def _potion(plan: Plan, me: Msg, sheet: Msg | None) -> Msg | None:
    if me["hp"] >= me["max_hp"] * POTION_BELOW or "potion" in plan.refused:
        return None
    carried = {i["item"] for i in (sheet or {}).get("inventory", []) if i.get("qty", 0) > 0}
    potion = next((p for p in POTIONS if p in carried), None)
    if potion is None:
        return None
    plan.refused.add("potion")  # at most one potion a turn
    return {"type": "use_item", "actor_id": plan.hero_id, "item": potion}


def _heal(plan: Plan, combat: Msg, party: list[Msg], spells: dict[str, int]) -> Msg | None:
    spell = next((s for s in HEALS if s in spells and f"cast:{s}" not in plan.refused), None)
    if spell is None:
        return None
    hurt = [
        p for p in party if not p["dead"] and (p.get("dying") or p["hp"] < p["max_hp"] * HEAL_BELOW)
    ]
    ally = next((token_of(combat, p["id"]) for p in hurt if token_of(combat, p["id"])), None)
    if ally is None:
        return None
    return _cast(plan, spell, spells[spell], ally["creature_id"])


def _cast(plan: Plan, spell: str, slot: int, target_id: str) -> Msg:
    return {
        "type": "cast",
        "actor_id": plan.hero_id,
        "spell_id": spell,
        "slot_level": slot,
        "target_ids": [target_id],
    }


def spell_command(
    plan: Plan, combat: Msg, party: list[Msg], sheet: Msg | None, target: Msg
) -> Msg | None:
    """A potion, a heal or a leveled damage spell to send now (module docstring), or None."""
    me = token_of(combat, plan.hero_id)
    eco = combat.get("economy") or {}
    if me is None or not plan.smart:
        return None
    if eco.get("action") or eco.get("bonus_action"):
        potion = _potion(plan, me, sheet)
        if potion is not None:
            return potion
    spells = castable(sheet)
    heal = (
        _heal(plan, combat, party, spells) if eco.get("action") or eco.get("bonus_action") else None
    )
    if heal is not None:
        return heal
    if not eco.get("action"):
        return None
    spell = next((s for s in DAMAGE if s in spells and f"cast:{s}" not in plan.refused), None)
    return None if spell is None else _cast(plan, spell, spells[spell], target["creature_id"])
