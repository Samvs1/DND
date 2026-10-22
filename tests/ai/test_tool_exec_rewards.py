"""grant_item, grant_xp, start_encounter executors: catalogue, caps, CR budget, confirm."""

from aidm.dm.tool_context import ToolContext
from aidm.models.encounter import EncounterStatus
from aidm.models.encounter_events import EncounterStarted
from aidm.models.events import CreatureAdded, InventoryChanged, XpGained
from aidm.models.world_events import AttitudeChanged, HostileActPending
from tests.ai.tool_fixtures import add_npc, apply_result, party_state, run_tool


def test_grant_item_catalogue_within_cap() -> None:
    state = party_state()
    result = run_tool(state, "grant_item", catalog_id="potion-of-healing", qty=1)
    event = result.events[0]
    assert isinstance(event, InventoryChanged)
    assert (event.creature_id, event.delta, event.qty) == ("fighter", 1, 2)
    torches = run_tool(state, "grant_item", catalog_id="torch", qty=10)
    assert torches.error is not None and "usable gear" in torches.error  # M27.5


def test_injection_grant_10000_gold_refused() -> None:
    state = party_state()
    gold = run_tool(state, "grant_item", catalog_id="gold", qty=100)
    assert gold.error is not None and "not a catalogue item" in gold.error
    assert gold.events == ()
    many = run_tool(state, "grant_item", catalog_id="arrow", qty=100)
    assert many.error is not None and many.events == ()


def test_grant_item_value_cap_by_region_tier() -> None:
    state = party_state()
    plate = run_tool(state, "grant_item", catalog_id="plate-armor")
    assert plate.error is not None and "cap of 75 gp" in plate.error
    two = run_tool(state, "grant_item", catalog_id="potion-of-healing", qty=2)
    assert two.error is not None
    state.world.region_tier = 2
    assert run_tool(state, "grant_item", catalog_id="potion-of-healing", qty=2).ok
    assert run_tool(state, "grant_item", catalog_id="potion-of-healing-superior").error


def test_grant_xp_tier_to_every_living_pc() -> None:
    state = party_state()
    state.creatures["wizard"].dead = True
    result = run_tool(state, "grant_xp", tier="moderate")
    gains = [e for e in result.events if isinstance(e, XpGained)]
    assert sorted(e.creature_id for e in gains) == ["cleric", "fighter", "rogue"]
    assert {e.amount for e in gains} == {75}


def test_start_encounter_within_budget() -> None:
    state = party_state()
    result = run_tool(
        state, "start_encounter", monster_ids=["goblin", "goblin"], terrain_tags=["forest"]
    )
    assert result.ok, result.error
    added = [e for e in result.events if isinstance(e, CreatureAdded)]
    assert [e.creature.id for e in added] == ["goblin-1", "goblin-2"]
    assert any(isinstance(e, EncounterStarted) for e in result.events)
    apply_result(state, result)
    assert state.encounter is not None and state.encounter.status is EncounterStatus.ACTIVE
    again = run_tool(state, "start_encounter", monster_ids=["goblin"])
    assert again.error is not None and "already" in again.error


def test_start_encounter_refusals() -> None:
    state = party_state()
    unknown = run_tool(state, "start_encounter", monster_ids=["tarrasque"])
    assert unknown.error is not None and "catalogue" in unknown.error
    too_strong = run_tool(state, "start_encounter", monster_ids=["troll"])
    assert too_strong.error is not None and "region" in too_strong.error
    deadly = run_tool(state, "start_encounter", monster_ids=["goblin"] * 6)
    assert deadly.error is not None and "too deadly" in deadly.error
    assert deadly.events == ()


def test_v1_hostile_act_confirm_before_combat() -> None:
    # v1: an unprompted attack on a friendly NPC became an instant 4v1 with no confirm step.
    state = party_state()
    add_npc(state, archetype="guard", name="Captain Rell", npc_id="npc-rell")
    pending = run_tool(state, "start_encounter", against_npcs=["npc-rell"])
    assert pending.pending is not None and pending.pending.tool == "start_encounter"
    assert "point of no return" in pending.pending.prompt
    # SPEC 6.3: "the acting player must confirm before start_encounter runs"
    assert pending.pending.actor_id == "fighter" and pending.pending.npc_ids == ("npc-rell",)
    assert not any(isinstance(e, CreatureAdded) for e in pending.events)
    assert [type(e) for e in pending.events] == [HostileActPending]
    apply_result(state, pending)
    assert state.encounter is None
    confirmed = run_tool(
        state, "start_encounter", ctx=ToolContext("fighter", True), against_npcs=["npc-rell"]
    )
    assert confirmed.ok, confirmed.error
    assert isinstance(confirmed.events[0], AttitudeChanged) and confirmed.events[0].hostile
    spawned = [e for e in confirmed.events if isinstance(e, CreatureAdded)]
    assert [e.creature.name for e in spawned] == ["Captain Rell"]
    apply_result(state, confirmed)
    assert state.encounter is not None and state.world.npcs["npc-rell"].hostile


def test_hostile_npc_fight_needs_no_confirm() -> None:
    state = party_state()
    add_npc(state, archetype="bandit", name="Vex", npc_id="npc-vex", hostile=True)
    result = run_tool(state, "start_encounter", against_npcs=["npc-vex"], surprise="hostile")
    assert result.ok and result.pending is None


def test_push_and_zone_effects_in_a_fight() -> None:
    state = party_state()
    apply_result(state, run_tool(state, "start_encounter", monster_ids=["goblin"]))
    assert state.encounter is not None
    start = state.encounter.combatants["goblin-1"].zone_id
    moved = False
    for seed in range(1, 40):
        result = run_tool(
            state,
            "creative_effect",
            seed=seed,
            actor="fighter",
            target="goblin-1",
            effect_kind="push",
            severity="major",
        )
        assert result.ok, result.error
        if len(result.events) > 1:
            moved = True
            break
    assert moved
    dark = run_tool(
        state,
        "creative_effect",
        actor="fighter",
        target=start,
        effect_kind="dark",
        severity="moderate",
        duration_rounds=5,
    )
    assert dark.ok and dark.events
    apply_result(state, dark)
    zone = state.encounter.zone_map.zone(start)
    assert [(s.kind, s.rounds_left) for s in zone.surfaces] == [("darkness", 2)]
    light = run_tool(state, "creative_effect", actor="fighter", target=start, effect_kind="light")
    apply_result(state, light)
    assert state.encounter.zone_map.zone(start).surfaces == []
    rubble = run_tool(
        state, "creative_effect", actor="fighter", target="nowhere", effect_kind="difficult_terrain"
    )
    assert rubble.error is not None and "unknown zone" in rubble.error
