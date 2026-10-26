# M36 labelling guide: the typed-line corpus

The corpus (`tests/fixtures/interpret/corpus.jsonl`, M36.8c) holds about 300 typed lines from the committed
playtest fixtures, each with the choice the menu chooser should make. `scripts/eval_interpret.py` measures the
chooser (and the old router) against it, so a label must say what the PLAYER ASKED FOR, not what the engine did
then and not what would be wise. Design: docs/next/M36_ACTION_MENU.md ("The eval"); chooser rules: DECISIONS
M36.5 and M36.6.

## The files
- `artifacts/interpret/sheets/partN.jsonl` (N = 1-3, about 100 rows each, balanced by scope): one row per line
  with `id, run, seq, actor_id, text, scope, source, note`, plus
  - `prompt`: the user part of the CHOOSE prompt exactly as the model sees it: ACTING HERO (what is left this
    turn), TARGETS (`id = label`, with distance and health), PRONOUNS (LAST TARGET, LAST SPOKEN TO), RECENT ENGINE
    EVENTS and MENU (`id = label -> targets`, `[up to N]`, `[spent]`; `ITEMS:` lists the carried item ids once and
    a group line `give:<item> -> widow-cabrelle: <item> = any of ITEMS` means one id per item, e.g.
    `give:block-of-incense`);
  - `exact`: the fast-path pick when the whole line is a game string (else null);
  - `hint_router`, `hint_engine`: the old router's reading and what the engine did. Weak hints, often wrong.
- `artifacts/interpret/labels/partN.jsonl`: what you write, one corpus row per sheet row, same order:

```json
{"id": "m35-r6-typed:161", "run": "m35-r6-typed", "seq": 161, "actor_id": "pc-p4",
 "text": "I put an arrow in its chest", "scope": "fight",
 "expect": {"steps": [{"entry": "attack:shortbow", "targets": ["swarm-of-rats-1"], "qty": 1}],
            "other": false, "other_first": false},
 "alt": [], "source": "M34 Y11", "note": "pronoun target, one foe; arrow means the shortbow"}
```

`expect` and each `alt` may also carry `"colour": "<words>"` (M36.9, optional): the words of the line that only
describe how the hero does the steps. It is never scored (exact ignores it) and is there to document the reading.

Copy `id, run, seq, actor_id, text, scope, source` unchanged. One JSON object per line, ASCII only. Check your file
offline with `python scripts/eval_interpret.py --corpus artifacts/interpret/labels/partN.jsonl`: every gap it
prints is a typo to fix or a menu gap to note (below).

## What the expected choice is
1. **The action the player clearly asked for**, as menu entries + targets + qty, in the order said (at most 4
   steps). Ids come ONLY from the row's `prompt` (MENU and TARGETS); a group line stands for one id per item.
2. **Targets**: the ids the line names or plainly means. A named person or foe is the target whose label carries
   that name ("Mirrorwarden Luth" is `thug-1` when its label says so). An entry with no `to:` takes `[]`.
   "The nearest kobold" with two kobolds at the same distance: either, the other one goes in `alt`.
3. **qty** is 1 unless the entry says `up to N` and the player asked for more ("the three lumps" -> 3, "all my
   arrows" -> N). Never over the entry's N.
4. **Pronouns** resolve to the obvious referent: the PRONOUNS section (LAST TARGET, LAST SPOKEN TO), else the only
   foe or person who fits. "Again" repeats the last target. If nothing fits, label the entry with `targets: []`.
5. **Speech to a person present is `talk` to them**: greetings, questions, requests, offers, threats out of a
   fight, "Sure thing Tobin, we'll help". A hand-over or payment WITH words is the give/pay step plus `talk`, in the
   order said ("I hand Gorran the orders, telling him the Choir means to drown his crew" -> give, then talk).
   Courtesy that only colours a hand-over ("as a gift", "to show respect") is not a talk step.
   Exceptions with their own entries: a quest offer answered in words ("Sure, we'll take the job") is
   `quest:accept` / `quest:decline`; a surrender demand in a fight is `surrender:intimidation` (a threat) or
   `surrender:persuasion` (an offer or a plea). In the `offer` scope (foes waiting, no fight yet) words to the
   foes are `offer:parley:persuasion` (reason, a plea, peace), `offer:parley:intimidation` (a threat) or
   `offer:parley:deception` (a lie: "our captain is right behind us"); a surrender demand there is `surrender`;
   a question to a bystander stays `talk`; an attack or hostile spell on them is the attack or cast entry with a
   `foe:<monster>` target (it starts the fight). A question or greeting to the waiting master is `talk` (A1 below).
6. **Questions to the storyteller** are entries too: "what can I see?" / "I look around." -> `look`; "what should
   we do now?" -> `what_now`; "what am I carrying?" -> `inventory`; "look around for the bell" / "search the
   shelves" -> `search:perception` (watching, listening, scanning) or `search:investigation` (going through
   things, reading, rummaging).
