NEXT: M3.1 Zones. Delegate to hard-engineer. Last gate: M2 FULL GATE PASS 8/8.

# PROGRESS

Source of truth: `SPEC.md`. Work order and agent routing: `docs/USAGE_PLAN.md`. Operating manual: `CLAUDE.md`.
Each checkpoint takes about 20 to 40 minutes, ends with a green gate, and gets its own commit (`WIP M<n>.<k>: <what>`).
The last checkpoint of each milestone runs the FULL gate (`.\scripts\gate.ps1`) and commits `M<n>: <title>`.
Type: **M** = mechanical (mechanical-engineer, sonnet). **H** = hard (hard-engineer, opus).

Update rule: tick `[x]`, append ` (commit <shorthash>)`, rewrite `NEXT:` (exact action, files in flight, last gate result).
Stashes and blockers: record them in the Notes section at the bottom.

---

## M0 Foundation (SPEC 0, 4, 5, 13 gates, 14)
- [x] M0.1 **M** Plan: CLAUDE.md, PROGRESS.md, docs/USAGE_PLAN.md, the two agents. Gate: the files exist and CLAUDE.md is <=150 lines.
- [x] M0.2 **M** Skeleton: `pyproject.toml` (deps + dev extras, ruff, pyright strict on rules/models, pytest config with a `live` skip unless RUN_LIVE=1, import-linter layer contracts), `.venv`, `aidm/{models,data,rules,dm,session,server,web}` packages, `tests/` tree with one smoke test, full `.gitignore` (.env, saves/, logs/, .venv/, artifacts/, __pycache__/), `.env.example` (names only), `docs/DECISIONS.md`, `docs/RULES_DECISIONS.md`. Gate: `pip install -e .[dev]` OK; `pytest -q`, `ruff check .`, `ruff format --check .`, `pyright`, `lint-imports` all green.
- [x] M0.3 **M** Gate scripts: `scripts/check_structure.py` (AST: 400 lines/file, 60 lines/function, no root .py, no star import, no re-export-only module, no duplicate public names across rules/ and dm/) with tests using fixture files; `scripts/check_secrets.py` (compares in memory, prints paths only) with a test; minimal `models/protocol.py` (Ping/Pong) plus `scripts/gen_protocol.py [--check]`; `scripts/gate.ps1` runs all 8 gates and prints the tails and PASS/FAIL. Gate: `.\scripts\gate.ps1` all PASS. (commit e7d904a)
- [x] M0.4 **M** v1 assets and lessons: copy v1 `web/static/{img,audio,fonts}`, `assets_src/portraits_src`, `Downloads\DnD UI` into `aidm/web/static/` (copy only); write `docs/V1_LESSONS.md` (<=80 lines) digesting the v1 files listed in SPEC 3. Gate: files present, check_secrets PASS, `git status` shows no audio or image over 5 MB (ask in Notes if so).
- [x] M0.5 **M** SRD vendoring: `scripts/fetch_srd.py` downloads the 5e-bits/5e-database 2014 JSON (spells, monsters, equipment, magic-items, races, subraces, classes, subclasses, levels, features, traits, conditions, skills, damage-types, proficiencies, backgrounds) into `data/srd/`, plus a SOURCE.md with the commit/date and the CC-BY note. Gate: script idempotent; files committed; pytest green.
- [x] M0.6 **M** Typed loaders: pydantic SRD entry models plus registries in `aidm/data` for spells, equipment, races/subraces, classes/levels, conditions and skills; `tests/unit/data/test_schema_*.py` checks that every entry validates. Gate: pytest data tests green, pyright green.
- [x] M0.7 **M** Monster loader: preserves breath-weapon DCs and recharge, multiattack, legendary actions and spellcasting; golden tests (adult red dragon breath DC/damage, young green dragon, mage spell list, ogre multiattack, 6 more). FULL gate. Commit `M0: Foundation`. (commit see git log, `M0: Foundation`)

