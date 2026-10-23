# M29 round 2: agent playtests on the live storyteller (DRAFT)

Round 2 (2026-10-23), after M29.5a-c and M29.6b, live DeepSeek. Personas: #4 rogue-heavy (Sonnet, full campaign),
full playthrough classic four (Sonnet), #5 solo careful (Haiku, acts 1-2), #7 economy duo (Haiku, acts 1-2),
#8 all casters (Haiku, acts 1-2). Saves: saves/playtests/r2-*/saves (gitignored). Reports came back as text; the main
session checked each bug against its save before listing it here.
Spend: 1324 DeepSeek calls (logs/llm.jsonl lines 1465-2788), 5.57M prompt + 0.21M completion tokens (roughly
0.3-1.8 USD depending on cache hits).
Outcome: the two full-campaign runs (#4, full classic) reached the epilogue; #5, #7 and #8 reached the act-3 border
as planned. No defeat in any run. Masters met at level 2 / 3 / 4-5 in every run (the M29.6b targets).

## Harness problems (scripts/agent only)
- H7 `trade` reads the `shop_stock` message right after the turn settles and does not wait for it; on the live
  storyteller the stock arrives late, so the first trade after arriving says "The shop did not open (no vote?)" although
  the engine opened the shop (p5 events 327-328, 713). `open_stock` must wait for the stock message. Fixed in M29.7e (61f85c9): `trade` / `open_stock` wait (bounded, 10 s fake, 90 s live) for the `shop_stock` message after the votes; `test_m29_h7_trade_waits_for_the_late_shop_stock`.
- H8 `do attack` without an option picks the attack with the best hit chance only (`Link.best_option`), so a fighter
  with Archery always fires the crossbow, even with the foe in its zone (p5 549-640). Weigh expected damage. Fixed in M29.7e (61f85c9): `Link.best_option` picks by hit chance x average damage (+ crit share, bonus dice), damage from the sheet's attack lines (`scripts/agent/damage.py`); `test_m29_h8_best_option_weighs_expected_damage`.
- H9 Display: every turn line shows `attacks_left=0` at the start of a turn; Action Surge is listed as "(spent or
  unavailable)" until the action is spent; the region milestone XP line is unlabelled; the first fight line says
  "turn of None". Fixed in M29.7e (61f85c9): no `attacks_left=0` (shown only when more attacks wait), Action Surge listed until spent, XP lines labelled, no "turn of None"; `test_m29_h9_display_turn_start_surge_xp_and_first_fight_line`.
