# M36.9 live eval: typed lines read from the engine's menu

Corpus: `tests/fixtures/interpret/corpus.jsonl`, 300 labelled typed lines from rounds 1-6 (explore 150,
fight 100, offer 50; 120 cited in a playtest finding, 20 button sentences). Scoring:
`scripts/interpret/score.py`. Runs: `python scripts/eval_interpret.py --router --live --cap 400`
(raw results in `artifacts/eval/<timestamp>.json`, gitignored). Spend: 1,332 DeepSeek calls of the
2,500 approved (pass 1 330, pass 2 330, pass 3 343, pro diagnostic 329).

## Result: the pass bar is NOT met

| metric | bar | router | pass 1 | pass 2 (iter 1) | pass 3 (iter 2) | pro diagnostic (iter 2) |
|---|---|---|---|---|---|---|
| exact | >= 92% | n/a | 85.7% | 91.0% | 90.0% | 91.7% |
| act match | | 56.7% | | 91.0% | 90.0% | 92.0% |
| finding-cited (exact) | 100% | 54.2% (act) | 85.8% | 89.2% | 90.0% | 89.2% |
| false action | <= 2% | | 5.7% | 6.0% | 4.0% | 3.0% |
| false other | <= 5% | | 9.3% | 2.7% | 3.3% | 1.7% |
| p90 latency | <= 4 s | | 1.85 s | 1.82 s | 2.01 s | 2.70 s |
| better than router | yes | | yes | yes | yes | yes |

By scope (pass 3 / pro): explore 88.0 / 89.3%, offer 88.0 / 88.0%, fight 94.0 / 97.0%; the 20
button sentences 100%. The router is the old phrase-table reader on the same rows, scored by acts.
The pro diagnostic is the same prompt and menu as pass 3 with `DEEPSEEK_MODEL_FAST=deepseek-v4-pro`
(no code change). It is a check of whether the ceiling is the model; it is not a third iteration.

## What each iteration changed (DECISIONS M36.9, M36.9 iteration 2)
- Iteration 1 (after pass 1, 43 misses, about 20 of them a flourish sent to `other`): the `colour`
  field (how the hero does it, narration only), `other` redefined, short rules (no added steps,
  showing is not giving, melee out of reach is the attack alone, area spells, offer surprise and
  parley), fight zones name who stands in them, scorer fix (act match ignores other's words).
- Iteration 2 (after pass 2, 27 misses): a rendering defect. The offer answers were grouped like
  items (`offer:<item>: fight, surprise, ..., parley:persuasion`), so the model never saw what an
  answer does and read pleas to a waiting master as `talk`. Fixes: offer answers are listed one per
  line, same-stem entries share a line, clearer parley and Persuasion-surrender labels, and rules
  3 and 5 in general words. The prompt budget was kept (messages 1,763 of 1,800, total 2,588 of
  2,600). The talk-vs-parley rows now mostly pass (1044, 638 parley; 773 parley but without the give).

## Why it stalls near 90-92%
- Run-to-run noise is about +-4 rows-in-100. Of the 47 rows missed by any of passes 2, 3 or pro,
  36 pass in at least one of them. Only 11 are missed every time.
- The 11 hard rows:
  - Uncarried or unregistered items (418 receipt-scroll, 521 Caul's Bait-Cache, 638 Sister's
    Locket, 868 chime by the body). The menu cannot name the thing, so the model either swaps in a
    carried item (a false action) or drops the off-menu part. The labels want `other`.
  - Genuinely two-way lines: 466 "four silver" (pay counts gold; the model pays 4 gp), 468 "boards
    the boat" (the model either travels or leaves it out; the label wants `other`), 666 "carry Rook
    ... and wait until he wakes" (rest short or not), 377 "offers to pay for the grave stone" (an
    offer or a payment).
  - 1910 an answer to a master's challenge (talk or parley), 773 laying the chime down (give plus
    parley; the model parleys only), 515 "and buys a little more" (shop).
- The finding-cited bar (100%) cannot be reached by a sampling model on its own. Each pass misses a
  different 10-13 of the 120 cited rows, and some of the cited lines are the ambiguous ones above.
- A bigger model is not the fix: pro gains about 1 point exact and 1 point false action, at 1.5x
  the latency and a higher per-call price.

## What the misses cost a player
- False action (pass 3: 12 rows; pro: 9) is the harmful kind: a step the player did not ask for.
  Most are cheap (an extra `what_now`, `inventory` or `talk`). The costly ones: a travel that moves
  the party (935 climb back up, 45 accepting a run), a pay (377), a give of a substitute item
  (418, 521).
- False other (pass 3: 10; pro: 5): the storyteller adjudicates a flourish as a stunt. The action
  still happens; only the narration adds a roll or a beat.
- Everything else gets the right act with a small shape difference (a missing `other`, a missing
  `talk` after a give).

## Options for the owner
1. Flip to the menu interpreter at about 90% (FAST model, p90 about 2 s) and accept that the bar
   is out of reach for this approach. It beats the router by about 33 points on the same lines
   (finding-cited 90% against 54%). The remaining misses become corpus rows for later work.
2. The same as option 1 but on the pro model: about 1 point better and fewer false actions (3.0%),
   p90 2.7 s, at a higher per-call price on every typed line.
3. One targeted menu change before flipping (outside the two prompt iterations, so it needs your
   OK): name the things the hero does not carry but can see or mean (an ally's items, a thing in
   the scene) as "not carried" targets, so `other` has a target and no item gets swapped. It aims at
   4 of the 11 hard rows and most substitute-item false actions. Cost: one more live pass, about
   330 calls (1,332 of 2,500 used).
4. Keep the router: not recommended (56.7% act).

Recommendation: option 1. Option 3 can be done after the flip if you want it.
