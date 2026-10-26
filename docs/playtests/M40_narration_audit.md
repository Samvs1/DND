# M40.3/M40.4 narration audit: stale story records

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

## M40.4: story records are past records (before / after)

M40.4 stamps every record when it is stored and shows it through ONE rule (`aidm.rules.story_records`,
DECISIONS M40.4): a fact or a place description a later engine change superseded is left out; summaries and
narrated turns stay as history, dated ("Earlier this scene", "Earlier, scene N", "Narrated earlier ...").
The audit now tells three outcomes apart for every stale record: shown as the PRESENT (its prompt line is
undated), shown DATED as past (every prompt line holding it starts "- Earlier" or "- Narrated earlier"), or
LEFT OUT. The journal's scene recaps count as past (titled past-tense recaps); its facts are notes (present).
The epilogue column reads the epilogue's own ledger (`epilogue_facts`). One audit fix: offer words must start
a word ("Cofferlight" matched "offer" and tied place facts to quests). Target: stale shown as the present is 0
in every reader on every fixture.

Before (the M40.3 code, measured with the M40.4 audit; summaries were already dated "Earlier (scene N ...)"):

```
run | narr | shown f/s/n/d | stale as present f/s/n/d | stale dated past f/s/n/d | stale left out f/s/n/d | prompts>=1 present | journal r/present/past | epilogue r/s
----------------------------------------------------------------------------------------------------
m29-p2 | 90 | 629/721/549/13 | 65/0/125/0 | 0/272/0/0 | 160/0/221/0 | 71 | 20/0/2 | 24/2
m29-p3 | 99 | 762/1224/573/18 | 92/0/62/0 | 0/488/0/0 | 936/0/88/0 | 87 | 20/1/2 | 24/2
m29-p6 | 88 | 624/479/519/6 | 36/0/74/0 | 0/282/0/0 | 195/0/134/0 | 32 | 20/3/4 | 24/5
m29-r2-full | 223 | 1372/5214/1323/37 | 99/0/189/0 | 0/1781/0/0 | 4838/107/358/0 | 100 | 20/3/2 | 24/3
m29-r2-p4 | 200 | 1410/3941/1198/31 | 178/0/175/0 | 0/1768/0/0 | 1775/27/356/0 | 130 | 20/0/2 | 24/3
m29-r2-p5 | 92 | 675/1113/531/17 | 50/0/128/0 | 0/445/0/0 | 636/0/191/0 | 54 | 20/0/2 | 24/2
m29-r2-p7 | 116 | 837/1625/687/23 | 252/0/132/0 | 0/688/0/0 | 797/0/221/0 | 114 | 20/0/1 | 24/1
m29-r2-p8 | 104 | 733/752/603/11 | 9/0/151/0 | 0/272/0/0 | 152/0/272/0 | 42 | 20/1/2 | 24/2
m29-r3-casters | 103 | 765/1315/597/21 | 55/0/119/0 | 0/417/0/0 | 523/0/234/0 | 67 | 20/1/4 | 24/4
m29-r3-full | 175 | 1296/3269/1037/28 | 211/0/202/0 | 0/1480/0/0 | 2416/8/387/0 | 163 | 20/2/3 | 24/4
m29-r3-items | 177 | 1410/2427/1047/17 | 69/0/144/0 | 0/808/0/0 | 1114/0/257/0 | 89 | 20/2/3 | 24/5
m31-r4-full | 185 | 1284/3297/1096/29 | 245/0/248/0 | 0/1453/0/0 | 1629/12/460/0 | 165 | 20/2/2 | 24/3
m31-r4-quests | 132 | 1003/1822/771/20 | 145/0/109/0 | 0/777/0/0 | 727/0/189/13 | 107 | 20/1/2 | 24/3
m31-r4-typed | 201 | 1689/2430/1196/19 | 346/0/81/0 | 0/598/0/0 | 1123/0/208/0 | 173 | 20/0/1 | 24/0
m32-r5-full | 137 | 929/1802/819/21 | 63/0/139/0 | 0/690/0/0 | 1079/0/238/0 | 70 | 20/4/3 | 24/5
m32-r5-quests | 97 | 744/813/565/13 | 30/0/109/0 | 0/312/0/0 | 479/0/200/0 | 40 | 20/0/2 | 24/3
m32-r5-typed | 147 | 1095/1451/867/14 | 31/0/111/0 | 0/401/0/0 | 507/0/220/0 | 61 | 20/1/3 | 24/2
m35-r6-full | 47 | 272/239/261/9 | 34/0/68/0 | 0/98/0/0 | 79/0/90/0 | 41 | 20/0/2 | 24/1
m35-r6-quests | 104 | 794/945/609/13 | 108/0/114/0 | 0/397/0/0 | 531/0/191/0 | 87 | 20/3/3 | 24/7
m35-r6-typed | 140 | 1052/1511/832/17 | 242/0/76/0 | 0/708/6/0 | 661/0/134/1 | 139 | 20/2/2 | 24/4
m39-r7-full | 169 | 1262/2569/993/19 | 342/0/206/0 | 0/1258/0/0 | 1646/0/347/0 | 167 | 20/1/3 | 24/4
m39-r7-quests | 92 | 703/998/537/15 | 70/0/143/0 | 0/545/0/0 | 713/0/264/0 | 61 | 20/1/3 | 24/4
m39-r7-typed | 156 | 1184/1734/915/25 | 61/0/143/0 | 0/1096/0/0 | 1133/0/261/0 | 75 | 20/0/2 | 24/2
m40-r7-typed | 72 | 512/377/411/20 | 35/0/101/0 | 0/238/0/0 | 217/0/156/0 | 43 | 20/3/6 | 24/6
TOTAL stale as present f/s/n/d: 2868/0/3149/0
```

