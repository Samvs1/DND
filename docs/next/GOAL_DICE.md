# GOAL: Dice at the table (M26)

Owner request 2026-10-16. Binding. Mockups: canvas "AIDM UI Revamp Concepts", page Dice
(https://claude.ai/artifact/MinEzzrb43Zk9TkxSMtiGJ). Owner answers to the mockup questions:
1. Direction A (the roll stage) for checks and saves out of combat, C (results on the board) for
   combat, and B's folded one-line results as the history in the TV's side column.
2. The stage is NOT used for combat rolls, not even crits ("let's not complicate it").
3. The rolls of one action reveal in sequence, even though it slows a turn down.
4. A natural 20 on an ability or skill check always succeeds (already the rule: `rules/checks.py`,
   and a natural 1 always fails, as in BG3).
5. A dice sound, yes.
Owner bar: "the animation is really on point and repeatable (such as Baldur's Gate) so it doesn't get
annoying or boring fast". Timing: "one animation waits for the next, the narrator doesn't spoil the
roll beforehand". Rolling stays automatic: nobody taps to roll.

## What the table sees
- Out of combat, a check or save is the ROLL STAGE on the TV: the scene dims; title ribbon (the
  skill), who rolls and why; DC plaque left (number + tier word), bonuses plaque right (each bonus
  named: DEX +3, PROF +2, other); one big d20 is thrown, tumbles and lands; the bonuses add into the
  total; the verdict slams in (SUCCESS, FAILURE, NATURAL 20, NATURAL 1). Advantage/disadvantage:
  two dice are thrown, the dropped one shrinks aside, struck through, and a chevron chip names why.
  The roller's phone shows the same roll as a card ("Your roll"); the others only see the TV.
- In combat, results land ON THE BOARD: a die arcs from the attacker's token to the target's, lands
  with its number, the verdict floats over the target (HIT / MISS), damage dice follow and the damage
  floats up (-12) while the HP bar drains. A save shows a die over each saver and its verdict. A strip
  under the board spells out the maths of the current action. The side column's dice card becomes
  THIS ROUND: one line per finished action, newest on top.
- Words and colours are told from the party's side: the die's look says WHO rolled (teal steel = a
  hero, crimson = a monster); the verdict's colour says what it MEANS for the party (teal good,
  crimson bad). A monster making its save against a hero reads RESISTED (crimson), failing it reads
  CAUGHT (teal); a monster's attack on a hero reads MISSED <hero> (teal) or HIT <hero> (crimson).
- Phones: the acting hero gets a result card for their action; a hero who is attacked gets an
  "incoming" card (the die, the total against their AC, the verdict) and the hit comes off the HP
  strip only when the TV shows it. The toast and "Your last roll" follow the same words.
- Sound (screen only): every throw rattles and lands on the table; the stage verdict has a sting
  (success, failure, natural 20, natural 1); combat landings are quieter clacks with a hit or miss.
  An Effects volume joins the audio settings.

## Repeatable, never boring (the BG3 lessons)
- Fast: a stage roll is about 3 s from throw to fade (a natural 20 adds a beat); a combat attack
  about 2 s, a miss about 1 s. Tapping the TV skips to the verdict.
- Never the same twice: each throw gets its own path (entry side, spins, bounces, final tilt) from a
  seeded random; the face flickers random numbers and never shows the result before landing; sounds
  come in several variants, never the same one twice in a row.
- Weight: squash on landing, a glow on the kept face, the verdict slam and its sting are the payoff.
- Backlog: when rolls queue up (a monster turn with several attacks) the shows speed up rather than
  lag behind. Reduced motion: no tumble or arcs, short fades, same order and sounds.

## Timing (the hard rule)
- ONE presentation queue per client (`js/show/pacer.js`, between the websocket and the dispatcher):
  a roll starts a show; every later message (event lines, narration chunks, snapshots, combat state,
  turn prompts, quest and loot notices) waits until the show ends, then flows on in order. The
  narration can never appear or be heard before the verdict; HP never drops before the hit lands.
- Hello / story_history (reload, reconnect) never animates: the queue is cleared and the latest
  state is shown at once. Only a short list of transport messages bypasses the queue (pong, typing).
- The screen reports `presented {seq}` when its queue has shown everything up to seq; an AI turn
  waits for that (floor `ai_turn_pause_s`, cap 8 s; no screen connected = the fixed pause), so the
  server never runs ahead of the TV.

## Data the show needs (engine owns every number)
DiceView gains: `kind` (attack, check, save, death_save, damage, heal, other), `target_id`, `source_id`
(who caused a save), `parts` (named bonuses of a check or save, from `rules/checks.py`), `adv_why`
(the advantage/disadvantage sources), `difficulty` (the DC tier word), readable labels (no raw ids
like "sneak-attack"). Damage events reach the client with the creature and the amount taken.

## Assets
- Dice art: the 12 pixel pieces made for the mockup (d4-d12 and d20 hero teal, d20 monster crimson,
  gold d20 for a natural 20, cracked d20 for a natural 1, advantage/disadvantage chevrons, the crit
  burst) as real UI_ART entries, source `generated:gpt-image-2.5-m26`. Numbers are drawn by CSS.
- Sound: synthesised by `scripts/gen_dice_sfx.py` (seeded, deterministic, no samples to license):
  throw variants, landings, stings, combat clack/hit/miss; one final lossy encode; manifest `sfx.*`.

## Done means
The stage and the board shows work in the real app (videos at 1920x1080 and 1280x720, phones at
390x844) for: a check, a check with advantage, a natural 20, a natural 1, a save; a hero attack that
hits, a miss, a crit, a monster attack on a hero, a spell with saves on two monsters, a death save.
UI tests prove the order (no narration or HP change before the verdict), the skip, the reload and the
backlog speed-up. The manual describes the dice, words, colours, sound and skip. FULL gate green.
