# Ultrareview findings

Cloud ultrareview of branch `review` against `main`, finished 2026-10-24. There are 10 findings, all severity
normal, in the order the review returned them. The comment and reasoning text is copied word for word. Some
reasoning sections stop partway through their trace; that is how the review delivered them.

## 1. `aidm/dm/spell_names.py`, lines 68-85

**Status:** fixed in M33.1 (8853559)

- **File:** aidm/dm/spell_names.py
- **Lines:** 68-85
- **Severity:** normal

### Comment

A ready single-word cantrip name that is also an ordinary word, above all the new Light cantrip, now hijacks weapon attacks. `named_spell`/`names_spell` match it anywhere in the line, including inside weapon names like "light crossbow" or "light hammer". The attack and weapon_strike rows are now vetoed by `no_spell_named`, so the line falls through to fight_cast and casts Light on the hero instead of attacking.

### Reasoning

A bard, cleric, sorcerer or wizard with the new Light cantrip ready types "I attack the goblin with my light crossbow" in a fight. `names_spell` sees "light" through `said_name(words, ready_spells(actor))`. The `attack` row (precedence 3100, now `when: no_spell_named`) and the `weapon_strike` row are skipped. The `fight_cast` row (3320) returns `CastCommand(spell_id='light')` with self targeting. The hero spends the action lighting themselves and never rolls the crossbow attack. In the base, Light was not in the spell registry and the attack row had no spell veto, so this line was a normal AttackCommand. Fix: apply the `_plain_word_spell` rule from cast_intent (a LightSource or Utility spell counts only after a cast word) inside `named_spell`, and ignore a spell-name span that sits inside a weapon or attack option name the hero has. That covers both the veto and the fight_cast routing.

**Verification:** normal. Trigger: a caster with Light among their cantrips (now possible because data/bg3/spells/light.json is new and lists bard, cleric, sorcerer and wizard) types a weapon attack in a fight that names a "light crossbow" or "light hammer". Both are simple weapons, and the SRD gives clerics and sorcerers a light crossbow as a starting choice.

How it happens:
1. Tokenising and matching. `fight_names.tokens` splits "I attack the goblin with my light crossbow" into words that include "light".

## 2. `aidm/dm/give_intent.py`, lines 166-173

**Status:** fixed in M33.1 (8853559)

- **File:** aidm/dm/give_intent.py
- **Lines:** 166-173
- **Severity:** normal

### Comment

A counted give of a stacked inventory item ("give two arrows to Bram", "give 3 potions of healing to X") hands over only ONE unit, then tells the player it was all they had ("X had only 1 of those to give") even when they carry plenty.

### Reasoning

`_count` sets `said=2`, and `_thing` returns the inventory key. `more` is built only from `_keepsakes(...)`, so for a normal item it is empty. hand_over.give_intent then calls `_give(..., (thing,))`, and `gift_events` takes exactly one unit (`delta=-1`, social_deeds.py:116). Because `GIVE_ALL > 2 > 1` is true, hand_over.py:84 then shows the notice `ONLY` with n=1. Result: a hero holding 20 arrows who types "give two arrows to Bram" gives one arrow and is told falsely that they only had one. Before this change the count was not parsed: one item went over and there was no false notice. Fix: only count keepsakes toward `said` (or repeat the gift per unit for inventory items, checking the real qty), and only show `ONLY` when the hero really holds fewer than asked.

**Verification:** normal. Trigger: a hero types a counted give of an ordinary stacked inventory item to an NPC, e.g. "give two arrows to Bram". I traced it through the code:

- **Count is parsed.** `_count` (give_intent.py:91-95) matches the `counted` pattern `(?P<n>\d+|two|...) (?P<rest>.+)` (intent_phrases.json:802), so it returns `said=2` and `name="arrows"`.
- **The item is found.** `_thing` (98-116) finds no keepsake, then matches the inventory entry: `item_words` strips the trailing "s" (quest_items.py:131), so "arrows" fits "arrow". It returns the inventory key.

## 3. `aidm/dm/offer_intent.py`, lines 51-60

**Status:** fixed in M33.1 (8853559)

- **File:** aidm/dm/offer_intent.py
- **Lines:** 51-60
- **Severity:** normal

