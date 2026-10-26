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
