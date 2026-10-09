"""Command line of scripts/gen_scribe_voice.py (M13.3, docs/next/GOAL_SCRIBE.md "Audio").

Modes (ASCII output only):
- default (dry run): the plan per line (characters, cached raw or API call needed) and totals.
  No network, writes nothing.
- `--yes`: requests every missing raw WAV from the provider (VOICE_PROVIDER=fish by default with
  FISH_API_KEY from the environment / .env, or `fake` for offline runs), then processes, encodes,
  indexes and reports the selected lines.
- `--reprocess`: the same from the raw cache only; it never builds a provider.
- `--reselect` (implies --reprocess): for lines with `takes` > 1, pick the best of the cached takes
  again (after a scorer change) and print the choice; no API call.
- `--check`: offline staleness check of lines.json against the config and the files.
- `--only ID` (repeatable) limits dry run, --yes and --reprocess to those lines.

Exit codes: 0 ok; 1 `--check` found problems, an unknown `--only` id or conflicting modes;
2 `--reprocess` without a cached raw WAV for some line; 3 provider unavailable or failed (no key,
API error; the key is never printed); 4 built, but some line failed its measurement checks
(F0 drift over 1%, loudness off by more than 0.5 LU, true peak over the ceiling).

Public API: `main`, `parse_args`, `provider_from_env`, `Out`.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Sequence
from pathlib import Path

from aidm.server.voicegen.config import VoiceConfig, VoiceLine, load_config
from aidm.server.voicegen.encode import Encoder, encode_mp3
from aidm.server.voicegen.index import check
from aidm.server.voicegen.provider import FakeTts, FishWavProvider, TtsProvider, VoiceProviderError
from aidm.server.voicegen.runner import (
    LineBuild,
    MissingRaw,
    VoicePaths,
    build_lines,
    raw_path,
    reselect,
)

type Out = Callable[[str], None]
type ProviderFactory = Callable[[], TtsProvider]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="gen_scribe_voice.py", description=__doc__)
    parser.add_argument("--yes", action="store_true", help="call the TTS API for missing raws")
    parser.add_argument("--reprocess", action="store_true", help="process from the raw cache")
    parser.add_argument("--check", action="store_true", help="offline staleness check")
    parser.add_argument("--reselect", action="store_true", help="re-pick cached takes, reprocess")
    parser.add_argument("--only", action="append", default=[], metavar="ID")
    return parser.parse_args(list(argv))


def provider_from_env(root: Path) -> TtsProvider:
    """VOICE_PROVIDER (fish by default, or fake); values are never echoed."""
    from dotenv import load_dotenv

    load_dotenv(root / ".env", override=False)
    name = (os.environ.get("VOICE_PROVIDER") or "fish").strip().lower()
    if name == "fake":
        return FakeTts()
    if name != "fish":
        raise VoiceProviderError("VOICE_PROVIDER must be fish (or fake for offline runs)")
    key = (os.environ.get("FISH_API_KEY") or "").strip()
    if not key:
        raise VoiceProviderError("FISH_API_KEY is not set")
    return FishWavProvider(api_key=key)


def _plan(paths: VoicePaths, lines: Sequence[VoiceLine], out: Out) -> int:
    calls = [line for line in lines if not raw_path(paths, line).is_file()]
    for line in lines:
        state = "API call" if line in calls else "cached"
        out(f"  {line.id:<22} {len(line.text):>4} chars  {line.profile:<5}  {state}")
    chars = sum(len(line.text) for line in calls)
    out(f"lines: {len(lines)}, cached raws: {len(lines) - len(calls)}, API calls: {len(calls)}")
    out(f"characters to synthesize: {chars}")
    out("dry run: nothing written. --yes generates, --reprocess reuses the cache only.")
    return 0


def _check(config: VoiceConfig, paths: VoicePaths, out: Out) -> int:
    found = check(config, paths.out_dir)
    for problem in found:
        out(problem)
    if found:
        out(f"scribe voice: {len(found)} problem(s); run python scripts/gen_scribe_voice.py --yes")
        return 1
    out(f"scribe voice: ok ({len(config.lines)} lines)")
    return 0


def _summary(builds: Sequence[LineBuild], paths: VoicePaths, out: Out) -> int:
    failed: list[str] = []
    for build in builds:
        m = build.metrics
        out(
            f"  {m.id:<22} {m.duration_s:6.2f} s  {m.lufs:6.2f} LUFS  {m.true_peak_db:6.2f} dBTP"
            f"  F0 {m.f0_raw_hz:.1f}->{m.f0_dry_hz:.1f} Hz  wet {m.wet_dry_db:+.1f} dB"
        )
        failed += build.problems
    out(f"built {len(builds)} line(s) -> {paths.out_dir.name}/; report in {paths.report_dir}")
    for problem in failed:
        out(f"CHECK FAILED: {problem}")
    return 4 if failed else 0


def _reselect(paths: VoicePaths, lines: Sequence[VoiceLine], out: Out) -> None:
    for line in lines:
        if line.takes > 1:
            picked = reselect(paths, line)
            note = "no cached takes" if picked is None else f"take {picked[0]} (score {picked[1]})"
            out(f"  {line.id:<22} reselected: {note}")


def _build(
    args: argparse.Namespace,
    config: VoiceConfig,
    lines: Sequence[VoiceLine],
    paths: VoicePaths,
    deps: tuple[ProviderFactory, Encoder, Out],
) -> int:
    factory, encoder, out = deps
    if args.reprocess:
        missing = [line for line in lines if not raw_path(paths, line).is_file()]
        for line in missing:
            out(f"{line.id}: no cached raw WAV; run with --yes")
        if missing:
            return 2
    try:
        provider = None if args.reprocess else factory()
        builds = build_lines(paths, config, lines, provider, encoder)
    except VoiceProviderError as exc:
        out(f"provider unavailable: {exc}")
        return 3
    except MissingRaw as exc:
        out(str(exc))
        return 2
    return _summary(builds, paths, out)


def main(
    argv: Sequence[str],
    *,
    root: Path,
    paths: VoicePaths | None = None,
    provider_factory: ProviderFactory | None = None,
    encoder: Encoder = encode_mp3,
    out: Out = print,
) -> int:
    args = parse_args(argv)
    where = paths if paths is not None else VoicePaths.for_root(root)
    config = load_config(where.config)
    if args.check:
        return _check(config, where, out)
    if args.yes and args.reprocess:
        out("choose one of --yes and --reprocess")
        return 1
    try:
        lines = config.select(args.only)
    except KeyError as exc:
        out(f"unknown line id(s): {exc.args[0]}")
        return 1
    if args.reselect and not args.yes:
        args.reprocess = True
        _reselect(where, lines, out)
    if not (args.yes or args.reprocess):
        return _plan(where, lines, out)
    factory = provider_factory or (lambda: provider_from_env(root))
    return _build(args, config, lines, where, (factory, encoder, out))
