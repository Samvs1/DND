"""Spectrogram PNG of one line: raw TTS on top, processed output below (M13.3).

numpy STFT (Hann, 2048 points at 48 kHz, scaled for other rates), a log-frequency axis from 40 Hz
to 20 kHz, one shared dB scale for both panels (90 dB range under the loudest bin of either), the
same seconds-per-pixel for both so the reverb tail is visible as extra width, guide lines at
100 Hz, 1 kHz and 10 kHz. Rendered with Pillow only (no matplotlib).

Public API: `spectrogram_png`, `render_panels`.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw

type Audio = npt.NDArray[np.float64]

WIDTH = 1200
ROWS = 256
LABEL_H = 16
F_LO = 40.0
F_HI = 20000.0
RANGE_DB = 90.0
GUIDES_HZ = (100.0, 1000.0, 10000.0)
_STOPS = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
_COLOURS = np.array(
    [[0, 0, 0], [40, 10, 90], [150, 30, 120], [240, 120, 40], [255, 245, 170]], dtype=np.float64
)


def _stft_db(mono: Audio, rate: int, seconds: float) -> Audio:
    """(ROWS, columns) magnitude in dB on the log-frequency grid; columns cover `seconds`."""
    n_fft = 2048 if rate <= 48000 else 4096
    columns = max(1, round(WIDTH * min(1.0, mono.size / rate / seconds)))
    hop = max(1, (mono.size - n_fft) // max(1, columns - 1)) if mono.size > n_fft else 1
    padded = np.pad(mono, (0, max(0, n_fft + hop * (columns - 1) - mono.size)))
    idx = np.arange(n_fft)[None, :] + hop * np.arange(columns)[:, None]
    window = np.hanning(n_fft)
    mag = np.abs(np.fft.rfft(padded[idx] * window, axis=1))
    bins = np.arange(mag.shape[1]) * rate / n_fft
    grid = F_LO * (F_HI / F_LO) ** (np.arange(ROWS) / (ROWS - 1))
    rows = np.stack([np.interp(grid, bins, col) for col in mag], axis=1)
    return 20.0 * np.log10(rows + 1e-9)


def _colour(db: Audio, top: float) -> npt.NDArray[np.uint8]:
    level = np.clip((db - (top - RANGE_DB)) / RANGE_DB, 0.0, 1.0)
    rgb = np.stack([np.interp(level, _STOPS, _COLOURS[:, c]) for c in range(3)], axis=-1)
    return rgb.astype(np.uint8)


def _panel(db: Audio, top: float, label: str) -> Image.Image:
    body = np.zeros((ROWS, WIDTH, 3), dtype=np.uint8)
    body[:, : db.shape[1]] = _colour(db, top)[::-1]
    image = Image.new("RGB", (WIDTH, ROWS + LABEL_H), (24, 24, 28))
    image.paste(Image.fromarray(body), (0, LABEL_H))
    draw = ImageDraw.Draw(image)
    draw.text((4, 2), label, fill=(230, 230, 230))
    for hz in GUIDES_HZ:
        y = LABEL_H + ROWS - 1 - round((ROWS - 1) * math.log(hz / F_LO) / math.log(F_HI / F_LO))
        draw.line([(0, y), (WIDTH - 1, y)], fill=(90, 90, 100))
        draw.text(
            (4, y - 12), f"{int(hz) // 1000}k" if hz >= 1000 else f"{int(hz)}", fill=(200,) * 3
        )
    return image


def render_panels(raw: Audio, raw_rate: int, out: Audio, out_rate: int) -> Image.Image:
    out_mono = out.reshape(out.shape[0], -1).mean(axis=1)
    seconds = max(raw.size / raw_rate, out_mono.size / out_rate, 1e-3)
    raw_db = _stft_db(raw, raw_rate, seconds)
    out_db = _stft_db(out_mono, out_rate, seconds)
    top = max(float(raw_db.max()), float(out_db.max()))
    upper = _panel(raw_db, top, f"raw TTS ({raw_rate} Hz)")
    lower = _panel(out_db, top, f"processed ({out_rate} Hz, {seconds:.2f} s)")
    sheet = Image.new("RGB", (WIDTH, upper.height * 2 + 4), (0, 0, 0))
    sheet.paste(upper, (0, 0))
    sheet.paste(lower, (0, upper.height + 4))
    return sheet


def spectrogram_png(raw: Audio, raw_rate: int, out: Audio, out_rate: int, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    render_panels(raw, raw_rate, out, out_rate).save(tmp, format="PNG")
    os.replace(tmp, path)
