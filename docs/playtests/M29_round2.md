# M29 round 2: agent playtests on the live storyteller (DRAFT)

Round 2 (2026-10-23), after M29.5a-c and M29.6b, live DeepSeek. Personas: #4 rogue-heavy (Sonnet, full campaign),
full playthrough classic four (Sonnet), #5 solo careful (Haiku, acts 1-2), #7 economy duo (Haiku, acts 1-2),
#8 all casters (Haiku, acts 1-2). Saves: saves/playtests/r2-*/saves (gitignored). Reports came back as text; the main
session checked each bug against its save before listing it here.
Spend: logs/llm.jsonl had 1464 lines before round 2 (total filled in when the round ends).

## Harness problems (scripts/agent only)
- H7 `trade` reads the `shop_stock` message right after the turn settles and does not wait for it; on the live
  storyteller the stock arrives late, so the first trade after arriving says "The shop did not open (no vote?)" although
  the engine opened the shop (p5 events 327-328, 713). `open_stock` must wait for the stock message.
- H8 `do attack` without an option picks the attack with the best hit chance only (`Link.best_option`), so a fighter
  with Archery always fires the crossbow, even with the foe in its zone (p5 549-640). Weigh expected damage.
- H9 Display: every turn line shows `attacks_left=0` at the start of a turn; Action Surge is listed as "(spent or
  unavailable)" until the action is spent; the region milestone XP line is unlabelled; the first fight line says
  "turn of None".
