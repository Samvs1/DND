// The manual view: a contents list, a search box and the rendered sections. One view serves both the /manual page
// (TV or laptop) and the phone's full-screen panel. `load()` returns the Markdown text (a promise).
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { parseBlocks, renderBlock, sectionText, toSections } from './markdown.js';

export function createManualView(root, { load }) {
  const body = h('div', { class: 'mn-body', 'data-testid': 'manual-body' });
  const toc = h('nav', { class: 'mn-toc', 'aria-label': t('manual.tocLabel'), 'data-testid': 'manual-toc' });
  const search = h('input', { type: 'search', id: 'manual-search', class: 'mn-search', placeholder: t('manual.searchPlaceholder'), 'data-testid': 'manual-search', autocomplete: 'off' });
  const status = h('p', { class: 'mn-status', role: 'status' });
  const view = h('div', { class: 'mn-view', 'data-testid': 'manual-view' }, h('div', { class: 'mn-side' }, h('label', { for: 'manual-search', class: 'mn-label' }, t('manual.searchLabel')), search, toc), h('div', { class: 'mn-main' }, status, body));
  root.append(view);
  let sections = [];
  let shown = [];

  function renderToc() {
    clear(toc);
    const links = sections.filter((s) => s.level === 2 && shown.includes(s)).map((s) => h('a', { href: `#${s.id}`, class: 'mn-link', 'data-testid': 'manual-toc-link', onclick: (e) => jump(e, s) }, s.title));
    toc.append(h('p', { class: 'mn-label' }, t('manual.tocLabel')), ...links);
  }

  function jump(event, section) {
    event.preventDefault();
    const el = body.querySelector(`[data-section="${section.id}"]`);
    if (el) el.scrollIntoView({ block: 'start' });
  }

  function renderBody() {
    clear(body);
    shown.forEach((s) => body.append(h('section', { class: `mn-section mn-level-${s.level}`, 'data-section': s.id, id: s.id }, ...s.blocks.map(renderBlock))));
    status.textContent = shown.length ? '' : t('manual.noMatch');
  }

  function filter() {
    const query = search.value.trim().toLowerCase();
    if (!query) {
      shown = sections;
    } else {
      const hit = (s) => s.id !== 'top' && (s.title.toLowerCase().includes(query) || sectionText(s).includes(query));
      // A main section stays (with its title) while any of its sub-sections matches.
      const groupHit = (i) => sections.slice(i + 1).findIndex((n) => n.level === 2) < 0 ? sections.slice(i + 1).some(hit) : sections.slice(i + 1, i + 1 + sections.slice(i + 1).findIndex((n) => n.level === 2)).some(hit);
      shown = sections.filter((s, i) => hit(s) || (s.level === 2 && groupHit(i)));
    }
    renderToc();
    renderBody();
  }

  async function open() {
    status.textContent = t('manual.loading');
    try {
      sections = toSections(parseBlocks(await load()));
      filter();
    } catch {
      clear(body);
      status.replaceChildren(t('manual.failed'), ' ', h('button', { type: 'button', class: 'btn btn-small', 'data-testid': 'manual-retry', onclick: open }, t('manual.retry')));
    }
  }

  search.addEventListener('input', filter);
  open();
  return () => view.remove();
}
