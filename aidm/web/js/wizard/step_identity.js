// Step 9: name, pronouns and a backstory (counter, limit mirrored from the server).
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { BACKSTORY_MAX, NAME_MAX, PRONOUNS_MAX } from './model.js';

const PRESETS = ['she/her', 'he/him', 'they/them'];

export function renderIdentity(env) {
  const { draft, touch } = env;
  const name = h('input', { id: 'hero-name', type: 'text', maxlength: NAME_MAX, value: draft.name, autocomplete: 'off', 'data-testid': 'hero-name' });
  const pronouns = h('input', { id: 'hero-pronouns', type: 'text', maxlength: PRONOUNS_MAX, value: draft.pronouns, list: 'pronoun-presets', 'data-testid': 'hero-pronouns' });
  const story = h('textarea', { id: 'hero-story', rows: 6, maxlength: BACKSTORY_MAX, 'data-testid': 'hero-backstory' }, draft.backstory);
  const count = h('p', { class: 'wz-counter', 'data-testid': 'story-count' }, t('wz.storyCount', { n: draft.backstory.length, max: BACKSTORY_MAX }));
  name.addEventListener('input', () => touch((d) => (d.name = name.value)));
  pronouns.addEventListener('input', () => touch((d) => (d.pronouns = pronouns.value)));
  story.addEventListener('input', () => {
    touch((d) => (d.backstory = story.value));
    count.textContent = t('wz.storyCount', { n: story.value.length, max: BACKSTORY_MAX });
  });
  return h(
    'div',
    { class: 'wz-identity' },
    h('label', { for: 'hero-name' }, t('wz.nameLabel')),
    name,
    h('label', { for: 'hero-pronouns' }, t('wz.pronounsLabel')),
    pronouns,
    h('datalist', { id: 'pronoun-presets' }, ...PRESETS.map((p) => h('option', { value: p }))),
    h('label', { for: 'hero-story' }, t('wz.storyLabel')),
    story,
    count,
  );
}
