# GOAL: the phone is a controller, not a second screen (M18, owner request 2026-10-10)

Owner: "We don't need to see the text on the phone screen itself since it's on the central screen. Come up with
a new sleek UI where the information on the screen and the phone are not necessarily always duplicated (like the
narrated text)." And: the bottom tab bar is still hidden in Brave on Android (its bottom toolbar covers the page).

## Rule of thumb
The screen is for watching together: story, voice, party, board, big dice, Scribe. The phone is for MY hands:
who I am, what I can do here, how I say it, and what happened to my own rolls. Nothing on the phone repeats the
narration. The story stays reachable (Journal, Story) for a player who missed a line, but it is never in the way.

## Layout (all tabs)
```
+--------------------------------------------+
| [portrait] Name  AC 18   [status chip] [FS] |  hero header (HP bar, conditions, resources)
| Play | Hero | Journal | Scribe | More      |  tab bar at the TOP (never under a browser toolbar)
|--------------------------------------------|
| [vote card, sticky, when a vote is open]   |
| pane content (scrolls)                      |
|                                             |
| ... scroll room (6rem) so the last item can |
|     be scrolled above a bottom toolbar      |
+--------------------------------------------+
```
- Nothing essential is pinned to the bottom of the viewport. The vote card moves from a bottom sheet to a
  sticky card under the tab bar. Toasts stay at the top.
- [FS] = a Full screen button (Fullscreen API) where the browser supports it: on Android it hides the browser's
  own bars. Also in More. No PWA manifest: installability needs a valid certificate, which a LAN game with a
  self-signed one does not have.

## Play tab, exploring
1. **Now card**: one big line saying what is going on for ME: "Your move", "The story is being told: watch the
   screen" (narration in progress), "Weighing Mira's action", "Queued: you are 2nd", "Paused", "Your hero is
   down". Under it the place (scene name) and the first active quest objective, small.
2. **Composer**: the action box (Act, Dictate) right under the Now card, near the top, so neither a bottom
   toolbar nor the keyboard hides it.
3. **Ideas chips** (from the public scene, tap = put a sentence in the composer and focus it, never auto-send):
   - People here: "Talk to <npc>" per NPC in the scene.
   - Things here: "Examine <feature>" per discovered feature, "Take <item>" per loose item.
   - Ways on: "Travel to <exit>" per exit (a locked exit is shown dimmed with a lock).
   - Always: Look around, Search, Short rest, and Trade (opens the shop) when a shopkeeper is present.
   Each group has a small icon (`ui_icon.act-<kind>`; placeholders until M18.3 generates them).
4. **Your last roll**: a slim card with my most recent roll (label, dice, total, outcome), persistent; the
   5 s toast still pops on a new roll.

## Play tab, in a fight
Now card ("Your turn 2:41" / "Mira is acting"), then the hotbar and target chips on my turn, the suggestion
box on someone else's turn. The composer shows only on my turn (creative actions). No story text.

## Journal tab
Sub-tabs Journal, Map and **Story**: the recent story in full (the old Play story box), for catching up.

## Not changed
Hero (sheet, inventory, spellbook, level up), Scribe and More keep their content; the screen is unchanged.
