"""Client -> server websocket messages (SPEC 10). Joined into `ClientMsg` by `protocol.py`.

Every message has a literal `type`. Player text fields are bounded; the session treats all text
as untrusted (SPEC 6.7). Host messages are accepted only from the host seat.

Public API: `Hello`, `CreateCharacter`, `RollAbilities`, `SubmitAction`, `CombatCommandMsg`,
`Suggestion`, `ConfirmHostile`, `CancelHostile`, `Vote`, `AnswerOffer`, `LevelUp`, `ShopBuy`,
`ShopSell`, `Give`, `Equip`, `Unequip`, `UseItem` (M7.5b: a potion outside a fight, on the
hero or a party member; `target_id` None = the hero), `RequestHitChances`, `Chat`, `HostStart`,
`HostPause`, `HostResume`, `HostKick`, `HostDifficulty`, `HostTtsToggle`, `HostSave`, `HostLoad`,
`HostNew`, `HostEnd`, `HostForceVote`, `ExportCharacter`, `ImportCharacter`, `Ping`;
`HOST_MESSAGES` (the host-only message classes); M11.1 defeat choices `DefeatRetry`,
`DefeatLoad`, `DefeatNew` (`DEFEAT_MESSAGES`: host or the sole player, phase defeated only);
M11.2 `DeviceRole` (`Hello.role`: "screen" = the shared display, "controller" = a phone seat;
`spectator: true` is the older spelling of role "screen"), `Typing` (composing on/off) and
`AudioSettingsMsg` (the screen's volumes and mutes, from any seated player); M13.1
`ScribeRevive` (pay the Scribe to rewrite a fallen hero, `aidm.rules.scribe`); M13.2 `ScribeSkip`
(host only: stop the Scribe's current line on every screen); M15.1 `HostTurnTimer` (host only:
the combat turn timer, off / 90 s / 3 min / 5 min); M20.2 `HelpUp` (outside a fight, help a
downed party member up to 1 HP, `aidm.rules.downed`); M23.4 `AnswerQuestOffer` (Accept / Not now
on the giver's quest card, `aidm.rules.quest_offers`); M23.8 `AskWhatNow` (the What now? button:
answered at once from the state, never a turn, `aidm.rules.quest_hints`); M23.9 `ChooseFinale`
(the finale card: one of the plan's two endings; only `confirm: true`, sent after the phone's
"Are you sure? This ends the story", makes the choice, `aidm.rules.finale`); M26.3 `Presented`
(a screen has finished showing every event line and dice roll up to `seq`; AI turns wait for it);
M27.7 `CopyScroll` (the Spellbook tab: a wizard copies a carried scroll into the spellbook out of
a fight, `aidm.rules.scrolls`); M29.7a `HandOver` (hand items, a keepsake or gold to another
hero, `aidm.rules.hero_handing`).
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.abilities import Skill
from aidm.models.campaign_state import OfferChoice
from aidm.models.commands import Command
from aidm.models.creation import CreationChoices
from aidm.models.leveling import LevelUpChoices

MAX_TEXT = 1000
MAX_NAME = 40
MAX_IMPORT = 48_000  # a character JSON document; the socket refuses frames over 64 KB


class _Client(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DeviceRole(StrEnum):
    CONTROLLER = "controller"  # /play: a seat with private data and actions
    SCREEN = "screen"  # /screen: the shared display, public feed only, cannot act


class Hello(_Client):
    type: Literal["hello"] = "hello"
    name: str = Field(min_length=1, max_length=MAX_NAME)
    token: str | None = Field(default=None, max_length=200)
    last_seq: int | None = Field(default=None, ge=0)
    role: DeviceRole = DeviceRole.CONTROLLER
    spectator: bool = False  # older spelling of role "screen"


class CreateCharacter(_Client):
    type: Literal["create_character"] = "create_character"
    choices: CreationChoices


class RollAbilities(_Client):
    type: Literal["roll_abilities"] = "roll_abilities"


class SubmitAction(_Client):
    type: Literal["submit_action"] = "submit_action"
    text: str = Field(max_length=MAX_TEXT)


class CombatCommandMsg(_Client):
    type: Literal["combat_command"] = "combat_command"
    command: Command


class Suggestion(_Client):
    type: Literal["suggestion"] = "suggestion"
    text: str = Field(min_length=1, max_length=MAX_TEXT)


class ConfirmHostile(_Client):
    type: Literal["confirm_hostile"] = "confirm_hostile"


class CancelHostile(_Client):
    type: Literal["cancel_hostile"] = "cancel_hostile"


class Vote(_Client):
    type: Literal["vote"] = "vote"
    vote_id: str
    ready: bool


class AnswerOffer(_Client):
    type: Literal["answer_offer"] = "answer_offer"
    choice: OfferChoice
    skill: Skill | None = None


class AnswerQuestOffer(_Client):
    type: Literal["answer_quest_offer"] = "answer_quest_offer"
    quest_id: str = Field(min_length=1, max_length=MAX_NAME * 2)
    accept: bool


class ChooseFinale(_Client):
    type: Literal["choose_finale"] = "choose_finale"
    option_id: str = Field(min_length=1, max_length=MAX_NAME)
    confirm: bool = False


class LevelUp(_Client):
    type: Literal["level_up"] = "level_up"
    choices: LevelUpChoices


class ShopBuy(_Client):
    type: Literal["shop_buy"] = "shop_buy"
    npc_id: str
    item_id: str
    qty: int = Field(default=1, ge=1, le=99)


class ScribeRevive(_Client):
    """M13.1: pay the Scribe (from the sender's own hero) to rewrite a fallen hero."""

    type: Literal["scribe_revive"] = "scribe_revive"
    target_id: str = Field(min_length=1, max_length=64)


class ScribeSkip(_Client):
    """M13.2: the host skips the Scribe's current line (`line_id` optional, else the last one)."""

    type: Literal["scribe_skip"] = "scribe_skip"
    line_id: str | None = Field(default=None, max_length=64)


class ShopSell(_Client):
    type: Literal["shop_sell"] = "shop_sell"
    npc_id: str
    item_id: str
    qty: int = Field(default=1, ge=1, le=99)


class Give(_Client):
    """Hand something to an NPC who is here: `item_id` is an inventory item key, or (M23.3) the id
    of a keepsake the hero carries (a quest item is delivered this way)."""

    type: Literal["give"] = "give"
    npc_id: str
    item_id: str


class HandOver(_Client):
    """Hand something to another hero (M29.7a): `item_id` an inventory item key (`qty` copies) or
    the id of a keepsake the hero carries, and/or `gold` coins."""

    type: Literal["hand_over"] = "hand_over"
    to_id: str = Field(min_length=1, max_length=MAX_NAME * 2)
    item_id: str | None = Field(default=None, max_length=MAX_NAME * 3)
    qty: int = Field(default=1, ge=1, le=99)
    gold: int = Field(default=0, ge=0, le=100_000)


class Equip(_Client):
    type: Literal["equip"] = "equip"
    item_id: str


class Unequip(_Client):
    type: Literal["unequip"] = "unequip"
    item_id: str


class Drop(_Client):
    type: Literal["drop"] = "drop"
    item_id: str


class UseItem(_Client):
    type: Literal["use_item"] = "use_item"
    item_id: str
    target_id: str | None = None


class CopyScroll(_Client):
    type: Literal["copy_scroll"] = "copy_scroll"
    item_id: str = Field(min_length=1, max_length=64)


class HelpUp(_Client):
    type: Literal["help_up"] = "help_up"
    target_id: str = Field(min_length=1, max_length=64)


class AskWhatNow(_Client):
    type: Literal["what_now"] = "what_now"


class RequestSheet(_Client):
    type: Literal["request_sheet"] = "request_sheet"


class RequestHitChances(_Client):
    type: Literal["request_hit_chances"] = "request_hit_chances"
    target_id: str


class Chat(_Client):
    type: Literal["chat"] = "chat"
    text: str = Field(min_length=1, max_length=MAX_TEXT)


class HostStart(_Client):
    type: Literal["host_start"] = "host_start"
    theme: str | None = Field(default=None, max_length=300)


class HostPause(_Client):
    type: Literal["host_pause"] = "host_pause"


class HostResume(_Client):
    type: Literal["host_resume"] = "host_resume"


class HostKick(_Client):
    type: Literal["host_kick"] = "host_kick"
    player_id: str


class HostDifficulty(_Client):
    type: Literal["host_difficulty"] = "host_difficulty"
    monster_hp: float = Field(default=1.0, ge=0.25, le=3.0)
    monster_damage: float = Field(default=1.0, ge=0.25, le=3.0)


class HostTtsToggle(_Client):
    type: Literal["host_tts_toggle"] = "host_tts_toggle"
    enabled: bool


class HostTurnTimer(_Client):
    """M15.1: the host's combat turn timer in seconds (0 = off)."""

    type: Literal["host_turn_timer"] = "host_turn_timer"
    seconds: Literal[0, 90, 180, 300]


class HostSave(_Client):
    type: Literal["host_save"] = "host_save"


class HostLoad(_Client):
    type: Literal["host_load"] = "host_load"
    campaign_id: str


class HostNew(_Client):
    type: Literal["host_new"] = "host_new"


class HostEnd(_Client):
    type: Literal["host_end"] = "host_end"


class HostForceVote(_Client):
    type: Literal["host_force_vote"] = "host_force_vote"


class ExportCharacter(_Client):
    type: Literal["export_character"] = "export_character"


class ImportCharacter(_Client):
    type: Literal["import_character"] = "import_character"
    text: str = Field(min_length=2, max_length=MAX_IMPORT)


class Ping(_Client):
    type: Literal["ping"] = "ping"


class Presented(_Client):
    """M26.3: the screen's show queue has shown everything up to `seq` (the highest `seq` of an
    event line or dice roll it finished). Only screens count; a player's is ignored."""

    type: Literal["presented"] = "presented"
    seq: int = Field(ge=0)


class DefeatRetry(_Client):
    """M11.1: after a party wipe, go back to the last checkpoint (host or the sole player)."""

    type: Literal["defeat_retry"] = "defeat_retry"


class DefeatLoad(_Client):
    type: Literal["defeat_load"] = "defeat_load"
    campaign_id: str = Field(min_length=1, max_length=64)


class DefeatNew(_Client):
    type: Literal["defeat_new"] = "defeat_new"


class Typing(_Client):
    """M11.2: the player is composing (`on`) or stopped; expires on the server after ~8 s."""

    type: Literal["typing"] = "typing"
    on: bool


class AudioSettingsMsg(_Client):
    """M11.2: set the shared screen's audio (any seated player, last write wins)."""

    type: Literal["audio_settings"] = "audio_settings"
    narration_volume: int = Field(ge=0, le=100)
    music_volume: int = Field(ge=0, le=100)
    narration_muted: bool = False
    music_muted: bool = False
    effects_volume: int = Field(default=80, ge=0, le=100)  # M26.8: the dice sounds
    effects_muted: bool = False


HOST_MESSAGES: tuple[type[BaseModel], ...] = (
    HostStart,
    HostPause,
    HostResume,
    HostKick,
    HostDifficulty,
    HostTtsToggle,
    HostTurnTimer,
    HostSave,
    HostLoad,
    HostNew,
    HostEnd,
    HostForceVote,
)

DEFEAT_MESSAGES: tuple[type[BaseModel], ...] = (DefeatRetry, DefeatLoad, DefeatNew)