- H10 `trade list` shows the pack only, never keepsakes (p7's "vanished" clapper was held all along, p7 546); there
  is no `equip`/`unequip` command although the protocol has both. Fixed in M29.7e (61f85c9): `trade list` ends with the keepsakes marked not for sale, new `equip <item>` / `unequip <item>` commands over the existing messages; `test_m29_h10_keepsakes_and_equip_commands`.
- H11 `look` does not show which hero carries a lit light, zone cover, or why a roll had advantage or disadvantage
  (the events carry `adv_why`, e.g. "high ground", and `target_ac` 21 with three-quarters cover, p4 862-871);
  thrown oil and ball bearings print no zone or surface. The phone shows light and cover; the harness must too. Fixed in M29.7e (61f85c9): `look` shows the lit light per hero, zone cover, high ground, light and surfaces (oil, ball bearings), and the last roll with its `adv_why` (digest rolls too); `test_m29_h11_look_shows_light_cover_surfaces_and_the_roll_reason`.
- H12 `settle` still returns during the live model's silent gap now and then: p4's "ignored" fight act (1371) has
  its narration at 1372 (G4 again); full-run parley, surprise and typed attacks printed the state before the result
  (full 66 vs 69, 457-475, 2247). H7 hit the full run too (589, 752, 768). Fixed in M29.7e (61f85c9): `settle` also waits for the narration of the acted turn, bounded by a quiet period (grace 1.5 s fake, 15 s live); `test_m29_h12_settle_waits_for_the_narration_of_the_acted_turn`, `test_m29_h12_settle_ends_after_a_bounded_quiet_when_no_narration_comes`.
- H13 After the finale the tool prints only "THE CAMPAIGN IS COMPLETE"; the ending narration (full 2311) is not shown. Fixed in M29.7e (61f85c9): the epilogue text prints after "THE CAMPAIGN IS COMPLETE" (`Ending:`) and in the digest; `test_m29_h13_the_ending_narration_is_printed`.
- H14 `look` shows no spell slots, camp supplies, spell list out of a fight, or what a level-up taught; `trade list`
  shows the camp ration at 1 gp while it costs 0.5 gp (G28 rounding) and does not state the 10-per-trade cap.
  One driver answers every hero's vote, so votes never show (by harness design, not a game bug). Fixed in M29.7e (61f85c9): every view has `Camp supplies` and a `Heroes:` block (slots, spells out of a fight, resources); `levelup` prints what the level taught (before/after sheet); `trade list` shows the bulk price ("2 for 1 gp") and the per-trade cap; the help text says votes are answered by one driver by design; `test_m29_h14_slots_spells_level_up_prices_and_the_cap`.

## Game findings (each fix needs a `test_m29_<slug>`)
| id | what | where (run / event) | severity | status |
|---|---|---|---|---|
| R1 | A quest step's text does not match its node: the "clear Gallowroot Copse" step reads "Snuff the bone-pyre the acolytes are stoking" while the copse fields stirge/goblin; a "learn" step tagged ashmede completes from an earlier ashmede fact ("met by what the party has already done") | p5 2 (plan), 243-244; also 453, 498; p4 202, 451 (accepting a quest completed it), 732, 1224-1228, 1656 | medium: story coherence | fixed M29.7c 15674fa + 3210c4a: every clear step reads "Win the fight at <place> (<its foes>)" (plan repair + prompt line); a learn step needs what teaches it now (the place it names, a find or a secret there, a finished quest), never an old visit; a step met by earlier play names what met it (`rules/quest_reasons`); accepting with the work done stays legit and is now told why |
| R2 | Routed travel stops one node short (Mothfen Hollow, a quest ask), but the narration tells arrival at The False Hearth and records three facts placing the hero there | p5 682-691; p7 764, 898; full 672, 882 | medium: honest storyteller (place) | fixed M29.7b d407fc9: the narrator is told where the party stopped, one place short of the goal; the goal named without a distance word is flagged (SHORT_TRAVEL), in the summary and its facts too (`test_m29_travel_stopped_short_is_told_where_it_stopped`, `test_m29_travel_short_in_other_runs`); full 672 tells no place name, so only the fact covers it |
| R3 | A ranged weapon attack against a foe in the attacker's own zone has no disadvantage (SRD 5.1 "Ranged Attacks in Close Combat"; BG3 Threatened); the crossbow is always the better pick in melee | p5 549-640 | medium: rules gap | fixed M29.7d 2ccd441: a ranged weapon or spell attack (thrown too) has disadvantage while a foe who can see the attacker and can act shares its zone, monsters too, shown as "close combat" in adv_why and in the hit-chance preview (`rules.hit_chance.threatened`; `test_golden_ranged_attack_in_close_combat`, `test_m29_close_combat_needs_a_foe_that_can_see`, `test_m29_monsters_shoot_at_disadvantage_in_close_combat_too`, `test_m29_bot_prefers_melee_in_close_combat`) |
| R4 | A typed Persuasion check that passed (20 vs 20) while an encounter offer was pending did not count for the parley; the parley then rolled again and failed | p5 539, 547 | medium: confusing | fixed M29.7a f1eef45: typed talk / threaten / lie while an offer waits is the parley with that skill, one roll (`test_m29_typed_parley_rolls_once_for_the_offer`) |
| R5 | Narration names a weapon the attacker does not carry (sickle for a scimitar); G7's check only flags a different weapon the attacker carries | p5 75, 88 | low | open |
| R6 | Selling a 1 gp item (hammer, rope, incense) is refused as "not worth buying (shop_worthless)"; the line reads as "this is junk" rather than "worth under 1 gp to this trader" | p5 720-726; p7 55 | low: wording | fixed M29.7d 3709f73: the refusal says the rule ("a trader pays half an item's value in whole gold, so Hammer (worth 1 gp) fetches nothing"; phone: "anything worth under 2 gp fetches nothing"); stock lines carry the exact unit price and a "2 for 1 gp" note so the phone shows a lot's price as charged (10 rations 5 gp) (`test_m29_sale_refusal_says_the_true_rule`, `test_m29_sub_gold_prices_are_shown_as_charged`) |
| R7 | Typed "Brienne hands the Herbal Poultice to Elowen ... keep it" is read as using it on Elowen (full HP): no effect, poultice spent | p7 65-67 | high: item lost | fixed M29.7a 70d27f1: hand / give / pass to a hero with no drink word is a hand-over, the poultice moves (`test_m29_hand_poultice_to_a_hero_is_a_hand_over`) |
| R8 | No hero-to-hero handover: "gives the spare crowbar to Elowen" is prose only ("makes no move to take it"); gold is per hero with no way to pass coin (a 50 gp potion refused with 84 gp in the party) | p7 69-70, 289 | high: missing capability (owner rule: a possible action happens) | fixed M29.7a 70d27f1: hero-to-hero hand-over of items, keepsakes and gold (`rules.hero_handing`, typed and `hand_over` message; `test_m29_hand_crowbar_and_gold_between_heroes`) |
| R9 | Typed "Elowen unhooks her mace and wields the new warhammer" and "I put on the studded leather armor" equip nothing while the narration says they did (later attacks are Mace, AC stays 14); "equip studded-leather-armor" works | p7 394-395, 447; p4 1201, 1203 | medium | fixed M29.7a df888d2: wield / put on / don / strap on / swap / take off, third person and 'instead' read as equip (`test_m29_typed_put_on_and_wield_equip`) |
| R10 | A quest's reward item is the item it asks for: The Drowned Ledger pays out a fresh "tollmaster-s-ledger" after delivery (shown "Tollmaster S Ledger"); The Master's Oath's reward_item is its own "unfinished chime" | p7 269, 274; plan quests[2]; full plan quests[1] ("Mord's Coin") | medium: campaign plan | fixed M29.7c 15674fa: a reward with the words of the quest's own item becomes "<giver>'s Token" (secrets follow); a lone "s" in an item key renders as a possessive ("Tollmaster's Ledger", Python and web) |
| R11 | Two quests that need the same named item get two copies in one place (main route and side quest "unfinished chime", both hidden at Hollowbarrow Hall); the hero finds one, its twin stays on the ground, and the main quest's chime given to the side-quest giver strands the main route; p8's chapel had two "Cold Clapper"s (both picked up, the narration denied the second) | p7 332-333, 555, 571; p8 16, 18, 200, 206 | high: campaign plan, seen twice | fixed M29.7c 15674fa: one item per name and place (plan repair unifies lookalikes, the engine places it once, every quest counts it, a handed-over copy stays obtained); a shared item goes to one person, the other quest's deliver becomes "Show the X to Y" (meet) |
| R12 | Narrator tells an item made or picked up with no event behind it: the sweetwater "vial" (the quest's proof is a hidden "reedglass charm" at Thornwold, never searched for), the chime "lifted from Hesk's body" recorded as fact; an arrival narration tells Rook handing the ledger to Serin (no event; the typed hand-over at 718 did it) | p7 320, 348, 873-874; full 698 | medium: honest storyteller (items) | fixed M29.7b d407fc9: 'fills a glass vial' claims a vial the hero lacks (CLAIMED_ITEM), a pick-up no event made is flagged (UNMADE_PICKUP), an arrival hand-over is flagged ('book' = ledger, 'once' no longer hides it); one-turn summaries and facts refuse both (`test_m29_vial_never_carried`, `test_m29_chime_lifted_from_the_dust`, `test_m29_ledger_handed_in_an_arrival_narration`) |
| R13 | Narration names people not on the manifest ("the ferry-rat") and says a present NPC is "nowhere in sight" | p7 34, 308, 342 | low | fixed M29.7b d407fc9: a present NPC told absent ('nowhere in sight') is flagged (`test_m29_present_npc_told_absent`); not reproduced: 'the ferry-rat' is Wren's own role (DECISIONS M29.7b) |
| R14 | The last master's peace route ends in a "meet" step that completes on arrival, so the master turns ally and its offer resolves as a parley the player never chose (+2600 XP, finale) | p4 1725-1733 | high: agency | fixed M29.7c 3210c4a: while the master's offer waits a finished Peace route never answers it; Parley shows "(sure to hold)" and holds with no roll, fight stays open; a hand-over to the master is the party's answer; same for act-1/act-2 masters (p7 Gurn test) |
| R15 | With the master an ally and the finale up, a confirmed "point of no return" attack makes it hostile but starts no fight; the narration has it dodge | p4 1742-1747 | medium | fixed M29.7c 3210c4a: a confirmed attack on someone out of a fight starts the fight with them at once (no budget refusal); the region stays resolved by alliance and the finale card waits until the fight is over |
| R16 | The plan makes one person two records: NPC "Dusk Oron" and the region boss "Dusk Oron, Keeper of the Ledger", both at the shrine; killing the boss leaves the NPC alive and present, and the narrator greets him | p4 4 (plan npcs[7]), 12, 17, 1159, 1313-1314 | medium: campaign plan | fixed M29.7c 15674fa: a cast member with the master's name head living at its lair is the master (one record, merged at install) |
| R17 | Typed light words: "light a candle ..., then look around" only searches and the prose says the candle "stays dark"; "light my torch" with the torch burning since 107 is told "the flame will not come" (not "already lit"); "pinch out the candle" makes no light event while the prose says it went out, and the next surprise fails on "they saw your light" ("put out the candle" works) | p4 211-215, 244-246, 677 | high: light vs stealth must be visible (owner) | fixed M29.7a df888d2: pinch out / blow out / shutter put out, 'light X, then ...' lights and does the rest, a lit light says 'already lit' in an engine line (`test_m29_pinch_out_the_candle_puts_it_out`); prose part fixed M29.7b d407fc9: light told out, dark or already lit against the light state is flagged (LIGHT_STATE) and the facts name every burning light (`test_m29_light_prose_matches_the_light_state`) |
| R18 | "I show Farran Dell the Bailiff's Broken Link" gives the main-quest keepsake away ("hands the The Bailiff's ..."); asking for it back is prose; a natural-20 Sleight of Hand to lift it back is narrated as done but no item moves | p4 292-299 | high: owner rule (a possible action happens), closed world | fixed M29.7a d23fb61: show is not give; lifting a keepsake an NPC holds is a Sleight of Hand check that moves it or is noticed (`test_m29_lifting_a_held_keepsake_moves_it_or_is_noticed`) |
| R19 | Fight narration invents foe blows, hits and kills: a hero's missed shot comes with the foe's charge and a claw hit (no foe action, no damage); a bugbear at 12/27 "drops face-first"; shafts "find their mark" in two heroes with no roll; kills credited to the wrong hero. G6's check covers only fights with no blow resolved, G21's misses "drops face-first" | p4 871-874, 1034; full 88, 395, 509, 1072, 1389, 1416, 1579, 2061; p8 185 | high: recurring in nearly every fight | fixed M29.7b d407fc9: per-creature fight truth: a told attacker needs its own blow event, a told hit a hit-point loss, a told miss a missed attack, a told killer the killing damage (PHANTOM_BLOW, PHANTOM_HIT, FALSE_MISS, WRONG_KILLER), 'face-first' joins the defeat phrases, and the facts list each blow and who did nothing (`test_m29_foe_claw_hit_beside_a_lone_miss` and five more in tests/ai/test_m29_honest_blows.py); p8 185: Rook's graze was real (Tamsin's Burning Hands), the cultist's cut is the flagged lie |
| R20 | Animal Friendship's charm does not end when the party harms the beast (SRD 5.1: "If you or one of your companions harms the target, the spell ends"); the charmed death dog stays charmed after a longbow hit, and a fight with only a charmed foe has no peaceful end | p4 1374-1378; data/bg3/spells/animal-friendship.json | medium: rules data | fixed M29.7d 3709f73: Animal Friendship and Charm Person apply "befriended" (implies charmed) that ends when the caster's side damages the bearer (`rules.harm_ends`, data field `ends_on_source_side_harm`); Animal Friendship takes beasts only (the p4 death dog is a monstrosity: now refused); decided: a fight with only befriended foes left ends as a victory, no XP or loot from them (DECISIONS M29.7d R20) (`test_m29_animal_friendship_ends_when_the_party_harms_the_beast`, `test_m29_animal_friendship_needs_a_beast`, `test_m29_a_fight_with_only_befriended_foes_left_ends`) |
| R21 | A snake_case token ("offer_favour") reached the prose (G22 caught only placeholder tokens) | p4 751 | low | fixed M29.7b d407fc9: any snake_case token and any kebab id of the manifest in prose is flagged (IDENTIFIER) (`test_m29_engine_id_in_prose`) |
| R22 | Typed "I swing my longsword at Mirrorwarden Luth" in a fight becomes a creative action (Strength check, flat 2d6), not a longsword attack against AC; it killed the act-1 master | full 456-460 | high: rules exploit | fixed M29.7a 3221e2e: a plain typed weapon attack on a foe is the AttackCommand with that weapon, rolled against AC (`test_m29_typed_weapon_attack_rolls_against_ac`) |
| R23 | A quest hand-over under another name fails: "I give Mord Wexley the bent silver coin" (keepsake "Mord's Coin", Mord is the giver) logs only an attitude change while the narration completes the quest; the quest is later left behind unfinished | full 582-585, 743 | high: quest lost | fixed M29.7a d23fb61: a keepsake is matched by its quest's deliver NPC and description words; a thing not carried is refused plainly (`test_m29_quest_keepsake_by_another_name_is_delivered`) |
| R24 | A lock that cannot be picked (the Foundling Vault door) still gets a Sleight of Hand check; 18 vs 15 passes and the prose says the lock refuses. With R4: a passed check that counts for nothing | full 123-125 | medium | fixed M29.7c 6f9b954: picking or forcing a locked exit is read before the model and answered with what opens the way, no check |
| R25 | The model's plan carries a typo into a finale option ("Comple the Seal"); `levelup` refuses unconscious heroes while `look` says LEVEL UP available | full 5 (plan finale), 2286 | low | fixed M29.7c 6f9b954: the harness offers LEVEL UP to standing heroes only and the refusal says why; decided: the finale typo has no cheap check (DECISIONS) |
| R26 | A self-ranged cone or line ignores the chosen zone and covers the caster's own zone, allies included, with no warning (M3.4 rule): Burning Hands aimed at the archway burned three allies in the reeds and missed the foe | p8 141-150 | high: friendly fire nobody chose | fixed M29.7d 2ccd441: a self cone, line or cube (`targeting.shape`: Burning Hands, Color Spray, Thunderwave 15 ft, Fear 30, Lightning Bolt 100) is aimed at the caster's zone or a neighbour whose edge is no longer than the shape, never the caster (p8: the archway at 25 ft is out of a 15-ft cone's reach, refused with nothing spent); the phone asks for the zone and every Move chip says who it would hit, allies marked, or Out of reach; bots aim through the same `area_zones` (`test_m29_self_cone_aims_at_the_chosen_zone`, `test_m29_self_cone_too_short_for_the_edge_is_refused_and_costs_nothing`, `test_m29_bot_aims_the_cone_away_from_its_friends`, tests/ui/test_area_preview.py) |
| R27 | To check: a level-up seems to refill spell slots (p4 210 sets slot 1 to 2/2 at level 2; p8's wizard cast four 1st-level spells between long rests with three slots) | p4 210; p8 222-680 | check | not reproduced: a level-up adds only the new slots (current = new maximum - spent); p4 210 is a ranger's first slots at level 2 and p8's fourth cast came from Arcane Recovery on the short rest (p8 486-488) (`test_m29_level_up_adds_new_slots_and_keeps_spent_ones`, `test_m29_round_two_level_ups_never_refilled_slots`) |
| R28 | Narration counts the party wrong ("the five of you" with four heroes; "all four of you whole" with Tamsin at 5/14) and gives a hero a race the state does not have | full 574; p8 ~690, ~866 | low | fixed M29.7b d407fc9: an overcount ('the five of you' with four heroes) is flagged (WRONG_COUNT), a hurt hero told whole or the whole party told whole while one is hurt is flagged (HURT_TOLD_WHOLE), and the facts give the party size and who is still hurt (`test_m29_party_counted_wrong`, `test_m29_hurt_hero_told_whole`); decided: undercounts and a lone hero's 'the two of you' stay clean (DECISIONS M29.7b); not reproduced: 'the dwarf' in p8 is Elowen, a hill dwarf (a race nobody has is now flagged, `test_m29_race_the_party_does_not_have`) |

Not bugs: drinking a healing item at full HP spends it for no effect (owner rule: a possible action happens and
costs what it costs; full ~1515, p4); the act-2 wight's 26 HP is the M29.6b boss scale (owner: boss HP scaling stays).

Not reproduced: p7 "tarnished clapper vanishes" (a keepsake, still held at 546; see H10).

## Balance notes
### #5 solo careful (Haiku), save r2-p5-solo c-20261023-150919-0001
108 commands, 8 fights all won, stopped at the act-3 border alive at level 4 (36/36 HP, 69 gp).
- Levels on target: level 2 at the act-1 master, level 3 at the act-2 master.
- Act-1 master (Candle-Mother Adra, "easy", 9 HP for one level-2 hero) died in two hits under a surprise: a warm-up,
  not a master. Act-2 master (Hearthkeeper Veles, "deadly", 38 HP) took 7 rounds, one 19-damage hit, the hero down
  to 9/28 HP; survived with Second Wind and Action Surge and lucky misses (the sims lose 20 of 25 solo runs here).
- Gold plentiful: trivial act-2 kobolds paid 17-23 gp each, Veles 88 gp; a Potion of Healing was affordable after
  every second fight. Three potions, two poultices, a tonic and two draughts were never used.

### #7 economy duo (Haiku), save r2-p7-economy c-20261023-153034-0001
148 commands, 7 fights all won (no hero down), stopped on entering region 3 at level 3 (149 + 36 gp).
- Levels on target: level 3 at the act-2 master; about 2,550 XP per hero by the end of region 2 (level 4 at 2,700),
  which the player felt as fast against SRD per-fight XP; the M29.6b curve aims at 4-5 for act 3.
- Gold: end of act 1 49 gp for the party, end of act 2 220 gp (120 of it one quest). The 10 and 25 gp healing was
  affordable from the start, the 50 gp potion only after the act-2 quest pay.
- Shops met the M29.6b floor but sold no upgrade: ring mail (worse than chain), a light crossbow, a warhammer
  (one die up from a mace, and it could not be equipped by typing, R9).
- Fights easy; the "trivial" zombie (22 HP) took 6 rounds. Hesk (hard) died in 3 rounds.

### #4 rogue-heavy (Sonnet), save r2-p4-rogues c-20261023-150919-0001
About 299 commands, 13 fights, full campaign to the epilogue (The Open Road), all three heroes alive at level 5.
- Masters met at level 2 / 3 / 5 (on target), but they did not feel like masters: the act-1 Bailiff had 11 HP, the
  act-2 priest 18 HP (one scroll of Scorching Ray), the act-3 Saltwright was skipped by R14.
- The hardest fight was a "trivial" bugbear on a three-quarters cover battlement (AC 21 to the party's bows,
  javelins back): about 12 rounds and 50 commands, Elowen down three times, Rook at 5 HP. The danger label ignores
  cover and range.
- XP generous (levels never a limit; the new-place milestone outweighs fight XP); gold tight early (about 15 gp
  each), then one side quest paid about 150 gp each. A long rest costs 30 camp supplies (about 15 gp of rations).
- Cunning play worked: hide, then Sneak Attack, a lit light spoiling surprise, oil plus torch, Help, Animal
  Friendship, typed potion revives. Oil and torch fire did 1-5 a burn, weak next to Sneak Attack.

### Full playthrough, classic four (Sonnet), save r2-full-classic c-20261023-150919-0001
About 340 commands, 11 fights, 4 short and 4 long rests (3 more refused for supplies), finale "Shatter the Glass",
all four alive at level 5. No defeat.
- Masters at level 2 / 3 / 4 (on target, act 3 at the low end). Act 1 (thug Luth, 2 skeletons, a cultist,
  "medium") and act 2 (wight Curator, 26 HP, "medium") fair, 4 rounds each, the wizard down twice in act 2.
  Act 3 (medusa Reflected Hunger, 64 HP, "deadly") put three heroes down over 8 rounds and was won by a looted
  Scroll of Sleep and a natural-20 death save; the cleric ran out of slots.
- "Trivial" foes at levels 3-4 spike: a Cult Fanatic's Inflict Wounds did 22 to a 26-HP wizard; an ogre zombie
  (85 HP) was a 5-round slog.
- Level 2 by command 22 (one trivial fight, one parley at 100 XP); level 3 before the act-2 master, level 4 at the
  first act-3 place.
- Gold: 3-12 per fight each; a 50 gp potion every 2-3 fights (6 bought); long rests cost 40 supplies (about 27 gp).
  The 10 gp poultice and the 25 gp tonic each healed 2 HP on their rolls; armour upgrades were minor (studded
  leather 45 gp for +1 AC) or out of reach (splint 200 gp).

### #8 all casters (Haiku), save r2-p8-casters c-20261023-155806-0001
About 235 commands, 8 fights, 3 long and 1 short rest (one long rest refused for supplies), stopped at the act-3
border at level 3, all four alive.
- Levels on target: level 2 before the act-1 master, level 3 before the act-2 master.
- Labels underrate beasts against 20-HP casters: an "easy" sahuagin dropped a wizard to 0 in round 1, a "trivial"
  brown bear took the wizard from 13 to 0 in one turn; the "medium" wight was the easiest fight (no damage).
- Slots felt right: a long rest about every 3-4 fights, cantrips carry most fights; the warlock never spent a pact
  slot, so short-rest recovery is untested. Camp supplies (40 per long rest, about 20 gp) were the biggest gold sink.

## Balance across round 2
- Levels: every run met the masters at the planned level (M29.6b fixed the round-1 curve). Players still read the
  early levels as fast: level 2 by command 22-29.
- Danger labels: the worst fights of the round were labelled trivial or easy (p4 bugbear in three-quarters cover,
  AC 21; p8 sahuagin and brown bear against casters; full cult fanatic, 22 damage to a 26-HP wizard). The label
  counts SRD XP and breath (M29.6b) but not cover or the foe's damage against the party's HP.
  Fixed M29.7d d5629d7: the word is also at least each foe's round-damage rating (expected damage
  per round over the heroes' average HP: 0.4 medium, 0.5 hard, 0.8 deadly) and one step harder for
  a shooter in three-quarters cover: p8 brown bear trivial -> hard, sahuagin easy -> medium, p4
  bugbear in cover trivial -> easy; the full run's cult fanatic stays easy (its expected round is
  0.23 of the party's average HP; the 22 was a high Inflict Wounds roll). Label only: spokes still
  pick by XP (DECISIONS M29.7d).
- Masters: small parties found the act-1 and act-2 masters weak (p5 9 HP, p4 11 HP and 18 HP); the four-hero full run
  found them fair and the act-3 medusa deadly. The sims agree on act 3; no master change from this round alone.
- Gold: tight in act 1 for every party (15 gp each, a 50 gp potion out of reach), comfortable by the end of act 2;
  shops met the M29.6b floor but rarely sold an upgrade over the starting kit. Cheap healing rolls low (1d4+1, 2d4).
