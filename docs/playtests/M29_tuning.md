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
