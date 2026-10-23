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

## Game findings (each fix needs a `test_m29_<slug>`)
| id | what | where (run / event) | severity | status |
|---|---|---|---|---|
| R1 | A quest step's text does not match its node: the "clear Gallowroot Copse" step reads "Snuff the bone-pyre the acolytes are stoking" while the copse fields stirge/goblin; a "learn" step tagged ashmede completes from an earlier ashmede fact ("met by what the party has already done") | p5 2 (plan), 243-244; also 453, 498 | medium: story coherence | open |
| R2 | Routed travel stops one node short (Mothfen Hollow, a quest ask), but the narration tells arrival at The False Hearth and records three facts placing the hero there | p5 682-691; p7 764, 898 | medium: honest storyteller (place) | open |
| R3 | A ranged weapon attack against a foe in the attacker's own zone has no disadvantage (SRD 5.1 "Ranged Attacks in Close Combat"; BG3 Threatened); the crossbow is always the better pick in melee | p5 549-640 | medium: rules gap | open |
| R4 | A typed Persuasion check that passed (20 vs 20) while an encounter offer was pending did not count for the parley; the parley then rolled again and failed | p5 539, 547 | medium: confusing | open |
| R5 | Narration names a weapon the attacker does not carry (sickle for a scimitar); G7's check only flags a different weapon the attacker carries | p5 75, 88 | low | open |
| R6 | Selling a 1 gp item (hammer, rope, incense) is refused as "not worth buying (shop_worthless)"; the line reads as "this is junk" rather than "worth under 1 gp to this trader" | p5 720-726; p7 55 | low: wording | open |
| R7 | Typed "Brienne hands the Herbal Poultice to Elowen ... keep it" is read as using it on Elowen (full HP): no effect, poultice spent | p7 65-67 | high: item lost | open |
| R8 | No hero-to-hero handover: "gives the spare crowbar to Elowen" is prose only ("makes no move to take it"); gold is per hero with no way to pass coin (a 50 gp potion refused with 84 gp in the party) | p7 69-70, 289 | high: missing capability (owner rule: a possible action happens) | open |
| R9 | Typed "Elowen unhooks her mace and wields the new warhammer" equips nothing (the phone's `equip` exists) while the narration says it is wielded; later attacks are Mace | p7 394-395, 447 | medium | open |
| R10 | A quest's reward item is the item it asks for: The Drowned Ledger pays out a fresh "tollmaster-s-ledger" after delivery (shown "Tollmaster S Ledger"); The Master's Oath's reward_item is its own "unfinished chime" | p7 269, 274; plan quests[2] | medium: campaign plan | open |
| R11 | Two quests that need the same named item get two copies in one place (main route and side quest "unfinished chime", both hidden at Hollowbarrow Hall); the hero finds one, its twin stays on the ground, and the main quest's chime given to the side-quest giver strands the main route | p7 332-333, 555, 571 | medium: campaign plan | open |
| R12 | Narrator tells an item made or picked up with no event behind it: the sweetwater "vial" (the quest's proof is a hidden "reedglass charm" at Thornwold, never searched for), the chime "lifted from Hesk's body" recorded as fact | p7 320, 348, 873-874 | medium: honest storyteller (items) | open |
| R13 | Narration names people not on the manifest ("the ferry-rat") and says a present NPC is "nowhere in sight" | p7 34, 308, 342 | low | open |

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
