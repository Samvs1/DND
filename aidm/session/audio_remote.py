"""The audio remote (M11.2): any seated player sets the shared screen's audio.

`audio_settings {narration_volume, music_volume, narration_muted, music_muted, effects_volume,
effects_muted}` (the effects pair, M26.8's dice sounds, is optional; volumes 0-100,
checked by the protocol model: out of range is an `invalid` error at the socket) from a seated
player replaces `TableCore.audio` (last write wins), is broadcast as `audio_settings` to every
connection (the screen applies it) and is written to table.json at once (`write_meta`; it is
table metadata, NOT a game event). `PublicState.audio` carries it in every snapshot, so a screen
that connects later starts with it. More than `audio_limit` changes in its window are refused
(`refused`, refusal "rate_limited"). Allowed while paused and while DEFEATED; screens may not
send it (`spectators.refuse`).

Public API: `RATE_LIMITED`, `set_audio`.
"""

import logging

from aidm.models.protocol_client import AudioSettingsMsg
from aidm.models.protocol_server import AudioSettingsState, ErrorCode
from aidm.models.protocol_views import AudioSettings
from aidm.session.table_core import Player, TableCore

_LOG = logging.getLogger(__name__)
RATE_LIMITED = "Too many audio changes at once. Wait a moment."


def set_audio(core: TableCore, player: Player, msg: AudioSettingsMsg) -> None:
    if not core.audio_limit.allow(player.id, core.config.clock.time()):
        core.error(player.id, ErrorCode.REFUSED, RATE_LIMITED, "rate_limited")
        return
    settings = AudioSettings(
        narration_volume=msg.narration_volume,
        music_volume=msg.music_volume,
        narration_muted=msg.narration_muted,
        music_muted=msg.music_muted,
        effects_volume=msg.effects_volume,
        effects_muted=msg.effects_muted,
    )
    core.audio = settings
    core.broadcast(AudioSettingsState(settings=settings))
    _persist(core)


def _persist(core: TableCore) -> None:
    store = core.config.store
    if store is None:
        return
    try:
        store.write_meta(core.save_id or core.state.campaign_id, core.table_meta())
    except OSError:
        _LOG.exception("saving the audio settings failed; the next autosave retries")
