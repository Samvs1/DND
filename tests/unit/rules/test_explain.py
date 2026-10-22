"""Tooltip text builder (M28.1): goldens, completeness and key rules."""

import re

from aidm.data.condition_defs import condition_defs
from aidm.data.item_catalogue import item_catalogue
from aidm.data.item_uses import item_use_data
from aidm.data.spell_defs import spell_defs
from aidm.rules.explain import all_tips, build_tips, tips_payload

KEY = re.compile(r"^[a-z]+:[a-z0-9_-]+$")


def _text(key: str) -> str:
    return all_tips()[key].text


def test_golden_fire_bolt() -> None:
    # SRD 5.1 Fire Bolt: ranged spell attack, 120 ft (2 zones), 1d10 fire, scales at 5/11/17.
    assert _text("spell:fire-bolt") == (
        "Fire Bolt. Cantrip, action. Ranged spell attack, up to 2 zones away. "
        "On a hit 1d10 fire (more dice at levels 5, 11 and 17)."
    )


def test_golden_cure_wounds() -> None:
    # SRD 5.1 Cure Wounds: touch, 1d8 + spellcasting modifier, +1d8 per slot level.
    assert _text("spell:cure-wounds") == (
        "Cure Wounds. Level 1, action. Touch, same zone, one creature. "
        "Heals 1d8 plus your spellcasting modifier. Higher slot: +1d8 per slot level above its own."
    )


def test_golden_sleep() -> None:
    # SRD 5.1 Sleep: 5d8 hit points of creatures, lowest first, +2d8 per slot level.
    assert _text("spell:sleep") == (
        "Sleep. Level 1, action. Up to 2 zones away, hits everyone else in a zone. "
        "Rolls 5d8 hit points of creatures, lowest first; each one that fits: Asleep. "
        "Higher slot: +2d8 hit points per slot level above its own."
    )


def test_golden_shield_of_faith() -> None:
    # Shield (a reaction) is not shipped; Shield of Faith: SRD 5.1 +2 AC, concentration.
    assert _text("spell:shield-of-faith") == (
        "Shield of Faith. Level 1, bonus action, concentration. "
        "Up to 1 zone away, one creature. +2 AC."
    )


def test_golden_fireball() -> None:
    # SRD 5.1 Fireball: DEX save, 8d6 fire, half on success, +1d6 per slot level above 3rd.
    assert _text("spell:fireball") == (
        "Fireball. Level 3, action. DEX save, up to 2 zones away, hits everyone else in a zone. "
        "On a failed save 8d6 fire, half on a success. "
        "Higher slot: +1d6 per slot level above its own."
    )


def test_golden_potion_of_healing() -> None:
    # SRD 5.1 Potion of healing: 2d4 + 2, 50 gp.
    assert (
        _text("item:potion-of-healing")
        == "Potion of Healing. Potion, 0.5 lb, worth 50 gp. Heals 2d4+2."
    )


def test_golden_torch() -> None:
    # data/bg3/item_uses.json torch-light: light_place, bonus action, consumes.
    assert _text("item:torch") == (
        "Torch. Gear, 1 lb, worth 0.01 gp. "
        "Uses: light the torch; throw the lit torch at a creature; throw the lit torch into a zone."
    )
    assert _text("use:torch-light") == (
        "Light the torch. Used in a dark place; costs a bonus action in a fight. "
        "Lights the place; shows you to anything waiting. "
        "Stays lit and travels with you until a long rest; used up when lit."
    )


def test_golden_prone() -> None:
    # SRD 5.1 Prone: disadvantage on its attacks; melee attacks against it have advantage,
    # ranged attacks against it have disadvantage.
    assert _text("condition:prone") == (
        "Prone. Its attacks have disadvantage; melee attacks against it have advantage; "
        "ranged attacks against it have disadvantage."
    )


def test_golden_bloodied() -> None:
    assert _text("word:bloodied") == "Bloodied. A quarter of its hit points or fewer are left."


def test_golden_half_cover() -> None:
    # SRD 5.1 Cover: half cover is +2 to AC.
    assert _text("word:half-cover") == (
        "Half cover. A ranged attack from another zone at someone here has to beat +2 AC. "
        "Melee and same-zone attacks ignore cover."
    )


def test_every_spell_item_use_and_condition_has_a_tip() -> None:
    tips = all_tips()
    assert all(f"spell:{s.index}" in tips for s in spell_defs().all())
    assert all(f"item:{i.id}" in tips for i in item_catalogue().all())
    assert all(f"use:{u.id}" in tips for u in item_use_data().uses)
    assert all(f"condition:{c.index}" in tips for c in condition_defs().all())


def test_tip_keys_are_ascii_kind_id_and_lines_are_short() -> None:
    for key, tip in build_tips().items():
        assert KEY.match(key), key
        assert 1 <= len(tip.lines) <= 4, key
        assert (tip.title + "".join(tip.lines)).isascii(), key
        assert all(line.endswith((".", ")", "?")) for line in tip.lines), key


def test_payload_is_json_shaped() -> None:
    payload = tips_payload()
    assert payload["word:dash"] == {
        "title": "Dash",
        "lines": ["Adds your speed again to your movement this turn."],
    }


def test_every_race_trait_has_a_tip() -> None:
    from aidm.data.race_defs import race_defs

    ids: set[str] = set()
    for race in race_defs().all():
        ids.update(race.traits)
        for sub in race.subraces:
            ids.update(sub.traits)
    assert len(ids) >= 28
    missing = [i for i in sorted(ids) if f"trait:{i}" not in all_tips()]
    assert missing == []


def test_golden_trait_darkvision() -> None:
    # SRD 5.1 Darkvision: dim light within 60 feet as if bright (dwarf, elf, ...).
    text = _text("trait:darkvision")
    assert "60 feet" in text and "A racial trait of the" in text and "Dwarf" in text


def test_every_hotbar_action_slot_has_a_word_tip() -> None:
    # Slot ids of aidm/web/js/combat/hotbar_slots.js; the Spells and Items openers have none.
    slots = [
        "attack", "throw", "shove-prone", "shove-push", "jump", "dash", "disengage", "dodge",
        "hide", "help", "flee",
    ]  # fmt: skip
    tips = tips_payload()
    for slot in slots:
        assert f"word:{slot}" in tips, slot
    assert "1d4" in str(tips["word:throw"]["lines"])
