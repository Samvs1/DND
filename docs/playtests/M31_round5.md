# M31 round 5: verifying M31.1a-g on the live storyteller

Round 5 (2026-10-24) ran after the M31 fixes: M31.1a-c fixed round 4's V1-V21, M31.1d-g made masters tougher, and
M31.1e fixed the harness. The owner approved it on 2026-10-24 ("Ok for round 5 if necessary"). The runs:
- typed everything, acts 1-2 (Sonnet), `r5-typed`, seed 2, fighter/rogue/wizard/cleric;
- quest audit, acts 1-2 (Haiku), `r5-quests`, seed 3, classic;
- full campaign to the ending (Sonnet), `r5-full`, seed 1, classic.

Saves are in saves/playtests/r5-*/saves (gitignored). The main session checked each claim against its save before
listing it here. Findings are numbered X1.. (rounds 1-4 used G, R, T and V).

## The runs
| Run | How far | Commands | Party at the end | Guard (narrations / rewritten once) |
|---|---|---|---|---|
| r5-typed (c-20261024-113624-0002) | acts 1-2, stopped at the act-3 gate | about 217 of 220 | all alive, level 3, 213-234 gp | 149 / 32 (21.5%) |
| r5-quests (c-20261024-113626-0003) | acts 1-2, stopped at the act-3 border | 139 of 180 | all alive, level 3, 15-25 gp | 115 / 27 (23.5%) |
| r5-full (c-20261024-113624-0001) | full campaign, ending reached (1443) | 221 of 320 | all alive, level 5, 79-105 gp | 141 / 37 (26.2%) |

## What the fixes did (verified in the saves)
| Fix | Verdict | Events |
|---|---|---|
| V1 typed casts in fights | Verified: Guiding Bolt, Magic Missile, Fire Bolt, Ray of Frost, Scorching Ray and Sacred Flame each rolled, spent the slot and dealt real damage. | typed 77, 93, 144 |
| V2 scene casts near people | Verified: Burning Hands at ferns with an NPC near spent the slot, "strikes no one", and no backfire was invented. | typed 46 |
| V3 weapon phrasings | Half: "loose an arrow ... with my shortbow" and "jab ... with my rapier" attack; many other weapon lines still become creative checks (X1). | typed 102, 200 |
| V4 words to foes | Half: a peaceful line shows the confirm card, cancel keeps the offer and confirm rolls. One peace line to a master started the fight (X4). | typed 62, 65, 71 |
| V5 undead surrender | Verified in fights: no roll, a plain line, the action is kept. Not while the offer waits (X5). | typed 354, 428, 1176 |
| V6 drinking | Verified: a poultice and a potion healed only the drinker. | typed 560, 1140 |
| V7 compound gear | Half: the shield half worked and the sword half was dropped (X6). | typed 37 |
| V8 typed quest answers | Verified: typed accept and decline. | typed 35, 297, 890; quests 392-396 |
| V9 searching | Verified: discovery checks find hidden quest items and lay them on the ground. | typed 301, 588, 1011; quests 336, 667 |
| V10 multi-foe offers | Verified: every foe of the offer joins a typed attack and `answer fight`. | quests 166-168, 173 |
| V11/V12 masters and the way on | Verified: a master's region settles only through a route that is done ("the master still waits" before it). | quests 362, 806 |
| V13 learning from talk | Verified, but a favour's own giver can teach it (X9). | quests 399-400 |
| V14 come-back favours | Verified: favours end with "Meet <giver>". The asker still promises coin (X11). | quests 393 |
| V17-V20 storyteller | Half: foe actions in hero turns and invented foes remain (X13, X15). The ending's engine-written record is right (masters, who lived, quests, left behind). The prose names the wrong start place and the finale ends with a filler line (X16). | full 1442-1443 |
| M31.1e harness | Verified: heal lines show die and bonus, damage lines say "resists", lot prices ("2 for 3 gp"), `look` and `act "what now"` show the open steps. Footer lag remains outside foe turns (X17). | full; typed |
| M31.1d-g masters | As designed: bugbear 32, basilisk 42, ghoul 26 (SRD 22 raised by the spoke floor), bearded devil 42 (52 x 0.8), vampire spawn 41 (82 x 0.5). In play they are short fights (Balance). | typed 837; full 526, 906 |

