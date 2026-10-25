"""Pick the typed lines to label for the interpreter corpus (M36.8a, docs/next/M36_LABELLING.md).

Usage: python scripts/select_label_rows.py [--candidates PATH] [--out PATH] [--sheets DIR]
  --candidates  artifacts/interpret/candidates.jsonl (make it with scripts/extract_typed_lines.py)
  --out         artifacts/interpret/selected.jsonl: the picked rows (finding-cited first)
  --sheets      also write the label sheets part1-3.jsonl and README.txt into DIR
                (default DIR when the flag has no value: artifacts/interpret/sheets)

Prints the finding-cited count per round, the source kinds and the scope mix. Deterministic: the
same candidates give the same rows (scripts/interpret/select.py, fixed seed).
"""

import argparse
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ART = ROOT / "artifacts" / "interpret"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", default=str(ART / "candidates.jsonl"))
    parser.add_argument("--out", default=str(ART / "selected.jsonl"))
    parser.add_argument("--sheets", nargs="?", const=str(ART / "sheets"), default=None)
    return parser


def main(argv: list[str]) -> int:
    from scripts.interpret.select import load_citations, mix, select
    from scripts.interpret.sheets import write_sheets

    args = _parser().parse_args(argv)
    source = Path(args.candidates)
    if not source.is_file():
        print(f"no candidates at {source}: run python scripts/extract_typed_lines.py first")
        return 2
    lines = source.read_text(encoding="utf-8").splitlines()
    candidates = [json.loads(line) for line in lines if line.strip()]
    citations = load_citations()
    rows = select(candidates, citations)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=True) + "\n" for r in rows), "utf-8")
    os.replace(tmp, out)
    counts = mix(rows)
    for name, counter in counts.items():
        print(f"{name}: " + ", ".join(f"{k} {v}" for k, v in sorted(counter.items())))
    for source_id, why in citations.missing:
        print(f"not in the fixtures: {source_id} ({why})")
    print(f"total: {len(rows)} -> {out}")
    if args.sheets is not None:
        for path, count in write_sheets(rows, Path(args.sheets)):
            print(f"sheet: {path} ({count} rows)")
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
