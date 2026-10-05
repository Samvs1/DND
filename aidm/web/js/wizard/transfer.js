// Hero files (the server's rules/character_io JSON): the import block on the first wizard step
// (import_character -> creation_result) and the export button on the finished sheet
// (export_character -> character_export, saved as a download). Import works in the lobby only.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

function errorTexts(errors) {
  const texts = new Set();
  for (const error of errors) {
    const text = t(`wzErr.${error.code}`);
    texts.add(text === `wzErr.${error.code}` ? t('wzErr.generic') : text);
  }
  return [...texts];
}

export function importBlock(env) {
  const { importState, importHero } = env;
  const input = h('input', { type: 'file', accept: '.json,application/json', class: 'sr-only', tabindex: '-1', 'data-testid': 'import-file' });
  input.addEventListener('change', async () => {
    const file = input.files?.[0];
    input.value = '';
    if (file) importHero(await file.text());
  });
  const busy = importState.status === 'sending';
  const errors = importState.errors.length
    ? h('div', { class: 'wz-errors', role: 'alert', 'data-testid': 'import-errors' }, h('p', {}, t('wz.importFailed')), h('ul', {}, ...errorTexts(importState.errors).map((x) => h('li', {}, x))))
    : null;
  return h(
    'div',
    { class: 'wz-import', 'data-testid': 'import-block' },
    h('button', { type: 'button', class: 'btn btn-small', 'data-testid': 'import-hero', disabled: busy, onclick: () => input.click() }, busy ? t('wz.importing') : t('wz.importHero')),
    h('span', { class: 'hint' }, t('wz.importHint')),
    input,
    errors,
  );
}

export function exportButton(env) {
  return h('button', { type: 'button', class: 'btn', 'data-testid': 'export-hero', onclick: () => env.send('export_character', {}) }, t('wz.exportHero'));
}

/** Save a character_export message as a .json download. */
export function saveExport(msg) {
  const name = (msg.name || 'hero').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'hero';
  const url = URL.createObjectURL(new Blob([msg.text], { type: 'application/json' }));
  const link = h('a', { href: url, download: `${name}.json`, hidden: true });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
