# GOAL: Tooltips on the phone (M28)

Owner request, 2026-10-17. Binding. Main-session decisions are marked **D:** and repeated in docs/DECISIONS.md.
Runs after M27 (Gear that matters) so item uses get their tooltips too.

Owner: "Tooltips for everything on the phone (enable tooltips button). We have items but players might like a
tooltip, same with spells explaining what the spell does etc." and "I want a small '?' icon to be present. When
pressed a small popup opens acting as the tooltip. Press to hold is bad design."

## Owner answers
1. A small **'?' icon** next to each thing that can be explained. Pressing it opens a **small popup**: the tooltip.
2. **No press-and-hold** anywhere.
3. Tooltips can be switched on and off (a **Tooltips** switch).
4. Phone only (the screen keeps its legend).

## How it works
- **Settings (More tab): Tooltips**, ON by default, remembered per device (`localStorage` in try/catch; the page
  works without it). Off = no '?' icons at all.
- **The '?' icon:** small and quiet (tab colour, pixel style), next to the name of the thing it explains. Its touch
  target is at least 24x24 px (WCAG 2.2 AA), even when the drawn icon is smaller. It never changes what tapping the
  thing itself does: tapping a hotbar slot still picks it, tapping an item still opens its card.
- **Dense grids** (hotbar slots, the pack grid): the '?' sits in the slot's corner on its own touch target, clear of
  the slot's own tap area. **D:** if a corner badge proves too cramped at 390 px in the review, the '?' moves to the
  line that names the picked slot or tapped item instead (judged on screenshots, M28.6).
- **The popup:** small (max ~280 px wide), anchored to its '?', kept inside the viewport (flips above or below),
  non-modal (the game keeps running behind it), one open at a time. Closes on its X, a tap outside, Esc, or when
  the view under it changes. Title, 1 to 4 short lines, no scrolling for normal entries. Accessible: the '?' is a
  button named "What is <name>?", the popup is announced, focus returns to the '?' on close.

## One source of truth for the text
**D:** tooltip text is built from the game data by ONE pure builder, `aidm/rules/explain.py`, never written by hand
in the client. Spells have no description text in our data (only casting time, range, targeting and effects), so
their tooltip is built from those fields and cannot disagree with the engine:
*Fire Bolt. Cantrip, action. Ranged spell attack, up to 2 zones away. 1d10 fire.*
- Spells: level or cantrip, action cost, range in zones, attack or save (ability), damage dice and type, conditions,
  surfaces, area, concentration, what a higher slot adds.
- Items: kind, weight, value, healing, camp supply, what a key opens, its M27 uses ("Light this dark place").
- Conditions: the SRD description, shortened. Features: their data text or built from their mechanics.
- Combat words: actions (Dash, Dodge, Disengage, Help, Hide...), health words (Unhurt ... Fled), advantage and
  disadvantage, cover, high ground, rough ground, surfaces, Dark/Lit, range rules.
- Sheet: abilities, saving throws, skills, speed, initiative, proficiency, passive Perception, AC, HP, XP, spell
  slots, camp supplies, rests, keepsakes vs quest items.
- Journal and Play: main quest, ways (Force/Peace/Cunning), leads, left behind, favours, What now?, the Scribe,
  shop prices.
Served once as static JSON (`GET /api/tips`, like the manual route), keyed `<kind>:<id>`; the client caches it.
`scripts/gen_manual.py` reuses the same builder for its generated tables, so the manual and the tooltips never drift.

## Where the '?' goes (everything on the phone)
- **Hero tab:** ability tiles, saves, skills, the overview facts, features, conditions, training, every worn and pack
  item, keepsakes and quest items, spells and spell slots.
- **Fight:** every hotbar slot (attacks, spells, actions, bonus actions, items, class features), target chip health
  words, the advantage/disadvantage tag, Move list badges (cover, high ground, rough, surfaces, Dark/Lit), the
  conditions on the hero strip.
- **Play:** the Now card, the quest offer card, the finale card, the roll card terms (DC tier words).
- **Journal:** main quest, ways, leads, left behind, favours. **Shop:** buy and sell prices. **Scribe**, **More**.

## Done means
- With Tooltips on, every element listed above shows a '?'; pressing it opens the popup with text from
  `/api/tips`; with Tooltips off, none show. No press-and-hold anywhere (a UI test asserts no long-press handler).
- Tapping a hotbar slot or an item still does exactly what it did before (existing tests unchanged).
- Spell tooltips match the engine for a golden set (Fire Bolt, Cure Wounds, Sleep, Shield, Fireball).
- The popup never leaves the viewport at 390x844 and 393x702; a11y tests pass.
