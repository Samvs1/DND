# GOAL: Impossible actions (M30)

Owner request, 2026-10-20. Binding. Only option 1 of the three discussed (the other two, a DC cap on the
natural-20 rule and a prompt-only rule, are NOT part of this goal).

## The problem
A player types "I jump onto the house" and rolls a natural 20 on Athletics. Today the DC tiers stop at
`nearly_impossible` (DC 30) and a natural 20 on an ability or skill check always succeeds (BG3,
`rules/checks.py`), so a nat 20 beats ANY tier. The model has no way to say "this cannot be attempted"; its
only exits are `no_mechanics` (no roll at all, nothing recorded) or a check that a nat 20 can win.

## The change
The model may declare an action **impossible**. The engine then refuses to roll: no dice, no nat-20 rescue.

- `request_check` (and `request_save`, if it makes sense there: **D:** decide in M30.1) accepts an
  `impossible` outcome next to the six DC tiers. It is NOT a seventh DC number: `DcTier` and `DC_BY_TIER`
  stay as they are (hidden features, offers and parley tiers use them). It is a separate option on the tool
  schema, with a short `reason` ("a person cannot jump onto a roof").
- The executor returns an event (`ActionImpossible`: actor, text, reason) and NO dice. The reducer records it
  in `events.jsonl`; replay still equals the snapshot.
- The tool result goes back to the model like any check result, and the narrator is told the engine's verdict
  ("cannot be done: <reason>") so it narrates the attempt failing in fiction, never the success.
- The guard rejects narration that claims success after an `ActionImpossible` for that action.
- The player sees a short in-fiction line; no raw error. No dice card is shown (nothing was rolled).

## Open points to decide in M30.1 (log in docs/DECISIONS.md)
1. Does an impossible declaration spend the hero's action in a fight? Today any executed tool spends it.
   Leaning: **not spent** (the hero tried nothing), so a player can pick something else.
2. How does the model learn what is impossible? A short prompt rule in `dm/context_text.py` listing the
   option ("physically impossible for a person, or against the closed world: use impossible, not a hard DC").
   The rule is guidance only; the engine behaviour above is what is tested.
3. Magic and class features that really make it possible (a Jump spell, a flying hero) must still work:
   the model only declares impossible when nothing in the hero's sheet or the manifest allows it.

## Done means
- A fake-LLM test: "I jump onto the house" -> `request_check` with `impossible` -> no dice event, an
  `ActionImpossible` event, narration says it fails, even with an RNG seeded to roll a natural 20
  (`test_m30_impossible_ignores_nat20`).
- A test that normal checks still roll and a nat 20 still wins at `nearly_impossible`.
- Schema, protocol (`gen_protocol.py --check`), reducer replay, guard and event text covered.
- A live probe (`RUN_LIVE=1`) with three typed actions: one clearly impossible, one hard but possible, one fine.
- `docs/PLAYER_MANUAL.md` explains that some actions are refused outright; `docs/RULES_DECISIONS.md` has one line.
