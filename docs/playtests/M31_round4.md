# M31 round 4: verifying M29.9 and M30 on the live storyteller

Round 4 (2026-10-24), after M29.9a-d (round-3 fixes) and M30 (one intent router, impossible actions, no free
spells). The owner approved it on 2026-10-24 ("You may run a fourth play test if necessary"). The runs:
- typed everything, acts 1-2 (Sonnet), `r4-typed`, seed 2, fighter/rogue/wizard/cleric;
- quest audit, acts 1-2 (Haiku), `r4-quests`, seed 3, classic;
- full campaign to the ending (Sonnet), `r4-full`, seed 1, classic (Tamsin the half-orc wizard).

Saves are in saves/playtests/r4-*/saves (gitignored). Reports came back as text. The main session checked each
claim against its save before listing it here. Findings are numbered V1.. (rounds 1-3 used G, R and T).

## The runs
| Run | How far | Commands | Party at the end | Guard (narrations / rewritten once) |
|---|---|---|---|---|
| r4-typed (c-20261024-023915-0002) | acts 1-2, stopped at the act-3 border | 262 of 300 | all alive, level 3, 84-137 gp | 199 / 27 (13.6%) |
| r4-quests (c-20261024-023917-0003) | acts 1-2, stopped at the act-3 border | about 188 of 300 | all alive, level 3, 90-117 gp | 151 / 31 (20.5%) |
| r4-full (c-20261024-023916-0001) | full campaign, ending reached (1643) | about 268 of 450 | all alive, level 5 (9279 XP), 58-118 gp | 194 / 50 (25.8%) |

## What the fixes did (verified in the saves)
| Fix | Verdict | Events |
|---|---|---|
| T1 Sleep spares undead | Verified: the cultist slept, the zombie did not. | full 74 |
| T19 Acid Arrow on a miss | Verified: a miss still did half (12 rolled, 6 lost). | full 1402 |
| T18 Relentless Endurance | Verified: Tamsin stayed at 1 HP and spent the use; at 0/1 she fell; a long rest restored it. | full 187, 403, 509 |
| T20 prepared spells | Verified: the wizard's prepared list only grew across four level-ups. | full 319, 775, 1175, 1580 |
| T12 surrender | Verified against living foes: one roll, the fight ends as a victory, XP and loot paid, the yielded foe counts as beaten. Not against undead (V5). | full 427-447; typed 518, 888, 1442 |
| T15 / R14 sure parley | Verified twice: after the peaceful route the master's offer waited through other actions and a hand-over, showed "parley (sure to hold)", and settled by alliance with no roll. | full 1145-1173, 1625-1641 |
| T8 offer respawn | Verified: after a typed fight, `answer fight/escape/parley` on the same offer reply "nothing is waiting"; no foe came back, nothing paid twice. | quests 59-98 |
| T14 / T3 quest payouts | Verified: no step closed and nothing paid at acceptance in 8 acceptances; visits count only after acceptance; step lines are plain. | quests 34, 227, 696, 823, 930; full 339, 498, 513, 751 |
| T17 paying | Verified: typed pay and count out move gold; over-paying is refused plainly. | typed 40, 44, 47; quests 1160 |
| T5 placing | Verified: setting an item before an NPC gives it; setting a pack down with nobody named does not. | typed 57, 59, 1360, 1364 |
| T9 stowed weapon | Verified: the named stowed weapon is drawn, then attacks. | typed 141, 389 |
| T16 bystanders | Verified: questions to bystanders during a fight offer stay talk. | typed 113, 334, 770 |
| M30 impossible | Verified: no roll and a plain line, in and out of fights; the action is kept in a fight; hard climbs get a check. One miss (a ferry-boat lift got a DC 20 check). | typed 235, 238, 804, 241, 1450 |
| M30.2b scene casts | Verified when nobody stands near (heals and buffs typed outside fights spend slots). Not when NPCs stand near (V2). | typed 79, 94, 903, 1345 |
| T21 ending | Half: allies "sided with the party", routes told by deed. The prose still drops the quest list and contradicts itself (V20). | full 1643 |