### Comment

`offer_strike` decides a typed line is an attack just because some word in it appears in a lexicon set. It does not check which word is the verb, whether the line is negated, or what the line means. 'bow' is in both `weapon_ranged_words` and `lead_in_verbs`, so a courteous bow to the waiting foe answers the offer as FIGHT. The fight cannot be undone, and the same line is then replayed as a ranged attack.

### Reasoning

An encounter offer waits at the party's location. A player types 'I bow to the bandit captain'. The `offer_strike` row fires because the foe is named and no parley, strike-veto or stealth word appears. `said_weapon` finds 'bow' in `weapon_ranged_words` and returns the hero's ranged option, so `offer_strike_turn` answers the offer as FIGHT and starts combat. `waiting_line` keeps the text, and on the hero's turn `weapon_strike` reads 'bow' plus the foe as an `AttackCommand` with the ranged option. A polite gesture becomes a fight and a shot. Other lines that trip it the same way: 'I warm my hands by the fire, watching the bandits' ('fire' is a strike verb) and 'I keep my bow slung and greet the gnoll'. Negated lines such as 'I won't attack the bandit' also trip it unless a parley word happens to veto them. Before this change all of these went to the storyteller or the parley path, and the offer kept waiting.

**Verification:** normal. Trigger: an encounter offer is waiting at the party's location, the hero has a ranged attack option (shortbow, crossbow and so on), and the player types a courtesy such as "I bow to the bandit captain".

How it happens:
- The `offer_strike` row (data/bg3/intent_phrases.json:2394-2418) has no patterns. In `intent_match._matches`, a row with no patterns gives `[(-1, None)]`, so it matches any line. Its only gates are the `offer_waits_here` and `foe_named` conditions, plus vetoes from the `parley_*`, `strike_vetoes`, `self_surrender` and `stealth_words` sets.

## 4. `aidm/session/scene_votes.py`, lines 54-63

**Status:** fixed in M33.1 (8853559)

- **File:** aidm/session/scene_votes.py
- **Lines:** 54-63
- **Severity:** normal

### Comment

The road-by-road travel walk does not stop when a quest giver at an intermediate stop opens their Accept / Not now card. `_stop_reason` checks only a pending crossing card, a fight, a shut road and an encounter offer. It never checks `state.world.quest_ask`, so the walk takes the next road at once, and `PartyMoved` withdraws the giver's question (world_apply.py:148 sets `quest_ask = None`). Before this change, travel was always one road, so the party always stopped at the node where the card opened. Fix: `_stop_reason` should treat an open quest ask (and, in the same way, an open finale card, the other 'busy' states in `rules.quest_offers._busy`) as a stop reason, with a STOPPED line.

### Reasoning

The party is at A and types "we head to the Briar Vein", which is C, reached via B in the same region. The vote passes and `_route_job` runs `travel_job(B)`. `conclude` -> `follow_ups` -> `settle_after` -> `ask_events` sees the PartyMoved arrival at B, where a side-quest giver is meetable, and applies `QuestAsked`. The narration tells the giver asking for help and the Accept / Not now card opens on the phones. `_stop_reason(core, B, ...)` returns None: `core.pending` is None (travel_job cleared it), there is no fight, current_node == B and there is no encounter offer. So the loop sets `hop = C` and calls `travel_job(C)`. `run_move_party` has no quest_ask check, and only cross-region moves raise a crossing card, so `PartyMoved` is applied and `_moved` sets `world.quest_ask = None`. The card the players just saw is withdrawn before anyone can answer it, and the party ends at C. To take the quest, the players must walk back to B so it is asked again. Before this change the same typed travel moved only to B and stopped there, so the card stayed answerable.

**Verification:** normal. Trigger: a multi-road travel goal (`TravelIntent.goal`, new in this change) passes through an intermediate node where a side-quest or favour giver can be met.

How it happens:
- `_route_job` (aidm/session/scene_votes.py:66-89) calls `party_actions.travel_job(core, actor_id, hop)()` for each road. That function (party_actions.py:91-93) clears `core.pending` and applies the move, then runs `conclude`.
- `conclude` calls `follow_ups` (telling.py:129), which calls `settle_after` (quest_flow.py:56), which calls `ask_events`.

