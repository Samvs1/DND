"""Voice config resolution (M13.3): deep merge default <- profile <- line, hashes, selection."""

import subprocess
import sys

import pytest

from aidm.server.voicegen.config import deep_merge, load_config, parse_config
from tests.unit.voicegen.helpers import small_config


def test_deep_merge_nested_and_replace() -> None:
    base = {"reverb": {"wet": 0.3, "rt60_s": 2.4}, "x": 1}
    merged = deep_merge(base, {"reverb": {"wet": 0.2}, "x": 2})
    assert merged == {"reverb": {"wet": 0.2, "rt60_s": 2.4}, "x": 2}
    assert base["reverb"]["wet"] == 0.3


def test_merge_order_default_profile_line() -> None:
    raw = small_config(chain={"reverb": {"rt60_s": 3.0}}, profile="short")
    line = parse_config(raw).lines[0]
    assert line.chain["reverb"]["wet"] == 0.22  # from the short profile
    assert line.chain["reverb"]["rt60_s"] == 3.0  # line override beats the profile's 1.8
    assert line.chain["reverb"]["damping_hz"] == raw["chain"]["reverb"]["damping_hz"]


def test_real_config_profiles() -> None:
    config = load_config()
    by_id = {line.id: line for line in config.lines}
    assert by_id["welcome.first"].chain["reverb"]["wet"] == 0.30
    assert by_id["revive.1"].chain["reverb"]["wet"] == 0.22
    assert by_id["revive.1"].chain["reverb"]["rt60_s"] == 1.8


def test_hashes_track_text_and_chain() -> None:
    base = parse_config(small_config()).lines[0]
    edited = parse_config(small_config(text="Other words.")).lines[0]
    tweaked = parse_config(small_config(chain={"reverb": {"wet": 0.1}})).lines[0]
    assert base.text_sha != edited.text_sha and base.raw_key != edited.raw_key
    assert base.chain_sha != tweaked.chain_sha
    assert base.raw_key == tweaked.raw_key  # a sound tweak reuses the cached raw WAV
    assert base.raw_name.startswith("test.long__") and base.raw_name.endswith(".wav")


def test_select_unknown_and_unknown_profile() -> None:
    config = parse_config(small_config())
    assert [line.id for line in config.select(["test.short"])] == ["test.short"]
    with pytest.raises(KeyError):
        config.select(["nope"])
    with pytest.raises(ValueError):
        parse_config(small_config(profile="missing"))


def test_game_server_never_imports_the_voice_build() -> None:
    code = "import sys, aidm.server.app; print('aidm.server.voicegen' in sys.modules)"
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert done.stdout.strip() == "False"
