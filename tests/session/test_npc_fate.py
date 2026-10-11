"""An NPC's fight creature dying is the NPC's death (M20.5, playtest 3: the boss died, stayed in the
scene and was fought again). Saves from before M20.5 have no `npc_id`: the one NPC of that name."""

from aidm.models.combat_events import CreatureRevived
from aidm.models.events import CreatureAdded, CreatureDied
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.session.reducer import apply, replay
from tests.ai.guard_fixtures import inn_state
from tests.ai.tool_fixtures import add_npc


def _foe(cid: str, name: str, npc_id: str | None = None) -> Creature:
    return Creature(id=cid, name=name, kind=CreatureKind.MONSTER, max_hp=4, hp=4, npc_id=npc_id)


def test_npc_creature_death_and_revival_follow_the_npc() -> None:
    initial = inn_state()
    events = [
        CreatureAdded(creature=_foe("commoner-1", "Mira", "npc-mira")),
        CreatureDied(creature_id="commoner-1"),
    ]
    state = replay(initial, events)
    assert state.world.npcs["npc-mira"].dead and not state.world.npcs["npc-hobb"].dead
    apply(state, CreatureRevived(creature_id="commoner-1"))
    assert not state.world.npcs["npc-mira"].dead


def test_old_saves_match_the_one_npc_with_that_name() -> None:
    state: GameState = inn_state()
    apply(state, CreatureAdded(creature=_foe("acolyte-1", "Hobb")))
    apply(state, CreatureDied(creature_id="acolyte-1"))
    assert state.world.npcs["npc-hobb"].dead
    twins = inn_state()
    add_npc(twins, "npc-mira-2", name="Mira", role="cook")
    apply(twins, CreatureAdded(creature=_foe("commoner-1", "Mira")))
    apply(twins, CreatureDied(creature_id="commoner-1"))
    assert not twins.world.npcs["npc-mira"].dead and not twins.world.npcs["npc-mira-2"].dead
