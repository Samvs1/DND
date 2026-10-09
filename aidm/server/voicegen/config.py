"""The voice build config: data/voice/scribe.json resolved per line (M13.3).

The file holds `voice` (Fish TTS settings), `chain` (the default sound chain), `profiles` (named
partial chains) and `lines` (id, group, text, profile, optional partial `chain`, optional partial
`voice`: a line's voice settings are the deep merge voice <- line.voice; `voiced: false` marks a
text-only line, which the build skips; `takes: N` generates N takes and keeps the best one).
The chain of a line is the deep merge default <- profile <- line: nested dicts merge key by key,
any other value replaces. Hashes are stable (sorted-key JSON):
- `raw_key`: sha1(text | voice settings)[:12], the name of the cached raw WAV, so only a text or
  voice change needs a new API call;
- `text_sha`: sha1 of the text; `chain_sha`: sha1 of the resolved chain plus the voice settings.

A line may instead list `parts` (M13.4e): separately generated pieces spliced into one raw before
the chain, e.g. an opening and a weighty last word ("Rise."). Each part has `text`, an optional
partial `voice` (merged over the line's), `takes` and `select` ("final_word" or "phrase" with
`ref_f0_hz`), and for every part after the first `gap_ms` (silence before it) and `gain_db` (its
level against the first part). A part's raw is content addressed (`part__<key>.wav`), so lines
sharing a part share one recording. The line's `text` is the parts' texts joined; its `chain_sha`
also covers the parts' settings (lines without parts hash exactly as before).

Public API: `VoiceConfig`, `VoiceLine`, `VoicePart`, `load_config`, `parse_config`, `deep_merge`,
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
class VoicePart:
    text: str
    voice: Json
    takes: int = 1
    select: str = "final_word"
    ref_f0_hz: float = 0.0
    gap_ms: float = 0.0
    gain_db: float = 0.0

    @property
    def key(self) -> str:
        return _sha1(f"{self.text}|{_canon(self.voice)}")[:12]

    @property
    def raw_name(self) -> str:
        return f"part__{self.key}.wav"

    def settings(self) -> Json:
        return {
            "text": self.text,
            "voice": self.voice,
            "select": self.select,
            "ref_f0_hz": self.ref_f0_hz,
            "gap_ms": self.gap_ms,
            "gain_db": self.gain_db,
        }


@dataclass(frozen=True)
class VoiceLine:
    id: str
    group: str
    text: str
    profile: str
    chain: Json
    voice: Json
    takes: int = 1  # > 1: generate that many takes and keep the best final word (takes.py)
    parts: tuple[VoicePart, ...] = ()  # spliced pieces instead of one take (empty: one take)

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
        payload: Json = {"chain": self.chain, "voice": self.voice}
        if self.parts:
            payload["parts"] = [part.settings() for part in self.parts]
        return _sha1(_canon(payload))


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
        line_voice = deep_merge(voice, item.get("voice", {}))
        parts = tuple(_part(raw_part, line_voice) for raw_part in item.get("parts", []))
        text = " ".join(part.text for part in parts) if parts else str(item["text"])
        lines.append(
            VoiceLine(
                id=str(item["id"]),
                group=str(item.get("group", "")),
                text=text,
                profile=profile,
                chain=resolved,
                voice=line_voice,
                takes=max(1, int(item.get("takes", 1))),
                parts=parts,
            )
        )
    if len({line.id for line in lines}) != len(lines):
        raise ValueError("duplicate line id")
    return VoiceConfig(voice=voice, lines=tuple(lines))


def _part(raw: Mapping[str, Any], line_voice: Json) -> VoicePart:
    select = str(raw.get("select", "final_word"))
    if select not in ("final_word", "phrase"):
        raise ValueError(f"unknown part select {select!r}")
    return VoicePart(
        text=str(raw["text"]),
        voice=deep_merge(line_voice, raw.get("voice", {})),
        takes=max(1, int(raw.get("takes", 1))),
        select=select,
        ref_f0_hz=float(raw.get("ref_f0_hz", 0.0)),
        gap_ms=float(raw.get("gap_ms", 0.0)),
        gain_db=float(raw.get("gain_db", 0.0)),
    )


def load_config(path: Path | None = None) -> VoiceConfig:
    target = path if path is not None else DEFAULT_CONFIG
    return parse_config(json.loads(target.read_text(encoding="utf-8")))
