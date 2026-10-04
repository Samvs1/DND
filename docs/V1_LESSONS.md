# V1 lessons (digest; read this, not v1)

Source: v1 CLAUDE.md, grounding.py, llm.py, web/tts.py, BACKLOG.md, playtester and QA memory. No key values here.

## Fish adapter reference (v1 web/tts.py)
- Package `fish-audio-sdk`, lazy guarded import inside the synth function (module imports fine without it):
  `from fish_audio_sdk import Session, TTSRequest, Prosody`; on ImportError log once and return None.
- Call shape: `session = Session(api_key)`; `req = TTSRequest(text=text, reference_id=voice_id or None,
  format="mp3", prosody=Prosody(speed=s), temperature=t)`; `for chunk in session.tts(req, backend=model): buf.extend(chunk)`.
  The SDK streams mp3 byte chunks; join them; empty result means failure (None).
- `backend=` carries the model id (env FISH_MODEL, default `s1`). `reference_id` is the cloned voice id (FISH_VOICE_ID).
- Per-tone params (speed -> Prosody, temperature -> TTSRequest): combat 1.12 / 0.85, social 0.95 / 0.55,
  exploration 1.00 / 0.70; unknown or empty tone = 1.00 / 0.70.
- Cache key: sha1 of `model|voice_id|tone|text` (utf-8), file `<hex>.mp3` in the cache dir (default `saves/tts_cache`).
  Cache hit = no API call. Write atomically (temp file with pid suffix, then replace).
- Contract: `synthesize(text, tone) -> Path | None`, never raises; returns None if text blank, not active, SDK missing or error.
  `is_active` = key present AND narration enabled AND voice selected; when off, the server never calls (zero cost).
- Runtime-mutable settings (enabled, voice, model) plus a name -> reference_id voice registry; `set_voice` accepts a name
  or a raw id. Env vars: FISH_API_KEY, TTS_ENABLED, FISH_VOICE_ID, FISH_VOICE_NAME, FISH_MODEL, TTS_CACHE_DIR.
- Run synthesis on a worker thread so the game loop is never blocked. Narration prose only (not system text).

## DeepSeek usage facts (v1 llm.py and call sites)
- OpenAI-compatible: `openai.OpenAI(api_key=..., base_url="https://api.deepseek.com")`; fresh client per call is fine.
- Model ids used: `deepseek-v4-flash` (FAST: routing, extraction, classification) and `deepseek-v4-pro`
  (QUALITY: judge, social, narrators, NPC and world design). Override per role by env var; keep ids in ONE module.
- Every structured call: tools plus forced `tool_choice={"type":"function","function":{"name":...}}` and
  `extra_body={"thinking":{"type":"disabled"}}`. Thinking mode is disabled everywhere in v1.
- max_tokens used: 64 to 150 for slot extraction, 300 to 512 for narration, 1024 for the judge. Under-sized limits
  truncated JSON ("Unterminated string", ~2.4K to 5.4K chars) on world bible and graph theming; v2 floor is 4000
  for structured calls. Truncated or malformed tool JSON must be retried with error feedback, never shown raw.
- Flash ignores a lone positive example that contradicts a rule in the same prompt (5/5 runs); give several
  consistent examples or do the mapping in code. Single-shot classifiers drift on short casual phrasing.

## Narrator hallucination classes (guard test seeds)
- Invented interactive features: "a section of granite shifts, revealing a hidden seam" (also pressure plates, levers).
  Synonym vocabulary defeats keyword bans; the rule must be principle-level.
