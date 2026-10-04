# Usage plan: building `aidm` on Claude Pro, interrupted and unattended

## Constraints this plan is built around
- **Claude Pro**: a rolling 5-hour usage window plus a weekly cap. Either one can cut a session off mid-step.
  Opus uses the budget several times faster than Sonnet.
- **The owner is asleep** for long stretches. Nothing can depend on a human answering a question.
  Agents never ask. They decide, log the decision in `docs/DECISIONS.md` and move on (SPEC 0.6).
- **Any session may be brand new.** All state lives in `PROGRESS.md` (`NEXT:`), git history and `CLAUDE.md`.

## Budget strategy
1. **Main session = Sonnet orchestrator** (`/model sonnet`). It reads `NEXT:`, delegates ONE checkpoint,
   relays the gate tail and loops. It holds little context and does little thinking, so it is cheap.
2. **Opus only where reasoning pays off**: the 33 **H** checkpoints go to `hard-engineer` (opus, effort high).
3. **The 33 M checkpoints go to `mechanical-engineer`** (sonnet, effort low). That is half the plan at a fraction of the cost.
4. **Cold-start cost is controlled by narrow prompts.** Each agent reads only CLAUDE.md, its PROGRESS line,
   the cited SPEC sections and the files in flight. `docs/V1_LESSONS.md` replaces re-reading v1.
5. **Commit per checkpoint.** A cutoff loses at most one checkpoint (about 30 minutes).
6. **Within a 5-hour window**: start with H checkpoints while budget is fresh. When the window is nearly spent,
   or Opus is rate-limited, switch to an eligible M checkpoint (see Pull-forward) instead of idling.

## Ordering principles (highest value and lowest risk first)
The milestone spine M0 -> M9 is fixed by SPEC 0.2 and by real dependencies. Inside that spine:
1. **Gates before code** (M0.2, M0.3). They are cheap, near-zero risk, and every later checkpoint relies on them.
2. **Engine before AI.** A correct deterministic engine is the product's core value (the dice and rules can be trusted)
   and its risk is low because everything is testable offline.
3. **Interpreter before content.** Build the DSL or loader (H) first, then bulk content (M) that only fills data.
4. **Fallback before the LLM path.** Template narration (M4.5) and the sample campaign (M5.1) land before
   or alongside the live-model paths. If the budget dies, the game is still playable without a key.
5. **External services last.** DeepSeek live tests, Fish audio and live simulation (M8, M9.4) carry outside
   risk (API changes, cost) and add polish, not core value.
6. **Hardening at the end only finds bugs.** Every v1 regression test is written inside the milestone that owns it.

## Ordered checkpoint list (76 total: 35 H, 38 M, 3 ORCH; A1-A3 from docs/ADDENDUM_ASSETS.md, M10 from docs/ADDENDUM_ASSET_GEN.md)
ORCH = done by the main (orchestrator) session itself, not delegated, because it requires viewing images and judging them.
Value: 3 = core and blocks everything, 2 = needed for a playable game, 1 = polish or verification.
Risk: L/M/H = chance of rework or getting stuck.