## 5. `aidm/session/intent_turn.py`, lines 116-120

**Status:** fixed in M33.1 (8853559)

- **File:** aidm/session/intent_turn.py
- **Lines:** 116-120
- **Severity:** normal

### Comment

Compound line playback throws away every unrouted part whose first word is in `lead_in_verbs`. That list includes check-worthy acts (climb, jump, leap, vault, scramble, dash, charge), so they are never ruled on or told.

### Reasoning

Out of a fight, a player types "I climb the wall and search the room". `clause_parts` splits it into two parts. "search the room" routes to SearchIntent, so `_compound` returns both parts. In `_play_parts`, "climb the wall" routes to None and `is_lead_in` is true ("climb" is in data/bg3/intent_phrases.json lead_in_verbs), so `left += []` drops it. The search runs, the climb gets no Athletics check, and the storyteller never hears of it. The docstring says such parts are "told with the rest", but nothing tells them. On the base branch the whole line went to one path (search_turn or the adjudicator) with all its words. Fix: add lead-in parts to the storyteller text instead of dropping them, or narrow the list to pure gestures.

**Verification:** normal. Trigger: out of a fight, a player types a compound line where one part starts with a movement or stunt verb from `lead_in_verbs` and another part routes to an intent, e.g. "I climb the wall and search the room" in a place with something hidden, or "...and look around" / "...and hand X to Y".

How it happens:
- `aidm/session/intent_turn.py:119-120` handles a part that routes to nothing with `left += [] if is_lead_in(part) else [part]`. A lead-in part is therefore neither run nor added to `left`, the list that goes to `adjudicated` at line 126.

## 6. `aidm/dm/guard_present.py`, lines 92-99

- **File:** aidm/dm/guard_present.py
- **Lines:** 92-99
- **Severity:** normal

### Comment

`stale_terms` flags every encounter-catalogue foe name not in play during every fight and every waiting offer, and `stale_foe_skips` is empty in the lexicon. Ordinary words like "scout(s)", "noble", "priest", "knight", "veteran", "acolyte" and "mimic" become STALE_FOE violations in normal prose.

### Reasoning

In a fight against wolves, the narration says "Rook scouts the treeline for the pack leader" or "the priest's warning comes back to her" (an NPC who is not present). `_in_play` is true whenever a fight is active. 'scout', 'priest', 'noble', 'knight' and 'veteran' are single words of 5+ letters in data/bg3/encounter_monsters.json, so they land in `stale_foes`. `guard_talk.stale_foe` matches "scouts" or "priest" and raises STALE_FOE ("no Scout is here now"). The guard rejects or scrubs good sentences, which leads to retries and template fallbacks, in every fight. Before this change, no such check existed. Fix: limit stale terms to names that cannot be read as common English words (fill `stale_foe_skips` with scout, noble, priest, knight, veteran, acolyte, mimic, gladiator, ...), or only flag a term when it is used as a creature noun (a count word or article plus the noun as the subject of an action).

**Verification:** normal. Trigger: any narration written during an active fight or while an offer is waiting that uses an ordinary English word which is also the name of a catalogue monster not in play, e.g. "scouts", "noble", "priest", "knight", "veteran", "mimics", "skeleton", "assassin".

How it happens:
- `aidm/dm/guard_present.py:69-74` `_in_play` is true whenever `enc.status is EncounterStatus.ACTIVE` or `state.campaign.offer is not None`.
- `stale_terms` (lines 92-99) then adds every encounter_monsters entry that is not one of the present foes.

## 7. `aidm/session/waiting_line.py`, lines 23-25

**Status:** fixed in M33.1 (8853559)

- **File:** aidm/session/waiting_line.py
- **Lines:** 23-25
- **Severity:** normal

### Comment

An attack typed at the offer and held on the seat is dropped silently if the player has no open connection when the hero's turn opens. This happens when the player is away within the reconnect grace, and on the autoplay 'away' path. The WAITS notice had promised the line would be played as typed.

### Reasoning

