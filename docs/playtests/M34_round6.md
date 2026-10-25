# M34 round 6: verifying M32 and M33 on the live storyteller

Round 6 (2026-10-24/25) ran after M32 (round-5 fixes X1-X17, masters at full SRD HP) and M33 (the 10 ultrareview
fixes). The owner approved it on 2026-10-24 ("Let's run round 6"). The runs had the same shape as round 5:
- typed everything, acts 1-2 (Sonnet), `r6-typed`, seed 2, fighter/rogue/wizard/cleric;
- quest audit, acts 1-2 (Haiku), `r6-quests`, seed 3, classic;
- full campaign to the ending (Sonnet), `r6-full`, seed 1, classic.

Saves are in saves/playtests/r6-*/saves (gitignored). The main session checked each claim against its save before
listing it here; the event numbers below are the checked ones (the quest run's report numbers ran about 2 high).
Findings are numbered Y1.. (rounds 1-5 used G, R, T, V and X).

## The runs
| Run | How far | Commands | Party at the end | Guard (narrations / rewritten once) |
|---|---|---|---|---|
| r6-typed (c-20261024-191446-0002) | acts 1-2, stopped at the act-3 tower | about 217 of 220 | all alive, level 3, 31-67 gp | 140 / 33 (23.6%) |
| r6-quests (c-20261024-191446-0003) | acts 1-2, stopped at the act-3 border | 161 of 180 | all alive, level 3, 184-233 gp | 104 / 17 (16.3%) |
| r6-full (c-20261024-191446-0001) | full campaign, ending reached (1821) | 253 of 320 | all alive, level 5 (Tamsin died once, Revivify), 50-249 gp | 170 / 36 (21.2%) |

r6-typed and r6-full played the built-in sample campaign "The Drowned Beacon": campaign generation fell back (Y20).

## What the fixes did (verified in the saves)
| Fix | Verdict | Events |
|---|---|---|
| X1 weapon lines attack | Verified for named weapons and weapon kinds ("drive my longsword into the swarm", "put an arrow in the kobold's chest"). A pronoun target still fails (Y11). | typed 161 (fail), 405-407 |
| X2 named spell is a cast | Verified: "I hit the swarm with a Guiding Bolt", "hit the crocodile with Magic Missile", "blast the armor with a Scorching Ray" all cast and spent the slot. An unnamed spell ("a bolt of fire") is still a creative action (Y11). | typed 124, 975-984, 1252 |
| X3 attack at a waiting offer | Half: a typed arrow starts the fight and plays on the archer's turn with no free blow. A typed spell is cast at the scene and wasted (Y9); a melee line at a foe out of reach is swapped or dropped (Y10). | typed 107-116, 378-380, 435-437, 968 |
| X4 peace line never starts a fight | Verified: confirm card, cancel keeps the offer, confirm rolls; a success gives no fight. | typed 103-105, 752-756 |
| X5 undead or mindless surrender | Verified for a construct ("a made thing knows no fear", no roll). Undead not reached. | typed 941-942 |
| X6 compound and counted lines | Half: "sheathe my sword and sling my shield" does both and a counted hand-over gives the count; "draw my sword and strap the shield back on", "picks up X and Y" and "picks up the three lumps" drop parts (Y12). | typed 34-36, 50-53; full 1413; quests 297 |
| X7 route item to a master while its offer waits | Verified twice: the step closes, the offer reads "parley sure to hold", the parley settles it. | full 535-549; quests 1095-1109 |
| X8 impossible lines in other words | Verified: "lift the whole quay", "lift the whole bridge" give action_impossible, no dice. | typed 55-56, 816-817 |
| X9 favour learn steps | Not reached (no learn step came up). | - |
| X10 errands only through the favour tool | Verified: every errand had a quest behind it; no coin promised in asks. | quests 568, 782 |
| X11 coin told as paid with no gold | Not fixed: "I slip 6 gold over to Brienne" told as paid, no gold moved (Y18). | typed 696-697 |
| X12 foe actions in a hero's turn | Not fixed: still frequent (Y16). | typed 410; full 127-138; quests 132 |
| X13 gift told refused against attitude | Verified: the Vesper gift was not told as refused. | quests 1095-1108 |
| X14 stale foes from an earlier scene | One new form: an invented skeleton carried across three narrations (Y17). | quests 596, 610, 615 |
| X15 finale filler, epilogue start place | Verified: no filler at the end; the epilogue begins at Gullmere Quay. | full 1820-1821 |
| X16 found told as taken | Partly: the guard flagged it 3 times (found_taken) but it still slipped through (Y18). | quests 296, 616 |
| X17 harness | `act` and `do` now wait; `do attack` takes the best hit chance; `look` shows gear and pack. New: `move` returns after the first hop (H1). | full 509-520 |
| M33 #1 Light vs "light crossbow" | Not reached (no hero knew Light); "my light crossbow" attacked. | typed 167 |
| M33 #2 counted give | Verified: "I give two torches to Elowen" gave 2. | typed 50-53 |
| M33 #3 courtesy, scene and negated lines at an offer | Verified: "I bow politely to the rats" and "We won't attack you" left the offer waiting. | typed 103-105 |
| M33 #4 walk stops at a quest ask | Verified: walks stopped at Tollgate (Orrick) and Moonshade (Mirelle), the accept card answerable. | quests 567-577, 782-787; typed 253 |
| M33 #5 check-worthy movement told | Verified: "scramble up the drainpipe ... and search" rolled Athletics and was told honestly. | typed 61-62 |
| M33 #7 held offer-strike line | Verified: queued lines play on the hero's turn. The out-of-reach melee case is Y10. | typed 114-116, 435 |
| M33 #6, #8, #9 guard terms, coin_ok, offer master | No false flags or misses seen; not directly testable in play. | - |
| M33 #10 TTS executor | Not reached (playtests run without TTS). | - |

## Findings
| # | Finding | Events | Family | Status |
|---|---|---|---|---|
| Y1 | **Two side quests finishing on the same step lose the first payout.** `rules.quest_progress.quest_progress_events` builds every active side quest's completion from the same state; `rules.rewards.payout_events` writes GoldChanged(gold=old+share) and XpGained(xp=old+amount) from that snapshot, and the reducer sets the absolute value, so the second payout overwrites the first: -60 gold and -150 XP each (79 to 44 gp, 668 to 568 XP). A scan of every save for "absolute value != running total + delta" finds 428 mismatches in 66 event logs: r6-typed and 65 balance simulations (M31d to M32c), all losses. | typed 664-685 | rules | open |
| Y2 | Guiding Bolt's "guided" gives advantage to every attack on the target until it ends (a dagger and a longsword both rolled with it); SRD 5.1: the next attack roll only. | typed 1260, dagger and longsword rolls before 1293 | rules | open |
| Y3 | A concentration spell whose only effect ends leaves the caster concentrating (Guidance used up at 313, no concentration_ended), so later hits roll needless Constitution saves. | typed 262-263, 313, 405 | rules | open |
| Y4 | A long rest is taken with a master's encounter offer waiting in the room; the master "has not moved". | full 519, 526-534 | rules | fixed in M35.2 |
| Y5 | Channel Divinity: Preserve Life does nothing: its feature row is "unsupported" (since M3.4). 14 of the 107 class features in data/bg3/features.json are unsupported, among them Uncanny Dodge, Sculpt Spells, Fighting Style: Protection, Eldritch Invocations, Pact Boon and both Hunter's Prey picks. | quests 283 | rules (data) | open |
| Y6 | A favour whose last step is "Win the fight at The Wailing Keep" can never close once the master there is settled peacefully; a challenge to the settled master gets narration only. | quests 782, 1092-1112 | quests | fixed in M35.2 |
| Y7 | **Quest steps do not match the quest text.** Steps can only be visit, clear and meet: "Recover the warden's signet" and "Recover the harbour ledger" are a clear step plus meet-the-giver, a clear step is credited at acceptance from a fight won before the quest existed (Toll for the Silence paid 50 XP and 25 gp at acceptance), the giver hands over the "lost" item as the reward, and the favour "see the beacon relit" closes on a visit plus a meeting. | full 857-866, 1168-1171, 333; quests 568-581; full 1529-1811 | quests | open |
| Y8 | **Better shop stock delivers less than the owner's call** (M31.2c). A general store's premium picks come only from its own categories and scrolls, and both later shops in the full run were general stores: act 2 Poison 100 and Scroll of Scorching Ray 150, act 3 Scroll of Blur, Scorching Ray and Fireball. No potion above Potion of Healing and no armour upgrade was for sale; about 670 gp sat unspent. The manual says every tier 2-3 shop keeps greater potions and heavy armour. | full 595, 1205, 1252 | quests (economy) | open |
| Y9 | A hostile spell typed at a waiting offer is cast at the scene: the slot is spent, "it strikes no one", and the offer keeps waiting. | typed 378-380 | typed actions | fixed in M35.2 |
| Y10 | A line naming a melee weapon at a foe out of reach is silently swapped to the ranged weapon ("drive my longsword into the nearest kobold" became a crossbow shot) or plays with no result; "run at the gnoll and strike it" refuses the move, then a creative Athletics check spends the action with 30 ft unused. | typed 435-437, 968, 860-863 | typed actions | open |
| Y11 | Phrasings that miss their route: "I put an arrow in its chest" (pronoun, one foe) became a Dexterity check; "flings a bolt of fire at the swarm" became a creative action dealing 3 fire damage; "raise my holy symbol and command the undead to turn away" became a creative Wisdom save with no Turn Undead and no Channel Divinity spent. | typed 161-164, 181-184, 1165-1168 | typed actions | open |
| Y12 | Compound and counted lines still drop parts: "draw my sword again and strap the shield back on" did nothing while told done; "picks up the Salt-stained letter and the Ember-stone" took only the stone and said nothing of the letter; "picks up the three lumps" took one. | typed 37-42; full 1413-1416; quests 297-301 | typed actions | open |
| Y13 | "gives Widow Cabrelle a block of incense" was refused give_not_carried with Block of incense x5 in the pack; the retry produced no engine event and the story said she declined. | quests 563-565 | typed actions | open |
| Y14 | Taking items from a fallen hero's pack has no path; the story says the pack holds no scroll or potion while the state lists them. | full 1540-1541 | typed actions | open |
| Y15 | "We leave the vestry and head on to Lamplighters' Rest" walked the wrong way (vestry to the Quay, "closed for now") although the region had just resolved and the vestry borders the Rest; a travel line to the place the party already stands in is told as a blocked way. | typed 761-771, 751, 798 | typed actions | open |
| Y16 | **Foe actions and flight told with no event**: kobolds "surge forward with hooked knives, one slicing toward Brienne" while they slung stones from range; a rat told bolting under the boards while it stays in the fight; a skeleton's 5-damage hit told as "the shot travels wide of any of you". | typed 392-410; full 127-138; quests 126-132 | storyteller | open |
| Y17 | Invented things: a skeleton at the act-1 master's shoulder (the offer had only her) carried into two more narrations and into a check reason; a model-made cache yielded a Pouch while the story said the smugglers' tide-orders (a quest item placed elsewhere) were in her hands. | quests 595-596, 610, 615; typed 344-351 | storyteller | open |
| Y18 | State told that did not happen: a sword drawn and a shield strapped on with no equipment change, "there is no longsword among the party's gear" (it was in the pack), six gold told as paid with no gold moved, searched items told as already in the pouch or hand. | typed 38-42, 696-697; quests 296, 616 | storyteller | open |
| Y19 | Results told flatly or not at all: template event lines as the story ("The party grows more experienced." x4; "Death Dog unleashes Multiattack."); a 300 XP / 150 gp favour reward never told; the Healing Word line labels the 1d4+Wisdom total "die" and the capped Disciple of Life extra "bonus" (aidm/session/public_feed.py:175), so a d4 shows "die 6". | quests 633, 1051, 952-962, 101-102 | storyteller | open |
| Y20 | **Campaign generation fell back to the sample campaign on 2 of 3 runs** (the first fallbacks in 22 live runs). r6-typed: three malformed JSON replies inside one attempt, and `generate_campaign` falls back at once on a client failure instead of trying again. r6-full: three attempts, then a whole plan thrown away for one leftover problem ("'lizardfolk' is tier 1, the region is tier 2"). Fail soft worked: the table was told it plays a prepared adventure. | llm.jsonl 5133-5152; session.jsonl "campaign" lines | AI layer | open |

## Not bugs
- The main quest of each region is taken on without an accept card (quests 29, 638): by design, it is the act's story.
- `do attack` picked a crossbow or shortbow next to a foe (quests 355): the harness takes the best hit chance, and with Darkness already giving disadvantage, close combat adds nothing; the crossbow (+6 with Archery) beats the longsword (+4).
- A yield demand to beasts shows the parley confirm card (typed 102, 281): M32.1a's no-roll line is for undead and mindless foes; beasts can be scared off.
- The finale reply's "lantern room" (full 1820): the master's lair is The Dark Lantern Room (full 1800).
- Healing Word's numbers are right (1d4 + Wisdom, then Disciple of Life, capped at max HP); only the label is wrong (in Y19).
- An inn rest costs camp supplies (typed 732): inn rooms are not modelled. Typed "buy" opens the shop (typed 81): by design.
- The masters settled with no fight (quests acts 1-2, full act 1): the peaceful routes work as intended.

## Harness and low items
- H1: `move` to a far place returns after the first hop while the walk goes on (full 509-520); a `levelup` takes about 2 minutes per hero in the agent tool (full and typed); there is no Scribe command; "<hero> is now the host" prints on nearly every action.

## Balance
| Master | Run | HP | Word | Rounds | Acted | Heroes down |
|---|---|---|---|---|---|---|
| Gorran Hookhand | typed act 1 | - | easy | settled by parley and the tide-orders | - | - |
| Cantor Ashmere Voll (wight) | typed act 2 | 45 | hard | 3 (surprised in round 1) | twice | 0 |
| Gorran Hookhand (bandit) | full act 1 | 11 | easy | settled by the tide-orders and a sure parley | - | - |
| Cantor Ashmere Voll (wight) | full act 2 | 45 | hard | 2 (surprise) | once (1 hit, 3 damage) | 0 |
| Magister Orsolo Venk (gladiator) | full act 3 | 112 | hard | 2 | twice (Tamsin 26 to 1, Relentless Endurance) | 0 |
| Acolyte Nyra, Vesper the Echo-Thief | quests acts 1-2 | - | trivial, medium | settled by parley and gift | - | - |

- Live: 0 heroes down in 3 master fights at full SRD HP. A prepared party of four kills a "hard" master in 2-3 rounds (surprise, a crit, a 300 gp Fireball scroll).
- Danger words under-read single strong foes: a "trivial" cult fanatic killed the wizard outright with a critical Inflict Wounds (full 1470); "trivial" death dogs (39 HP) dropped the 20-HP wizard twice (quests).
- XP: milestones far outweigh fights (place visits and clears 50-800 each, region 150/600/2600, fights 12-175). Level 3 by command ~111-150 in acts 1-2; level 5 at the end. (Owner kept the milestone table.)
- Gold: quest payouts 25-150 gp each, fight loot 2-45 gp; 184-249 gp per hero at the end of the longer runs, with nothing above 50 gp worth buying except scrolls (Y8). Y1 means the M31 balance simulations under-counted gold and XP.
- Rest: a long rest costs 39-40 camp supplies; camp baskets (3 supplies for 1.5 gp) make it cheap once known.

## Round 6 totals
- Spend: 637 calls (logs/llm.jsonl lines 5133-5769), 2.65M prompt and 0.12M completion tokens: 97% of round 5 (657).
- Guard: 414 narrations, 86 rewritten once (20.8%), 12 template (2.9%), 12 mixed (2.9%).

| Round | Narrations | Rewritten once | Template | Mixed |
|---|---|---|---|---|
| 2 | 854 | 179 (21.0%) | 21 (2.5%) | 22 (2.6%) |
| 3 | 472 | 113 (23.9%) | 12 (2.5%) | 20 (4.2%) |
| 4 | 544 | 108 (19.9%) | 7 (1.3%) | 15 (2.8%) |
| 5 | 405 | 96 (23.7%) | 13 (3.2%) | 15 (3.7%) |
| 6 | 414 | 86 (20.8%) | 12 (2.9%) | 12 (2.9%) |

## By family
- Rules engine: Y1-Y5 (the first rules findings since round 3; Y1 is old code).
- Quests and economy: Y6-Y8.
- Typed actions: Y9-Y15.
- Storyteller: Y16-Y19.
- AI layer: Y20.
- Harness: H1.

## Next
The owner asked for round 6 and then an honest code-health assessment, and the project PAUSES after it: no fix
milestone starts until the owner decides which findings to take on.
