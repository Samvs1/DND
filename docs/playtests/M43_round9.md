# M43.6 Round 9: three live runs after M43 (the contract) (2026-10-28)

Every finding below was checked against the run's save (event numbers are `seq` in its events.jsonl), by one
read-only checker per save. Claims a save did not bear out are listed at the end. No fixes were made: the owner decides.

## Runs
| run | party, persona | campaign (generated) | reach | events | commands |
|---|---|---|---|---|---|
| r9-typed (seed 2, Sonnet) | fighter, rogue, wizard, cleric; types everything, probes B1-B5 twice each | Act 1-2, into act 3 (Char Vaults) | all alive, L4 | 1717 | about 213 of 220 |
| r9-quests (seed 3, Haiku) | classic; quest auditor | Brinehollow Coast, Gleamhollow Fen | acts 1-2 settled by alliance, all alive, L3 | 1159 | 169 of 180 |
| r9-full (seed 1, Sonnet) | classic; normal table, balance numbers | "The Bell and the Bloom" | epilogue reached, nobody fell, L5 | 1768 | about 250 of 320 |

Saves: saves/playtests/r9-*/saves/ (c-20261028-161756-0002 typed, -0003 quests, -0001 full). Spend: **1,021 DeepSeek calls**
(llm.jsonl 7693-8713; round 8: 875). Playtester reports and the three verdict files are in the session scratchpad.

## The contract on the live saves (`python scripts/contract.py`)
| save | A1 | A2 | A3 | A4 | B1 | B6 | C1 | C2 | C3 | C4 | D1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| r9-typed | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| r9-quests | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| r9-full | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |

**All 5 findings are false alarms of the checks** (BB18): the 4 B1 hits are questions about a place ("I ask Mirelle where the
smugglers are on the Salt Flats", talk is the right outcome), and the C3 hit (r9-full 735) judged a step on a stale state.
**The contract caught none of the real defects below.** Why: B1 checks that a typed line has *an* outcome; the typed-line defects
of this round all had one, just the wrong one (a stand-in zone, a story instead of a cast or a buy). B3-B5 are covered by session
tests only, and the tests cover the cases round 8 found, not the next form.

## M43 verdicts
- **Held:** state A1-A4 (0 on all saves; ledger, replay = snapshot, no stale record shown as present). Quests at registration
  C1-C4 (0; AA5 held: no quest targets its giver). AA2: a hand-over typed at a master's waiting fight offer works (r9-quests 570, 1142;
  r9-full 1497). AA4: every leveled cast spends a slot. B5: waiting cards stayed through other lines (r9-typed 75-77, 334-342,
  1033-1042, 1422-1433 and more). D1: refusals with reasons reach the story (r9-typed 644, 741, 291, 975) and so does who burned whom
  (178, 447, 688).
- **Not held:** AA1/B3 (3 of 3), AA6/B2 on the shop path, AA8/B4 (a part dropped with nothing said), B2 for spells and features
  named out of a fight or by another hero (BB2-BB5). AA15 (the harness returns before a line resolves) was not in M43's scope.

## Findings
### Harmful
- **BB1 A typed area spell aimed at a named foe still lands on the caster's own zone (AA1, B3), 3 of 3.** r9-typed 160 "Rook casts
  Burning Hands at the wolf" read `cast:burning-hands>scrub` (the party's zone; the wolf in `boulders`), burning Brienne, Elowen and
  Tamsin (165-176); 434 and 678 (Thunderwave) the same. No refusal. Cause: the menu lists only the zones the cone reaches, the model
  picks one of them; M43.2's fix covers a pick at the creature, not a pick at a stand-in zone.
- **BB2 A typed buy is a buy AND a payment: 100 gold for a 50-gold potion (new).** r9-quests 618 "buys a potion of healing from the
  peddler for fifty gold" read `[buy, pay>peddler]`: -50 at 620 and -50 handed over at 623-624. r9-typed 285 the same, saved only by a
  short purse. The ledger passes (each debit has a cause).
- **BB3 Typed shop buys of stocked items go to the storyteller, which denies the stock (AA6 on the shop path).** r9-typed 1006/1010
  Potion of Greater Healing (stocked 150), 1546-1553 Scroll of Revivify (stocked 300): `other`, no buy, no refusal; the stock is not in
  the storyteller's manifest (guard flag `unknown_name:Scroll`), so it says there is no such scroll. 279 and 938: a buy part neither
  played nor refused.
- **BB4 Named spells and features out of a fight go to the storyteller (B2).** r9-quests 284 "casts healing word on her" (Tamsin at 0 HP):
  `other`, no cast, "the light fades"; it forced a 40-supply long rest (293), against the manual's "Healing outside a fight".
  r9-typed 728 Channel Divinity: Preserve Life: told as healing, no HP, the use never spent. 231 Bless on the party: an invented failure.
- **BB5 A line naming another hero runs as the acting hero (new).** r9-typed 79/91 "Tamsin buys a Healer's Kit" from Brienne's seat took
  Brienne's gold and gave Brienne the kit; 214 "Tamsin casts Cure Wounds on Brienne" from Brienne's seat went to the storyteller.
  (M41.3 Z7 covers shared steps such as search and pickup, not buys or casts.)
- **BB6 A part of a line is dropped with nothing said (AA8, B4).** r9-typed 151 "I end my turn and then dodge": steps `[end-turn]`, the
  dodge never played or told. 1593: the order of three parts changed and the refusal reason was incomplete.
