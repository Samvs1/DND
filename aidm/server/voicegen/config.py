"""The voice build config: data/voice/scribe.json resolved per line (M13.3).

The file holds `voice` (Fish TTS settings), `chain` (the default sound chain), `profiles` (named
partial chains) and `lines` (id, group, text, profile, optional partial `chain`, optional partial
`voice`: a line's voice settings are the deep merge voice <- line.voice; `voiced: false` marks a
text-only line, which the build skips). The chain of a
line is the deep merge default <- profile <- line: nested dicts merge key by key, any other value
replaces. Hashes are stable (sorted-key JSON):
- `raw_key`: sha1(text | voice settings)[:12], the name of the cached raw WAV, so only a text or
  voice change needs a new API call;
- `text_sha`: sha1 of the text; `chain_sha`: sha1 of the resolved chain plus the voice settings.

Public API: `VoiceConfig`, `VoiceLine`, `load_config`, `parse_config`, `deep_merge`,
`DEFAULT_CONFIG`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "data" / "voice" / "scribe.json"

type Json = dict[str, Any]


def deep_merge(base: Mapping[str, Any], over: Mapping[str, Any]) -> Json:
    """A new dict: `over` merged into `base`; nested dicts merge, other values replace."""
    out: Json = {key: _copy(value) for key, value in base.items()}
    for key, value in over.items():
        current = out.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            out[key] = deep_merge(current, value)
        else:
            out[key] = _copy(value)
    return out


def _copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return deep_merge({}, value)
    return value


def _sha1(payload: str) -> str:
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class VoiceLine:
    id: str
    group: str
    text: str
    profile: str
    chain: Json
    voice: Json

    @property
    def raw_key(self) -> str:
        return _sha1(f"{self.text}|{_canon(self.voice)}")[:12]

    @property
    def raw_name(self) -> str:
        return f"{self.id}__{self.raw_key}.wav"

    @property
    def text_sha(self) -> str:
        return _sha1(self.text)

    @property
    def chain_sha(self) -> str:
        return _sha1(_canon({"chain": self.chain, "voice": self.voice}))


@dataclass(frozen=True)
class VoiceConfig:
    voice: Json
    lines: tuple[VoiceLine, ...]

    def ids(self) -> tuple[str, ...]:
        return tuple(line.id for line in self.lines)

    def select(self, only: list[str] | None) -> tuple[VoiceLine, ...]:
        """The lines named by `only` (config order), or every line; unknown ids raise KeyError."""
        if not only:
            return self.lines
        unknown = sorted(set(only) - set(self.ids()))
        if unknown:
            raise KeyError(", ".join(unknown))
        return tuple(line for line in self.lines if line.id in set(only))


def parse_config(raw: Mapping[str, Any]) -> VoiceConfig:
    voice: Json = dict(raw["voice"])
    chain: Json = dict(raw["chain"])
    profiles: Mapping[str, Any] = raw.get("profiles", {})
    lines: list[VoiceLine] = []
    for item in raw["lines"]:
        if item.get("voiced", True) is False:
            continue  # text-only line (shown, never spoken): nothing to build
        profile = str(item.get("profile", "long"))
        if profile not in profiles:
            raise ValueError(f"line {item['id']}: unknown profile {profile}")
        resolved = deep_merge(deep_merge(chain, profiles[profile]), item.get("chain", {}))
        lines.append(
            VoiceLine(
                id=str(item["id"]),
                group=str(item.get("group", "")),
                text=str(item["text"]),
                profile=profile,
                chain=resolved,
                voice=deep_merge(voice, item.get("voice", {})),
            )
        )
    if len({line.id for line in lines}) != len(lines):
        raise ValueError("duplicate line id")
    return VoiceConfig(voice=voice, lines=tuple(lines))


def load_config(path: Path | None = None) -> VoiceConfig:
    target = path if path is not None else DEFAULT_CONFIG
    return parse_config(json.loads(target.read_text(encoding="utf-8")))