- H10 `trade list` shows the pack only, never keepsakes (p7's "vanished" clapper was held all along, p7 546); there
  is no `equip`/`unequip` command although the protocol has both.
- H11 `look` does not show which hero carries a lit light, zone cover, or why a roll had advantage or disadvantage
  (the events carry `adv_why`, e.g. "high ground", and `target_ac` 21 with three-quarters cover, p4 862-871);
  thrown oil and ball bearings print no zone or surface. The phone shows light and cover; the harness must too.
- H12 `settle` still returns during the live model's silent gap now and then: p4's "ignored" fight act (1371) has
  its narration at 1372 (G4 again); full-run parley, surprise and typed attacks printed the state before the result
  (full 66 vs 69, 457-475, 2247). H7 hit the full run too (589, 752, 768).
- H13 After the finale the tool prints only "THE CAMPAIGN IS COMPLETE"; the ending narration (full 2311) is not shown.

## Game findings (each fix needs a `test_m29_<slug>`)
| id | what | where (run / event) | severity | status |
|---|---|---|---|---|
| R1 | A quest step's text does not match its node: the "clear Gallowroot Copse" step reads "Snuff the bone-pyre the acolytes are stoking" while the copse fields stirge/goblin; a "learn" step tagged ashmede completes from an earlier ashmede fact ("met by what the party has already done") | p5 2 (plan), 243-244; also 453, 498; p4 202, 451 (accepting a quest completed it), 732, 1224-1228, 1656 | medium: story coherence | open |
| R2 | Routed travel stops one node short (Mothfen Hollow, a quest ask), but the narration tells arrival at The False Hearth and records three facts placing the hero there | p5 682-691; p7 764, 898; full 672, 882 | medium: honest storyteller (place) | open |
| R3 | A ranged weapon attack against a foe in the attacker's own zone has no disadvantage (SRD 5.1 "Ranged Attacks in Close Combat"; BG3 Threatened); the crossbow is always the better pick in melee | p5 549-640 | medium: rules gap | open |
| R4 | A typed Persuasion check that passed (20 vs 20) while an encounter offer was pending did not count for the parley; the parley then rolled again and failed | p5 539, 547 | medium: confusing | open |
| R5 | Narration names a weapon the attacker does not carry (sickle for a scimitar); G7's check only flags a different weapon the attacker carries | p5 75, 88 | low | open |
| R6 | Selling a 1 gp item (hammer, rope, incense) is refused as "not worth buying (shop_worthless)"; the line reads as "this is junk" rather than "worth under 1 gp to this trader" | p5 720-726; p7 55 | low: wording | open |
| R7 | Typed "Brienne hands the Herbal Poultice to Elowen ... keep it" is read as using it on Elowen (full HP): no effect, poultice spent | p7 65-67 | high: item lost | open |
| R8 | No hero-to-hero handover: "gives the spare crowbar to Elowen" is prose only ("makes no move to take it"); gold is per hero with no way to pass coin (a 50 gp potion refused with 84 gp in the party) | p7 69-70, 289 | high: missing capability (owner rule: a possible action happens) | open |
| R9 | Typed "Elowen unhooks her mace and wields the new warhammer" and "I put on the studded leather armor" equip nothing while the narration says they did (later attacks are Mace, AC stays 14); "equip studded-leather-armor" works | p7 394-395, 447; p4 1201, 1203 | medium | open |
| R10 | A quest's reward item is the item it asks for: The Drowned Ledger pays out a fresh "tollmaster-s-ledger" after delivery (shown "Tollmaster S Ledger"); The Master's Oath's reward_item is its own "unfinished chime" | p7 269, 274; plan quests[2]; full plan quests[1] ("Mord's Coin") | medium: campaign plan | open |
| R11 | Two quests that need the same named item get two copies in one place (main route and side quest "unfinished chime", both hidden at Hollowbarrow Hall); the hero finds one, its twin stays on the ground, and the main quest's chime given to the side-quest giver strands the main route | p7 332-333, 555, 571 | medium: campaign plan | open |
| R12 | Narrator tells an item made or picked up with no event behind it: the sweetwater "vial" (the quest's proof is a hidden "reedglass charm" at Thornwold, never searched for), the chime "lifted from Hesk's body" recorded as fact; an arrival narration tells Rook handing the ledger to Serin (no event; the typed hand-over at 718 did it) | p7 320, 348, 873-874; full 698 | medium: honest storyteller (items) | open |
| R13 | Narration names people not on the manifest ("the ferry-rat") and says a present NPC is "nowhere in sight" | p7 34, 308, 342 | low | open |
| R14 | The last master's peace route ends in a "meet" step that completes on arrival, so the master turns ally and its offer resolves as a parley the player never chose (+2600 XP, finale) | p4 1725-1733 | high: agency | open |
| R15 | With the master an ally and the finale up, a confirmed "point of no return" attack makes it hostile but starts no fight; the narration has it dodge | p4 1742-1747 | medium | open |
| R16 | The plan makes one person two records: NPC "Dusk Oron" and the region boss "Dusk Oron, Keeper of the Ledger", both at the shrine; killing the boss leaves the NPC alive and present, and the narrator greets him | p4 4 (plan npcs[7]), 12, 17, 1159, 1313-1314 | medium: campaign plan | open |
| R17 | Typed light words: "light a candle ..., then look around" only searches and the prose says the candle "stays dark"; "light my torch" with the torch burning since 107 is told "the flame will not come" (not "already lit"); "pinch out the candle" makes no light event while the prose says it went out, and the next surprise fails on "they saw your light" ("put out the candle" works) | p4 211-215, 244-246, 677 | high: light vs stealth must be visible (owner) | open |
| R18 | "I show Farran Dell the Bailiff's Broken Link" gives the main-quest keepsake away ("hands the The Bailiff's ..."); asking for it back is prose; a natural-20 Sleight of Hand to lift it back is narrated as done but no item moves | p4 292-299 | high: owner rule (a possible action happens), closed world | open |
| R19 | Fight narration invents foe blows, hits and kills: a hero's missed shot comes with the foe's charge and a claw hit (no foe action, no damage); a bugbear at 12/27 "drops face-first"; shafts "find their mark" in two heroes with no roll; kills credited to the wrong hero. G6's check covers only fights with no blow resolved, G21's misses "drops face-first" | p4 871-874, 1034; full 88, 395, 509, 1072, 1389, 1416, 1579, 2061 | high: recurring in nearly every fight | open |
| R20 | Animal Friendship's charm does not end when the party harms the beast (SRD 5.1: "If you or one of your companions harms the target, the spell ends"); the charmed death dog stays charmed after a longbow hit, and a fight with only a charmed foe has no peaceful end | p4 1374-1378; data/bg3/spells/animal-friendship.json | medium: rules data | open |
| R21 | A snake_case token ("offer_favour") reached the prose (G22 caught only placeholder tokens) | p4 751 | low | open |
| R22 | Typed "I swing my longsword at Mirrorwarden Luth" in a fight becomes a creative action (Strength check, flat 2d6), not a longsword attack against AC; it killed the act-1 master | full 456-460 | high: rules exploit | open |
| R23 | A quest hand-over under another name fails: "I give Mord Wexley the bent silver coin" (keepsake "Mord's Coin", Mord is the giver) logs only an attitude change while the narration completes the quest; the quest is later left behind unfinished | full 582-585, 743 | high: quest lost | open |
| R24 | A lock that cannot be picked (the Foundling Vault door) still gets a Sleight of Hand check; 18 vs 15 passes and the prose says the lock refuses. With R4: a passed check that counts for nothing | full 123-125 | medium | open |
| R25 | The model's plan carries a typo into a finale option ("Comple the Seal"); `levelup` refuses unconscious heroes while `look` says LEVEL UP available | full 5 (plan finale), 2286 | low | open |

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