offer_strike_turn tells the player "What you typed waits for {name}'s turn and is played then, as typed." If the phone drops or reloads before that turn, `_prompt` takes the grace branch (combat_flow.py:169-170). It then calls `waiting_line.play`, which clears `owner.waiting_line` and, because `owner.conns` is empty, never queues the line. When the player reconnects inside the grace window they get their turn back, but the attack is gone with no notice. If the seat is fully away, combat_flow.py:138-141 autoplays the safe default and the line is dropped later by `drop_all`. Either way the promised act never happens and nobody is told, which breaks the review notes' rule that a held line is never replayed twice or never and nothing fails silently. Fix: keep the line until it is actually submitted (for example, play it on resume or reconnect while the turn is still open), or tell the player plainly that it was dropped.

**Verification:** normal (small, bounded): this happens when the player's phone drops or reloads after the WAITS notice and before their hero's turn opens, or while that turn's narration is still being told. The reconnect grace was added for exactly this case: combat_flow.py:95-96 says "a phone that drops for a moment does not lose its turns".

How it happens: offer_strike.py:45-46 stores the text with `waiting_line.keep(player, entry.text)` and tells the player WAITS ("What you typed waits for {name}'s turn and is played then, as typed.").

## 8. `aidm/dm/guard_turn.py`, lines 282-289

- **File:** aidm/dm/guard_turn.py
- **Lines:** 282-289
- **Severity:** normal

### Comment

`talk_truth` sets `coin_ok` only for a shop event, or for an open non-favour quest that is asked or whose giver stands here. It ignores coin the engine itself moves this turn: a pay hand-over (`GoldChanged` + `HandedOver` from rules.paying.pay_events) or a completed campaign quest's gold payout (quest_rewards; the quest is now COMPLETED, so `_givers_here` skips it). As a result, `promised_coin` flags honest narration of real payments and rewards ('as payment', 'your reward', 'good coin', 'a few coins' with a coin noun). Fix: set `coin_ok` when these events move gold, i.e. a GoldChanged, a HandedOver with gold, or a quest completing with a payout.

### Reasoning

Case 1: the player types 'I pay Rutter 5 gold for the crossing'. The new pay path applies GoldChanged and HandedOver, and `conclude` narrates them. talk_truth sees no ShopOpened/ItemsTraded, and Rutter gives no non-favour quest, so coin_ok=False. The narration 'Rook presses five gold into Rutter's palm as payment' contains 'as payment' (coin_promises) and 'gold' (coin_nouns), with no negation, so it gets COIN_PROMISED ('nobody promises coin here'). Case 2: delivering a campaign side quest pays its gold reward (GoldChanged) with QuestUpdated(COMPLETED). The completed quest is no longer open, so coin_ok=False, and 'Merre counts out your reward: forty gold' is flagged too. The same check binds NPC speech, so 'Here is your reward, as promised' in the giver's voice is also rejected. The base has no such check, so after this change the guard retries the model and then falls back to the template on exactly the payment and reward beats the engine produced. The tests only check that false promises are flagged and never try a turn with a real payment or reward.

**Verification:** normal. Trigger: a typed payment to an NPC who gives no open non-favour quest, or a turn that completes a quest and pays its gold, narrated with ordinary words like "as payment", "your reward" or "good coin". The guard flags this honest narration as COIN_PROMISED.

Mechanism, checked in aidm/dm/guard_turn.py:282-289:
- `coin_ok = shop or any(q.kind is not QuestKind.FAVOUR for q in held)`
- `held` is built only from the quests of `QuestAsked` events plus `_givers_here(state)`.

## 9. `aidm/dm/guard_present.py`, lines 48-110

- **File:** aidm/dm/guard_present.py
- **Lines:** 48-110
- **Severity:** normal

### Comment

guard_present leaves out the offer's master (boss_npc_id). The master is never in `monster_ids`: encounter_offer._monsters drops it with `[1:]`, and it is kept only as `boss_npc_id`. The new `OfferResolved.foes` copies only `offer.monster_ids`. So on the turn a master offer is answered (parley or escape success, which clears `campaign.offer`), `foes_here` adds 0 for the master. `stale_terms` also never counts the master's kind as in play, and it leaves NPC `archetype_id` out of `taken` even though guard_scene._role_words (guard_scene.py:140) includes it. Fix: include the master in the offer's foe set, either a boss field on OfferResolved or its archetype in `foes`, and add present NPCs' archetype words to `taken`.

