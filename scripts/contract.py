"""The game's contract checked on saves (M43.1, docs/next/M43_CONTRACT.md). No model, no network.

  python scripts/contract.py [SAVE_DIR ...]     default: every folder in tests/fixtures/saves

Replays each save once through the one reducer and prints one line per finding:
  <save> <rule> <event index> <short reason>
then a per-rule count table. Rules: A1 replay = snapshot, A2 ledger, A3 stale story shown as the
present, A4 hp and resources in 0..max, B1 every typed line ends in an outcome (needs the
`line_read` record), B6 a leveled spell spends a slot and uses its caster's DC, C1-C4 generated
quests, D1 every refusal reaches the next narration's rebuilt prompt. A save without
initial.json (events only) cannot be replayed: its checks are skipped and said so. The exit
code is 0 (a report). In the gate, tests/sim/test_contract_fixtures.py holds every fixture to
its recorded history, `tests/fixtures/contract_baseline.json` (M43.5).
"""

import io
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = ROOT / "tests" / "fixtures" / "saves"
RULES = ("A1", "A2", "A3", "A4", "B1", "B6", "C1", "C2", "C3", "C4", "D1")


def check_save(folder: Path) -> tuple[Sequence[tuple[str, int, str]], list[str]]:
    """The findings of one save folder, and the rules skipped on it (with the reason)."""
    from pydantic import ValidationError

    from scripts.contractlib.line_rules import LineOutcomes
    from scripts.contractlib.quest_rules import QuestRules
    from scripts.contractlib.save import load_save, walk
    from scripts.contractlib.spell_rules import SpellPaths
    from scripts.contractlib.state_rules import Bounds, a1_replay, a2_ledger, a3_stale
    from scripts.contractlib.story_rules import TurnOutcomes

    try:
        save = load_save(folder)
    except ValidationError as err:
        return [], [f"all (the log does not parse: {err.error_count()} errors, a hand-built save)"]
    if save.initial is None:
        return [], [f"all (no initial.json, {len(save.events)} events cannot be replayed)"]
    lines = LineOutcomes()
    final, found = walk(save, [Bounds(), SpellPaths(), QuestRules(), lines, TurnOutcomes()])
    found = a1_replay(save, final) + a2_ledger(save) + a3_stale(save) + found
    skipped = [] if lines.records else ["B1 (no line_read record: a save from before M43.1)"]
    return found, skipped


def table_lines(counts: dict[str, dict[str, int]]) -> list[str]:
    out = ["save | " + " ".join(RULES), "-" * 60]
    for name, row in counts.items():
        out.append(f"{name} | " + " ".join(str(row.get(r, 0)) for r in RULES))
    out.append("TOTAL | " + " ".join(str(sum(r.get(x, 0) for r in counts.values())) for x in RULES))
    return out


def findings(folders: list[Path]) -> tuple[dict[str, dict[str, int]], list[str]]:
    """Per save the count per rule, and the report lines (each finding, each skip)."""
    counts: dict[str, dict[str, int]] = {}
    out: list[str] = []
    for folder in folders:
        found, skipped = check_save(folder)
        row = counts.setdefault(folder.name, {})
        for rule, idx, reason in found:
            row[rule] = row.get(rule, 0) + 1
            out.append(f"{folder.name} {rule} {idx} {reason}".encode("ascii", "replace").decode())
        out += [f"{folder.name} SKIP {why}" for why in skipped]
    return counts, out


def main(argv: list[str]) -> int:
    folders = [Path(a) for a in argv] or sorted(p for p in FIXTURES.iterdir() if p.is_dir())
    counts, out = findings(folders)
    for line in out + table_lines(counts):
        print(line)
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
