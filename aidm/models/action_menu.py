"""The acting hero's menu of legal actions and the model's pick from it (M36, SPEC 6.2).

Built by `aidm.rules.action_menu.build_menu` on every typed line; the model answers only with
entry ids (`MenuChoice`), and the engine runs the steps through the button code paths. Never
stored, never an event payload. Ids are stable and built from data keys (`attack:longsword`,
`cast:fire-bolt`, `feature:turn-undead`, `item:potion-of-healing`, `dash`, `move`), so the eval
corpus can name them.

Public API:
- `MenuScope` (fight, off_turn, explore, offer), `ActionKind`, `TargetKind`, `EntryCost`,
  `STRIKE_KINDS` (the kinds that may start a fight).
- `MenuTarget(id, label, kind)`: a creature, zone, person (an NPC here), place (a travel
  destination), thing (a feature here) or foe the entries may aim at, its label written for a
  model choosing ("Kobold A, 15 ft, unhurt", "Lamplighters' Rest, next door"). M36.3: the foes of
  a waiting encounter offer are `foe:<monster>` (or the master's NPC id) until the fight spawns
  them.
- `MenuEntry(id, kind, label, target_ids, max_targets, qty_max, zone_ids, cost, spent, note,
  target_notes, approach, far, option, spell_id, slot_level, feature_id, item, use_id,
  condition, skill, draw, quest_id, starts_fight)`: `max_targets` 0 means no target;
  `zone_ids` a second pick (where a push sends the foe); `spent` = the action or bonus action
  it needs is used this turn (the rules answer it plainly); `approach` = target -> feet the
  hero moves first (a melee strike out of reach), `far` = targets out of reach this turn;
  `option` .. `draw` are the data keys the executor needs (attack option, spell, lowest slot,
  feature, item, gear use, condition ended, surrender skill, a stowed weapon drawn first).
  M36.3: `quest_id` names the quest a quest-card answer answers (only a `quest` entry has
  one); `starts_fight` = a strike at a waiting offer's foes (the offer is answered as Fight
  and the strike plays on the hero's turn). Out of a fight `option` carries the entry's
  choice (rest kind, offer answer, quest accept; M36.8c: a `feed:` draught's "their_own", a
  person strike's attack option), `item` an inventory key, keepsake id or world item id,
  `qty_max` the count carried or held.
- `ActionMenu(scope, actor_id, entries, targets)`: entry ids and target ids are unique and every
  target id an entry names is in `targets`.
- `MenuStep(entry, targets, qty)`, `MenuChoice(steps, other, other_text, other_first)`: up to 4
  ordered steps, `other` (a stunt or something off the menu), or both (M36.5, DECISIONS: "I leap
  onto the table and fire at the kobold" is a stunt and an attack). `other_text` is the
  off-menu part in the player's words ("" = the whole line); `other_first` = it happens before
  the steps (else after them).
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_STEPS = 4
ENTRY_ID_PATTERN = r"^[a-z0-9][a-z0-9_:-]*$"


class MenuScope(StrEnum):
    FIGHT = "fight"
    OFF_TURN = "off_turn"
    EXPLORE = "explore"
    OFFER = "offer"


class ActionKind(StrEnum):
    ATTACK = "attack"
    CAST = "cast"
    FEATURE = "feature"
    ITEM = "item"
    GEAR = "gear"
    THROW = "throw"
    MOVE = "move"
    STAND = "stand"
    DASH = "dash"
    DISENGAGE = "disengage"
    DODGE = "dodge"
    HIDE = "hide"
    HELP = "help"
    SHOVE = "shove"
    JUMP = "jump"
    END_CONDITION = "end_condition"
    FLEE = "flee"
    END_TURN = "end_turn"
    SURRENDER = "surrender"
    TALK = "talk"
    LOOK = "look"
    SEARCH = "search"
    INVENTORY = "inventory"
    WHAT_NOW = "what_now"
    TRAVEL = "travel"
    UNLOCK = "unlock"
    REST = "rest"
    SHOP = "shop"
    BUY = "buy"
    SELL = "sell"
    GIVE = "give"
    HAND = "hand"
    PAY = "pay"
    TAKE = "take"
    LIFT = "lift"
    EQUIP = "equip"
    UNEQUIP = "unequip"
    DROP = "drop"
    PUT_OUT = "put_out"
    COPY_SCROLL = "copy_scroll"
    OFFER = "offer"
    QUEST = "quest"
    HELP_UP = "help_up"


type TargetKind = Literal["foe", "ally", "self", "zone", "person", "place", "thing"]
STRIKE_KINDS = frozenset({ActionKind.ATTACK, ActionKind.CAST, ActionKind.FEATURE, ActionKind.THROW})
type EntryCost = Literal["action", "bonus", "attack", "extra", "movement", "free"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MenuTarget(_Frozen):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    kind: TargetKind


class MenuEntry(_Frozen):
    id: str = Field(pattern=ENTRY_ID_PATTERN)
    kind: ActionKind
    label: str = Field(min_length=1)
    target_ids: tuple[str, ...] = ()
    max_targets: int = Field(default=0, ge=0)
    qty_max: int = Field(default=1, ge=1)
    zone_ids: tuple[str, ...] = ()
    cost: EntryCost = "action"
    spent: bool = False
    note: str = ""
    target_notes: dict[str, str] = Field(default_factory=dict[str, str])
    approach: dict[str, int] = Field(default_factory=dict[str, int])
    far: tuple[str, ...] = ()
    option: str | None = None
    spell_id: str | None = None
    slot_level: int | None = Field(default=None, ge=1, le=9)
    feature_id: str | None = None
    item: str | None = None
    use_id: str | None = None
    condition: str | None = None
    skill: str | None = None
    draw: str | None = None
    quest_id: str | None = None
    starts_fight: bool = False

    @model_validator(mode="after")
    def _targets_fit(self) -> Self:
        named = set(self.target_ids)
        if self.max_targets == 0 and named:
            raise ValueError(f"{self.id}: targets listed but max_targets is 0")
        loose = (set(self.approach) | set(self.far) | set(self.target_notes)) - named
        if loose:
            raise ValueError(f"{self.id}: notes for targets not listed: {sorted(loose)}")
        if self.starts_fight and self.kind not in STRIKE_KINDS:
            raise ValueError(f"{self.id}: only a strike can start a fight")
        if (self.quest_id is not None) != (self.kind is ActionKind.QUEST):
            raise ValueError(f"{self.id}: a quest answer names its quest, nothing else does")
        return self


class ActionMenu(_Frozen):
    scope: MenuScope
    actor_id: str = Field(min_length=1)
    entries: tuple[MenuEntry, ...] = ()
    targets: tuple[MenuTarget, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [e.id for e in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate entry ids: {sorted(i for i in ids if ids.count(i) > 1)}")
        known = {t.id for t in self.targets}
        for entry in self.entries:
            missing = (set(entry.target_ids) | set(entry.zone_ids)) - known
            if missing:
                raise ValueError(f"{entry.id}: unknown targets {sorted(missing)}")
        target_ids = [t.id for t in self.targets]
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("duplicate target ids")
        return self


class MenuStep(_Frozen):
    entry: str = Field(min_length=1)
    targets: tuple[str, ...] = ()
    qty: int = Field(default=1, ge=1)


class MenuChoice(_Frozen):
    steps: tuple[MenuStep, ...] = Field(default=(), max_length=MAX_STEPS)
    other: bool = False
    other_text: str = ""
    other_first: bool = False

    @model_validator(mode="after")
    def _steps_or_other(self) -> Self:
        if not self.other and not self.steps:
            raise ValueError("a choice needs steps, other or both")
        if not self.other and (self.other_text or self.other_first):
            raise ValueError("other_text and other_first belong to other")
        return self
