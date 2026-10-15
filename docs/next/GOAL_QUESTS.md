# GOAL: Quests you can follow (M23)

Owner request, 2026-10-15. Binding. Main-session decisions are marked **D:** and repeated in docs/DECISIONS.md
when they land.

Owner: "I had many quests that randomly started, not sure when it was getting updated etc... For us it was not
always clear what to do, when we got quest items what to do with them" and "it would be cool to be able to
complete the main questline in different ways."

## What the Slendee playtest showed (save c-20261010-161143-6031)
- No quest ever became active or completed: all 6 quest events are `offered` (3 bulk-offered at install, 3 the
  moment Brother Molt died). The AI never called `update_quest`; the objective is free text the engine cannot check.
- The AI context lists quests as `title [id] (state), given by X` only (`dm/context_sections.quest_lines`): no
  objective, no act goal, no route. Yeva invented a different bell quest; the found "False Bell-Tongue" keepsake
  did nothing. Killing Molt at the bell abbey did not finish the bell quest.
- An act-1 quest's giver lived in the act-2 region (The Ferrystones). The shrine quest said "cult", the shrine had
  stirges. Korvell's ally path needs a river-stone no quest places.
- Vess "took" the bell-tongue in the story, the save still has it on Slendee (no hand-over for keepsakes).
- The gateway rule (opens when every spoke is visited) is shown nowhere: ~10 actions spent on the abbey door.
- The screen header showed "Objective: A Bell's False Tongue" (first offered quest by id) the whole game.