- **BB7 Own Fireballs did 56% of all damage the party took in r9-full (by design, AA1's last sentence).** 1530, 1665: 89 of 158 HP; the
  second ended Elowen's Spirit Guardians. Sculpt Spells is an `unsupported` hook (RULES_DECISIONS M2.4) and areas hit allies (M3.4). The
  phone marks "(ally)" per zone; the text harness does not show it. Stored fact 1763 says Tamsin burned herself (the caster is excluded): false.

### What the storyteller says
- **BB8 Foe acts told before (or without) the engine's events: the largest family.** r9-full 9 narrations (94, 99, 176, 250, 938, 988, 1395,
  1577, 1702: the animated armour never attacks in its fight yet shoves and swings twice); r9-typed 6 more (542, 557, 563, 571, 579, 589:
  written at the hero's end of turn, before the foes' turn exists; the real blows at 592-624 differ). The manual promises a foe that did
  not attack this moment is never told lunging or swinging. Cause is timing, not input: the telling at a turn boundary runs before the
  foes act.
- **BB9 The real shop stock is not in the storyteller's input.** Invented wares and prices (rope, oiled hide, lamp oil, "steel shirt 80 gp":
  r9-quests 159-168, 552, 553, 611; r9-full 13 narrations), stocked items denied (BB3), and "no one moves to buy" right after sales (r9-full
  512, 519, 670, 685, 865, 872).
- **BB10 Told but not done:** a hand-over (r9-quests 768 the song to Nettledew; r9-full 846 the vellum to Marl), a favour's coin promised and
  never paid (r9-quests 51, round-5 X11), a person told absent (r9-full 1352 Maple Fenwick), phantom foes (1086), "learned nothing" after the
  step was learned (905), damage on a passed save (r9-quests 362).
- **Slip rate (D2), confirmed slips per 100 narrations:** r9-typed 8.8 (11.3 with 4 more found), r9-quests 4.3, r9-full 12.4; all three:
  **38 to 42 in 427 narrations, 9 to 10 per 100** (13.6 if the invented-wares lines count). Round 8: 2.6 (11 in 427). **Not like for
  like:** round 8 counted the testers' claims; this round the testers were told to list every slip and r9-full's checker read all 153
  narrations. More than a third of round 9's slips (15) are BB8, a kind round 8 did not count.

### Smaller, new
- **BB11** A learn step is met by a shop: the generated lore tag is the start town's name and every generic peddler is "<town> Peddler"
  (r9-quests 160, `lore_talk` counts a person whose name holds the tag).
- **BB12** A bribe the hero could not pay moved the person's attitude (+10) and was narrated before the refusal (r9-typed 1325-1329).
- **BB13** Two Investigation rolls for one search line, the second from the storyteller (r9-full 1334, 1336).
- **BB14** A decoy item: the pruning hook is taken by the master with no step asking for it (r9-full 1497; the route had no hand-over).
- **BB15** Action Surge refused as "already used your action" when the real reason is that it is spent (r9-typed 1649).
- **BB16** A refused long rest (not enough supplies) leaves no `action_impossible` (r9-typed 916): B1 gap outside the typed path.
- **BB17** The Hollowsalt peddler speaks over the person the player addressed (r9-quests 8 narrations at 34-155).
- **BB18** Contract false alarms: B1 counts a question about a place as a line with no outcome; C3 reuses a stale state after a
  `route_discovered` in the same pass (scripts/contractlib/quest_rules.py).

### Balance (r9-full `balance_report.py`: every target PASS or N/A)
- Fights cost little: HP lost per fight 6, 0, 12, 7, 0, 0, 0, 0, 0, 133 (the last: 89 own Fireballs, 44 from the master). Labels still
  undersell for a small wizard (r9-quests: "trivial" worg and animated armour took Tamsin to 0 five times; AA11). Every foe attack in
  r9-full (17 of 17) went at Tamsin (AC 11).
- Gold floods from act 2: r9-full 2,730 in, 300 out, 2,490 unspent (AA13); r9-typed one talk quest paid 300 gp each against 15 gp at start.
- XP: 80% from milestones, 11% quests, 9% fights (owner kept the table; AA14). A long rest costs 40 supplies everywhere, inns included (AA12).

## Not borne out / by design
- r9-quests "quests complete before their hand-over" and "an item no longer held was accepted": the side quest and the master's peace way
  share a title; the song was in Brienne's pack until the real hand-over at 1142. "Fight step credited with no fight": by design (manual).
- r9-typed "searches dropped" (played at 125, 328, after the footer: AA15), "kit buy failed" (bought 88-90), "3 minutes" (31.9 s max).
- r9-full multi-hop move (the engine walks the whole route; the harness returns after the first hop: AA15), Mass Healing Word one target
  (the line named one), the off-hand dagger (it exists; never tried), the finale confirm (harness syntax).

## For the owner (no fixes made)
1. The typed-line families (BB1-BB6) came back in new forms: the contract checks that a line had an outcome, not that the outcome is
   what the line named. A check that compares `line_read` (what the model picked) with the names the line holds (the same whole-word
   name match the menu already uses) would have caught BB1, BB3, BB4 and BB5 from the saves.
2. The two biggest storyteller families have plain-code causes: BB8 is when the telling runs (before the foes' turn), BB9 is a missing
   input (the shop stock). Both are input or timing fixes of the D1 kind, not phrase checks.
3. BB2 (double charge) and BB5 (the wrong hero pays) are engine reading defects with money at stake.
4. Sculpt Spells (BB7) is an SRD Evocation feature the engine marks unsupported.
5. The D2 target is still open; the measured rate depends on how hard one looks (2.6 by tester claims, 9-10 by reading).
