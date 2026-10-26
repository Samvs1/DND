# M38 interpretation eval: the router's trap sentences

The corpus is tests/fixtures/interpret/synthetic.jsonl: 161 rows. 153 of them are lines from the deleted keyword-router
tests and 8 are M38.1 seed rows, all on synthetic scenes (scripts/interpret/synthetic.py). The chooser, prompt and model are
the same as M36.9 pass 3 (deepseek flash). The only change since then is the M38.2 menu gap: attack-roll spells can now be aimed at a person here.

## M38.3 live pass (2026-10-26, 192 calls; M36 allowance 1,573 of 2,500 used)
The first run (`--cap 170`) scored 147 rows in 172 calls. The 14 rows the cap cut off were scored in a second run (20 calls).
Raw output: artifacts/eval/20261026-105005.json and artifacts/eval/20261026-105147.json (gitignored).

| metric | M38.3 (161 rows) | M36.9 pass 3 (300 playtest rows) |
|---|---|---|
| exact | 73.9% (119) | 90.0% |
| false action | 20.5% (33) | 4.0% |
| false other | 3.1% (5) | 3.3% |
| p90 latency | 2.34 s / 3.65 s | 2.01 s |

These lines were written to break a keyword reader, so a lower score than on real play is expected. Not all of the
traps catch the model. "I will not cast fire bolt", "I bow to the zombie", "I warm my hands by the fire" and
"I cast light on my light crossbow" pass. False actions, though, are five times the playtest rate. They group by cause:

### A. The named target is not offered, so the model swaps in one that is (8 rows; menu cause)
- "I help Rook up" (Rook is standing): help_up on Elowen, who is down.
- "I slap 10 gold down for Brienne": pay 10 to the peddler (the label is a hand-over to Brienne).
- "I leave 5 gold for the poor": pay 5 to Merre.
- "I ask my companions": talk to Reeve Hallick.
- "Elowen casts guidance on Old Renn": guidance on Elowen.
- "We go to the Old Bridgeheart" (barred): travel to Saltcrag Chapel.
- "Rook bows low to the thug" and "I keep my bow slung and greet the thug": talk to Reeve Hallick.

This is the cause behind the playtest rows the M36.9 report names (418, 521, 638, 868: an uncarried item swapped for a carried one), now
seen for people, heroes and places as well. It is the most harmful kind, because the engine acts on someone the player did not name.

### B. A save or auto-hit spell at a person out of a fight (4 rows; menu cause)
- "I cast burning hands at Merre / at the peddler / at him" and "Brienne casts magic missile at the ferryman" each give the bare scene cast.
  M38.2 opened the strike path for attack-roll spells only, so these have no entry that names the person.

### C. A menu label read the wrong way (3 rows; label cause)
- "I surrender" in a fight: `surrender:persuasion`, the entry that DEMANDS the foes' surrender.
- "I bow to the thug" and "I won't attack the thug" while an offer waits: `offer:parley:persuasion` (a persuasion roll).

### D. Word play with no menu cause (about 12 rows; no fix)
- "I cast a glance at the zombie": a longsword attack.
- "I cast a glance at the light": search.
- "I rest my hand on the hilt": talk.
- "we are lost": talk.
- "I get going": what_now.
- "I browse the wares": inventory.
- "I set my torch before the door": use the torch.
- "I tell the others to get ready": offer:fight.
- "I head towards the Low Rise": move plus dash.
- "I open my pack by the Foundling Vault": travel plus inventory.
- "I use the rope to force open the lock": use the rope.

These are the model's reading. Phrase rules and confirm prompts are ruled out (owner), so round 7 measures how often they come up in real play.

### E. Coins below 1 gp (2 rows; known gap, gold only)
- "four silver": the model paid 4 gp.
- "25 silver pieces": sent to `other`.

### F. Stunt or strike (3 rows; label judgement, kept)
- "I drop the longsword on the goblin's head", "I swing from the chandelier into the thug" and "I trip the thug with my longsword"
  were picked as a plain attack. The labels follow M36_LABELLING (a stunt is `other`, a trip is a shove).

## Plan for M38.4 (from these causes)
A, B and C are menu causes, so M38.4 covers all three:
- A: names the hero means but cannot act on (uncarried items, people and heroes not valid for an entry, barred places) are listed as
  not-offered targets that lead to `other`.
- B: save and auto-hit spells aimed at a person here take the M38.2 strike path.
- C: the demand-surrender and parley labels say what they do.

D, E and F get no fix.

## M38.5 live pass 1 (2026-10-26, after M38.4; 521 calls, allowance 2,094 of 2,500 used)
Raw output: artifacts/eval/20261026-114643.json (main) and artifacts/eval/20261026-115022.json (synthetic).

