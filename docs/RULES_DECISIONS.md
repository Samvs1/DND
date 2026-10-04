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