## M1 Rules core (SPEC 2, 5, 7.1, 13)
- [x] M1.1 **H** Dice and abilities: an injected-RNG dice roller returning typed Roll results (expression, rolls, kept, total), ability modifiers, proficiency by level, advantage/disadvantage cancellation; property tests (seeded determinism, bounds). Gate: `pytest -q tests/unit/rules tests/property`. (commit c5d141b)
- [x] M1.2 **H** Event sourcing: `models` GameState (minimal) plus an Event discriminated union, `session/reducer.apply`, hypothesis test replay(events) == snapshot. Gate: pytest plus lint-imports.
- [x] M1.3 **H** Checks and defences: skills (18), checks, saves, passives, DC tier map (5-30); AC (armor, shield, Unarmored Defense for Barbarian/Monk data, Mage Armor); HP by level; temp HP. Gate: pytest rules. (commit 305ab6c)
- [x] M1.4 **H** Damage choke point: typed damage only, resist/immune/vuln, temp HP absorbs first, HP clamped to [0, max], healing, death saves, stabilise, instant death; properties (never negative, within bounds). Gate: pytest rules plus property.
- [x] M1.5 **H** Conditions: `data/bg3/conditions.json` (all 15 SRD conditions as data: attack/save/speed/action effects, duration, save-ends) plus a generic interpreter; concentration (damage check, single concentration); `test_v1_conditions_persist_after_combat`. Gate: pytest rules. (commit 38a6def)
- [x] M1.6 **H** Rests and coverage: short rest (limit 2 per long rest, hit dice), long rest (camp supplies per living member, tunable), slot model stub; bring `rules/` coverage to >=90%. FULL gate plus coverage tail. Commit `M1: Rules core`. (commit see git log, `M1: Rules core`)

## M2 Characters (SPEC 7.5, 8)
- [x] M2.1 **M** Class, race and background data overlay: `data/bg3/classes/*.json` (6 classes, levels 1-5, subclass level, proficiencies, equipment packages), races and subraces from SRD, `data/bg3/backgrounds.json` (original wording); schema tests. Gate: pytest data.
- [x] M2.2 **H** Creation pipeline: point buy 27, standard array, 4d6-drop-lowest (roll shown), racial bonuses, skill/tool picks, equipment package choice, backstory <=400 chars; validation errors are typed. Gate: pytest rules (parametrised over 6 classes x all races). (commit f4e2363)
- [x] M2.3 **H** The ONE spell-slot model (full, pact magic), known vs prepared, cantrip picks, spell DC and attack bonus. Gate: pytest rules.
- [x] M2.4 **H** Feature hooks: data entries plus a generic hook interpreter (damage_rider, bonus_action, resource, fighting_style, expertise, resistance, advantage_on, extra_attack, sneak_attack, toggle). Gate: pytest rules. (commit b4b76a0)
- [x] M2.5 **H** Level-up 1->5: XP table, HP gain, subclass at the right level, ASI, BG3-style spell learning, wizard scroll copy (rules only); derived sheet model (everything SPEC 8 lists). Gate: pytest rules.
- [x] M2.6 **M** Per-class goldens: AC, attack bonus, save DC, slots and HP at levels 1-5 for all 6 classes; JSON export/import round trip. FULL gate. Commit `M2: Characters`. (commit M2: Characters)

## M3 Combat (SPEC 6.1, 7.2-7.4)
- [ ] M3.1 **H** Zones: model (3-6 zones, adjacency, distance label, cover, high ground, surfaces slot), seeded generation from terrain tags, movement cost per hop, range bands, high-ground adv/disadv. Gate: pytest rules.
- [ ] M3.2 **H** Encounter lifecycle: start (surprise), 1d4+DEX initiative, turn order, action/bonus/movement/reaction state, end turn, victory/flee/party wipe, CR budget builder. Gate: pytest rules.
- [ ] M3.3 **H** Commands: attack (melee/ranged/finesse/crit double dice/nat 1), `rules.hit_chance` preview, dash, disengage, bonus-action shove/jump, hide, help, throw, use_item (potion bonus action, give to adjacent ally); `test_v1_potion_full_hp_refused_not_consumed`, `test_v1_invalid_input_never_consumes_turn`. Gate: pytest rules.
- [ ] M3.4 **H** Spell effect DSL: schema plus ONE interpreter (attack_roll, save half/none/condition, typed damage with upcast, heal, apply/remove_condition, temp_hp, ac_buff, surface, multi_target), slot validation, upcasting, concentration hookup; 10 spells with goldens. Gate: pytest rules.
- [ ] M3.5 **M** Spell content batch 1: all cantrips and level 1 for the 6 classes' lists as DSL JSON, a golden test each. Gate: pytest spells.
- [ ] M3.6 **M** Spell content batch 2: levels 2-3 until >=50 shipped; unsupported spells listed in RULES_DECISIONS and hidden from pickers. Gate: pytest spells plus a count assertion >=50.
- [ ] M3.7 **H** Surfaces lite: `data/bg3/surfaces.json` (fire, oil/grease, water, ice, poison cloud), interactions (fire+oil, water+lightning, water+cold, fire clears ice/water), turn-start and enter triggers, attached to zones. Gate: pytest rules.
- [ ] M3.8 **H** Monster actions: execute multiattack, breath weapon with recharge, spell kits and legendary actions through the same attack/DSL paths. Gate: pytest rules.
- [ ] M3.9 **M** Monster catalogue: >=60 encounter-ready SRD monsters CR<=8 (including a breath dragon and a caster), with goldens for 10. Gate: pytest data plus a count assertion.
- [ ] M3.10 **H** Monster AI: value-based targeting (threat, kill chance, vulnerability, concentration breaking), zone/range awareness, spell and multiattack choice, retreat when broken; seeded determinism test. Gate: pytest rules.
- [ ] M3.11 **H** Headless combat sim: `tests/sim/test_combat_seeds.py` runs 50 seeds (party vs encounter, both sides AI) asserting invariants (HP bounds, slot conservation, termination, replay == snapshot). FULL gate. Commit `M3: Combat`.

