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
