"""Shared helpers for the voice build tests: a small config in a temp repo, synthetic signals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from aidm.server.voicegen.config import DEFAULT_CONFIG, load_config
from aidm.server.voicegen.runner import VoicePaths

type Audio = npt.NDArray[np.float64]

SR = 48000


def real_chain() -> dict[str, Any]:
    """The resolved chain of the first configured line (the real default + its profile)."""
    return load_config().lines[0].chain


def small_config(**line_overrides: Any) -> dict[str, Any]:
    raw = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    lines = [
        {"id": "test.long", "group": "welcome_first", "profile": "long", "text": "A long test."},
        {"id": "test.short", "group": "revive", "profile": "short", "text": "Short one."},
    ]
    lines[0].update(line_overrides)
    raw["lines"] = lines
    return raw


def make_paths(tmp: Path, config: dict[str, Any] | None = None) -> VoicePaths:
    paths = VoicePaths.for_root(tmp)
    paths.config.parent.mkdir(parents=True, exist_ok=True)
    paths.config.write_text(json.dumps(config or small_config()), encoding="utf-8")
    return paths


def tone(freq: float, seconds: float, amp: float = 0.5, rate: int = SR) -> Audio:
    t = np.arange(int(rate * seconds)) / rate
    return amp * np.sin(2.0 * np.pi * freq * t)


def harmonic_voice(f0: float, seconds: float, rate: int = SR) -> Audio:
    t = np.arange(int(rate * seconds)) / rate
    out = np.zeros_like(t)
    for k in range(1, int(16000 // f0) + 1):
        out += np.sin(2.0 * np.pi * f0 * k * t + 0.3 * k) / k
    return 0.4 * out / np.max(np.abs(out))


def rms_db(x: Audio) -> float:
    return 20.0 * float(np.log10(np.sqrt(np.mean(x**2)) + 1e-20))
