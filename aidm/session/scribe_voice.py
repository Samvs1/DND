"""When the Scribe speaks (M13.2, docs/next/GOAL_SCRIBE.md "What he does" 1-3).

Every appearance is ONE `scribe_line` broadcast (screens and phones) with a line of
data/voice/scribe.json picked by `ScribeMemory` (its own seeded random; no events, no replay
impact, a reconnect never replays old lines):
- `welcome_first`: a new campaign enters play, sent BEFORE the opening narration
  (`lobby.start_campaign`);
- `welcome_back`: a saved campaign was loaded (host load and defeat load, `host_switch.load`);
  a boot-time `--load` marks it due (`welcome_back_later`) and `on_join` sends it when the first
  screen or player connects. A save still in the lobby gets no welcome back;
- `campaign_won`: the campaign completes (`telling.maybe_epilogue`, before the epilogue is told).
  He says nothing after an ordinary won fight (owner feedback, M13.4);
- `revived`: a successful `scribe_revive` (`scribe_desk`): one brief spoken line for everyone.
  Refusals are never voiced (owner feedback, M13.4c): the phone shows his text-only line for the
  refusal code (`voiced: false` lines in data/voice/scribe.json);
- `skip` (client `scribe_skip`, host only, refusal `scribe_skip_host_only`) broadcasts
  `scribe_skip {line_id}` so screens stop his audio and overlay.

Public API: `say`, `welcome_first`, `welcome_back`, `welcome_back_later`, `on_join`,
`campaign_won`, `revived`, `skip`, `SKIP_REFUSAL`.
"""

from aidm.data.scribe_lines import ScribeGroup, audio_url, scribe_lines
from aidm.models.protocol_client import ScribeSkip
from aidm.models.protocol_server import ErrorCode, ScribeLineMsg, ScribeSkipMsg
from aidm.models.protocol_views import TablePhase
from aidm.session.table_core import Player, TableCore

SKIP_REFUSAL = "scribe_skip_host_only"


def say(core: TableCore, group: ScribeGroup, to_player_id: str | None = None) -> ScribeLineMsg:
    line = core.scribe.pick(scribe_lines().group(group), core.state.seed)
    msg = ScribeLineMsg(
        line_id=line.id,
        group=line.group.value,
        text=line.display,
        audio_url=audio_url(line.id),
        to_player_id=to_player_id,
    )
    core.broadcast(msg)
    return msg


def welcome_first(core: TableCore) -> None:
    core.scribe.welcome_due = False
    say(core, ScribeGroup.WELCOME_FIRST)


def welcome_back(core: TableCore) -> None:
    core.scribe.welcome_due = False
    if core.phase is not TablePhase.LOBBY:
        say(core, ScribeGroup.WELCOME_RETURN)


def welcome_back_later(core: TableCore) -> None:
    core.scribe.welcome_due = True


def on_join(core: TableCore) -> None:
    if core.scribe.welcome_due and (core.conn_player or core.spectators):
        welcome_back(core)


def campaign_won(core: TableCore) -> None:
    say(core, ScribeGroup.VICTORY_CAMPAIGN)


def revived(core: TableCore) -> None:
    say(core, ScribeGroup.REVIVE)


def skip(core: TableCore, player: Player, msg: ScribeSkip) -> None:
    if not player.is_host:
        core.error(player.id, ErrorCode.NOT_HOST, "Only the host can do that.", SKIP_REFUSAL)
        return
    core.broadcast(ScribeSkipMsg(line_id=msg.line_id or core.scribe.current))
    core.scribe.current = None
