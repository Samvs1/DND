"""M19.2 (owner playtest 2026-10-10): attacking an NPC you were talking to starts the fight with
that NPC in your zone, and your swing is rolled right away (BG3 style) before the first turn."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from aidm.dm.fake_llm import fake_calls, fake_text
from aidm.dm.tools import StartEncounterArgs
from aidm.models.combat_events import AttackRolled, SpellCast
from aidm.models.encounter_events import EncounterStarted, TurnStarted
from aidm.models.protocol_client import ConfirmHostile, SubmitAction
from aidm.rules.scene import current_scene
from tests.ai.tool_fixtures import run_tool
from tests.session.defeat_fixtures import end_turns_until_over, hurt
from tests.session.table_fixtures import assert_replays, fake_llm, join, running

OPEN = {"against_npcs": ["npc-mira"], "opening_strike_on": "npc-mira"}


def test_opening_strike_must_name_a_foe_of_the_fight() -> None:
    with pytest.raises(ValidationError):
        StartEncounterArgs(against_npcs=["npc-mira"], opening_strike_on="npc-bob")
    assert StartEncounterArgs(**OPEN).opening_strike_on == "npc-mira"


async def test_the_swing_that_starts_a_fight_is_rolled_before_the_first_turn(
    tmp_path: Path,
) -> None:
    llm, _ = fake_llm(tmp_path, [fake_calls([("start_encounter", OPEN)]), fake_text("Steel!")])
    async with running(llm) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text="I swing my hammer at Mira"))
        await table.settle()
        ann.send(ConfirmHostile())
        await table.settle()
        events = [entry.event for entry in table.log]
        start = next(i for i, e in enumerate(events) if isinstance(e, EncounterStarted))
        started = events[start]
        assert isinstance(started, EncounterStarted)
        zones = {c.creature_id: c.zone_id for c in started.encounter.combatants.values()}
        assert len(set(zones.values())) == 1  # Mira stands where the party stands
        strikes = [
            (i, e) for i, e in enumerate(events) if isinstance(e, AttackRolled) and i > start
        ]
        first_turn = next(
            (i for i, e in enumerate(events) if isinstance(e, TurnStarted) and i > start),
            len(events),
        )
        assert strikes and strikes[0][0] < first_turn
        assert strikes[0][1].attacker_id == "fighter"
        assert_replays(table)


async def test_a_fight_without_an_opening_strike_rolls_nothing_first(tmp_path: Path) -> None:
    plain = fake_calls([("start_encounter", {"against_npcs": ["npc-mira"]})])
    llm, _ = fake_llm(tmp_path, [plain, fake_text("They square up.")])
    async with running(llm) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text="I square up to Mira"))
        await table.settle()
        ann.send(ConfirmHostile())
        await table.settle()
        events = [entry.event for entry in table.log]
        start = next(i for i, e in enumerate(events) if isinstance(e, EncounterStarted))
        first_turn = next(i for i, e in enumerate(events) if isinstance(e, TurnStarted))
        between = events[start:first_turn]
        assert not any(isinstance(e, AttackRolled) for e in between)


async def test_the_declared_spell_opens_the_fight(tmp_path: Path) -> None:
    # M20.5 (playtest 3): the warlock cast Eldritch Blast and the engine rolled her dagger.
    spell = {**OPEN, "opening_attack": "fire-bolt"}
    llm, _ = fake_llm(tmp_path, [fake_calls([("start_encounter", spell)]), fake_text("Fire!")])
    async with running(llm) as (table, _):
        ann = await join(table, "Ann", "wizard")
        ann.send(SubmitAction(text="I hurl a fire bolt at Mira"))
        await table.settle()
        ann.send(ConfirmHostile())
        await table.settle()
        events = [entry.event for entry in table.log]
        start = next(i for i, e in enumerate(events) if isinstance(e, EncounterStarted))
        first_turn = next(
            (i for i, e in enumerate(events) if isinstance(e, TurnStarted) and i > start),
            len(events),  # the bolt may drop Mira before anyone's turn
        )
        opening = events[start:first_turn]
        casts = [e for e in opening if isinstance(e, SpellCast)]
        assert casts and casts[0].caster_id == "wizard" and casts[0].spell_id == "fire-bolt"
        strikes = [e for e in opening if isinstance(e, AttackRolled)]
        assert strikes and strikes[0].attack == "Fire Bolt"
        assert_replays(table)


async def test_a_slain_npc_stays_dead(tmp_path: Path) -> None:
    # M20.5 (playtest 3): the boss died, was talked to as if alive, and was fought a second time.
    plain = fake_calls([("start_encounter", {"against_npcs": ["npc-mira"]})])
    llm, _ = fake_llm(tmp_path, [plain, fake_text("They square up.")])
    async with running(llm) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text="I square up to Mira"))
        await table.settle()
        ann.send(ConfirmHostile())
        await table.settle()
        mira = next(c for c in table.state.creatures.values() if c.name == "Mira")
        assert mira.npc_id == "npc-mira"
        await hurt(table, mira.id, 999)
        await end_turns_until_over(table, [ann])
        assert table.state.world.npcs["npc-mira"].dead
        assert "npc-mira" not in current_scene(table.state).npc_ids
        again = run_tool(table.state, "start_encounter", against_npcs=["npc-mira"])
        assert not again.ok and "dead" in (again.error or "")
        assert_replays(table)
