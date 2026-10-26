"""Offline audit of stale story records shown as the present (M40.3). No model, no network.

  python scripts/narration_audit.py [FIXTURE ...]     default: every folder in tests/fixtures/saves

Replays each fixture through the one reducer. At every `narration_recorded` it rebuilds the
narrator prompt from the state just before it (as `narrate` / `narrate_round_segment` do: the
engine events since the previous narration plus the RESOLVED notes) and counts, per store
(facts, summaries, narration lines, descriptions), the records shown and the STALE ones shown.
At the end it also counts stale records in the journal view and the epilogue input.
The staleness heuristic is documented in scripts/audit/stale.py.
"""

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = ROOT / "tests" / "fixtures" / "saves"


def main(argv: list[str]) -> int:
    from scripts.audit.replay import audit_run, table_lines

    names = argv or sorted(p.name for p in FIXTURES.iterdir() if (p / "initial.json").exists())
    runs = [audit_run(FIXTURES / n) for n in names]
    for line in table_lines(runs):
        print(line)
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