## Findings
| # | Finding | Events | Family |
|---|---|---|---|
| X1 | **Typed weapon lines still become creative checks.** "I run the thug through with my longsword", "I slash at the thug's knees with my longsword", "I hack at the thug with my big sword", "lets fly with her shortbow at the fungus", "I put an arrow in the zombie's chest", "I hammer the Duke again with my longsword": a bare ability check spends the action, sometimes deals damage with no attack roll, and the story tells a kill ("pinning him to the toll gate ... the fight goes still", thug alive at 2/32) or a hit (fungus 18/18). | typed 118, 177, 215-217, 354-356, 448-450, 756 | typed actions |
| X2 | A named spell phrased as a strike ("Tamsin hits the zombie with a Guiding Bolt") is read as a melee attack and refused as out of range. | typed 497 | typed actions |
| X3 | **A typed attack or hostile spell at a waiting offer only starts the fight**: no attack and no cast follow, while the story tells the hit or the cast ("Rook's arrow flies true", "Flame roars from his palms"). | quests 162-166; typed 354, 938 | typed actions |
| X4 | **A peace line to a master started the fight with no roll** ("sings a quiet song for the drowned to Drum-Captain Orvo Hael, offering him peace" -> offer resolved as fight); the confirm card was shown but nothing was left to confirm. | full 903-904 | typed actions |
| X5 | Demanding surrender from undead while the offer waits rolls Intimidation and the story says the zombie obeys; then the fight starts. | typed 420-422 | typed actions |
| X6 | Lines with two parts do only one: the sword half of "sheathe my sword and sling my shield" (typed 37), the attack of "charge the zombie and cleave it" (typed 431), the hand-over of "pick up the salt and hand it to Gran Tevin" (full 614). "Hands the three salt-lanterns to Bram" gives one of three (quests 284-285). Multi-hop travel stops at the first hop (typed 402, 592, 1038). | as listed | typed actions |
| X7 | **Giving the route item to a master while its offer waits does nothing** ("Rook gives Caul's Bait-Cache to Abbess Marwen Salt" -> no event and the filler "The moment passes, and the world waits for what you do next."), so the peaceful route could not be finished. A ring given to the yielded Duke never moved and the line said he "turns hostile". A move to a place that is not adjacent gets the same filler with no reason. | full 519-522, 619; typed 853-855 | typed actions |
| X8 | An impossible line in other words ("I lift the whole thicket out of the ground and hurl it over the treetops") rolled Strength. | typed 642 | typed actions |
| X9 | A favour's learn step is taught by the favour's own giver, who says she has not gone in to look; the step text shows the raw tag ("Learn about fog-leaves-standing"). | quests 393, 399-400 | quests |
| X10 | The storyteller made an errand outside the quest system ("a run of silverleaf to the manse gate", a keepsake with no quest, coin promised); it was never a step. | quests 44-46 | quests |
| X11 | Favour asks still promise coin ("I will pay fifteen silver") and the story later says the full sum was paid while no gold moved. | quests 391, 395, 638 | storyteller |
| X12 | Foe actions told in a hero's turn remain ("The thug slashes low with the hook-knife", "the next javelin takes Rook across the ribs" with Rook unhurt), foes told scattering while alive (rats at 1/24, bats at 22/22), a sleeping cultist told lifting his blade, Scorching Ray hits told in the wrong order. | quests 477; typed 121, 683, 1227, 1318-1321; full 140, 372, 401, 451 | storyteller |
| X13 | A gift told as refused ("makes no move to take it ... his warmth cools") while the model's own tool made him friendly and closed the step. | full 180-182 | storyteller |
| X14 | Stale scene: a parley with the ghast at the Leech-Beds told as the earlier bandit captain and "the three behind him"; "three shapes" behind a one-foe offer ("shapes" is not a foe-kind word, a known M31.1c gap). | full 1223, 1256 | storyteller |
| X15 | The finale reply ends with the filler "The moment settles, and the scene waits on your next move."; the epilogue prose says the tale "ended where it began, in the Flooded Chapel" (it began in Tidefall). | full 1442-1443 | storyteller |
| X16 | Found told as taken ("Rook's fingers close on a carved peat node", "the locket sits in her open palm" while it lies on the ground). | quests 338; typed 1011 | storyteller |

