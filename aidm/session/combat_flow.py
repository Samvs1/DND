"""Combat inside the table actor (SPEC 6.1 combat turns, 10 combat rules).

`advance` drives the fight until a PLAYER must act: it opens turns (`rules.turns.begin_turn`),
plays monsters with `rules.monster_ai` (via `CombatRunner.play_turn` + legendary actions),
plays a hero whose player is away (disconnected, kicked, never seated) or who is down with
`rules.party_ai.safe_default_turn` (Dodge, or Dash toward allies), and stops at a connected
player's standing hero: the segment since the last narration is told in ONE
`narrate_round_segment` call, then `combat_state` + `turn_prompt` go out and the turn clock
starts (`turn_clock`, M15.1: the host's timer, default 3 min, only when another player waits;
an owner who is away keeps the turn for a short reconnect grace; on timeout the safe default
plays that turn). The fight's end sends `combat_state` with no combat and the `outcome`.
Only that hero's player may send `combat_command`; anyone else gets `not_your_turn` and nothing
is consumed. A fight's end runs loot (`end_encounter_with_loot`), bystander deeds
(`combat_help_deed_events`), region rewards (`resolution_reward_events`) and spoke milestones
(`milestone_events`, M9.2), tells the last segment, records it and returns to exploration.
Every mid-fight segment narration is recorded too (`narration_recorded`, M20.1).
A lost fight that wiped the party is turned into the DEFEATED phase right after the job by
`defeat_flow.after_job` (M11.1); the fight start was marked as a retry checkpoint.

Public API: `MAX_COMBAT_STEPS`, `runner`, `after_resolution`, `begin_combat`, `advance`,
`tell_segment`, `after_player_step`, `player_command`, `turn_timeout`, `autoplay_safe`,
`finish_fight`, `end_player_turn`.
"""

from collections.abc import Sequence

from aidm.dm.narrator import narrate_round_segment, record_narration
from aidm.models.commands import AnyCommand, EndTurnCommand, MonsterActionCommand
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent
from aidm.models.protocol_server import CombatState, ErrorCode, NoticeKind, TurnPrompt
from aidm.rules.command_checks import CommandRefused
from aidm.rules.commands import execute_command
from aidm.rules.encounter import encounter_outcome
from aidm.rules.loot import end_encounter_with_loot, loot_rng
from aidm.rules.milestones import milestone_events
from aidm.rules.party_ai import safe_default_turn
from aidm.rules.quest_rewards import resolution_reward_events
from aidm.rules.social_deeds import combat_help_deed_events
from aidm.rules.turns import begin_turn, next_turn
from aidm.session import checkpoints, turn_clock, votes
from aidm.session.combat_runner import CombatRunner
from aidm.session.table_core import Player, TableCore
from aidm.session.telling import maybe_epilogue, remember, tell
from aidm.session.views import public_combat

MAX_COMBAT_STEPS = 400
FIGHT_OVER = "The fight is over."


def runner(core: TableCore) -> CombatRunner:
    return CombatRunner(
        core.state,
        core.regs.combat,
        core.rng,
        on_event=lambda state, event: core.record(event, state.event_count - 1),
    )


async def after_resolution(core: TableCore, events: Sequence[AnyEvent]) -> None:
    if not core.in_combat and core.combat_active():
        await begin_combat(core)


async def begin_combat(core: TableCore) -> None:
    """Enter combat after the start was narrated (the segment starts empty); the fight start is
    a retry checkpoint (M11.1)."""
    checkpoints.mark_fight(core)
    core.in_combat = True
    core.segment = []
    core.pending = None
    for entry in core.queue:
        text = "The fight overtakes your plan; act again when it is over."
        core.notice(entry.player_id, NoticeKind.INFO, text)
    core.queue.clear()
    core.broadcast_queue()
    if core.vote is not None:
        votes.close_vote(core, passed=False, reason="a fight broke out")
    await advance(core)


def _prompt_player(core: TableCore, creature_id: str) -> Player | None:
    """The seat that gets this turn: a connected owner, or one who left within the reconnect
    grace (M15.1: a phone that drops for a moment does not lose its turns)."""
    creature = core.state.creatures[creature_id]
    owner = core.owner_of(creature_id)
    if creature.pc is None or creature.hp <= 0 or owner is None:
        return None
    return owner if owner.connected or turn_clock.grace_left(core, owner) > 0 else None


async def advance(core: TableCore) -> None:
    """Play AI turns until a player must act or the fight ends; a very long AI stretch
    yields to the inbox by re-scheduling itself as a new job (never a silent stall)."""
    run = runner(core)
    for _ in range(MAX_COMBAT_STEPS):
        state, enc = core.state, core.state.encounter
        if enc is None or enc.status is not EncounterStatus.ACTIVE:
            return
        status = encounter_outcome(state)
        if status is not None:
            await finish_fight(core, status)
            return
        if not enc.turn_open:
            if next_turn(state) is None:
                return
            core.apply_all(begin_turn(core.rng, state))
            continue
        active = enc.active_id()
        if active is None:
            return
        owner = _prompt_player(core, active)
        if owner is not None:
            await _prompt(core, active, owner)
            return
        if state.creatures[active].pc is not None:
            why = "downed" if state.creatures[active].hp <= 0 else "away"
            core.diag("auto_turn", creature_id=active, reason=why)
            autoplay_safe(core, run, active)
        else:
            run.play_turn(active)
        if encounter_outcome(state) is None:
            run.legendary()
    core.schedule(lambda: advance(core))


