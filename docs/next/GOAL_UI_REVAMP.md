# GOAL: Dark pixel UI (M24)

Owner request 2026-10-16. Binding. The owner approved the mockup "Dark pixel v2" (canvas
"AIDM UI Revamp Concepts", page Dark pixel v2; renders in `docs/next/ui_revamp/`). Keep the buttons,
the information each screen shows, the icons and the pixel art. Replace the brown/gold look and the
background.

## Owner answers
- Every phone tab, top to bottom: ribbon + picture, the tab content, the hero strip (name, class,
  Second Wind, HP bar, AC shield), the tab menu at the very bottom. This supersedes M18.2 (tabs on top).
- Bottom only: no "menu at the top" setting. Full screen (button on the picture) is the answer when a
  browser toolbar covers the bottom (Brave Android, M18.2).
- Generate more assets when something new or unexpected turns up (through the asset rules below).

## Look
- Ground: near black `#0b0b0d` with a barely visible stone tile (`ui_skin.stone`). No gold glow, no scanlines.
- Text: `#dedad0` main, `#aba79d` secondary, `#85827a` hint (all pass 4.5:1 on the cards).
- Fonts: Jersey 10 for titles, labels, buttons and numbers; VT323 (OFL, local file) for body text.
- Cards: the iron frame (`ui_skin.frame`, 9-slice, 8 px on phones, 10 px on the TV). Only the picture and
  the main cards are framed: no frames inside frames, no framed buttons, chips or tab cells.
- Buttons: flat. Secondary = `#18181b` fill, 2 px `#3a3a40` border, dark inset bottom edge. Primary =
  the tab colour fill with its light border. One primary per card.
- One colour per tab, used by its ribbon, its active tab cell, its primary buttons and its labels:
  Play teal, Play in a fight crimson, Hero blue, Journal olive, Scribe purple, More grey.
  | colour | light (labels, borders) | mid (fills) | dark (gradient end) | ribbon art |
  |---|---|---|---|---|
  | teal | `#6fc0ba` | `#255e60` | `#163a3c` | `ui_skin.ribbon-teal` |
  | crimson | `#e0767d` | `#6a2129` | `#3a1015` | `ui_skin.ribbon-crimson` |
  | blue | `#86a8e4` | `#2b4b80` | `#172a4a` | `ui_skin.ribbon-blue` |
  | olive | `#aebe68` | `#4a5a22` | `#283112` | `ui_skin.ribbon-olive` |
  | purple | `#b096ee` | `#47307c` | `#24183f` | `ui_skin.ribbon-purple` |
  | grey | `#b4b4bc` | `#3c3c44` | `#222226` | `ui_skin.ribbon-grey` |
- HP bars red (`#df5d57` over `#ad302d`), XP and movement bars blue (`#6aa2ea` over `#3a6fba`).
- Slots (hotbar, equipment, portraits in the turn order): `ui_skin.slot`, `ui_skin.slot-selected` (cyan, the
  chosen or acting one), `ui_skin.slot-far` (red, out of range or a foe).
- AC is an iron shield (`ui_icon.ac-shield`) with "AC" and the number on it. Timer: `ui_icon.hourglass`.

## Phone pictures (ribbon text / picture)
- Play: the location name / the place's region banner (`region_banner.<terrain>` from the scene's
  terrain, else the tier banner). In a fight: "ROUND n · YOUR TURN" (or whose turn) / the zone the
  hero stands in, with the zone name and the turn timer on the picture.
- Hero: CHARACTER / the hero's portrait. Journal: JOURNAL / `scene.journal` (map desk).
- Scribe: THE SCRIBE / `scene.scribe`. More: MORE / `scene.more`.

## TV (/screen)
- Top: the location ribbon over the region banner, the main objective as a caption on the picture.
- Fights: no ribbon on the board. A turn-order bar: "ROUND n" label, then the order as slot portraits
  with names (the acting one outlined in crimson), the zone legend at its right end. Bigger hexes;
  each zone shows name, cover and size on two lines (nothing under the lower hex).
- Party (slot portrait, name, class, HP bar with numbers in a fixed column, AC shield), the acting
  timer (hourglass, name, m:ss), rolls (die slot, who and what, total right aligned with HIT/MISS).

## Asset rules
- Art only through manifest keys and `assetUrl`; CSS gets the skin as custom properties set by
  `js/ui/skin.js` from `realAssetUrl` (`none` when the file is missing, so placeholders stay usable).
- New pieces are `UI_ART` entries (`aidm/server/asset_ui.py`; real, so never regenerated),
  source `generated:gpt-image-1.5-m24` in the manifest. More pieces may be generated with the image
  key when the work needs them; each one is judged by eye before it is installed.

## Done means
All phone tabs, the fight hotbar, the TV, the lobby, character creation and every dialog use the new
look; the UI suite passes; screenshots of the real app at 390x844, 393x702, 1280x720 and 1920x1080
are judged; the player manual describes the new layout (tabs at the bottom).