### Reasoning

A region master offer waits: the master, a bandit-captain archetype named 'Captain Vex' with role 'boss', plus 2 companions. The party parleys and succeeds. The events are [OfferResolved(foes=(2 companions)), CheckResolved], and the reducer sets campaign.offer=None. `foes_here` now returns 2 + master 0 = 2. The honest line 'Vex nods, and the two behind him lower their blades' matches figure_counts' 'the two behind him' pattern as 2+1 = 3 > 2, so it is flagged FOE_COUNT ('only 2 foes here'). While the same offer waited, the count was 3. Separately, while a master offer waits or is answered, `here` holds only the companions' kinds, and `taken` holds only the NPC's name and role ('boss'). So 'Vex, the bandit captain, steps forward' is flagged STALE_FOE ('no Bandit Captain is here now') even though that master is the one standing there. The guard re-asks the model or falls back to the template on the region master's own beat. The base has neither check, so this false rejection of honest prose is new. The existing tests (test_m32_r5_storyteller X14) only use a master-less offer, so they do not catch it.

**Verification:** normal (bounded: the guard wrongly flags honest narration on the turn a master offer is resolved). Trigger: a region-master offer with companions is answered by parley or escape and the narration counts the master's companions as "the N behind him".

Why the master is left out:
- aidm/rules/encounter_offer.py builds the master's company with `_company(rng, data, themes, cap, [boss.archetype_id], len(levels))[1:]`. `_company` starts `picked = list(lead)`, so the `[1:]` drops the master. The offer then stores `monster_ids=tuple(monsters)` and keeps the master only as `boss_npc_id=boss.id`.

## 10. `aidm/server/tts.py`, lines 110-113

- **File:** aidm/server/tts.py
- **Lines:** 110-113
- **Severity:** normal

### Comment

Conditional: this applies when a Fish Audio render takes longer than the timeout. That happens when the provider is slow or hangs, or when the SDK's sync HTTP client has no shorter read timeout. `asyncio.wait_for(asyncio.to_thread(self._render, ...), timeout_s)` gives up waiting but cannot stop the worker thread. Each timed-out or cancelled render keeps a thread of the loop's shared default executor busy until the SDK call returns. Nothing caps how many renders are in flight: NarrationPipe starts one synth task per sentence and cancels it after tts_wait_s (8 s). Fix: run renders on a dedicated, small, bounded executor (or a semaphore that skips synthesis when it is full), and give the SDK call its own client-side timeout, so a stuck render can never take threads from the default executor.

### Reasoning

The host turns TTS on, and Fish starts stalling (a provider incident or a dead connection with no read timeout). Each narrated sentence calls `NarrationPipe.add` -> `_synthesize` -> `FishTts.synthesize` -> `to_thread(_render)`. After 8 s `_audio` cancels the task, and after 25 s at most `synthesize`'s own wait_for gives up, but the thread keeps blocking in `session.tts(...)`. A few narrations of 5-6 sentences fill the default ThreadPoolExecutor (min(32, cpu+4) workers, for example 8 on a 4-core host). asyncio's `loop.getaddrinfo` uses that same default executor, and anyio/httpx use it for every new LLM connection. So DNS for new LLM connections queues behind the stuck TTS threads, `LlmClient._send` hits its timeout, and narration and adjudication fall back to templates for the whole table until the stuck renders return or the server restarts. Even without a full hang, every render that finishes after its waiter was cancelled is paid for and thrown away, because `_store` never runs.

**Verification:** normal. Trigger: TTS is on and Fish Audio is slow or stalls (a provider incident, or a dead connection the sync SDK client never times out). aidm/server/tts.py is a new file in this diff. Lines 110-113 run `asyncio.wait_for(asyncio.to_thread(self._render, ...), self.settings.timeout_s)`, which uses the loop's shared default ThreadPoolExecutor. A timeout or cancel only cancels the asyncio wrapper. The worker thread keeps blocking in `for chunk in session.tts(request, ...)` (line 142), and nothing in `_render` can interrupt it.
