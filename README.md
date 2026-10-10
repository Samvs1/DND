# AI Dungeon Master (aidm)

A D&D 5e game for 1 to 4 players on one local network, with an AI Dungeon Master.
Rules come from the SRD 5.1 and follow Baldur's Gate 3 style combat (zones instead of a grid, d4 initiative,
bonus actions, surfaces, high ground). The AI only describes and decides what happens through typed tools;
the rules engine owns every number, so the dice, hit points and spell slots are never made up by the model.

Players join from a phone or laptop browser, build a hero in a wizard, explore together by typing what they
do, and fight with a hotbar. A `/screen` page shows the story on a TV and plays the narrated voice.

## Requirements

- Windows 10 or 11 and Python 3.13 (the project is developed and tested on Windows only).
- A DeepSeek API key for the live Dungeon Master (optional: without it the game still plays with built-in
  fallback narration, see Troubleshooting).
- A Fish Audio key and voice id for spoken narration (optional).
- A modern browser. Chromium is installed through Playwright for the UI tests only.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m playwright install chromium     # only needed for tests\ui
```

Copy `.env.example` to `.env` and fill in the values you have. `.env` is gitignored; never commit it and never
paste its contents anywhere. The names (see [.env.example](.env.example)) are:

| Name | Purpose |
|---|---|
| `DEEPSEEK_API_KEY` | the Dungeon Master brain (live AI) |
| `DEEPSEEK_MODEL_FAST`, `DEEPSEEK_MODEL_QUALITY` | model ids; blank = discovered from the API |
| `FISH_API_KEY`, `FISH_VOICE_ID`, `FISH_VOICE_NAME`, `FISH_MODEL` | narration voice |
| `TTS_ENABLED` | initial voice on/off (the host can toggle it in the game) |
| `AIDM_HOST`, `AIDM_PORT` | bind address (default `127.0.0.1:8000`) |
| `AIDM_FAKE_LLM` | `1` = deterministic fake AI, used by tests |
| `RUN_LIVE` | `1` = enable the live API tests |
| `IMAGE_PROVIDER`, `IMAGE_API_KEY` | reserved for the asset generator (M10) |

## Running

```powershell
python -m aidm                  # http://127.0.0.1:8000/  (this computer only)
python -m aidm --lan            # reachable from your network; prints a LAN URL, the lobby shows a QR code
python -m aidm --lan --https    # the same over https (self-signed), needed for the phone mic button
python -m aidm --load <id>      # open a saved campaign instead of a new lobby
python -m aidm --saves D:\games # keep saves somewhere else (default .\saves)
$env:AIDM_FAKE_LLM = "1"; python -m aidm   # no API calls at all (offline demo, deterministic)
```

Other flags: `--host`, `--port`. Saves live in `saves\<campaign_id>\` and are gitignored.

### Playing over the LAN (Windows Firewall)

`--lan` binds to all interfaces so phones on the same Wi-Fi can open the printed `LAN URL` (or scan the QR in the
lobby). The first time, Windows asks whether Python may accept connections: allow it on **private networks**.
If the prompt never appeared or you dismissed it, add an inbound rule for TCP port 8000 (or the port you chose)
in Windows Defender Firewall, scoped to the private profile, or allow `python.exe` there.

This is meant for a trusted home network only: there are no accounts, and without `--https` there is no TLS.
A player is identified by a random token kept in their browser. Do not expose the port to the internet.

### HTTPS and voice input

`--https` creates a self-signed certificate in `certs\` (gitignored; reused while it is valid and still covers
`localhost`, `127.0.0.1` and the LAN address) and serves everything, including `/healthz`, over https. The LAN
URL and the QR then start with `https://`. Each browser warns about the certificate once: choose "Advanced",
then continue to the site. Browsers only allow speech input on a secure page, so the mic button next to Send
appears only over https (or on `127.0.0.1`) in a browser with speech recognition. Without it, the action box
shows a hint to use the dictation key of the phone keyboard instead.

