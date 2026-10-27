# M43 The game's contract: rules it never breaks, checked on every save

Owner 2026-10-27: "after 8 rounds novel bugs and recurring bugs keep showing up. We should find a more definitive way to
prevent this." Answer: stop finding bugs by playtest and fixing them one by one. Write down what the game must never do,
check it automatically on every save, and fix each family where it starts. Playtests become rare (feel, balance, new families).

## Why the loop happens (the evidence)
- **State families stopped recurring once they had an automatic check.** Ledger (double payouts), replay = snapshot, the
  narration audit (stale facts): 0 problems on every round-7 and round-8 save since M35 and M40.
- **Three families have no check and come back every round in a new form:**
  - typed lines doing the wrong thing: G4 G17 G33, R7-R9 R22 R26, T5-T9 T16 T17, V1-V9, X1-X8, Y9-Y15, Z1-Z8, AA1-AA4 AA6 AA8 AA9.
    AA1 is R26 again: aimed cones were fixed for the button in round 3; the typed path never got the fix.
  - the storyteller saying what did not happen: G1 G3 G21 G31 G32, R2 R12 R19, T4 T10 T11, V17-V20, X10-X16, Y16-Y19, Z9-Z13, AA10.
  - generated quests that cannot be followed: G20 G30, R1 R10 R11 R14 R16, T2 T3 T13-T15, V13-V16, X9, Y6 Y7, Z14 Z15, AA5 AA7.
- Three runs of about 700 commands sample a tiny part of "any line x any state x any campaign"; each fix closes the corner
  that was found, so each round finds 15-24 new ones.

## The rules
Each rule names how it is checked. "Saves" = `scripts/contract.py`, run in the gate over all 27 fixture saves and on any live save.

### A. State (exist; keep)
- **A1** Replaying events.jsonl gives snapshot.json. (`scripts/sim/checks.replay_problems`)
- **A2** Every gold, XP and item change has its cause, and each reward pays once. (`scripts/sim/ledger.ledger_problems`)
- **A3** No story record older than a change to what it names is shown as the present. (`scripts/narration_audit.py`)
- **A4** HP and every resource stay within 0..max. (`scripts/sim/checks.engine_invariants`)

### B. Typed lines (the turn contract)
- **B1 Every typed line ends in one of four outcomes:** engine events for what it named, a card waiting for its player,
  a refusal with a reason (`action_impossible`), or, only when it names no game thing, talk or flavour from the storyteller.
  Never silence, and never "nothing happens" without the reason.
  Covers G4 G17 G33, T17, V8, X3 X7, Y13, Z3-Z5, AA3 AA6.
- **B2 A line that names a game thing never goes to the storyteller as a creative action.** Game things: a known spell,
  weapon, item, gold amount or place. The line becomes a menu entry or a refusal with the reason (no slot, out of reach,
  not carried, not enough gold, not open yet). Creative actions stay for stunts that name no game thing.
  Covers R22, V1 V3, X1, AA3 AA4 AA6.
- **B3 The act aims at what the line named, or refuses.** No stand-in target, spell, weapon or place. An area spell's
  zone holds the named target, or the line is told it is out of the spell's reach. Covers R26 = AA1, Y10, Z2, Z5, G23.
- **B4 Every part of a line plays in order, or the dropped part is told.** Covers V7, X6, Y12, Z6, AA8.
- **B5 A waiting card is answered only by a line that picks one of its choices.** Any other line, a hand-over included,
  leaves it waiting, plays on it as itself (the route hand-over), or asks. A bare "yes" at a card with more than two
  choices asks which one. Covers T8 T16, V4, X3-X5 X7, Z1, AA2 AA9.
- **B6 The same act follows the same rules on every path** (button, typed, held). Saves: a `spell_cast` above
  cantrip level spends a slot of that caster (unless from a scroll or item), with the caster's save DC. Covers V1, AA4.

### C. Generated quests (checked where a quest is registered: the campaign install and the favour tool)
- **C1** A quest's target is never its giver, nor anyone friendly or allied with the party; one person is one record.
  Covers G30, R16, Z15, AA5.
