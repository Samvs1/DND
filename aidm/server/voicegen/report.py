"""The measurement report of the voice build (M13.3), for a session that cannot listen.

Per line `artifacts/voice/report/<line_id>.json` (all `LineMetrics` fields) and one `report.md`
table over every line of the config that has a JSON (so a `--only` run keeps the others). The
checks a line must pass: processed dry F0 within 1% of the raw F0 (no pitch shift), integrated
loudness within 0.5 LU of the target, true peak at or under the ceiling.

Public API: `LineMetrics`, `measure`, `problems`, `write_line_report`, `write_summary`.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from aidm.server.voicegen.analysis import high_band_db, median_f0, tail_s
from aidm.server.voicegen.chain import ProcessResult

type Audio = npt.NDArray[np.float64]

F0_TOLERANCE = 0.01
LUFS_TOLERANCE = 0.5


@dataclass(frozen=True)
class LineMetrics:
    id: str
    profile: str
    duration_s: float
    lufs: float
    target_lufs: float
    true_peak_db: float
    ceiling_db: float
    f0_raw_hz: float
    f0_dry_hz: float
    f0_delta_pct: float
    air_raw_db: float
    air_dry_db: float
    air_out_db: float
    wet_dry_db: float
    tail_s: float
    encoder: str


def measure(
    line_id: str, profile: str, raw: Audio, raw_rate: int, result: ProcessResult, chain: Any
) -> dict[str, Any]:
    f0_raw = median_f0(raw, raw_rate)
    f0_dry = median_f0(result.dry, result.rate)
    delta = 100.0 * (f0_dry - f0_raw) / f0_raw if f0_raw > 0 else 0.0
    return {
        "id": line_id,
        "profile": profile,
        "duration_s": round(result.duration_s, 3),
        "lufs": round(result.lufs, 2),
        "target_lufs": float(chain["loudness"]["target_lufs"]),
        "true_peak_db": round(result.true_peak_db, 2),
        "ceiling_db": float(chain["loudness"]["true_peak_db"]),
        "f0_raw_hz": round(f0_raw, 2),
        "f0_dry_hz": round(f0_dry, 2),
        "f0_delta_pct": round(delta, 3),
        "air_raw_db": round(high_band_db(raw, raw_rate), 2),
        "air_dry_db": round(high_band_db(result.dry, result.rate), 2),
        "air_out_db": round(high_band_db(result.out.mean(axis=1), result.rate), 2),
        "wet_dry_db": round(result.wet_dry_db, 2),
        "tail_s": round(tail_s(result.out, result.dry, result.rate), 2),
    }


def problems(m: LineMetrics) -> list[str]:
    found: list[str] = []
    if m.f0_raw_hz <= 0 or abs(m.f0_delta_pct) > 100.0 * F0_TOLERANCE:
        found.append(f"{m.id}: F0 {m.f0_raw_hz} Hz raw vs {m.f0_dry_hz} Hz processed")
    if abs(m.lufs - m.target_lufs) > LUFS_TOLERANCE:
        found.append(f"{m.id}: loudness {m.lufs} LUFS, target {m.target_lufs}")
    if m.true_peak_db > m.ceiling_db + 1e-6:
        found.append(f"{m.id}: true peak {m.true_peak_db} dBTP over {m.ceiling_db}")
    return found


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def write_line_report(report_dir: Path, metrics: LineMetrics) -> Path:
    path = report_dir / f"{metrics.id}.json"
    _atomic(path, json.dumps(asdict(metrics), indent=2) + "\n")
    return path


_HEAD = (
    "| line | profile | dur s | LUFS | TP dBTP | F0 raw | F0 dry | dF0 % "
    "| air raw dB | air dry dB | air out dB | wet/dry dB | tail s |"
)


def _row(m: dict[str, Any]) -> str:
    keys = (
        "id",
        "profile",
        "duration_s",
        "lufs",
        "true_peak_db",
        "f0_raw_hz",
        "f0_dry_hz",
        "f0_delta_pct",
        "air_raw_db",
        "air_dry_db",
        "air_out_db",
        "wet_dry_db",
        "tail_s",
    )
    return "| " + " | ".join(str(m.get(key, "")) for key in keys) + " |"


def write_summary(report_dir: Path, line_ids: tuple[str, ...]) -> Path:
    rows: list[str] = []
    for line_id in line_ids:
        path = report_dir / f"{line_id}.json"
        if path.is_file():
            rows.append(_row(json.loads(path.read_text(encoding="utf-8"))))
    body = [
        "# Scribe voice report",
        "",
        "Built by scripts/gen_scribe_voice.py. air = energy above 10 kHz relative to the total;",
        "F0 is the YIN median of voiced frames (raw TTS vs the processed dry chain); tail is the",
        "time from the end of the dry voice to -60 dB. Spectrograms: <line_id>.png.",
        "",
        _HEAD,
        "|" + "---|" * 13,
        *rows,
    ]
    path = report_dir / "report.md"
    _atomic(path, "\n".join(body) + "\n")
    return path
