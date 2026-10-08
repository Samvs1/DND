"""Auto checkpoints for the defeat retry (M11.1, DECISIONS M11.1).

A checkpoint is a sequence marker in the event log: the state at the marker is the replay of
the first `seq` events (no state copy is stored). Two kinds are written automatically:
- "fight": in `combat_flow.begin_combat`, after the fight start was narrated and before any turn
  (a retry resumes the fight from its first round, with reseeded dice);
- "arrival": at the end of a job in which the party moved (`TableCore.mark_due`, set when a
  `PartyMoved` is recorded), once the arrival was described; skipped when that job started a
  fight (the fight marker is newer) or ended in a party wipe.
Markers live in `core.checkpoints` and `saves/<id>/checkpoints.json` (atomic write; a failing
disk is logged and never stops the game). The newest `MAX_CHECKPOINTS` are kept; a marker at the
same `seq` as the newest one replaces it.

Public API: `mark(core, kind, label)`, `mark_fight(core)`, `flush_arrival(core)`, `save(core)`,
`place_name(core)`.
"""

import logging
from datetime import UTC, datetime

from aidm.models.defeat import MAX_CHECKPOINTS, Checkpoint, CheckpointKind
from aidm.rules.party_wipe import party_wiped, standing_foes
from aidm.session.table_core import TableCore

_LOG = logging.getLogger(__name__)


def place_name(core: TableCore) -> str:
    node = core.state.world.current_node or ""
    return core.state.world.node_names.get(node, node.replace("-", " ")) or "the road"


def save(core: TableCore) -> None:
    store = core.config.store
    if store is None:
        return
    try:
        store.write_checkpoints(core.save_id or core.state.campaign_id, core.checkpoints)
    except OSError:
        _LOG.exception("writing checkpoints failed")


def mark(core: TableCore, kind: CheckpointKind, label: str) -> Checkpoint:
    seq = core.state.event_count
    point = Checkpoint(seq=seq, label=label, kind=kind, created=datetime.now(UTC).isoformat())
    kept = [c for c in core.checkpoints.checkpoints if c.seq < seq]
    core.checkpoints.checkpoints = [*kept, point][-MAX_CHECKPOINTS:]
    save(core)
    return point


def _joined(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names) or "foes"
    return f"{', '.join(names[:-1])} and {names[-1]}"


def mark_fight(core: TableCore) -> None:
    core.mark_due = False
    foes = _joined(standing_foes(core.state))
    mark(core, "fight", f"{place_name(core)}, before the fight with {foes}")


def flush_arrival(core: TableCore) -> None:
    """End of a job: write the arrival marker a `PartyMoved` asked for, if still sensible."""
    if not core.mark_due:
        return
    core.mark_due = False
    if core.combat_active() or party_wiped(core.state) or core.state.defeat is not None:
        return
    mark(core, "arrival", f"{place_name(core)}, on arrival")
