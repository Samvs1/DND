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
