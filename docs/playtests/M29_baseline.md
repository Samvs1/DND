# M29.2 baseline: scripted full campaigns (fake storyteller)

Date 2026-10-23, commit after `433aee8`. Nothing is tuned yet (that is M29.6); this is the measurement.

## What ran
- `python scripts/simulate_party.py --style <styles> --party all --seeds 5 --out saves/balance/M29_baseline`,
  in 4 detached processes side by side (balanced+aggressive, cautious+talker, cunning+spender, hoarder).
- **Grid: 7 styles x 5 parties x 5 seeds = 175 full campaigns, nothing cut.** 0 runs failed a check
  (no server exception, no silent turn, no softlock, invariants, privacy and replay all clean).
- Runtime: 112 minutes of run time in total (12 to 70 s per campaign), about 36 minutes wall clock with
  4 processes. Report: `python scripts/balance_report.py saves/balance/M29_baseline --markdown [--group style|party]` (9 s).
- Styles: balanced (reference), aggressive (rests only when nearly dead, no camp before a master), cautious
  (rests early, camps before every master, searches), talker (parley everything, follows the Peace way),
  cunning (surprise = sneak in, searches), spender (healing potions at every hub), hoarder (buys nothing but
  camp food). Parties: classic (fighter, cleric, rogue, wizard), martial (fighter, ranger, rogue, fighter),
  casters (wizard, cleric, warlock, wizard), solo (fighter), duo (fighter, cleric). The data ships six classes.
- The bots are plain players: they attack, use their first cantrip, spend slots on healing and single-target
  damage spells, drink potions below 35% HP, use the healer's kit, oil and torches. They do not use class
  feature actions (Second Wind, Action Surge, Cunning Action), positioning or concentration tricks, so the
  numbers are a floor for a thoughtful table.
- A lost fight is retried 3 times (the defeat screen's retry); a 4th loss ends the run ("lost for good").
  Each retried wipe is counted as a lost fight (`wipes`, M29.2 metric).

## What stands out
- **Almost no campaign finishes: 35 of 175 reach the epilogue.** Casters do best (talker/casters 5 of 5,
  cautious, hoarder and spender casters 4 of 5); classic 10 of 35, martial 2 of 35, **solo and duo 0 of 70**.
- **Normal fights are far too hard**: the balanced clean-win rate is 0.32 to 0.56 per party (target
  0.75 to 0.90), and the groups wipe 0.8 to 6.6 times per campaign on average (most 3 to 4.5).
- **Where runs die**: Cistern of Echoes (act 3 spoke, an earth elemental) 35, Sunken Vestry (act 1 master,
  bugbear with company) 33, Harrowmere Bridge (act 2 spoke, bandit captain) 32, Keeper's Barracks (act 3
  spoke, gladiator) 16, Fogwright's Tower (act 2 master) 12. Single high-CR monsters at spokes are the walls.
- **Masters: 2 to 3.5 heroes down on average for four-hero parties** (target at most 1). Solo and duo pass
  that target only because they have fewer heroes to lose.
- **Levels at each master are on plan** (act 1: 2, act 2: 3, act 3: 5 at the lowest), so the gap is the
  fights, not the experience curve.
- **Gold is placeholder-range everywhere**: about 120 gp per hero at the end of act 1, 155 to 180 after act 2,
  205 to 270 after act 3; martial ends act 3 at 194 (MISS by 6). The spender ends act 2 at 101 (potions),
  the hoarder holds about the same as everyone, because nothing worth buying is on sale in quantity.
- **Style matters less than party**: cautious and cunning finish more often than balanced; aggressive is the
  worst (1 of 25, 2.95 heroes down per master). Spending on potions did not change the outcome.
- **The Peace way is rare**: talkers resolved 4 regions by alliance out of 49; the master's parley needs a
  hard Persuasion (DC 20 by act 3) and no shipped class leads with Charisma except the warlock.

