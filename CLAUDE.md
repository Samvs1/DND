# CLAUDE.md: AI Dungeon Master v2 (`aidm`)

`SPEC.md` is the single source of truth. This file is the short operating manual.
Progress and the exact next action are in `PROGRESS.md`. Work order and agent routing are in `docs/USAGE_PLAN.md`.

## Session start (every session, every resume, every post-compaction turn)
1. Read `PROGRESS.md` (the `NEXT:` line first), this file, and run `git log --oneline -15`.
2. Run `git status`. If the tree is dirty, follow the "Dirty tree on resume" steps below.
3. Read ONLY the SPEC.md section for the current milestone (the section numbers are in PROGRESS.md).
4. Continue from `NEXT:`. Do not re-plan. Do not re-read the whole codebase.

### Dirty tree on resume
- Run the current checkpoint's gate. If it is green, commit `WIP M<n>: <what>` and continue.
- If it is red and the cause is not obvious within 10 minutes, run `git stash push -m "resume-<checkpoint>"`,
  record the stash name in PROGRESS.md and restart the checkpoint from its last commit. Never `reset --hard`.

## Checkpoint loop (the unit of work, about 20 to 40 minutes)
1. Take the checkpoint named in `NEXT:`. Look up whether it is mechanical (M) or hard (H) in `docs/USAGE_PLAN.md`.
2. Delegate it (see Delegation) or do it inline if it is under about 10 minutes.
3. Gate green -> tick it in PROGRESS.md -> set `NEXT:` -> commit `WIP M<n>.<k>: <what>`.
   The LAST checkpoint of a milestone runs the FULL gate and commits `M<n>: <title>` (SPEC section 14).
4. Paste the gate output tail (last ~15 lines) into the conversation (SPEC 0.4). Subagent output is not
   visible to the user or the evaluator, so the orchestrator re-runs or relays the tail.
5. Never more than ~30 minutes uncommitted. Never commit a red tree.

## Delegation (agents in `.claude/agents/`)
| Agent | Model | Use for |
|---|---|---|
| `hard-engineer` | opus | Checkpoints marked **H**: rules core, combat, AI layer, guard, table actor, live-AI work, fixing defects found by sims or QA |
| `mechanical-engineer` | sonnet, low effort | Checkpoints marked **M**: scaffolding, data conversion and content batches, loaders, gate scripts, protocol codegen, persistence, server wiring, frontend views, docs |

- Recommended main session: `/model sonnet` as a thin orchestrator. It reads NEXT, delegates one checkpoint, relays the gate tail and loops.
- Give each agent a narrow prompt: the checkpoint id, its deliverables and gate (copied from PROGRESS.md),
  the SPEC section numbers, and the files in flight. Do not paste whole files.
- Escalation: if a mechanical checkpoint fails its gate twice, hand it to `hard-engineer`.
  If a hard checkpoint fails twice, apply the stuck rule (SPEC 0.6): take the simpler deterministic option and log it in `docs/DECISIONS.md`.
- One agent at a time writes to the tree. Parallel agents are allowed only for read-only work.

## Commands (Windows PowerShell; never chain with `&&`, use `;` or separate calls)
```powershell
python -m venv .venv                         # once (M0.2); `python` is 3.13 on this machine
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m playwright install chromium        # M9 only
.\scripts\gate.ps1                           # FULL gate (from M0.3); prints each tool's tail plus PASS/FAIL
pytest -q tests/unit/rules                   # a typical checkpoint-scoped gate
pytest -q --cov=aidm/rules --cov-report=term-missing tests/unit tests/property
uvicorn aidm.server.app:app --port 8000      # or: python -m aidm.server [--lan]   (from M6)
$env:AIDM_FAKE_LLM="1"                       # deterministic server mode for UI tests
$env:RUN_LIVE="1"; pytest -q tests/live       # opt-in live DeepSeek/Fish tests
python scripts/simulate_party.py --seeds 20  # M9
python scripts/code_map.py                   # code map (about 1 s): artifacts/codemap/
```
The full gate is `pytest -q`, `ruff check .`, `ruff format --check .`, `pyright`, `lint-imports`,
`python scripts/check_structure.py`, `python scripts/check_secrets.py` and `python scripts/gen_protocol.py --check`.

## Code map (`scripts/code_map.py`, about 1 s, standard library only)
- Writes `artifacts/codemap/` (gitignored). Run it at session start and before planning a refactor or a new module.
- `INDEX.md`: one line per file in aidm/ and scripts/: path, lines, imported by, imports, first docstring line.
  Grep it to find where a concept lives BEFORE opening files.
- `CODEMAP.md`: lines per folder, hubs (imported by many AND importing many), most imported files, files near the
  400-line limit, and families (one name prefix, many files: a concept split across files, e.g. `aidm/dm/guard*`).
  Read it before adding a module: a change to a hub reaches far; do not grow a big family without a reason.
- Every module starts with a one-line docstring (Python) or header comment (JS): it is the file's index entry.

## Layering (SPEC 5; enforced by import-linter, never weakened)
`models, data` <- `rules` <- `dm` <- `session` <- `server`. Nothing imports upward.
- `aidm/models`: pydantic v2 only (state, commands, events, tool schemas, protocol). No logic beyond validators.
- `aidm/data`: loaders and typed registries for `data/srd` and `data/bg3`. No game logic.
- `aidm/rules`: PURE. No I/O, no clock, no network, no AI, no `openai`, `httpx` or `fastapi`. RNG is injected (`random.Random(seed)`).
  Functions take state and inputs and RETURN events. They never mutate.
