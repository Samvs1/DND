# M29 round 3: verifying the M29.7a-e fixes on the live storyteller (DRAFT)

Round 3 (2026-10-23), after M29.7a-e and the harness cone fix (60e1daa), on live DeepSeek. The owner approved
2-3 runs at about round-2 cost or less. The runs:
- full campaign, classic four (Sonnet), `r3-full-classic`;
- item tricks, acts 1-2 (Sonnet), `r3-items`;
- all casters, acts 1-2 (Haiku), `r3-casters`.

Saves are in saves/playtests/r3-*/saves (gitignored). Reports came back as text. The main session checked each
claim against its save before listing it here. Findings are numbered T1.. (round 1 used G, round 2 used R).

## r3-casters (Haiku, acts 1-2, save c-20261023-204914-0001)
- **How far:** 141 of 300 commands. Act 1 was resolved by alliance; the act-2 master, Castellan Vane, was
  defeated. All four heroes alive at level 4. Stopped at the act-3 border.
- **Guard:** 115 narrations; 17 rewritten once (14.8%; round-2 casters 14.3%), 4 template (3.5%), 2 mixed.

### What the fixes did
| Fix | Verdict | Events |
|---|---|---|
| R26 aimed cones | Verified. Burning Hands at a 15-ft neighbour caught only the two zombies there (370-375). A 25-ft zone was refused with no slot spent (per the report; the refusal is a client error, so it is not in the save). Sleep on the casters' own zone took the allies there in hit-point order (Tamsin 8, Rook 10), as SRD Sleep does; the pool ran out before anyone else. | 370-375, 99 |
| R3 close combat | Verified: `adv_why` "close combat" (disadvantage) on Guiding Bolt, Eldritch Blast and Fire Bolt with a foe in the zone. | 113, 207, 402, 411, 435 |
| R27 slots at level-up | Verified. Three level-ups each kept spent slots spent and added the new ones. Arcane Recovery gave slots back. A long rest refilled all. | 238-245, 652-665, 1066-1073 |
| R6 lot prices | Verified. "Camp Ration 2 for 1 gp"; 2 rations cost 1 gp, 10 cost 5 gp. | 43, 508 |
| R20 befriended | Not reached: no hero had Animal Friendship. | - |
| H7-H14 harness | Used throughout: slots, supplies, close-combat reason and trade notes all showed. | - |