## M4 AI layer (SPEC 4 DeepSeek, 6.1-6.8)
- [ ] M4.1 **H** `dm/llm_client.py` (openai SDK -> DeepSeek, FAST/QUALITY roles, model discovery with fallback, schema validation, bounded retries with error feedback, max_tokens >=4000 for structured calls, typed fallbacks, `logs/llm.jsonl` without keys or raw player text) plus `tests/ai/fake_llm.py` (scripted tool calls, streaming, malformed JSON, truncation, timeout, hallucination). Gate: pytest tests/ai.
- [ ] M4.2 **H** Tools: pydantic schemas for every SPEC 6.3 tool plus executors -> rules -> events; tier maps (dc, severity by party level, xp, item value cap by region tier); validation errors returned as tool errors; point-of-no-return event. Gate: pytest tests/ai.
- [ ] M4.3 **H** Entity registry plus `dm/context.py` (the ONE builder): 7 sections, deterministic order, token budget with truncation priority, closed-world manifest statement, secrets only in npc_voice; tests that secrets never reach narration context. Gate: pytest tests/ai.
- [ ] M4.4 **H** Adjudicator: tool loop (<=5 tools/round, <=3 rounds), deterministic pre-checks (rest, shop, travel to neighbour, inventory, look around), creative_action in combat. Gate: pytest tests/ai.
- [ ] M4.5 **H** Narrator: streamed QUALITY call, sentence chunker, tone from state, template narration from events (no key or outage); `test_v1_failed_checks_always_narrate`. Gate: pytest tests/ai.
- [ ] M4.6 **H** `dm/guard.py`: unlisted names (word boundary, lore allow-list), dead creatures acting, undestroyed items described destroyed, wrong class/name, unlisted features; one retry with scrubbed context, then the safe fallback; v1 tests (hidden-door synonyms, "unbroken", dead boss, crowd plurals, absent NPCs in an empty scene). Gate: pytest tests/ai.
- [ ] M4.7 **H** Memory and NPC voice: scene summariser (FAST, structured), fact ledger with entity-tag retrieval, summarise every 12 turns or at scene end; npc_voice with private data, guarded. Gate: pytest tests/ai.
- [ ] M4.8 **H** Injection suite (>=20 FakeLLM adversary cases), end-to-end fallback test (no key = fully playable exploration plus combat), `tests/live` scaffolding (skipped without RUN_LIVE). FULL gate. Commit `M4: AI layer`.

