// Hotbar slot descriptors: attacks (with hit-chance tooltips), standard actions and bonus actions.
// A descriptor is {id, label, sub, art, tip, flags, off (disabled reason), run}; hotbar.js renders them.
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { isEnemy, isLive, percent } from './model.js';

const ATTACK_KEYS = new Set(['main_hand', 'ranged', 'unarmed']);

export function chanceText(chance) {
  if (!chance) return t('hotbar.noTarget');
  if (!chance.in_range) return t('hotbar.outOfRange');
  const parts = [t('hotbar.hitChance', { p: percent(chance.probability) }), t('hotbar.crit', { p: percent(chance.crit_chance) }), t('hotbar.versusAc', { ac: chance.target_ac })];
  parts.push(t(`hotbar.adv_${chance.adv}`));
  if (chance.long_range) parts.push(t('hotbar.longRange'));
  return parts.join('. ');
}

function aimAt(ctrl, steps, build) {
  ctrl.arm({ steps, build });
}

const foe = (token) => isEnemy(token) && isLive(token);
const ally = (me) => (token) => !isEnemy(token) && !token.dead && token.creature_id !== me;

export function attackSlots(ctx) {
  const { ctrl, sheet, econ, me } = ctx;
  const target = ctrl.ui.target;
  const out = [];
  for (const a of sheet?.attacks ?? []) {
    const offhand = a.hand === 'off_hand';
    const can = offhand ? econ.bonus_action : econ.action || econ.attacks_left > 0;
    const chance = target ? ctrl.ui.chances[target]?.[a.hand] : null;
    const attack = (id) => ({ type: 'attack', actor_id: me, target_id: id, option: a.hand });
    out.push({
      id: `attack-${a.hand}`,
      group: offhand ? 'bonus' : 'attacks',
      label: a.name,
      sub: chance ? (chance.in_range ? percent(chance.probability) : t('hotbar.outOfRange')) : t('hotbar.attackLine', { bonus: a.attack_bonus >= 0 ? `+${a.attack_bonus}` : a.attack_bonus, damage: a.damage }),
      adv: chance && chance.in_range ? chance.adv : 'normal',
      art: assetUrl(['item_icon.' + (a.item || a.hand), `item_icon.${a.range_band === 'ranged' ? 'weapon' : 'weapon'}`]),
      tip: `${t(`hotbar.hand_${a.hand}`)}. ${t('hotbar.attackLine', { bonus: a.attack_bonus >= 0 ? `+${a.attack_bonus}` : a.attack_bonus, damage: a.damage })}. ${chanceText(chance)}`,
      off: can ? null : offhand ? 'no_bonus_action' : 'no_action',
      run: () => (target ? ctrl.send(attack(target)) : aimAt(ctrl, [{ need: 'creature', valid: foe, prompt: t('combat.pickTarget') }], (p) => attack(p[0][0]))),
      kind: ATTACK_KEYS.has(a.hand) ? 'attack' : 'bonus',
    });
  }
  return out;
}

function simple(id, type, ctx, extra = {}) {
  const { ctrl, econ, me } = ctx;
  const bonus = Boolean(extra.bonus_action);
  return {
    id: `${bonus ? 'bonus-' : ''}${id}`,
    group: bonus ? 'bonus' : 'moves',
    label: bonus ? t('hotbar.cunning', { name: t(`hotbar.${id}`) }) : t(`hotbar.${id}`),
    tip: t(`hotbar.tip_${id}`),
    off: (bonus ? econ.bonus_action : econ.action) ? null : bonus ? 'no_bonus_action' : 'no_action',
    run: () => ctrl.send({ type, actor_id: me, ...extra }),
  };
}

export function moveSlots(ctx) {
  const { ctrl, econ, me } = ctx;
  const needsAction = econ.action ? null : 'no_action';
  const pick = (id, steps, build, group = 'moves', off = needsAction) => ({ id, group, label: t(`hotbar.${id}`), tip: t(`hotbar.tip_${id}`), off, run: () => aimAt(ctrl, steps, build) });
  return [
    simple('dash', 'dash', ctx),
    simple('disengage', 'disengage', ctx),
    simple('dodge', 'dodge', ctx),
    simple('hide', 'hide', ctx),
    pick('help', [{ need: 'creature', valid: ally(me), prompt: t('combat.pickTarget') }], (p) => ({ type: 'help', actor_id: me, target_id: p[0][0] })),
    pick('throw', [{ need: 'creature', valid: foe, prompt: t('combat.pickTarget') }], (p) => ({ type: 'throw', actor_id: me, target_id: p[0][0] })),
    { id: 'flee', group: 'moves', label: t('hotbar.flee'), tip: t('hotbar.tip_flee'), off: needsAction, run: () => ctrl.send({ type: 'flee', actor_id: me }) },
  ];
}