After (M40.4):

```
run | narr | shown f/s/n/d | stale as present f/s/n/d | stale dated past f/s/n/d | stale left out f/s/n/d | prompts>=1 present | journal r/present/past | epilogue r/s
----------------------------------------------------------------------------------------------------
m29-p2 | 90 | 587/721/549/13 | 0/0/0/0 | 0/272/125/0 | 225/0/221/0 | 0 | 20/0/2 | 24/0
m29-p3 | 99 | 744/1224/573/18 | 0/0/0/0 | 0/488/62/0 | 1028/0/88/0 | 0 | 20/0/2 | 24/0
m29-p6 | 88 | 624/479/519/6 | 0/0/0/0 | 0/282/74/0 | 231/0/134/0 | 0 | 20/0/4 | 20/0
m29-r2-full | 223 | 1304/5190/1323/37 | 0/0/0/0 | 0/1764/189/0 | 4937/124/358/0 | 0 | 20/0/2 | 24/0
m29-r2-p4 | 200 | 1350/3931/1198/31 | 0/0/0/0 | 0/1762/175/0 | 1953/33/356/0 | 0 | 20/0/2 | 24/0
m29-r2-p5 | 92 | 674/1113/531/17 | 0/0/0/0 | 0/445/128/0 | 686/0/191/0 | 0 | 20/0/2 | 24/0
m29-r2-p7 | 116 | 763/1625/687/23 | 0/0/0/0 | 0/688/132/0 | 1049/0/221/0 | 0 | 20/0/1 | 24/0
m29-r2-p8 | 104 | 619/752/603/11 | 0/0/0/0 | 0/272/151/0 | 161/0/272/0 | 0 | 20/0/2 | 24/0
m29-r3-casters | 103 | 764/1315/597/21 | 0/0/0/0 | 0/417/119/0 | 578/0/234/0 | 0 | 20/0/4 | 24/0
m29-r3-full | 175 | 1248/3264/1037/28 | 0/0/0/0 | 0/1476/202/0 | 2627/12/387/0 | 0 | 20/0/3 | 24/0
m29-r3-items | 177 | 1428/2427/1047/17 | 0/0/0/0 | 0/808/144/0 | 1183/0/257/0 | 0 | 20/0/3 | 24/0
m31-r4-full | 185 | 1246/3284/1096/29 | 0/0/0/0 | 0/1449/248/0 | 1874/16/460/0 | 0 | 20/0/2 | 24/0
m31-r4-quests | 132 | 999/1822/771/20 | 0/0/0/0 | 0/777/109/0 | 872/0/189/13 | 0 | 20/0/2 | 24/0
m31-r4-typed | 201 | 1650/2430/1196/19 | 0/0/0/0 | 0/598/81/0 | 1469/0/208/0 | 0 | 20/0/1 | 24/0
m32-r5-full | 137 | 927/1802/819/21 | 0/0/0/0 | 0/690/139/0 | 1142/0/238/0 | 0 | 20/0/3 | 24/0
m32-r5-quests | 97 | 743/813/565/13 | 0/0/0/0 | 0/312/109/0 | 509/0/200/0 | 0 | 20/0/2 | 24/0
m32-r5-typed | 147 | 1066/1451/867/14 | 0/0/0/0 | 0/401/111/0 | 538/0/220/0 | 0 | 20/0/3 | 24/0
m35-r6-full | 47 | 251/239/261/9 | 0/0/0/0 | 0/98/68/0 | 113/0/90/0 | 0 | 20/0/2 | 23/0
m35-r6-quests | 104 | 766/945/609/13 | 0/0/0/0 | 0/397/114/0 | 639/0/191/0 | 0 | 20/0/3 | 24/0
m35-r6-typed | 140 | 1037/1511/832/17 | 0/0/0/0 | 0/708/82/0 | 903/0/134/1 | 0 | 20/0/2 | 24/0
m39-r7-full | 169 | 1183/2569/993/19 | 0/0/0/0 | 0/1258/206/0 | 1988/0/347/0 | 0 | 20/0/3 | 24/0
m39-r7-quests | 92 | 672/998/537/15 | 0/0/0/0 | 0/545/143/0 | 783/0/264/0 | 0 | 20/0/3 | 24/0
m39-r7-typed | 156 | 1170/1734/915/25 | 0/0/0/0 | 0/1096/143/0 | 1194/0/261/0 | 0 | 20/0/2 | 24/0
m40-r7-typed | 72 | 498/377/411/20 | 0/0/0/0 | 0/238/101/0 | 252/0/156/0 | 0 | 20/0/6 | 19/0
TOTAL stale as present f/s/n/d: 0/0/0/0
```

Reading it: stale records shown as the present go from 2,868 facts and 3,149 narrated lines (and 0 to 4
journal notes, 0 to 7 epilogue facts per run) to 0 everywhere. Stale facts are now left out (dated past: 0);
stale summaries and narrated turns are shown dated as past. Prompts with at least one stale record shown as the
present: from 32 to 173 per run to 0. The heuristic still never finds a stale description (a blind spot); the
mechanism leaves out a description that names a foe since dead or gone (tested). Known r7 cases: the stirges
fact at r7b-full 513 and the "not yet accepted" fact at r7b-quests 119 are left out (tests
`tests/unit/scripts/test_narration_audit.py`, `tests/ai/test_story_records_r7.py`), and the r7b-typed lie
("offers ... not taken up") is no longer written: no engine event refused anything.
