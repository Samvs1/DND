# GOAL: shared screen + phone controllers, defeat flow, split volumes, remaining art (M11, M12)

Owner feedback after a first playthrough (2026-10-08), verbatim intent:

1. ONE shared UI (`/screen`) shows the texts, combat details and so on. Every player joins with a phone or
   own device over the LAN. On their own device (`/play`) they see the personal things (inventory, spellbook,
   journal ...) and, very important, THEIR OWN ACTIONS: type or speak an action on the phone and it plays out
   on the shared screen. Out of combat the floor is first come first served. The goal is a much less cluttered UI.
2. Singleplayer death bug: the hero died, there was no defeat screen, the player lay there unconscious but
   could still type, the narrator kept answering and nothing happened. (Log of the run: saves/c-20261008-161136-2923.)
3. Narrator volume and music volume must be separate options.
4. Generate every asset still left as a placeholder (or that improves the product) with the OpenAI image key.

## Evidence from the logged run (do not re-investigate)
- Wolf bite took Sam to 0 HP, `condition_applied unconscious`, `encounter_ended status=defeat`, then three more
  `narration_recorded` and nothing else. No death saves ran (combat was already over), no phase change, no
  lock, no UI. `session/combat_flow.finish_fight` just returns to exploration with the party at 0 HP.
- `/screen` (views/screen.js) is already a read-only spectator view that plays narration and music.
  `/play` (views/table.js) is the full table. Nothing splits the personal parts out.
- Audio has ONE `volume` setting (js/settings/model.js) used by both narration.js and music.js.

## Owner decisions (answered, binding)
- Defeat: **defeat screen + retry.** Death saves keep running while a hero is dying and someone can still act. When the
  whole party is dead or down with nobody able to act (a wipe), the table enters a DEFEATED state: in-fiction
  epilogue, input locked, and the options **retry from the last checkpoint** (auto checkpoint at each scene
  arrival and each fight start), **load a save**, **new adventure**.
- Devices: **always two surfaces.** `/screen` is the shared display, `/play` is the slim controller. There is NO
  combined single-device view; solo play opens /screen on one device and /play on another (or a second window).
- Voice: **keyboard dictation + optional HTTPS.** Typed input always works (the phone keyboard mic works anywhere).
  `python -m aidm --lan --https` serves a self-signed certificate so the in-app mic button (Web Speech API) works
  on phones; without a secure context the mic button is hidden and a one-line hint explains the keyboard mic.
- Budget: **15 EUR total** (`--cap 15`, ledger total includes the 2.3124 EUR already spent). Sound effects and music
  are not images and stay placeholders.

## Design (orchestrator's decisions inside those answers)
- Screen shows: scene art + title, story feed, party strip (HP, conditions), initiative + combat board, the dice
  roll display (big), queue ("Sam is typing", "next: Mira"), vote prompts (read-only with counts), notices, the
  level-up and defeat overlays, the join QR when seats are free. It plays narration and music. No inputs except
  a small audio gear (local volume).
- Controller shows: whose turn it is, MY action box (type or mic), my hotbar and target chips in combat (no
  board), my hero (overview, inventory, spellbook, level-up), journal, map, shop, host panel (host only),
  settings, the last narration line only, a toast for my own dice results. Tabs at phone width.
- Targets on the phone come from a target list (chips with name + HP bar), the board stays on the screen.
- Audio remote: any seated player's volume sliders (narrator, music, mute each) set the SCREEN's audio through the
  server (`audio_settings` message, stored in table state, broadcast to the screen). Last write wins.
- Defeat checkpoints are stored as event-log sequence markers in `saves/<id>/checkpoints.json` (state at a marker =
  replay of the first N events). Retry truncates the live log to the marker (old log kept as `events.<n>.defeat`)
  and reseeds the dice so the same fight can end differently. Replay must still equal the snapshot.

## Acceptance (each proven by raw output in the final report)
1. FULL gate green (pytest, ruff check, ruff format --check, pyright, lint-imports, check_structure, check_secrets,
   gen_protocol --check, build_manifest --check, gen_assets_todo --check) with the new tests.
2. Deterministic regression test that reproduces the logged death (single hero dropped to 0 HP by a wolf) and now
   ends in the DEFEATED state with input refused, plus a retry test and a replay-equals-snapshot test.
3. Playwright with THREE browser contexts (one /screen, two /play phones at 390 px): a phone action appears on the
   screen, a second phone's action queues behind it, a combat turn is played from the phone, the screen shows
   the defeat overlay and the phone shows retry/load/new. Screenshots opened and judged.
4. Volume: unit + UI tests that narrator and music volume are independent, persisted, and settable from a phone.
5. HTTPS: `python -m aidm --lan --https` boots (healthz ok over https), banner shows the https URL, mic button
   present only in a secure context (test).
6. Art: dry-run (`--tier 2` / all remaining), real run under `--cap 15`, ledger printed, every accepted asset
   style >= 4, rejected ones listed, FINAL_REVIEW opened, new Playwright screenshots opened.
7. check_secrets: no key material in tracked files; `.env` values never printed.
