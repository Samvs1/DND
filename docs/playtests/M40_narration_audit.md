# M40.3 narration audit: stale story records (baseline)

Offline, no model calls: `python scripts/narration_audit.py` (helpers in `scripts/audit/`).

## Method

Each fixture in `tests/fixtures/saves` is replayed through the one reducer. At every `narration_recorded` the
narrator prompt is rebuilt from the state just before it (engine events since the last narration plus the
RESOLVED notes). A record counts as SHOWN when its text appears in that prompt. It is STALE when it was made
(the seq of the event that added it) before a later engine change to an entity it names: a creature died, went
down or left, a quest changed state or stopped being the pending ask, an item changed holder. Heroes count only
when dead. A record names an entity by its entity ids or by the entity name in the text (details and limits in
the `scripts/audit/stale.py` docstring; it is a measurement, not game logic). Offer wording ("accepted",
"request") also names the quests the mentioned giver gives. Stores: facts (f), scene summaries (s),
`Narrated:` lines (n), place descriptions (d). Journal r/s and epilogue r/s are records / stale records in the
players' journal view and the epilogue ledger at the end of the run.

## Baseline (rounds 1 to 7)

```
run | narr | shown f/s/n/d | stale f/s/n/d | prompts>=1 stale | journal r/s | epilogue r/s
------------------------------------------------------------------------------------------
m29-p2 | 90 | 629/721/549/13 | 65/272/125/0 | 89 | 20/2 | 24/2
m29-p3 | 99 | 762/1224/573/18 | 92/488/62/0 | 97 | 20/3 | 24/2
m29-p6 | 88 | 624/479/519/6 | 36/282/74/0 | 62 | 20/7 | 24/5
m29-r2-full | 223 | 1372/5214/1323/37 | 99/1781/189/0 | 215 | 20/5 | 24/3
m29-r2-p4 | 200 | 1410/3941/1198/31 | 178/1768/175/0 | 199 | 20/2 | 24/3
m29-r2-p5 | 92 | 675/1113/531/17 | 50/445/128/0 | 81 | 20/2 | 24/2
m29-r2-p7 | 116 | 837/1625/687/23 | 252/688/132/0 | 114 | 20/1 | 24/1
m29-r2-p8 | 104 | 733/752/603/11 | 9/272/151/0 | 89 | 20/3 | 24/2
m29-r3-casters | 103 | 765/1315/597/21 | 55/417/119/0 | 90 | 20/5 | 24/4
m29-r3-full | 175 | 1296/3269/1037/28 | 211/1480/202/0 | 174 | 20/5 | 24/4
m29-r3-items | 177 | 1410/2427/1047/17 | 69/808/144/0 | 167 | 20/5 | 24/5
m31-r4-full | 185 | 1284/3297/1096/29 | 245/1453/248/0 | 175 | 20/4 | 24/3
m31-r4-quests | 132 | 1003/1822/771/20 | 145/777/109/0 | 131 | 20/3 | 24/3
m31-r4-typed | 201 | 1689/2430/1196/19 | 346/598/81/0 | 190 | 20/1 | 24/0
m32-r5-full | 137 | 929/1802/819/21 | 63/690/139/0 | 113 | 20/7 | 24/5
m32-r5-quests | 97 | 744/813/565/13 | 30/312/109/0 | 86 | 20/2 | 24/3
m32-r5-typed | 147 | 1095/1451/867/14 | 31/401/111/0 | 146 | 20/4 | 24/2
m35-r6-full | 47 | 272/239/261/9 | 34/98/68/0 | 46 | 20/2 | 24/1
m35-r6-quests | 104 | 794/945/609/13 | 108/397/114/0 | 102 | 20/6 | 24/7
m35-r6-typed | 140 | 1052/1511/832/17 | 242/708/82/0 | 139 | 20/4 | 24/4
m39-r7-full | 169 | 1262/2569/993/19 | 342/1258/206/0 | 167 | 20/4 | 24/4
m39-r7-quests | 92 | 703/998/537/15 | 70/545/143/0 | 90 | 20/4 | 24/4
m39-r7-typed | 156 | 1184/1734/915/25 | 74/1096/143/0 | 154 | 20/2 | 24/2
m40-r7-typed | 72 | 512/377/411/20 | 48/238/101/0 | 70 | 20/9 | 24/7
```

Reading it: `shown` counts are summed over all narrations of the run (one record shown in 100 prompts counts
100). Summaries dominate because every summary is shown in every prompt for the rest of the run, so one
summary of a dead foe is counted again each time. Nearly every prompt carries at least one stale record.
Descriptions show no staleness because the heuristic finds few entity names in them (a blind spot, not proof
they are fresh). The journal and epilogue each show about 1 to 9 stale records out of 20 and 24.

## Known round 7 cases (tested)

- r7b-full, seq 513: fact-8 (made at seq 197) "Two stirges rose ... and hover before the party; no blow has yet
  been struck" is shown while all four stirges are dead.
- r7b-quests, seq 119: fact-3 (seq 29) "The party has not yet accepted or refused Sable Marowe's request" is
  shown beside fact-5 "The party accepted Sable Marowe's request"; the quest changed state at seq 49.

Test: `tests/unit/scripts/test_narration_audit.py`.
