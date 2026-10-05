# AI Dungeon Master (aidm)

A local-network D&D 5e (SRD 5.1 rules, BG3-style combat) game with an AI Dungeon Master.
This README is a stub: M9.6 completes it (run, `--lan`, firewall note, SRD attribution).

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
