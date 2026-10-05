// Table view placeholder: the real story feed, party panel and combat view arrive in M7.3-M7.4.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

export function mountTable(root) {
  root.append(h('section', { class: 'panel table-stub' }, h('h1', {}, t('table.heading')), h('p', {}, t('table.soon'))));
  return () => {};
}
