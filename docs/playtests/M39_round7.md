# M39 Round 7: three live runs after M38 (2026-10-26)

Every finding below was checked against the run's save (event numbers are `seq` in its events.jsonl).
"Output only" means the claim leaves no event (a refused `do` command, a console ERROR), so it rests on the playtester's output.
No fixes were made. The owner decides.

## Runs
| run | party, persona | campaign (generated) | reach | events | commands |
|---|---|---|---|---|---|
| r7b-typed (seed 2) | fighter, rogue, wizard, cleric; types everything | 4 regions, act 2 reached | end of act 2 (Second Seal of Null), all alive, L3 | 1512 | 219 of 220 |
| r7b-quests (seed 3) | classic; quest auditor | "The Grief of Ironglass" | region 2, mid-fight with its master, all alive, L3 | 916 | 160 of 180 |
| r7b-full (seed 1) | classic; normal table | "The Cinders at the World's Root" | acts 1 and 2 won, tier 3 reached, mid-fight, all alive, L4 | 1791 | about 313 of 320 |

Saves: saves/playtests/<run>/saves/ (c-20261026-120134-0002, c-20261026-120118-0003, c-20261026-120119-0001).
The first start (r7-typed, r7-quests, r7-full) was dropped: all three began in the same second, and commands without
`--run` went to the run started last (Z18). Its save c-20261026-114809-0001 is used only for Z8 and Z21.

## Fix verdicts
- **Y1 (two payouts on one step), holds.** The M35.1 ledger check (`scripts/sim/ledger.ledger_problems`) finds 0 problems on all three saves.
  In r7b-quests the peaceful give to Maresth closed The Drowned Toll and Widow's Due in one step, and both paid.
- **Y4 (no long rest while a foe waits), holds.** r7b-quests 848-856: a typed long rest with Marovech's offer waiting is refused,
  and the fight starts with the party surprised (manual Rests).
- **Y20 (campaign generation), holds.** All three campaigns were generated live, none fell back to the sample.
- **Y7 sub-case (a clear step credited from an earlier fight), still open** as M35.2 left it: Z15.
- **Y2, Y3 (guided, concentration) and Y9 (spell at a waiting offer)** did not come up.
- **M36/M38 menu interpreter in real play.** Most typed lines did the right thing: gives, buys, talk checks for the named hero,
  greetings and flourishes with no roll, the typed potion drink. The harmful misses are Z1 to Z8. Z1 and Z2 act on something the player did not mean.

## Findings
### Typed-line interpretation
- **Z1 (harmful) A typed "yes" at a talk card starts the fight.** r7b-typed 382 "...let us talk", 383 "Yes, go ahead, I mean it",
  384 `offer_resolved` choice `fight`. The same shape at the Orlok card worked (603-606 parley, success, alliance), so the playtester's "did nothing" claim is wrong.
- **Z2 (harmful) Travel to a place out of reach goes to another place.** r7b-typed 649 "We follow Sersha's trail to the Gear Nave",
  650 `party_moved` to the Censer Vault. The Gear Nave is the arrival of the tier-3 region. The barred-place fix from M38 does not hold here.
- **Z3 Gold from hero to hero moves only sometimes.** r7b-typed 36-41 and 147-148: four lines ("Brienne gives Elowen 3 gold",
  "I pass 5 gp to Rook", "Elowen pays Brienne 7 gold") move nothing, and the story says the other hero would not take it.
  r7b-full 423-426 "Rook hands Elowen 8 gold coins" moved 8. Gold to an NPC works (r7b-typed 149-151).
- **Z4 Paying more than the hero has pays everything.** r7b-typed 1250-1251: "Elowen pays Wren 500 gold" took all 60 she had.
  The manual says more gold than you have is refused with the reason.
- **Z5 A spell with no slot becomes another spell, silently.** r7b-typed 1277 "Tamsin sends a guiding bolt at the armor",
  1279 `spell_cast` sacred-flame. Tamsin (the cleric) had both slot levels at 0 (981, 1128) and no rest since.
- **Z6 Parts of a line are dropped.** r7b-typed 541 "We trudge back to the Rust Chapel and I search the iron walls" gives
  only the move (542). r7b-quests 913 "Elowen calls out and the party flees" removes only Elowen (915).
