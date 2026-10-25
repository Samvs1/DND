# M29.6 tuning: scripted full campaigns after tuning (fake storyteller)

Date 2026-10-23. Same grid as the baseline (docs/playtests/M29_baseline.md): **7 styles x 5 parties x
5 seeds = 175 full campaigns**, `python scripts/simulate_party.py --style <styles> --party all --seeds 5
--out saves/balance/M29_tuned` in 4 detached processes; 0 runs failed a check (no exception, silent turn,
softlock, invariant, privacy or replay problem). Runtime: 7322 s of run time (122 min, 12 to 70 s a
campaign), **37 minutes wall clock** on 4 processes. Report: `python scripts/balance_report.py
saves/balance/M29_tuned --markdown [--group style|party]`.

## What changed (data, plus one generic hook each; every step with its metrics in docs/DECISIONS.md M29.6)
- **Cause found**: a spoke whose theme monsters were all over the party's XP budget still fielded the
  cheapest one (so every act-2/3 spoke was deadly for a solo or duo and the act-3 CR 5 spokes were hard
  for four level-4 heroes), and the master is a fixed archetype whose own XP ignored the party (deadly for
  one or two heroes) while its company filled a HARD cap with 5 to 7 bandits and cultists.
- `encounter_budget.json`: `spoke_stand_ins` true (terrain-matched stand-ins inside the budget),
  `spoke_rating_cap` easy for every tier (tiers 2-3 were medium), `spoke_budget_scale` 0.6/0.5/0.5,
  `boss_rating_cap` hard -> medium, `boss_company_max_per_pc` 1, `boss_hp_scale_floor` 0.5 (a master too
  strong alone for the party spawns with hit points x budget / adjusted XP, never below half).
- `dm_tiers.json`: master parley `boss_parley_dc_tiers` medium/hard/hard -> easy/medium/medium (DC
  15/20/20 -> 10/15/15); `xp_by_level` level-4 moderate 500 -> 750 (gives back the act-3 XP the smaller
  spokes no longer pay, so parties meet the last master at level 5).
- SRD stat blocks, monster XP, the encounter thresholds, prices, shops and loot tables are unchanged.

## Headline, baseline -> tuned (175 runs each)
| measure | baseline | tuned | target |
|---|---|---|---|
| campaigns reaching the epilogue | 35/175 | **134/175** | - |
| epilogues: classic / casters / martial | 10 / 23 / 2 (of 35) | 33 / 30 / 28 | - |
| epilogues: duo / solo | 0 / 0 (of 35) | 30 / 13 | a meaningful share |
| balanced clean-win: classic / casters | 0.36 / 0.44 | **0.82 / 0.87 PASS** | 0.75-0.90 |
| balanced clean-win: martial / duo / solo | 0.44 / 0.32 / 0.56 | 0.91 / 0.98 / 0.97 (over the ceiling) | 0.75-0.90 |
| balanced clean-win, all parties pooled | 0.41 | 0.91 (over the ceiling by 0.01) | 0.75-0.90 |
| heroes down per master, all styles: classic / casters / martial | 3.39 / 2.57 / 3.48 | 1.40 / 1.62 / 2.24 | <= 1 |
| heroes down per master, all styles: duo / solo | 0.97 / 0.74 | 0.74 / 0.66 | <= 1 |
| heroes down per master, balanced style (all parties) | 2.44 | **0.97 PASS** | <= 1 |
| talker regions won by alliance | 4 of 49 | 21 of 71 | - |
| talker master parleys won | 4 of 31 | 21 of 55 | - |
| level at the masters (lowest median) | 2 / 3 / 5 | 2 / 3 / 4 (casters; others 5) | 2 / 3 / 4 |
| gold per hero, act ends (pooled medians) | ~120 / 150-180 / 194-270 | 116-132 / 146-264 / 213-485 | placeholder bounds, all PASS |

