# GOAL: Balancing by playtest (M29)

Owner request, 2026-10-17. Binding. Main-session decisions are marked **D:** and repeated in docs/DECISIONS.md.
Runs last (after M27 gear and darkness, M28 tooltips): balance is measured on the finished mechanics.

Owner: "I want opus 5.5 to orchestrate the testing using sonnet/haiku agents playing a full playthrough with
different party groups, playstyles, approaches etc... If a bug is found also report (no need to scan the ui
everytime, bugs mainly related to backend systems)."

## Owner answers
1. Balance targets: the main session's defaults (below).
2. Agents play against the **live DeepSeek** storyteller; the scripted simulations use the **fake** one.
3. No UI scanning per run: agents play through a text tool; UI bugs are out of scope unless something crashes.

## Targets (`data/balance_targets.json`, data so they can be tuned)
- Normal fights at the default difficulty: **75-90% won with no hero falling** (balanced play style).
- Boss fights: **at most one hero down** on average.
- The party reaches each region's boss at the **planned level** (the plan's tier levels).
- Gold: **about one meaningful upgrade per region**: median gold per hero at a region's end is at least the price
  of the cheapest next-tier upgrade, and less than three times it.
- Health of the system: 0 server exceptions, 0 silent turns, AI fallback rate under 5% of narrated turns,
  every save replays to its snapshot.

## Two layers
**D: volume in code, exploration by agents.** Agents are expensive (a full playthrough is 200-400 actions,
several hundred thousand tokens), so the numbers come from free scripted runs and the agents hunt bugs and odd play.

### Layer 1: scripted simulations (fake storyteller, free, hundreds of runs)
- `scripts/simulate_party.py` grows play styles (aggressive, cautious, talker/Peace, cunning, big spender, hoarder)
  and party shapes (classic four, all martial, all casters, solo, two players), and plays a **full campaign** to the
  epilogue (today it stops at the first gateway).
- `scripts/run_metrics.py <save>`: metrics read from a save's `events.jsonl` (works for sims, agents and real
  players' saves): fights won/lost, HP lost per fight, heroes down, deaths, rests, gold in/out by source, XP and level
  per act, level at each boss, quest outcomes, AI fallbacks and refusals, exceptions.
- `scripts/balance_report.py`: aggregates many runs against the targets, PASS/MISS per target per style and party.

### Layer 2: agent playthroughs (live storyteller, a few runs)
- `scripts/agent_play.py`: a text tool over a real server on its own port. `new` (party, play style, live AI),
  `look` (a SHORT state: place, exits, people, things, party HP/slots/conditions, hotbar options with ids in a fight,
  cards waiting, What now?), `act "<text>"`, `do <slot> [target]`, `move <zone>`, `answer <card> <choice>`.
  Every output carries the save id and event number so a bug reproduces.
- `.claude/agents/playtester.md`: Haiku by default, tools limited to running `agent_play.py` and writing its report;
  never edits the tree. The persona comes in the spawn prompt.
- Report per run (`saves/playtests/<run>/report.md`, gitignored): bugs (title, severity, save id, event number,
  steps, expected, actual), balance notes (too easy/hard where), frustrations, a 5-line summary.
- **Opus orchestrates:** briefs the agents, runs 2-3 at a time (this PC runs low on memory), reads ONLY the reports
  (never transcripts), removes duplicates, reproduces each bug from its save, and writes
  `docs/playtests/M29_round<n>.md`.

### Personas (round 1)
| # | Party | Style | Length | Model |
|---|---|---|---|---|
| 1 | classic four (fighter, cleric, rogue, wizard) | balanced | full campaign | Haiku |
| 2 | all martial | fights everything, never talks | full campaign | Haiku |
| 3 | talkers (bard, cleric, warlock or nearest) | avoids fights, Peace ways | full campaign | Sonnet |
| 4 | rogue-heavy | Cunning ways, gear and darkness, locks | full campaign | Sonnet |
| 5 | solo hero | careful | acts 1-2 | Haiku |
| 6 | any | tries to break it: item tricks, invented items, injections, out-of-turn actions | act 1 | Sonnet |
| 7 | any | economy: shops, selling, potions, hoarding | acts 1-2 | Haiku |
| 8 | all casters | spell slots and rests | acts 1-2 | Haiku |
Classes follow what the data ships. A cap of 400 actions per run; a stuck agent reports and stops.

## Fixing and tuning
- Every confirmed bug goes to `hard-engineer` with a named regression test (`test_m29_<slug>`); never a skipped test.
- Tuning changes **data only** (`dm_tiers.json`, `encounter_budget.json`, `loot_tables.json`, shops, prices), never
  SRD numbers or their goldens; each change gets a DECISIONS line with the metric before and after.
- After tuning, Layer 1 re-runs until the targets pass (or a DECISIONS line says why one cannot); round 2 of the
  agents covers the changed areas plus one full playthrough.

## Done means
- `balance_report.py` over the final scripted runs prints PASS for every target (or a documented exception).
- Two agent rounds done; every bug they found is fixed with its regression test or logged with a reason.
- `docs/playtests/M29_round1.md`, `M29_round2.md` and the final balance table are committed.