export function bonusSlots(ctx) {
  const { ctrl, sheet, econ, me } = ctx;
  const noBonus = econ.bonus_action ? null : 'no_bonus_action';
  const out = [
    {
      id: 'shove-prone', group: 'bonus', label: t('hotbar.shoveProne'), tip: t('hotbar.tip_shove'), off: noBonus,
      run: () => aimAt(ctrl, [{ need: 'creature', valid: foe, prompt: t('combat.pickTarget') }], (p) => ({ type: 'shove', actor_id: me, target_id: p[0][0], mode: 'prone' })),
    },
    {
      id: 'shove-push', group: 'bonus', label: t('hotbar.shovePush'), tip: t('hotbar.tip_shove_push'), off: noBonus,
      run: () => aimAt(ctrl, [{ need: 'creature', valid: foe, prompt: t('combat.pickTarget') }, { need: 'zone', prompt: t('combat.pickPush') }], (p) => ({ type: 'shove', actor_id: me, target_id: p[0][0], mode: 'push', to_zone: p[1][0] })),
    },
    {
      id: 'jump', group: 'bonus', label: t('hotbar.jump'), tip: t('hotbar.tip_jump'), off: noBonus,
      run: () => aimAt(ctrl, [{ need: 'zone', prompt: t('combat.pickZone') }], (p) => ({ type: 'jump', actor_id: me, zone_id: p[0][0] })),
    },
  ];
  if ((sheet?.features ?? []).some((f) => f.index === 'cunning-action')) {
    for (const id of ['dash', 'disengage', 'hide']) out.push(simple(id, id, ctx, { bonus_action: true }));
  }
  return out;
}

// Class and race feature actions from the sheet (`feature_actions`): Second Wind, Action Surge, Breath Weapon,
// Turn Undead. Aimed like spells; remaining uses shown under the label; the server validates everything.
function featureOff(f, econ) {
  if (!f.available) return 'ability_spent';
  if (f.economy === 'action') return econ.action ? null : 'no_action';
  if (f.economy === 'bonus_action') return econ.bonus_action ? null : 'no_bonus_action';
  return econ.action ? 'action_unused' : null;
}

function featureTip(f) {
  const parts = [t(`hotbar.econ_${f.economy}`)];
  if (f.heal) parts.push(t('hotbar.tip_heal', { dice: f.heal }));
  else if (f.target_kind === 'area') parts.push(t(f.range_kind === 'self' ? 'hotbar.tip_around' : 'hotbar.tip_aimZone'));
  else if (f.target_kind === 'self') parts.push(t('hotbar.tip_self'));
  else parts.push(t('hotbar.tip_aimTarget'));
  if (f.uses_max != null) parts.push(t('hotbar.usesLeft', { n: f.uses_left, max: f.uses_max }));
  return parts.join('. ');
}

export function featureSlots(ctx) {
  const { ctrl, sheet, econ, me } = ctx;
  return (sheet?.feature_actions ?? []).map((f) => {
    const command = (extra) => ({ type: 'feature_action', actor_id: me, feature_id: f.feature, ...extra });
    const zone = (f.target_kind === 'area' && f.range_kind !== 'self') || f.target_kind === 'point';
    const creature = f.target_kind === 'creature' || f.target_kind === 'creatures';
    let run = () => ctrl.send(command({}));
    if (zone) run = () => aimAt(ctrl, [{ need: 'zone', prompt: t('combat.pickZone') }], (p) => command({ target_zone: p[0][0] }));
    else if (creature) run = () => aimAt(ctrl, [{ need: 'creature', valid: (tk) => !tk.dead, prompt: t('combat.pickTarget') }], (p) => command({ target_ids: p[0] }));
    return {
      id: `feat-${f.feature}`,
      group: 'features',
      label: f.name,
      sub: f.uses_max != null ? t('hotbar.usesLeft', { n: f.uses_left, max: f.uses_max }) : null,
      tip: featureTip(f),
      off: featureOff(f, econ),
      run,
    };
  });
}
