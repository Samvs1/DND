"""Live Fish Audio check (M8.1, SPEC 13 Live): one short sentence becomes an mp3 over 5 KB.

Runs only with RUN_LIVE=1 (tests/conftest.py); then a missing key or voice id is a failure, not
a skip. The key comes from the environment or the gitignored .env (read by name, never printed).
The mp3 size is recorded with `live_say`, so it shows in the "live results" summary under -q.
"""

import dataclasses
from collections.abc import Callable
from pathlib import Path

from aidm.models.narration import NarrationTone
from aidm.server.tts import FishTts, fish_settings_from_env

MIN_BYTES = 5 * 1024


async def test_fish_synthesizes_one_sentence(
    tmp_path: Path, live_env: dict[str, str], live_say: Callable[[str], None]
) -> None:
    settings = fish_settings_from_env(live_env)
    assert settings.ready, "RUN_LIVE=1 needs FISH_API_KEY and FISH_VOICE_ID (env or .env)"
    tts = FishTts(dataclasses.replace(settings, cache_dir=tmp_path))
    sentence = (
        "The lantern light trembles on the old stone wall, and somewhere below the inn "
        "a heavy door groans open in the dark."
    )
    path = await tts.synthesize(sentence, NarrationTone.EXPLORATION)
    assert path is not None, "synthesis failed (the log line names the error class)"
    size = path.stat().st_size
    live_say(f"LIVE fish: model={settings.model} mp3 bytes={size} (> {MIN_BYTES} required)")
    assert size > MIN_BYTES
