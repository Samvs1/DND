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

This is meant for a trusted home network only: there is no TLS and there are no accounts. A player is identified
by a random token kept in their browser. Do not expose the port to the internet.

## How to play

1. **Host**: run `python -m aidm --lan`, open the URL on your own device, enter your name. The first player in
   is the host.
2. **Join**: everyone else opens the LAN URL (or scans the QR) and enters a name. Reconnecting with the same
   browser brings you back to your hero.
3. **Wizard**: each player builds a hero: race, class (fighter, rogue, wizard, cleric, ranger, warlock),
   ability scores (point buy, standard array or rolled), skills, equipment, spells and a short backstory. You
   can export a hero to a JSON file and import it later.
4. **Start**: when every player has a hero the host starts the campaign. The AI writes a three-act campaign
   (or uses the built-in sample), and the table view opens.
5. **Exploration**: type what your hero does. Actions queue in order (one waiting action per player), the
   DM asks for checks when something is uncertain, and the dice tray shows every roll. Travel, rests and
   shopping ask the table for a quick vote.
6. **Combat**: a fight appears as zone cards with token chips and an initiative strip. On your turn the hotbar
   shows attacks with hit chances in the tooltips, spells with slot counts, class features, items, move, dash,
   disengage, hide and end turn. The number keys trigger the slots. Other players can send suggestions.
7. **Sheet**: the drawer on your party card shows stats, inventory (equip, unequip, drop, use), the spellbook,
   and the level-up dialog when you have earned a level (levels 1 to 5).
8. **`/screen`**: open `http://<host>:8000/screen` on a TV or a spare laptop. It shows the story, party and
   battlefield read-only and is the default audio device: while a screen is connected the players' own
   devices stay quiet unless a player turns sound on.

### Host controls

The host panel offers pause and resume, kick a player, monster hit-point and damage multipliers (0.25 to 3.0),
the voice on/off switch, save, load, new campaign, end campaign and token totals. Only the host can use them.

## Tests and gates

```powershell
powershell -ExecutionPolicy Bypass -File scripts\gate.ps1     # the full gate: 10 checks, prints PASS/FAIL each
pytest -q                                                   # the unit, property, ai, session, sim and ui tests
$env:RUN_LIVE = "1"; pytest -q tests\live                   # real DeepSeek and Fish (costs a little money)
python scripts\simulate_party.py --seeds 5                  # 3 bot players over real websockets, fake AI
python scripts\simulate_party.py --seeds 1 --live-ai        # the same with the real model
pytest -q tests\ui                                          # Playwright, two browser contexts, screenshots in artifacts\ui
```

The gate runs `pytest`, `ruff check`, `ruff format --check`, `pyright`, `lint-imports`, `check_structure.py`,
`check_secrets.py`, `gen_protocol.py --check`, `build_manifest.py --check` and `gen_assets_todo.py --check`.
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

Some art is AI generated (95 assets: portraits, banners, monster tokens, icons). Only the P1 tier was
generated; the rest are still placeholders. It was made by `scripts/gen_assets.py` (OpenAI image API, hard
cap 8 EUR, every call booked in `logs/asset_spend.json`), reviewed with `scripts/contact_sheet.py` and
installed with `scripts/install_assets.py`. `scripts/final_review.py` and `scripts/assets_report.py` write the
final review sheets and `ASSETS_REPORT.md`. To undo one asset: `python scripts/revert_asset.py <key>`.
License caveat: AI generated via OpenAI API, check provider terms before commercial use.

## Troubleshooting

- **A banner says the Dungeon Master is using fallback narration.** There is no usable DeepSeek key (or the
  service is down). The game stays fully playable with template narration and the built-in sample campaign.
  Put `DEEPSEEK_API_KEY` in `.env`, restart, and check `http://127.0.0.1:8000/healthz`: it reports only
  booleans (`ok`, `deepseek`, `fish`, `tts_enabled`, `version`), never a key.
- **No voice.** The voice is off unless `TTS_ENABLED=1` (or the host switches it on) and both `FISH_API_KEY` and
  `FISH_VOICE_ID` are set. If Fish fails, narration is shown as text and typed out; nothing blocks. Browsers
  block audio until you click once: use the "Click to enable sound" banner.
- **Phones cannot reach the game.** Use `--lan`, put every device on the same Wi-Fi, and check the firewall note above.
- **A campaign takes long to start.** The model can need up to two minutes to write the plan; the lobby shows progress.
- **A player vanished.** Reopen the page in the same browser: the stored token returns the same hero.
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
