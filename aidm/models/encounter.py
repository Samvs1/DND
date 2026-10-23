"""Encounter (combat) state: who fights, where they stand, whose turn it is (SPEC 6.1, 7.2, 7.3).

`GameState.encounter` holds at most one `Encounter`. It stays after the fight ends (status no
longer ACTIVE) so the UI and narrator can show the outcome; the next `start_encounter` replaces
it. Creatures themselves stay in `GameState.creatures`; the encounter only references them by id.

State model (all mutable state models, changed only by the reducer, new fields need defaults):
- `Side`: PARTY (PCs and allied NPCs), HOSTILE, NEUTRAL (bystanders: never decide the outcome).
- `WithdrawReason`: FLED / SURRENDERED. A withdrawn combatant is out of the turn order and no
  longer counts for victory or defeat, but stays in state.
- `TurnEconomy(action, bonus_action, movement_left, reaction, dashed, disengaged, attacks_left,
  once_per_turn_used)`: the per-turn budget (BG3: action, bonus action, movement in feet, one
  reaction). Only the active creature's action/bonus/movement are meaningful; `reaction`
  refreshes at the start of the creature's own turn. `dashed` / `disengaged` are flags the M3.3
  commands set. `attacks_left` counts the further attacks of an Attack action already taken
  (Extra Attack); `once_per_turn_used` lists feature ids whose once-per-turn rider applied
  (Sneak Attack). Both reset with the fresh economy of the next turn.
- `Combatant(creature_id, side, zone_id, economy, xp, withdrawn, surprised)`: one participant.
  `zone_id` IS the creature's position (a zone of `Encounter.zone_map`). `xp` is the kill XP it is
  worth (SRD monster `xp`; 0 for PCs and allies). `surprised` records the start-of-fight state
  (the mechanics are the data-driven "surprised" condition).
- `InitiativeEntry(creature_id, roll, modifier, total, dex)`: BG3 1d4 + DEX; `roll` is the d4.
- `EncounterStatus`: ACTIVE / VICTORY / DEFEAT / FLED / PARLEY.
- `Encounter(id, zone_map, combatants, initiative, round, active_index, turn_open, status)`:
  `initiative` is sorted (highest total first) and never re-sorted. `active_index` points into it:
  -1 before the first turn. `turn_open` is True between `TurnStarted` and `TurnEnded`.
  `round` starts at 1 and increments when the order wraps. Helpers: `combatant(cid)`,
  `positions()` (creature id -> zone id), `active_id()` (None when no turn is open).
  `node_id` (M29.9a) is the place the fight started.

Setup inputs (frozen, built by the DM tool or the session):
- `SurpriseKind`: NONE / PARTY (the party is ambushed) / HOSTILE (the party ambushes).
- `PartyPlacement(creature_id, zone_id, side)`: an existing creature joining the fight.
- `MonsterSpawn(monster, zone_id, side, name, npc_id, hp_scale)`: an SRD monster index to
  instantiate; `hp_scale` (M29.6, at most 1) scales its hit points on top of the host
  difficulty (a boss too strong alone for a small party, `aidm.rules.encounter_offer`).
- `EncounterSetup(encounter_id, zone_map, party, monsters, surprise, offer_id)`: `offer_id`
  names the waiting offer this fight answers (its `OfferResolved` is already emitted).
- `Difficulty`: EASY / MEDIUM / HARD / DEADLY (the encounter budget tiers).
- `BudgetCheck(adjusted_xp, deadly_budget, difficulty, allowed)`: a rated monster list
  (`aidm.rules.encounter_budget.check_encounter_budget`).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.zones import ZoneMap


class Side(StrEnum):
    PARTY = "party"
    HOSTILE = "hostile"
    NEUTRAL = "neutral"


class WithdrawReason(StrEnum):
    FLED = "fled"
    SURRENDERED = "surrendered"


class EncounterStatus(StrEnum):
    ACTIVE = "active"
    VICTORY = "victory"
    DEFEAT = "defeat"
    FLED = "fled"
    PARLEY = "parley"


class SurpriseKind(StrEnum):
    NONE = "none"
    PARTY = "party"
    HOSTILE = "hostile"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    DEADLY = "deadly"


class TurnEconomy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action: bool = False
    bonus_action: bool = False
    movement_left: int = Field(default=0, ge=0)
    reaction: bool = True
    dashed: bool = False
    disengaged: bool = False
    attacks_left: int = Field(default=0, ge=0)
    once_per_turn_used: tuple[str, ...] = ()


class Combatant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    creature_id: str = Field(min_length=1)
    side: Side
    zone_id: str = Field(min_length=1)
    economy: TurnEconomy = TurnEconomy()
    xp: int = Field(default=0, ge=0)
    withdrawn: WithdrawReason | None = None
    surprised: bool = False


class InitiativeEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    creature_id: str = Field(min_length=1)
    roll: int = Field(ge=1, le=4)
    modifier: int
    total: int
    dex: int = Field(ge=1)


class Encounter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    zone_map: ZoneMap
    combatants: dict[str, Combatant] = Field(default_factory=dict[str, Combatant])
    initiative: list[InitiativeEntry] = Field(default_factory=list[InitiativeEntry])
    round: int = Field(default=1, ge=1)
    active_index: int = Field(default=-1, ge=-1)
    turn_open: bool = False
    status: EncounterStatus = EncounterStatus.ACTIVE
    node_id: str | None = None  # M29.9a T8: the place the fight started (None in older saves)

    def combatant(self, creature_id: str) -> Combatant:
        return self.combatants[creature_id]

    def positions(self) -> dict[str, str]:
        return {cid: c.zone_id for cid, c in self.combatants.items()}

    def active_id(self) -> str | None:
        if not self.turn_open or self.active_index < 0:
            return None
        return self.initiative[self.active_index].creature_id


class PartyPlacement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    creature_id: str = Field(min_length=1)
    zone_id: str = Field(min_length=1)
    side: Side = Side.PARTY


class MonsterSpawn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    monster: str = Field(min_length=1)
    zone_id: str = Field(min_length=1)
    side: Side = Side.HOSTILE
    name: str | None = None
    npc_id: str | None = None  # M20.5: the world NPC this creature is (its death is theirs)
    hp_scale: float = Field(default=1.0, gt=0, le=1.0)


class EncounterSetup(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    encounter_id: str = Field(min_length=1)
    zone_map: ZoneMap
    party: tuple[PartyPlacement, ...] = ()
    monsters: tuple[MonsterSpawn, ...] = ()
    surprise: SurpriseKind = SurpriseKind.NONE
    offer_id: str | None = None  # M29.9a T8: the offer this fight answers (already resolved)


class BudgetCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    adjusted_xp: int = Field(ge=0)
    deadly_budget: int = Field(ge=0)
    difficulty: Difficulty | None
    allowed: bool
