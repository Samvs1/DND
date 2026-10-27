# M42 Round 8: three live runs after M40 and M41 (2026-10-27)

Every finding below was checked against the run's save (event numbers are `seq` in its events.jsonl).
Claims a save did not bear out are listed under "Not borne out" at the end.
No fixes were made. The owner decides.

## Runs
| run | party, persona | campaign (generated) | reach | events | commands |
|---|---|---|---|---|---|
| r8-typed (seed 2, Sonnet) | fighter, rogue, wizard, cleric; types everything, probes the M40/M41 fixes | Greyfell Lowreach | act 1 master dead, into act 2, all alive, L3 | 1309 | about 214 of 220 |
| r8-quests (seed 3, Haiku) | classic; quest auditor | "The Chain of Ashes" | act 1 won (Vell), into act 2, all alive, L3 | 1028 | 169 of 180 |
| r8-full (seed 1, Sonnet) | classic; normal table, keeps balance numbers | "The Hollow Crown of Veyr" | acts 1 and 2 won, act 3 mid-fight (mimic), all alive, L4 | 1801 | about 318 of 320 (cap) |

Saves: saves/playtests/<run>/saves/ (c-20261027-064955-0002, -0003, -0001). Playtester reports were kept in the session scratchpad.
No cross-talk: every command carried `--run` (Z18 fix).

## Automatic checks (all three saves)
- Ledger (`scripts/sim/ledger.ledger_problems`): **0 problems**. Replaying events.jsonl equals snapshot.json: **yes** on all three.
- Narration audit (`scripts/narration_audit.py`, M40.3): **0 stale records shown as the present** in every store, journal and epilogue
  (427 narrations; round 7 before M40: ~90-100% of prompts had at least one).

## Fix verdicts (round-7 findings)
- **Z1 (typed yes at a card starts the fight), holds for confirm cards, new variant open.** Typed "Yes, go ahead" took a quest (r8-typed 381-382),
  answered a parley confirm (607) and "Yes, do it" confirmed the attack on Marrow Snagg (629). But a peaceful hand-over typed at a master's
  fight offer still ends in the fight (AA2), and a bare "yes" at a four-choice offer picks fight (AA9).
- **Z2 (out-of-reach travel swapped), holds.** Snagglegate (act gate), the Candle Stair (master first) and an unknown vault were refused in the story with the reason.
- **Z3, Z8 (hero-to-hero gold, counts), hold.** r8-typed 41 (5 gold), 350 (4 gold), 46 (two rations), 338 (three candles); a give beyond what the hero holds is refused with the reason (345).
- **Z4 (paying more than the hero has), holds for gives, open for shops and gifts.** "I slide Brenn 300 gold" is refused: "Brienne has only 10 gold" (96).
  A shop buy without the gold and a large gift to an NPC give no reason (AA6).
- **Z5 (spell with no slot), holds outside a fight, open in one fight case.** Out of a fight: "You have no spell slot left for that" (1211). In a fight one case was told honestly (1238), one was told as a kill (AA3).
- **Z6 (parts of a line dropped), mostly holds.** "Rook lights a candle and we all head down to The Gearcut Ossuary" did both (868); the Brenn line told the cut part (96).
  "We walk back to Saltmere Landing and then I search the walls" (373): the travel happened and the search was told ("turns up only old timber", 380) with no roll.
- **Z7 (named hero acts), holds.** "Tamsin searches the bandits' bodies" from Rook's seat rolled for Tamsin (329); "Elowen picks up the Hidden Skiff" from Brienne's seat gave it to Elowen (333).
- **Z14 (favour completes away from its giver), holds.** Every side quest that closed in the three saves closed on a give or meet step at its giver (r8-typed 388, r8-full 533, 625, 1114, 1706, r8-quests 994).
- **Z15 (favour against a friend), open in a new form.** A favour names its own giver as its target (AA5).
- **Z18, Z19 (harness), hold.** No cross-talk; `do use potion-of-healing` works as a bonus action in a fight (r8-full).
- **Z9-Z13 (storyteller slips), not fixed by M40's input fix.** The stale-input family is gone (audit 0), but 11 slips were found in 427 narrations (round 7: 8 listed). See "What the storyteller says".

