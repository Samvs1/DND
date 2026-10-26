"""Out-of-fight casts on the menu (M36.3, SPEC 6.2). Pure.

Every spell the hero can cast now (a ready cantrip, or a ready leveled spell with a slot of its
level or higher, `menu_magic.lowest_slot`; a spell paid from a race or feature pool is listed and
the rules answer an empty pool), labelled from its own data (`menu_labels.spell_label`). M36.10a:
a ready leveled spell with no slot left stays listed, `spent` and noted NO_SLOT (never a strike at
a waiting foe), so a typed cast of it is refused by the rules in plain words (M30.2b: never a free
spell through the storyteller):
- a spell that strikes no one and takes creatures (healing, a ward, a buff) aims at the heroes,
  the hero first (`rules.spells.cast_spell`, the typed-healing path);
- any other spell (self, a point or an area, or a hostile spell with no one to strike) is cast at
  the scene (`rules.spells.scene_cast`: the slot is spent, nothing moves);
- while a foe's offer waits here a hostile spell (`spell_targets.strikes_creatures`: an attack,
  a save, damage, an HP pool such as Sleep) is a strike at the offer's foes (`starts_fight`): the
  offer is answered as Fight and the cast plays on the hero's turn (M35.2 Y9,
  `rules.waiting_foe.cast_starts_fight`), never a scene cast.
M38.2: a ready spell with an attack roll (`spell_chances.spell_attack_options`, Fire Bolt,
Eldritch Blast) also aims at the people standing here, as a held weapon does (M36.8c): `option`
is its opening-strike key (`spell:<id>`), so a person named is the engine's attack on a person
(`PersonStrikeIntent`: `start_encounter` with the spell as the opening strike, the
point-of-no-return question first for a non-hostile person), and no one named stays the scene
cast. M38.4 (owner rule: never refuse a possible action): a harmful spell with no attack roll,
any that deals damage (`spell_targets.deals_damage`: Burning Hands, Sacred Flame, Magic
Missile), can open a fight on a person too, its opening strike cast at the person (an area at
the zone they stand in, `rules.opening_strike`). M38.5 fix: that is its own entry,
`strike:<spell>` ("Burning Hands at a person here" -> the people here, note STRIKE_NOTE), and its
`cast:<spell>` entry stays the plain scene cast with no target, so a cast at the ferns or the
water is never aimed at a person. While an offer waits, the strike at the foes also takes the
people here (`strike_casts`). A hostile spell that deals no damage (Charm Person, Sleep, Hold
Person) stays the scene cast out of a fight.

M36.4: `feature:<name>`: a class feature usable out of a fight (`feature_commands.
usable_out_of_fight`: a healing bonus action such as Second Wind) with uses left, the same id as
in a fight; Action Surge, Turn Undead and Breath Weapon need a fight and are not listed.

Public API: `explore_casts(view)`, `strike_casts(view, foe_ids)`, `explore_features(view)`,
`SCENE_NOTE`, `PERSON_NOTE`, `NO_SLOT`, `STRIKE_PREFIX`, `STRIKE_NOTE`.
"""

from collections.abc import Iterator

from aidm.data.spell_defs import SpellDef
from aidm.models.action_menu import ActionKind, MenuEntry
from aidm.models.sheet import SpellLine
from aidm.rules.feature_commands import usable_out_of_fight
from aidm.rules.features import command_hook
from aidm.rules.menu_labels import spell_label
from aidm.rules.menu_magic import lowest_slot, needs_of
from aidm.rules.menu_scene_view import SceneMenuView
from aidm.rules.menu_view import slug
from aidm.rules.spell_chances import SPELL_OPTION_PREFIX, spell_attack_options
from aidm.rules.spell_targets import deals_damage, strikes_creatures

SCENE_NOTE = "cast at the scene"
STRIKE_PREFIX = "strike"
STRIKE_NOTE = "starts a fight"
PERSON_NOTE = "cast at the scene, or at a person here: starts a fight"
NO_SLOT = "no spell slot left"


def _rolled(view: SceneMenuView) -> frozenset[str]:
    """The ready spells with an attack roll (M38.2), when someone stands here to aim them at."""
    if not view.people:
        return frozenset()
    hero = view.state.creatures[view.actor_id]
    keys = spell_attack_options(hero, view.regs.chars, view.regs.spells)
    return frozenset(p.key.removeprefix(SPELL_OPTION_PREFIX) for p in keys)