| # | Checkpoint | Type | Value | Risk | Note |
|---|---|---|---|---|---|
| 1 | M0.1 Plan | M | 3 | L | done in commit `M0: plan` |
| 2 | M0.2 Skeleton plus tooling | M | 3 | L | |
| 3 | M0.3 Gate scripts plus gate.ps1 | M | 3 | L | |
| 4 | M0.4 v1 assets plus V1_LESSONS digest | M | 2 | L | |
| 5 | M0.5 SRD vendoring | M | 3 | L | network once |
| 6 | M0.6 Typed loaders | M | 3 | L | |
| 7 | M0.7 Monster loader goldens -> `M0: Foundation` | M | 3 | M | v1 bug class |
| 8 | M1.1 Dice and abilities | H | 3 | L | |
| 9 | M1.2 Events, reducer, replay | H | 3 | M | architecture keystone |
| 10 | M1.3 Checks and defences | H | 3 | L | |
| 11 | M1.4 Damage choke point, death saves | H | 3 | L | |
| 12 | M1.5 Conditions plus concentration | H | 3 | M | |
| 13 | M1.6 Rests plus coverage -> `M1: Rules core` | H | 3 | L | |
| 14 | M2.1 Class, race and background data | M | 2 | L | pull-forward OK |
| 15 | M2.2 Creation pipeline | H | 3 | M | |
| 16 | M2.3 Spell-slot model | H | 3 | M | single source of truth |
| 17 | M2.4 Feature hooks | H | 3 | H | design-heavy |
| 18 | M2.5 Level-up plus derived sheet | H | 2 | M | |
| 19 | M2.6 Per-class goldens -> `M2: Characters` | M | 2 | L | |
| 20 | M3.1 Zones | H | 3 | M | |
| 21 | M3.2 Encounter lifecycle | H | 3 | M | |
| 22 | M3.3 Combat commands plus hit chance | H | 3 | M | |
| 23 | M3.4 Spell DSL interpreter | H | 3 | H | design-heavy |
| 24 | M3.5 Spells batch 1 (cantrips, level 1) | M | 2 | L | |
| 25 | M3.6 Spells batch 2 (to >=50) | M | 2 | L | |
| 26 | M3.7 Surfaces lite | H | 2 | M | |
| 27 | M3.8 Monster actions | H | 3 | M | |
| 28 | M3.9 Monster catalogue >=60 | M | 2 | L | stat goldens pull-forward OK |
| 29 | M3.10 Monster AI | H | 3 | M | |
| 30 | M3.11 50-seed combat sim -> `M3: Combat` | H | 3 | M | |
| 31 | M4.1 LLM client plus FakeLLM | H | 3 | M | |
| 32 | M4.2 Tools plus executors | H | 3 | M | |
| 33 | M4.3 Registry plus context builder | H | 3 | M | |
| 34 | M4.4 Adjudicator plus pre-checks | H | 3 | H | |
| 35 | M4.5 Narrator plus template fallback | H | 3 | M | fallback = playable without a key |
| 36 | M4.6 Guard | H | 3 | H | v1's #1 failure |
| 37 | M4.7 Memory plus NPC voice | H | 2 | M | |
| 38 | M4.8 Injection suite plus no-key e2e -> `M4: AI layer` | H | 3 | M | |
| 39 | M5.1 Plan schema plus sample campaign | M | 3 | L | pull-forward OK (after M1.2) |
| 40 | M5.2 Region graph plus soft-lock checks | M | 3 | L | escalate if it fails twice |
| 41 | M5.3 Campaign generator (LLM) | H | 2 | M | |
| 42 | M5.4 Progression plus encounters | H | 3 | M | |
| 43 | M5.5 Social plus point of no return | H | 2 | M | |
| 44 | M5.6 Items >=80, shops, loot, XP, quests | M | 2 | L | catalogue data pull-forward OK |
| 45 | M5.7 Epilogue -> `M5: Campaign` | M | 1 | L | |
| 46 | M6.1 Protocol plus codegen | M | 3 | L | |
| 47 | M6.2 Table actor | H | 3 | H | concurrency plus combat ownership |
| 48 | M6.3 Persistence plus replay on disk | M | 3 | L | |
| 49 | M6.4 Server, WS, reconnect, healthz, LAN | M | 3 | M | |
| 50 | M6.5 Host controls -> `M6: Session and server` | M | 2 | L | |
| 51 | M7.1 Frontend shell plus lobby | M | 3 | L | |
| 51a | A1 Asset manifest, assetUrl, SVG placeholders | M | 2 | L | Addendum A |
| 52 | M7.2 Character wizard | M | 3 | L | |
| 53 | M7.3 Table view | M | 3 | M | |
| 54 | M7.4 Combat view plus hotbar | M | 3 | M | |
| 55 | M7.5 Sheet, inventory, spellbook | M | 2 | L | |
| 56 | M7.6 Journal, map, shop, host -> `M7: Frontend` | M | 2 | L | |
| 57 | M8.1 Fish adapter plus cache | M | 1 | M | external API; pull-forward OK |
| 58 | M8.2 TTS sentence pipeline | M | 1 | M | |
| 59 | M8.3 Music plus /screen | M | 1 | L | |
| 59a | A2 Style bible plus ASSETS_TODO | M | 1 | L | Addendum A |
| 59b | A3 Placeholder-only Playwright proof | M | 1 | M | Addendum A |
| 60 | M8.4 Accessibility -> `M8: Audio and polish` | M | 1 | L | |
| 61 | M9.1 simulate_party.py | M | 2 | L | |
| 62 | M9.2 Fix sim defects | H | 3 | H | |
| 63 | M9.3 Playwright suite | M | 2 | M | |
| 64 | M9.4 Live DeepSeek and Fish tests | H | 2 | H | costs API credits |
| 65 | M9.5 Adversarial QA plus fixes | H | 2 | M | the QA itself is a fresh read-only subagent |
| 66 | M9.6 Docs plus verification report -> `M9: Hardening` | M | 1 | L | |
| 67 | M10.1 Generator core plus budget guard plus FakeImageProvider | H | 2 | M | money safety |
| 68 | M10.2 Auto-checks, slicer, contact sheet, install/revert | M | 2 | L | |
| 69 | M10.3 Dry run plus ASSET_PRIORITY.md | M | 2 | L | |
| 70 | M10.4 Live smoke (1 image) | H | 2 | H | BLOCKED path if key or org verification fails |
| 71 | M10.5 P1 generation run | ORCH | 2 | M | the main session itself |
| 72 | M10.6 Review loop | ORCH | 2 | M | the main session opens every sheet |
| 73 | M10.7 Final review plus UI screenshots -> `M10: AI assets` | ORCH | 1 | L | then the final VERIFICATION REPORT |