## What still misses, and why
- **Heroes down per master for four-hero parties (classic 1.40, casters 1.62, martial 2.24 vs <= 1).**
  The walls are now only the masters: the act-3 master (the SRD **mage**, Dark Lantern Room) caused 12 to 16
  of each four-hero party's wipes. It is rated medium at level 5, but its fireball (three 3rd-level slots)
  and cone of cold land on a party that the zone map starts in one zone, and the bots do not spread out
  or focus the caster. The act-2 master (the **wight**, Fogwright's Tower) resists nonmagical weapon damage,
  which the martial party (12 + 9 wipes there) and the solo fighter (52 wipe attempts) carry exclusively;
  the bots do not use oil, fire or radiant options against it. Both are properties of the SRD stat blocks
  and of bot play (the bots use no class features, positioning or concentration), not of the budget, so no
  further budget step would fix them without making every other fight trivial. Left for the M29.4 agent
  playtests: if real play agrees, the lever is the master pick in the plan (data), not the numbers.
- **Clean-win above the 0.90 ceiling for martial, duo and solo (0.91 / 0.98 / 0.97).** One budget scale
  serves every party size; with the SRD small-party multiplier a solo's easy spoke is a single CR 1/8 to
  1/4 creature. Too easy beats too hard here (solo/duo went from 0 to 43 epilogues); a per-size scale
  can come later if the agent playtests find small parties bored.
- **Solo epilogues 13/35.** Solo dies at the masters (wight 52 attempts, bugbear 23, mage 21), all scaled
  to half hit points already; a lone fighter without Second Wind or potions in the bot loses a coin flip
  four times in a row often enough.
- **Gold** stays inside the placeholder bounds; nothing in the gold metrics asked for a loot or price change,
  so shops and loot tables were not touched.

## Targets by style (all parties pooled)
| verdict | style | party | runs | target | value | bounds |
|---|---|---|---|---|---|---|
| MISS | aggressive | all | 25 | boss_heroes_down_avg | 2.02 | -..1 |
| PASS | aggressive | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | aggressive | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | aggressive | all | 25 | boss_level_act3 | 5 | 4..- |
| PASS | aggressive | all | 25 | gold_act1_end | 119 | 30..300 |
| PASS | aggressive | all | 25 | gold_act2_end | 268 | 100..900 |
| PASS | aggressive | all | 25 | gold_act3_end | 358 | 200..1800 |
| MISS | balanced | all | 25 | normal_clean_win_rate | 0.91 | 0.75..0.9 |
| PASS | balanced | all | 25 | boss_heroes_down_avg | 0.97 | -..1 |
| PASS | balanced | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | balanced | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | balanced | all | 25 | boss_level_act3 | 4 | 4..- |
| PASS | balanced | all | 25 | gold_act1_end | 118.5 | 30..300 |
| PASS | balanced | all | 25 | gold_act2_end | 174 | 100..900 |
| PASS | balanced | all | 25 | gold_act3_end | 329 | 200..1800 |
| MISS | cautious | all | 25 | boss_heroes_down_avg | 1.48 | -..1 |
| PASS | cautious | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | cautious | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | cautious | all | 25 | boss_level_act3 | 5 | 4..- |
| PASS | cautious | all | 25 | gold_act1_end | 117.5 | 30..300 |
| PASS | cautious | all | 25 | gold_act2_end | 171 | 100..900 |
| PASS | cautious | all | 25 | gold_act3_end | 328 | 200..1800 |
| MISS | cunning | all | 25 | boss_heroes_down_avg | 1.08 | -..1 |
| PASS | cunning | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | cunning | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | cunning | all | 25 | boss_level_act3 | 5 | 4..- |
| PASS | cunning | all | 25 | gold_act1_end | 117 | 30..300 |
| PASS | cunning | all | 25 | gold_act2_end | 155 | 100..900 |
| PASS | cunning | all | 25 | gold_act3_end | 248 | 200..1800 |
| PASS | hoarder | all | 25 | boss_heroes_down_avg | 1 | -..1 |
| PASS | hoarder | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | hoarder | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | hoarder | all | 25 | boss_level_act3 | 4 | 4..- |
| PASS | hoarder | all | 25 | gold_act1_end | 118.5 | 30..300 |
| PASS | hoarder | all | 25 | gold_act2_end | 183 | 100..900 |
| PASS | hoarder | all | 25 | gold_act3_end | 306.5 | 200..1800 |
| PASS | spender | all | 25 | boss_heroes_down_avg | 1 | -..1 |
| PASS | spender | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | spender | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | spender | all | 25 | boss_level_act3 | 4 | 4..- |
| PASS | spender | all | 25 | gold_act1_end | 118 | 30..300 |
| PASS | spender | all | 25 | gold_act2_end | 103.5 | 100..900 |
| PASS | spender | all | 25 | gold_act3_end | 230.5 | 200..1800 |
| MISS | talker | all | 25 | boss_heroes_down_avg | 1.03 | -..1 |
| PASS | talker | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | talker | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | talker | all | 25 | boss_level_act3 | 5 | 4..- |
| PASS | talker | all | 25 | gold_act1_end | 109 | 30..300 |
| PASS | talker | all | 25 | gold_act2_end | 147 | 100..900 |
| PASS | talker | all | 25 | gold_act3_end | 222 | 200..1800 |

## Targets by party (all styles pooled; the clean-win target is defined for the balanced style only)
| verdict | style | party | runs | target | value | bounds |
|---|---|---|---|---|---|---|
| MISS | all | casters | 35 | boss_heroes_down_avg | 1.62 | -..1 |
| PASS | all | casters | 35 | boss_level_act1 | 2 | 2..- |
| PASS | all | casters | 35 | boss_level_act2 | 3 | 3..- |
| PASS | all | casters | 35 | boss_level_act3 | 4 | 4..- |
| PASS | all | casters | 35 | gold_act1_end | 116.5 | 30..300 |
| PASS | all | casters | 35 | gold_act2_end | 146 | 100..900 |
| PASS | all | casters | 35 | gold_act3_end | 232.5 | 200..1800 |
| MISS | all | classic | 35 | boss_heroes_down_avg | 1.4 | -..1 |
| PASS | all | classic | 35 | boss_level_act1 | 2 | 2..- |
| PASS | all | classic | 35 | boss_level_act2 | 3 | 3..- |
| PASS | all | classic | 35 | boss_level_act3 | 5 | 4..- |
| PASS | all | classic | 35 | gold_act1_end | 116 | 30..300 |
| PASS | all | classic | 35 | gold_act2_end | 147 | 100..900 |
| PASS | all | classic | 35 | gold_act3_end | 214 | 200..1800 |
| PASS | all | duo | 35 | boss_heroes_down_avg | 0.74 | -..1 |
| PASS | all | duo | 35 | boss_level_act1 | 2 | 2..- |
| PASS | all | duo | 35 | boss_level_act2 | 3 | 3..- |
| PASS | all | duo | 35 | boss_level_act3 | 5 | 4..- |
| PASS | all | duo | 35 | gold_act1_end | 120 | 30..300 |
| PASS | all | duo | 35 | gold_act2_end | 179 | 100..900 |
| PASS | all | duo | 35 | gold_act3_end | 306.5 | 200..1800 |
| MISS | all | martial | 35 | boss_heroes_down_avg | 2.24 | -..1 |
| PASS | all | martial | 35 | boss_level_act1 | 2 | 2..- |
| PASS | all | martial | 35 | boss_level_act2 | 3 | 3..- |
| PASS | all | martial | 35 | boss_level_act3 | 5 | 4..- |
| PASS | all | martial | 35 | gold_act1_end | 117 | 30..300 |
| PASS | all | martial | 35 | gold_act2_end | 151 | 100..900 |
| PASS | all | martial | 35 | gold_act3_end | 213 | 200..1800 |
| PASS | all | solo | 35 | boss_heroes_down_avg | 0.66 | -..1 |
| PASS | all | solo | 35 | boss_level_act1 | 2 | 2..- |
| PASS | all | solo | 35 | boss_level_act2 | 4 | 3..- |
| PASS | all | solo | 35 | boss_level_act3 | 5 | 4..- |
| PASS | all | solo | 35 | gold_act1_end | 132 | 30..300 |
| PASS | all | solo | 35 | gold_act2_end | 264 | 100..900 |
| PASS | all | solo | 35 | gold_act3_end | 485 | 200..1800 |

## How the runs ended (per style and party)
| style | party | runs | epilogue | lost for good | top level (median) | wipes/run |
|---|---|---|---|---|---|---|
| aggressive | casters | 5 | 3 | act 1: 1, act 3: 1 | 5 | 2 |
| aggressive | classic | 5 | 4 | act 3: 1 | 5 | 1.8 |
| aggressive | duo | 5 | 3 | act 2: 2 | 5 | 2.6 |
| aggressive | martial | 5 | 2 | act 1: 1, act 2: 1, act 3: 1 | 5 | 2 |
| aggressive | solo | 5 | 1 | act 2: 2, act 3: 2 | 5 | 5.4 |
| balanced | casters | 5 | 4 | act 3: 1 | 5 | 0.6 |
| balanced | classic | 5 | 4 | act 3: 1 | 5 | 0.6 |
| balanced | duo | 5 | 5 | - | 5 | 0.2 |
| balanced | martial | 5 | 5 | - | 5 | 0.6 |
| balanced | solo | 5 | 2 | act 1: 1, act 2: 1, act 3: 1 | 5 | 3.2 |
| cautious | casters | 5 | 5 | - | 5 | 0.2 |
| cautious | classic | 5 | 5 | - | 5 | 1.2 |
| cautious | duo | 5 | 2 | act 3: 3 | 5 | 2 |
| cautious | martial | 5 | 3 | act 1: 1, act 2: 1 | 5 | 1.8 |
| cautious | solo | 5 | 3 | act 2: 2 | 5 | 2.2 |
| cunning | casters | 5 | 5 | - | 5 | 0.2 |
| cunning | classic | 5 | 5 | - | 5 | 0.2 |
| cunning | duo | 5 | 5 | - | 5 | 1.6 |
| cunning | martial | 5 | 3 | act 2: 2 | 5 | 1.2 |
| cunning | solo | 5 | 0 | act 1: 1, act 2: 4 | 4 | 3.4 |
| hoarder | casters | 5 | 4 | act 3: 1 | 5 | 0.8 |
| hoarder | classic | 5 | 5 | - | 5 | 0 |
| hoarder | duo | 5 | 5 | - | 5 | 0.6 |
| hoarder | martial | 5 | 5 | - | 5 | 0.6 |
| hoarder | solo | 5 | 1 | act 1: 1, act 2: 1, act 3: 2 | 5 | 2.8 |
| spender | casters | 5 | 4 | act 3: 1 | 5 | 0.6 |
| spender | classic | 5 | 5 | - | 5 | 0.4 |
| spender | duo | 5 | 5 | - | 5 | 0.6 |
| spender | martial | 5 | 5 | - | 5 | 0.8 |
| spender | solo | 5 | 3 | act 1: 1, act 3: 1 | 5 | 1.8 |
| talker | casters | 5 | 5 | - | 5 | 0 |
| talker | classic | 5 | 5 | - | 5 | 1 |
| talker | duo | 5 | 5 | - | 5 | 0.4 |
| talker | martial | 5 | 5 | - | 5 | 0.8 |
| talker | solo | 5 | 3 | act 2: 2 | 5 | 2 |

<details><summary>Every target per style and party</summary>

| verdict | style | party | runs | target | value | bounds |
|---|---|---|---|---|---|---|
| MISS | aggressive | casters | 5 | boss_heroes_down_avg | 2.78 | -..1 |
| PASS | aggressive | casters | 5 | boss_level_act1 | 2 | 2..- |
| PASS | aggressive | casters | 5 | boss_level_act2 | 3 | 3..- |
| PASS | aggressive | casters | 5 | boss_level_act3 | 5 | 4..- |
| PASS | aggressive | casters | 5 | gold_act1_end | 118 | 30..300 |
| PASS | aggressive | casters | 5 | gold_act2_end | 219.5 | 100..900 |
| PASS | aggressive | casters | 5 | gold_act3_end | 358 | 200..1800 |
| MISS | aggressive | classic | 5 | boss_heroes_down_avg | 2.52 | -..1 |
| PASS | aggressive | classic | 5 | boss_level_act1 | 2 | 2..- |
| PASS | aggressive | classic | 5 | boss_level_act2 | 3 | 3..- |
| PASS | aggressive | classic | 5 | boss_level_act3 | 5 | 4..- |
| PASS | aggressive | classic | 5 | gold_act1_end | 117 | 30..300 |
| PASS | aggressive | classic | 5 | gold_act2_end | 149 | 100..900 |
| PASS | aggressive | classic | 5 | gold_act3_end | 212 | 200..1800 |
| MISS | aggressive | duo | 5 | boss_heroes_down_avg | 1.31 | -..1 |
| PASS | aggressive | duo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | aggressive | duo | 5 | boss_level_act2 | 3 | 3..- |
| PASS | aggressive | duo | 5 | boss_level_act3 | 5 | 4..- |
| PASS | aggressive | duo | 5 | gold_act1_end | 120 | 30..300 |
| PASS | aggressive | duo | 5 | gold_act2_end | 313 | 100..900 |
| PASS | aggressive | duo | 5 | gold_act3_end | 425 | 200..1800 |
| MISS | aggressive | martial | 5 | boss_heroes_down_avg | 3.64 | -..1 |
| PASS | aggressive | martial | 5 | boss_level_act1 | 2 | 2..- |
| PASS | aggressive | martial | 5 | boss_level_act2 | 3 | 3..- |
| PASS | aggressive | martial | 5 | boss_level_act3 | 5 | 4..- |
| PASS | aggressive | martial | 5 | gold_act1_end | 120.5 | 30..300 |
| PASS | aggressive | martial | 5 | gold_act2_end | 300 | 100..900 |
| PASS | aggressive | martial | 5 | gold_act3_end | 366.5 | 200..1800 |
| PASS | aggressive | solo | 5 | boss_heroes_down_avg | 0.75 | -..1 |
| PASS | aggressive | solo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | aggressive | solo | 5 | boss_level_act2 | 4 | 3..- |
| PASS | aggressive | solo | 5 | boss_level_act3 | 5 | 4..- |
| PASS | aggressive | solo | 5 | gold_act1_end | 138 | 30..300 |
| PASS | aggressive | solo | 5 | gold_act2_end | 245 | 100..900 |
| PASS | aggressive | solo | 5 | gold_act3_end | 477 | 200..1800 |
| PASS | balanced | casters | 5 | normal_clean_win_rate | 0.87 | 0.75..0.9 |
| MISS | balanced | casters | 5 | boss_heroes_down_avg | 1.72 | -..1 |
| PASS | balanced | casters | 5 | boss_level_act1 | 2 | 2..- |
| PASS | balanced | casters | 5 | boss_level_act2 | 3 | 3..- |
| PASS | balanced | casters | 5 | boss_level_act3 | 4 | 4..- |
| PASS | balanced | casters | 5 | gold_act1_end | 115 | 30..300 |
| PASS | balanced | casters | 5 | gold_act2_end | 149 | 100..900 |
| PASS | balanced | casters | 5 | gold_act3_end | 297.5 | 200..1800 |
| PASS | balanced | classic | 5 | normal_clean_win_rate | 0.82 | 0.75..0.9 |
| MISS | balanced | classic | 5 | boss_heroes_down_avg | 1.11 | -..1 |
| PASS | balanced | classic | 5 | boss_level_act1 | 2 | 2..- |
| PASS | balanced | classic | 5 | boss_level_act2 | 4 | 3..- |
| PASS | balanced | classic | 5 | boss_level_act3 | 5 | 4..- |
| PASS | balanced | classic | 5 | gold_act1_end | 119 | 30..300 |
| PASS | balanced | classic | 5 | gold_act2_end | 153 | 100..900 |
| PASS | balanced | classic | 5 | gold_act3_end | 291.5 | 200..1800 |
| MISS | balanced | duo | 5 | normal_clean_win_rate | 0.98 | 0.75..0.9 |
| PASS | balanced | duo | 5 | boss_heroes_down_avg | 0.25 | -..1 |
| PASS | balanced | duo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | balanced | duo | 5 | boss_level_act2 | 3 | 3..- |
| PASS | balanced | duo | 5 | boss_level_act3 | 5 | 4..- |
| PASS | balanced | duo | 5 | gold_act1_end | 117 | 30..300 |
| PASS | balanced | duo | 5 | gold_act2_end | 174 | 100..900 |
| PASS | balanced | duo | 5 | gold_act3_end | 305 | 200..1800 |
| MISS | balanced | martial | 5 | normal_clean_win_rate | 0.91 | 0.75..0.9 |
| MISS | balanced | martial | 5 | boss_heroes_down_avg | 1.17 | -..1 |
| PASS | balanced | martial | 5 | boss_level_act1 | 2 | 2..- |
| PASS | balanced | martial | 5 | boss_level_act2 | 3 | 3..- |
| PASS | balanced | martial | 5 | boss_level_act3 | 5 | 4..- |
| PASS | balanced | martial | 5 | gold_act1_end | 119 | 30..300 |
| PASS | balanced | martial | 5 | gold_act2_end | 152 | 100..900 |
| PASS | balanced | martial | 5 | gold_act3_end | 214 | 200..1800 |
| MISS | balanced | solo | 5 | normal_clean_win_rate | 0.97 | 0.75..0.9 |
| PASS | balanced | solo | 5 | boss_heroes_down_avg | 0.67 | -..1 |
| PASS | balanced | solo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | balanced | solo | 5 | boss_level_act2 | 4 | 3..- |
| PASS | balanced | solo | 5 | boss_level_act3 | 5 | 4..- |
| PASS | balanced | solo | 5 | gold_act1_end | 133 | 30..300 |
| PASS | balanced | solo | 5 | gold_act2_end | 245 | 100..900 |
| PASS | balanced | solo | 5 | gold_act3_end | 470 | 200..1800 |
| MISS | cautious | casters | 5 | boss_heroes_down_avg | 1.12 | -..1 |
| PASS | cautious | casters | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cautious | casters | 5 | boss_level_act2 | 3 | 3..- |
| PASS | cautious | casters | 5 | boss_level_act3 | 5 | 4..- |
| PASS | cautious | casters | 5 | gold_act1_end | 117 | 30..300 |
| PASS | cautious | casters | 5 | gold_act2_end | 140 | 100..900 |
| PASS | cautious | casters | 5 | gold_act3_end | 221 | 200..1800 |
| MISS | cautious | classic | 5 | boss_heroes_down_avg | 1.86 | -..1 |
| PASS | cautious | classic | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cautious | classic | 5 | boss_level_act2 | 3 | 3..- |
| PASS | cautious | classic | 5 | boss_level_act3 | 5 | 4..- |
| PASS | cautious | classic | 5 | gold_act1_end | 117 | 30..300 |
| PASS | cautious | classic | 5 | gold_act2_end | 144 | 100..900 |
| PASS | cautious | classic | 5 | gold_act3_end | 204 | 200..1800 |
| MISS | cautious | duo | 5 | boss_heroes_down_avg | 1.16 | -..1 |
| PASS | cautious | duo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cautious | duo | 5 | boss_level_act2 | 3 | 3..- |
| PASS | cautious | duo | 5 | boss_level_act3 | 5 | 4..- |
| PASS | cautious | duo | 5 | gold_act1_end | 120 | 30..300 |
| PASS | cautious | duo | 5 | gold_act2_end | 171 | 100..900 |
| PASS | cautious | duo | 5 | gold_act3_end | 374.5 | 200..1800 |
| MISS | cautious | martial | 5 | boss_heroes_down_avg | 2.81 | -..1 |
| PASS | cautious | martial | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cautious | martial | 5 | boss_level_act2 | 3 | 3..- |
| PASS | cautious | martial | 5 | boss_level_act3 | 5 | 4..- |
| PASS | cautious | martial | 5 | gold_act1_end | 117 | 30..300 |
| PASS | cautious | martial | 5 | gold_act2_end | 153 | 100..900 |
| PASS | cautious | martial | 5 | gold_act3_end | 226 | 200..1800 |
| PASS | cautious | solo | 5 | boss_heroes_down_avg | 0.52 | -..1 |
| PASS | cautious | solo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cautious | solo | 5 | boss_level_act2 | 4 | 3..- |
| PASS | cautious | solo | 5 | boss_level_act3 | 5 | 4..- |
| PASS | cautious | solo | 5 | gold_act1_end | 132 | 30..300 |
| PASS | cautious | solo | 5 | gold_act2_end | 388 | 100..900 |
| PASS | cautious | solo | 5 | gold_act3_end | 611 | 200..1800 |
| PASS | cunning | casters | 5 | boss_heroes_down_avg | 0.5 | -..1 |
| PASS | cunning | casters | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cunning | casters | 5 | boss_level_act2 | 4 | 3..- |
| PASS | cunning | casters | 5 | boss_level_act3 | 5 | 4..- |
| PASS | cunning | casters | 5 | gold_act1_end | 116 | 30..300 |
| PASS | cunning | casters | 5 | gold_act2_end | 145 | 100..900 |
| PASS | cunning | casters | 5 | gold_act3_end | 213 | 200..1800 |
| PASS | cunning | classic | 5 | boss_heroes_down_avg | 0.94 | -..1 |
| PASS | cunning | classic | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cunning | classic | 5 | boss_level_act2 | 3 | 3..- |
| PASS | cunning | classic | 5 | boss_level_act3 | 5 | 4..- |
| PASS | cunning | classic | 5 | gold_act1_end | 116 | 30..300 |
| PASS | cunning | classic | 5 | gold_act2_end | 147 | 100..900 |
| PASS | cunning | classic | 5 | gold_act3_end | 214 | 200..1800 |
| PASS | cunning | duo | 5 | boss_heroes_down_avg | 0.7 | -..1 |
| PASS | cunning | duo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cunning | duo | 5 | boss_level_act2 | 4 | 3..- |
| PASS | cunning | duo | 5 | boss_level_act3 | 5 | 4..- |
| PASS | cunning | duo | 5 | gold_act1_end | 120 | 30..300 |
| PASS | cunning | duo | 5 | gold_act2_end | 180 | 100..900 |
| PASS | cunning | duo | 5 | gold_act3_end | 308 | 200..1800 |
| MISS | cunning | martial | 5 | boss_heroes_down_avg | 2.47 | -..1 |
| PASS | cunning | martial | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cunning | martial | 5 | boss_level_act2 | 3 | 3..- |
| PASS | cunning | martial | 5 | boss_level_act3 | 5 | 4..- |
| PASS | cunning | martial | 5 | gold_act1_end | 116 | 30..300 |
| PASS | cunning | martial | 5 | gold_act2_end | 144 | 100..900 |
| PASS | cunning | martial | 5 | gold_act3_end | 204 | 200..1800 |
| PASS | cunning | solo | 5 | boss_heroes_down_avg | 0.85 | -..1 |
| PASS | cunning | solo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | cunning | solo | 5 | boss_level_act2 | 4 | 3..- |
| N/A | cunning | solo | 5 | boss_level_act3 | - | 4..- |
| PASS | cunning | solo | 5 | gold_act1_end | 134 | 30..300 |
| N/A | cunning | solo | 5 | gold_act2_end | - | 100..900 |
| N/A | cunning | solo | 5 | gold_act3_end | - | 200..1800 |
| MISS | hoarder | casters | 5 | boss_heroes_down_avg | 1.95 | -..1 |
| PASS | hoarder | casters | 5 | boss_level_act1 | 2 | 2..- |
| PASS | hoarder | casters | 5 | boss_level_act2 | 3 | 3..- |
| PASS | hoarder | casters | 5 | boss_level_act3 | 4 | 4..- |
| PASS | hoarder | casters | 5 | gold_act1_end | 116 | 30..300 |
| PASS | hoarder | casters | 5 | gold_act2_end | 146 | 100..900 |
| PASS | hoarder | casters | 5 | gold_act3_end | 295 | 200..1800 |
| PASS | hoarder | classic | 5 | boss_heroes_down_avg | 0.4 | -..1 |
| PASS | hoarder | classic | 5 | boss_level_act1 | 2 | 2..- |
| PASS | hoarder | classic | 5 | boss_level_act2 | 3 | 3..- |
| PASS | hoarder | classic | 5 | boss_level_act3 | 5 | 4..- |
| PASS | hoarder | classic | 5 | gold_act1_end | 116 | 30..300 |
| PASS | hoarder | classic | 5 | gold_act2_end | 145 | 100..900 |
| PASS | hoarder | classic | 5 | gold_act3_end | 216 | 200..1800 |
| PASS | hoarder | duo | 5 | boss_heroes_down_avg | 0.44 | -..1 |
| PASS | hoarder | duo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | hoarder | duo | 5 | boss_level_act2 | 3 | 3..- |
| PASS | hoarder | duo | 5 | boss_level_act3 | 5 | 4..- |
| PASS | hoarder | duo | 5 | gold_act1_end | 121 | 30..300 |
| PASS | hoarder | duo | 5 | gold_act2_end | 183 | 100..900 |
| PASS | hoarder | duo | 5 | gold_act3_end | 311 | 200..1800 |
| MISS | hoarder | martial | 5 | boss_heroes_down_avg | 1.5 | -..1 |
| PASS | hoarder | martial | 5 | boss_level_act1 | 2 | 2..- |
| PASS | hoarder | martial | 5 | boss_level_act2 | 3 | 3..- |
| PASS | hoarder | martial | 5 | boss_level_act3 | 5 | 4..- |
| PASS | hoarder | martial | 5 | gold_act1_end | 118 | 30..300 |
| PASS | hoarder | martial | 5 | gold_act2_end | 147 | 100..900 |
| PASS | hoarder | martial | 5 | gold_act3_end | 208 | 200..1800 |
| PASS | hoarder | solo | 5 | boss_heroes_down_avg | 0.68 | -..1 |
| PASS | hoarder | solo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | hoarder | solo | 5 | boss_level_act2 | 4 | 3..- |
| PASS | hoarder | solo | 5 | boss_level_act3 | 5 | 4..- |
| PASS | hoarder | solo | 5 | gold_act1_end | 130.5 | 30..300 |
| PASS | hoarder | solo | 5 | gold_act2_end | 264 | 100..900 |
| PASS | hoarder | solo | 5 | gold_act3_end | 576 | 200..1800 |
| MISS | spender | casters | 5 | boss_heroes_down_avg | 1.72 | -..1 |
| PASS | spender | casters | 5 | boss_level_act1 | 2 | 2..- |
| PASS | spender | casters | 5 | boss_level_act2 | 3 | 3..- |
| PASS | spender | casters | 5 | boss_level_act3 | 4 | 4..- |
| PASS | spender | casters | 5 | gold_act1_end | 118 | 30..300 |
| MISS | spender | casters | 5 | gold_act2_end | 49 | 100..900 |
| MISS | spender | casters | 5 | gold_act3_end | 187 | 200..1800 |
| PASS | spender | classic | 5 | boss_heroes_down_avg | 0.56 | -..1 |
| PASS | spender | classic | 5 | boss_level_act1 | 2 | 2..- |
| PASS | spender | classic | 5 | boss_level_act2 | 4 | 3..- |
| PASS | spender | classic | 5 | boss_level_act3 | 5 | 4..- |
| PASS | spender | classic | 5 | gold_act1_end | 118 | 30..300 |
| MISS | spender | classic | 5 | gold_act2_end | 46 | 100..900 |
| MISS | spender | classic | 5 | gold_act3_end | 123 | 200..1800 |
| PASS | spender | duo | 5 | boss_heroes_down_avg | 0.39 | -..1 |
| PASS | spender | duo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | spender | duo | 5 | boss_level_act2 | 3 | 3..- |
| PASS | spender | duo | 5 | boss_level_act3 | 5 | 4..- |
| PASS | spender | duo | 5 | gold_act1_end | 120 | 30..300 |
| MISS | spender | duo | 5 | gold_act2_end | 78 | 100..900 |
| PASS | spender | duo | 5 | gold_act3_end | 211 | 200..1800 |
| MISS | spender | martial | 5 | boss_heroes_down_avg | 1.84 | -..1 |
| PASS | spender | martial | 5 | boss_level_act1 | 2 | 2..- |
| PASS | spender | martial | 5 | boss_level_act2 | 3 | 3..- |
| PASS | spender | martial | 5 | boss_level_act3 | 5 | 4..- |
| PASS | spender | martial | 5 | gold_act1_end | 117 | 30..300 |
| MISS | spender | martial | 5 | gold_act2_end | 48 | 100..900 |
| MISS | spender | martial | 5 | gold_act3_end | 100 | 200..1800 |
| PASS | spender | solo | 5 | boss_heroes_down_avg | 0.48 | -..1 |
| PASS | spender | solo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | spender | solo | 5 | boss_level_act2 | 4 | 3..- |
| PASS | spender | solo | 5 | boss_level_act3 | 5 | 4..- |
| PASS | spender | solo | 5 | gold_act1_end | 133.5 | 30..300 |
| PASS | spender | solo | 5 | gold_act2_end | 200 | 100..900 |
| PASS | spender | solo | 5 | gold_act3_end | 485 | 200..1800 |
| PASS | talker | casters | 5 | boss_heroes_down_avg | 0.5 | -..1 |
| PASS | talker | casters | 5 | boss_level_act1 | 2 | 2..- |
| PASS | talker | casters | 5 | boss_level_act2 | 4 | 3..- |
| PASS | talker | casters | 5 | boss_level_act3 | 5 | 4..- |
| PASS | talker | casters | 5 | gold_act1_end | 110 | 30..300 |
| PASS | talker | casters | 5 | gold_act2_end | 128 | 100..900 |
| PASS | talker | casters | 5 | gold_act3_end | 202 | 200..1800 |
| MISS | talker | classic | 5 | boss_heroes_down_avg | 1.76 | -..1 |
| PASS | talker | classic | 5 | boss_level_act1 | 2 | 2..- |
| PASS | talker | classic | 5 | boss_level_act2 | 3 | 3..- |
| PASS | talker | classic | 5 | boss_level_act3 | 5 | 4..- |
| PASS | talker | classic | 5 | gold_act1_end | 101 | 30..300 |
| PASS | talker | classic | 5 | gold_act2_end | 140 | 100..900 |
| PASS | talker | classic | 5 | gold_act3_end | 215 | 200..1800 |
| PASS | talker | duo | 5 | boss_heroes_down_avg | 0.33 | -..1 |
| PASS | talker | duo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | talker | duo | 5 | boss_level_act2 | 4 | 3..- |
| PASS | talker | duo | 5 | boss_level_act3 | 5 | 4..- |
| PASS | talker | duo | 5 | gold_act1_end | 100 | 30..300 |
| PASS | talker | duo | 5 | gold_act2_end | 151 | 100..900 |
| PASS | talker | duo | 5 | gold_act3_end | 269 | 200..1800 |
| MISS | talker | martial | 5 | boss_heroes_down_avg | 1.71 | -..1 |
| PASS | talker | martial | 5 | boss_level_act1 | 2 | 2..- |
| PASS | talker | martial | 5 | boss_level_act2 | 4 | 3..- |
| PASS | talker | martial | 5 | boss_level_act3 | 5 | 4..- |
| PASS | talker | martial | 5 | gold_act1_end | 106 | 30..300 |
| PASS | talker | martial | 5 | gold_act2_end | 129 | 100..900 |
| MISS | talker | martial | 5 | gold_act3_end | 188 | 200..1800 |
| PASS | talker | solo | 5 | boss_heroes_down_avg | 0.6 | -..1 |
| PASS | talker | solo | 5 | boss_level_act1 | 2 | 2..- |
| PASS | talker | solo | 5 | boss_level_act2 | 4 | 3..- |
| PASS | talker | solo | 5 | boss_level_act3 | 5 | 4..- |
| PASS | talker | solo | 5 | gold_act1_end | 129 | 30..300 |
| PASS | talker | solo | 5 | gold_act2_end | 326 | 100..900 |
| PASS | talker | solo | 5 | gold_act3_end | 542 | 200..1800 |


</details>

# M29.6b: balance from the live playtests (2026-10-23)

Same grid: **7 styles x 5 parties x 5 seeds = 175 full campaigns** on the fake storyteller,
`python scripts/simulate_party.py --style <styles> --party all --seeds 5 --out saves/balance/M29b_final`
in 4 detached processes, **36 minutes wall clock** (16:06-16:42); 0 runs failed a check. Report:
`python scripts/balance_report.py saves/balance/M29b_final --markdown [--group style|party]`.
Before = the M29.6 grid above (saves/balance/M29_tuned, re-read with today's metrics). Each change
and its slice numbers are in docs/DECISIONS.md (M29.6b).

## What changed
1. **XP curve** (p3 level 5 by action 203; milestones 75-800 vs fights 12-175): spoke and region
   milestones followed the party level, so each level raised the next payout. Now fixed per region
   tier (`dm_tiers.milestone_xp`: visit/clear/region 50/100/150, 100/200/600, 400/800/1000, final
   +1600). New metric `master_levels` and targets `master_level_act1..3` [2] [3] [4-5] (every style;
   the talker rows are the talk path).
2. **Gift deeds** (one candle five times made a master an ally): a repeat item earns no deed, nor
   a minor gift past `gift_deeds_per_npc` 2 (`WorldNpc.gifts`).
3. **Dragon labels** (wyrmling "trivial", young black dragon "medium"): a breath weapon is rated by
   its average damage over the heroes' average max HP (`area_damage_rating` 0.4/0.6/0.9); the label
   is the higher rating; spokes never field a breath over their cap; such a master comes alone and
   the plan check `boss_area` refuses it (the prompt lists 12 "never a boss" monsters).
4. **Shops**: a general store always has a weapon, an armour, a Herbal Poultice (10 gp) and a
   Traveller's Tonic (25 gp) besides the SRD Potion of Healing (50 gp); every region needs a trader
   that sells weapons, armour and potions (else a peddler).
5. **DC 20 gate**: requested checks and new locks are capped per region tier (medium / hard / very
   hard; `check_dc_tier_cap`).
6. **Masters at the planned level** (found by the first grid, saves/balance/M29b_first: the act-2
   wight met at level 3 instead of 4 raised balanced heroes down per master 0.97 -> 1.36):
   `boss_budget_scale` {1: 0.8, 2: 0.45, 3: 0.6} on the boss cap (company and hit point scale).

## Headline, M29.6 -> M29.6b (175 runs each)
| measure | M29.6 | M29.6b | target |
|---|---|---|---|
| campaigns reaching the epilogue | 134/175 | **140/175** | - |
| epilogues: classic / casters / martial | 33 / 30 / 28 | 35 / 35 / 33 (of 35) | - |
| epilogues: duo / solo | 30 / 13 | 27 / 10 | a meaningful share |
| median level at the masters, every style | 2 / **4** / 5 | **2 / 3 / 5** (talker 2 / 3 / 4) | 2 / 3 / 4-5 |
| XP per hero to the epilogue (median) | 10500-13100 | 9400-10100 | - |
| XP share from fights (median) | 0.09-0.11 | 0.11-0.14 | not the only route |
| balanced clean-win: classic / casters | 0.82 / 0.87 | **0.82 / 0.84 PASS** | 0.75-0.90 |
| balanced clean-win: martial / duo / solo / pooled | 0.91 / 0.98 / 0.97 / 0.91 | 0.91 / 1.00 / 0.95 / 0.90 | 0.75-0.90 |
| heroes down per master, balanced (all parties) | 0.97 | **0.67 PASS** | <= 1 |
| heroes down per master, all styles: classic / casters / martial | 1.40 / 1.62 / 2.24 | 1.08 / **0.39** / 1.20 | <= 1 |
| heroes down per master, all styles: duo / solo | 0.74 / 0.66 | 0.88 / 0.73 | <= 1 |
| talker regions won by alliance | 21 of 71 | 24 of 69 | - |
| gold per hero at act ends (pooled medians) | 116-132 / 146-264 / 213-485 | 113-130 / 143-289 / 203-500 | spender act 3 95 (MISS) |

## What still misses, and why
- **Clean-win over the 0.90 ceiling** for martial, duo, solo and the balanced pool (0.90): spokes
  were not touched (M29.6 note stands: too easy beats too hard for small parties).
- **Heroes down per master, classic 1.08 (balanced 1.42), martial 1.20, aggressive 1.29**: the
  act-2 wight at the planned level 3 (classic 2.1 downs there; resists nonmagical weapons, which
  bots never answer with oil, fire or radiant) and the mage's fireball on a party starting in one
  zone. Scaling further would make the masters trivial for casters and duos (0.39 / 0.88 now).
  Round 2 of the live playtests decides; the lever stays the master pick or the boss scale (data).
- **Spender gold at act 3 (95 vs >= 200)**: general stores now sell weapons, armour and cheap
  healing, so the spender style spends 1.8x more (shop buys 3760-3890 vs 2070-2210 gold over
  five four-hero runs). That is the shop fix working; every other style passes.
- **Solo epilogues 10/35** (13 before): 20 of the 25 lost solo runs end at Fogwright's Tower, the act-2 wight (already at half hit points for one hero), now met at level 3 instead of 4; 4 at the act-1 bugbear, 1 at the mage. Duo loses 5 of its 8 there. A per-size boss scale is the data lever if round 2 agrees.

## Targets by style (all parties pooled)
| verdict | style | party | runs | target | value | bounds |
|---|---|---|---|---|---|---|
| MISS | aggressive | all | 25 | boss_heroes_down_avg | 1.29 | -..1 |
| PASS | aggressive | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | aggressive | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | aggressive | all | 25 | boss_level_act3 | 4 | 4..- |
| PASS | aggressive | all | 25 | master_level_act1 | 2 | 2..2 |
| PASS | aggressive | all | 25 | master_level_act2 | 3 | 3..3 |
| PASS | aggressive | all | 25 | master_level_act3 | 5 | 4..5 |
| PASS | aggressive | all | 25 | gold_act1_end | 117 | 30..300 |
| PASS | aggressive | all | 25 | gold_act2_end | 146 | 100..900 |
| PASS | aggressive | all | 25 | gold_act3_end | 212.5 | 200..1800 |
| MISS | balanced | all | 25 | normal_clean_win_rate | 0.9 | 0.75..0.9 |
| PASS | balanced | all | 25 | boss_heroes_down_avg | 0.67 | -..1 |
| PASS | balanced | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | balanced | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | balanced | all | 25 | boss_level_act3 | 4 | 4..- |
| PASS | balanced | all | 25 | master_level_act1 | 2 | 2..2 |
| PASS | balanced | all | 25 | master_level_act2 | 3 | 3..3 |
| PASS | balanced | all | 25 | master_level_act3 | 5 | 4..5 |
| PASS | balanced | all | 25 | gold_act1_end | 115 | 30..300 |
| PASS | balanced | all | 25 | gold_act2_end | 188 | 100..900 |
| PASS | balanced | all | 25 | gold_act3_end | 311 | 200..1800 |
| PASS | cautious | all | 25 | boss_heroes_down_avg | 0.91 | -..1 |
| PASS | cautious | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | cautious | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | cautious | all | 25 | boss_level_act3 | 4 | 4..- |
| PASS | cautious | all | 25 | master_level_act1 | 2 | 2..2 |
| PASS | cautious | all | 25 | master_level_act2 | 3 | 3..3 |
| PASS | cautious | all | 25 | master_level_act3 | 5 | 4..5 |
| PASS | cautious | all | 25 | gold_act1_end | 115 | 30..300 |
| PASS | cautious | all | 25 | gold_act2_end | 210.5 | 100..900 |
| PASS | cautious | all | 25 | gold_act3_end | 327.5 | 200..1800 |
| PASS | cunning | all | 25 | boss_heroes_down_avg | 0.59 | -..1 |
| PASS | cunning | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | cunning | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | cunning | all | 25 | boss_level_act3 | 5 | 4..- |
| PASS | cunning | all | 25 | master_level_act1 | 2 | 2..2 |
| PASS | cunning | all | 25 | master_level_act2 | 3 | 3..3 |
| PASS | cunning | all | 25 | master_level_act3 | 5 | 4..5 |
| PASS | cunning | all | 25 | gold_act1_end | 115.5 | 30..300 |
| PASS | cunning | all | 25 | gold_act2_end | 178 | 100..900 |
| PASS | cunning | all | 25 | gold_act3_end | 300 | 200..1800 |
| PASS | hoarder | all | 25 | boss_heroes_down_avg | 0.78 | -..1 |
| PASS | hoarder | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | hoarder | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | hoarder | all | 25 | boss_level_act3 | 4 | 4..- |
| PASS | hoarder | all | 25 | master_level_act1 | 2 | 2..2 |
| PASS | hoarder | all | 25 | master_level_act2 | 3 | 3..3 |
| PASS | hoarder | all | 25 | master_level_act3 | 5 | 4..5 |
| PASS | hoarder | all | 25 | gold_act1_end | 117 | 30..300 |
| PASS | hoarder | all | 25 | gold_act2_end | 176 | 100..900 |
| PASS | hoarder | all | 25 | gold_act3_end | 304 | 200..1800 |
| PASS | spender | all | 25 | boss_heroes_down_avg | 0.74 | -..1 |
| PASS | spender | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | spender | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | spender | all | 25 | boss_level_act3 | 4 | 4..- |
| PASS | spender | all | 25 | master_level_act1 | 2 | 2..2 |
| PASS | spender | all | 25 | master_level_act2 | 3 | 3..3 |
| PASS | spender | all | 25 | master_level_act3 | 5 | 4..5 |
| PASS | spender | all | 25 | gold_act1_end | 107 | 30..300 |
| PASS | spender | all | 25 | gold_act2_end | 147 | 100..900 |
| MISS | spender | all | 25 | gold_act3_end | 95 | 200..1800 |
| PASS | talker | all | 25 | boss_heroes_down_avg | 0.91 | -..1 |
| PASS | talker | all | 25 | boss_level_act1 | 2 | 2..- |
| PASS | talker | all | 25 | boss_level_act2 | 3 | 3..- |
| PASS | talker | all | 25 | boss_level_act3 | 4 | 4..- |
| PASS | talker | all | 25 | master_level_act1 | 2 | 2..2 |
| PASS | talker | all | 25 | master_level_act2 | 3 | 3..3 |
| PASS | talker | all | 25 | master_level_act3 | 4 | 4..5 |
| PASS | talker | all | 25 | gold_act1_end | 106 | 30..300 |
| PASS | talker | all | 25 | gold_act2_end | 156 | 100..900 |
| PASS | talker | all | 25 | gold_act3_end | 259 | 200..1800 |

## Targets by party (all styles pooled; the clean-win target is defined for the balanced style only)
| verdict | style | party | runs | target | value | bounds |
|---|---|---|---|---|---|---|
| PASS | all | casters | 35 | boss_heroes_down_avg | 0.39 | -..1 |
| PASS | all | casters | 35 | boss_level_act1 | 2 | 2..- |
| PASS | all | casters | 35 | boss_level_act2 | 3 | 3..- |
| PASS | all | casters | 35 | boss_level_act3 | 4 | 4..- |
| PASS | all | casters | 35 | master_level_act1 | 2 | 2..2 |
| PASS | all | casters | 35 | master_level_act2 | 3 | 3..3 |
| PASS | all | casters | 35 | master_level_act3 | 5 | 4..5 |
| PASS | all | casters | 35 | gold_act1_end | 113 | 30..300 |
| PASS | all | casters | 35 | gold_act2_end | 143 | 100..900 |
| PASS | all | casters | 35 | gold_act3_end | 203 | 200..1800 |
| MISS | all | classic | 35 | boss_heroes_down_avg | 1.08 | -..1 |
| PASS | all | classic | 35 | boss_level_act1 | 2 | 2..- |
| PASS | all | classic | 35 | boss_level_act2 | 3 | 3..- |
| PASS | all | classic | 35 | boss_level_act3 | 4 | 4..- |
| PASS | all | classic | 35 | master_level_act1 | 2 | 2..2 |
| PASS | all | classic | 35 | master_level_act2 | 3 | 3..3 |
| PASS | all | classic | 35 | master_level_act3 | 5 | 4..5 |
| PASS | all | classic | 35 | gold_act1_end | 113 | 30..300 |
| PASS | all | classic | 35 | gold_act2_end | 143 | 100..900 |
| PASS | all | classic | 35 | gold_act3_end | 203 | 200..1800 |
| PASS | all | duo | 35 | boss_heroes_down_avg | 0.88 | -..1 |
| PASS | all | duo | 35 | boss_level_act1 | 2 | 2..- |
| PASS | all | duo | 35 | boss_level_act2 | 3 | 3..- |
| PASS | all | duo | 35 | boss_level_act3 | 4 | 4..- |
| PASS | all | duo | 35 | master_level_act1 | 2 | 2..2 |
| PASS | all | duo | 35 | master_level_act2 | 3 | 3..3 |
| PASS | all | duo | 35 | master_level_act3 | 5 | 4..5 |
| PASS | all | duo | 35 | gold_act1_end | 117 | 30..300 |
| PASS | all | duo | 35 | gold_act2_end | 181.5 | 100..900 |
| PASS | all | duo | 35 | gold_act3_end | 305 | 200..1800 |
| MISS | all | martial | 35 | boss_heroes_down_avg | 1.2 | -..1 |
| PASS | all | martial | 35 | boss_level_act1 | 2 | 2..- |
| PASS | all | martial | 35 | boss_level_act2 | 3 | 3..- |
| PASS | all | martial | 35 | boss_level_act3 | 4 | 4..- |
| PASS | all | martial | 35 | master_level_act1 | 2 | 2..2 |
| PASS | all | martial | 35 | master_level_act2 | 3 | 3..3 |
| PASS | all | martial | 35 | master_level_act3 | 5 | 4..5 |
| PASS | all | martial | 35 | gold_act1_end | 114 | 30..300 |
| PASS | all | martial | 35 | gold_act2_end | 146 | 100..900 |
| PASS | all | martial | 35 | gold_act3_end | 210 | 200..1800 |
| PASS | all | solo | 35 | boss_heroes_down_avg | 0.73 | -..1 |
| PASS | all | solo | 35 | boss_level_act1 | 2 | 2..- |
| PASS | all | solo | 35 | boss_level_act2 | 3 | 3..- |
| PASS | all | solo | 35 | boss_level_act3 | 4 | 4..- |
| PASS | all | solo | 35 | master_level_act1 | 2 | 2..2 |
| PASS | all | solo | 35 | master_level_act2 | 3 | 3..3 |
| PASS | all | solo | 35 | master_level_act3 | 5 | 4..5 |
| PASS | all | solo | 35 | gold_act1_end | 130 | 30..300 |
| PASS | all | solo | 35 | gold_act2_end | 289 | 100..900 |
| PASS | all | solo | 35 | gold_act3_end | 500 | 200..1800 |

## How the runs ended (per style and party)
| style | party | runs | epilogue | lost for good | top level (median) | wipes/run |
|---|---|---|---|---|---|---|
| aggressive | casters | 5 | 5 | - | 5 | 0.4 |
| aggressive | classic | 5 | 5 | - | 5 | 1 |
| aggressive | duo | 5 | 1 | act 2: 3, act 3: 1 | 3 | 2.6 |
| aggressive | martial | 5 | 5 | - | 5 | 1 |
| aggressive | solo | 5 | 0 | act 2: 5 | 3 | 4.2 |
| balanced | casters | 5 | 5 | - | 5 | 0 |
| balanced | classic | 5 | 5 | - | 5 | 0.8 |
| balanced | duo | 5 | 5 | - | 5 | 0.2 |
| balanced | martial | 5 | 5 | - | 5 | 0 |
| balanced | solo | 5 | 3 | act 1: 1, act 2: 1 | 5 | 3.2 |
| cautious | casters | 5 | 5 | - | 5 | 0 |
| cautious | classic | 5 | 5 | - | 5 | 0.4 |
| cautious | duo | 5 | 4 | act 2: 1 | 5 | 1.8 |
| cautious | martial | 5 | 4 | act 2: 1 | 5 | 0.8 |
| cautious | solo | 5 | 2 | act 2: 3 | 3 | 4.6 |
| cunning | casters | 5 | 5 | - | 5 | 0 |
| cunning | classic | 5 | 5 | - | 5 | 0.2 |
| cunning | duo | 5 | 4 | act 2: 1 | 5 | 0.8 |
| cunning | martial | 5 | 5 | - | 5 | 0.4 |
| cunning | solo | 5 | 1 | act 1: 1, act 2: 3 | 3 | 3 |
| hoarder | casters | 5 | 5 | - | 5 | 0 |
| hoarder | classic | 5 | 5 | - | 5 | 0 |
| hoarder | duo | 5 | 5 | - | 5 | 0.6 |
| hoarder | martial | 5 | 4 | act 2: 1 | 5 | 0.8 |
| hoarder | solo | 5 | 0 | act 1: 1, act 2: 4 | 3 | 3.2 |
| spender | casters | 5 | 5 | - | 5 | 0 |
| spender | classic | 5 | 5 | - | 5 | 0.4 |
| spender | duo | 5 | 4 | act 3: 1 | 5 | 1.2 |
| spender | martial | 5 | 5 | - | 5 | 0.4 |
| spender | solo | 5 | 2 | act 1: 1, act 2: 2 | 3 | 2.4 |
| talker | casters | 5 | 5 | - | 5 | 0 |
| talker | classic | 5 | 5 | - | 5 | 0.2 |
| talker | duo | 5 | 4 | act 3: 1 | 5 | 1.4 |
| talker | martial | 5 | 5 | - | 5 | 0.6 |
| talker | solo | 5 | 2 | act 2: 2, act 3: 1 | 5 | 2.8 |

# M29.7d: small grid after the round-2 rules fixes (2026-10-23)

Slice of the M29.6b grid, 30 full campaigns on the fake storyteller, 0 runs failed a check:
balanced x classic, martial (`saves/balance/M29d_a`), balanced x casters, duo, solo (`M29d_b`) and
aggressive x classic (`M29d_c`), 5 seeds each. Report:
`python scripts/balance_report.py saves/balance/M29d_a saves/balance/M29d_b saves/balance/M29d_c --markdown`.
Before = the same slice of `saves/balance/M29b_final`, re-read with the same report.

Changes since M29.6b that act in the sims: aimed self cones and lines (R26; the bots aim away from
their friends), ranged attacks in close combat at disadvantage for heroes and monsters (R3),
befriended charms that end on the party's harm (R20). The new danger labels only label: spokes still
pick by XP (docs/DECISIONS.md M29.7d).

| slice | clean-win | heroes down per master | epilogues | wipes/run |
|---|---|---|---|---|
| balanced classic | 0.82 -> 0.82 | **1.42 -> 0.53** (now PASS) | 5 -> 5 | 0.8 -> 0 |
| balanced casters | 0.84 -> 0.87 | 0.27 -> 0.40 | 5 -> 5 | 0 -> 0 |
| balanced martial | 0.91 -> 0.93 | 0.73 -> 0.13 | 5 -> 5 | 0 -> 0 |
| balanced duo | 1.00 -> 1.00 | 0.19 -> 0.58 | 5 -> 5 | 0.2 -> 0.8 |
| balanced solo | 0.95 -> 0.97 | 0.62 -> 0.74 | 3 -> 1 | 3.2 -> 3.4 |
| aggressive classic | - | 1.95 -> 1.31 | 5 -> 5 | 1 -> 0.2 |

Target for clean-win: 0.75-0.90 (balanced only). For heroes down per master: <= 1. Master levels
2 / 3 / 4-5 and gold at the act ends pass in every slice.

## Reading
- **No target broke.** The misses are the M29.6b misses: clean-win over the ceiling for martial, duo
  and solo (spokes untouched), and aggressive classic heroes down per master (1.31, down from 1.95).
- **Classic at the masters is much safer** (1.42 -> 0.53). Two changes likely explain it, though
  5 seeds cannot prove which: the wizard no longer catches its friends with a self cone in its own
  zone, and a master's bow (the wight's longbow) now rolls at disadvantage when a hero stands in its
  zone.
- **Solo epilogues 1/5** (3/5 before): all 4 lost runs end at Fogwright's Tower, the act-2 wight, at
  level 3. That is where M29.6b lost 20 of its 25 solo runs. Across the M29.6b styles solo ranged from
  0 to 3 epilogues per 5 seeds, so 1/5 is inside the noise of one slice. R3 does reach this fight,
  though: next to the fighter the wight's bow rolls at disadvantage, but it may step out of the zone
  first, since leaving a zone provokes no attack. So a real effect cannot be ruled out. The lever is
  still a per-size boss scale (data); round 3 and the next wide grid decide.

# M31.1d: tougher masters (2026-10-24)

Owner (2026-10-24): "Yes make them tougher as part of m31." Round 4 met Grinner Voss (a hobgoblin,
11 HP), Brother Mallow (a ghoul, 22 HP, never acted) and the Tithekeeper (a wight, 26 HP against the
SRD 45). Same slice as M29.7d: balanced x classic, martial (`saves/balance/M31d_<run>_a`), balanced
x casters, duo, solo (`_b`) and aggressive x classic (`_c`), 5 seeds each, 30 full campaigns on the
fake storyteller, 3 detached processes, about 12 minutes a grid; 0 runs failed a check. Report:
`python scripts/balance_report.py saves/balance/M31d_after_a saves/balance/M31d_after_b
saves/balance/M31d_after_c --markdown`. Before = HEAD 0e0d3e9 (`M31d_before_*`).

## Cause of the weak masters
- **Hit points scaled for full parties.** The M29.6 small-party scale (`boss_hp_scale_floor`)
  compares the lone master's adjusted XP with the boss cap x `boss_budget_scale` (M29.6b). For four
  level-3 heroes that cap is 899 x 0.45 = 404, below one CR 3 monster (700 XP), so the act-2 wight
  spawned with 45 x 404 / 700 = 26 HP (r4-typed event 1098). The same held for the act-3 mage (40 ->
  31 HP at level 5). The rule meant for solo and duo hit every party size.
- **The master's stat block is the plan's pick, checked only for tier.** Tier 1 accepts any CR up
  to 1, so a CR 1/2 hobgoblin (11 SRD HP) can be a master while the region's spokes field up to
  239 adjusted XP for four level-2 heroes; nothing compared the master with the region's own fights.
  The ghoul "never acted": 22 HP died to four heroes before its first turn.

## What changed
- `rules.master_boost` (the one interpreter) and `data/bg3/master_template.json` (typed loader
  `aidm.data.master_template`): a party of `small_party_max` (2) or fewer keeps the M29.6 scale (owner
  rule); a party of `party_min` (3) or more never gets it and receives the template: hit points
  towards the hit dice maximum (`hit_dice_share`), a master's turn (`legendary_points`: one-point
  legendary single attacks after other creatures' turns, refilled on a d6 >= `legendary_recharge`)
  and a features.json trait (`masters-resolve`: advantage on saves against stunned, paralyzed,
  charmed, frightened, incapacitated, restrained).
- Every master is never weaker than the region's strongest spoke group (`offer_spokes.spoke_strength`:
  the spoke budget cap, or the cheapest theme monster when nothing fits): below it, hit points and
  rated XP rise by the ratio, at most `floor_hp_scale_max` (2.0).
