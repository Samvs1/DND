// A player's typed action in the story feed (M22.1, owner request): the hero's portrait, the player's name,
// the hero's name and their words, so the whole table knows who did what before the telling.
// Items come from story.js ({kind: 'action', text, creatureId, playerName, heroName}); art only through assetUrl.
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { publicState } from './lookup.js';
import { portraitKeys } from './party.js';

const GENERIC = 'portrait.npc.commoner';

/** The hero's name when it differs from the player's (a player who named their hero after themselves reads once). */
function heroLabel(item) {
  const hero = (item.heroName || '').trim();
  return hero && hero.toLowerCase() !== (item.playerName || '').trim().toLowerCase() ? hero : '';
}

/** "Ann (Brienne)" or "Ann": the plain-text speaker of a typed action (the phone's Story view). */
export function actionWho(item) {
  const hero = heroLabel(item);
  return hero ? t('table.actionWhoHero', { player: item.playerName, hero }) : item.playerName;
}

/** The plain-text line of a typed action: Ann (Brienne): "I look inside the cabin". */
export function actionLine(item) {
  return t('table.actionLine', { who: actionWho(item), text: item.text });
}

export function actionCard(item, state, live) {
  const hero = publicState(state)?.party.find((c) => c.id === item.creatureId);
  const art = assetUrl(hero ? portraitKeys(hero) : [GENERIC]);
  const heroName = heroLabel(item);
  return h(
    'div',
    { class: live ? 'act live' : 'act', 'data-creature': item.creatureId, 'data-testid': 'player-action' },
    h('img', { class: 'act-portrait', src: art, alt: '', width: 44, height: 44, 'data-testid': 'player-action-portrait' }),
    h(
      'div',
      { class: 'act-body' },
      h(
        'p',
        { class: 'act-who' },
        h('strong', { class: 'act-player', 'data-testid': 'player-action-name' }, item.playerName),
        heroName ? h('span', { class: 'act-hero' }, ` ${t('table.actionAs', { hero: heroName })}`) : null,
      ),
      h('p', { class: 'act-words', 'data-testid': 'player-action-text' }, item.text),
    ),
  );
}
