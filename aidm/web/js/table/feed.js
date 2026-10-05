// Story feed: narration paragraphs (one per narration id, a span per sentence, tone class), mechanical
// event lines and the epilogue. A live sentence with audio is revealed when its clip starts playing
// (`audio.enqueue`); one without is revealed with a typewriter; the
// existing story is rendered at once. Reduced motion reveals everything immediately.
import { reducedMotion, revealMs } from '../settings/model.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

const TICK_MS = 16;
const BACKLOG = 4; // beyond this many queued sentences, reveal at once to catch up
const STICK_PX = 140;

function createTypist() {
  const queue = [];
  let timer = null;

  function step() {
    const job = queue[0];
    if (!job) {
      timer = null;
      return;
    }
    if (job.finish) {
      job.finish();
      queue.shift();
      step();
      return;
    }
    const perTick = Math.max(1, Math.ceil(job.text.length / (revealMs() / TICK_MS)));
    job.pos = Math.min(job.text.length, (job.pos ?? 0) + perTick);
    job.span.textContent = job.text.slice(0, job.pos);
    job.onTick?.();
    if (job.pos >= job.text.length) queue.shift();
    timer = setTimeout(step, TICK_MS);
  }

  function start() {
    if (timer === null) timer = setTimeout(step, TICK_MS);
  }

  return {
    type(span, text, onTick) {
      if (reducedMotion() || revealMs() === 0 || queue.length > BACKLOG) {
        span.textContent = text;
        onTick?.();
        return;
      }
      queue.push({ span, text, onTick });
      start();
    },
    after(fn) {
      if (queue.length === 0) fn();
      else {
        queue.push({ finish: fn });
        start();
      }
    },
    stop() {
      clearTimeout(timer);
      timer = null;
      queue.length = 0;
    },
  };
}

function narrationNode(item) {
  const p = h('p', { class: `narr tone-${item.tone}`, 'data-id': item.id, 'data-testid': 'narration' });
  for (const sentence of item.sentences) p.append(h('span', { class: 'sentence' }, `${sentence.text} `));
  if (item.done) p.classList.add('done');
  return p;
}

function plainNode(item) {
  if (item.kind === 'event') return h('p', { class: 'event-line', 'data-testid': 'event-line' }, item.text);
  return h('p', { class: 'epilogue', 'data-testid': 'epilogue' }, h('strong', {}, t('table.epilogue')), ' ', item.text);
}

export function mountFeed(root, story, audio = null) {
  const log = h('div', { class: 'feed', role: 'log', 'aria-live': 'polite', 'aria-label': t('table.feed'), tabindex: '0', 'data-testid': 'feed' });
  const empty = h('p', { class: 'hint feed-empty' }, t('table.feedEmpty'));
  const typist = createTypist();
  const nodes = new Map();
  root.append(log);

  const nearBottom = () => log.scrollHeight - log.scrollTop - log.clientHeight < STICK_PX;
  const toBottom = () => {
    log.scrollTop = log.scrollHeight;
  };

  function addItem(item, live) {
    empty.remove();
    const stick = nearBottom();
    const node = item.kind === 'narration' ? narrationNode(item) : plainNode(item);
    if (item.kind === 'narration') nodes.set(item.id, node);
    if (live && item.kind === 'narration') node.classList.add('typing');
    log.append(node);
    if (stick) toBottom();
  }

  function renderAll() {
    typist.stop();
    nodes.clear();
    log.replaceChildren();
    if (story.items.length === 0) log.append(empty);
    for (const item of story.items) addItem(item, false);
    toBottom();
  }

  function onChange(change) {
    if (change.type === 'reset' || change.type === 'load') {
      renderAll();
    } else if (change.type === 'item') {
      addItem(change.item, true);
    } else if (change.type === 'chunk') {
      const node = nodes.get(change.item.id);
      if (!node) return;
      const span = h('span', { class: 'sentence' });
      node.append(span);
      const text = `${change.sentence.text} `;
      const reveal = () => {
        const stick = nearBottom();
        span.textContent = text;
        if (stick) toBottom();
      };
      // With audio the text appears when the clip starts; otherwise it is typed at the reading speed.
      if (!audio?.enqueue(change.sentence.audio, reveal)) typist.type(span, text, () => nearBottom() && toBottom());
      toBottom();
    } else if (change.type === 'done') {
      const node = nodes.get(change.item.id);
      if (node) typist.after(() => node.classList.remove('typing') || node.classList.add('done'));
    }
  }

  renderAll();
  const stop = story.subscribe(onChange);
  return () => {
    stop();
    typist.stop();
  };
}
