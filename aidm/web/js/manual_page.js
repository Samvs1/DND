// Entry point of the /manual page: no table connection, just the manual for a TV or a laptop.
import { loadSettings } from './settings/model.js';
import { createManualView } from './manual/view.js';
import { fetchManual } from './manual/source.js';
import { saved } from './state.js';
import { t } from './strings.js';
import { h } from './ui/dom.js';

document.title = t('manual.pageTitle');
loadSettings(saved);
const app = document.getElementById('app');
app.append(h('h1', { class: 'mn-title' }, t('manual.title')));
createManualView(app, { load: fetchManual });