- The offer rates the master at its SRD XP x hit point scale x the round damage its master's turn
  adds, and the round-damage word counts the extra attacks, so the word follows the real strength.
- Targets (`data/balance_targets.json`): `master_heroes_down_floor` bounds heroes down per master to
  [0.6, 1.0] (the same metric as `boss_heroes_down_avg`, whose cap stays 1.0) and
  `boss_hp_lost_share` >= 0.4 (mean share of the party's hit point maximum lost per master fight,
  a retried wipe included), both for the balanced and aggressive styles.

## Iterations (four-hero slices; solo and duo do not get the template)
| run | template | classic | casters | martial | aggressive classic |
|---|---|---|---|---|---|
| before | (scaled full-party masters) | 0.53 | 0.07 | 0.20 | 0.73 |
| i1 | hit dice max, 1 master's turn every round, trait | 3.79 | 3.18 | - | 4.04 (0/5 epilogues) |
| i2 | SRD hit points, trait | 1.61 | 1.63 | 2.32 | 1.94 |
| i3 | SRD hit points, no trait | 1.61 | 1.63 | 2.32 | 1.94 |
| after | = i2 (shipped) | 1.61 | 1.63 | 2.32 | 1.94 |
Heroes down per master. i2 and i3 are identical run for run: no bot spell ever forced a master's save
against those conditions, so the trait is neutral in the sims (it answers live play's holds).

## Before -> after (shipped template: SRD floor, trait, hit dice share 0, no master's turn)
| slice | clean-win | heroes down per master | party HP lost in master fights | wipes/run | epilogues |
|---|---|---|---|---|---|
| balanced classic | 0.80 -> 0.82 | 0.53 -> **1.61** | 0.31 -> 0.43 | 0.4 -> 0.6 | 5 -> 4 |
| balanced casters | 0.93 -> 0.84 | 0.07 -> **1.63** | 0.22 -> 0.44 | 0 -> 0.8 | 5 -> 4 |
| balanced martial | 0.87 -> 0.90 | 0.20 -> **2.32** | 0.24 -> 0.62 | 0 -> 1.2 | 5 -> 3 |
| balanced duo | 1.00 -> 1.00 | 0.55 -> 0.55 | 0.60 -> 0.60 | 1.0 -> 1.0 | 5 -> 5 |
| balanced solo | 0.89 -> 0.89 | 0.74 -> 0.74 | 0.91 -> 0.91 | 3.8 -> 3.8 | 0 -> 0 |
| aggressive classic | 0.56 -> 0.64 | 0.73 -> **1.94** | 0.27 -> 0.59 | 0 -> 0.6 | 5 -> 5 |
Bounds: heroes down per master 0.6..1.0, party HP lost >= 0.4, clean-win 0.75..0.90 (balanced).
Solo and duo margin: at most +0.5 wipes per run over M29.7d (solo 3.4 -> <= 3.9, duo 0.8 -> <= 1.3):
solo 3.8 and duo 1.0 hold, unchanged by this checkpoint (the template does not reach them; today's
HEAD already ran solo at 3.8).

## Reading
- **Both bounds cannot hold with SRD-hit-point masters and these bots.** With the template switched
  fully off, the mandated floor alone (a full party's master keeps its SRD hit points) takes every
  four-hero shape from under the floor (0.07-0.53) to over the cap (1.61-2.32). Before, the band was
  only met because full parties fought masters at 58% (act 2) and 78% (act 3) of their hit points.
  The HP-spend floor passes everywhere now (0.43-0.62, from 0.22-0.31).
- **Where the downs are**: wipes at two SRD masters, as M29.6 found. The act-3 mage either dies in
  round 1 (31 HP did, 40 HP often does not) or lands a fireball on a party standing in one zone
  (32 damage, 3-4 heroes down; casters 4 and classic 3 wipes there). The act-2 wight at 45 HP resists
  the martial party's nonmagical weapons (6 wipes, 3.64 downs per fight). Act 1 stays at 0.4 for
  balanced parties; aggressive classic's 2.0 there predates this checkpoint (no camp before the
  master).
- **So the boost values stay at zero** (`hit_dice_share` 0, `legendary_points` 0): every extra point
  of master strength moves away from the cap (i1). The machinery ships tested and data-switchable.
- **Levers left, each an owner or harness call**: bot tactics (spread out against an area caster,
  answer resistant undead with fire, oil or radiant), the master pick (count a master's area spells
  like breath weapons in the `boss_area` plan check), or a per-tier full-party hit point floor below
  SRD (against this checkpoint's rule).

# M31.1f: master walls (2026-10-24)

Orchestrator default for the M31.1d owner call: levers 1 (bot tactics) and 2 (count a master's area
spells in the `boss_area` plan check) first, then report. Same slice and seeds as M31.1d: balanced x
classic, martial (`saves/balance/M31f_<run>_a`), balanced x casters, duo, solo (`_b`) and aggressive
x classic (`_c`), seeds 1-5, 30 full campaigns on the fake storyteller, 3 detached processes, about
12 minutes a grid; 0 runs failed a check. Report: `python scripts/balance_report.py
saves/balance/M31f_after_a saves/balance/M31f_after_b saves/balance/M31f_after_c --markdown`.
Before = M31.1d after (`M31d_after_*`). The runs are deterministic per seed, so a change between two
grids is caused by the change between them.

## What changed
- **`boss_area` counts area spells** (`rules.encounter_danger`, one rule): with the spell registry,
  `area_damage` also takes the strongest shipped area damage spell the monster's kit can cast (a
  slot of its level or higher, an innate use or at will), at its base dice. Only the plan check
  (`campaign_check.master_too_dangerous`) passes the registry; the offer word and the spoke filter
  are unchanged. Plan picks: tier 1 and 2 are unchanged (the priest's Spirit Guardians lays a
  surface and rolls no damage); tier 3 loses the **mage** (Fireball 8d6 = 28 against the tier's
  29 reference hit points: deadly, above the medium cap). The generator's prompt lists it under
  "never a boss (area attack or spell too strong)". The check runs when a plan is made, never on
  load: round 4's quests save (a mage master) still replays (test).
- **The built-in sample campaign** (the fallback the fake storyteller plays) had the mage as its
  act-3 master and would no longer validate, so Magister Orsolo Venk is now a **gladiator** (CR 5,
  1800 XP, 112 SRD hit points, three spear attacks, Parry): the tier-3 humanoid leader of the lair's
  terrain (keep); the plan's text is unchanged. This, not the tactics, moves the act-3 numbers.
- **Bot tactics** (`scripts/sim/tactics.py`, campaign bots only, from the foe token's
  `monster_index` stat block, never its name or hidden numbers): spread one step into a free
  touching zone against a foe with an area blast (the same `area_damage` rule) when sharing a zone
  with an ally, not in a foe's zone and able to strike from afar; against the target's defences
  (THE `damage_after_defenses` check) the weapon option with the most expected damage, a cantrip
  the target takes more of (a caster's fire bolt on a fire elemental becomes ray of frost; a hero
  whose every weapon is resisted casts a known damaging cantrip), the leveled damage spell it takes
  most of (never one it is immune to), and carried damage gear (holy water, alchemist's fire, acid)
  that beats the best weapon after defences.

## Iterations
| run | change | classic | casters | martial | aggressive classic | duo | solo |
|---|---|---|---|---|---|---|---|
| M31.1d after | (mage master, no tactics) | 1.61 | 1.63 | 2.32 | 1.94 | 0.55 | 0.74 |
| i1 | `boss_area` spells, sample master gladiator, tactics off | 2.50 | 0.93 | 2.26 | 3.23 | 1.04 | 0.74 |
| after | i1 + bot tactics (shipped) | 2.50 | 0.93 | 2.33 | 3.23 | 1.04 | 0.74 |
Heroes down per master. i1 and after are identical run for run except the martial slice: no area
foe was ever met once the mage left (spokes never field a breath above their cap), so the spread
rule never fired; the classic party's defence-aware picks (about 40 a run, mostly at the wight) chose
the same weapon as before, and its cleric and wizard already cast radiant and fire.

## Before -> after
| slice | clean-win | heroes down per master | party HP lost in master fights | wipes/run | epilogues |
|---|---|---|---|---|---|
| balanced classic | 0.82 -> 0.82 | 1.61 -> **2.50** | 0.43 -> 0.47 | 0.6 -> 0.6 | 4 -> 5 |
| balanced casters | 0.84 -> 0.84 | 1.63 -> **0.93** | 0.44 -> **0.28** | 0.8 -> 0 | 4 -> 5 |
| balanced martial | 0.897 -> **0.905** | 2.32 -> **2.33** | 0.62 -> 0.61 | 1.2 -> 1.4 | 3 -> 3 |
| balanced duo | 1.00 -> 1.00 | 0.55 -> **1.04** | 0.60 -> 0.74 | 1.0 -> **2.2** | 5 -> 4 |
| balanced solo | 0.89 -> 0.89 | 0.74 -> 0.74 | 0.91 -> 0.91 | 3.8 -> 3.8 | 0 -> 0 |
| aggressive classic | 0.64 -> 0.64 | 1.94 -> **3.23** | 0.59 -> 0.63 | 0.6 -> 1.4 | 5 -> 5 |
Bounds: heroes down per master 0.6..1.0, party HP lost >= 0.4, clean-win 0.75..0.90 (balanced).
Per act (heroes down per master, retried wipes included): act 3 classic 2.25 -> 4.25, casters
3.22 -> 2.40, martial 0.67 (3 fights) -> 3.25 (8), duo 0.57 -> 1.54, aggressive 2.14 -> 4.64; act 2
martial 3.64 -> 2.50 (wight wipes 6 -> 3, the tactics); acts 1 and 2 otherwise unchanged.

## Reading
- **The four-hero cap still misses** for classic 2.50, martial 2.33 and aggressive classic 3.23;
  casters pass the band (0.93) but drop under the HP floor (0.28: they kill the gladiator from range
  before it reaches them). Not tuned further (checkpoint rule).
- **Walls left**: (1) the act-3 master at SRD strength. The mage's Fireball wall is gone from plans,
  but every other tier-3 master is a 78-127 hit point brute (the mage at 40 was the outlier), and
  the gladiator alone (112 HP, AC 16, three attacks of 11) downs 4.25 heroes per fight for classic;
  (2) the act-2 wight against weapons: the tactics cut martial's wight downs (3.64 -> 2.50) by
  picking the better weapon, but no party carries what it does not resist (the martial party has
  only torches; holy water, alchemist's fire or silvered arms would need shopping).
- **Normal fights**: the 75-90% band is unchanged except martial, 0.897 -> 0.905 (just over 0.90):
  the parties that now survive the wight play act 3's spokes.
- **Solo and duo**: the scaling is untouched; solo is identical; duo now meets the gladiator (scaled,
  at least half its hit points) in act 3: 8 wipes there, 2.2 wipes per run, over the M31.1d margin
  (<= 1.3), and heroes down per master 1.04 (cap 1.0).
- **Owner call** (unchanged levers): a per-tier full-party hit point floor below SRD, accept harder
  masters (SRD strength, today's numbers), or a different act-3 master for the built-in campaign.

# M31.1g: masters tuned to the cap (2026-10-24)

Owner call (2026-10-24), "Tune HP to the cap": a full party's master gets a share of its hit points
per tier, stored as data, tuned until four-hero parties land at 0.6-1.0 heroes down per master.
Same slice and seeds as M31.1d and M31.1f: balanced x classic, martial (`saves/balance/M31g_<run>_a`),
balanced x casters, duo, solo (`_b`) and aggressive x classic (`_c`), seeds 1-5, 30 full campaigns
on the fake storyteller, 3 detached processes per grid; 0 runs failed a check. Report: `python
scripts/balance_report.py saves/balance/M31g_i2_a saves/balance/M31g_i2_b saves/balance/M31g_i2_c
--markdown` (i2 is the shipped data, so it is the after grid). Before = M31.1f after (`M31f_after_*`).

## What changed
- `data/bg3/master_template.json` `full_party_hp_share` (region tier -> share), typed in
  `aidm.data.master_template`, applied by the one interpreter `rules.master_boost` for parties of
  `party_min` (3)+: hit points = template hit points (`hit_dice_share`, 0 = SRD) x the tier's share
  (1.0 when not listed), **never below the M29.6 small-party scale for the same party**
  (`small_party_scale`: 1.0 when the lone master fits the boss cap x `boss_budget_scale`, else
  max(0.5, cap / its adjusted XP); round 4's wight at 26 HP is that scale), then the spoke floor and
  the spawn cap as before. This replaces the M31.1d "at least SRD" floor. Solo and duo unchanged.
- Shipped shares: tier 1 1.0, tier 2 0.8, tier 3 0.5.

## Hit points the sample campaign's masters get (four heroes, the level the grid meets them at)
| act | master (SRD) | level | M31.1f | M31.1g | old M29.6 scale (guard) | offer word before -> after |
|---|---|---|---|---|---|---|
| 1 | bugbear (27) | 2 | 32 (spoke floor) | 32 (spoke floor) | 1.0 (27) | easy -> easy (with a cultist) |
| 2 | wight (45) | 3 | 45 | **36** | 0.577 (26) | medium -> **easy** |
| 3 | gladiator (112) | 4 | 112 | **56** | 0.5 (56) | hard -> hard |
| 3 | gladiator (112) | 5 | 112 | 112 | 0.999 (112) | hard -> hard |
Solo and duo masters are unchanged (bugbear 14 / 22, wight 22, gladiator 56). The act-2 word reads
easy: 700 x 0.8 = 560 rated XP against medium 600 for four level-3 heroes; its resistance to
nonmagical weapons is not part of the rating (as before).

## Iterations (heroes down per master; party HP lost in master fights in brackets)
| run | shares t1 / t2 / t3 | classic | casters | martial | aggressive classic | duo | solo |
|---|---|---|---|---|---|---|---|
| M31.1f after | SRD floor | 2.50 (0.47) | 0.93 (0.28) | 2.33 (0.61) | 3.23 (0.63) | 1.04 | 0.74 |
| i1 | 1.0 / 0.7 / 0.6 | 2.50 (0.45) | 1.00 (0.27) | 0.73 (0.34) | 2.50 (0.49) | 1.04 | 0.74 |
| **i2** | 1.0 / 0.8 / 0.5 (shipped) | **1.69 (0.38)** | **0.73 (0.23)** | **0.87 (0.40)** | **1.40 (0.35)** | 1.04 | 0.74 |
| i3 | 1.0 / 0.9 / 0.5 | 1.88 (0.40) | 0.87 (0.27) | 1.61 (0.55) | 2.63 (0.56) | 1.04 | 0.74 |
| x1 (not shipped) | i2, guard off | 1.31 (0.33) | 0.67 (0.20) | 0.73 (0.36) | 1.13 (0.28) | 1.04 | 0.74 |
x1 ran from a scratch copy of the tree with the round-4 guard removed (the gladiator at 56 HP at
level 5 too), only to measure what the guard costs. Solo and duo are identical in every grid (the
share never reaches them). Per act, i2: classic 0.4 / 1.0 / 3.33 (6 fights), casters 0.4 / 0 / 1.8,
martial 0.6 / 0.8 / 1.2, aggressive 2.0 / 0.2 / 2.0, duo 0.2 / 0.75 / 1.54 (13 fights).

## Before -> after (M31.1f -> M31.1g, shipped = i2)
| slice | clean-win | heroes down per master | party HP lost in master fights | wipes/run | epilogues |
|---|---|---|---|---|---|
| balanced classic | 0.82 -> 0.84 | 2.50 -> **1.69** | 0.47 -> **0.38** | 0.6 -> 0.2 | 5 -> 5 |
| balanced casters | 0.84 -> 0.84 | 0.93 -> **0.73** | 0.28 -> **0.23** | 0 -> 0 | 5 -> 5 |
| balanced martial | 0.905 -> **0.933** | 2.33 -> **0.87** | 0.61 -> 0.40 | 1.4 -> 0 | 3 -> 5 |
| balanced duo | 1.00 -> 1.00 | 1.04 -> 1.04 | 0.74 -> 0.74 | 2.2 -> 2.2 | 4 -> 4 |
| balanced solo | 0.89 -> 0.89 | 0.74 -> 0.74 | 0.91 -> 0.91 | 3.8 -> 3.8 | 0 -> 0 |
| aggressive classic | 0.64 -> 0.57 | 3.23 -> **1.40** | 0.63 -> **0.35** | 1.4 -> 0.2 | 5 -> 5 |
Bounds: heroes down per master 0.6..1.0, party HP lost >= 0.4, clean-win 0.75..0.90 (balanced).

## Reading
- **Martial passes both master bounds** (0.87, HP lost 0.40): the wight at 36 HP is no longer a wall
  for weapons it resists (act-2 downs 2.50 -> 0.80, 0 wipes). At 40 HP (i3) the wall is back (2.25).
- **Casters pass the band** (0.73) but miss the HP floor (0.23): they kill every master from range,
  at any share tried (0.20-0.28); HP alone cannot fix it without pushing them over the cap elsewhere.
- **Classic misses the cap** (1.69) because of tier 3 under the guard: against four level-5 heroes the
  old M29.6 scale is 1799 / 1800, so the gladiator keeps its SRD 112 HP whatever the share (2.5 downs
  per fight there); the one level-4 seed meets it at 56 HP (the guard's half and the share) and still
  takes 4 downs and a wipe. With the guard off (x1) classic is 1.31: still over. Stopped here as the
  checkpoint asks (no other levers pushed): the tier-3 wall is the round-4 guard plus the
  gladiator's damage (three attacks of 11 a round), not hit points alone.
- **Aggressive classic** 3.23 -> 1.40 (reported, not fitted); its act-1 2.0 predates M31.1d.
- **Duo** keeps the small-party scale (owner rule): unchanged at 1.04, 2.2 wipes per run; the master
  that misses is the act-3 **gladiator** at 56 HP (13 fights, 1.54 downs each, 8 wipes).
- **Normal fights**: classic and casters stay in band; martial 0.905 -> 0.933 because all five
  martial runs now live through act 3's spokes (5 epilogues, was 3); aggressive classic (no clean-win
  target) 0.64 -> 0.57 the same way. No target in data/balance_targets.json was touched.
- **Owner levers left**: the guard's reading for tier 3 (the literal M29.6 scale keeps a CR 5
  master at full HP for four level-5 heroes; round 4's weak masters were a hobgoblin, a ghoul and
  the act-2 wight), a less damaging act-3 master for the built-in campaign, or accepting classic at
  about 1.7.

# M32.1c: masters at full HP (owner, 2026-10-24)

Owner call after live round 5 (docs/playtests/M31_round5.md, Balance: 1 hero down in 5 master fights,
each 1-3 rounds): "Full HP again". `full_party_hp_share` is 1.0 for every tier in
`data/bg3/master_template.json` (the field and code path stay, so a later call is a data edit); the
spoke floor and the solo/duo scaling are unchanged. Same slices and seeds as M31.1g, saves in
`saves/balance/M32c_a` (balanced classic, martial), `_b` (balanced casters, duo, solo), `_c`
(aggressive classic), seeds 1-5, 30 campaigns on the fake storyteller; 0 runs failed a check.

## Hit points of the sample campaign's masters (four heroes)
| act | master (SRD) | level | M31.1g | M32.1c | offer word before -> after |
|---|---|---|---|---|---|
| 1 | bugbear (27) | 2 | 32 (spoke floor) | 32 (spoke floor) | easy -> easy |
| 2 | wight (45) | 3 | 36 | **45** | easy -> **medium** (700 XP vs medium 600) |
| 3 | gladiator (112) | 4 | 56 | **112** | hard -> hard |
| 3 | gladiator (112) | 5 | 112 | 112 | hard -> hard |

The "after" words were recomputed in M32.1d: `arrival_offer_events` at each master's gateway for four heroes (`tests/session/test_encounter_scaling._offer_at`, which runs `rules.offer_label.danger_label`) gave wight L3 medium, gladiator L4 hard, gladiator L5 hard, so the gladiator rows stand as written (the "before" words were not recomputed).

## Grid, before (M31.1g i2) -> after (heroes down per master; party HP lost in brackets)
| slice | M31.1g i2 | M32.1c |
|---|---|---|
| balanced classic | 1.69 (0.38) | 2.50 (0.47) |
| balanced casters | 0.73 (0.23) | 0.93 (0.28) |
| balanced martial | 0.87 (0.40) | 2.33 (0.61) |
| aggressive classic | 1.40 (0.35) | 3.23 (0.63) |
| balanced duo | 1.04 (0.74) | 1.04 (0.74) |
| balanced solo | 0.74 (0.91) | 0.74 (0.91) |
Wipes per run: classic 0.2 -> 0.6, martial 0 -> 1.4, aggressive classic 0.2 -> 1.4, casters 0 -> 0.

These numbers equal the M31.1f "SRD floor" grid run for run (full SRD hit points either way). The
grid's cap misses (heroes down per master above 1.0 for classic, martial and aggressive classic)
are expected and accepted: the bots do not play like the live table (live round 5 had 0.2 heroes
down per master fight). Live play rules over the scripted grid for masters; the targets in
`data/balance_targets.json` are unchanged.

# M35.5 re-run after Y1 (2026-10-25)

M35.1 fixed round-6 Y1 (two quest payouts in one pass: the second wrote its absolute from the
same snapshot and wiped the first). The M31.1d-M32.1c grids were measured with that loss. Same
slices, seeds 1-5 and fake storyteller as M32.1c, 30 campaigns at HEAD a475afa (M32.1c + 38
commits: M32.1d-M35.4), saves in `saves/balance/M35e_a` (balanced classic, martial), `_b`
(balanced casters, duo, solo), `_c` (aggressive classic); 0 runs failed a check, nothing retuned.
Ledger check (`scripts.sim.ledger.ledger_problems`, also run inside every sim's `replay_problems`):
**0 problems in all 30 new logs**; the same check over the 30 M32.1c logs finds problems in 6, all
seed 5 (one per slice): 60 gold and 75-150 XP lost per hero in act 1.

## Before (M32.1c) -> after (M35.5); gold and XP are the mean per hero when each act's master is first offered
| slice | gold m1 / m2 / m3 | XP m1 / m2 / m3 | level at masters | heroes down per master (HP lost) | clean-win | epilogues | wipes/run |
|---|---|---|---|---|---|---|---|
| balanced classic | 90/101/134 -> 102/111/149 | 672/1918/6592 -> 687/1933/6620 | 2/3/5 -> 2/3/5 | 2.50 (0.47) -> 2.24 (0.40) | 0.82 -> 0.76 | 5 -> 5 | 0.6 -> 0.4 |
| balanced casters | 92/100/138 -> 103/114/151 | 685/1931/6630 -> 695/1942/6641 | 2/3/5 -> 2/3/5 | 0.93 (0.28) -> 2.18 (0.45) | 0.84 -> 0.91 | 5 -> 5 | 0 -> 0.4 |
| balanced martial | 91/103/136 -> 103/115/151 | 675/1914/6563 -> 710/1952/6626 | 2/3/5 -> 2/3/5 | 2.33 (0.61) -> 1.12 (0.42) | 0.905 -> 0.84 | 3 -> 5 | 1.4 -> 0.2 |
| balanced duo | 89/118/199 -> 100/129/215 | 669/1894/6594 -> 699/1924/6624 | 2/3/5 -> 2/3/5 | 1.04 (0.74) -> 1.22 (0.78) | 1.00 -> 0.98 | 4 -> 4 | 2.2 -> 2.6 |
| balanced solo | 87/144/- -> 102/157/- | 695/2020/- -> 725/2050/- | 2/3/5 -> 2/3/5 | 0.74 (0.91) -> 0.78 (0.85) | 0.89 -> 1.00 | 0 -> 1 | 3.8 -> 3.4 |
| aggressive classic | 92/110/155 -> 104/117/158 | 672/1916/6565 -> 687/1923/6592 | 2/3/5 -> 2/3/4.5 | 3.23 (0.63) -> 3.50 (0.75) | - | 5 -> 3 | 1.4 -> 2.0 |
Per act, heroes down per master after: classic 0.6 / 0.4 / 4.71, casters 0.4 / 0.4 / 4.71, martial
2.17 / 0.2 / 0.8, aggressive 3.29 / 2.9 / 4.57, duo 1.0 / 1.42 / 1.17, solo 0.56 / 0.93 / 0.67
(before: classic 0.4 / 1.8 / 4.25, casters 0.4 / 0 / 2.4, martial 0.6 / 2.5 / 3.25). Solo m3 is one
run either way (not shown). Report: `python scripts/balance_report.py saves/balance/M35e_a
saves/balance/M35e_b saves/balance/M35e_c --markdown`.

## Reading
The economy shift is exactly Y1 and nothing else: seeds 1-4 meet the act-1 master with the same gold
(within 2; XP equal but one run 25 apart) and later masters within about 10 gold (loot rolls), while seed 5, the one campaign where two side
quests finish on the same step in act 1, now keeps both payouts and meets the act-1 master with
about 100 gold and 610-720 XP per hero instead of 38-44 gold and 536-568 XP; that lifts each
slice's mean by about 11-15 gold and 15-35 XP per hero at every master. Levels at the masters do not
move (the lost XP never crossed a level line), and every gold target stays in band. The master and
clean-win numbers move a lot (casters 0.93 -> 2.18 from two act-3 wipes, martial 2.33 -> 1.12 with
all five runs reaching the epilogue, aggressive classic loses two runs), but that is not Y1: the
38 commits since M32.1c (M33-M35 rules fixes: guided on the next attack only, concentration ending
with its last effect, waiting-foe rests, and more) change the dice stream of every fight, and five
seeds per slice swing a master average by a hero or more. No rest ambush (M35.2) happened in any
run. Nothing was retuned; the owner decides balance (live play rules over the bots for masters,
M32.1c).