def _at_people(view: SceneMenuView) -> frozenset[str]:
    """The spells the hero can open a fight with on a person here: a ready spell with an attack
    roll (M38.2), or a harmful one, any that deals damage, with a slot left (M38.4)."""
    if not view.people:
        return frozenset()
    harmful = {s.index for s, _, _, left in _castable(view) if left != 0 and deals_damage(s)}
    return _rolled(view) | harmful


def _person_strike(
    view: SceneMenuView, spell: SpellDef, line: SpellLine, level: int | None
) -> MenuEntry:
    """M38.5 fix: a harmful spell with no attack roll at a person here is its own entry, so its
    scene cast never takes a person as a target ("Burning Hands at the damp ferns")."""
    return MenuEntry(
        id=f"{STRIKE_PREFIX}:{spell.index}",
        kind=ActionKind.CAST,
        label=f"{line.name} at a person here",
        target_ids=view.people,
        max_targets=1,
        note=STRIKE_NOTE,
        option=f"{SPELL_OPTION_PREFIX}{spell.index}",
        spell_id=spell.index,
        slot_level=level,
    )


def _castable(view: SceneMenuView) -> Iterator[tuple[SpellDef, SpellLine, int | None, int | None]]:
    """(spell, line, lowest slot level, slots left there) for every spell castable now."""
    block = view.sheet.spellcasting
    if block is None:
        return
    lines = [*block.cantrips, *(s for g in block.levels for s in g.spells)]
    for line in lines:
        spell = view.regs.spells.find(line.index)
        if spell is None or not line.prepared:
            continue
        if line.level == 0 or line.resource is not None:
            yield spell, line, None, None
            continue
        slot = lowest_slot(block, line.level)
        yield (spell, line, slot[0], slot[1]) if slot is not None else (spell, line, line.level, 0)


def explore_casts(view: SceneMenuView) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    party = (view.actor_id, *view.heroes)
    people = _rolled(view)
    strikes: list[MenuEntry] = []
    for spell, line, level, left in _castable(view):
        hostile = strikes_creatures(spell)
        if hostile and view.threat:
            continue  # a strike at the waiting foes (`strike_casts`)
        aimed = needs_of(spell) == "creature" and not hostile
        at_person = not aimed and left != 0 and spell.index in people
        if view.people and left != 0 and not at_person and deals_damage(spell):
            strikes.append(_person_strike(view, spell, line, level))
        note = NO_SLOT if left == 0 else "" if aimed else PERSON_NOTE if at_person else SCENE_NOTE
        out.append(
            MenuEntry(
                id=f"cast:{spell.index}",
                kind=ActionKind.CAST,
                label=spell_label(spell, line, left),
                target_ids=party if aimed else view.people if at_person else (),
                max_targets=max(1, line.target_count) if aimed else 1 if at_person else 0,
                spent=left == 0,
                note=note,
                option=f"{SPELL_OPTION_PREFIX}{spell.index}" if at_person else None,
                spell_id=spell.index,
                slot_level=level,
            )
        )
    return out + strikes


def strike_casts(view: SceneMenuView, foe_ids: tuple[str, ...]) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    people = _at_people(view)
    for spell, line, level, left in _castable(view):
        if not strikes_creatures(spell) or left == 0:
            continue
        count = line.target_count if needs_of(spell) == "creature" else len(foe_ids)
        at_person = spell.index in people
        out.append(
            MenuEntry(
                id=f"cast:{spell.index}",
                kind=ActionKind.CAST,
                label=spell_label(spell, line, left),
                target_ids=foe_ids
                + tuple(p for p in view.people if at_person and p not in foe_ids),
                max_targets=max(1, min(count, len(foe_ids))),
                option=f"{SPELL_OPTION_PREFIX}{spell.index}" if at_person else None,
                note="starts the fight",
                spell_id=spell.index,
                slot_level=level,
                starts_fight=True,
            )
        )
    return out


def explore_features(view: SceneMenuView) -> list[MenuEntry]:
    hero = view.state.creatures[view.actor_id]
    feats = view.regs.chars.features
    out: list[MenuEntry] = []
    for line in view.sheet.feature_actions:
        hook = command_hook(hero, feats, line.feature)
        if not line.available or hook is None or not usable_out_of_fight(hook):
            continue
        entry_id = f"feature:{slug(line.name)}"
        if any(e.id == entry_id for e in out):
            continue
        parts = [f"heals {line.heal}"] if line.heal else []
        parts += [f"{line.uses_left} left"] if line.uses_left is not None else []
        out.append(
            MenuEntry(
                id=entry_id,
                kind=ActionKind.FEATURE,
                label=f"{line.name} ({', '.join(parts)})" if parts else line.name,
                cost="bonus",
                feature_id=line.feature,
            )
        )
    return out