## Targets by style (all parties pooled)
| verdict | style | party | runs | target | value | bounds |
|---|---|---|---|---|---|---|
| MISS | aggressive | all | 25 | boss_heroes_down_avg | 2.95 | -..1 |
| PASS | aggressive | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | aggressive | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | aggressive | all | 25 | boss_level_act3 | 5 | 4..- |
| PASS | aggressive | all | 25 | gold_act1_end | 124 | 30..300 |
| PASS | aggressive | all | 25 | gold_act2_end | 159 | 100..900 |
| PASS | aggressive | all | 25 | gold_act3_end | 210 | 200..1800 |
| MISS | balanced | all | 25 | normal_clean_win_rate | 0.41 | 0.75..0.9 |
| MISS | balanced | all | 25 | boss_heroes_down_avg | 2.44 | -..1 |
| PASS | balanced | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | balanced | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | balanced | all | 25 | boss_level_act3 | 5 | 4..- |
| PASS | balanced | all | 25 | gold_act1_end | 120.5 | 30..300 |
| PASS | balanced | all | 25 | gold_act2_end | 181 | 100..900 |
| PASS | balanced | all | 25 | gold_act3_end | 208 | 200..1800 |
| MISS | cautious | all | 25 | boss_heroes_down_avg | 2.58 | -..1 |
| PASS | cautious | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | cautious | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | cautious | all | 25 | boss_level_act3 | 5 | 4..- |
| PASS | cautious | all | 25 | gold_act1_end | 120 | 30..300 |
| PASS | cautious | all | 25 | gold_act2_end | 157 | 100..900 |
| PASS | cautious | all | 25 | gold_act3_end | 212 | 200..1800 |
| MISS | cunning | all | 25 | boss_heroes_down_avg | 1.88 | -..1 |
| PASS | cunning | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | cunning | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | cunning | all | 25 | boss_level_act3 | 5 | 4..- |
| PASS | cunning | all | 25 | gold_act1_end | 123 | 30..300 |
| PASS | cunning | all | 25 | gold_act2_end | 168 | 100..900 |
| PASS | cunning | all | 25 | gold_act3_end | 220 | 200..1800 |
| MISS | hoarder | all | 25 | boss_heroes_down_avg | 2.52 | -..1 |
| PASS | hoarder | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | hoarder | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | hoarder | all | 25 | boss_level_act3 | 5 | 4..- |
| PASS | hoarder | all | 25 | gold_act1_end | 126 | 30..300 |
| PASS | hoarder | all | 25 | gold_act2_end | 155 | 100..900 |
| PASS | hoarder | all | 25 | gold_act3_end | 214 | 200..1800 |
| MISS | spender | all | 25 | boss_heroes_down_avg | 2.12 | -..1 |
| PASS | spender | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | spender | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | spender | all | 25 | boss_level_act3 | 5 | 4..- |
| PASS | spender | all | 25 | gold_act1_end | 121 | 30..300 |
| PASS | spender | all | 25 | gold_act2_end | 101 | 100..900 |
| PASS | spender | all | 25 | gold_act3_end | 270 | 200..1800 |
| MISS | talker | all | 25 | boss_heroes_down_avg | 2.2 | -..1 |
| PASS | talker | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | talker | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | talker | all | 25 | boss_level_act3 | 5 | 4..- |
| PASS | talker | all | 25 | gold_act1_end | 117 | 30..300 |
| PASS | talker | all | 25 | gold_act2_end | 168 | 100..900 |
| PASS | talker | all | 25 | gold_act3_end | 205 | 200..1800 |

## Targets by party (all styles pooled; the clean-win target is defined for the balanced style only)
| verdict | style | party | runs | target | value | bounds |
|---|---|---|---|---|---|---|
| MISS | all | casters | 35 | boss_heroes_down_avg | 2.57 | -..1 |
| PASS | all | casters | 35 | boss_level_act1 | 2 | 2..- |
| PASS | all | casters | 35 | boss_level_act2 | 3 | 3..- |
| PASS | all | casters | 35 | boss_level_act3 | 5 | 4..- |
| PASS | all | casters | 35 | gold_act1_end | 120 | 30..300 |
| PASS | all | casters | 35 | gold_act2_end | 155 | 100..900 |
| PASS | all | casters | 35 | gold_act3_end | 214 | 200..1800 |
| MISS | all | classic | 35 | boss_heroes_down_avg | 3.39 | -..1 |
| PASS | all | classic | 35 | boss_level_act1 | 2 | 2..- |
| PASS | all | classic | 35 | boss_level_act2 | 3 | 3..- |
| PASS | all | classic | 35 | boss_level_act3 | 5 | 4..- |
| PASS | all | classic | 35 | gold_act1_end | 122 | 30..300 |
| PASS | all | classic | 35 | gold_act2_end | 155 | 100..900 |
| PASS | all | classic | 35 | gold_act3_end | 211.5 | 200..1800 |
| PASS | all | duo | 35 | boss_heroes_down_avg | 0.97 | -..1 |
| PASS | all | duo | 35 | boss_level_act1 | 2 | 2..- |
| PASS | all | duo | 35 | boss_level_act2 | 3 | 3..- |
| N/A | all | duo | 35 | boss_level_act3 | - | 4..- |
| PASS | all | duo | 35 | gold_act1_end | 121 | 30..300 |
| PASS | all | duo | 35 | gold_act2_end | 212 | 100..900 |
| N/A | all | duo | 35 | gold_act3_end | - | 200..1800 |
| MISS | all | martial | 35 | boss_heroes_down_avg | 3.48 | -..1 |
| PASS | all | martial | 35 | boss_level_act1 | 2 | 2..- |
| PASS | all | martial | 35 | boss_level_act2 | 3 | 3..- |
| PASS | all | martial | 35 | boss_level_act3 | 5 | 4..- |
| PASS | all | martial | 35 | gold_act1_end | 120 | 30..300 |
| PASS | all | martial | 35 | gold_act2_end | 150 | 100..900 |
| MISS | all | martial | 35 | gold_act3_end | 194 | 200..1800 |
| PASS | all | solo | 35 | boss_heroes_down_avg | 0.74 | -..1 |
| PASS | all | solo | 35 | boss_level_act1 | 2 | 2..- |
| PASS | all | solo | 35 | boss_level_act2 | 4 | 3..- |
| N/A | all | solo | 35 | boss_level_act3 | - | 4..- |
| PASS | all | solo | 35 | gold_act1_end | 133.5 | 30..300 |
| N/A | all | solo | 35 | gold_act2_end | - | 100..900 |
| N/A | all | solo | 35 | gold_act3_end | - | 200..1800 |