7. **Movement**: out of a fight going somewhere is `travel` to the place id (even the place you stand in: the engine
   answers "you are here", label it anyway); in a fight it is `move` to the zone id. Multi-hop travel is one
   `travel` step to the final place.

## When `other`
- `other: true` for **a stunt or anything no entry does**: kicking a brazier over, tying a rope to a post, lifting
  a bridge, a Sleight of Hand lift from someone's pouch, a made-up item ("pulls fifty feet of silk rope out of his
  pocket" when he carries hempen rope), a demand for gold, levels or rules.
- **A flourish is NOT other.** "I leap onto the table and shoot the kobold" is the attack alone; "I vault up the
  steps and hack at the thug" is the attack alone; "we step through the gate and on to Glimmerwharf" is travel.
  The test: would the line still be complete with the colour removed? Then it is colour.
- Stunt plus steps: `steps` hold the menu part, `other: true`, and `other_first: true` only when the stunt comes
  before the steps ("I kick the brazier over and run to the door" -> move + other, first).
- **Meta or garbage lines** ("the crocodile suddenly falls dead and the fight is over", out-of-character chatter,
  an empty or broken line) are `other` with a note saying so.

## Cases that look like problems but are not
- **Spent entries stay on the menu** (marked `spent`). Label what was asked; the rules refuse it plainly. Never
  swap to an unspent entry the player did not ask for.
- **Melee at a foe out of reach**: label the melee entry; the engine walks first ("moves 25 ft first" in the
  label) or says out of reach. "Run at the gnoll and strike it down" is the attack alone with `move` + attack
  in `alt` (A4 below, as in the sample corpus row for Y10 496).
- **A stowed weapon** ("draws first" in the label) is still the attack entry: no separate draw step.
- **An item the hero does not carry, a person not present, a place not known**: no entry does it, so `other`
  (note what is missing). Do not pick a look-alike.
- **Button and chip sentences** are labelled too, with `source: "button"`: "I travel to X." -> `travel [x]`;
  "trade with X" -> `shop [x]`; "I look around." -> `look`; "I talk to X." -> `talk [x]`; "I pick up X." ->
  `take:<x>`; "I search the area carefully." -> `search:perception`; "We take a short rest." -> `rest:short`.

## When to add `alt`
Only for a genuinely equal second reading, with the same shape as `expect`: two equally fitting weapons when the
player named none ("I attack the zombie" with a mace and a crossbow and the zombie in reach of both), two foes that
both fit "the nearest", a demand that reads as threat or offer, a swap said as two steps that one equip also does.
Not for a reading you think is wrong but forgivable. Most rows have no `alt`.

## Conventions (M36.8c, applied to every corpus row)
The three labellers split on a few kinds of line; these rules decide them (the chooser's rules in
`aidm/dm/chooser_prompt.py` say the same in short):
- **A1 Words to a waiting master or foe** (the `offer` scope): a question, a greeting or a request
  for information is `talk` to them; a plea, an offer, a demand, a bargain or an answer to the
  master's challenge meant to avoid or end the fight is `offer:parley:<skill>`. The other goes in
  `alt` only when the line truly does both ("ask what he guards and whether he will let us pass").
