// Target chip list for the phone (the board lives on the shared screen). One chip per living creature of the fight
// with name, side colour, health band, conditions, zone and distance, plus the hit chance when the server sent it.
// Tapping a chip does exactly what tapping the token on the board did (`ctrl.pickToken`). Shown on MY turn only.
// The zones to move to are their own list under the Now card (moves.js, M19.4).
import { combatOf, healthState, isEnemy, isLive, isMyTurn, moveCost, percent, tokenById } from '../combat/model.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';
import { zoneDimmed } from '../table/light.js';

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
    foe && zoneDimmed(ctx.zoneOf.get(token.zone_id)) ? h('span', { class: 'ct-zb ct-t-dark', 'data-testid': 'target-dark', title: t('light.darkTarget') }, t('light.dark')) : null,
    h('span', { class: 'ct-t-where hint', 'data-testid': 'target-where' }, where),
  );
}

export function mountTargets(root, { store }, ctrl) {
  const box = h('section', { class: 'ct-targets', hidden: true, 'aria-label': t('ct.targets'), 'data-testid': 'targets' });
  root.append(box);
  let last = '';

  function render(state) {
    const combat = combatOf(state);
    const show = Boolean(combat) && isMyTurn(state);
    box.hidden = !show;
    if (!show) {
      last = '';
      return;
    }
    const key = JSON.stringify([combat.tokens, combat.zones, combat.economy, ctrl.ui.target, ctrl.ui.chances]);
    if (key === last) return;
    last = key;
    const mine = tokenById(combat, ctrl.actor());
    const zones = new Map(combat.zones.map((z) => [z.id, z.name]));
    const zoneOf = new Map(combat.zones.map((z) => [z.id, z]));
    clear(box);
    const live = combat.tokens.filter((tk) => isLive(tk) && tk.creature_id !== ctrl.actor());
    box.append(h('h3', { class: 'side-h' }, t('ct.targets')), h('div', { class: 'ct-target-list' }, ...live.map((tk) => chip(tk, { combat, mine, ctrl, zones, zoneOf }))));
  }
  render(store.get());
  const stopStore = store.subscribe(render);
  const stopCtrl = ctrl.subscribe(() => render(store.get()));
  return () => {
    stopStore();
    stopCtrl();
  };
}
