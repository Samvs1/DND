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
M1.2 event payloads | events carry resolved results (HpChanged has delta AND new_hp; DeathSaveRolled has the roll AND the new counters); reducer only assigns | replay is exact and trivial; delta kept for audit/narration
M1.2 seq | seq is not in event payloads; persisted log lines are LoggedEvent(seq, event) with seq == state.event_count before apply (0-based) | events stay pure values; GameState.event_count doubles as the next seq
M1.2 reducer mutation | apply mutates the actor-owned state IN PLACE and returns it; replay deep-copies the initial state once; inserted payloads (CreatureAdded) are deep-copied so logged events never alias state | combat sims apply thousands of events (about 1 us per HpChanged)
M1.2 reducer errors | unknown/duplicate creature ids raise ReducerError before any mutation | an invalid event is an engine bug, never silently ignored
M1.2 log-only events | DiceRolled changes nothing but event_count; no roll history kept in state | the event log is the history; snapshots stay small
M1.2 conditions | ConditionApplied replaces an instance with the same (name, source_id); ConditionRemoved removes all of a name, or only one source when source_id is given | stacking/exhaustion semantics refined in M1.5
M1.2 schema growth | state/event models use extra="forbid"; every later field must have a default | old snapshots and logs keep validating and replaying
M1.3 check logging | rules check functions return a typed CheckResult; the caller logs a log-only CheckResolved(creature_id, result, reason) event; consequences are separate events | one d20 audit record per test without coupling rules to logging
M1.3 skills | Skill StrEnum (values = SRD index) and SKILL_ABILITY constant in models/abilities.py, verified against data/srd/skills.json by a test | rules stay free of data loading; models cannot import data
M1.3 proficiency on Creature | proficiency_bonus (stored, default 2), save_proficiencies, skill_proficiencies, skill_expertise fields with defaults | monsters have SRD PB, PCs set it at creation/level-up via events
M1.3 AC formulas | AcFormula schema + loader in aidm/data/ac_formulas.py, entries in data/bg3/ac_formulas.json (indexed); features/spells reference them by index | models and data are independent layers, so the content schema lives in data; new formulas are data only
M1.4 damage choke point | rules/damage.resolve_damage(target, packets, crit, source_id) is the ONLY damage path; DamagePacket requires a DamageType; one call = one hit/source | SPEC 7.1 typed damage at one choke point
M1.4 damage events | resolve_damage emits a log-only DamageTaken (per-part rolled/taken, total, temp_absorbed, hp_lost, crit, source_id) then TempHpSet/HpChanged and 0-HP consequences | narrator/audit see the breakdown; M1.5 concentration reads DamageTaken.total (DC max(10, total/2))
M1.4 death state | new DeathSavesSet(successes, failures, stable) event for damage at 0 HP and revival; dying = hp 0 + alive + not stable + uses_death_saves; unconscious condition source "zero_hp" | explicit resolved values, no implicit reducer side effects
M1.4 death_saves flag | Creature.death_saves: None (PC-only) / True / False | per-creature override without a per-monster branch
M1.5 condition data | schema + loader aidm/data/condition_defs.py (pattern of ac_formulas), data/bg3/conditions.json; ONE interpreter rules/conditions.py, lifecycle rules/condition_timing.py, concentration rules/concentration.py | data over code: no per-condition branch
M1.5 ActiveCondition | duration (ROUNDS / UNTIL_LONG_REST / UNTIL_REMOVED), rounds_left, tick_on + tick_creature_id (None = bearer), save_ends; rounds_left alone implies ROUNDS so old logs validate; persists_after_combat is a plain property (not serialised) | one condition instance shape for spells, surfaces and features
M1.5 condition events | new ConditionTicked (countdown), ConditionRemoved.exact_source (remove exactly one (name, source) instance, None included), ConcentrationStarted/Ended | expiry must never remove another source's instance
M1.5 condition saves | effects roll saves through rules.conditions.save_with_conditions (auto-fail + condition adv); raw checks.saving_throw stays for death saves | one save path that honours conditions
M1.5 condition damage defences | resist_all_damage / damage_immunities from conditions are read inside damage_after_defenses | the choke point stays the only place defences apply
M1.5 condition immunity | Creature.condition_immunities (keys) blocks apply_condition | SRD monsters list condition immunities
