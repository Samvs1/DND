"""Protocol unions and the generated files (SPEC 10, M6.1)."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from aidm.models import protocol
from aidm.models.protocol_client import HOST_MESSAGES, CombatCommandMsg, SubmitAction
from aidm.models.protocol_server import NarrationChunkMsg, Notice, NoticeKind
from aidm.models.protocol_views import PublicState

from .helpers import load_script

gen = load_script("gen_protocol")

# Every ServerMsg type. The M7.1 frontend handler-coverage test reads the same list from
# aidm/web/protocol.json; a new server message must be added here AND get a JS handler.
SERVER_TYPES = {
    "floor_state",  # M11.2
    "audio_settings",  # M11.2
    "scribe_line",  # M13.2
    "scribe_skip",  # M13.2
    "player_action",  # M22.1
    "what_now_answer",  # M23.8
    "welcome",
    "snapshot",
    "event",
    "lobby_roster",
    "ability_rolls",
    "creation_result",
    "queue_state",
    "resolving",
    "dice_roll",
    "narration_chunk",
    "narration_done",
    "vote_open",
    "vote_update",
    "vote_closed",
    "pending_confirmation",
    "encounter_offer",
    "combat_state",
    "hit_chances",
    "turn_prompt",
    "shop_stock",
    "level_up_available",
    "notice",
    "error",
    "host_stats",
    "chat",
    "suggestion",
    "pong",
    "story_history",
    "character_export",
    "sheet",
    "epilogue",
}

CLIENT_TYPES = {
    "typing",  # M11.2
    "audio_settings",  # M11.2
    "scribe_revive",  # M13.1
    "scribe_skip",  # M13.2
    "hello",
    "create_character",
    "roll_abilities",
    "submit_action",
    "combat_command",
    "suggestion",
    "confirm_hostile",
    "cancel_hostile",
    "vote",
    "answer_offer",
    "answer_quest_offer",
    "choose_finale",  # M23.9
    "level_up",
    "shop_buy",
    "shop_sell",
    "give",
    "equip",
    "unequip",
    "drop",
    "use_item",
    "help_up",
    "copy_scroll",  # M27.7
    "what_now",  # M23.8
    "presented",  # M26.3
    "request_sheet",
    "request_hit_chances",
    "chat",
    "host_start",
    "host_pause",
    "host_resume",
    "host_kick",
    "host_difficulty",
    "host_tts_toggle",
    "host_turn_timer",
    "host_save",
    "host_load",
    "host_new",
    "host_end",
    "host_force_vote",
    "ping",
    "export_character",
    "import_character",
    "defeat_retry",
    "defeat_load",
    "defeat_new",
}


def test_every_server_message_type_is_listed() -> None:
    types = {gen.message_type_name(m) for m in protocol.SERVER_MESSAGES}
    assert types == SERVER_TYPES
    assert len(protocol.SERVER_MESSAGES) == len(SERVER_TYPES)


def test_every_client_message_type_is_listed() -> None:
    types = {gen.message_type_name(m) for m in protocol.CLIENT_MESSAGES}
    assert types == CLIENT_TYPES
    host = {gen.message_type_name(m) for m in HOST_MESSAGES}
    assert host == {t for t in CLIENT_TYPES if t.startswith("host_")}


def test_protocol_json_lists_types_for_the_frontend() -> None:
    data = json.loads(gen.build_json())
    assert set(data["server"]["types"]) == SERVER_TYPES
    assert set(data["client"]["types"]) == CLIENT_TYPES


def test_generated_files_are_current() -> None:
    assert gen.stale_files(gen.repo_root()) == []


def test_stale_file_is_reported(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PROTOCOL.md").write_text("old\n", encoding="utf-8")
    assert set(gen.stale_files(tmp_path)) == {"aidm/web/protocol.json", "docs/PROTOCOL.md"}


def test_client_union_parses_by_type() -> None:
    msg = protocol.client_adapter.validate_python({"type": "submit_action", "text": "look"})
    assert isinstance(msg, SubmitAction)
    cmd = protocol.client_adapter.validate_json(
        '{"type": "combat_command", "command": {"type": "dodge", "actor_id": "pc-1"}}'
    )
    assert isinstance(cmd, CombatCommandMsg) and cmd.command.type == "dodge"


def test_client_union_rejects_unknown_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        protocol.client_adapter.validate_python({"type": "rm_rf"})
    with pytest.raises(ValidationError):
        protocol.client_adapter.validate_python({"type": "ping", "admin": True})
    with pytest.raises(ValidationError):
        protocol.client_adapter.validate_python({"type": "submit_action", "text": "x" * 5000})


def test_server_messages_round_trip() -> None:
    for msg in (
        NarrationChunkMsg(id="n1", index=0, text="Rain falls."),
        Notice(kind=NoticeKind.FALLBACK, text="The world holds its breath."),
    ):
        dumped = msg.model_dump_json()
        assert protocol.server_adapter.validate_json(dumped) == msg


def _property_names(schema: dict[str, Any]) -> set[str]:
    names = set(schema.get("properties", {}))
    for sub in schema.get("$defs", {}).values():
        names |= set(sub.get("properties", {}))
    return names


def test_public_state_has_no_private_npc_fields() -> None:
    names = _property_names(PublicState.model_json_schema())
    assert "attitude" in names and "revealed_secrets" in names
    for private in ("motive", "secrets", "base", "social", "deeds", "discover_dc", "hidden"):
        assert private not in names
