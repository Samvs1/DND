"""The spell or feature a typed line names (M31.1a V1, V2): matched on the names the hero has
READY, so it is data-driven (no spell is named in code).

- `ready_spells(actor)`: (index, name) of the hero's ready spells: cantrips and prepared or
  known spells of the ONE sheet builder (`rules.sheet_spells.spellcasting_block`), racial and
  feature spells too;
- `targeted_features(actor)`: (feature id, name) of the active abilities the hotbar offers
  that aim at others (Turn Undead);
- `said_name(words, options)`: the option whose name words stand together in the line, the
  longest name first, unless a veto word of the lexicon's `spell_name_vetoes` stands just
  before it ("I ask about sacred flame" casts nothing). Returns (key, name, span).

- `named_spell(actor, words)` (M32.1a): (key, name, span, is_feature) of the ready spell, else
  the targeted feature, else (after a cast word) any spell of the registry the words name;
- `names_spell(actor, words)` (M32.1a X2): the line names a spell (`named_spell`, or any
  registry spell of two or more words: "a Guiding Bolt", "fire bolt"), so it is never read as a
  weapon blow.
- M33.1 (ultrareview 1: "I attack the goblin with my light crossbow" cast Light): both read a
  spell whose name is an everyday word (`plain_word_spell`: only light or utility effects, Light
  and Mage Hand) only after a cast word ("I cast light on my shield"), and never inside the name
  of a weapon or attack option the hero has ("light crossbow", "light hammer"), so the veto of
  the weapon rows and the fight cast follow one rule.

Public API: `Option`, `ready_spells`, `targeted_features`, `said_name`, `named_spell`,
`names_spell`, `plain_word_spell`.
"""

from aidm.data.combat_data import combat_registries
from aidm.data.intent_phrases import intent_phrases
from aidm.data.spell_defs import LightSourceEffect, SpellDef, UtilityEffect
from aidm.dm.fight_names import name_span, tokens
from aidm.models.state import Creature
from aidm.rules.attack_profiles import attack_options
from aidm.rules.features import feature_actions
from aidm.rules.sheet_spells import spellcasting_block

type Option = tuple[str, str]
type Said = tuple[str, str, tuple[int, int]]
type SaidSpell = tuple[str, str, tuple[int, int], bool]
_LOOK_BACK = 3


def ready_spells(actor: Creature) -> list[Option]:
    block = spellcasting_block(actor, combat_registries().chars)
    if block is None:
        return []
    lines = [*block.cantrips, *(s for g in block.levels for s in g.spells)]
    return [(s.index, s.name) for s in lines if s.prepared]


def targeted_features(actor: Creature) -> list[Option]:
    feats = combat_registries().chars.features
    return [
        (o.feature, o.name)
        for o in feature_actions(actor, feats)
        if o.command and o.action == "ability" and o.target_kind != "self" and o.name
    ]


def said_name(words: list[str], options: list[Option]) -> Said | None:
    vetoes = intent_phrases().lexicon["spell_name_vetoes"]
    found: list[tuple[int, int, Said]] = []
    for key, name in options:
        span = name_span(words, name)
        if span is None or set(words[max(0, span[0] - _LOOK_BACK) : span[0]]) & vetoes:
            continue
        found.append((span[0] - span[1], span[0], (key, name, span)))
    return min(found)[2] if found else None


def _all_spells() -> list[Option]:
    return [(s.index, s.name) for s in combat_registries().chars.spells.all()]


def plain_word_spell(spell: SpellDef) -> bool:
    """A utility spell with no dice or buff (Light, Mage Hand: M31.2a): its name is an everyday
    word ("I light the torch"), so it is cast only after a cast word ("I cast light on ...")."""
    return all(isinstance(e, LightSourceEffect | UtilityEffect) for e in spell.effects)


def _weapon_names(actor: Creature) -> list[str]:
    """The names of the hero's attack options and carried weapons, in both SRD word orders
    ("Crossbow, light" is also "light crossbow")."""
    chars = combat_registries().chars
    names = [o.name for o in attack_options(actor, chars)]
    rows = actor.pc.inventory if actor.pc is not None else []
    found = (chars.equipment.find(r.item) for r in rows)
    names += [e.name for e in found if e is not None and e.weapon_category is not None]
    turned = [f"{after} {head}" for head, _, after in (n.partition(",") for n in names) if after]
    return names + turned


def _unweaponed(actor: Creature, words: list[str]) -> list[str]:
    """The words with every weapon name the hero has blanked out (indices kept)."""
    out = list(words)
    for name in _weapon_names(actor):
        if len(tokens(name)) < 2:
            continue  # a one-word weapon name holds no other word
        span = name_span(out, name)
        while span is not None:
            out[span[0] : span[1]] = [""] * (span[1] - span[0])
            span = name_span(out, name)
    return out


def _after_cast(words: list[str], name: str) -> bool:
    want, casts = tokens(name), intent_phrases().lexicon["cast_words"]
    size = len(want)
    return any(
        words[i : i + size] == want and set(words[max(0, i - _LOOK_BACK) : i]) & casts
        for i in range(len(words) - size + 1)
    )


def _castable(words: list[str], options: list[Option]) -> list[Option]:
    """The options minus every plain-word spell not said right after a cast word."""
    spells = combat_registries().spells
    kept: list[Option] = []
    for key, name in options:
        spell = spells.find(key)
        if spell is not None and plain_word_spell(spell) and not _after_cast(words, name):
            continue
        kept.append((key, name))
    return kept


def named_spell(actor: Creature, words: list[str]) -> SaidSpell | None:
    words = _unweaponed(actor, words)
    said = said_name(words, _castable(words, ready_spells(actor)))
    if said is not None:
        return (*said, False)
    feature = said_name(words, targeted_features(actor))
    if feature is not None:
        return (*feature, True)
    if not set(words) & intent_phrases().lexicon["cast_words"]:
        return None
    other = said_name(words, _castable(words, _all_spells()))
    return (*other, False) if other is not None else None


def names_spell(actor: Creature, words: list[str]) -> bool:
    if named_spell(actor, words) is not None:
        return True
    long_names = [(key, name) for key, name in _all_spells() if len(name.split()) > 1]
    words = _unweaponed(actor, words)
    return said_name(words, _castable(words, long_names)) is not None
