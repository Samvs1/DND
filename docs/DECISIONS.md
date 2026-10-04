# Decisions

Format: one line per decision: `topic | choice | reason`.

M0.4 assets | copied v1 web/static/{img,audio,fonts} to aidm/web/static/, v1 assets_src/portraits_src to assets_src/portraits_src, Downloads/DnD UI to assets_src/dnd_ui (copy only, v1 untouched) | SPEC 3 reusable assets
M0.4 skipped >15 MB | v1 audio/music/combat.mp3 (55.7 MB), audio/music/ambient.mp3 (17.2 MB); DnD UI Audio/Music/combat.mp3 (55.7 MB), Audio/Music/exploration.mp3 (17.2 MB), Audio/Voice/Scribe ending voic effecte.wav (23.3 MB), Audio/Voice/Scribe opening voice effect.wav (18.1 MB) | over size limit; combat and ambient beds must be re-encoded smaller (<=5 MB, e.g. 96 kbps mono) by a later checkpoint from the originals in v1
M0.4 skipped archives | DnD UI *.zip and *.rar (3 zips in Asset Packs, Characters/main_pack_110_fantasy_rpg_inventory_icons.zip 8.4 MB, 1 rar) | redundant packed duplicates, bloat the repo; extracted icon PNGs are copied
M0.4 skipped BG3 audio | DnD UI Audio/Voice/Baldur's Gate 3 - Withers - Post Credit Scene.mp3 (copied then removed) | BG3 content is not allowed (CLAUDE.md hard rules)
M0.4 skipped caches | v1 had no hashed TTS mp3 cache under web/static (cache lives in saves/tts_cache, not copied); no .py, .env or config files copied | secrets and generated files stay out
M1.1 rng | rules take `rng: Rng` (Protocol with randint(a, b)); random.Random(seed) satisfies it; no global random anywhere in rules | SPEC 2.4 reproducible from a seed, easy scripted RNGs in tests
M1.1 dice models | DiceExpr/Roll/D20Roll/AdvState are frozen pydantic models in aidm/models/dice.py; parse/roll/combine logic in aidm/rules | models hold no logic; rolls embed in events
M1.1 dice grammar | "XdY[khN|klN]" terms and integer constants joined by +/-; subtracting dice rejected; "MOD" placeholders substituted by the caller; parse cached | covers every SRD damage string; keep-highest serves 4d6-drop-lowest (M2.2)
M1.1 negative totals | Roll.total is raw arithmetic and may be negative; the damage choke point (M1.4) clamps damage to >= 0 | one clamp point, no hidden adjustments in the roller
M1.1 crit | roll(..., crit=True) / double_dice doubles dice counts (and keep counts), never the modifier; recorded expression is the doubled one | SRD Critical Hits; audit shows what was rolled
M1.1 d20 | roll_d20 records both dice under adv/disadv, is_crit = natural >= crit_on (default 20, for Improved Critical), is_fumble = natural 1; callers decide what crits mean | one d20 roller for attacks, checks and saves
M1.1 naming | `combine_adv` and `ability_modifier` instead of bare `combine`/`modifier` | check_structure forbids duplicate public names across rules/ and dm/; bare names would collide