## Not bugs
- A master's region settles through any one route that is done (quests 362, 806): the quest run expected every route's steps first. "What now?" lists every route without saying one is enough (low, in X17 below).
- Death saves roll at the start of the fallen hero's own turn (quests 536-537), as in round 4.
- The Cold Clapper was not found: three failed checks (3, 0 and 8 against DC 10, all at disadvantage in darkness).
- Sleep skipped the undead zombie and put Brienne to sleep (typed 466): SRD 5.1 Sleep spares undead and takes the next lowest hit points in the area, allies included.
- Burning Hands hit allies in a shared zone (typed 788): Sculpt Spells is the known gap in docs/RULES_DECISIONS.md.
- The Healing Word "die" reads 4-6: it is 1d4 plus the cleric's Wisdom; the bonus is Disciple of Life.

## Harness and low items
- X17: `act` and `do` still return before the turn settles with the live storyteller outside foe turns ("the table said nothing", results a few events later: typed 149/153, 431/439, 276/281; quests 518/522 a `do cast` printed nothing). `do attack` breaks an expected-damage tie toward the light crossbow over a ready longsword (quests 510). `look` shows no wielded gear or pack. `do feature action-surge` fails (the id is `action-surge-1-use`). "What now?" could say that one route settles a master.

## Balance
| Master | Run | HP | Word | Rounds | Acted | Heroes down |
|---|---|---|---|---|---|---|
| Duke Ossric (bugbear) | typed act 1 | 32 | easy | 3 (yielded) | every round, all on Rook | 0 |
| Mother Vyra (basilisk) | typed act 2 | 42 | easy | 2 | once (a miss) | 0 |
| Abbess Marwen Salt (ghoul) | full act 1 | 26 | easy | 1 | once (a miss) | 0 |
| Drum-Captain Orvo Hael (bearded devil) | full act 2 | 42 | easy | 2 | twice (Tamsin 19 to 1, Relentless Endurance) | 0 |
| The Marrow Caul (vampire spawn) | full act 3 | 41 | medium | 2 | twice | 1 (Tamsin, stable) |
| The Thornmaw, The Unwed King | quests acts 1-2 | - | easy | settled by a sure parley | - | - |

- Live: 1 hero down in 5 master fights (0.2), against the scripted grid's 1.69 for classic at the same HP: the grid bots play far worse than real players.
- Owner decision 2026-10-24, asked after this round: "Full HP again". Masters facing 3-4 heroes go back to their full SRD hit points; solo and duo keep the small-party scaling.
- XP: a parley or clear pays a milestone far above a fight (+800 each for a ghast parley at tier 3, +150 and +600 per region, arrivals +50 to +400; fights +50 to +175).
- Gold: side quests pay 60-150 gp each, fight loot 1-21 gp, and nothing in the shops is worth buying; 79-234 gp sat unused per hero at the end.
- Darkness gives disadvantage to most attacks in lair fights, so "trivial" and "easy" fights drag on (quests: death dog 39 HP, 4 rounds).

## Round 5 totals
- Spend: 657 calls (logs/llm.jsonl lines 4476-5132), 2.68M prompt and 0.12M completion tokens: 71% of round 4 (931).
- Guard: 405 narrations, 96 rewritten once (23.7%), 13 template (3.2%), 15 mixed (3.7%).

| Round | Narrations | Rewritten once | Template | Mixed |
|---|---|---|---|---|
| 2 | 854 | 179 (21.0%) | 21 (2.5%) | 22 (2.6%) |
| 3 | 472 | 113 (23.9%) | 12 (2.5%) | 20 (4.2%) |
| 4 | 544 | 108 (19.9%) | 7 (1.3%) | 15 (2.8%) |
| 5 | 405 | 96 (23.7%) | 13 (3.2%) | 15 (3.7%) |

## By family
- Typed actions: X1-X8.
- Quests: X9, X10.
- Storyteller: X11-X16.
- Harness: X17.

## Fix plan (M32 Round 5)
- **M32.1a H typed actions:** X1-X8.
- **M32.1b H quests and storyteller:** X9-X16.
- **M32.1c M masters at full HP** (owner 2026-10-24 "Full HP again").
- **M32.1d M harness and rewards:** X17, and why a parley pays more than the same fight.
- Then the FULL gate and the commit `M32: Round 5`. A round 6 needs a fresh owner OK.
