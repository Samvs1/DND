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
| G1 | Narrator describes a purchase and payment no shop tool performed; gold and pack unchanged | p6 60, 67, 75 | high: closed world |
| G2 | A Restorative Draught in the pack cannot be drunk by typing; narrator says the pack holds no draught | p6 875-884 | high |
| G3 | Narrator treats claimed items as real (potion "shatters" then becomes canon, silk rope, javelin, 500 gold) | p6 37, 39, 41, 86, 335 | high: closed world |
| G4 | Free-text `act` during a fight returns nothing (no reply, no error, no event) | p6 151, 180, 702 | high: "never silent" |
| G5 | Away heroes are auto-played without a visible "(away)" label; grace differs per hero (30 s / 4.5 s / none) | p1 66-69, 83 | medium |
| G6 | Narration describes attacks before they are rolled / against the wrong target | p1 59 | medium |
| G7 | Narration names the wrong weapon (mace / blade for crossbow, shortbow, longbow, bite) | p1 82; p6 158, 241 | low |
| G8 | "Brienne keeps the Burned Shoes" but no pack lists them (maybe a quest-item list `inventory` omits: verify) | p6 357 | check |
| G9 | A second torch "catches" in prose while only one torch is consumed | p6 82 | low |
| G10 | Invented place mapped to a real exit and described as blocked | p6 90 | low |
| G11 | Attacking a friendly NPC prints only "stands on the brink of violence" with no explanation | p6 106, 108 | low |
| G12 | Refusal after a defeat says "There is no fight: use act." | p1 517 | low |
| G13 | Opening recap says "The party found a way: ..." before any action | p1 24-25 | low |
| G14 | Duplicate lead line at campaign start ("Someone at Tollgate Halt may need help" x2) | livecheck c-20261023-080351-0001 | low |
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
| G17 | Rest by typing is prose only (HP unchanged); out-of-fight Cure Wounds and Potion of Healing / Herbal Poultice on an ally do nothing | 355-361, 662-666 | blocker (rest: check vote; healing: real gap, G2 family) |
| G18 | XP maybe paid twice: 75 at the warning beat and again at victory (zombie 47/118, thug 179/240, wolves 273/336) | 47, 118, 179, 240, 273, 336 | high (balance) |
| G19 | Items "found" on a FAILED Investigation while prose says nothing found; an item (hatched moth) described as a creature | 135, 143 | medium |
| G20 | Quest step completes on accept, narrator claims the hero did it | 707 | medium |
| G21 | Narrator kills foes before the engine does ("lies still" at 3/22, 8/32; "the last bandit" with one alive) | 97, 207, 533 | medium |
| G22 | "[unlisted] [unlisted]" placeholder in prose | 143 | low |
| G23 | Foe numbering shifts after deaths; fled foes listed but not numbered; `attack 1` may hit another foe | 313, 336, 580 | medium |
| G24 | Level-up prompt flags only one of four eligible heroes | 246 | medium |
| G25 | Spell options shown with no action/slot left; ally target ids not discoverable for healing spells | 313, 476, 614 | low (harness or view) | (fixed M29.5a 5bdb9de: harness part)
| G26 | HP lost with no damage line; monster attacks narrated without a roll line | 381-393, 59, 75, 308 | medium |
| G27 | Free-text act moved the party; refused moves still print "X moves: ..." | 672, 712, 255, 689 | low | (fixed M29.5a 5bdb9de: harness part)
| G28 | Sub-gp prices: 2 dice sets cost 1 gp total (rounding per line?) | harness smoke s1 | check |
Balance: region 1's only shop has no weapons/armour and a Potion of Healing costs 50 gp vs about 27 gp per hero; a DC 20 Athletics gate (frozen thing) failed 6/6 with no other route; L2 after two fights (see G18).

## Batch 2, persona #3 talkers (Sonnet), save p3-talkers c-20261023-093353-0001
Whole campaign to the epilogue in 261 actions; all alive, L5; one defeat + retry; the Peace path works in all three regions.
Explains G16: travel into the next region waits for `answer confirm`, which the harness never shows (harness gap, not an engine bug).
| id | what | where (event) | severity |
|---|---|---|---|
| G29 | Boss encounter offer stays open after the region resolves by alliance; a failed parley on it turns the allied boss hostile; blocks travel and the finale | 849-890, 1061, 1533-1714 | blocker |
| G30 | Side-quest NPC and boss share one name ("Ranna" x2 in People); "give X to Ranna" goes to the boss record; the deliver step cannot finish | 420-426 | blocker (route) |
| G31 | Narrator narrates a hand-over that did not happen (only "give X to Y" works) | 415-420 | high: closed world |
| G32 | Narrator invents wounds and kills (lizardfolk "falls still" at 22/22; "rat-bites" on full-HP heroes) | 66, 74, 150, 315, 496 | medium |
| G33 | Out-of-fight Cure Wounds by typing narrates a heal, HP and slots unchanged (G17 family) | 592 | high |
| G34 | Generated campaign with NO shop in any of 15 places; long-rest refusal does not say supplies vs hour | 1363 | high (generator) |
| G35 | Epilogue contradicts state (dead/alive bosses, the egg) | 1761 | medium |
| G36 | Prompt instructions leak into notice lines ("Do NOT choose for them...") | 1551, 1760 | high (guard) |
| G37 | `do flee`: fled hero still listed in the zone; after a retry two heroes were auto-played "dodging" the whole rematch | 1571, 1749 | medium (check harness after retry) | (fixed M29.5a 5bdb9de: harness part)
| G38 | Offer lists the boss foe as "?" | 850, 1534 | low | (fixed M29.5a 5bdb9de: harness shows the boss name)
| G39 | No cantrips in casters' fight options (eldritch blast, fire bolt, sacred flame) | 66-82 | check (harness or view) | (fixed M29.5a 5bdb9de: harness only; the server sends cantrips)
| G40 | Harness: travel confirm, finale and offers not shown in `look`; parley skill choice (persuasion/intimidation) not shown; area spells cannot take a zone | 460-473 | harness | (fixed M29.5a 5bdb9de)
Balance: XP far too fast (L5 by action 203; milestones 75-800, boss alliances 600 and 3200 vs fights 12-175); gift deeds farmable (same candle x5 -> boss ALLY, 431-449); dragon labels wrong (green wyrmling "trivial" nearly TPK; young black dragon "medium", breath 51/47 on 30-48 HP heroes, 1714); parley success about 45 percent; no shop (G34) made gold useless.
