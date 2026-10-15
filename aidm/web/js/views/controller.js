// Phone controller (/play once the adventure runs): a persistent hero strip on top with the five tabs (Play, Hero,
// Journal, Scribe, More) right under it (M18.2: never at the bottom, where a browser toolbar can cover them), an open
// vote and a giver's quest offer (M23.4) as sticky cards at the top of the content, and dialogs for shop, host, settings and the manual. The shared
// story, party and board live on /screen; nothing important is pinned to the bottom of the phone.
import { createController } from '../combat/controller.js';
import { mountDefeatPanel } from '../controller/defeat.js';
import { mountJournalTab } from '../controller/journal.js';
import { mountMore } from '../controller/more.js';
import { mountPlay } from '../controller/play.js';
import { mountScribeTab } from '../controller/scribe.js';
import { mountVictoryPanel } from '../controller/victory.js';
import { mountStrip } from '../controller/strip.js';
import { mountTabs } from '../controller/tabs.js';
import { mountToast } from '../controller/toast.js';
import { mountHostGate } from '../host/gate.js';
import { mountManualPanel } from '../manual/panel.js';
import { mountSettings } from '../settings/settings.js';
import { mountSheet } from '../sheet/drawer.js';
import { mountLevelUp } from '../sheet/levelup.js';
import { mountSheetSync } from '../sheet/sync.js';
import { mountShop } from '../shop/shop.js';
import { mountConfirm, mountOffer } from '../table/dialogs.js';
import { mountNotices } from '../table/notices.js';
import { mountQuestOffer } from '../table/quest_offer.js';
import { mountVote } from '../table/vote.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { TABS } from '../controller/tabs.js';

export function mountController(root, ctx) {
  const { store } = ctx;
  document.body.classList.add('is-controller');
  const strip = h('header', { class: 'ct-strip', 'data-testid': 'strip' });
  const levelSlot = h('div', { class: 'ct-levelup' });
  const notices = h('div', { class: 'ct-notices' });
  const panes = Object.fromEntries(TABS.map((id) => [id, h('section', { class: `ct-pane ct-pane-${id}`, id: `ct-pane-${id}`, role: 'tabpanel', 'aria-labelledby': `ct-tab-${id}`, 'data-testid': `pane-${id}` })]));
  const nav = h('nav', { class: 'ct-tabs', role: 'tablist', 'aria-label': t('ct.tabs'), 'data-testid': 'ct-tabs' });
  const sheetSlot = h('div', { class: 'ct-sheet' });
  const main = h('main', { class: 'ct-main' }, sheetSlot, notices, levelSlot, ...Object.values(panes));
  const toastSlot = h('div', { class: 'ct-toasts' });
  const dialogs = h('div', { class: 'ct-dialogs' });
  root.append(h('div', { class: 'ct', 'data-testid': 'controller' }, strip, nav, main), toastSlot, dialogs);
  const ctrl = createController(ctx);

  const stops = [
    () => ctrl.stop(),
    mountSheetSync(ctx),
    mountStrip(strip, store),
    mountTabs(nav, panes, store),
    ...mountPlay(panes.play, ctx, ctrl),
    mountSheet(panes.hero, ctx, (state) => state.ctab === 'hero'),
    mountJournalTab(panes.journal, ctx),
    mountScribeTab(panes.scribe, ctx, toastSlot),
    mountMore(panes.more, ctx),
    mountNotices(notices, store),
    mountLevelUp(levelSlot, ctx),
    mountVote(sheetSlot, ctx),
    mountQuestOffer(sheetSlot, ctx),
    mountToast(toastSlot, ctx),
    mountConfirm(dialogs, ctx),
    mountOffer(dialogs, ctx),
    mountShop(dialogs, ctx),
    mountHostGate(dialogs, ctx),
    mountSettings(dialogs, ctx),
    mountManualPanel(dialogs, ctx),
    mountDefeatPanel(root, ctx),
    mountVictoryPanel(root, ctx),
  ];
  return () => {
    stops.forEach((stop) => stop());
    document.body.classList.remove('is-controller');
  };
}
