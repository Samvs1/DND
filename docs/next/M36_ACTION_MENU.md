# M36: the engine builds the menu, the model picks from it (Approach A)

Owner decision 2026-10-25 ("Go for A"), after round 6 (docs/playtests/M34_round6.md, Y9-Y15) and the
code-health assessment. Owner: "It doesn't make sense to keep patching these bugs every iteration with more
lines of code. Even asking for confirmation is not sufficient. We need to tackle the root cause."

## Root cause
Two systems read every typed line. A keyword router (aidm/dm/intent_router.py, intent_match.py,
intent_conditions.py, ~20 `*_intent.py` modules, compound_lines/strike_words/spell_names; ~3,300 Python lines
plus data/bg3/intent_phrases.json, 2,577 lines) owns every real action. The LLM adjudicator is offered only GM
tools (in a fight: request_check, request_save, creative_effect, use_item, no_mechanics). A router miss lands on
a model that cannot pick the right action, so it becomes a creative check. Every fix added phrase rows; typed
findings stayed at 9, 8, 7 per round.

## The design
1. On every typed line the ENGINE builds the acting hero's full menu of legal actions right now: everything the
   buttons offer (attacks per weapon, spells with targets, features, items, fight actions) plus the scene (people
   to talk to, give/hand/pay/take, search, look, exits and travel destinations, rest, shop, equip, offer answers,
   the quest card, helping a downed hero up, taking from a fallen hero's pack). Each entry has a stable id built
   from data keys (`attack:longsword`, `cast:fire-bolt`, `give:block-of-incense`, `travel`), a short label with
   descriptors from data ("Fire Bolt (cantrip, fire, 120 ft)"), its allowed targets and quantity bound.
2. The model gets the line, the menu and a small scene context (FAST role, one forced tool `choose_actions`) and
   may only answer with menu ids: up to 4 ordered steps `{do, to, qty}`, `other` (a stunt or something off the
   menu), or both (M36.5: `other: {text, first}`, the stunt before or after the steps). The schema is built per call with enums; a validator rejects any target or quantity that does not fit
   its entry and the client's existing retry-with-feedback loop repairs it.
3. The engine turns steps into acts (pure rules) and runs them through the SAME code paths the buttons and jobs
   use. `other` goes to the existing creative/social adjudicator, so nothing physically possible is refused.
4. Engine meaning, not language: a melee attack at a foe out of reach = approach then strike when movement allows
   (else a plain line, never a silent swap to ranged); a stowed weapon is drawn first; travel to where you already
   are = "You are already at X."; counted give/take/buy; compound lines are the ordered steps, each on the state
   the previous one left, stopping when a fight starts or the turn ends.
5. No confirmation prompt (owner). The action log shows what was chosen.
6. Fail soft: an exact match of a whole line to a menu label or a known button/chip sentence plays with no model
   call (also the fallback when the call fails); otherwise the in-fiction fallback notice, turn not consumed.
   Off-turn lines in a fight answer "not your turn" with no call.
7. Narration is unchanged in M36 (event beats are a separate later step, not yet approved).

## Layout (layering models, data <- rules <- dm <- session <- server)
- `aidm/models/action_menu.py`: MenuScope, ActionKind, MenuTarget, MenuEntry, ActionMenu, MenuStep, MenuChoice.
- `aidm/rules/acts.py` (+ `acts_fight.py`): the existing intent dataclasses MOVED (not copied) from dm.
- `aidm/rules/action_menu.py` `build_menu(state, actor_id, regs)` with `menu_fight.py`, `menu_scene.py`,
  `menu_items.py`, `menu_offer.py`, `menu_labels.py`; built on sheet.py, attack_profiles, gear_menu, world_graph,
  zones.
- `aidm/rules/menu_steps.py` `to_acts(state, menu, choice)`; `aidm/rules/approach.py` `approach_moves`.
- `aidm/dm/choice_tool.py` `choice_tool(menu) -> ToolDef`; `aidm/dm/chooser.py` + `chooser_prompt.py`; the context
  is a new `ContextPurpose.CHOOSE` in the one builder `dm/context.py`.
- Session: `intent_turn.resolve_line` and `fight_text.combat_text` call the chooser then `to_acts`, then the
  existing runners. `TableConfig.interpreter: "router" | "menu"` until the switch.
- Client: one `MenuAct` message for the 4 buttons that send text today (map travel, shop visit, gear uses,
  put out the light).

## The eval (how this layer is measured from now on)
- Source: all rounds 1-6 are committed fixtures (tests/fixtures/saves/{m29-*,m31-r4-*,m32-r5-*,m35-r6-*}); typed
  lines are `action_declared` events (~1,800); `persistence.replay_log` rebuilds the state before each one.
- Corpus `tests/fixtures/interpret/corpus.jsonl`: ~300 labelled lines (every line cited in a playtest finding plus
  a sample stratified by scope), `{id, run, seq, actor_id, text, scope, expect:{steps, other}, alt, source, note}`.
- `scripts/eval_interpret.py`: offline (FakeLLM) the menu must cover every expected entry and target (100%);
  `--live` scores exact and entry match, false-action and false-other rates, latency and tokens. The old router
  is scored on the same corpus as the baseline.
- Live pass bar: >= 92% exact overall, 100% on finding-cited lines, false action <= 2%, false other <= 5%,
  p90 <= 4 s, and better than the router baseline.
- Live spend: owner OK 2026-10-25 for up to 2,500 DeepSeek calls in M36 (est. $1-3); stop at the cap.

## Decisions taken under standing owner rules
- Taking from a fallen hero's pack (Y14): downed or dead, out of a fight (never-refuse rule: physically possible).
- The router's own unit tests are removed together with the router; every sentence they test moves into the
  corpus and into new menu/executor tests (not a weakened gate: the code they test is gone). Owner informed.
- `creative_weapon` keeps only the creative_effect tool's `item` argument, no text rules.
- DeepSeek strict function calling: tried in the eval if available; the validator plus retry stays either way.
- SPEC 6.1/6.2 are rewritten for the menu chooser ("no separate classifier" no longer holds).

## Kept after the switch
gear_words (creative_gear, tool_exec_checks), wording, impossible_text, cast_text, item_text, refusal_text,
SHOP_ROLES/is_shop (moved to rules), look_around_text (to dm/scene_text.py), come_back_words (to
data/bg3/plan_words.json with a loader).

## Deleted at the end
intent_router, intent_match, intent_conditions, precheck, all `*_intent.py`, compound_lines, strike_words,
spell_names, fight_names, far_travel, sentence, aidm/data/intent_phrases.py, data/bg3/intent_phrases.json.

## Checkpoints
See PROGRESS.md "M36". Order: docs; moves (no behaviour change); fight menu + approach; scene menus; steps to acts
+ Y14 rule; tool + chooser; session wiring behind the flag; eval scripts; labelling + menu gaps (offline 100%);
LIVE eval (pass bar); flip + test rewrite; client MenuAct + manual; delete the router; FULL gate, `M36`.
