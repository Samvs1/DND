"""One `Table` per campaign (SPEC 5): creates a new table or loads a save (M6.4).

The server runs one active table. `start()` opens a new lobby table, or the save named by
`campaign_id`; the host's `host_new` / `host_load` switch the table's contents in place
(`session.host`), so open sockets stay attached. `stop()` saves, stops the table and closes the
LLM client. A save opened at start marks the Scribe's welcome back due; it is spoken when the
first screen or player connects (M13.2, `session.scribe_voice`).

Public API: `TableRegistry` (`table`, `start`, `stop`, `list_saves`).
"""

from pathlib import Path

from aidm.dm.llm_client import LlmClient
from aidm.models.state import GameState
from aidm.server.settings import ServerSettings
from aidm.server.tts import FishTts, tts_hook
from aidm.session.persistence import CampaignStore, SaveInfo, new_game_state
from aidm.session.restore import restore
from aidm.session.scribe_voice import welcome_back_later
from aidm.session.session_log import FileLog
from aidm.session.table import Table
from aidm.session.table_core import TableConfig


class TableRegistry:
    def __init__(
        self,
        settings: ServerSettings,
        llm: LlmClient,
        *,
        state: GameState | None = None,
        campaign_id: str | None = None,
        config: TableConfig | None = None,
    ) -> None:
        self.llm = llm
        self.store = CampaignStore(settings.saves_dir)
        self._tts = FishTts(settings.fish)
        self._config = config or TableConfig(
            store=self.store,
            tts_enabled=settings.tts_enabled,
            tts=tts_hook(self._tts),
            session_log=FileLog(Path(settings.saves_dir).parent / "logs" / "session.jsonl"),
            ai_turn_pause_s=settings.ai_turn_pause_s,
            show_wait_cap_s=settings.show_wait_cap_s,
            grace_seconds=settings.grace_seconds,
            turn_seconds=settings.turn_seconds,
        )
        self._state = state
        self._campaign_id = campaign_id
        self.table = Table(state or new_game_state(), llm, self._config)

    async def start(self) -> None:
        if self._campaign_id is not None and self._state is None:
            restore(self.table, self.store.load(self._campaign_id))
            welcome_back_later(self.table)
        await self.table.start()

    async def stop(self) -> None:
        await self.table.stop()
        self._tts.close()
        await self.llm.aclose()

    def list_saves(self) -> list[SaveInfo]:
        return self.store.list_campaigns()
