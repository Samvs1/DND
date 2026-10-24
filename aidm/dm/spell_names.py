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

Public API: `Option`, `ready_spells`, `targeted_features`, `said_name`, `named_spell`,
`names_spell`.
"""

from aidm.data.combat_data import combat_registries
from aidm.data.intent_phrases import intent_phrases
from aidm.dm.fight_names import name_span
from aidm.models.state import Creature
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


def named_spell(actor: Creature, words: list[str]) -> SaidSpell | None:
    said = said_name(words, ready_spells(actor))
    if said is not None:
        return (*said, False)
    feature = said_name(words, targeted_features(actor))
    if feature is not None:
        return (*feature, True)
    if not set(words) & intent_phrases().lexicon["cast_words"]:
        return None
    other = said_name(words, _all_spells())
    return (*other, False) if other is not None else None


def names_spell(actor: Creature, words: list[str]) -> bool:
    if named_spell(actor, words) is not None:
        return True
    long_names = [(key, name) for key, name in _all_spells() if len(name.split()) > 1]
    return said_name(words, long_names) is not None
