"""Final review sheets and ASSETS_REPORT.md from synthetic data (no network)."""

import json
from pathlib import Path

from PIL import Image

from aidm.server.assetgen.final_review import build_final_review
from aidm.server.assetgen.report import CAP_EUR, render_report
from tests.unit.assetgen.imgs import noise_png


def _entry(kind: str, file: str, source: str, status: str = "real") -> dict[str, object]:
    return {"kind": kind, "file": file, "status": status, "source": source}


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    static = tmp_path / "static"
    manifest = {
        "portrait.class.a": _entry("portrait", "img/a.png", "v1"),
        "portrait.class.b": _entry("portrait", "img/b.png", "v1"),
        "portrait.class.c": _entry("portrait", "img/c.png", "v1"),
        "portrait.npc.x": _entry("portrait", "img/x.png", "generated:m1"),
        "region_banner.tier1": _entry("region_banner", "img/t.png", "generated:m1"),
        "item_icon.torch": _entry("item_icon", "img/i.png", "generated:m1"),
        "monster_token.orc": _entry("monster_token", "img/o.png", "", "placeholder"),
        "spell_icon.cold": _entry("spell_icon", "img/s.png", "", "placeholder"),
    }
    for rel in ("a", "b", "c", "x", "t", "i"):
        (static / "img").mkdir(parents=True, exist_ok=True)
        (static / "img" / f"{rel}.png").write_bytes(noise_png(40, 30))
    path = static / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, static


def test_final_review_builds_overview_and_sheets(tmp_path: Path) -> None:
    manifest, static = _setup(tmp_path)
    written = build_final_review(manifest, static, tmp_path / "out")
    names = [p.name for p in written]
    assert names[0] == "FINAL_REVIEW.png"
    assert names[1:] == ["FINAL_REVIEW_1.png", "FINAL_REVIEW_2.png", "FINAL_REVIEW_3.png"]
    assert all(p.is_file() for p in written)
    assert Image.open(written[0]).width <= 2000


def test_assets_report_renders_tables(tmp_path: Path) -> None:
    manifest, _ = _setup(tmp_path)
    art = tmp_path / "art"
    (art / "candidates").mkdir(parents=True)
    for n in (1, 2):
        side = {"keys": ["portrait.npc.x"]}
        (art / "candidates" / f"portrait.npc.x__c{n}.json").write_text(json.dumps(side))
    scores = {"subject": 5, "style": 4, "composition": 4, "cleanliness": 5, "readability_64": 4}
    (art / "review_1.json").write_text(
        json.dumps(
            {
                "portrait.npc.x": {**scores, "verdict": "retry"},
                "portrait.npc.y": {**scores, "verdict": "reject"},
            }
        )
    )
    (art / "review_2.json").write_text(
        json.dumps({"portrait.npc.x": {**scores, "verdict": "accept"}})
    )
    (art / "review_1.index.json").write_text("{}")
    ledger = tmp_path / "spend.json"
    entry = {
        "call_id": "c1",
        "keys": ["portrait.npc.x"],
        "model": "gpt-image-test",
        "endpoint": "edit",
        "size": "1024x1024",
        "quality": "medium",
        "attempt": 1,
        "status": "settled",
        "estimate_eur": 0.1,
        "actual_eur": 0.04,
        "usage_reported": True,
    }
    ledger.write_text(json.dumps({"currency": "EUR", "entries": [entry]}))
    text = render_report(manifest, art, ledger)
    assert "- Committed: 0.0400 EUR over 1 calls" in text
    assert f"- Remaining: {CAP_EUR - 0.04:.4f} EUR" in text
    assert "gpt-image-test" in text
    assert "| portrait.npc.x | 2 | 5 | 4 | 4 | 5 | 4 | accept | yes |" in text
    assert "- portrait.npc.y: last verdict reject, 0 attempts" in text
    assert "- Generated: 3" in text
    assert "  - monster_token: 1" in text
    assert text == render_report(manifest, art, ledger)
    assert text.isascii()
