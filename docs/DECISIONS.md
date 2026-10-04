# Decisions

Format: one line per decision: `topic | choice | reason`.

M0.4 assets | copied v1 web/static/{img,audio,fonts} to aidm/web/static/, v1 assets_src/portraits_src to assets_src/portraits_src, Downloads/DnD UI to assets_src/dnd_ui (copy only, v1 untouched) | SPEC 3 reusable assets
M0.4 skipped >15 MB | v1 audio/music/combat.mp3 (55.7 MB), audio/music/ambient.mp3 (17.2 MB); DnD UI Audio/Music/combat.mp3 (55.7 MB), Audio/Music/exploration.mp3 (17.2 MB), Audio/Voice/Scribe ending voic effecte.wav (23.3 MB), Audio/Voice/Scribe opening voice effect.wav (18.1 MB) | over size limit; combat and ambient beds must be re-encoded smaller (<=5 MB, e.g. 96 kbps mono) by a later checkpoint from the originals in v1
M0.4 skipped archives | DnD UI *.zip and *.rar (3 zips in Asset Packs, Characters/main_pack_110_fantasy_rpg_inventory_icons.zip 8.4 MB, 1 rar) | redundant packed duplicates, bloat the repo; extracted icon PNGs are copied
M0.4 skipped BG3 audio | DnD UI Audio/Voice/Baldur's Gate 3 - Withers - Post Credit Scene.mp3 (copied then removed) | BG3 content is not allowed (CLAUDE.md hard rules)
M0.4 skipped caches | v1 had no hashed TTS mp3 cache under web/static (cache lives in saves/tts_cache, not copied); no .py, .env or config files copied | secrets and generated files stay out
