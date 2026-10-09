// Target chip list for the phone (the board lives on the shared screen). One chip per living creature of the fight
// with name, side colour, health band, conditions, zone and distance, plus the hit chance when the server sent it.
// Tapping a chip does exactly what tapping the token on the board did (`ctrl.pickToken`); the "Move to" list
// does what tapping a zone did (`ctrl.pickZone`). Shown on MY turn only.
import { combatOf, healthState, isEnemy, isLive, isMyTurn, isRough, moveCost, percent, tokenById } from '../combat/model.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';

function distance(combat, mine, token, zone) {
  if (!mine || mine.zone_id === token.zone_id) return t('ct.zoneHere', { zone });
  const feet = moveCost(combat, mine.zone_id, token.zone_id);
  return feet === null ? zone : t('ct.zoneAt', { zone, feet });
}

function chanceLabel(ctrl, token) {
  const set = Object.values(ctrl.ui.chances[token.creature_id] ?? {});
  if (!set.length) return null;
  const best = set.filter((c) => c.in_range).sort((x, y) => y.probability - x.probability)[0];
  return best ? t('ct.targetHit', { p: percent(best.probability) }) : t('hotbar.outOfRange');
}

function chip(token, ctx) {
  const { combat, mine, ctrl, zones } = ctx;
  const foe = isEnemy(token);
  const band = healthState(token);
  const hp = foe ? t(`combat.${band}`) : `${token.hp}/${token.max_hp}`;
  const targeted = ctrl.ui.target === token.creature_id;
  const where = distance(combat, mine, token, zones.get(token.zone_id) ?? '');
  const conds = token.conditions.map(titleCase).join(', ');
  const hit = foe ? chanceLabel(ctrl, token) : null;
  return h(
    'button',
    { type: 'button', class: `ct-target ${foe ? 'foe' : 'ally'} is-${band}${targeted ? ' targeted' : ''}`, 'aria-pressed': targeted ? 'true' : 'false', 'data-testid': 'target-chip', 'data-creature': token.creature_id, 'data-side': token.side, onclick: () => ctrl.pickToken(token) },
    h('strong', { class: 'ct-t-name' }, token.name),
    h('span', { class: 'ct-t-hp', 'data-testid': 'target-hp' }, hp),
    hit ? h('span', { class: 'ct-t-hit', 'data-testid': 'target-hit' }, hit) : null,
    conds ? h('span', { class: 'ct-t-cond' }, conds) : null,
    h('span', { class: 'ct-t-where hint', 'data-testid': 'target-where' }, where),
  );
}

/** Compact facts about a zone for its Move to chip (the same ones the board shows). */
function zoneBadges(zone) {
  const out = [];
  if (zone.cover !== 'none') out.push(t(`combat.cover_${zone.cover}`));
  if (zone.high_ground) out.push(t('combat.highGround'));
  if (isRough(zone)) out.push(t('combat.difficult'));
  for (const s of zone.surfaces) out.push(s.rounds_left ? t('combat.surfaceRounds', { name: titleCase(s.kind), n: s.rounds_left }) : t('combat.surfaceLasting', { name: titleCase(s.kind) }));
  return out;
}

function placeChip(zone, label, { reachable, arming, ctrl }) {
  const facts = zoneBadges(zone);
  const badges = facts.length ? h('span', { class: 'ct-t-badges' }, ...facts.map((f) => h('span', { class: 'ct-zb', 'data-testid': 'zone-badge' }, f))) : null;
  return h('button', { type: 'button', class: 'ct-target place', disabled: !reachable && !arming, 'data-testid': 'zone-chip', 'data-zone': zone.id, onclick: () => ctrl.pickZone(zone) }, h('span', { class: 'ct-t-zone' }, label), badges);
}

function placeList(combat, mine, ctrl, remember) {
  const arming = ctrl.ui.arming?.steps[ctrl.ui.arming.step];
  const list = h('div', { class: 'ct-places' });
  const left = combat.economy?.movement_left ?? Infinity;
  for (const zone of combat.zones) {
    const feet = mine ? moveCost(combat, mine.zone_id, zone.id) : null;
    const reachable = zone.id !== mine?.zone_id && feet !== null && feet <= left;
    const label = zone.id === mine?.zone_id ? t('ct.zoneHere', { zone: zone.name }) : feet === null ? zone.name : t('ct.zoneAt', { zone: zone.name, feet });
    list.append(placeChip(zone, label, { reachable, arming, ctrl }));
  }
  const box = h('details', { class: 'ct-places-box', open: remember.open || arming?.need === 'zone', 'data-testid': 'places' }, h('summary', {}, t('ct.places')), list);
  box.addEventListener('toggle', () => (remember.open = box.open));
  return box;
}

export function mountTargets(root, { store }, ctrl) {
  const box = h('section', { class: 'ct-targets', hidden: true, 'aria-label': t('ct.targets'), 'data-testid': 'targets' });
  root.append(box);
  let last = '';
  const remember = { open: false };

  function render(state) {
    const combat = combatOf(state);
    const show = Boolean(combat) && isMyTurn(state);
    box.hidden = !show;
    if (!show) {
      last = '';
      return;
    }
    const arming = ctrl.ui.arming?.steps[ctrl.ui.arming.step];
    const key = JSON.stringify([combat.tokens, combat.zones, combat.economy, ctrl.ui.target, ctrl.ui.chances, arming?.need]);
    if (key === last) return;
    last = key;
    const mine = tokenById(combat, ctrl.actor());
    const zones = new Map(combat.zones.map((z) => [z.id, z.name]));
    clear(box);
    const live = combat.tokens.filter((tk) => isLive(tk) && tk.creature_id !== ctrl.actor());
    box.append(h('h3', { class: 'side-h' }, t('ct.targets')), h('div', { class: 'ct-target-list' }, ...live.map((tk) => chip(tk, { combat, mine, ctrl, zones }))), placeList(combat, mine, ctrl, remember));
  }
  render(store.get());
  const stopStore = store.subscribe(render);
  const stopCtrl = ctrl.subscribe(() => render(store.get()));
  return () => {
    stopStore();
    stopCtrl();
  };
}