## How to play

Every player-facing rule is in the [Player manual](docs/PLAYER_MANUAL.md). It is also in the game: the **Player manual**
button on the phone's More tab, or the page `/manual`. Its reference tables are generated from the data
(`python scripts/gen_manual.py`, checked by the gate).

The game always uses two kinds of surface. **`/screen`** is the shared display on a TV or laptop: scene art,
the story, the party, the battle board, big dice, who is acting and who is waiting, votes, and the narrator
voice and music. Each player's **phone** is their controller (`/` or `/play`). There is no combined
single-device view: to play solo, open `/screen` in one window and `/play` in another (or on a second device).

1. **Screen**: run `python -m aidm --lan`, then open `http://<host>:8000/screen` on the TV. It shows a QR code
   while seats are free.
2. **Host**: open the LAN URL on your phone (or scan the QR) and enter your name. The first player in is the
   host; if the host leaves the lobby, the next player still there becomes host (during an adventure after
   60 seconds away). Everyone else does the same. Reconnecting with the same browser brings you back to your
   hero. After a server restart every open page shows the join form again (an old page never takes a seat by itself).
3. **Wizard**: each player builds a hero: race, class (fighter, rogue, wizard, cleric, ranger, warlock),
   ability scores (point buy, standard array or rolled), skills, equipment, spells and a short backstory. You
   can export a hero to a JSON file and import it later.
4. **Start**: when every player has a hero the host starts the campaign. The AI writes a three-act campaign
   (or uses the built-in sample). The screen shows the table and each phone opens its controller, with five
   tabs at the top: **Play**, **Hero**, **Journal** (with the map and the story), **Scribe** and **More**. The full
   screen button next to the hero hides the browser bars (Android).
5. **Exploration** (Play tab): type (or dictate) what your hero does. The phone is a controller, not a second
   screen: a Now card (your move, the story is being told, who is acting, your place in line), the action box,
   idea chips from the scene (people, things, ways on, look, search, rest, trade; a tap fills the action box)
   and your last roll. The story and every roll are on the screen (Journal, Story keeps the recent story). Actions queue in order,
   one waiting action per player: the screen shows who is typing, who is acting and who is next, and your
   phone shows "Waiting (n)". Travel, rests and shopping ask the table for a quick vote.
6. **Combat** (Play tab): the zone board and initiative strip are on the screen. Your phone says the round and how
   many turns until yours; on your turn it shows "Your turn", target chips (name and health state), and the hotbar with hit chances, spells with slot counts,
   class features, items, move, dash, disengage, hide and end turn. Other players can send suggestions.
   **The Scribe** (Scribe tab): when a hero has fallen, a standing hero can pay 25 gp per level of the fallen hero
   to have the Scribe rewrite them into the story. Outside combat only. He speaks rarely: a welcome, a welcome
   back, the campaign victory and a brief line at a revive. If he refuses, his reason shows as text on your
   phone. He speaks and appears only on the shared screen; the host can skip him from the Host panel and anyone
   can skip on the screen.
7. **Hero** tab: stats, inventory (equip, unequip, drop, use), the spellbook, and the level-up dialog when you
   have earned a level (levels 1 to 5). The **Journal** tab holds the journal and the map (travel).
8. **More** tab: settings, text size, hero file export, the host panel (host only) and the screen's audio
   remote: separate narrator and music volume and mute. Any seated player can change them; the last change
   wins. The screen's gear button has the same sliders for the screen itself. The screen is the
   audio device and the only one: phones never play sound, and it asks for one click when it opens.
9. **Defeat**: if the whole party falls, the screen shows the defeat overlay and the phones lock. The host (or
   the only player) can retry from the last checkpoint (arriving in a scene or a fight starting), load a save,
   or start a new adventure. A retry rerolls the dice, so the same fight can end differently.

### Host controls

The host panel offers pause and resume, kick a player, monster hit-point and damage multipliers (0.25 to 3.0),
the voice on/off switch, save, load, new campaign, end campaign and token totals. Only the host can use them.

