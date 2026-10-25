"""Live menu-chooser probe (M36.12): skipped unless RUN_LIVE=1 (tests/conftest.py).

20 representative corpus lines (8 explore, 7 fight, 5 offer; finding-cited rows first, the labelled
`M29 ...`/`M31 ...`/`M34 ...` sources) go through the REAL chooser (`aidm.dm.chooser.choose`) with
DeepSeek through THE one LLM client. The floor: at least 16 of 20 are an exact or act match, and
none fails outright. Spend: 20 model calls (the exact label fast path asks none). The full 300-row
eval is `python scripts/eval_interpret.py --live`.
"""

import dataclasses
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest

from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_factory import make_llm_client
from aidm.dm.llm_settings import llm_settings_from_env
from aidm.dm.llm_types import LlmMode
from scripts.interpret.corpus import Row, load_corpus
from scripts.interpret.evaluate import live

CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "interpret" / "corpus.jsonl"
SHARE = {"explore": 8, "fight": 7, "offer": 5}
FLOOR = 16


def _cited(row: Row) -> bool:
    return row.source not in ("sample", "button")


def pick_rows(rows: list[Row]) -> list[Row]:
    chosen: list[Row] = []
    for scope, count in SHARE.items():
        mine = sorted((r for r in rows if r.scope == scope), key=lambda r: (not _cited(r), r.id))
        chosen += mine[:count]
    return chosen


@pytest.fixture
async def client(tmp_path: Path, live_env: dict[str, str]) -> AsyncIterator[LlmClient]:
    settings = dataclasses.replace(
        llm_settings_from_env(live_env), log_path=tmp_path / "llm.jsonl", fake=False
    )
    made = make_llm_client(settings)
    if made.mode is not LlmMode.LIVE:
        pytest.fail("RUN_LIVE=1 needs DEEPSEEK_API_KEY in the environment or .env")
    await made.discover_models()
    yield made
    await made.aclose()


def test_the_selection_is_twenty_rows_with_findings_first() -> None:
    rows = pick_rows(load_corpus(CORPUS))
    assert len(rows) == 20
    assert sum(_cited(r) for r in rows) >= 12


async def test_live_chooser_reads_twenty_corpus_lines(
    client: LlmClient, live_say: Callable[[str], None]
) -> None:
    rows = pick_rows(load_corpus(CORPUS))
    run = await live(rows, client, cap=40, limit=None)
    results = run["results"]
    assert run["scored"] == 20, run
    matched = [r for r in results if r["verdict"]["exact"] or r["verdict"]["act"]]
    failed = [r["id"] for r in results if r["verdict"]["failed"]]
    live_say(f"interpret live: {len(matched)} of {len(results)} exact or act, {run['calls']} calls")
    for r in results:
        if r not in matched:
            live_say(f"  miss {r['id']} [{r['scope']}] {r['text'][:60]!r} -> {r['pick']}")
    assert not failed, failed
    assert len(matched) >= FLOOR
