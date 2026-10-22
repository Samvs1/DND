# GOAL: Gear that matters (M27)

Owner request, 2026-10-17. Binding. Main-session decisions are marked **D:** and repeated in docs/DECISIONS.md
(rules choices in docs/RULES_DECISIONS.md) when they land.

Owner: "items that don't do anything (scrolls, ropes etc...). I want players to still be able to use them and gain
some sort of advantage by actually applying them correctly (in combination with their proficiency). For example, a
dark cave, player says i light my torch -> cave gets illuminated."

## What is there today (main-session survey, 2026-10-17)
- Only weapons, armour, potions, camp supplies and engine-placed quest items do anything. ~147 SRD gear and tool
  items are price and weight only.
- Unwired: `rules/scrolls.py` (wizard copy, never called), `rules/item_grants.party_key_for` (keys, never called),
  `data/srd/magic_items.json` (never loaded). Shops sell keys and scrolls that do nothing.
- Unused on the sheet: darkvision (`character_io.py`), tool proficiencies.
- Reusable: `RequestCheckArgs.advantage` + `CheckResult.adv_why` (M26.2, the dice show the reason), surfaces with
  interactions (`surfaces.json` has oil; fire into oil ignites), hidden features/items found by search,
  `WorldFeature` kinds (door, cache, container, passage, trap...; no lock state), the potion Use flow and the hotbar
  Items section, the deterministic give parser (`dm/give_intent.py`), the spell engine, surprise in encounters.
- Places have no light level. Zone templates: wilds, forest, ruins, bridge, cave, village, swamp, keep, crypt.

## Owner answers
1. Scrolls as in BG3: **anyone** can read one.
2. Darkness **imposes disadvantage**; light **removes** it (no advantage from light itself).
3. The AI **keeps** its free advantage flag for situations no item covers.
4. Wear: consumables are used up (oil, torches, scrolls, vials), tools last forever, the healer's kit has charges,
   a lit torch lasts until the party leaves the place.
5. Using gear may carry a small risk (light gives you away, forcing a lock is loud), as long as the code stays simple.
6. Darkness in a fight: option **B** (heroes without darkvision attack at disadvantage in a dark place until it is lit).
7. Darkness must be **obvious** to players, especially in a fight, through the UI, **per zone**.

## Design
**D: ONE interpreter, data over code.** `data/bg3/item_uses.json` lists each usable item's uses; a pure
`rules/item_use.py` interprets them. No per-item branch anywhere. A use names:
- `item` (catalogue id; scrolls by the `scroll-of-*` family), `verbs` (parser words: light, tie, climb, pry, read...),
- `when`: `dark_place` | `locked` (feature) | `place` (any, out of a fight) | `fight` | `ally_down` | `long_rest` |
  `tagged_place` (terrain tag list, e.g. water),
- `effect`, one of a closed vocabulary: `light_place`, `boon` (advantage on listed skills or saves; scope `place` or
  `until_long_rest`), `surface` (zone + surface id), `damage` (attack or save, dice, type, optional creature types),
  `condition`, `unlock` (method key/pick/force), `supplies` (check + amount, once per place), `stabilize`, `craft`
  (inputs -> item), `cast_spell` (scroll), `reveal_map` (adjacent places become known),
- `cost` in a fight (`action` | `bonus`), `consumes` (bool) or `charges`, `tool` (true for SRD tools: proficiency applies),
  `noise` (bool: see Risk).

**D: the AI proposes, the engine disposes.** New tool `use_item(actor, item, target?)`. The engine checks: the hero
carries a CATALOGUE item (keepsakes never count, even when named "Rope"), a use of that item fits the target and
the situation, the action economy in a fight. Then it emits events, or `ItemUseRefused(message)` that tells the model
what to narrate instead (pattern: `FreeStepRefused`). A deterministic precheck (`dm/use_intent.py`, like
`give_intent`) answers the common phrasings without the model ("light my torch", "use the rope on the cliff",
"throw the oil at the goblin", "read the scroll of sleep").

**D: engine-owned advantage from gear.** An active boon applies to every matching check by itself, whatever the AI
asked, and `adv_why` names it (*Torchlight*, *Crowbar*). Darkness is applied the same way (*Darkness*). Advantage
never stacks (SRD).

**D: the rope rule (anti-trick), scoped (owner, 2026-10-22).** It applies only to situations the item table covers
(a lock, a dark place, climbing or crossing, searching, and the other `when`/skill pairs in item_uses.json): when
the acting text names an item the hero carries and that item has no use fitting the target there, the engine drops
the AI's advantage on that action's check (the attempt itself may still be a fair plain check, e.g. Strength to
force a door). Outside those situations the AI's judgment stands ("I tie up the goblin with my rope" gets a fair
call). The parser already finds item names; this is one check.