### Findings
| # | Finding | Events | Family | Status |
|---|---|---|---|---|
| T1 | Sleep put an undead zombie to sleep. SRD 5.1: "Undead and creatures immune to being charmed aren't affected by this spell." The spell DSL has an allow-list (`targeting.creature_types`) but no way to leave a type out. | 353-355 | rules (data) | open |
| T2 | A "clear" step names the plan's theme monsters ("Win the fight at Weeping Bastion (wight, ghast)"), while the place fielded a bugbear stand-in: no theme monster fit the party's budget (M29.6 `_stand_ins`). The M29.7c R1 fix wrote the text from `encounter_themes` at plan time, so there are still two sources for "who is there". The same happened at Saltmere Cellars ("gelatinous cube, ghast" vs a death dog). | 4, 821, 938 | campaign plan (R1 again) | open |
| T3 | Step text written by the model promises a deed the step kind does not check. The visit step "Walk the Fogward Gallows road at dusk and mark it with a lit brand" was met by an earlier visit, with no brand lit (the party's brand attempt failed at 722). "Find Sister Ilka keeping her own watch at the gallows" was met at Weeping Bastion, where she actually was. Both steps closed together on arrival at the Bastion, and the quest paid out. | 721-722, 743-747 | campaign plan (R1 family) | open |
| T4 | Invented foe attacks. "The wolf ... springs at Tamsin, jaws snapping shut a hand's breadth from her wrist" on a beat where the wolf had no turn. "Lunges. Its teeth close on her staff" when it only dashed (199-201). The zombies "both lunge" with no attack (409); "both swing at once" when only one slam resolved (433). The M29.7b blow check catches invented hits and kills, not invented attempts and near misses. | 187, 204, 409, 433 | storyteller honesty (R19 again) | open |
| T5 | "Rook sets the dripping Drowned Lockbox on the ferry boards in front of Old Renn" was not read as a hand-over: the keepsake stayed with Rook. The narration then told the delivery as done ("you have done it whole"). "Rook hands the Drowned Lockbox over" worked at 292-294. | 288-294 | typed intent + honesty | open, belongs to M30.0b |
| T6 | Travelling from one spoke straight to another (Fogward Gallows to Weeping Bastion, no road between them) fell through to the model. It invented a reason ("the way ... stays folded in mist"), which was recorded as a fact. `precheck._travel` returns None for a known place that is not an exit, where it could give the map's reason: back through the gatehouse. | 723-724, 731 | typed intent + honesty | open |
| T7 | "Brienne keeps a warm light going over the water" (the Light cantrip, by typing) stayed prose: no spell event, but the narration kept "Brienne's light". | 287 | typed intent (low) | open |

**Not bugs:**
- Arcane Recovery "spent with full slots" (B4): slot 1 was 3/4 after a cast at 682, so the recovery restored it to 4/4 (717-718).
- The bell "stilling" before the hand-over (B6): the narration says "no chime, no change". The line is Tessa's spoken hope.
- Disadvantage on Perception in darkness for darkvision heroes: SRD 5.1 treats darkness as dim light for darkvision, and dim light means disadvantage on sight-based Perception. The intro line about heroes without darkvision is generic, though.
- "I wrote 'Tamsin asks' and Brienne rolled": the hero acting is the `--as` hero by design (one hero per player).

**Harness, low:**
- A cone's zone list still shows zones it cannot reach (the refusal is clear).
- `levelup` takes the ability score increase, pact boon and subclass defaults without saying so.
- Healing Word prints the die and then the total healed.

**Balance:**
- Every fight was easy for four casters at levels 2-4. Only the act-2 master (rated "hard") hurt anyone: 15 damage in two hits.
- Level 4 by the end of act 2, and about 195 gold per hero, are both inside the M29.6b targets (act-3 master at level 4-5; act-2 gold 100-900). The persona found both generous.
- The sims put the casters' balanced clean-win rate at 0.87, inside its 0.75-0.90 target.
- Gold has little to buy beyond healing potions and supplies: the known missing gold sink.

## r3-items (Sonnet, acts 1-2, save c-20261023-204915-0001)
- **How far:** about 255 of 300 commands. Acts 1 and 2 cleared; all four heroes alive at level 3. Stopped before
  the act-3 border.
- **Guard:** 171 narrations; 41 rewritten once (24.0%), 4 template, 8 mixed.

### What the fixes did
| Fix | Verdict | Events |
|---|---|---|
| R7 R8 hand-overs between heroes | Verified: a torch, 10 gold, a potion and a worn shield (AC 18 -> 16 and back). Giving 500 gold the hero lacks was refused plainly. | 49, 54, 219, 1398-1406, 1418-1420 |
| R18 show is not give | Verified twice. Taking the note back from Anwen with a roll worked. | 77-90, 499-509 |
| R9 typed equip | Verified: "strap on the shield", "put on the scale mail", "wield the rapier", "put on my leather armour" (1424-1426, AC 15). | 105-110, 1422-1426 |
| R17 light phrases | Verified: torch, candle and hooded lantern; "already lit"; douse; pinch out; compound "light my torch, then head to ..." with a lit and an unlit torch. | 119-156, 1067, 1430-1437 |
| R22 typed weapon attacks | Mostly verified (shortbow, longbow, longsword, light crossbow, shortsword name that weapon); two misses, see T9. | 271-335, 600, 885 |
| R3 close combat | Verified, including no disadvantage after stepping out. | 352, 414, 463, 921 |
| R23 quest item to the giver | Verified: the ember to Beska paid out. | 205 |
| R24 locks on progress gates | Verified: a plain reason, no roll. | 177, 1038 |
| R6 shop wording, lots, cap | Verified: "2 for 1 gp", 4 for 2 gp, 3 for 2 gp, "worth 1 gp fetches nothing", "1 to 10 at a time". | 96-102, 225, 756 |
| R4 typed parley while an offer waits | Verified: answered as parley (Persuasion 17 vs 10). | 166 |

### Findings
| # | Finding | Events | Family | Status |
|---|---|---|---|---|
| T8 | **A typed attack starts the fight but leaves the waiting offer open; answering it later spawns a fresh copy of the dead foe.** "I draw my longsword and charge the ice mephit" started enc-818 while offer-804 stayed pending through the whole fight. After the victory, `answer escape` failed into a second fight against `ice-mephit-2` (21/21 HP), which paid another 25 XP each, 3 gp each and a Restorative Draught. This is an exploit. The M29.7c R15 path starts a fight without consuming the node's offer. | 804, 817-819, 930, 963-969, 1018-1023 | fight start (R15 follow-up) | open, high |
| T9 | Typed attacks that fall through to the model in a fight: "I stab the ice mephit with my rapier" (the rapier was stowed after `equip dagger`) became a Dex check that spent the action, and "I attack ... with my rapier" became a free 1d6 "Creative action". "I bring my mace down on the ice mephit" became a Str check. Under SRD rules, drawing a stowed weapon is part of the attack (free object interaction), so the attack was possible. | 875-878, 902-905, 909-912 | typed intent (R22 again) | open, belongs to M30.0b |
| T10 | A gift that is taken in state but refused in the story: Tamsin gives Anwen the route note, the keepsake moves to Anwen, and the narration says she "pushes it back across the table". | 499-501 | honesty | open |
| T11 | Accepting a quest is told as finishing it: "Beska takes your sun-ember to the faithless flame" (twice), but nobody held an ember. It was found later at the chapel (170-175). | 32-34 | honesty (invented hand-over) | open |
| T12 | A successful surrender demand has no engine effect. Intimidation 19 vs 15 ("they are beaten, surrender"), and the story tells weapons dropped, but the foes stay hostile. Burning oil kills them, including the cultist the party chose to spare. Demanding surrender is a possible action, so a success has to change the fight. | 663-664, 687-688 | rules gap (never refuse) | open, needs a design line |
| T13 | A quest the engine cannot finish: "The Archivist Is Missing" has the learn step "Read the spore-ink note the archivist left behind" (tag `blackpine`). Holding the note, giving it to Anwen and asking her about it record no learned fact with that tag, so the quest failed at the act border. | 744-749, 783 | campaign plan (T3 family) | open |
| T2+ | More step texts naming monsters the place never fielded: "Win the fight at The Singing Crevasse (ogre, grick)" for a dire wolf. "Win the fight at Wrenfall Chapel (cultist, skeleton)" was met by a parley, so "win the fight" is wrong too. | 1140, 166 | campaign plan | see T2 |
| T4+ | More invented foe actions: "a blade opens Brienne's forearm ... The tiefling's mace answers", while every foe was surprised and Rook had not acted (602). A mephit's cold "biting into the three of you" with no roll (881). The mephit "splitting into three icy shards" (908). | 602, 881, 908 | honesty | see T4 |

**Not bugs or not reproduced:**
- "I put on my leather armour" (B5) did work: AC 15 at 1426. The AC drop at 1427 came from a harness `unequip`; `equip` can never remove armour.
- The failed parley at the Hollow Hearth still gave the party surprise because an earlier route step had earned `boss_surprised` (`encounter_offer.offer_fight_events`). That is by design, though odd right after a conversation. Low.

**Low, or to check:**
- Equipping worn armour twice says "Chain mail is already in hand" (the `ALREADY_EQUIPPED` text).
- A rogue in chain mail showed no non-proficiency effect. SRD 5.1 gives disadvantage on Str and Dex rolls and no spellcasting; to check.
- The act-2 peddler sold no weapon or armour. M29.6b requires a weapons, armour and potions trader per region; to check.
- `move` to a place that is not an exit gives the generic "The moment passes" line (764, 1154); T6 family.
- The place line still says "(dark)" with a lit torch.
- Damage lines do not say "vulnerable" or "resisted".
- Ossuary zones carry outdoor names ("Windswept Field").

**Balance:**
- Every fight was trivial or easy. The act-2 master (a wight, 26 HP, labelled "medium") died in 2 rounds, dealing 6 damage.
- The party ended with 217 gold unspent; there is nothing to upgrade to.

## r3-full-classic (Sonnet, full campaign, save c-20261023-204914-0001 under saves/playtests/r3-full-classic)
- **How far:** about 255 of 450 commands to the epilogue ("The Unmade Crown"). 10 fights, 3 long rests, all four
  heroes level 5, nobody died. Masters: Voss and Ulva by peace, Sera Vask fought.
- **Guard:** 186 narrations; 55 rewritten once (29.6%), 4 template, 10 mixed. The new M29.7b kind `phantom_blow`
  fired 4 times.

### What the fixes did
| Fix | Verdict | Events |
|---|---|---|
| R14 sure parley | Half. The arrival notice says "a parley now would surely hold", and `answer parley` held with no roll (Voss). But a hand-over step resolved Ulva's offer by itself (T15). The harness offer line does not print the `sure` flag; the phone does (M29.7e screenshot). | 489-511, 1074 |
| H13 the ending | Verified: the ending text prints after the finale. | 1735 |
| R3, cover, high ground | Verified in the roll lines. | - |
| Typed heals, potions, long rest, give | Verified ("give the Broken Royal Seal to Legion-Captain Ulva" worked). | 1074-1079 |
| Masters at the planned level | Verified: level 2 / 3 / 4, and level 5 for the act-3 master. | 243, 526, 1080, 1429 |

### Findings
| # | Finding | Events | Family | Status |
|---|---|---|---|---|
| T14 | **Quests pay out for deeds nobody did.** Accepting "The Drowned Husband's Name" closed all three "Speak the name 'Corin Skell' at ..." steps at once ("the party has been to X") and paid 50 XP, 25 gp each and Brass Tears. "Bring Piper to her mother at Cinderstep Gate" closed on arrival at the Crown Forge for two quests (+1600 XP and +800 gp each), with no Piper anywhere in the state. "Read the muster roll" closed on arrival, while the real reading failed later. These are visit steps whose model-written text names a deed, credited by earlier visits. | 397-403, 855, 1649-1650 | campaign plan (T3 family) | open, high |
| T15 | A hand-over step that finishes a peace route resolves the master's offer by itself: Ulva's offer resolved as "parley (success)" in the same reply as the seal, with +600 XP twice and +300 gp each, and no answer from the player. M29.7c R14 fixed this for arrival only. | 1074-1078 | campaign plan (R14 again) | open |
| T16 | A question to an NPC while a fight offer waits is read as a parley with the foes: "Brienne asks Dreda Flint who she is ..." resolved offer-1417 as a failed parley (Persuasion 11 vs 15), and the ogre fight started. M29.7a R4 is too broad: it should take only words aimed at the foes. | 1440-1442 | typed intent (R4 overreach) | open |
| T17 | Paying an NPC is impossible. "Brienne pays Rutter the Gap for a crossing" was told as paid ("Rutter takes your silver") with no gold change. "Brienne hands Rutter the Gap 1 gold piece" was refused ("You do not carry that"). A favour that needs payment cannot progress. Gold can go to heroes (M29.7a R8), not to NPCs. | 44-46, 466-468 | engine gap (never refuse) + honesty | open |
| T18 | Relentless Endurance never fires: the feature hook has been `unsupported` since M3 ("needs a damage choke point hook"), but the sheet shows the resource at 1/1. Tamsin dropped to 0 twice with leftover damage far under her max HP. 15 features carry `unsupported` hooks; this is the most visible one. | 217, 1540 | rules | open |
| T19 | Acid Arrow does nothing on a miss. SRD 5.1 gives half the initial damage on a miss, and 2d4 acid at the end of the target's next turn on a hit. The data has `on_hit` only, and the DSL has no miss branch. | 886 | rules (data) | open |
| T20 | Level-up re-picks a wizard's prepared spells. Tamsin's prepared list went 4 / 5 / 6 / 8 at levels 2-5, and at level 3 it dropped thunderwave while adding two new spells. SRD: prepared count = Int modifier + wizard level, from the spellbook. The count looks one short; to verify against her Int at each level. | 262, 532, 1084, 1438 | rules | open |
| T21 | The ending says what did not happen. Voss and Ulva "joined the party" (they became allies; the party stayed four). "Cunning paved the way first: Drown the Furnace" names a route never taken. The three main quests are missing from "Completed quests". | 1735 | honesty (epilogue facts) | open |
| T2+ | "Win the fight at Bogmouth Shrine (cultist, ghoul)": no ghoul was fielded. | 144 | campaign plan | see T2 |
| T4+ | More: a fled cultist told as killed (97); the berserker "slumping into the cinders" at 6/67 (1195); animated armour and a death dog "strike" with no roll (633, 882); Sacred Flame saved against but told as scorching (119, 359, 1380). | various | honesty | see T4 |

**Harness, low:**
- The offer line lacks "(sure to hold)", though the client message carries `sure`.
- Racial Darkness (Infernal Legacy) is listed as "no slot left" but casts from its own resource.
- `answer finale <id>` fails; only `answer <id> confirm` works.
- `do end` often prints no Options.
- Heal rolls show the die and not the domain bonus.

**Low:**
- Items costing between 1 and 2 gp show the price rounded (Hearty Meal Basket shows 2 gp; the manual says 1.5).
- NPC dialogue is evasive on where to go ("ask the fen").

**Balance:**
- Fights were mostly easy. Three spikes all hit the AC 11 wizard (to 0 against the "easy" sahuagin and ogre, to 2 against the "trivial" ogre zombie).
- The act-3 master (a mage, 31 HP, "hard") died in 2 rounds without hitting anyone.
- Gold reached about 1300 per hero. That is inside the 200-1800 act-3 target, but almost all of it came from quest payouts, T14's included: +800 gp each for one unearned step. Nothing in three shops was worth buying beyond potions, so the missing gold sink shows again.

## Round 3 totals
- **Spend:** 746 DeepSeek calls (logs/llm.jsonl lines 2789-3534), 3.21M prompt + 0.13M completion tokens. That is about 56%
  of round 2 (1324 calls, 5.57M + 0.21M), so roughly 0.2-1.0 USD.
- **Outcome:** the full run reached the epilogue; both acts-1-2 runs reached the act-3 border. No defeat.

| Guard | Round 2 (5 runs) | Round 3 (3 runs) |
|---|---|---|
| narrations | 854 | 472 |
| rewritten once | 179 (21.0%) | 113 (23.9%) |
| template fallback | 21 (2.5%) | 12 (2.5%) |
| mixed | 22 (2.6%) | 20 (4.2%) |

The guard now catches more (the new `phantom_blow` kind; more rewrites), the fallback rate held at 2.5%, and false
claims still pass in the shapes T4, T10, T11 and T21: invented attempts and near misses, a made hand-over told as
refused, a quest told as done at acceptance, and allies told as companions.

## By family
| Family | Round 3 findings | Root cause |
|---|---|---|
| Campaign plan | T2, T3, T13, T14, T15 | The model writes step text for kinds the engine checks by place, person or item. Earlier visits then credit deeds, and themes name foes the budget never fields. |
| Storyteller honesty | T4, T10, T11, T21 | The blow check covers hits and kills but not attempts. Hand-overs and quest outcomes are not checked in every direction. Epilogue facts word an alliance as "joined". |
| Typed intent | T5, T7, T9, T16 | Phrase coverage, and the order of the parsers (M30.0b). |
| Engine and rules | T1, T8, T12, T17, T18, T19, T20 | Data gaps (a type exclusion, a miss branch), a fight start that leaves the offer, no surrender or NPC payment, an `unsupported` hook shown to players. |

## Fix plan (M29.9, before M30.0b)
- **M29.9a H, engine and rules:**
  - T8: any fight start consumes the node's offer (the exploit, first);
  - T15: no step kind resolves a master's offer;
  - T17: paying an NPC moves gold (event and typed path);
  - T1: `exclude_creature_types` plus charm immunity for Sleep;
  - T19: `on_miss` in the attack DSL for Acid Arrow;
  - T18: a drop-to-1 hook at the damage choke point;
  - T20: the prepared count at level-up;
  - T12: a `surrendered` condition from a successful demand in a fight. It ends the fight like befriended foes do; a DECISIONS line settles XP and loot.
- **M29.9b H, campaign plan:**
  - T2: clear steps never name foes before the offer;
  - T3, T14: the engine writes the text of every step kind it checks, with the flavour kept in the objective, and visit steps count only arrivals while the quest is active;
  - T13: holding or reading a keepsake records its learn fact;
  - a step whose person or item does not exist in the world is repaired at plan time (T14 Piper);
  - T21: epilogue facts say "sided with", not "joined", name only routes taken and list the main quests.
- **M29.9c H, storyteller honesty:**
  - T4: in a fight beat, an attack verb on a foe needs that foe's attack this beat; a saved spell is not a hit; a fled foe is not dead;
  - T10, T11: hand-over and quest-outcome checks in both directions.
- **M29.9d M, harness:** "(sure to hold)" in the offer line, resource-cast spells in Options, `answer finale <id>`, reachable zones marked for cones.
- **Typed intent T5, T7, T9 and T16:** these go into M30.0b (one intent router). T16 is small and can land in M29.9a if the router is not ready.