## Tests and gates

```powershell
powershell -ExecutionPolicy Bypass -File scripts\gate.ps1     # the full gate: 12 checks, prints PASS/FAIL each
pytest -q                                                   # the unit, property, ai, session, sim and ui tests
$env:RUN_LIVE = "1"; pytest -q tests\live                   # real DeepSeek and Fish (costs a little money)
python scripts\simulate_party.py --seeds 5                  # 3 bot players over real websockets, fake AI
python scripts\simulate_party.py --seeds 1 --live-ai        # the same with the real model
pytest -q tests\ui                                          # Playwright, two browser contexts, screenshots in artifacts\ui
```

The gate runs `pytest`, `ruff check`, `ruff format --check`, `pyright`, `lint-imports`, `check_structure.py`,
`check_secrets.py`, `gen_protocol.py --check`, `build_manifest.py --check`, `gen_assets_todo.py --check`,
`gen_scribe_voice.py --check` (the Scribe's audio matches `data/voice/scribe.json`) and
`gen_manual.py --check` (the generated tables of `docs/PLAYER_MANUAL.md` match the game data).
How the code is organised is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Adding or replacing art

Every image the game shows is looked up by key through the asset manifest
(`aidm/web/static/assets/manifest.json`). A key without a real file shows a generated placeholder,
so the game is always playable.

1. Open `ASSETS_TODO.md`. It lists every entry still on a placeholder, with the exact target file
   path, size, transparency need and a ready-to-use image prompt (style: `docs/STYLE_BIBLE.md`).
2. Drop your image at that exact path (for example `aidm/web/static/img/portraits/npc/acolyte.png`).
3. Run `python scripts/build_manifest.py`. The manifest flips that entry from `placeholder` to
   `real` and the game serves your file. No other change is needed.
4. Run `python scripts/gen_assets_todo.py` to refresh `ASSETS_TODO.md`.

`python scripts/build_manifest.py --check` and `python scripts/gen_assets_todo.py --check` fail when
the manifest or the TODO list is stale. To try the game with all real art hidden, copy `aidm/web`,
delete `static/img` in the copy and start the server with `AIDM_WEB_ROOT=<copy>`.

### AI-generated art

Some art is AI generated (277 assets: portraits, banners, monster tokens, spell, item and condition icons,
and the phone's action icons). The rest are still placeholders. It was made by `scripts/gen_assets.py`
(OpenAI image API, hard cap 15 EUR since 2026-10-10 (`--cap 15`), every call booked in `logs/asset_spend.json`), reviewed with `scripts/contact_sheet.py` and
installed with `scripts/install_assets.py`. `scripts/final_review.py` and `scripts/assets_report.py` write the
final review sheets and `ASSETS_REPORT.md`. To undo one asset: `python scripts/revert_asset.py <key>`.
License caveat: AI generated via OpenAI API, check provider terms before commercial use.

### Regenerating the Scribe's voice

The Scribe's lines are built, never hand-edited, by `scripts/gen_scribe_voice.py` from the one config
`data/voice/scribe.json` (voice model, TTS settings, the sound chain, per-length profiles and every line).

```powershell
python scripts/gen_scribe_voice.py                   # dry run: lines, characters, cached vs API calls
python scripts/gen_scribe_voice.py --yes             # Fish TTS for new or changed text, then build all
python scripts/gen_scribe_voice.py --reprocess       # rebuild from the cached raw audio, no API calls
python scripts/gen_scribe_voice.py --reselect        # re-pick the best cached take (lines with takes > 1)
python scripts/gen_scribe_voice.py --only revive.1   # repeatable, limits any run
python scripts/gen_scribe_voice.py --check           # offline: exit 1 if any file is missing or stale
```

`--yes` needs `FISH_API_KEY` in `.env` (never printed). Every approved raw take is also archived losslessly
as FLAC in `data/voice/takes/` (committed, the paper trail): a fresh clone rebuilds every line bit for bit with
`--reprocess`, and `--check` fails when a take in use is not archived. The raw Fish WAVs are cached in
`artifacts/voice/raw/` (gitignored), keyed by text and voice settings, so sound tweaks to the chain are free:
edit the config and run `--reprocess`. A line may set its own `voice` (e.g. `prosody_speed`), `voiced: false`
(text only, no audio) or `takes: N`: N takes are generated and the one whose final word (after the last
pause, like "Rise.") is longest, loudest and not rising in pitch is kept; every take stays in the cache. Output: `aidm/web/static/audio/voice/scribe/<line_id>.mp3` plus
`lines.json` (hashes, loudness, true peak). Every run writes `artifacts/voice/report/report.md` (loudness,
true peak, F0 before and after, energy above 10 kHz, wet/dry, tail) and a spectrogram PNG per line.
Exit codes: 0 ok, 1 check problems or bad arguments, 2 raw audio missing for `--reprocess`, 3 provider
unavailable, 4 a line failed its measurement checks.

## Troubleshooting

- **A phone keeps dropping, or a turn was played for me.** `logs/session.jsonl` records connections (with the websocket close code), turns and where the campaign plan came from (the AI or the prepared adventure, with the reasons); send it along with a bug report. It never holds tokens or keys.
- **A banner says the Dungeon Master is using fallback narration.** There is no usable DeepSeek key (or the
  service is down). The game stays fully playable with template narration and the built-in sample campaign.
  Put `DEEPSEEK_API_KEY` in `.env`, restart, and check `http://127.0.0.1:8000/healthz`: it reports only
  booleans (`ok`, `deepseek`, `fish`, `tts_enabled`, `version`), never a key.
- **No voice.** The voice is off unless `TTS_ENABLED=1` (or the host switches it on) and both `FISH_API_KEY` and
  `FISH_VOICE_ID` are set. If Fish fails, narration is shown as text and typed out; nothing blocks. Browsers
  block audio until you click once: use the "Click to enable sound" banner.
- **Phones cannot reach the game.** Use `--lan`, put every device on the same Wi-Fi, and check the firewall note above.
- **A campaign takes long to start.** The model can need up to two minutes to write the plan; the lobby shows progress.
- **A player vanished.** Reopen the page in the same browser: the stored token returns the same hero (within
  one server run, or after `--load`). After a restart without `--load` the page asks to join again.
- **The wrong player is host.** The host is the first seat; when that player is gone the role moves to the
  earliest-joined connected player (at once in the lobby, after 60 s away during play). `logs/session.jsonl`
  shows each `host_moved` and any `hello_refused` (a page from an earlier server run).
- **The `.env` loader prints a warning about a line.** python-dotenv skips lines it cannot parse (for example a
  line that starts with `/`); harmless.

## Licenses and attribution

This work includes material taken from the System Reference Document 5.1 ("SRD 5.1") by Wizards of the Coast LLC and available at https://dnd.wizards.com/resources/systems-reference-document. The SRD 5.1 is licensed under the Creative Commons Attribution 4.0 International License available at https://creativecommons.org/licenses/by/4.0/legalcode. SRD JSON provided by the 5e-bits/5e-database project (MIT).

Baldur's Gate 3 is a rules inspiration only (how combat flows, which actions exist). No Baldur's Gate 3 text,
characters, locations, spell descriptions or art is used. Names, places and descriptions in the sample campaign
and the BG3-style data files (`data/bg3/`) are original wording.

Assets in v1 form (everything under `aidm/web/static/` that is not a placeholder) are the project owner's own art
and assets carried over from the owner's v1 project, plus the Jersey 10 font (SIL Open Font License, text in
`aidm/web/static/fonts/Jersey10-OFL.txt`). The two music beds were re-encoded from the owner's v1 audio. Placeholder
art is generated on the fly as SVG and carries no license. Anything you drop in through "Adding or replacing art"
is yours to license; record its source in the manifest (`source` field) when you add it.
