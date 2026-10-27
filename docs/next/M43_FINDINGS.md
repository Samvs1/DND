# M43.1 findings: `python scripts/contract.py` on the 27 fixtures and the 3 round-8 saves

Run 2026-10-27. 27 fixture folders + r8-full (c-...-0001), r8-quests (-0003), r8-typed (-0002). Exit code 0 for now.
Skipped: all rules on `real-slendee` and `real-small` (events.jsonl only, no initial.json: cannot replay) and on
`synth-balanced` (hand-built log that does not parse); B1 on every other save (no `line_read` record before M43.1).
B6 and A1/A4 find nothing anywhere. A1 on fixtures only proves the replay runs (they have no snapshot.json); the r8 saves
have one and match.

| rule | total | per save |
|---|---|---|
| A1 | 0 | - |
| A2 | 8 | m35-r6-typed 8 |
| A3 | 0 | - |
| A4 | 0 | - |
| B1 | skipped | needs `line_read` (new saves only) |
| B6 | 0 | - |
| C1 | 9 | m29-p2 1, m29-p3 3, m29-r3-casters 1, m31-r4-full 2, m39-r7-full 1, **r8-quests 1** |
| C2 | 5 | m29-r2-p4 1, m29-r2-p8 1, m29-r3-items 1, m31-r4-quests 1, **r8-quests 1** |
| C3 | 10 | m29-p3 1, m29-r2-p7 1, m29-r3-full 1, m31-r4-full 1, m31-r4-quests 3, m31-r4-typed 1, m35-r6-quests 1, m39-r7-full 1 |
| C4 | 18 | m29-p3 3, m29-p6 3, m29-r2-full 3, m29-r2-p4 1, m29-r2-p5 1, m29-r2-p7 4, m29-r2-p8 1, m32-r5-full 1, **r8-full 1** |

## Examples and verdicts
- **A2** `m35-r6-typed A2 678 event 678 xp_gained pc-p2: wrote 568, running value 718` (8 lines, events 678-685, xp and gold).
  Real: the round-6 double payout, fixed in M35.1; none in any later save.
- **C1** `m39-r7-full C1 436 straighten-the-river: the target isca-murkline is a friend`;
  `m29-p3 C1 22 'Regent Varek' is two records: regent-varek, boss-bracken-march`;
  `r8-quests C1 669 the-coiner-s-false-gold: the target gerda-chainwright is the giver`. Real. The first is Z15, the
  second the boss-twin of R16; the r8 one (target = giver) is NEW after M41.4 and is a live bug for M43.4.
- **C2** `m29-r2-p8 C2 774 a-name-for-the-road: step 0 is a free step, the engine cannot check it`;
  `r8-quests C2 669 the-coiner-s-false-gold: step 1 repeats an earlier step` (two "Go to Gildspar Keep"). Real; the r8 one is live.
- **C3** `m39-r7-full C3 444 straighten-the-river: step 0 (clear) done, check fails` (the fight at the Grey Bog counted the
  moment the quest was accepted, the Z15 case); `m31-r4-typed C3 104 the-settled-ledger: step 0 (learn) done, check fails`.
  Real or an engine rule changed since the save (fixtures keep their own era's engine): r8 saves have 0, so no live C3.
  A step event decided in the same pass as an earlier one is judged on the state before that pass (false alarm fixed).
- **C4** `m29-p3 C4 4 the-last-egg: the reward 'Brood-egg' is asked for` (16 of these are the install-time reward = asked
  item, R10, repaired by M29.7c; all in m29 saves); `m32-r5-full C4 602 salt-for-the-elders: find 3 x Free-Given Salt, hand over 1`
  and `r8-full C4 127 the-painted-eggs: find 3 x Painted clutch eggs, hand over 1` (AA7). Real; the r8 one is live.
- **B6** false alarms fixed in the check: a racial spell spends a feature use (`infernal-legacy-darkness`, m29-r3-full 1450)
  and a scroll read is an `item_used` (m29-r2-p4 1145), neither a slot. The unit test drops a real slot event to prove the check bites.
- **B1** untested on live data until a new save exists; the unit tests cover it (a named spell answered by talk only = finding).

## What this tells M43.2 and M43.4
- Live now (r8): C1 target = giver, C2 repeated step, C4 find 3 / hand over 1. Nothing in A1-A4 or B6.
- The older fixtures will not be green: M43.5 needs either an allowlist per fixture (rule + index) or regenerating them.
- B1-B5 cannot be judged until a table writes `line_read`: the first new typed save is the baseline for M43.2.

## M43.3 D1: every refusal reaches the next narration's prompt
`scripts/contractlib/story_rules.TurnOutcomes`: for each `narration_recorded`, the prompt is rebuilt with the current
builder (`scripts/audit/replay.build_prompt`) on the state before it, from the events since the last narration WITHOUT
the refusal events themselves (the session does not hand every refusal over as an event: M43.2's menu refusals are
log-only), and every `action_impossible` since then whose reason is not in that prompt is a finding.

| save | D1 before | D1 after |
|---|---|---|
| m31-r4-typed | 3 | 0 |
| m35-r6-typed | 2 | 0 |
| m42-r8-typed | 2 | 0 |
| other 24 fixtures | 0 | 0 |
| r8-typed (-0002) | 2 | 0 |
| r8-full (-0001) | 0 | 0 |
| r8-quests (-0003) | 0 | 0 |

The pre-M43.3 saves hold only the storyteller's own impossible verdicts (M30.1, e.g. r8-typed 94 "Brienne has only
10 gold."), which the live narrator did get as events; the "before" count measures what the builder carried on its own,
which is what a menu refusal (M43.2, never handed over) depends on. After: the reducer keeps every refusal in
`Memory.untold` until the next narration and the builder tells it, so the rebuilt prompt always holds it.
Example, r8-typed 95 (rebuilt, events without the refusal): before, the EVENTS section was empty; after it reads
`Brienne tried "I slide Brenn 300 gold to tell me who winds the lower hand": nothing happened, because Brienne has only 10 gold.`
Who did it, r8-typed 482 (the rats told biting the party): the section had "Brienne loses 6 HP (now 14)." and no
source; it now also reads `Rook cast Burning Hands.` and `Rook dealt 6 fire damage to Brienne.` (and Elowen, Tamsin).
Not covered by D1 (no refusal exists): the skiff (r8-typed 335) and the wares (402) are stunts or a shop proposal with
no engine event; their telling is already told "No rule applied and nothing in the world changed." Vell (r8-quests 390)
is AA2 (B5, fixed in M43.2). The narration audit is unchanged in stale-as-present (0); three fixtures show 1-4 fewer
past records (FACTS trimmed first under the token budget: the outcome lines take priority over flavour).
