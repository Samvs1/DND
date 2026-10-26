"""Evaluate the menu interpreter on a labelled corpus (M36.7, docs/next/M36_ACTION_MENU.md).

  python scripts/eval_interpret.py [--corpus PATH]        offline: the menu covers every expected
                                                          entry and target (no model, no network)
  ... --live [--limit N] [--cap N] [--strict]             the real chooser on each row (DeepSeek
                                                          key from .env, never printed); cap =
                                                          model calls

Live runs write artifacts/eval/<timestamp>.json and print an ASCII summary.
Scoring definitions: scripts/interpret/score.py.
"""

import argparse
import asyncio
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_CORPUS = ROOT / "tests" / "fixtures" / "interpret" / "corpus.jsonl"


def report(name: str, run: dict[str, Any]) -> dict[str, Any]:
    from scripts.interpret.score import latency, table, tallies

    results = run["results"]
    print(f"{name}: scored {run['scored']} of {run['asked']} rows, {run['calls']} model calls")
    for line in table(tallies(results)):
        print(line)
    p50, p90 = latency(results)
    prompt = sum(r.get("prompt_tokens", 0) for r in results)
    done = sum(r.get("completion_tokens", 0) for r in results)
    print(f"latency p50 {p50:.2f}s p90 {p90:.2f}s; tokens prompt {prompt} completion {done}")
    return {"p50": p50, "p90": p90, "prompt_tokens": prompt, "completion_tokens": done}


def write(payload: dict[str, Any]) -> Path:
    out = ROOT / "artifacts" / "eval" / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=True), encoding="utf-8")
    os.replace(tmp, out)
    return out


async def run_live(args: argparse.Namespace, rows: list[Any]) -> dict[str, Any] | None:
    import dataclasses

    from aidm.dm.llm_factory import make_llm_client
    from aidm.dm.llm_settings import llm_settings_from_env
    from aidm.dm.llm_types import LlmMode
    from aidm.server.settings import load_env
    from scripts.interpret.evaluate import live

    env = load_env(ROOT / ".env")
    if args.strict:
        env["AIDM_STRICT_TOOLS"] = "1"
    log = ROOT / "artifacts" / "eval" / "llm.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    settings = dataclasses.replace(llm_settings_from_env(env), log_path=log)
    client = make_llm_client(settings)
    if client.mode is not LlmMode.LIVE:
        print("live eval needs DEEPSEEK_API_KEY in .env (or the environment)")
        return None
    await client.discover_models()
    return await live(rows, client, args.cap, args.limit)


def main(argv: list[str]) -> int:
    from scripts.interpret.corpus import load_corpus
    from scripts.interpret.evaluate import DEFAULT_CAP, coverage

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--cap", type=int, default=DEFAULT_CAP)
    args = parser.parse_args(argv)
    try:
        rows = load_corpus(Path(args.corpus))
    except ValueError as exc:
        print(f"BAD ROW in {args.corpus}: {str(exc).splitlines()[0]}")
        return 1
    problems = coverage(rows)
    for problem in problems:
        print(f"GAP {problem}")
    bad = len({p.split(": ")[0] for p in problems})
    print(f"coverage: {len(rows) - bad} of {len(rows)} rows covered")
    payload: dict[str, Any] = {"corpus": args.corpus, "rows": len(rows), "gaps": problems}
    if args.live:
        live_run = asyncio.run(run_live(args, rows))
        if live_run is None:
            return 2
        payload["live"] = {**live_run, **report("live", live_run)}
        print(f"written: {write(payload)}")
    return 1 if problems else 0


if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
