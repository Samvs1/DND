# Playtest report: smoke (M29.3 harness check)

Played by the harness author following `.claude/agents/playtester.md` (the new agent type is not
loaded in the session that built it, so the same commands were run by hand). Fake storyteller,
so the prose is canned; this run checks the harness and the backend plumbing, not the story.

## Summary (5 lines)
1. Classic four (fighter, cleric, rogue, wizard), balanced, act 1 on the fake storyteller; 44 actions, 2 fights won, heroes still level 1.
2. No crash or silent turn; one wrong-looking state: Tamsin lay DYING (0/8, unconscious) after an easy fight and nothing offered help.
3. Balance: the easy grimlock + kobold fight dropped the wizard to 0 HP; the 2-rat fight cost nothing.
4. Confusing: XP lines appear when a warning beat opens ("Brienne gains 75 XP" x4) and again after the fight (3 heroes).
5. Suggestion: show shopkeeper names (not the id `dessa-orrin`) in the scene's Shops line.

## Persona
- Party (classes, shape): classic (Brienne fighter, Elowen cleric, Rook rogue, Tamsin wizard)
- Play style: balanced, talks to everyone, fights every offer
- Storyteller: fake
- Run name, port, seed: smoke, 8121, seed 1

## Run length
- Actions taken (cap): 44 of 40 (the cap was about 40); fights: 2; rests: 1; ended by: cap
- Final state: Saltcellar Tunnels (dark); Brienne, Elowen, Rook 12/12, 10/10; Tamsin 0/8 unconscious; 18gp each (Tamsin 17gp);
  last footer `[save c-20261023-075509-0001 | event 235]`

## What worked
- `new` started the background server, seated four heroes and began the campaign; later commands reused it; `stop` ended it (no listener left on 8121).
- Quest offers, offers (fight, parley with a Persuasion roll), a travel vote, a short rest and the dark-place fight text all read clearly.
- In a fight the acting hero is chosen automatically and `look` lists the exact `do` options; attacks, ends, and a refused out-of-range attack came back as plain lines.
- Every output ended with the save id and event number.

## Bugs
No confirmed bug. Two suspects, to reproduce from the save:

### S1: a hero left DYING outside combat
- Severity: wrong-state (suspect)
- Save id / event number: `c-20261023-075509-0001` / `235`
- Steps: `move "Saltcellar Tunnels"`, `answer parley` (failed), fight with `do attack 1` / `do end` until both foes died.
- Expected: after the fight the fallen wizard is stable or the table is told how to help her.
- Actual: `look` shows `Tamsin 0/8hp ... DYING [unconscious]` with no card or hint; she is not up for the next action.

### S2: XP lines at the warning beat and again after the fight
- Severity: cosmetic (suspect)
- Save id / event number: `c-20261023-075509-0001` / `126` (2-rat fight), `235` (grimlock fight)
- Steps: `move "Rotting Boathouse"` then `answer fight` and finish the fight.
- Expected: XP is announced once, when the fight is won.
- Actual: "gains 75 XP" for all four heroes right after the warning beat, then again for three heroes after the fight.

## Confusing moments
- `Shops: dessa-orrin` shows an id, not the shopkeeper's name (footer event 30).
- `do attack 1` is listed even when the foe is out of range (answer: `ERROR refused: Grimlock is out of range`, event ~225).
- A single `act` often prints two DM lines (canned fake prose); with the live storyteller check that narration is not duplicated.
- A short rest and travel passed at once with no vote visible to the tester (the other heroes were not connected).

## Balance feel
- Fights: 2 giant rats (trivial) were free. Grimlock + kobold (easy, dark) put the wizard at 0 HP by round 3.
- Gold and prices: only 15gp each at start, 18gp after two fights; no purchase was tried (the fake storyteller does not run shops).
- XP and levels: 150 XP per hero after two fights, no hero could level up yet (`levelup` said none available).
- Rest and resources: one short rest; no slots or potions used.

## Suggestions
- Print shopkeeper names in the scene's Shops line.
- Hide or mark out-of-range targets in the hotbar options when the foe is not reachable.
- Check the double XP announcement and the post-fight DYING hero on a live-storyteller run.