- Invented or imported people: "Sister Kelene and her grizzled sergeant" (named only in the opening crawl or history).
- Crowd pluralising: "a throng of onlookers murmurs" when one NPC is present.
- Erasing present NPCs: "The vast hall holds only you" with four NPCs listed.
- Destroyed-item claims: "wet glass shards scatter" when the potion was retained and inventory shows it.
- Wrong or swapped names: "the Warden in Stone doesn't even slow" when Aria resisted; a Fighter called "the young rogue".
- Dead things alive: a defeated gateway boss described as present in their node; empty scene still narrating prior NPCs.
- Outcome contradiction: "boots skids, she drops to one knee" right after prone was cleared; "staggers but does not fall" on a kill.
- Name-list preamble leaking before prose: "Sergeant Aria, Brother-Captain Serev ..." then the narration.
- Guard false positives to test against: "unbroken" and "not broken" must not trip a destroyed-item check.

## Rules and combat bug classes
- Library data dropped: breath-weapon DCs missing, spell damage ignoring slot level, heal off by one. Vendor SRD, golden tests.
- Conditions wiped at combat end (`end_encounter` set conditions to empty), so timed conditions were inert in exploration.
- Concentration cleanup depended on a hand-kept map of spell to condition; new concentration spells silently left conditions behind.
- Unprompted attack on a friendly NPC became an instant 4v1 with no confirm step.
- Victory declared mid-combat step then post-combat housekeeping narrated aftermath after the victory screen.
- Short phrasings route wrongly: "I get back up" went to ambient, so prone was never cleared; a greeting classified ambient.
- AoE spells hit the whole pool; needed a data-driven max_targets. Group phrasing ("the goblins") failed target extraction.
- Failed social checks drove relationship unboundedly negative; talk must cap at friendly, only deeds cross the ally bar.
- Gateway boss could be bypassed or soft-lock the ally path unless defeat is always available and cross-region edges gate on resolve.

## Session and UX bug classes
- Silent turn drops: JSON parse error, empty return, or exception swallowed with no narration; raw "API error: Unterminated string" shown to players.
- Gift to a vague recipient or insufficient gold fell through silently; gift resolved to the wrong NPC.
- Judge possible=false in combat consumed the turn without any message; invalid input burned the turn.
- Social partner continuity: must hold across turns but also yield when the player turns to a different NPC; "who is here?" must not cost a turn.
- Default responder and the NPC speaking in the narration diverged on the first social turn.
- Hand-maintained Python-to-JS event doc drifted; test scripts pytest could not collect; live-API tests broke the gate.
- Old saves must keep loading (`.get(default)` everywhere); cp1252 console crashed on Unicode in labels.

## Asset notes
- Portraits `img/portraits/`: `<class>_cropped.png` (full portrait) and `<Class>_p_icon.png` (class icon) for cleric, fighter, ranger,
  rogue, warlock, wizard; plus `scribe_cropped.png` and `shopkeeper_cropped.png`. Sources in `assets_src/portraits_src/`.
- Conditions (`icons/conditions/`): baned, blessed, blinded, charmed, deafened, exhaustion, frightened, grappled, illuminated,
  incapacitated, mage_armored, marked, paralyzed, petrified, poisoned, prone, restrained, shielded, stable, stunned, turned, unconscious.
- Spell school icons: acid, arcane, fire, force, frost, lightning, nature, necrotic, poison, radiant, thunder; plus scroll, wand.
- Stats: str, dex, constitution, int, wis, cha. Tabs: feed, map, player, scribe, shopkeeper, spellbook (each with `_active`).
- Dice: `ui/dice_overlay.png`. Backgrounds: `ui/bg_stone.png`, `bg_stone_scribe.png`, `bg_vellum.png`, `bg_lobby.jpg`; `overlay_grit.png`
  texture; logos `logo.png`, `logo_ribbon.png`; `ac_shield.png`; `corner.svg`.
- Fonts: `Jersey10.ttf` (OFL text `Jersey10-OFL.txt`).
- Audio (v1 book.js): two looping beds, `ambient.mp3` (exploration, calm) and `combat.mp3` (fight), crossfaded by combat state and
  ducked while the narrator speaks; one-shot stingers `defeat.mp3` (party wipe) and `victory.mp3` (campaign won).
  Ambient and combat exceed 15 MB and were NOT copied; they must be re-encoded from v1. `scribe_intro.mp3` is the Scribe intro.
