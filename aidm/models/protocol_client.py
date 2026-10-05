"""Client -> server websocket messages (SPEC 10). Joined into `ClientMsg` by `protocol.py`.

Every message has a literal `type`. Player text fields are bounded; the session treats all text
as untrusted (SPEC 6.7). Host messages are accepted only from the host seat.

Public API: `Hello`, `CreateCharacter`, `RollAbilities`, `SubmitAction`, `CombatCommandMsg`,
`Suggestion`, `ConfirmHostile`, `CancelHostile`, `Vote`, `AnswerOffer`, `LevelUp`, `ShopBuy`,
`ShopSell`, `Equip`, `Unequip`, `RequestHitChances`, `Chat`, `HostStart`, `HostPause`,
`HostResume`, `HostKick`, `HostDifficulty`, `HostTtsToggle`, `HostSave`, `HostLoad`, `HostNew`,
`HostEnd`, `HostForceVote`, `Ping`; `HOST_MESSAGES` (the host-only message classes).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.abilities import Skill
from aidm.models.campaign_state import OfferChoice
from aidm.models.commands import Command
from aidm.models.creation import CreationChoices
from aidm.models.leveling import LevelUpChoices

MAX_TEXT = 1000
MAX_NAME = 40


class _Client(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Hello(_Client):
    type: Literal["hello"] = "hello"
    name: str = Field(min_length=1, max_length=MAX_NAME)
    token: str | None = Field(default=None, max_length=200)


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


class LevelUp(_Client):
    type: Literal["level_up"] = "level_up"
    choices: LevelUpChoices


class ShopBuy(_Client):
    type: Literal["shop_buy"] = "shop_buy"
    npc_id: str
    item_id: str
    qty: int = Field(default=1, ge=1, le=99)


class ShopSell(_Client):
    type: Literal["shop_sell"] = "shop_sell"
    npc_id: str
    item_id: str
    qty: int = Field(default=1, ge=1, le=99)


class Equip(_Client):
    type: Literal["equip"] = "equip"
    item_id: str


class Unequip(_Client):
    type: Literal["unequip"] = "unequip"
    item_id: str


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


class Ping(_Client):
    type: Literal["ping"] = "ping"


HOST_MESSAGES: tuple[type[BaseModel], ...] = (
    HostStart,
    HostPause,
    HostResume,
    HostKick,
    HostDifficulty,
    HostTtsToggle,
    HostSave,
    HostLoad,
    HostNew,
    HostEnd,
    HostForceVote,
)