- **C2** Every step is a kind the engine checks, appears once, and names the place, person or item it checks.
  Covers R1, T2 T3 T13, V15 V16, Y7, AA5.
- **C3** A step completes only from events after the quest was accepted, at its place or person; a "come back" step
  completes only at the giver. Covers G20, T11 T14, V14, Z14, Z15 (Y7 sub-case).
- **C4** A counted find and its hand-over use the same count; the reward is never the item asked for.
  Covers R10, R11, AA7.
- **C5** Every route can be finished: a route's last hand-over or meet works while that master's offer waits.
  Covers R14, T15, Y6, AA2.

### D. The storyteller
- **D1 The storyteller is always told the turn's outcome in plain words**, including "nothing happened, because X" and
  who did what (whose fire burned whom). Saves: every `action_impossible` and every refusal reaches the prompt that
  tells it (rebuilt as `narration_audit` does). Round 8: 4 of the 11 slips came after a turn where the engine did
  nothing or refused without the storyteller knowing why (AA3, the skiff, the wares, Vell), one more was who did it
  (the rats), and the stale 50-gold answer (AA6, r8-typed 63) is the same shape.
- **D2 The slip rate is measured, not guessed.** Each live round reports slips per 100 narrations from the saves
  (round 8: 11 in 427, 2.6 per 100). The target is the owner's call.

### Not rules
Balance (fight labels, supplies, gold, XP pace) is tuned from numbers, not pass/fail; it stays with `scripts/balance_report.py`
and the sims. Rules accuracy against SRD 5.1 stays with the golden tests.

## The story check: what plain code can and cannot do
The plan promised a plain-code story check before players see the story. The evidence says it would not work:
- The existing word-based claim classifier (`aidm/rules/story_claims.claim_kinds`, built for stored facts) finds **0 of the 11**
  round-8 slips. The storyteller writes "snuffing out his snarl" and "slides back into the water", not "killed" or "fled".
- The prose guard already does this with 2,929 phrases in 31 modules (4,271 lines), and slips reached players in every round.

So no new phrase or word check. What plain code can do is D1: remove the biggest trigger by telling the storyteller what
happened and why. What is left (an invented item, a person told absent, a foe told leaving) can only be caught by reading
meaning. After D1, round 9 measures the rate (D2), and the owner chooses: accept the measured rate, or a model check on the
risky beats only (paused 2026-10-26).

## Simplicity limits (every brief carries them)
- Reuse what exists: `scripts/sim/checks.py`, `ledger.py`, `narration_audit.py`, `rules/menu_unoffered.py`, `action_impossible`,
  and the campaign validator in `dm/campaign_steps.py`. No new framework, registry or plugin layer.
- `scripts/contract.py` is one runner. Each rule check is at most about 30 lines, with one test built from a real save event.
- One new persisted record at most: how a typed line was read (its menu entries or its refusal), so that B1-B5 can be
  checked from a save. A refusal is an `action_impossible` event (it exists), not a notice only.
- B2's fix removes a route (named game things into the creative action). Its diff should delete more than it adds; if it
  grows, stop and review.
- No phrase rows, lexicon words, guard keys or new confirm prompts (owner, M36). The guard does not grow.

## Steps
| step | what | who | model, effort |
|---|---|---|---|
| M43.1 | `scripts/contract.py`: A1-A4 wired, B6, C1-C4 from saves; the read-line record; run on all 27 fixtures and the 3 r8 saves; findings list | mechanical-engineer | Sonnet, medium |
| M43.2 | B1-B5: one path for typed lines (named game things never reach the creative action; refusals are events; cards answered only by a choice) | hard-engineer | Opus, high |
| M43.3 | D1: the turn's outcome, refusal and who-did-it reach the storyteller | hard-engineer | Opus, medium |
| M43.4 | C1-C5 at registration (install and the favour tool): repair or reject | mechanical-engineer | Sonnet, medium |
| M43.5 | contract green on all fixtures, `/simplify` pass, FULL gate, commit `M43: The contract` | orchestrator | - |
| M43.6 | round 9 (needs a fresh OK): contract on the live saves, slip rate (D2), balance numbers | playtesters | Sonnet/Haiku |
