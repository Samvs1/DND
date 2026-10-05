# Rules decisions

Format: one line per decision: `topic | choice | reason` (BG3 rule unsure -> SRD 5.1 used).

M1.3 check crits | ability and skill checks: natural 20 always succeeds, natural 1 always fails (BG3); saving throws compare the total only (SRD 5.1, BG3 save behaviour unsure) | BG3 dice-roll checks auto-pass/fail on 20/1; saves left at SRD
M1.3 DC tiers | trivial 5, easy 10, medium 15, hard 20, very_hard 25, nearly_impossible 30 | SRD 5.1 Typical Difficulty Classes, SPEC 6.3
M1.3 passive | 10 + check bonus (+ situational), +5 advantage, -5 disadvantage | SRD 5.1 Passive Checks
M1.3 AC | best of (worn armor or 10+DEX) and every allowed formula (Unarmored Defense, Mage Armor), + shield + flat bonus; monk formula needs no shield | SRD 5.1: only one base-AC calculation applies, the creature picks the best
M1.3 HP by level | level 1 = hit die max + CON; later levels fixed average (die/2+1) + CON; at least 1 per level; current CON applies to all levels | BG3 uses the fixed average, never rolls; SRD: CON changes retroactively change max HP
M1.3 temp HP | never stack; new temp HP replace old only when higher | SRD 5.1 Temporary Hit Points (BG3 behaves the same)
M1.4 resist+vuln | per packet: negative raw amount -> 0, immunity -> 0, resistance halves (floor), vulnerability doubles; both -> halve then double | SRD 5.1 Damage Resistance and Vulnerability
M1.4 0 HP | PCs (or death_saves=True) fall unconscious (condition source "zero_hp") and dying; NPCs/monsters die unless death_saves=True | SRD 5.1 "Monsters and Death" option the SRD recommends; BG3 same
M1.4 instant death | from above 0: damage left after reaching 0 >= max HP kills; at 0: a single hit >= max HP kills | SRD 5.1 Instant Death and Damage at 0 Hit Points
M1.4 damage at 0 | 1 death save failure, 2 on a crit, stable is lost; damage fully absorbed by temp HP causes no failure | SRD 5.1 Damage at 0 Hit Points (it is the damage that triggers the failure)
M1.4 death saves | DC 10, situational bonus allowed (Bless); nat 20 regains 1 HP and resets counters; nat 1 = 2 failures; 3 successes stable; 3 failures dead | SRD 5.1 Death Saving Throws
M1.4 stabilize | effect (Spare the Dying) or DC 10 Wisdom (Medicine) check; a stable creature stays unconscious at 0 HP; regaining 1 HP after 1d4 hours is not modelled (rests heal) | SRD 5.1 Stabilizing a Creature; time skips go through rests
M1.4 healing | capped at max HP; nothing for the dead; healing from 0 removes the zero_hp unconscious condition and resets death-save state | SRD 5.1 Healing
M1.5 exhaustion | single level = SRD level 1 (disadvantage on ability checks), ends on a long rest | BG3 has no exhaustion; SRD levels 2-6 add bookkeeping with no BG3 counterpart
M1.5 unconscious | no separate prone instance; attacks against have advantage (melee and ranged), melee hits crit | BG3 downed behaviour; SRD ranged-vs-prone disadvantage would cancel the advantage
M1.5 frightened/charmed | the source is assumed in sight; "cannot move closer" and the charmer's social advantage are DM-adjudicated | zones have no line of sight
M1.5 blinded/deafened | sight/hearing-based checks auto-fail by DM adjudication, not data | no perception model in zones
M1.5 combat end | ROUNDS durations expire when combat ends; until_long_rest and until_removed persist | 1-minute effects are combat-scale; v1 wiped every condition (SPEC 13)
M1.5 auto-fail saves | paralyzed/petrified/stunned/unconscious STR and DEX saves still roll for display but fail | SRD 5.1 Conditions
M1.5 concentration | CON save DC max(10, DamageTaken.total // 2) per damage instance (temp-HP-absorbed damage counts); dead or incapacitated ends it with no roll; surprised does not | SRD 5.1 Concentration
M1.5 extras | dodging (SRD Dodge action, until start of own next turn), hidden (SRD unseen attacker), surprised (BG3: no move/action/reaction until the end of its first turn) as non-SRD condition data | M3.2/M3.3 need them
M1.6 short rest | at most 2 between long rests; each living PC regains max_hp // 2 (a 0-HP member wakes) and SHORT_REST resources; no hit dice | BG3 short rest heals half max HP and spends no hit dice; SPEC 7.2 limit 2
M1.6 long rest cost | CAMP_SUPPLY_PER_MEMBER = 10 per living PC (4 members pay 40, the BG3 full-rest cost); refused (RestRefused NOT_ENOUGH_SUPPLIES) when the pool is short; the dead neither pay nor revive | SPEC 7.2 constant per living member, tunable
M1.6 long rest effects | full HP (death-save state reset), temporary HP cleared, all resources restored, ROUNDS and UNTIL_LONG_REST conditions end, concentration ends, short-rest counter resets | SRD 5.1 Long Rest plus BG3 behaviour (temp HP do not survive a long rest)
M2.2 point buy | 27 points, scores 8..15 before racial bonuses, SRD cost table (14 = 7, 15 = 9); underspending is allowed | SRD 5.1 "Variant: Customizing Ability Scores"; BG3 uses the same budget
M2.2 skill overlap | a class or race skill pick that repeats a skill already granted (background, race) is an error, not a free swap | SRD lets you choose a replacement; the wizard just offers the remaining skills, so the result is the same
M2.2 starting gold | 0 gold at creation; class equipment packages and background gear only | SRD offers packages OR gold; backgrounds data carries no gold, shops come in M5.6
M2.2 level-1 spells | cantrips = class level-1 `cantrips_known` from the SRD class list; known/pact casters pick `spells_known` spells of a level they have slots for; a wizard's spellbook holds 6 level-1 wizard spells; prepared spells come from the spellbook (wizard) or the class list (cleric) | SRD 5.1 class Spellcasting features; domain and patron expanded lists are M2.4 hooks
M2.3 pact magic | pact slots are all of the pact level, always cast at that level (a request for another level cannot use them), recharge on short and long rests | SRD 5.1 Pact Magic; BG3 same
M2.3 prepared casters | prepared spells = casting modifier + class level, minimum 1; wizards prepare from the spellbook, clerics from the class list; re-preparation on long rest is Tier 2 | SRD 5.1 Cleric/Wizard Spellcasting; SPEC 7.2
M2.3 spell numbers | save DC = 8 + proficiency bonus + casting modifier; spell attack = proficiency bonus + casting modifier | SRD 5.1 Spellcasting Ability
M2.3 level-up slots | slots already spent stay spent when maxima grow; a pact pool that changes level keeps its spent count | BG3 level-up does not refill slots
M2.4 unsupported features | `fighter-fighting-style-protection`, `uncanny-dodge`, `hunters-prey-giant-killer` (reactions, Tier 2); `channel-divinity-turn-undead`, `destroy-undead-cr-1-2-or-below`, `channel-divinity-preserve-life`, `sculpt-spells`, `breath-weapon` effect (need the M3.4 effect DSL); `hunters-prey-horde-breaker` (needs the M3.3 second-target attack); `relentless-endurance` effect (needs a 0-HP hook; its 1/long-rest resource is seeded); `favored-enemy-1-type`, `natural-explorer-1-terrain-type`, `primeval-awareness`, `second-story-work`, `naturally-stealthy` (exploration benefits the DM adjudicates); `eldritch-invocations`, `pact-boon` (picks are Tier 2) | marked `unsupported` hooks in data/bg3/features.json, never silently ignored; a test checks this list
M2.4 sneak attack | once per turn, finesse or ranged weapon, needs advantage, or a non-incapacitated ally next to the target and no disadvantage; 1d6 at 1, 2d6 at 3, 3d6 at 5 | SRD 5.1 Rogue table; BG3 same
M2.4 expertise | rogue expertise picks two proficient SKILLS (thieves' tools expertise is not offered) | BG3 offers skills only; SRD allows thieves' tools as an alternative
M2.4 fighting styles | Archery +2 ranged attack; Defense +1 AC only while wearing body armor; Dueling +2 damage with a one-handed melee weapon and no other weapon held (a shield is fine); Great Weapon Fighting rerolls damage dice showing 1 or 2 once for two-handed melee; Two-Weapon Fighting adds the ability modifier to the off-hand hit | SRD 5.1 Fighting Style
M2.4 save advantage tags | effects carry tags (condition key, damage type, "magic"); Dwarven Resilience matches "poison"/"poisoned", Fey Ancestry "charmed" (magical sleep immunity not modelled), Brave "frightened", Gnome Cunning "magic" for INT/WIS/CHA saves | SRD 5.1 racial traits; the combat layer supplies the tags
M2.4 lucky | a natural 1 on an attack roll, ability check or saving throw is rerolled once (new roll stands) | SRD 5.1 Halfling Lucky; BG3 same
M2.4 savage attacks | on a melee crit, one extra weapon damage die that is not itself doubled | SRD 5.1 Half-Orc
M2.4 second wind / action surge | Second Wind bonus action heals 1d10 + level, 1 per short rest; Action Surge one extra action, 1 per short rest | SRD 5.1 Fighter; BG3 same
M2.4 arcane recovery | once per long rest (used after a short rest), regain slots whose levels total ceil(level / 2), none of 6th level or higher | SRD 5.1 Wizard
M2.4 domain spells | life domain spells are always prepared, do not count against the prepared limit, and are granted at cleric 1/3/5 | SRD 5.1 Divine Domain
M2.4 patron list | fiend expanded spells are added to the warlock's learnable list (not auto-known) | SRD 5.1 Otherworldly Patron
M2.4 infernal legacy | thaumaturgy at 1; hellish rebuke (as 2nd level) at 3 and darkness at 5, each 1 per long rest, Charisma | SRD 5.1 Tiefling
M2.4 dwarven toughness | +1 maximum HP per character level, applied at creation and every level-up | SRD 5.1 Hill Dwarf
M2.5 XP and cap | XP thresholds 0 / 300 / 900 / 2700 / 6500 (levels 1-5), MAX_LEVEL = 5; XP keeps accumulating past the cap; a level is taken by an explicit level-up with choices, never automatically | SRD 5.1 Character Advancement; BG3 levels up from the character menu
M2.5 level-up HP | max HP = level-1 max + fixed average (die/2 + 1) per later level, all with the CURRENT CON modifier, plus feature HP per level; current HP rises by the same amount (no full heal); a dead or 0-HP character cannot level up | SRD 5.1 Hit Points (fixed value, CON retroactive); BG3 healing on level-up unsure, SRD gives none
M2.5 ASI | at class ASI levels: +2 to one ability or +1 to two, no score above 20; feats are out of scope (Tier 2) | SRD 5.1 Ability Score Improvement
M2.5 spell learning | cantrips and known spells by the class table difference; known and pact casters may swap one known spell per level; wizards add 2 spells of a level they have slots for per level; prepared casters may submit a new prepared list (limit = modifier + level), otherwise keep theirs; long-rest re-preparation stays Tier 2 | SRD 5.1 class Spellcasting; BG3 level-up spell picks
M2.5 scroll copy | no Arcana check and no time cost; 50 gold per spell level (Evocation Savant halves evocation); the scroll is consumed; only wizard-list spells (expanded grants included) of a level the wizard has slots for; cantrips cannot be copied | BG3 copies for gold with no check; SRD Your Spellbook (50 gp per level, needs a slot level)
M2.5 sheet numbers | initiative shows +DEX (BG3 1d4 + DEX); unarmed strike 1 + STR bludgeoning, proficient; finesse uses the better of STR/DEX; a versatile weapon held with no shield and no off-hand weapon uses its two-handed die; the off-hand attack adds no positive modifier without Two-Weapon Fighting | SRD 5.1 Making an Attack, Unarmed Strike, Two-Weapon Fighting
M3.1 zone movement | a hop costs the edge's feet (terrain hop_feet), doubled when ENTERING a difficult zone; moving inside a zone is free; paths are cheapest-cost (Dijkstra, ties by zone id) | SRD 5.1 Difficult Terrain on a zone graph; BG3 has no grid either
M3.1 range bands | one mapping for weapons and spells: range <= 10 ft (melee, touch, self, 10-ft reach) = same zone only; <= 60 ft = 1 hop; > 60 ft = 2 hops (cap); a weapon's long range reaches hops_for_range(long), hops beyond its normal band are at disadvantage (hand crossbow 30/120: 1 hop, 2 at disadvantage) | SPEC 7.3 "same or adjacent zone", plus a far band for long-ranged attacks; reach is Tier 2
M3.1 high ground | attacker on high ground vs a target not on it: +1 advantage source (melee and ranged); ranged attacker below a high-ground target: +1 disadvantage source; same zone: no effect; sources feed combine_adv | SPEC 7.2 (BG3 high ground), expressed as adv/dis counts
M3.1 cover | ranged attacks from ANOTHER zone into a zone with cover: +2 AC (half), +5 AC (three-quarters); melee and same-zone ranged attacks ignore zone cover; the DEX-save bonus of cover is not modelled | SRD 5.1 Cover, simplified to zones
M3.2 monster HP | spawned monsters use the stat block's fixed average `hit_points`, never rolled | SRD 5.1 lists both; fixed keeps budgets predictable (BG3 uses fixed HP)
M3.2 monster defences | SRD resistance/immunity strings name their damage types; "from nonmagical weapons/attacks" qualifiers count fully (party gear at levels 1-5 is mundane), other qualified strings ("damage from spells", "from magic weapons wielded by good creatures") are ignored; listed skill bonuses >= ability mod + 2 x PB become expertise | no magical-weapon flag exists yet; the catalogue (M3.9) can avoid weapon-immune monsters for low levels
M3.2 monster speed | walking speed, or the best other speed (fly, swim, climb, burrow) when there is none | zones have no vertical dimension
M3.2 initiative | 1d4 + DEX modifier per creature (BG3), rolled once; ties: higher DEX score, then creature id | SPEC 7.2; deterministic order
M3.2 surprise | the surprised side gets the data-driven "surprised" condition (no actions, movement or reactions; expires at the end of its first turn), so its first turn is empty; reactions return at its next turn start | SRD 5.1 Surprise with BG3's one-turn skip
M3.2 turn order | dead, removed and withdrawn creatures are skipped; dying and stable PCs keep their turns (death save at the start of each of a dying creature's turns, SRD) | SRD 5.1 Death Saving Throws
M3.2 outcome | standing = alive, HP > 0, not withdrawn; no PARTY-side combatant standing: FLED when a party member fled and is still up, else DEFEAT (party wipe: dead, dying or stable at 0 HP, allied NPCs count as conscious allies); else no HOSTILE standing: VICTORY (dead, at 0 HP, fled or surrendered); NEUTRAL never decides | BG3 game over when the whole party is down
M3.2 kill XP | the XP of every defeated hostile (dead, at 0 HP or surrendered; fled enemies give none) is split evenly, rounded down, among the party-side PCs that are not dead, whatever the ending | SRD 5.1 XP split among participants; BG3 awards per kill
M3.2 encounter budget | thresholds per character level (levels 1-12, standard 5e numbers: SRD 5.1 has no encounter-building table), group multiplier 1/1.5/2/2.5/3/4 by monster count with one step up for parties of <= 2 (top 5) and one step down for >= 6 (bottom 0.5); a list is rejected when its adjusted XP exceeds the party's deadly threshold; pick_monsters adds random fitting candidates up to 8 monsters | standard 5e encounter building as data
M3.3 attack economy | the first attack of a turn spends the action and leaves attacks_per_action - 1 further attacks; the off-hand attack is a bonus action with no prior Attack action needed; Throw is a full action (thrown weapon at its throw range, else an improvised 1d4 bludgeoning STR throw without proficiency; the object is not removed from the inventory) | BG3 action economy; ground items are Tier 2
M3.3 movement | moving to a zone pays the cheapest path; a prone creature stands for half its speed when it moves (moving to its own zone just stands up); Dash adds the current speed (refused at speed 0); Disengage only sets a flag (opportunity attacks are Tier 2) | SRD 5.1 Being Prone, Dash, Disengage
M3.3 jump and shove | Jump: bonus action plus the edge's plain feet of movement to an ADJACENT zone, ignoring difficult terrain, not while prone; Shove: bonus action, same zone, target at most one size larger, target rolls the better of Athletics/Acrobatics first, the shover must beat it (tie fails), success pushes into a zone adjacent to the target or knocks it prone | BG3 bonus-action Shove/Jump on SRD 5.1 Shoving
M3.3 hide and help | Hide (action, or Cunning Action): Stealth vs the highest passive Perception of standing, non-incapacitated opponents (meeting it succeeds); "hidden" ends when the creature attacks. Help (action): an ally in the same zone gets advantage on its next attack or check until the helper's next turn; on an ally at 0 HP it restores 1 HP (BG3 Help revives) | SRD 5.1 Hide/Help with BG3's downed-ally Help
M3.3 attack details | a natural 1 always misses; Lucky rerolls a natural 1 on an attack once; Great Weapon Fighting rerolls each weapon die below 3 once (riders are not rerolled); a melee hit on a paralyzed/unconscious target crits (melee = same zone); kill temp HP (Dark One's Blessing) applies when a hostile drops to 0 | SRD 5.1 features on zone combat
M3.3 potions | drinking or giving a potion (ally in the same zone) is a bonus action; refused without consumption when the target is at full HP or dead | BG3 (SPEC 7.2) and the v1 regression
M3.4 bonus-action spells | BG3 rule: casting a bonus-action spell does not limit the action to a cantrip (the SRD 5.1 restriction is dropped); the casting time only decides which part of the economy is spent | BG3 lets an action spell and a bonus-action spell share a turn
M3.4 area spells | an area covers every creature (allies included, never the caster) in the chosen zone, or the caster's zone for self-ranged cones/lines; one damage roll for all targets, each saves separately | SRD 5.1 Areas of Effect on zones
M3.4 spell targets | Hold Person's humanoid restriction is not enforced (creatures carry no type yet); "creatures" spells may not pick the same creature twice unless darts/beams (`repeat`); Magic Missile darts and Eldritch Blast beams roll separately (each dart is its own damage instance and concentration check) | BG3 rolls per dart; types arrive with the monster catalogue
M3.4 spell durations | rounds-based spell conditions count down at the end of the caster's turns; save-ends conditions repeat the save against the caster's DC at the end of the bearer's turns; a creature incapacitated by a spell loses its own concentration | SRD 5.1 durations on the combat round
M3.4 healing spells | heal dice + spellcasting modifier + feature bonuses (Disciple of Life 2 + the CAST level); cantrip damage scales at character levels 5, 11, 17 | SRD 5.1 Cure Wounds, Life Domain, cantrip scaling
M3.5 cantrip riders | Chill Touch drops the no-healing and undead-disadvantage riders; Acid Splash picks up to two creatures of one zone (no 5-ft adjacency check); Ray of Frost is modelled as two thirds speed until the end of the caster's next turn; Shocking Grasp drops the metal-armor advantage; True Strike gives the caster advantage on the first attack of the next turn (not tied to one target) | SRD 5.1 spell text; the DSL has no such riders
M3.5 level 1 simplifications | Charm Person and Animal Friendship do not check creature type (humanoid, beast, INT 3 or less) and Animal Friendship does not end when the target is harmed; Guiding Bolt gives advantage to ALL attacks against the target until the end of the caster's next turn (SRD: the next attack); Mage Armor is a flat +3 AC (SRD: 13 + DEX when unarmored) and does not check armor; Thunderwave does not push; Hideous Laughter does not give advantage on saves after damage | SRD 5.1 spell text; DSL limits, the DM adjudicates the rest
M3.6 level 2-3 simplifications | Acid Arrow deals only the hit damage (no end-of-next-turn damage, no half damage on a miss); Aid gives temporary HP instead of raising the HP maximum; Blindness/Deafness only blinds; Invisibility ends on the bearer's first attack roll (SRD: also on casting); Slow drops the -2 DEX save penalty and the one-action limit; Hypnotic Pattern lets the target repeat the WIS save each turn instead of waking when damaged; Lightning Bolt hits the caster's zone and the adjacent ones instead of a line; Fear does not make creatures drop items; Lesser Restoration does not cure disease | SRD 5.1 spell text; DSL limits, the DM adjudicates the rest
M3.6 shipped count | 40 spells are shipped (9 cantrips, 15 level 1, 10 level 2, 6 level 3), short of the SPEC 7.4 target of 50: the rest of the wizard/cleric/warlock/ranger SRD lists are utility spells or need DSL features that do not exist yet (HP-pool targeting, negative dice, damage-rider conditions, heal-from-damage, surfaces, speed above 1x, check dice, raising the dead); see the unsupported list | SPEC 7.4 forbids approximating those; hard-engineer decides which DSL features to add
M3.7 surface numbers | fire 1d4 fire on entering or starting a turn, 3 rounds; grease DEX save or prone (create, enter, turn start), 1 minute; ice DEX DC 10 or prone; poison cloud CON save or 1d6 poison and poisoned for 1 round, 3 rounds; oil and water do nothing alone; steam is cosmetic, 2 rounds; environmental save DC 12, spell surfaces use the caster's DC | BG3 surface behaviour with SRD-scale numbers (BG3 exact numbers unsure)
M3.7 surface interactions | fire + oil/grease (placed or fire damage): the slick burns (becomes fire) with a 2d6 fire burst, DEX 12 half; lightning into water: CON 12 or 1d4 lightning and shocked 1 round, the water stays; cold into water: ice; fire (placed or damage) on water or ice: steam; fire on web: the web burns away, 2d4 fire to everyone in it (SRD Web); sleet storm puts out fire; interactions never chain (a created surface does not interact again) | SPEC 7.2 minimum set plus SRD Web
M3.7 surface triggers | only the destination zone of a move, jump or push triggers "enter" harms (zones are abstract), every time it is entered (SRD "first time on a turn" is not tracked); turn-start harms come after the condition ticks and before the death save; durations count down at the start of each new round; spell damage hits the target's zone (and an area spell its zone, even empty) once per zone and damage type, weapon attacks never trigger interactions; surface damage never triggers on-kill features; surface saves use condition advantage only (no feature advantage such as Gnome Cunning) | one generic interpreter; BG3 triggers on enter and turn start
M3.7 obscurement | fog, magical darkness and the cloud spells give "blinded" (own attacks at disadvantage, attacks against at advantage) while the creature is inside, re-applied each turn start and ended on leaving or when the surface goes; Devil's Sight and lightly obscured areas are not modelled | BG3 applies Blinded inside fog and darkness; SRD heavily obscured = effectively blinded
M3.7 web and grease | Grease and Web are zone surfaces: grease saves at turn start (BG3; SRD: end of turn); a webbed creature re-saves DEX at each turn start inside (its escape; SRD: an action STR check) and is freed when the web burns or the concentration ends | BG3 surfaces; DSL keeps one save path

## Unsupported spells (hidden from pickers)
Spells on the wizard, cleric, warlock or ranger SRD lists that the effect DSL cannot express are NOT shipped (SPEC 7.4); `tests/unit/data/test_spell_coverage.py` checks that every in-scope SRD spell is shipped or listed here. Format: `- <srd-index> (L<level>) | reason`.
- dancing-lights (L0) | utility light effect, no combat mechanics
- light (L0) | utility light effect on an object, no combat mechanics
- mage-hand (L0) | utility exploration effect, summons no combat actor
- mending (L0) | utility repair effect, no combat mechanics
- message (L0) | utility communication effect, no combat mechanics
- minor-illusion (L0) | illusion, needs DM adjudication of belief
- prestidigitation (L0) | utility exploration effect, no combat mechanics
- thaumaturgy (L0) | flavour effect, no combat mechanics
- guidance (L0) | adds a die to ability checks; the DSL has attack and save dice only
- resistance (L0) | adds a die to ONE saving throw once; the DSL has no consumed save dice
- spare-the-dying (L0) | needs a stabilise effect on a dying creature (death saves are not a DSL effect)
- alarm (L1) | ritual exploration ward, no combat mechanics
- comprehend-languages (L1) | language utility, no combat mechanics
- create-or-destroy-water (L1) | utility water effect, no combat mechanics
- detect-evil-and-good (L1) | detection utility, DM adjudicated
- detect-magic (L1) | detection utility, DM adjudicated
- detect-poison-and-disease (L1) | detection utility, DM adjudicated
- disguise-self (L1) | illusion, needs DM adjudication
- find-familiar (L1) | summons a persistent companion creature, not a DSL effect
- floating-disk (L1) | summons an object, no combat mechanics
- identify (L1) | 10-minute ritual that reveals item properties, DM adjudicated
- illusory-script (L1) | utility writing effect, no combat mechanics
- purify-food-and-drink (L1) | utility effect, no combat mechanics
- silent-image (L1) | illusion, needs DM adjudication of belief
- speak-with-animals (L1) | social utility, DM adjudicated
- unseen-servant (L1) | summons an object-creature, no DSL effect
- bane (L1) | subtracts a die from attacks and saves; DSL dice cannot be negative
- color-spray (L1) | hit-point-pool targeting (lowest HP first) is not in the DSL
- sleep (L1) | hit-point-pool targeting (lowest HP first) is not in the DSL
- command (L1) | one-word command with several outcomes chosen at cast time; no DSL choice effect
- expeditious-retreat (L1) | bonus-action Dash every turn is a turn-economy grant, not a DSL effect
- feather-fall (L1) | reaction spell (reactions are Tier 2)
- hellish-rebuke (L1) | reaction spell (reactions are Tier 2)
- shield (L1) | reaction spell (reactions are Tier 2)
- fog-cloud (L1) | heavily obscured area needs the surfaces system (M3.7)
- goodberry (L1) | creates consumable items, not a DSL effect
- hunters-mark (L1) | extra damage on the caster's weapon hits against the mark; the DSL has no damage rider condition
- jump (L1) | jump distance bonus, no DSL movement effect
- longstrider (L1) | speed bonus above 1x is not expressible (speed_factor is at most 1)
- protection-from-evil-and-good (L1) | depends on attacker creature types, which creatures do not carry yet
- sanctuary (L1) | redirects attacks and breaks on hostile acts, no DSL effect
- alter-self (L2) | polymorph-style body change, no DSL effect
- animal-messenger (L2) | utility messaging effect, no combat mechanics
- arcane-lock (L2) | object ward, no combat mechanics
- arcanists-magic-aura (L2) | illusion utility, DM adjudicated
- augury (L2) | divination utility, DM adjudicated
- barkskin (L2) | sets a minimum AC of 16; the DSL has only flat AC bonuses
- calm-emotions (L2) | suppresses charm and fear with a choice of outcomes; no DSL choice effect
- continual-flame (L2) | utility light effect, no combat mechanics
- darkness (L2) | heavily obscured area needs the surfaces system (M3.7)
- darkvision (L2) | vision utility, no DSL effect
- detect-thoughts (L2) | divination utility, DM adjudicated
- enhance-ability (L2) | per-ability advantage chosen at cast time; no DSL choice effect
- enlarge-reduce (L2) | size change with a choice of modes and weapon damage dice; no DSL effect
- enthrall (L2) | attention effect on perception checks, DM adjudicated
- find-traps (L2) | detection utility, DM adjudicated
- flaming-sphere (L2) | summons a movable object that burns creatures each turn, not a DSL effect
- gentle-repose (L2) | ritual utility on corpses, no combat mechanics
- gust-of-wind (L2) | line of wind that pushes creatures and moves each turn; no DSL movement effect
- knock (L2) | utility object effect, no combat mechanics
- levitate (L2) | flight and lifting, no DSL movement effect
- locate-animals-or-plants (L2) | detection utility, DM adjudicated
- locate-object (L2) | detection utility, DM adjudicated
- magic-mouth (L2) | utility object effect, no combat mechanics
- magic-weapon (L2) | changes a weapon's attack and damage bonus, which the DSL cannot target
- mirror-image (L2) | illusory duplicates absorb attacks; no DSL effect
- misty-step (L2) | teleports the caster; the DSL has no movement effect
- pass-without-trace (L2) | stealth bonus on checks, DM adjudicated
- prayer-of-healing (L2) | 10-minute casting time (the DSL has action, bonus action and reaction only)
- protection-from-poison (L2) | advantage on one kind of save plus poison resistance; no DSL resistance effect
- ray-of-enfeeblement (L2) | halves the target's STR weapon damage; the DSL has no damage-dealt modifier
- rope-trick (L2) | extradimensional space, no DSL effect
- see-invisibility (L2) | vision utility, no DSL effect
- silence (L2) | area that blocks sound and spellcasting; needs the surfaces system (M3.7)
- spider-climb (L2) | movement utility, no DSL effect
- spike-growth (L2) | area that damages movement; needs the surfaces system (M3.7)
- spiritual-weapon (L2) | summons a weapon that attacks each turn, not a DSL effect
- suggestion (L2) | free-text command to a charmed creature, DM adjudicated
- warding-bond (L2) | shares damage between two creatures; no DSL effect
- zone-of-truth (L2) | area that compels honesty, DM adjudicated
- animate-dead (L3) | summons undead under the caster's control, not a DSL effect
- beacon-of-hope (L3) | grants advantage on WIS saves and max healing in an area; no DSL effect
- bestow-curse (L3) | curse with a choice of effects chosen at cast time; no DSL choice effect
- blink (L3) | random planar shifting each turn, no DSL effect
- clairvoyance (L3) | divination utility, DM adjudicated
- counterspell (L3) | reaction spell (reactions are Tier 2)
- create-food-and-water (L3) | creates consumable items, not a DSL effect
- daylight (L3) | light area needs the surfaces system (M3.7)
- dispel-magic (L3) | ends arbitrary spells; the DSL has no dispel effect
- fly (L3) | flight, no DSL movement effect
- gaseous-form (L3) | form change with a movement mode, no DSL effect
- glyph-of-warding (L3) | 1-hour casting time and a delayed trigger, no DSL effect
- haste (L3) | extra action and doubled speed; the DSL cannot grant actions or speed above 1x
- magic-circle (L3) | wards a zone against creature types, which creatures do not carry yet
- major-image (L3) | illusion, needs DM adjudication of belief
- meld-into-stone (L3) | merges the caster into a stone object, no DSL effect
- nondetection (L3) | divination ward, DM adjudicated
- phantom-steed (L3) | summons a mount, not a DSL effect
- protection-from-energy (L3) | resistance to one damage type chosen at cast time; no DSL resistance effect
- remove-curse (L3) | ends curses, which are not modelled as conditions
- revivify (L3) | returns a dead creature to life; a dead creature is not a valid spell target
- sending (L3) | unlimited-range messaging utility, DM adjudicated
- sleet-storm (L3) | difficult, slippery area; needs the surfaces system (M3.7)
- speak-with-dead (L3) | divination utility, DM adjudicated
- spirit-guardians (L3) | damaging aura that acts on creatures entering or starting a turn in it; needs the surfaces system (M3.7)
- stinking-cloud (L3) | lingering poison cloud with a start-of-turn save; needs the surfaces system (M3.7)
- tiny-hut (L3) | ritual shelter, no combat mechanics
- tongues (L3) | language utility, no combat mechanics
- vampiric-touch (L3) | melee attack that heals the caster for half the damage and repeats each turn; no DSL healing-from-damage
- water-breathing (L3) | environment utility, no DSL effect
- water-walk (L3) | environment utility, no DSL effect