| metric | main M38.5 | main M36.9 pass 3 | synthetic M38.5 | synthetic M38.3 |
|---|---|---|---|---|
| exact | 87.7% | 90.0% | 80.7% | 73.9% |
| finding-cited | 84.2% | 90.0% | | |
| false action | 5.7% (17) | 4.0% (12) | 14.3% (23) | 20.5% (33) |
| false other | 5.0% | 3.3% | 3.7% | 3.1% |
| chooser failed | 0 | 0 | 2 rows | 0 |
| p90 latency | 2.20 s | 2.01 s | 2.15 s | 2.34 s |

The trap sentences improved, but the real playtest lines got worse. 13 main rows that passed in all three M36.9 runs (passes 2, 3 and
pro) fail now, and no row that failed all three passes now. The 13 regressions point to the M38.4 changes:
- B (area spells take person targets) made scene casts worse.
  - 42 "I cast Burning Hands at the damp ferns" is now aimed at Mother Marrow, a person, which opens a fight: a harmful new false action.
  - 651 "burning hands on the violet fungus" became a fire bolt.
  - 1345 "thunderwave out over the black water" went to `other`.
- A (rule 1: "the target the line names goes in its step even if the entry does not list it") makes the model put places and things
  in steps, which then fall to `other`. That gives an extra `other` on 64, 201, 378, 588 and 631, a lost hand-over on 68, a stray lift on 294,
  and 797 "I travel to Lamplighters' Rest" picked as look.
- C (the new surrender and parley labels): 419 "Drop your weapons and yield!" is now a parley instead of the demand to surrender.
- 210 (perception against investigation) looks like run-to-run noise.

The four uncarried-item rows A aimed at did not pass. 418 and 638 picked a parley or a talk, and 868 handed the chime to Elowen.
On the synthetic side, A fixed help_up at a standing hero, guidance and the companions talk, and B fixed the four person casts. "I surrender" still picks the demand.

## M38.5 final pass (2026-10-26, after fixes B d9cc01c, A 0aacceb and C 05e4aff; 392 calls, allowance 2,486 of 2,500 used)
Raw output: artifacts/eval/20261026-122057.json (main, 333 calls) and artifacts/eval/20261026-122318.json (synthetic subset, 59 calls).

| main corpus (300) | final | pass 1 | M36.9 pass 2 / 3 / pro |
|---|---|---|---|
| exact | **90.7%** | 87.7% | 91.0 / 90.0 / 91.7% |
| finding-cited | 90.0% | 84.2% | 89.2 / 90.0 / 89.2% |
| false action | **3.7% (11)** | 5.7% (17) | 6.0 / 4.0 / 3.0% |
| false other | 3.0% | 5.0% | 2.7 / 3.3 / 1.7% |
| p90 latency | 2.44 s | 2.20 s | 1.82 / 2.01 / 2.70 s |

- 12 of the 13 pass-1 regressions pass again. The 13th, 42 "Burning Hands at the damp ferns", picked `strike:burning-hands` with no
  target. Played offline, that step is `CastIntent(at_scene=True)`, the same act as the label: an id miss with no harm, not a person strike.
- Four rows that passed in all three M36.9 runs miss now: 42 above, plus 296, 658 and 968. Two of them add `other` and one adds a stray move;
  at about +-4 rows per 100 this is run-to-run noise.
- 521 (Caul's Bait-Cache), which failed all three M36.9 runs, now passes. 418, 638 and 868 still miss, on the model's own reading.
- The main corpus is at par with M36.9, with a lower false-action rate than pass 3. The 92% bar is still out of reach (M36.9, option 1).

Synthetic subset (43 rows: every pass-1 miss plus the A, B and C target rows; a hard set by selection, so not comparable to a full pass):

| same 43 rows | M38.3 | pass 1 | final |
|---|---|---|---|
| exact | 9 | 12 | **21** |
| false action | 28 | 23 | **16** |
| chooser failed | 0 | 2 | 0 |

- Fixed now: the burning hands strikes at a person, the guidance on Old Renn, "I won't attack the thug", "I bow to the thug",
  the greeting with the bow slung, gold to Brienne, the barred Old Bridgeheart, and the two former chooser failures.
- Still wrong, and harmful:
  - "I help Rook up" (Rook is standing) helps Elowen up.
  - "I leave 5 gold for the poor" pays Merre.
  - "I surrender" picks the demand.
- Still wrong, harmless: "magic missile at the ferryman" is a scene cast, and the D word-play rows. Round 7 measures these in real play.