## Findings
| # | Finding | Events | Family | Status |
|---|---|---|---|---|
| V1 | **Typed spells in a fight never cast.** "I cast magic missile at the sahuagin" became a model check (INT vs DC 5, "strikes automatically"), a "creative action" spent the action, no slot, no damage, while the prose told three darts striking. Same for Guiding Bolt (the foe got "helped"), Inflict Wounds, Burning Hands, Turn Undead, Fire Bolt, Ray of Frost and "I call down sacred flame" (model DC 15, the real DC is 12). The M30.0b cast row exists only outside fights. | typed 127-128, 163, 356, 361, 392-395, 622, 655, 935 | typed actions | open, high |
| V2 | **Typed hostile spells at scenery outside a fight still go to the model when NPCs stand near** (M30.2b's "living NPC in the scene" exclusion is too broad): Burning Hands at reeds and Thunderwave over water spent no slot and the model invented backfire damage to the caster (2 fire, 9 thunder). A spell named without the word "cast" ("I murmur a healing word over Rook") was told as failing. | typed 80-87, 1346-1349 | typed actions | open, high |
| V3 | **Some weapon phrasings miss the attack rows** and become checks, and a "creative action" then deals damage with no attack roll (13 from a longsword, above its maximum of 11): "loose an arrow at ... with my shortbow", "jab ... in the ribs with my rapier", "cut down the spider with my sword", "cut down Penn". | typed 156, 478, 648, 859, 1393 | typed actions | open |
| V4 | **Words to foes during a fight offer have no single rule.** Peaceful lines with no name ("Easy now, friend in the robe ... we don't want a fight") got a model check and left the offer open; a question to the named master ("I ask Grinner Voss what the Silent Company collects") was a parley that failed (3 vs 10) straight into the fight. | typed 113-114, 579, 773; quests 373-381 | typed actions | open |
| V5 | Demanding surrender from undead rolls, "succeeds" (nat 20) and does nothing, with no line, and spends the action. Undead never yield, so there should be no roll and a plain line. | typed 1143-1146 | typed actions | open |
| V6 | "I drink the herbal poultice Brienne gave me" aimed the poultice at Brienne (full HP, no effect) and used it up. A drink always targets the drinker. | typed 1291-1293 | typed actions | open |
| V7 | "I sheathe my longsword and sling my shield on my back" was told, nothing changed (AC 18). A compound line with one half already done is refused whole. | typed 1335 | typed actions | open |
| V8 | Typed acceptance of a quest offer ("Sure, we'll take the job, Merre") does not accept it; only `answer yes` does. | typed 64, 537 | typed actions | open |
| V9 | **Searching:** a typed search of the priory shelves lit a candle and rolled no discovery check, so the hidden quest key (placed at 604, DC 10) was never found and the NPCs later said no key survives. Elsewhere a failed search check (13 vs a model DC 15) still discovered the item (its own DC is 10), and the line says both "fails" and "finds". | quests 604, 937-942, 1061; full 971-974 | typed actions | open |
| V10 | **A typed attack on a multi-foe offer brings only the named foe.** offer-97 (zombie, cultist) fielded only the zombie; offer-324 (sahuagin, stirge) only the sahuagin, while the prose kept the stirge; offer-633 (Brother Mallow and a cultist) only Mallow. | typed 97, 119-123, 324, 341, 391; full 633, 648-652 | encounters | open, high |
| V11 | A successful parley with a master before the peaceful route is done consumes the offer ("no fight"), leaves the region unresolved and the exit locked; the only way on was to attack. | full 633-650 | encounters | open |
| V12 | "Region resolved by alliance. The way to the next region is open." while the gate still wants one unseen place. | typed 284, 551 | encounters | open, low |
| V13 | **Learning from talk never counts.** Bramble said what he carries and the model recorded a fact tagged `bramble-grief`, yet the learn step stayed open and the favour failed. The act-1 peaceful route "Learn about mallow" could not be finished: Sister Thena's secret stayed hidden at deeds 20, and Mallow's own story did not count. Meanwhile a place-based learn step ("Learn about tithing") closes on mere arrival. | quests 42-52, 225-228, 685, 834; full 537-587, 645 | quests | open, high |
| V14 | Quests and favours that say "come back" end at the deed: Kreel's "go to the Priory and come back with word" closed on arrival; the ledger quest closed on pickup though the giver said "bring it back". Kreel also promised coin, and favours never pay. | quests 819-835; full 482 | quests | open |
| V15 | A favour's only step was repaired to an unrelated place ("Go to Cinder Cairn" for "what the ash left in the priory depths"). | quests 925-928 | quests | open |
| V16 | An unchecked step kind (`free`, "Open the unfinished mirror ... guide the twin's reflection free") kept model text that nothing can check. | quests 694 | quests | open |
| V17 | **The storyteller still invents foe actions and foes, and misreports results:** foe swings before the foe's turn (typed 391; full 155, 787, 871-887, 1372), robed cultists that do not exist (full 80, 89, 229), a real hit told as a near-miss (full 187), Acid Arrow on an acid-immune mimic told as a wound (1263), a half-damage miss told as a plain miss (1405), searched items told as taken while still on the ground (464, 606, 625), a gift to Thena told as to the peddler (545). | as listed | storyteller | open |
| V18 | A quest offer still waiting was told as accepted ("You accept Warder Pell's strange request"). | full 745, 749 | storyteller | open |
| V19 | A keepsake appeared with no hand-over told (the model gave it while the prose says the broker "lets the offer hang"). | quests 699-700 | storyteller | open, low |
| V20 | The ending says the Grieving Spark was "won over" and also "laid low", lists no quests, and ends with a template filler ("the scene waits on your next move"). | full 1643 | storyteller | open |
| V21 | The acting hero's gear is missing from what the model sees: a sealed-door check said "no crowbar at hand" while Brienne carried one since the start. | quests 0, 931-933 | storyteller | open |

## Not bugs
- Death saves are rolled at the start of the hero's own turn (quests 420-421), as SRD 5.1 says.
- Wren's "nothing without the False-Door Key" matches the quest's own find step (quests 694, 1045).
- Main quests are active on entering a region (quests 32, 683); a main quest closes when its master is beaten (force route).
- `answer finale <id>` confirms at once by design of the harness (M29.9d).
- A Healing Word heals more than the die line shows: the Life domain bonus (quests 433-434; full 426). Display only.

## Harness and low items
- `look` shows no open step text, only one-line quest summaries.
- `act` sometimes returns before the turn's narration is written, so the footer lags (typed 141, 160; full 426-455).
- `act "what now"` prints nothing; the finale description was cut ("forever a The campaign is complete.").
- Damage lines do not say "immune" or "resisted" (full 1260, 1392); the shop shows the Hearty Meal Basket at 2 gp but charges 1.5.
- Ammunition never runs down (arrow x20 after many shots). No RULES_DECISIONS line says so; BG3 does not track basic ammunition.
- "I toss Brienne 10 gold for her trouble" was refused as "does not carry that"; "I slap 50 gold down for Merre" (15 gold carried) was told as coins on the table with no refusal.

## Balance
- Every fight was easy or trivial in all three runs. The masters were weak: Grinner Voss (a hobgoblin, 11 HP), Brother Mallow (a ghoul, 22 HP, never acted), the Tithekeeper (a wight, 26 HP against the SRD 45). Only the Counting-House fight (quests) dropped heroes.
- Levels: level 3 at the end of act 2 in both short runs, level 5 in the middle of act 3 in the full run, inside the M29.6b targets. XP is dominated by place and master milestones (50/100, 100/200, 400/800 per place; 600 and 2600 for masters settled by peace) over fight XP (12-112).
- Gold at the end of act 2: 84-148 per hero, around the bottom of the M29.6b band (100-900). Quests carry most gold (25 gp to 150 gp each).

## Round 4 totals
Spend: 931 DeepSeek calls (logs/llm.jsonl lines 3545-4475), 4.43M prompt and 0.16M completion tokens, about 0.4-1.5
USD. That is 125% of round 3 (746 calls), above the "at or under round 3" aim, mostly because the full run went
to the ending and the typed run used 262 commands.

| Round | Narrations | Rewritten once | Template | Mixed |
|---|---|---|---|---|
| 2 | 854 | 179 (21.0%) | 21 (2.5%) | 22 (2.6%) |
| 3 | 472 | 113 (23.9%) | 12 (2.5%) | 20 (4.2%) |
| 4 | 544 | 108 (19.9%) | 7 (1.3%) | 15 (2.8%) |

## By family
- Typed actions (V1-V9): 9 of 21. The router made phrasing explicit, but whole scopes are missing (casts in fights, spells without "cast", searches, quest answers) and the offer talk rule is split across rows.
- Encounters (V10-V12): 3. V10 is one root: the typed fight start fields the attacked foe, not the offer's foes.
- Quests (V13-V16): 4. Learning is the weak point: talk never teaches, places teach on arrival.
- Storyteller (V17-V21): 5. Invented foe actions remain the largest honesty family.

## Fix plan (M31.1, before M31.2)
- **M31.1a H typed actions:** V1-V9.
- **M31.1b H encounters and quests:** V10-V16.
- **M31.1c H storyteller:** V17-V21.
- **M31.1d M harness and low items**, then the FULL gate and the commit `M31: Round 4`.