## Findings
### Harmful
- **AA1 A typed area spell lands on the caster's own zone and burns the party, the named foe untouched.** r8-typed 213 "Rook casts burning hands on Bandit B":
  216 `spell_cast` `target_zone` sunken_hall (Rook's zone; Bandit B was in the courtyard), 219-223 Elowen -4, Tamsin -9 (to 1 HP), Bandit B unharmed.
  Again at 466-476 ("on the giant rats"): Brienne, Elowen and Tamsin -6 each, all four rats untouched. The foe was out of the cone's reach;
  the line should be told that (not-offered with the reason), not cast at the only zone in reach. Sculpt Spells is unsupported (manual: `Sculpt Spells*`), so allies always take it.
- **AA2 A peaceful hand-over typed at a master's fight offer starts the fight and loses the peace route.** r8-quests 381 offer (Vell, two skeletons),
  388 "Rook ... holds out the Child's Glass Whistle to Vell the Ash-Broker", 389 `attitude_changed` +10, but no `keepsake_given` and no step done;
  390 the story has Vell refuse it; 391 `offer_resolved` fight. The peace route "One Memory Returned" ends exactly in that step
  ("Give Child's Glass Whistle to Vell the Ash-Broker"), so it could not be finished. Same family as Z1.
- **AA3 A spell with no slot is told as a kill.** r8-typed 261 "Rook casts magic missile at Bandit B" (Rook 0 slots): no cast, no damage;
  262 "Rook's magic missiles streak ... snuffing out his snarl". The bandit stands at 5 HP and is killed later.
- **AA4 A leveled spell runs as a free "Creative action".** r8-typed 549 "Rook casts thunderwave at giant rat A": `check_resolved` CON DC 15 (Rook's DC is 12),
  `dice_rolled` label "Creative action", no slot spent (Rook 1/3 before and after).

### Quests
- **AA5 A favour targets its own giver, with a doubled step.** r8-quests 669 "The Coiner's False Gold": `giver_npc_id` and `against_npc_id` both gerda-chainwright;
  steps 0 and 1 are both "Go to Gildspar Keep" and tick together (695, 696). It still closed at Gerda and paid once (993-997).
- **AA7 A three-part find leaves two keepsakes after the give.** r8-full 327-339: three "Painted clutch eggs" found (one shared item list for the main route and the side quest);
  531 one is given to Mara Ost and the quest completes; the other two stay in Brienne's keepsakes for the rest of the run.

### Typed-line interpretation
- **AA6 Buying or giving more gold than the hero has is told without the reason.** r8-typed 52-65: Elowen (20 gp) "I pay the peddler 100 gold for a healing potion",
  then "I buy a healing potion ... for 50 gold": "the coin stays in her hand", and 63 answers the earlier 100-gold line. 402-404 Tamsin (47 gp) "buys a Potion of Healing" (50 gp):
  no price or shortfall. 576-579 (400 gold to Yseult) and 607-609 (1000 gold to Marrow Snagg): "the gold stays in her hand". The give path does give the reason (96).
- **AA8 Two-act line: the second part is told without being played.** r8-typed 373-380 (above, Z6).
- **AA9 A bare "yes" at a four-choice offer picks fight.** r8-typed 184 "Yes, go ahead" at the two-bandit offer, 185 `offer_resolved` fight.
  The card offers fight, surprise, escape and parley; "yes" names none of them.

### What the storyteller says (11 slips in 427 narrations)
The manual promises each of these never happens ("What the storyteller can and cannot do"). Five follow a line where the engine did nothing
or refused without the storyteller being told why (AA3, AA10 skiff, AA10 wares, AA6's 63, AA2's 390).
- **AA10 Slips, by kind:**
  - an item that does not exist found: r8-quests 660-661, a successful search of Vell's body "draws out the Ashen Signet"; no item exists, and 656 just said it was not there (closed world).
  - a foe told gone while it fights: r8-full 73 and 89, the crocodile "slides back into the water" and "vanishes below the surface" at 11/19 HP; it moves at 80 and dies later. AA3 above.
  - a hand-over told that did not happen: r8-full 960, Brienne "sets [the ingot] into his waiting palm"; the step stays open until the real give (1113-1114).
  - the engine's result undone: r8-typed 844, 10 rations bought (840-842), told as "The sale never closes". r8-quests 390 (AA2).
  - who did it: r8-typed 482, the rats "close as one ... shallow bites" while the damage was Rook's fire (466-476) and the surprised rats did nothing (479-480);
    the false account is stored in the scene summary (572).
  - presence: r8-typed 336, the skiff "stays where it lies" while Elowen holds it (333); r8-typed 780, "Wex is not at his post" while Wex is present (Tamsin talks to him at 785).
  - shop stock: r8-typed 404, wares "tin trinkets ... a small oiled crossbow", none in the shop list.

### Balance (numbers from the saves and the playtesters' tallies)
- **AA11 Labels (Z16) still undersell.** Offers labelled trivial: dire wolf (r8-full 966, Tamsin to 1/20; r8-quests 819, the 10-HP wizard to 0 twice), duergar, gargoyle, cockatrice.
  The rats-and-stirge fight labelled easy took Brienne to 1/12 (r8-full 139). The hard master Marrow Snagg (r8-typed 592, offered with 4 bandits) was a 2-round fight.
  The labels follow the XP budget; what drives the danger is single big foes against a 10-14 HP wizard, high ground and darkness (shown in the roll lines).
  Foes pick the AC 11 wizard almost every time (r8-full).
- **AA12 Resources (Z17).** A long rest costs 40 supplies for 4 heroes (r8-typed 581: 49 -> 9; r8-full 43 -> 3 and 48 -> 8); 10 rations cost 5 gp, so supplies are cheap once known.
  Short rests: 2 per long rest, the third refused with a clear message; Arcane Recovery works (r8-typed 363-364). Casters ran dry after about two fights.
- **AA13 Gold swings from short to idle.** Start 15 gp, a potion costs 50 (r8-typed could afford one after pooling in act 2; about 4 gp per fight).
  r8-full: about 150 gp each after act 1, then 400 gp each from one act-3 quest, with nothing in the shops worth that.
- **AA14 Levels come from places, not fights.** "Clear" milestones pay 100-200 XP each (r8-quests 106 `clear:mirefold-tollhouse` +100, 794 +200) and quests 150-300;
  fight kills pay 12-50. L2 after the first fights, L3 at the end of act 1, L4 after the act-2 master (r8-full: 343 / 1111 / 3036 XP). Parley skips a master for full XP.
  This is the milestone table the owner chose to keep (M31); listed only as feel.

### Tooling (the harness, not the game)
- **AA15 `act` returns before a typed line resolves.** All three runs: "(the table said nothing for this line)", and the result lands 1-2 commands later
  (r8-typed 212/224, r8-full 94/114, r8-quests 160/167). Likely cause: `scripts/agent/link.py` `_told` counts a wait with no `event` yet as told, so the 2 s quiet window ends
  while the chooser call (FAST, before any event; M36) is still running. It made playtesters report working lines as ignored (see below).

### Smaller
- The roll line for a Life cleric's heal does not show the Disciple of Life bonus (r8-full 217-218: "1d4+3 = 5", heals 8). Correct by SRD (2 + spell level); confusing on screen.
- A cistern underground uses swamp zone names ("Stilt Hut", "Hollow Stumps", r8-typed 1237).

## Not borne out
- "Healing Word adds the modifier twice" (r8-full B1): it is Disciple of Life (SRD, +3 at 1st level); cure wounds shows the same (r8-typed 238-239).
- "Typed end turn is ignored" (r8-typed B7): "Elowen ends her turn" (132-133) and "Tamsin passes her turn" (241-242) end the turn. The harness lag (AA15) hid it.
- "The storyteller names the wrong foe and attacker" (r8-quests B5): Elowen did kill the zombie (348-352) and Brienne the first bandit (67-71).
- "Quest steps vanish when the master dies" (r8-quests B4): the main quest closes on the force route at Vell's death (645) by design; its other routes and leads go with it.
- "100-200 XP on fight start" (r8-quests B6): these are place-clear milestones (`reward_granted` kind milestone), not fight rewards.

## Spend
logs/llm.jsonl lines 6818-7692: **875 DeepSeek calls** (83% of round 7's 1,048).
deepseek-v4-pro: 447 narration streams + 54 tool calls (social/long lines and 3 campaigns); deepseek-flash: 250 chooser calls, 99 tool calls, 25 place descriptions.
Tokens: pro 2.01 M in / 0.06 M out, flash 1.21 M in / 0.06 M out.