## Owner answers
1. Taking on a quest is explicit: an **Accept / Not now** card.
2. Per act: **one pinned main quest** plus **1-2 deeper side quests**.
3. Next-step guidance only when someone presses **What now?** (no always-on next step).
4. Quests the AI makes up: the main session's **favours** proposal (below).
5. Only engine-placed quest items count; keepsakes stay flavour (main session's recommendation).
6. Leaving a region: confirm card, then unfinished tasks close as "left behind" (main session's recommendation).
7. The main questline can be finished in different ways (routes), and the finale is a real choice.

## Design
### Steps (one vocabulary, engine-checked)
A quest is 1-4 ordered steps. Each step has player text (<=100 chars) and one kind:
`visit(node)`, `clear(node)` (a fight there won), `defeat(npc)` (that NPC or boss dead), `obtain(item)` (a placed
quest item carried), `deliver(item, npc)` (handed over), `meet(npc)` (the party stands where that NPC is, alive and
not hostile), `win_over(npc, band)` (attitude band reached), `learn(tag)` (`rules.secrets.engine_knows`),
`free(text)` (only the AI can judge it; it proposes completion, the engine records it). The engine checks steps
after every mechanics batch (the same hook points as `resolution_reward_events`) and advances quests itself.
**D:** steps are sequential; `obtain` may need a count (3 keystones = one step "2/3").

### Kinds of quest
- **Main quest** (one per act, pinned): objective = the act goal, active at act start (no card: it is the story).
  It has **routes**; finishing any route resolves the region:
  - **Force** (always): explore the region (spokes visited x/N), then defeat the boss. Never removed (SPEC 9).
  - **Peace** (when the boss has an ally path): concrete steps from the ally path (e.g. obtain the river-stone,
    deliver it to Korvell). Completing it allies the boss through the existing alliance resolution.
  - **Cunning** (optional): steps that weaken the boss fight (its company deserts, or the party arrives unseen
    and the boss starts surprised). Does not resolve the region by itself.
  Routes are **discovered**, not listed: a route becomes known when the party meets its hint NPC (a plan NPC of
  that region, not hostile) or completes any of its steps. The narrator is told the hint once.
- **Side quest** (1-2 per act, from the plan): giver, objective, steps, reward tier, optional reward item.
- **Favour** (made up in play): the AI may register one only when a present NPC asks for something; exactly one
  typed step (no `free`); at most one open favour; same Accept card; the engine closes it; it pays goodwill with
  that NPC only (no XP, no gold: cannot be farmed); it expires when the party leaves the region.

### Lifecycle (who moves a quest)
- Nothing is bulk-offered. **Leads**: on first arrival in a region the journal gets one line per side-quest giver
  elsewhere in it ("Someone at Bleakfen Shrine may need help").
- **Offer through a person**: arriving where a side quest's giver is (alive, not hostile) makes the giver ask
  (one offer per arrival). The narrator gets "<giver> asks the party: <objective>"; the phones get the card
  "<giver> asks: <title>. Accept / Not now" (answered like the encounter offer card). Accept -> active.
  Not now -> stays offered; the card comes back on the next arrival there.
- **Act change**: regions are one-way (gateway -> next arrival). Crossing with open side quests or a favour asks
  first ("Crossing leaves these behind: ..."; same confirm pattern as the hostile-act card). On crossing: quests
  whose steps are all done complete (and pay); the rest close as **left behind** (no penalty, greyed in the journal).
- **Fail** only by events: the giver dies, a needed item is destroyed. Never by a timer.
- Plan quests and their steps are engine-owned: `update_quest` may only complete a `free` step.

### Items
- Quest items are keepsakes with a `quest_id` ("Quest item: for Yeva's task"), placed by the engine at a node of
  the act region at act start (visible, or hidden and found by search). They cannot be sold or dropped.
- Keepsakes without a quest are flavour and say so. Handing any keepsake to a present NPC really moves it
  (event), which is how `deliver` completes; a "Give <item> to <npc>" chip shows when that NPC is present, and
  typed "give the bell-tongue to Yeva" is a deterministic precheck.
- `give_keepsake` refuses a lookalike of a placed quest item that lies elsewhere; the AI is told where quest items
  lie, so it hands over the real one.

### What players see
- **Journal**: main quest pinned with its known routes; each quest shows giver, objective, the steps done so far
  (ticked, with counts) and a short log of what happened in it; groups Active, Offered, Leads, Completed,
  Left behind / Failed. **D:** the journal shows what is done, not the next step (owner answer 3).
- **What now?** (button on the Play tab, plus typed "what now / what should we do"): deterministic engine text,
  no model call, not a turn: the current step of the main quest's known routes and of every active quest, where
  to go (place names), offered quests waiting, leads; when nothing is known, a nudge toward an undiscovered
  route ("Yeva may know more about Brother Molt"). Shown on the asker's phone and in the screen feed.
- **Updates are moments**: quest offered / accepted / step done / completed / left behind are engine lines on the
  screen plus a toast on the phones ("Journal: The Ferrystones, keystones 2/3").
- Screen header: the main quest's objective (never a side quest title). Now card: the main objective.
- A locked gateway says why when the party tries it ("The abbey stays sealed while the Marches still hide
  places you have not seen: 2 left"). This is a world fact, not a hint.

### Finale
The plan writes a finale question with two endings (e.g. silence the song / let it finish). When the final
region resolves, the party gets the finale card (answered like the offer card, then "Are you sure? This ends the
story"); the choice is an event and the epilogue tells it together with how each region was resolved.

### Plan generator and checks
- Draft schema writes steps by name (places, NPCs, items) and code resolves them (repair over reject, M16.1):
  an unresolvable step becomes `free`; a quest whose giver lives in another act moves to that act.
- Checks: every `obtain` item is placed in the quest's act region; `deliver`/`meet`/`defeat` NPCs live in that
  region (or are its boss); no step names a later act's place; routes are completable; 1-2 side quests per act.
- The built-in sample campaign gets steps, routes and a finale.

### Old saves
Plans without steps load: side quest -> `[free(objective), meet(giver)]`; main quest from the act goal with the
Force route (and Peace as one `free` step when there is an ally path); no finale -> the campaign ends as today.
Bulk-offered quests in old saves stay offered. The Slendee save must load and read sensibly (test).
