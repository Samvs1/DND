# GOAL: The Scribe (M13) and the Player Manual (M14)

Owner request, 2026-10-09. Binding. Decisions taken by the main session are marked **D:** and repeated in
docs/DECISIONS.md when they land.

## Who he is
- A standalone being outside the story, quietly watching over it. Warm, courteous, ancient, drily amused;
  treats life and death as paperwork he is fond of. Godlike and mythical, never threatening, all the time in
  the world, motivations unexplained.
- Inspired by the tone of a well-known RPG's undead "wise servant" character. **Capture the tone, not the
  lines.** All dialogue is original. No names, lines, lore or art from that game (CLAUDE.md BG3 rule).
- Core look (owner art, keep it): a skeleton in a deep purple hood and robe, softly glowing violet eyes,
  writing in a ledger with a quill by candlelight, ink pot, old books. Owner files (read-only, never edit):
  `C:\Users\vanst\Downloads\DnD UI\Characters\The Scribe.jpg`, `The Scribe extended.jpg`,
  `The Scribe background.png`, `Extended\The Scribe Extended.jpg`, `Extended\1x\The Scribe cropped.png`,
  `Extended\1x\Scribe phone background.png`. Both .jpg files carry a small sparkle watermark at the bottom
  right; any copy we ship is cropped or masked so it is gone.

## What he does
1. **Welcome**: when the players load in he introduces himself, welcomes them and speaks warmly about
   fellowship and the road ahead, about one minute (**D:** `welcome.first` on a new campaign start,
   `welcome.return`, about 20-30 s, when a saved campaign is loaded). Shown on /screen with his portrait and
   subtitles; the opening narration waits until he is done; the host can skip him from their phone.
2. **Victory**: he congratulates the party on the victory screen, with random variants so it does not repeat.
   **D:** two moments: a short line on a won fight (`victory.fight.*`, 5 variants, 5-12 s, shown as a
   victory banner on /screen) and a longer one on the campaign victory screen (`victory.campaign.*`,
   3 variants, 25-45 s, a full overlay like the defeat overlay, with the epilogue). The server picks the
   variant with the table RNG and never repeats the previous pick.
3. **The Scribe tab** on the phone: pay him to revive a fallen teammate, who is "rewritten" into the story.
   - Only outside combat. During combat the tab stays visible but disabled and he explains why, in character.
   - Uses the existing currency (`Character.gold`, `GoldChanged`) and character state (`dead`, HP).
   - Edge cases: not enough gold, nobody fallen, several fallen (each listed with its own price), payer down,
     defeated table (locked by the defeat flow), paused table.
   - **D: price** = `per_level_gp x level of the fallen hero` with `per_level_gp = 25` (level 1: 25 gp,
     level 5: 125 gp; a potion of healing is 50 gp, a tier-1 fight drops 1d6-2d6 gp). Tunable in
     `data/bg3/scribe.json` with `base_gp`, `per_level_gp`, `restore` and `payment`.
   - **D:** "fallen" = a PC with `dead: true`. A PC at 0 HP who is still alive is not his yet (he says so).
   - **D:** the paying player's own hero pays (`payment: "payer"`); the payer's hero must be alive.
   - **D:** the revived hero returns with half its max HP (rounded up, `restore: "half"`), death saves reset,
     not dying, conditions cleared except exhaustion.
   - Voice lines: revive confirmation (3 variants), refusal during combat (2), insufficient funds (2).
     **D:** plus `none_fallen` (1) and `not_yet` (1, the hero is down but alive), text and voice.

## Audio: built by us, never by hand
- Fish Audio voice model (reference id) **`dab97346a1464e6ba09a592b4bd4b7d2`**. Generated at build time by a
  script; the API key (`FISH_API_KEY` in .env) never reaches client code or the repo.
- ONE config file, `data/voice/scribe.json`: voice model, TTS settings, the processing chain and every line
  (id, text, optional per-line chain overrides). The game reads the line texts from the same file (one source
  of truth for what he says). Changing the file and rerunning the script regenerates everything.
- Raw Fish output is requested as WAV (no lossy step) and cached in gitignored `artifacts/voice/raw/`, so a
  chain tweak reprocesses without new API calls. Processing runs at 48 kHz float64; the only lossy encode is
  the final one (mp3 320 kbps or better).
- Target sound: dry, warm, aged, slightly hollow, with a smooth dark hall-like reverb tail. Expensive and clean.
- Avoid: ANY pitch shifting (a too-deep version was rejected); heavy distortion, bitcrushing, stacked echo or
  chorus (metallic, lo-fi); aggressive high roll-off (keep the air); generational loss.
- Reference chain (starting point, tune per line, shorter lines drier): gentle high-pass, a little low-mid
  warmth, a touch of presence, soft top-end taper around 12 kHz, light compression, convolution reverb about
  30% wet with a synthetic dark hall impulse response, loudness normalisation to -16 LUFS (true peak <= -1 dBTP).
- Verification (the session cannot listen): per line LUFS, true peak, median F0 before vs after processing
  (must match: proves no pitch shift), energy above 10 kHz before vs after (air kept), wet/dry ratio and
  tail length, and spectrogram images that the main session opens and judges. Any change from the reference
  chain is reported to the owner.

## Visuals
- Reuse the owner art where it fits (seated at the ledger: tab header, subtitles card).
- Generate a few poses with the M10 image pipeline (budget-capped, reviewed, his art as reference images,
  same aesthetic, same core look): **D:** `portrait.scribe.welcome` (rising from the desk, one hand open in
  greeting, quill in the other) and `portrait.scribe.rewrite` (writing glowing violet words into the ledger,
  a faint figure of light forming above the page). Total art spend stays under the 15 EUR cap.

## The Player Manual (M14), created AND maintained
- `docs/PLAYER_MANUAL.md`: everything a player needs: setup and joining, screen vs phone, hero creation
  (races, classes, ability scores, backgrounds, skills, spells), exploration and actions, checks and DCs,
  votes, travel, rests, shops, combat (zones, d4 initiative, actions, bonus actions, reactions, movement,
  surfaces, high ground, cover, conditions), spells and slots, levelling, dying and death, defeat and retry,
  the Scribe and his prices, audio and voice, host controls, troubleshooting.
- Reference sections (classes, races, conditions, spells, surfaces, prices) are generated from the data files
  between markers by `scripts/gen_manual.py`; `--check` is a gate step, so data changes force a manual update.
- In the game: a Manual entry on the phone's More tab and a `/manual` page, both rendered from the same file.
- Maintenance rule (CLAUDE.md): every change to a player-facing mechanic updates the manual in the same commit.

## Acceptance
1. FULL gate green (with the new voice `--check` and manual `--check` steps).
2. Rules: golden price tests, every refusal path tested, revive replay equals the snapshot.
3. Playwright (screen 1920 + two phones 390): Scribe tab disabled in combat with his reason, revive with
   enough gold, refusal without, nobody fallen, several fallen; welcome overlay and skip; fight victory banner;
   campaign victory screen. Screenshots opened and judged.
4. Voice: every configured line generated, processed, measured (table in the final report), spectrograms
   opened; the script reruns from the config alone.
5. Manual: complete, accurate (checked against code by a fresh read-only reviewer), in-game and `--check`ed.