## M5 Campaign (SPEC 9)
- [ ] M5.1 **M** Campaign plan schema plus a built-in sample campaign (3 acts, original setting) used as the fallback. Gate: pytest.
- [ ] M5.2 **M** Region graph builder (arrival, 2-3 spokes, gateway), connectivity and no-soft-lock validation, gateway lock until spokes are visited, defeat path always present; `test_v1_unreachable_boss_never_softlocks`. Gate: pytest.
- [ ] M5.3 **H** `dm/campaign_gen.py`: one structured QUALITY call, validation, retry with errors, fallback to the sample; theme or "surprise me". Gate: pytest tests/ai.
- [ ] M5.4 **H** Progression: lazy node descriptions generated once and stored, travel, world-pulled encounters (CR budget), surprise/escape/parley options, region resolution by defeat or alliance. Gate: pytest.
- [ ] M5.5 **H** Social: attitude = capped and floored social contribution plus uncapped deeds, ally bar crossed only by deeds, reveal_secret conditions; `test_v1_social_score_floor`, `test_v1_hostile_act_confirm_before_combat`. Gate: pytest.
- [ ] M5.6 **M** Items to >=80 catalogue entries (camp supplies, keys, healing tiers), shops (prices from data, buy/sell), loot tables, kill and milestone XP, quests. Gate: pytest plus a count assertion.
- [ ] M5.7 **M** Epilogue built from the fact ledger (FakeLLM test that it only cites ledger facts), `test_v1_dead_boss_never_described_alive` end-to-end. FULL gate. Commit `M5: Campaign`.

## M6 Session and server (SPEC 4, 10)
- [ ] M6.1 **M** Protocol: full `ClientMsg`/`ServerMsg` discriminated unions; gen_protocol writes `aidm/web/protocol.json` and `docs/PROTOCOL.md`; a staleness test. Gate: pytest plus `gen_protocol.py --check`.
- [ ] M6.2 **H** Table actor: one asyncio task owns state; FIFO queue with one pending per player; ready votes (30s, host force); combat turn ownership, suggestions, turn timer with safe default autoplay; mechanical events broadcast before narration. Gate: pytest tests/session.
- [ ] M6.3 **M** Persistence: atomic snapshot plus `events.jsonl`, load, replay equals snapshot on disk; autosave after every resolved action. Gate: pytest tests/session.
- [ ] M6.4 **M** Server: FastAPI app, WS gateway (token join, snapshot plus seq catch-up on reconnect), lobby, static hosting, `/healthz` (booleans only), `--lan` with LAN URL and an inline SVG QR, `AIDM_FAKE_LLM`, and the `python -m aidm` entrypoint (`aidm/__main__.py`, binds 127.0.0.1:8000). Gate: pytest tests/session (TestClient WS).
- [ ] M6.5 **M** Host controls (pause/resume, kick, difficulty multipliers, TTS toggle, save/load/new, end, token totals) with tests. FULL gate. Commit `M6: Session and server`.

## M7 Frontend (SPEC 12)
- [ ] M7.1 **M** Shell: theme CSS variables with v1 art, `strings.js`, ws client plus a handler registry, a test that every ServerMsg type has a JS handler, lobby/join plus QR. Gate: pytest (handler coverage) plus a manual boot.
- [ ] A1 **M** Asset manifest (docs/ADDENDUM_ASSETS.md A.2, A.3, A.5): `aidm/web/static/assets/manifest.json` with keys derived from the data registries, `scripts/build_manifest.py [--check]`, the ONE server `asset_url(key)` and the ONE frontend `assetUrl(key)`, pure deterministic SVG placeholders in `aidm/server/placeholders.py` served at `/assets/placeholder/<kind>/<slug>.svg` (never raise; unknown key = generic), missing audio = silence; tests: every data key resolves, no hardcoded `/static/img` outside the helper, dropping a file flips it to real; add `build_manifest.py --check` to gate.ps1. Gate: FULL gate.
- [ ] M7.2 **M** Character wizard (all SPEC 8 steps, validation via the server). Gate: pytest plus a Playwright smoke if available, otherwise a manual boot note.
- [ ] M7.3 **M** Table view: streaming story feed, scene header, party panel, queue tracker, dice tray (adv/disadv), action input, ready vote, point-of-no-return dialog, fallback banner. Gate: as above.
- [ ] M7.4 **M** Combat view: zone cards with token chips, initiative strip, hotbar with hit-chance tooltips, action/bonus/move pips. Gate: as above.
- [ ] M7.5 **M** Sheet drawer, inventory (equip/unequip), spellbook with slot trackers. Gate: as above.
- [ ] M7.6 **M** Journal, map (fog), shop, host panel, settings; responsive check at 390px and 1920px; all art goes through `assetUrl` (Addendum A gates green). FULL gate. Commit `M7: Frontend`.

