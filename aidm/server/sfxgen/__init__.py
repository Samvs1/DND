"""The dice sounds (M26.8, docs/next/GOAL_DICE.md), seeded and repeatable. All synthesised except
success and a natural 20, which are built on one CC0 recording (data/sfx/SOURCES.md).

Modules: `names` (the shipped sound names, no numpy), `synth` (primitives), `dice` (impacts,
throws, clacks), `stings` (failure, natural 1, hit, miss), `impact` (the CC0 recording and its
shaping), `grains` (sparkle layers), `payoff` (success, the natural 20 and its beats), `catalog`
(every sound with its recipe), `cli` (the `scripts/gen_dice_sfx.py` build)."""