- `aidm/dm`: llm_client, tools, adjudicator, narrator, context (ONE builder), guard (ONE module), memory, campaign_gen, fallbacks.
- `aidm/session`: the table actor, queue, turn manager, `reducer.apply(state, event)`, which is the ONLY mutator, and persistence.
- `aidm/server`: FastAPI, websocket gateway, lobby, tts service, static hosting. `aidm/web`: vanilla ES modules, no build step.

## Hard rules
- **AI proposes, engine disposes.** The LLM only calls typed tools. The engine owns every number (DC tiers, severity tiers, XP tiers).
- **Closed world.** Things exist only once a creation tool has registered them. The narrator sees the manifest. Every prose output goes through `dm/guard.py`.
- **Events only.** Replaying `events.jsonl` must equal the snapshot (tested).
- **Fail soft, never silent.** Show an in-fiction fallback. Never show a raw error to a player, swallow an exception or drop a turn.
- **Data over code.** Spells, conditions, features, monsters, items and surfaces are JSON plus one generic interpreter. Never add a per-spell branch.
- **One source of truth per concept**: slot model, context builder, guard, LLM client, protocol, TTS adapter.
- Never weaken a gate: no skipped or deleted tests, no `# type: ignore`, no `noqa`, no raised limits. Fix the code.
- Structure limits: <=400 lines per `.py` file, <=60 lines per function, no star imports, no re-export shim modules.
- BG3 mechanics are allowed. BG3 text, names, lore and art are not. Rules content comes from SRD 5.1 (CC-BY-4.0).
- Unsure of a BG3 rule: use SRD 5.1 and add one line to `docs/RULES_DECISIONS.md`. Other choices go in `docs/DECISIONS.md`.

## Conventions
- Python 3.13, full type hints. Pyright strict on `aidm/rules` and `aidm/models`, basic elsewhere. Ruff for lint and format.
- Use `pathlib` everywhere, with no hardcoded `/` or `\`. Every script starts with `sys.stdout.reconfigure(encoding="utf-8")`.
- Test names, check labels and console output are ASCII only, because the cp1252 console crashed v1.
- Tests live in `tests/{unit,property,ai,session,sim,ui,live}` and are pytest only. `tests/live` is skipped unless `RUN_LIVE=1`.
  `tests/ai` uses `FakeLLM` and never the network.
- Scripts go in `scripts/` and saves in `saves/<campaign_id>/` (gitignored). Writes are atomic: temp file, then `os.replace`.
- Golden tests: name them `test_golden_<thing>` and hardcode the expected numbers with a comment citing the SRD source.
- Every v1 regression test from SPEC 13 gets its own named test (`test_v1_<slug>`).
- Commit messages: `WIP M<n>.<k>: <what>` per checkpoint, `M<n>: <title>` when a milestone closes.

## Secrets
- `.env` exists in the root and is gitignored. **Never print, log, echo, commit or paste its values.**
  To inspect it, list names only: `Get-Content .env | ForEach-Object { ($_ -split '=')[0] }`.
- Names present: `DEEPSEEK_API_KEY`, `FISH_API_KEY`, `FISH_VOICE_ID`, `FISH_MODEL`, `TTS_ENABLED`, `DEV`,
  `IMAGE_PROVIDER`, `IMAGE_API_KEY`, `OPENROUTER_API_KEY` (added 2026-10-24, $10 credit, not used by aidm yet;
  using it is new spend: ask the owner).
- `scripts/check_secrets.py` must pass before every commit from M0.3 onward.

## v1 reference (read-only, never modify)
`C:\Users\vanst\Desktop\DnD`. Its lessons are digested once into `docs/V1_LESSONS.md` (M0.4). Read that digest, not v1.
Assets are COPIED from v1 into `aidm/web/static/` in M0.4. Never edit the originals.

## Asset policy
- Missing art is fine: it shows as a placeholder through the manifest and `asset_url`/`assetUrl` (docs/ADDENDUM_ASSETS.md).
- Image generation goes ONLY through the M10 pipeline (`scripts/gen_assets.py`, docs/ADDENDUM_ASSET_GEN.md): budget-capped,
  reviewed, with P1 placeholders only. Never make ad hoc image API calls. Never overwrite real or v1 assets.
- M10.5-M10.7 (marked ORCH) are done by the main session itself, because it must open and judge every contact sheet.
- Voice lines (the Scribe) are made ONLY by `scripts/gen_scribe_voice.py` from the one config `data/voice/scribe.json`
  (docs/next/GOAL_SCRIBE.md): Fish key from .env at build time, never in client code. No pitch shifting, no
  distortion/bitcrush/chorus, high resolution processing, one final lossy encode. Never hand-edit the audio files.

## Player manual (owner rule: create AND maintain)
- `docs/PLAYER_MANUAL.md` is the player-facing truth. Any change to a player-facing mechanic, price, rule, screen or
  control updates the manual in the same commit. Generated reference sections come from data via
  `scripts/gen_manual.py`; its `--check` is gate step 12 (the FULL gate has 12 steps, and `python scripts/gen_manual.py` rewrites
  the tables between the `<!-- generated:name -->` markers). The in-game manual (`/manual`, More tab) renders the same file.

## Token discipline (Claude Pro: 5-hour window plus weekly cap)
- Keep gate output to its tail. Never paste whole files. Do not re-read files you already know.
- Prefer `Grep` (start with `artifacts/codemap/INDEX.md`) and targeted `Read` with offset and limit. Large data files are only touched by scripts.
- Update `NEXT:` in PROGRESS.md at least every 30 minutes: exact next action, files in flight, last gate result.