## M8 Audio and polish (SPEC 4 Fish, 11)
- [ ] M8.1 **M** `synthesize(text, tone) -> Path | None` (check the current Fish SDK/docs first), cache by hash, lazy guarded import, zero cost when disabled, `/tts/<hash>.mp3`. Gate: pytest (mocked).
- [ ] M8.2 **M** Sentence pipeline (synthesize N+1 while N plays), `narration_chunk`/`narration_done`, typewriter fallback, per-client mute/volume, autoplay hint. Gate: pytest plus a manual boot.
- [ ] M8.3 **M** Music crossfade by game state (the v1 ambient/combat beds were skipped for size in M0.4: re-encode smaller copies from v1 if ffmpeg is available, else log it and rely on silence fallback), `/screen` spectator view (default audio device). Gate: pytest.
- [ ] A2 **M** Style bible and TODO (Addendum A.4, A.6): view 3-4 v1 portraits once and write `docs/STYLE_BIBLE.md`; `scripts/gen_assets_todo.py [--check]` writes root `ASSETS_TODO.md` (key, target path, size, transparency, prompt = style prefix + data details, no BG3/IP references); add its `--check` to gate.ps1; reserve `IMAGE_PROVIDER` and `IMAGE_API_KEY` names in `.env.example`. Gate: FULL gate.
- [ ] A3 **M** Placeholder-only play proof (Addendum A.5, A.7): install Playwright chromium; a Playwright test that runs the app from a temp copy with the real img folder hidden and proves join, create, act and combat render on placeholders; screenshots in `artifacts/ui/`; README section "Adding or replacing art". Gate: that test plus the FULL gate.
- [ ] M8.4 **M** Accessibility pass (keyboard, focus-visible, text size, reduced motion, contrast); Addendum A gates green. FULL gate. Commit `M8: Audio and polish`.

## M9 Hardening (SPEC 13, 15)
- [ ] M9.1 **M** `scripts/simulate_party.py --seeds N [--live-ai]`: 3 WS bots (fighter, explorer, chaotic) plus the SPEC 13 assertions, printing `SIMULATION OK ...`. Gate: script runs (failures are allowed and logged to Notes for M9.2).
- [ ] M9.2 **H** Fix simulation defects until 20 seeds pass with the fake AI. Gate: `SIMULATION OK seeds=20` plus the full gate.
- [ ] M9.3 **M** Playwright suite (`AIDM_FAKE_LLM=1`, two contexts: join, create, act, narration, combat hotbar, reconnect), screenshots in `artifacts/ui/`. Gate: pytest tests/ui.
- [ ] M9.4 **H** Live: `RUN_LIVE=1 pytest tests/live` (DeepSeek tool round trip, campaign gen, guard on real output, injections, Fish mp3 >5 KB) plus `simulate_party.py --seeds 2 --live-ai`. Gate: live tests green.
- [ ] M9.5 **H** Adversarial QA by a fresh subagent (read-only report) and fix the defects. Gate: full gate plus the sim.
- [ ] M9.6 **M** README (run, `--lan`, firewall note, SRD attribution), `docs/ARCHITECTURE.md`, a server boot plus `/healthz`, the VERIFICATION REPORT, and an honest list of Tier-2 items not built. FULL gate. Commit `M9: Hardening`.