Balanced style, clean wins per party: casters 0.44, classic 0.36, duo 0.32, martial 0.44, solo 0.56 (all MISS).

## How the runs ended (per style and party)
| style | party | runs | epilogue | lost for good | top level (median) | wipes/run |
|---|---|---|---|---|---|---|
| aggressive | casters | 5 | 0 | act 1: 4, act 3: 1 | 2 | 3.8 |
| aggressive | classic | 5 | 1 | act 1: 4 | 2 | 4 |
| aggressive | duo | 5 | 0 | act 2: 4, act 3: 1 | 3 | 4.6 |
| aggressive | martial | 5 | 0 | act 1: 1, act 2: 2, act 3: 2 | 4 | 4.8 |
| aggressive | solo | 5 | 0 | act 1: 2, act 2: 3 | 3 | 4 |
| balanced | casters | 5 | 3 | act 3: 2 | 5 | 2.4 |
| balanced | classic | 5 | 0 | act 3: 5 | 4 | 4.2 |
| balanced | duo | 5 | 0 | act 2: 1, act 3: 4 | 4 | 6.6 |
| balanced | martial | 5 | 0 | act 1: 2, act 2: 1, act 3: 2 | 4 | 3.6 |
| balanced | solo | 5 | 0 | act 1: 1, act 2: 4 | 3 | 4 |
| cautious | casters | 5 | 4 | act 1: 1 | 5 | 2.8 |
| cautious | classic | 5 | 2 | act 3: 3 | 4 | 4.2 |
| cautious | duo | 5 | 0 | act 2: 1, act 3: 4 | 4 | 5 |
| cautious | martial | 5 | 1 | act 2: 2, act 3: 2 | 4 | 4.8 |
| cautious | solo | 5 | 0 | act 1: 2, act 2: 3 | 3 | 3.8 |
| cunning | casters | 5 | 3 | act 1: 1, act 3: 1 | 5 | 2.2 |
| cunning | classic | 5 | 2 | act 3: 3 | 4 | 2.4 |
| cunning | duo | 5 | 0 | act 1: 1, act 2: 3, act 3: 1 | 3 | 3.4 |
| cunning | martial | 5 | 1 | act 2: 2, act 3: 2 | 4 | 3.8 |
| cunning | solo | 5 | 0 | act 1: 1, act 2: 4 | 3 | 4.4 |
| hoarder | casters | 5 | 4 | act 1: 1 | 5 | 0.8 |
| hoarder | classic | 5 | 0 | act 3: 5 | 4 | 3.8 |
| hoarder | duo | 5 | 0 | act 1: 1, act 2: 2, act 3: 2 | 3 | 3.4 |
| hoarder | martial | 5 | 0 | act 1: 1, act 2: 2, act 3: 2 | 4 | 3.4 |
| hoarder | solo | 5 | 0 | act 1: 2, act 2: 3 | 3 | 3 |
| spender | casters | 5 | 4 | act 3: 1 | 5 | 2 |
| spender | classic | 5 | 1 | act 1: 1, act 3: 3 | 4 | 3.4 |
| spender | duo | 5 | 0 | act 2: 4, act 3: 1 | 4 | 4.2 |
| spender | martial | 5 | 0 | act 1: 2, act 2: 1, act 3: 2 | 3 | 3 |
| spender | solo | 5 | 0 | act 1: 3, act 2: 2 | 3 | 3 |
| talker | casters | 5 | 5 | - | 5 | 0.8 |
| talker | classic | 5 | 4 | act 1: 1 | 5 | 1.6 |
| talker | duo | 5 | 0 | act 3: 5 | 4 | 4.4 |
| talker | martial | 5 | 0 | act 1: 1, act 2: 1, act 3: 3 | 4 | 3.6 |
| talker | solo | 5 | 0 | act 2: 5 | 3 | 3.6 |

