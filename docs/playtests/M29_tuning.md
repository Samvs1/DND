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