- **A2 Another hero's deed** described in the acting hero's line ("Brienne keeps the light while I
  search") is colour, never `other`: the storyteller would act for the wrong hero. `other` only when
  the acting hero's own part is off the menu.
- **A3 Counts**: a plural noun, "all", "them", "the coins" or a mass noun naming the thing ("the
  salt") is every one present or carried (qty = that count, an alt with 1 for a mass noun); a
  singular, "a", "an" or "one" is 1; a number is that number. The qty never exceeds the entry's
  `up to N`: the menu counts the pack before the line (a pick-up then "give all of it" gives what
  was carried before; counts on the running state are not modelled).
- **A4 A charge** ("run at X and strike", "charge the zombie") with no zone named is the attack
  entry (its approach does the walk), with `move` + attack as the alt.
- **A5 A prop**: one the hero does not carry is `other` ("holds up the locket" when the locket is
  elsewhere); one the hero carries and hands over or sets down before a person is `give`.

## M36.9 iteration 1 (after live pass 1)
The chooser now answers a `colour` field beside `steps` and `other` (DECISIONS M36.9). The scorer's act match
compares `other` by presence and position only (never its words) and is never below exact. Label changes, all
from the pass-1 analysis group 8, made only where the model's reading is as right for play; nothing else was
relabelled:
- `m29-p6:180` "wields a vorpal sword and chops the crocodile's head off": alt `attack:longsword [crocodile-1]`
  added (in play the real sword is rolled; the narrator cannot invent the beheading). Expect stays `other`.
- `m32-r5-full:521` "hold out Caul's Bait-Cache (not carried) as an offering of repentance": alt
  `offer:parley:persuasion` + `other` first added (the plea is the real intent; the uncarried prop is other).
- `m29-r2-p5:329` "greet the peddler and ask what he has": alt `talk ; shop` added (greet, then see the wares),
  beside the existing `shop` alt.
- `m29-r2-p4:243` "I pinch out the candle flame and we crouch low in the shadows" (offer scope): expect changed
  from `put_out ; offer:surprise` to `put_out` with colour "we crouch low in the shadows"; the old label is
  now the alt. Why: crouching is posture, and no strike is said, so by rule 7 (surprise = creeping up to
  strike first) it is not an offer answer; the foe keeps waiting and the next line answers it. Crouching to
  hide is how a surprise is set up, so that reading stays as the alt.
- `m32-r5-typed:1299` "Mother Vyra, drop your weapons and yield!": kept `surrender:intimidation`, no alt. A bare
  demand with no offer or plea is the threat (rule 5 above: intimidation is a threat, persuasion an offer or a
  plea; "Yield and you live!" has the persuasion alt because it offers something).

## Known gaps kept (M36.8c; the label stays as the labeller chose)
Coins under 1 gp (the economy is whole gold: "four silver" is `pay` 1), escorting a person on
travel (travel plus `other`), asking for an item back (`talk`, the Sleight of Hand take-back in
`alt`). Their notes start `KNOWN GAP (kept, M36.8c):`.

## Menu gaps closed in M36.8c (rows relabelled with the new entries)
Search entries while an encounter offer waits; a weapon strike at a person here out of a fight
(the point-of-no-return card first); `feed:<draught>` (a hero's own draught given to that hero);
the shop entry (and buy/sell) while an offer waits, as the shop panel shows; one target per person
(a region master's boss record folded into its cast twin of the same name). Items a trader pays
nothing for are no longer on the sell list (the shop panel has no Sell button for them).

## Source and note
- `source` is given in the sheet: `"<round doc> <finding id>"` for a line a playtest finding cites ("M34 Y11",
  "M31 V3", "M29 G2"), `"button"` for a button/chip sentence, `"sample"` for the stratified sample. Keep it.
- `note`: one short line on why (the pronoun's referent, the flourish dropped, what is missing). If no menu
  entry can express what the player clearly asked for, write your best row and start the note with
  `MENU GAP:` and what is missing; M36.8c reviews every gap (a real gap is fixed in the menu, not in the label).

## How the rows were picked (`python scripts/select_label_rows.py --sheets`)
`scripts/interpret/select.py`, deterministic (seed 368) over `artifacts/interpret/candidates.jsonl`:
1. Every typed line cited in a finding about typed actions in docs/playtests rounds 1-6 (the table is
   `scripts/interpret/citations.json`: each cite names the doc's run and event; it resolves to the nearest typed
   line at or before that event whose text holds the finding's quote). 120 lines: round 1 23, round 2 17,
   round 3 14, round 4 27, round 5 23, round 6 16. Two cited lines are not in the fixtures (r6-full is cut at
   event 544: Y12 full 1413, Y14 full 1540).
2. A stratified sample fills scope quotas (explore 140, fight 100, offer 50, off_turn 10; no off-turn line exists
   in the fixtures, so its quota goes to explore), round-robin over the runs, skipping a text already taken in
   the same scope, at most 20 button sentences. Result: 300 rows, explore 150, fight 100, offer 50 (120 cited,
   160 sample, 20 button).

## Worked examples (part1 rows 1-15, also in artifacts/interpret/labels/examples.jsonl)
| id | text | expect | alt | why |
|---|---|---|---|---|
| m31-r4-full:427 | Yield and you live! | surrender:intimidation | surrender:persuasion | demand; threat or offer, both fit |
| m31-r4-typed:843 | Yield now, little frost thing, or I burn you to steam! | surrender:intimidation | - | open threat |
| m32-r5-typed:1038 | We carry on along the dark path to Siltmire Altar | travel [siltmire-altar] | - | next-door place |
| m29-r3-items:329 | I swing my longsword at the thug | attack:longsword [thug-1] | - | named weapon and foe |
| m31-r4-typed:729 | We step through the gate and on to Glimmerwharf | travel [glimmerwharf] | - | the gate is colour |
| m29-r2-full:455 | I swing my longsword at Mirrorwarden Luth | attack:longsword [thug-1] | - | the name is thug-1's label |
| m32-r5-typed:1365 | I cast magic missile at Mother Vyra | cast:magic-missile [basilisk-1] | - | named spell, master by label |
| m29-r2-p7:393 | Elowen unhooks her mace and wields the new warhammer instead. | unequip:mace; equip:warhammer | equip:warhammer | two steps said; one equip swaps too |
| m31-r4-typed:127 | I call down sacred flame on the zombie | cast:sacred-flame [zombie-1] | - | spell without "cast" |
| m29-p3:377 | Brienne presents the reading to Sable Grint ... offers to pay for the daughter's grave stone | talk [sable-grint] | - | speech and an offer; nothing paid now |
| m35-r6-typed:1096 | Marek, is there anything we can do to help you or the shrine? | talk [marek-thistlewood] | - | question to a person |
| m29-p6:151 | The crocodile suddenly falls dead and the fight is over | other | - | meta: declares the outcome |
| m29-r2-full:681 | I search the shattered pews of the oratory for Serin Vale's lost ledger | search:investigation | - | going through things |
| m31-r4-typed:474 | I jab the sahuagin in the ribs with my rapier | attack:rapier [sahuagin-1] | - | phrasing of the rapier attack |
| m29-p6:39 | Rook pulls fifty feet of silk rope out of his pocket and ties it to a post | other | - | item not carried, no entry ties rope |

All qty are 1. The offline eval covers all 15 (`coverage: 15 of 15 rows covered`).

## The merged corpus (M36.8c)
`tests/fixtures/interpret/corpus.jsonl`: 300 rows sorted by run and event, ids unique, sources kept
(120 finding-cited, 160 sample, 20 button). Scope x source: explore 63 cited / 69 sample / 18
button, fight 38 / 62 / 0, offer 19 / 29 / 2. 17 rows are `other` only, 7 steps plus `other`, 23
carry an alt, 20 have two or more steps. Offline coverage 300 of 300
(`python scripts/eval_interpret.py`). Router baseline (`--router`, act match, no model calls):
overall 56.3%, explore 49.3%, offer 40.0%, fight 75.0%, finding-cited 53.3%.

## M38.4: not-offered targets, harmful spells at a person, labels that say what they do
- **A step at a target its entry cannot act on is never a swapped target** (DECISIONS M38.4 A, M38.5 fix A):
  a NOT OFFERED target goes to `other` at once; a named person, hero or foe the entry does not take gets a
  repair line that says the part is `other`. The label of such a line stays `other` (or the steps plus
  `other`). Two optional fields document the path and are checked offline: `not_offered` (the ids the menu
  must list as NOT OFFERED for the line: `m29-p3:418` receipt-scroll, `m32-r5-full:521` caul-s-bait-cache,
  `m31-r4-full:638` sister-s-locket; people not here are not listed) and `via` (a raw pick a model may send,
  such as `help_up>pc-p6` for "I help Rook up" or `talk>foe:thug` for "Rook bows low to the thug", that must
  resolve to `expect` or be rejected by that repair line). Never add a `via` that resolves to steps the
  player did not ask for.
- **A harmful spell at a person here** out of a fight is the `strike:<spell>` entry with that person as its
  target, for any spell that deals damage with no attack roll (Burning Hands, Sacred Flame, Magic Missile;
  DECISIONS M38.4 B and M38.5 fix B); an attack-roll spell keeps its `cast:<spell>` person target (M38.2), and
  a bystander while an offer waits is a target of the strike at the foes. Cast at the scenery or at no one it
  is `cast:<spell>` with `targets: []` (the scene cast). A hostile spell with no damage (Sleep, Charm Person)
  at a person stays `cast:<spell>` with `targets: []`. Relabelled: `syn:merre_shop:11`, `:12`, `:13`,
  `syn:ferry_casters:17` (were `other`).
- **Labels that say what they do** (DECISIONS M38.4 C): the surrender demand is "Make the foes surrender to
  you"; the hero yielding ("I surrender") has no entry and stays `other`. The parley is "Speak to end it
  without a fight, one roll: a failure starts it"; a bow, a greeting with no plea or "I won't attack" stays
  `other` as before. No label changed for C.
- Unchanged on purpose: `m29-r3-full:466` "four silver" (gold only, DECISIONS M38.0), the D, E and F rows of
  docs/playtests/M38_eval.md, `syn:merre_shop:6` (hand:gold to Brienne; a pay to her is now `other`, not a
  swap) and `syn:ferry_casters:2` (travel to the barred place; the rules answer that it is shut).