<details><summary>Every target per style and party (280 rows)</summary>

| verdict | style | party | runs | target | value | bounds |
|---|---|---|---|---|---|---|
| MISS | aggressive | casters | 5 | boss_heroes_down_avg | 3.9 | -..1 |
| PASS | aggressive | casters | 5 | boss_level_act1 | 2 | 2..- |
| PASS | aggressive | casters | 5 | boss_level_act2 | 3 | 3..- |
| N/A | aggressive | casters | 5 | boss_level_act3 | - | 4..- |
| PASS | aggressive | casters | 5 | gold_act1_end | 108 | 30..300 |
| PASS | aggressive | casters | 5 | gold_act2_end | 159 | 100..900 |
| N/A | aggressive | casters | 5 | gold_act3_end | - | 200..1800 |
| MISS | aggressive | classic | 5 | boss_heroes_down_avg | 3.78 | -..1 |
| PASS | aggressive | classic | 5 | boss_level_act1 | 2 | 2..- |
| PASS | aggressive | classic | 5 | boss_level_act2 | 3 | 3..- |
| PASS | aggressive | classic | 5 | boss_level_act3 | 5 | 4..- |
| PASS | aggressive | classic | 5 | gold_act1_end | 123 | 30..300 |
| PASS | aggressive | classic | 5 | gold_act2_end | 155 | 100..900 |
| PASS | aggressive | classic | 5 | gold_act3_end | 210 | 200..1800 |
| PASS | aggressive | duo | 5 | boss_heroes_down_avg | 0.89 | -..1 |
| PASS | aggressive | duo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | aggressive | duo | 5 | boss_level_act2 | 4 | 3..- |
| N/A | aggressive | duo | 5 | boss_level_act3 | - | 4..- |
| PASS | aggressive | duo | 5 | gold_act1_end | 124 | 30..300 |
| PASS | aggressive | duo | 5 | gold_act2_end | 170 | 100..900 |
| N/A | aggressive | duo | 5 | gold_act3_end | - | 200..1800 |
| MISS | aggressive | martial | 5 | boss_heroes_down_avg | 3.45 | -..1 |
| PASS | aggressive | martial | 5 | boss_level_act1 | 2 | 2..- |
| PASS | aggressive | martial | 5 | boss_level_act2 | 3 | 3..- |
| N/A | aggressive | martial | 5 | boss_level_act3 | - | 4..- |
| PASS | aggressive | martial | 5 | gold_act1_end | 121.5 | 30..300 |
| PASS | aggressive | martial | 5 | gold_act2_end | 153 | 100..900 |
| N/A | aggressive | martial | 5 | gold_act3_end | - | 200..1800 |
| PASS | aggressive | solo | 5 | boss_heroes_down_avg | 0.79 | -..1 |
| PASS | aggressive | solo | 5 | boss_level_act1 | 2 | 2..- |
| N/A | aggressive | solo | 5 | boss_level_act2 | - | 3..- |
| N/A | aggressive | solo | 5 | boss_level_act3 | - | 4..- |
| PASS | aggressive | solo | 5 | gold_act1_end | 138 | 30..300 |
| N/A | aggressive | solo | 5 | gold_act2_end | - | 100..900 |
| N/A | aggressive | solo | 5 | gold_act3_end | - | 200..1800 |
| MISS | balanced | casters | 5 | normal_clean_win_rate | 0.44 | 0.75..0.9 |
| MISS | balanced | casters | 5 | boss_heroes_down_avg | 2.27 | -..1 |
| PASS | balanced | casters | 5 | boss_level_act1 | 2 | 2..- |
| PASS | balanced | casters | 5 | boss_level_act2 | 3 | 3..- |
| PASS | balanced | casters | 5 | boss_level_act3 | 5 | 4..- |
| PASS | balanced | casters | 5 | gold_act1_end | 120 | 30..300 |
| PASS | balanced | casters | 5 | gold_act2_end | 151 | 100..900 |
| PASS | balanced | casters | 5 | gold_act3_end | 208 | 200..1800 |
| MISS | balanced | classic | 5 | normal_clean_win_rate | 0.36 | 0.75..0.9 |
| MISS | balanced | classic | 5 | boss_heroes_down_avg | 3.93 | -..1 |
| PASS | balanced | classic | 5 | boss_level_act1 | 2 | 2..- |
| PASS | balanced | classic | 5 | boss_level_act2 | 4 | 3..- |
| N/A | balanced | classic | 5 | boss_level_act3 | - | 4..- |
| PASS | balanced | classic | 5 | gold_act1_end | 121 | 30..300 |
| PASS | balanced | classic | 5 | gold_act2_end | 156 | 100..900 |
| N/A | balanced | classic | 5 | gold_act3_end | - | 200..1800 |
| MISS | balanced | duo | 5 | normal_clean_win_rate | 0.32 | 0.75..0.9 |
| PASS | balanced | duo | 5 | boss_heroes_down_avg | 0.93 | -..1 |
| PASS | balanced | duo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | balanced | duo | 5 | boss_level_act2 | 4 | 3..- |
| N/A | balanced | duo | 5 | boss_level_act3 | - | 4..- |
| PASS | balanced | duo | 5 | gold_act1_end | 121 | 30..300 |
| PASS | balanced | duo | 5 | gold_act2_end | 269 | 100..900 |
| N/A | balanced | duo | 5 | gold_act3_end | - | 200..1800 |
| MISS | balanced | martial | 5 | normal_clean_win_rate | 0.44 | 0.75..0.9 |
| MISS | balanced | martial | 5 | boss_heroes_down_avg | 3.85 | -..1 |
| PASS | balanced | martial | 5 | boss_level_act1 | 2 | 2..- |
| PASS | balanced | martial | 5 | boss_level_act2 | 3 | 3..- |
| N/A | balanced | martial | 5 | boss_level_act3 | - | 4..- |
| PASS | balanced | martial | 5 | gold_act1_end | 119 | 30..300 |
| PASS | balanced | martial | 5 | gold_act2_end | 227 | 100..900 |
| N/A | balanced | martial | 5 | gold_act3_end | - | 200..1800 |
| MISS | balanced | solo | 5 | normal_clean_win_rate | 0.56 | 0.75..0.9 |
| PASS | balanced | solo | 5 | boss_heroes_down_avg | 0.73 | -..1 |
| PASS | balanced | solo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | balanced | solo | 5 | boss_level_act2 | 4 | 3..- |
| N/A | balanced | solo | 5 | boss_level_act3 | - | 4..- |
| PASS | balanced | solo | 5 | gold_act1_end | 137.5 | 30..300 |
| N/A | balanced | solo | 5 | gold_act2_end | - | 100..900 |
| N/A | balanced | solo | 5 | gold_act3_end | - | 200..1800 |
| MISS | cautious | casters | 5 | boss_heroes_down_avg | 3.7 | -..1 |
| PASS | cautious | casters | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cautious | casters | 5 | boss_level_act2 | 3 | 3..- |
| PASS | cautious | casters | 5 | boss_level_act3 | 5 | 4..- |
| PASS | cautious | casters | 5 | gold_act1_end | 120 | 30..300 |
| PASS | cautious | casters | 5 | gold_act2_end | 155.5 | 100..900 |
| PASS | cautious | casters | 5 | gold_act3_end | 217.5 | 200..1800 |
| MISS | cautious | classic | 5 | boss_heroes_down_avg | 3.35 | -..1 |
| PASS | cautious | classic | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cautious | classic | 5 | boss_level_act2 | 4 | 3..- |
| PASS | cautious | classic | 5 | boss_level_act3 | 5 | 4..- |
| PASS | cautious | classic | 5 | gold_act1_end | 123 | 30..300 |
| PASS | cautious | classic | 5 | gold_act2_end | 156 | 100..900 |
| PASS | cautious | classic | 5 | gold_act3_end | 205.5 | 200..1800 |
| PASS | cautious | duo | 5 | boss_heroes_down_avg | 0.86 | -..1 |
| PASS | cautious | duo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cautious | duo | 5 | boss_level_act2 | 3 | 3..- |
| N/A | cautious | duo | 5 | boss_level_act3 | - | 4..- |
| PASS | cautious | duo | 5 | gold_act1_end | 120 | 30..300 |
| PASS | cautious | duo | 5 | gold_act2_end | 248 | 100..900 |
| N/A | cautious | duo | 5 | gold_act3_end | - | 200..1800 |
| MISS | cautious | martial | 5 | boss_heroes_down_avg | 3.05 | -..1 |
| PASS | cautious | martial | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cautious | martial | 5 | boss_level_act2 | 3 | 3..- |
| PASS | cautious | martial | 5 | boss_level_act3 | 5 | 4..- |
| PASS | cautious | martial | 5 | gold_act1_end | 118 | 30..300 |
| PASS | cautious | martial | 5 | gold_act2_end | 147 | 100..900 |
| MISS | cautious | martial | 5 | gold_act3_end | 178 | 200..1800 |
| PASS | cautious | solo | 5 | boss_heroes_down_avg | 0.77 | -..1 |
| PASS | cautious | solo | 5 | boss_level_act1 | 2 | 2..- |
| N/A | cautious | solo | 5 | boss_level_act2 | - | 3..- |
| N/A | cautious | solo | 5 | boss_level_act3 | - | 4..- |
| PASS | cautious | solo | 5 | gold_act1_end | 128 | 30..300 |
| N/A | cautious | solo | 5 | gold_act2_end | - | 100..900 |
| N/A | cautious | solo | 5 | gold_act3_end | - | 200..1800 |
| MISS | cunning | casters | 5 | boss_heroes_down_avg | 2.2 | -..1 |
| PASS | cunning | casters | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cunning | casters | 5 | boss_level_act2 | 3 | 3..- |
| PASS | cunning | casters | 5 | boss_level_act3 | 5 | 4..- |
| PASS | cunning | casters | 5 | gold_act1_end | 122.5 | 30..300 |
| PASS | cunning | casters | 5 | gold_act2_end | 230 | 100..900 |
| PASS | cunning | casters | 5 | gold_act3_end | 366 | 200..1800 |
| MISS | cunning | classic | 5 | boss_heroes_down_avg | 1.31 | -..1 |
| PASS | cunning | classic | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cunning | classic | 5 | boss_level_act2 | 3 | 3..- |
| PASS | cunning | classic | 5 | boss_level_act3 | 5 | 4..- |
| PASS | cunning | classic | 5 | gold_act1_end | 122 | 30..300 |
| PASS | cunning | classic | 5 | gold_act2_end | 168 | 100..900 |
| PASS | cunning | classic | 5 | gold_act3_end | 213 | 200..1800 |
| MISS | cunning | duo | 5 | boss_heroes_down_avg | 1.1 | -..1 |
| PASS | cunning | duo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cunning | duo | 5 | boss_level_act2 | 4 | 3..- |
| N/A | cunning | duo | 5 | boss_level_act3 | - | 4..- |
| PASS | cunning | duo | 5 | gold_act1_end | 122.5 | 30..300 |
| PASS | cunning | duo | 5 | gold_act2_end | 346 | 100..900 |
| N/A | cunning | duo | 5 | gold_act3_end | - | 200..1800 |
| MISS | cunning | martial | 5 | boss_heroes_down_avg | 3.19 | -..1 |
| PASS | cunning | martial | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cunning | martial | 5 | boss_level_act2 | 4 | 3..- |
| PASS | cunning | martial | 5 | boss_level_act3 | 5 | 4..- |
| PASS | cunning | martial | 5 | gold_act1_end | 123 | 30..300 |
| PASS | cunning | martial | 5 | gold_act2_end | 160 | 100..900 |
| PASS | cunning | martial | 5 | gold_act3_end | 210 | 200..1800 |
| PASS | cunning | solo | 5 | boss_heroes_down_avg | 0.73 | -..1 |
| PASS | cunning | solo | 5 | boss_level_act1 | 2 | 2..- |
| N/A | cunning | solo | 5 | boss_level_act2 | - | 3..- |
| N/A | cunning | solo | 5 | boss_level_act3 | - | 4..- |
| PASS | cunning | solo | 5 | gold_act1_end | 134 | 30..300 |
| N/A | cunning | solo | 5 | gold_act2_end | - | 100..900 |
| N/A | cunning | solo | 5 | gold_act3_end | - | 200..1800 |
| MISS | hoarder | casters | 5 | boss_heroes_down_avg | 2.56 | -..1 |
| PASS | hoarder | casters | 5 | boss_level_act1 | 2 | 2..- |
| PASS | hoarder | casters | 5 | boss_level_act2 | 3 | 3..- |
| PASS | hoarder | casters | 5 | boss_level_act3 | 5 | 4..- |
| PASS | hoarder | casters | 5 | gold_act1_end | 120.5 | 30..300 |
| PASS | hoarder | casters | 5 | gold_act2_end | 158 | 100..900 |
| PASS | hoarder | casters | 5 | gold_act3_end | 214 | 200..1800 |
| MISS | hoarder | classic | 5 | boss_heroes_down_avg | 3.71 | -..1 |
| PASS | hoarder | classic | 5 | boss_level_act1 | 2 | 2..- |
| PASS | hoarder | classic | 5 | boss_level_act2 | 3 | 3..- |
| N/A | hoarder | classic | 5 | boss_level_act3 | - | 4..- |
| PASS | hoarder | classic | 5 | gold_act1_end | 128 | 30..300 |
| PASS | hoarder | classic | 5 | gold_act2_end | 153 | 100..900 |
| N/A | hoarder | classic | 5 | gold_act3_end | - | 200..1800 |
| PASS | hoarder | duo | 5 | boss_heroes_down_avg | 0.9 | -..1 |
| PASS | hoarder | duo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | hoarder | duo | 5 | boss_level_act2 | 4 | 3..- |
| N/A | hoarder | duo | 5 | boss_level_act3 | - | 4..- |
| PASS | hoarder | duo | 5 | gold_act1_end | 124.5 | 30..300 |
| PASS | hoarder | duo | 5 | gold_act2_end | 257.5 | 100..900 |
| N/A | hoarder | duo | 5 | gold_act3_end | - | 200..1800 |
| MISS | hoarder | martial | 5 | boss_heroes_down_avg | 3.69 | -..1 |
| PASS | hoarder | martial | 5 | boss_level_act1 | 2 | 2..- |
| PASS | hoarder | martial | 5 | boss_level_act2 | 3 | 3..- |
| N/A | hoarder | martial | 5 | boss_level_act3 | - | 4..- |
| PASS | hoarder | martial | 5 | gold_act1_end | 120 | 30..300 |
| PASS | hoarder | martial | 5 | gold_act2_end | 146.5 | 100..900 |
| N/A | hoarder | martial | 5 | gold_act3_end | - | 200..1800 |
| PASS | hoarder | solo | 5 | boss_heroes_down_avg | 0.73 | -..1 |
| PASS | hoarder | solo | 5 | boss_level_act1 | 2 | 2..- |
| N/A | hoarder | solo | 5 | boss_level_act2 | - | 3..- |
| N/A | hoarder | solo | 5 | boss_level_act3 | - | 4..- |
| PASS | hoarder | solo | 5 | gold_act1_end | 137 | 30..300 |
| N/A | hoarder | solo | 5 | gold_act2_end | - | 100..900 |
| N/A | hoarder | solo | 5 | gold_act3_end | - | 200..1800 |
| MISS | spender | casters | 5 | boss_heroes_down_avg | 1.21 | -..1 |
| PASS | spender | casters | 5 | boss_level_act1 | 2 | 2..- |
| PASS | spender | casters | 5 | boss_level_act2 | 3 | 3..- |
| PASS | spender | casters | 5 | boss_level_act3 | 5 | 4..- |
| PASS | spender | casters | 5 | gold_act1_end | 120 | 30..300 |
| MISS | spender | casters | 5 | gold_act2_end | 58 | 100..900 |
| MISS | spender | casters | 5 | gold_act3_end | 195.5 | 200..1800 |
| MISS | spender | classic | 5 | boss_heroes_down_avg | 3.6 | -..1 |
| PASS | spender | classic | 5 | boss_level_act1 | 2 | 2..- |
| PASS | spender | classic | 5 | boss_level_act2 | 4 | 3..- |
| PASS | spender | classic | 5 | boss_level_act3 | 5 | 4..- |
| PASS | spender | classic | 5 | gold_act1_end | 120 | 30..300 |
| PASS | spender | classic | 5 | gold_act2_end | 101 | 100..900 |
| PASS | spender | classic | 5 | gold_act3_end | 363 | 200..1800 |
| MISS | spender | duo | 5 | boss_heroes_down_avg | 1.25 | -..1 |
| PASS | spender | duo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | spender | duo | 5 | boss_level_act2 | 4 | 3..- |
| N/A | spender | duo | 5 | boss_level_act3 | - | 4..- |
| PASS | spender | duo | 5 | gold_act1_end | 121 | 30..300 |
| PASS | spender | duo | 5 | gold_act2_end | 236 | 100..900 |
| N/A | spender | duo | 5 | gold_act3_end | - | 200..1800 |
| MISS | spender | martial | 5 | boss_heroes_down_avg | 3.85 | -..1 |
| PASS | spender | martial | 5 | boss_level_act1 | 2 | 2..- |
| PASS | spender | martial | 5 | boss_level_act2 | 3 | 3..- |
| N/A | spender | martial | 5 | boss_level_act3 | - | 4..- |
| PASS | spender | martial | 5 | gold_act1_end | 120 | 30..300 |
| PASS | spender | martial | 5 | gold_act2_end | 170.5 | 100..900 |
| N/A | spender | martial | 5 | gold_act3_end | - | 200..1800 |
| PASS | spender | solo | 5 | boss_heroes_down_avg | 0.86 | -..1 |
| PASS | spender | solo | 5 | boss_level_act1 | 2 | 2..- |
| N/A | spender | solo | 5 | boss_level_act2 | - | 3..- |
| N/A | spender | solo | 5 | boss_level_act3 | - | 4..- |
| PASS | spender | solo | 5 | gold_act1_end | 135.5 | 30..300 |
| N/A | spender | solo | 5 | gold_act2_end | - | 100..900 |
| N/A | spender | solo | 5 | gold_act3_end | - | 200..1800 |
| MISS | talker | casters | 5 | boss_heroes_down_avg | 1.31 | -..1 |
| PASS | talker | casters | 5 | boss_level_act1 | 2 | 2..- |
| PASS | talker | casters | 5 | boss_level_act2 | 3 | 3..- |
| PASS | talker | casters | 5 | boss_level_act3 | 5 | 4..- |
| PASS | talker | casters | 5 | gold_act1_end | 117 | 30..300 |
| PASS | talker | casters | 5 | gold_act2_end | 150 | 100..900 |
| MISS | talker | casters | 5 | gold_act3_end | 199 | 200..1800 |
| MISS | talker | classic | 5 | boss_heroes_down_avg | 3.6 | -..1 |
| PASS | talker | classic | 5 | boss_level_act1 | 2 | 2..- |
| PASS | talker | classic | 5 | boss_level_act2 | 3 | 3..- |
| PASS | talker | classic | 5 | boss_level_act3 | 5 | 4..- |
| PASS | talker | classic | 5 | gold_act1_end | 115.5 | 30..300 |
| PASS | talker | classic | 5 | gold_act2_end | 213.5 | 100..900 |
| PASS | talker | classic | 5 | gold_act3_end | 261.5 | 200..1800 |
| PASS | talker | duo | 5 | boss_heroes_down_avg | 0.8 | -..1 |
| PASS | talker | duo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | talker | duo | 5 | boss_level_act2 | 4 | 3..- |
| N/A | talker | duo | 5 | boss_level_act3 | - | 4..- |
| PASS | talker | duo | 5 | gold_act1_end | 118 | 30..300 |
| PASS | talker | duo | 5 | gold_act2_end | 172 | 100..900 |
| N/A | talker | duo | 5 | gold_act3_end | - | 200..1800 |
| MISS | talker | martial | 5 | boss_heroes_down_avg | 3.5 | -..1 |
| PASS | talker | martial | 5 | boss_level_act1 | 2 | 2..- |
| PASS | talker | martial | 5 | boss_level_act2 | 3 | 3..- |
| N/A | talker | martial | 5 | boss_level_act3 | - | 4..- |
| PASS | talker | martial | 5 | gold_act1_end | 112 | 30..300 |
| PASS | talker | martial | 5 | gold_act2_end | 145 | 100..900 |
| N/A | talker | martial | 5 | gold_act3_end | - | 200..1800 |
| PASS | talker | solo | 5 | boss_heroes_down_avg | 0.33 | -..1 |
| PASS | talker | solo | 5 | boss_level_act1 | 2 | 2..- |
| N/A | talker | solo | 5 | boss_level_act2 | - | 3..- |
| N/A | talker | solo | 5 | boss_level_act3 | - | 4..- |
| PASS | talker | solo | 5 | gold_act1_end | 129 | 30..300 |
| N/A | talker | solo | 5 | gold_act2_end | - | 100..900 |
| N/A | talker | solo | 5 | gold_act3_end | - | 200..1800 |

</details>