async def _prompt(core: TableCore, creature_id: str, owner: Player) -> None:
    await tell_segment(core)
    enc = core.state.encounter
    if enc is None:
        return
    key = f"{enc.id}:{enc.round}:{enc.active_index}"
    core.turn_key = key
    if owner.connected:
        turn_clock.start(core, key, turn_clock.limit_for(core, owner))
    else:
        turn_clock.grace(core, key, owner)
    core.broadcast(CombatState(combat=public_combat(core.state)))
    seconds = core.turn_left()
    core.broadcast(TurnPrompt(creature_id=creature_id, player_id=owner.id, seconds=seconds))
    core.diag("turn_prompt", creature_id=creature_id, player_id=owner.id, seconds=seconds)


async def tell_segment(core: TableCore, *, record: bool = True) -> str:
    """Tell the combat events since the last narration in ONE batched call; a mid-fight telling
    is recorded (M20.1: the save shows what the table heard; the fight's end records its own)."""
    if not core.segment:
        return ""
    events, core.segment = core.segment, []
    text = await tell(core, narrate_round_segment(core.state, events, core.llm))
    recorded = record_narration(core.state, text) if record else None
    if recorded is not None:
        core.apply(recorded)
        core.segment = [e for e in core.segment if e is not recorded]
    return text


def end_player_turn(core: TableCore) -> None:
    core.turn_key = None
    turn_clock.stop(core)


def autoplay_safe(core: TableCore, run: CombatRunner, creature_id: str) -> None:
    for command in safe_default_turn(core.state, creature_id):
        done = run.execute(command)
        if isinstance(done, EndTurnCommand) or encounter_outcome(core.state) is not None:
            break
    enc = core.state.encounter
    if enc is not None and enc.active_id() == creature_id and encounter_outcome(core.state) is None:
        run.execute(EndTurnCommand(actor_id=creature_id))


def _check_turn(core: TableCore, player: Player, command: AnyCommand) -> str | None:
    enc = core.state.encounter
    active = enc.active_id() if enc is not None and core.combat_active() else None
    if active is None or core.turn_key is None or player.creature_id != active:
        core.error(player.id, ErrorCode.NOT_YOUR_TURN, "It is not your turn.")
        return None
    if command.actor_id != active or isinstance(command, MonsterActionCommand):
        core.error(player.id, ErrorCode.INVALID, "You can only act for your own hero.")
        return None
    return active


async def player_command(core: TableCore, player: Player, command: AnyCommand) -> None:
    active = _check_turn(core, player, command)
    if active is None:
        return
    try:
        events = execute_command(core.state, command, core.regs.combat, core.rng)
    except CommandRefused as refused:
        core.error(player.id, ErrorCode.REFUSED, refused.reason, refused.code.value)
        return
    core.apply_all(events)
    await after_player_step(core, active)


async def after_player_step(core: TableCore, active: str) -> None:
    """After a hero's command or creative action: continue the fight if the turn is over."""
    enc = core.state.encounter
    turn_over = enc is None or enc.active_id() != active
    if encounter_outcome(core.state) is None and not turn_over:
        core.broadcast(CombatState(combat=public_combat(core.state)))
        return
    end_player_turn(core)
    if encounter_outcome(core.state) is None:
        runner(core).legendary()
    await advance(core)


async def turn_timeout(core: TableCore, key: str, reason: str | None = None) -> None:
    enc = core.state.encounter
    if core.turn_key != key or enc is None:
        return
    if core.paused:
        turn_clock.start(core, key, core.turn_seconds or turn_clock.GRACE_SECONDS)
        return
    active = enc.active_id()
    end_player_turn(core)
    if active is None:
        return
    if reason is None:
        owner = core.owner_of(active)
        reason = "grace_expired" if owner is not None and not owner.connected else "timeout"
    if reason != "kicked":
        core.diag("turn_timeout", creature_id=active)
    if reason == "grace_expired" and owner is not None:
        core.diag("grace_ended", player_id=owner.id, creature_id=active, reason="expired")
    core.diag("auto_turn", creature_id=active, reason=reason)
    name = core.state.creatures[active].name
    core.notice(None, NoticeKind.INFO, f"{name} hesitates and takes a careful, defensive turn.")
    run = runner(core)
    autoplay_safe(core, run, active)
    if encounter_outcome(core.state) is None:
        run.legendary()
    await advance(core)


async def finish_fight(core: TableCore, status: EncounterStatus) -> None:
    end_player_turn(core)
    state, regs = core.state, core.regs
    rng = loot_rng(state)
    events = core.apply_all(end_encounter_with_loot(state, status, regs.loot, regs.catalogue, rng))
    events += core.apply_all(combat_help_deed_events(state, status, regs.tiers))
    events += core.apply_all(resolution_reward_events(state, regs.tiers, regs.catalogue))
    events += core.apply_all(milestone_events(state, events, regs.tiers, regs.catalogue))
    text = await tell_segment(core, record=False)
    core.in_combat = False
    core.segment = []
    await remember(core, text or FIGHT_OVER, events)
    core.broadcast(CombatState(combat=None, outcome=status))
    core.diag("encounter_ended", status=str(status))
    await maybe_epilogue(core)