Classification rule: **H** = rules core, combat, AI layer, guard, plus the table actor (it owns combat turn
order) and defect fixing, which needs cross-layer reasoning. Everything else is **M**.

## Pull-forward list (M work you may run early, for example when Opus is rate-limited)
Run these only when their dependencies are committed. Each still gets its own commit and does not break the gate.
- M2.1 class/race/background data: after M0.6.
- M3.9 monster catalogue selection plus stat goldens: after M0.7 (action-execution tests stay in M3.8).
- M5.1 campaign schema plus sample campaign: after M1.2.
- M5.6 item catalogue data only (shop logic waits): after M0.6.
- M8.1 Fish adapter (pure adapter plus mocked tests): after M0.3.
When you pull one forward, tick it in PROGRESS.md and keep `NEXT:` pointing at the spine checkpoint.

## If the weekly cap is about to stop the build (triage)
The minimum playable game without a key is M0-M3, M4.1-M4.5, M4.8 (fallback path), M5.1-M5.2, M6, M7.1-M7.4.
If the budget is clearly short, finish those first, then go back to the guard (M4.6), memory, polish and audio.
Record any reordering in `docs/DECISIONS.md`.

## Resume protocol
Paste this into a new session (or use it as the headless prompt):

> Resume the aidm build. Follow CLAUDE.md "Session start", then run the checkpoint loop from the NEXT: line
> in PROGRESS.md, delegating H checkpoints to hard-engineer and M checkpoints to mechanical-engineer.
> Keep going until the usage limit stops you. Do not ask questions; log decisions in docs/DECISIONS.md.

Optional, for unattended overnight runs (set it up and test it once while you are awake): a Windows Task
Scheduler job every ~5 hours that runs `claude -p "<prompt above>" --model sonnet` in this folder.
It needs pre-approved permissions in `.claude/settings.json` (pytest, ruff, pyright, lint-imports, python scripts,
git add/commit, pip) or it will stall on the first prompt. Because each run is a fresh session, a run that
starts while the limit is still active simply exits, and the next run picks up from `NEXT:`.