**D: proficiency.** Anyone may use any tool. A check made with a `tool` item adds the proficiency bonus when the hero
is proficient with the tool OR the skill (once, SRD); proficient in BOTH -> advantage (house rule, RULES_DECISIONS).
Herbalism crafting alone requires the tool proficiency (SRD).

## Light and darkness
- A place is dark when its zone template says so: `"dark": true` on `cave` and `crypt` in `zone_templates.json`
  (data; derived, never stored, so old saves need nothing). Magical Darkness surfaces stay as they are and mundane
  light does not dispel them (SRD).
- **D: a light is carried, not placed (owner, 2026-10-22).** Lighting a torch, candle or lantern gives that hero a
  lit light that stays lit and moves with them from place to place until the next long rest (one torch covers a
  whole trip; SRD: a torch burns 1 hour). A torch or candle is used up when lit, a lantern is not. A dark place is
  lit while a hero carrying a light is there. One light per hero; several heroes may carry one.
- **D: putting a light out (owner, 2026-10-22).** Free, in or out of a fight ("put out my torch", "douse the
  torch", the **Put out light** button). A torch or candle is spent once lit, so putting it out uses it up; a
  lantern can be put out and relit as often as you like (the light for a party that wants to sneak). Putting a
  light out does not un-alert a place that already saw it.
- Out of a fight, in a dark unlit place: sight checks (Perception, Investigation, and every search check) roll at
  disadvantage for everyone (darkvision sees darkness as dim light, which still gives disadvantage on Perception: SRD).
- **D: in a fight, light is per zone** (owner answer 7). In a dark place every zone is dark unless lit. ONE derived
  function `zone_lit(state, zone)`, nothing stored per zone: a zone is lit when a hero carrying a lit light stands
  in it or in a touching zone (torch and lantern: 20 ft of bright light covers the next 15 ft hop, SRD; a candle
  lights its own zone only), or a fire surface burns in it. The light moves with its bearer. Every hero carrying a
  light when the fight starts is a bearer.
- A hero WITHOUT darkvision attacks a target standing in a dark zone at disadvantage; monsters see (one more source
  in the existing attack advantage helper, next to high ground). Lighting a torch in a fight costs a bonus action.
  This makes the torchbearer's position matter, the way it does in BG3.
- **Never a softlock:** darkness only adds disadvantage. It never hides a quest item or a needed passage outright.

## Locks
- `WorldFeature.lock: LockInfo | None` (optional field; old saves load unlocked): `dc_tier`, `opens` kind for keys.
- Locks are placed only on caches, containers and side doors; **never** on the main path, a gateway or a quest item
  (checked by the plan checks; the generator repairs, never rejects).
- Ways to open: a fitting key (automatic, `party_key_for`), thieves' tools (DEX check, tool proficiency), force
  (Athletics; a crowbar gives advantage; noisy). Forcing can always be retried.

## Risk (kept simple)
**D: one flag.** A `noise` use (lighting a dark place, forcing a lock, a failed force) marks the place `alerted`
until the party leaves. Arriving in a dark place while carrying a lit light also marks it (the light gives the
party away; this keeps the choice between light and surprise now that a light lasts). Foes met at an alerted place
cannot be surprised by the party. Nothing else. To sneak, put the light out BEFORE walking into the next dark place.
**The party must always be able to see this rule** (owner, 2026-10-22; see "What players see").

## Items (first batch, ~25; SRD 5.1 numbers in the goldens)
| Item | Use | Effect |
|---|---|---|
| Torch, Candle | light a dark place (fight: bonus action) | `light_place`, consumed when lit, stays lit until the next long rest, noise; a torch thrown at an oil zone ignites it (and ends the thrower's light) |
| Lantern, hooded | light a dark place | `light_place`, not consumed, stays lit until the next long rest, noise |
| Lantern, bullseye | light + search | `light_place` + advantage on Investigation here |
| Crowbar | force a lock / stuck door | advantage on the Strength (Athletics) check (SRD), noise |
| Rope (hempen, silk), Grappling hook, Climber's kit, Piton | climb or cross here | advantage on Athletics here, out of a fight |
| Magnifying glass | inspect | advantage on Investigation here (SRD) |
| Spyglass | look far | advantage on Perception here |
| Cartographer's tools, Navigator's tools | chart the way | `reveal_map` (adjacent places known), tool |
| Thieves' tools | pick a lock | `unlock` by DEX check, tool |
| Disguise kit, Forgery kit | disguise / forge | advantage on Deception here, tool (needs proficiency) |
| Musical instruments, Gaming sets | perform / gamble | advantage on Performance here, tool (needs proficiency) |
| Healer's kit | stabilize a fallen ally | `stabilize`, no check (SRD), 10 charges |
| Herbalism kit | at a long rest | `craft`: 2 camp supplies -> 1 Herbal Poultice, needs proficiency |
| Fishing tackle | at a water place | `supplies`: Survival check -> +2 camp supplies, once per place |
| Hunting trap | in wilds/forest | `supplies`: Survival check -> +2 camp supplies, once per place |
| Antitoxin | drink | advantage on saves against poison until the next long rest (SRD) |
| Oil (flask) | throw at a zone | oil surface (exists); fire ignites it |
| Alchemist's fire | throw | ranged attack, 1d4 fire + burning (SRD) |
| Acid (vial) | throw | ranged attack, 2d6 acid (SRD) |
| Holy water | throw | ranged attack, 2d6 radiant to undead and fiends (SRD) |
| Caltrops, Ball bearings | scatter in a zone | new surfaces (data): caltrops = rough + damage on entering, DC 15 DEX save; ball bearings = DC 10 DEX save or prone (SRD) |
| Spell scrolls | read (action) | the spell through the spell engine, no slot, consumed; save DC / attack from the SRD Spell Scroll table by spell level; a wizard may instead COPY it (wire `rules/scrolls.py`, 50 gp per level) |

Everything else stays flavour you can sell. Magic items stay out of scope.

## Other rules
- `grant_item` refuses items that have uses (they come from shops, loot and starting packs only). Closes "I find a rope".
- One item use per action. A use that changes nothing (a torch in daylight) is refused and consumes nothing.
- The narrator is told only what happened: a refused or failed use is told as an attempt, never as a result.

## What players see
- The phone item card shows **Use** with what the item does here ("Light this dark place"), a target picker when
  needed; the hotbar Items section lists combat uses with their cost.
- **Darkness is never hidden** (owner answer 7):
  - **Hex map:** a dark zone is drawn dimmed (a dark overlay on its picture) with a **Dark** icon in its icon row;
    lit zones in a dark place glow warm around the bearer, whose token carries a small flame. The legend says what
    it means: *Dark: heroes without darkvision attack into it at disadvantage.* It updates as the bearer moves.
  - **Fight start:** an engine line on the screen and in the story: *It is dark here. Heroes without darkvision
    attack into dark zones at disadvantage.*
  - **Phone in a fight:** target chips carry a **Dark** badge and the hit chance already shows the disadvantage
    (*Darkness*); the Move list shows **Dark** / **Lit** per zone (like the cover badges); a hero who carries an
    unlit light gets a **Light torch (bonus)** slot on the hotbar while standing in the dark.
  - **Out of a fight:** the screen's scene picture is dimmed with a **Dark** badge on the ribbon, and so is the phone
    topper; the Now card says *It is dark here.*; an idea chip **Light a torch** shows when the party carries one.
  - **Who sees:** heroes with darkvision show an eye icon on their strip and in the turn order.
- **Light versus stealth is never hidden** (owner, 2026-10-22):
  - **Who carries a light:** a flame on the bearer's token and a **Torch lit** / **Lantern lit** chip on that hero
    in the party strip and on their phone.
  - **When a light is lit in a dark place:** one engine line in the story and on the phone: *Your light shows you
    the way, and shows you to anything waiting here.* The same sentence is in the Light and Put out tooltips (M28).
  - **Put out light:** a button on the bearer's phone (Now card and Items) whenever they carry a light; free.
  - **When it costs you:** a fight that starts at a place a light gave away says so in its start line: *They saw your
    light coming. No surprise.*
  - Manual: a short "Light and stealth" part in "Using your gear".
  - New pixel-art icons (dark zone, flame/lit, darkvision eye) go through the M10 pipeline; placeholders until then.
- Active boons show as chips on the phone.
- The dice show the reason (*Darkness*, *Torchlight*, *Crowbar*, *Tool + skill*).
- Manual: a new section "Using your gear" plus a generated table from `item_uses.json` (`gen_manual.py`).

## Done means
- In a cave: a search rolls at disadvantage (*Darkness*); "I light my torch" lights it, the torch is gone, the next
  search rolls straight; leaving and coming back the cave is dark again.
- A fight in a crypt: the board shows dark zones dimmed with the Dark icon; a human fighter attacking into a dark
  zone has disadvantage (shown on the phone before the attack), a dwarf does not; a torch (bonus action) lights the
  bearer's zone and its neighbours on the board, and the lit area moves when the bearer moves.
- "I use the rope to force open the lock": refused or a plain check, never advantage, never an open lock in prose
  without an `unlock` event (named FakeLLM test).
- "I search the corner and find a rope": no rope is granted.
- A rogue proficient in thieves' tools picks a lock with the bonus; a fighter forces it with a crowbar (advantage),
  the place is alerted.
- Oil then a thrown torch ignites the zone; alchemist's fire burns; holy water hurts only undead and fiends.
- Anyone reads a scroll of a shipped spell; a wizard can copy one for gold.
- Old saves load and replay unchanged.
