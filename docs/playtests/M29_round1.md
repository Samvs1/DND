# M29 round 1: agent playtests on the live storyteller (DRAFT, batch 1 of 3)

Batch 1 (2026-10-23): persona #1 classic four, balanced (Haiku) and persona #6 breaker (Sonnet), live DeepSeek.
Spend: 206 DeepSeek calls, 0.78M prompt + 58k completion tokens (about 0.4-1.6 USD before cache discounts).
The playtesters could not write report files (subagent Write refused), so the main session keeps the findings here.
Saves: saves/playtests/p1-classic/saves and saves/playtests/p6-breaker/saves (campaign c-20261023-080804-0001 in each).

## Harness problems (fix before batch 2; scripts/agent only)
- H1 The away-timer auto-plays heroes in a fight when an AI player takes >30 s per command; p1 was wiped in 6 auto-played rounds (p1 events 83-515); p6 fought 3 fights with 3 of 4 heroes auto-dodging. Playtests need the turn clock off. (fixed in 0314897)
- H2 A defeat cannot be answered (retry / load / new) from the tool (p1 event 523). (fixed in 0314897)
- H3 Command output shows the state BEFORE the event (move, short rest, fight end, quest answer). (fixed in 0314897)
- H4 Curly apostrophes print as "?" (ASCII console). (fixed in 0314897)
- H5 `new` moves the shared default run pointer (saves/playtests/CURRENT) while another run is live. (fixed in 0314897)
- H6 Class features (Second Wind etc.) are not listed in fight options / `do use`; `look` never says a level-up is available; no Trade/shop command (economy persona #7 needs one); options still list attack/dodge after the action is spent. (fixed in 0314897)

## Game bugs (for M29.5, each needs a `test_m29_<slug>`)
| id | what | where (save / event) | severity |
|---|---|---|---|
| G1 | Narrator describes a purchase and payment no shop tool performed; gold and pack unchanged | p6 60, 67, 75 | high: closed world | (fixed M29.5c a761c93: no payment is told without a gold event; the narrator is told no coin changed hands; test_m29_no_payment_without_a_sale) |
| G2 | A Restorative Draught in the pack cannot be drunk by typing; narrator says the pack holds no draught | p6 875-884 | high | (fixed M29.5b 1952114: typed drink/use/pour/give goes through the potion Use path) |
| G3 | Narrator treats claimed items as real (potion "shatters" then becomes canon, silk rope, javelin, 500 gold) | p6 37, 39, 41, 86, 335 | high: closed world | (fixed M29.5c a761c93: a thing the player uses as the hero's own that the hero does not carry is told as not there and flagged in prose; test_m29_claimed_potion_is_told_as_not_there) |
| G4 | Free-text `act` during a fight returns nothing (no reply, no error, no event) | p6 151, 180, 702 | high: "never silent" | (not reproduced: the save has a reply for each, 151-152 narration, 180-184 a creative-action check and damage, 702-703 narration; the harness `settle` returned during the live model's silent gap) |
| G5 | Away heroes are auto-played without a visible "(away)" label; grace differs per hero (30 s / 4.5 s / none) | p1 66-69, 83 | medium |
| G6 | Narration describes attacks before they are rolled / against the wrong target | p1 59 | medium | (fixed M29.5c a761c93: in a fight with no blow resolved, attack claims are flagged and the narrator is told nobody struck; reproduced on p3 495, p1 is not a fixture; test_m29_blows_before_any_roll) |
| G7 | Narration names the wrong weapon (mace / blade for crossbow, shortbow, longbow, bite) | p1 82; p6 158, 241 | low | (fixed M29.5c a761c93: attack lines and facts name the weapon, a different weapon on the attacker is flagged; test_m29_wrong_weapon_is_flagged_and_the_line_names_it) |
| G8 | "Brienne keeps the Burned Shoes" but no pack lists them (maybe a quest-item list `inventory` omits: verify) | p6 357 | check |
| G9 | A second torch "catches" in prose while only one torch is consumed | p6 82 | low | (fixed M29.5c a761c93: a light told catching with no light event is flagged; test_m29_second_torch_does_not_catch) |
| G10 | Invented place mapped to a real exit and described as blocked | p6 90 | low | (fixed M29.5c a761c93: an unknown destination is told as unknown, no other place stands in; test_m29_unknown_place_is_not_stood_in_for) |
| G11 | Attacking a friendly NPC prints only "stands on the brink of violence" with no explanation | p6 106, 108 | low | (fixed M29.5c a8c9c36: the hold line carries the reason; test_m29_hold_line_says_why) |
| G12 | Refusal after a defeat says "There is no fight: use act." | p1 517 | low | (fixed M29.5b ac03786: harness `do` says the fight is over / the party has fallen) |
| G13 | Opening recap says "The party found a way: ..." before any action | p1 24-25 | low | (fixed M29.5b 680460f: "a way the party knows of") |
| G14 | Duplicate lead line at campaign start ("Someone at Tollgate Halt may need help" x2) | livecheck c-20261023-080351-0001 | low | (fixed M29.5b 680460f: a second asker gets "Someone else at ... too") |
| G15 | Long rest in the fen refused only in prose ("no dry ground"), no engine reason or vote | p6 331, 333 | check |

## Balance notes
- 75 XP for every new place and for a parley vs 25 for a crocodile, 12 for two cultists: avoiding fights is the best XP route (p1 40-44, p6 366).
- Act-1 master Keeper's Shade (ghoul, paralysis) + hobgoblin labelled "medium" was deadly at L2 (with auto-dodging heroes; re-check once H1 is fixed).

## What held (engine)
Injections (5 kinds), invented gold/items/spells/NPCs, level-up and revive by narration, fight ending by narration,
out-of-turn and double actions, movement beyond speed, casting as a non-caster, keepsake as gear, impossible actions
turned into hard checks or no effect.

## Batch 2, persona #2 all martial (Haiku), save p2-martial c-20261023-093351-0001
About 132 actions, region 1 resolved, 0 defeats, stopped by the stuck rule. Suspected cause of the two blockers: party VOTES (travel, rest) the harness neither shows nor answers; verify from the save before fixing.
| id | what | where (event) | severity |
|---|---|---|---|
| G16 | Travel to region 2 ("Reedland Ferry") only "proposes", never travels, no reason shown | 689-691, 722 | blocker (check vote) | (fixed M29.5a 5bdb9de: travel confirm shown, answerable)
| G17 | Rest by typing is prose only (HP unchanged); out-of-fight Cure Wounds and Potion of Healing / Herbal Poultice on an ally do nothing | 355-361, 662-666 | blocker (rest: check vote; healing: real gap, G2 family) | (fixed M29.5b 1952114: healing part; rest part open: wordy rest sentences at 353-357 went to the storyteller, which has no rest tool; the plain commands work) | (fixed M29.5b 4a9f574: wordy rest sentences open the rest vote) |
| G18 | XP maybe paid twice: 75 at the warning beat and again at victory (zombie 47/118, thug 179/240, wolves 273/336) | 47, 118, 179, 240, 273, 336 | high (balance) | (not reproduced: not a double count; the first 75 is the spoke's first-visit milestone, the second its clear milestone, each paid once per source (RULES_DECISIONS M9.2); the curve is M29.6b's; guarded by a test in 680460f) |
| G19 | Items "found" on a FAILED Investigation while prose says nothing found; an item (hatched moth) described as a creature | 135, 143 | medium | (fixed M29.5b 680460f: discovery stays per item DC by rule; the storyteller is now told the search found the object even though the check missed its goal) |
| G20 | Quest step completes on accept, narrator claims the hero did it | 707 | medium | (fixed M29.5b 680460f: the step was met by an item picked up at 145 (kept); the step line now says who already carries it and to tell no new deed) |
| G21 | Narrator kills foes before the engine does ("lies still" at 3/22, 8/32; "the last bandit" with one alive) | 97, 207, 533 | medium | (fixed M29.5c a761c93: a standing foe told still or down is flagged in the whole clause and by pronoun; the narrator gets who still stands and the foes left; test_m29_foe_told_still_while_standing) |
| G22 | "[unlisted] [unlisted]" placeholder in prose | 143 | low | (fixed M29.5c a761c93: placeholder tokens are flagged, keepsake names are known words; test_m29_placeholder_never_reaches_prose) |
| G23 | Foe numbering shifts after deaths; fled foes listed but not numbered; `attack 1` may hit another foe | 313, 336, 580 | medium | (fixed M29.5b ac03786: harness numbers foes for the whole fight, dead/fled foes are refused as targets; the phone already targets by creature id and hides fled foes) |
| G24 | Level-up prompt flags only one of four eligible heroes | 246 | medium | (fixed M29.5b ac03786: the engine sent each owner its own prompt; the harness view now flags every eligible hero) |
| G25 | Spell options shown with no action/slot left; ally target ids not discoverable for healing spells | 313, 476, 614 | low (harness or view) | (fixed M29.5a 5bdb9de: harness part)
| G26 | HP lost with no damage line; monster attacks narrated without a roll line | 381-393, 59, 75, 308 | medium | (not reproduced: the save has the attack roll, damage dice and damage_taken for each loss (p2 387-390); the wrong weapon in prose is G7) |
| G27 | Free-text act moved the party; refused moves still print "X moves: ..." | 672, 712, 255, 689 | low | (fixed M29.5a 5bdb9de: harness part) | (not reproduced M29.5c: the act at 666 asked to carry Rook to Ash Hollow, a real exit, and move_party moved the party as asked) |
| G28 | Sub-gp prices: 2 dice sets cost 1 gp total (rounding per line?) | harness smoke s1 | check |
Balance: region 1's only shop has no weapons/armour and a Potion of Healing costs 50 gp vs about 27 gp per hero; a DC 20 Athletics gate (frozen thing) failed 6/6 with no other route; L2 after two fights (see G18).

## Batch 2, persona #3 talkers (Sonnet), save p3-talkers c-20261023-093353-0001
Whole campaign to the epilogue in 261 actions; all alive, L5; one defeat + retry; the Peace path works in all three regions.
Explains G16: travel into the next region waits for `answer confirm`, which the harness never shows (harness gap, not an engine bug).
| id | what | where (event) | severity |
|---|---|---|---|
| G29 | Boss encounter offer stays open after the region resolves by alliance; a failed parley on it turns the allied boss hostile; blocks travel and the finale | 849-890, 1061, 1533-1714 | blocker | (fixed M29.5b 9344e3f) |
| G30 | Side-quest NPC and boss share one name ("Ranna" x2 in People); "give X to Ranna" goes to the boss record; the deliver step cannot finish | 420-426 | blocker (route) | (fixed M29.5b 9344e3f) |
| G31 | Narrator narrates a hand-over that did not happen (only "give X to Y" works) | 415-420 | high: closed world | (fixed M29.5c a761c93 + a8c9c36: a hand-over with no event is flagged and told as not made; "Rook hands X over to Y, ..." goes through give; test_m29_hand_over_not_made_is_flagged, test_m29_third_person_hand_over_is_a_give) |
| G32 | Narrator invents wounds and kills (lizardfolk "falls still" at 22/22; "rat-bites" on full-HP heroes) | 66, 74, 150, 315, 496 | medium | (fixed M29.5c a761c93: wounds on unhurt heroes and blows before any roll are flagged; test_m29_rat_bites_on_unhurt_heroes) |
| G33 | Out-of-fight Cure Wounds by typing narrates a heal, HP and slots unchanged (G17 family) | 592 | high | (fixed M29.5b 1952114) |
| G34 | Generated campaign with NO shop in any of 15 places; long-rest refusal does not say supplies vs hour | 1363 | high (generator) | (fixed M29.5b 9344e3f) |
| G35 | Epilogue contradicts state (dead/alive bosses, the egg) | 1761 | medium | (fixed M29.5c a8c9c36: the epilogue facts state each boss's final fate and the epilogue guard reads "fell" as a death claim; test_m29_epilogue_facts_follow_the_final_state) |
| G36 | Prompt instructions leak into notice lines ("Do NOT choose for them...") | 1551, 1760 | high (guard) | (fixed M29.5c a761c93: instructions moved to model-only event notes and cut from public lines; test_m29_finale_notice_lines_carry_no_instruction) |
| G37 | `do flee`: fled hero still listed in the zone; after a retry two heroes were auto-played "dodging" the whole rematch | 1571, 1749 | medium (check harness after retry) | (fixed M29.5a 5bdb9de: harness part) (fixed M29.5b f37d4ea: restored seats get the reconnect grace) |
| G38 | Offer lists the boss foe as "?" | 850, 1534 | low | (fixed M29.5a 5bdb9de: harness shows the boss name)
| G39 | No cantrips in casters' fight options (eldritch blast, fire bolt, sacred flame) | 66-82 | check (harness or view) | (fixed M29.5a 5bdb9de: harness only; the server sends cantrips)
| G40 | Harness: travel confirm, finale and offers not shown in `look`; parley skill choice (persuasion/intimidation) not shown; area spells cannot take a zone | 460-473 | harness | (fixed M29.5a 5bdb9de)
Balance: XP far too fast (L5 by action 203; milestones 75-800, boss alliances 600 and 3200 vs fights 12-175); gift deeds farmable (same candle x5 -> boss ALLY, 431-449); dragon labels wrong (green wyrmling "trivial" nearly TPK; young black dragon "medium", breath 51/47 on 30-48 HP heroes, 1714); parley success about 45 percent; no shop (G34) made gold useless.