- **Z7 A line that names another hero sometimes acts as the sender.** Searches and pickups go to the sender: r7b-quests 114-117
  ("Tamsin searches..." sent from Brienne's seat, Brienne finds both items) and r7b-full 256-258 and 410 (Brienne keeps the notes and the moss).
  Talk checks go to the named hero: r7b-full 54-55 (Rook) and 57-58 (Elowen). No notice says who acted.
- **Z8 A count is lost.** Aborted r7-full 32-35: "Brienne hands Elowen two of the camp rations" moved 1. The line was another agent's, but it is a real line on a real state.

### What the storyteller says
The manual promises each of these never happens ("What the storyteller can and cannot do").
- **Z9 A foe is told down while it stands.** r7b-quests 739 (hobgoblin at 1 HP), 742 "folds over its axe... sprawling across the broken floor".
  r7b-full 673 (violet fungus at 6/18), 676 "folds with a wet sigh, its tendrils collapsing".
- **Z10 Sleep is told on foes it did not touch.** r7b-full 508-513: only Mortha sleeps, yet "the skeletons' strings slack, their bones settling".
- **Z11 A found item is told in hand before anyone picks it up.** r7b-quests 116-119: found, then "already rest in Brienne's hands";
  the pickup is only at 120-127.
- **Z12 The story undoes what the engine did.** r7b-quests 907-912: the potion is drunk (+7 HP), then "Marovech tears the potion from
  Tamsin's fingers... lets it fall to shatter". r7b-typed 1250-1253: Wren takes the 60 gold, then the next line has her turning the coins away.
- **Z13 A hand-over that cannot happen is told as the friend refusing it.** r7b-typed 47-48: Brienne "hands Rook the blanket"
  (she carries none; Tamsin does), and the story says Rook would not take it. r7b-typed 357: Rook's keepsake hand-over to Tamsin is told as hanging in the air.
  No reason is given. Z3's lines read the same way.

### Quests
- **Z14 A favour completes without returning to its giver.** r7b-quests 680-684: The Brief Life of War (giver Duscia Vane,
  "Prove to the archivist...") completes on its second visit step and pays 150 XP, 150 gold each and a signet.
- **Z15 A favour targets a friendly person and ticks a step off from an old fight.** r7b-full 436-444: Bram's "Straighten the River"
  has `against_npc_id` isca-murkline (the seer who had just helped); "Win the fight at The Grey Bog" closes at once from the fight before the quest (the Y7 sub-case).

### Balance (playtester feel, rolls in the saves)
- **Z16 "Trivial" and "easy" undersell some fights.** r7b-quests: a trivial hobgoblin on a dais (high ground: advantage for it,
  disadvantage for the party, 744 `adv_why` high ground) takes the 14-HP wizard to 0 in one round.
  r7b-full: a trivial berserker (67 HP) drops the wizard. r7b-typed: an easy bugbear takes 12 rounds (about 55 commands).
  High ground appears only in the roll line, and nothing says moving off it helps.
- **Z17 Resources run dry fast.** One long rest costs 10 supplies a hero, so it uses all 40 starting supplies (r7b-quests, r7b-typed).
  Casters are out of slots after one or two fights. A short rest offered no Arcane Recovery (r7b-full).
  Gold is plentiful from act 2 (r7b-quests 232 gp each at region 2).

### Tooling (the playtest harness, not the game)
- **Z18 Commands without `--run` go to the run started last** (saves/playtests/CURRENT). The first start was lost to it (127 calls).
- **Z19 `do use` lists only gear uses.** scripts/agent/commands.py `_use` reads the sheet's `gear_uses`. Potions are not there:
  the web hotbar lists them from the inventory (aidm/web/js/combat/hotbar_magic.js, category `potion`).
  So "the potion cannot be used from the fight buttons" (r7b-quests B2, r7b-full B1) is a harness gap; the typed drink works in both runs.
- **Z20 `do attack` sends no weapon choice** (`option: ""`), so the default attack can be the crossbow next to the foe,
  at close-combat disadvantage (r7b-quests 900-901). Not checked in the web UI.

### Small (output only unless an event is given)
- Z21: `ERROR wrong_phase` printed while the campaign was still generating (aborted start, event 23). Not seen again.
  One typed line opened the shop twice (aborted save 28 and 30).
- Z22: a two-hop `move` returns after the first hop, and the next `move` prints `ERROR already_queued` though the party does arrive (r7b-quests, r7b-full).
- Z23: many typed fight lines answer "the table said nothing" and resolve a few seconds later (r7b-typed).
- Z24: a chained `levelup` call hung for one hero; a direct call worked at once (r7b-quests 830-838).

## Spend
logs/llm.jsonl lines 5770-6817: **1,048 DeepSeek calls** (568 quality deepseek-v4-pro, 480 fast deepseek-flash),
3.57M prompt and 0.18M completion tokens, 47 `invalid` outcomes (retried).
127 of them (67 quality, 60 fast) were the dropped first start. The plan expected about 1,000. The round-7 approval is used up.
