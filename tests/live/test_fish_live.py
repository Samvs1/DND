"""Live Fish Audio check (M8.1): one short sentence becomes an mp3. Skipped unless RUN_LIVE=1.

The key comes from the environment or the gitignored .env (read by name, never printed).
"""

import dataclasses
import os
from pathlib import Path

import pytest
from dotenv import dotenv_values

from aidm.models.narration import NarrationTone
from aidm.server.tts import FishTts, fish_settings_from_env

ROOT = Path(__file__).resolve().parents[2]


async def test_fish_synthesizes_one_sentence(tmp_path: Path) -> None:
    values = {k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}
    settings = fish_settings_from_env({**values, **os.environ})
    if not settings.ready:
        pytest.skip("FISH_API_KEY / FISH_VOICE_ID not set")
    tts = FishTts(dataclasses.replace(settings, cache_dir=tmp_path))
    sentence = "The lantern light trembles on the old stone wall."
    path = await tts.synthesize(sentence, NarrationTone.EXPLORATION)
    assert path is not None, "synthesis failed (the log line names the error class)"
    size = path.stat().st_size
    print(f"fish live mp3 bytes: {size}")
    assert size > 5 * 1024