## M10 AI assets (docs/ADDENDUM_ASSET_GEN.md = Addendum B; starts only after M9; part of THIS goal)
Budget: hard cap 8 EUR (`--cap 8`). Only P1 placeholders. Never touch `status: real` or `source: v1`, never overwrite an existing file. The IMAGE_API_KEY value is never printed, logged or committed.
If the API rejects the key or needs organisation verification: stop M10 generation only, write `BLOCKED: <exact reason>` in Notes, finish everything else and say so in the final report.
- [ ] M10.1 **H** Generator core: an image provider interface, an OpenAI provider (lists models and picks the current GPT Image model, never a hardcoded retired id, no other network), `FakeImageProvider`, `data/asset_costs.json`, the budget guard with the `logs/asset_spend.json` ledger (written before each call at worst case, updated after with the actual cost, refuses calls past the cap, retries count), `scripts/gen_assets.py` (`--dry-run` default, `--yes`, `--cap`, `--tier`), and P1/P2 derivation into `docs/ASSET_PRIORITY.md`; B.6 tests (dry-run spends nothing, cap refusal, ledger before and after, retries count, key never in logs or ledger). Gate: FULL gate.
- [ ] M10.2 **M** Pipeline tools: Pillow auto-checks (size, alpha corners, blankness, uniform borders, file size), a 4x4 sheet slicer modelled on v1 `assets_src/slice.py`, `scripts/contact_sheet.py` (<=12 labelled candidates plus 2 v1 reference thumbnails), atomic install with a manifest update (`source: generated:<model>`, prompt, cost, license, reviewed), `scripts/revert_asset.py <key>`, ASSETS_TODO regeneration; B.6 tests (slicer, contact sheet, install/revert, real/v1 never overwritten). Gate: FULL gate.
- [ ] M10.3 **M** Dry run: `python scripts/gen_assets.py --dry-run` shows the entries, API calls, cost per call and a total under the cap; commit `docs/ASSET_PRIORITY.md`. Gate: dry-run output plus the FULL gate.
- [ ] M10.4 **H** Live smoke: `RUN_LIVE_IMAGES=1` opt-in test generates exactly ONE small image; record the real cost and the model id queried from the API. Gate: live smoke passes, ledger shown, check_secrets PASS.
- [ ] M10.5 **ORCH** P1 generation: `python scripts/gen_assets.py --yes --cap 8` in batches, with portraits and banners passing 2-3 real v1 references through the edit endpoint and icons generated as 4x4 sheets. Gate: ledger total <= cap, check_secrets PASS.
- [ ] M10.6 **ORCH** Review loop: the main session OPENS every contact sheet and writes `artifacts/assets/review_<n>.json` (5 scores; accept only if all >= 4), with up to 3 attempts per key; install the accepted ones. Gate: every accepted asset scores >= 4 on style match; the FULL gate passes.
- [ ] M10.7 **ORCH** Final review: `artifacts/assets/FINAL_REVIEW.png` (opened), `ASSETS_REPORT.md` (spend vs cap, accepted, rejected, kept as placeholder), a Playwright UI run with wizard, combat and sheet screenshots viewed and crops fixed, a revert_asset demo (manifest status before and after), README art section updated. FULL gate. Commit `M10: AI assets`.

---

## Goal acceptance (from the owner's /goal; the final report must prove each with raw output)
1. Commits `M0: ...` to `M9: ...` exist and every box above is checked.
2. `python -m pytest -q` exits 0 with >=300 tests, rules/ coverage >=90%, and the named v1 regression tests.
3. ruff check, ruff format --check, pyright, lint-imports, check_structure, check_secrets and gen_protocol --check all exit 0.
4. `RUN_LIVE=1 python -m pytest tests/live -q` passes (DeepSeek tool round trip, campaign gen, injections; Fish mp3 >5 KB with size shown).
5. `python scripts/simulate_party.py --seeds 5` and `--seeds 1 --live-ai` both print SIMULATION OK.
6. `python -m pytest tests/ui -q` passes (Playwright, two contexts) and screenshots exist in artifacts/ui/.
7. `python -m aidm` boots on 127.0.0.1:8000 and /healthz returns ok, deepseek and fish all true, with no key material.
8. A fresh adversarial subagent attacks the game (invalid input, 20+ injections, disconnects, hallucination probes), its defects are fixed, and everything re-runs green.
9. README.md, docs/ARCHITECTURE.md and docs/RULES_DECISIONS.md exist.
11. Addendum A (docs/ADDENDUM_ASSETS.md, binding): build_manifest and gen_assets_todo `--check` pass; ASSETS_TODO.md, docs/STYLE_BIBLE.md and the README art section exist.
12. M10 (owner addendum): every M10 box is checked before the final report, and the report includes the evidence from items 2-7 of docs/next/GOAL_ASSETS.txt: the dry-run output, the live smoke cost and model id, the spend ledger under the 8 EUR cap, the review verdict table, FINAL_REVIEW.png opened, and UI screenshots with the new art (or BLOCKED with its exact reason).
10. The final message is a VERIFICATION REPORT plus the Tier-2 items not built.

## Notes (stashes, blockers, decisions pending)
- M2.4 resolved the M2.2 deferred hooks (hill dwarf HP, racial resistances, life domain heavy armor, rogue expertise, domain/patron spells). Unsupported feature mechanics are listed in RULES_DECISIONS M2.4 for M3 (reactions, DSL effects).
