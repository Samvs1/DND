// Story feed: narration paragraphs (one per narration id, a span per sentence, tone class), mechanical
// event lines and the epilogue. Inside a paragraph an engine statement (`line`) sits on its own line and an
// NPC's spoken words read once as `Name: "..."` (one speech block per speaker run; M20.7). A live sentence with audio is revealed when its clip starts playing
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

// The element a sentence's span goes into: the paragraph, or the speaker's quote (opened on their first words).
function slotFor(p, sentence) {
  if (sentence.line || !sentence.speaker) return p;
  const last = p.lastElementChild;
  if (last?.classList.contains('speech') && last.dataset.speaker === sentence.speaker) return last.querySelector('.said');
  const said = h('span', { class: 'said' });
  p.append(h('span', { class: 'speech', 'data-speaker': sentence.speaker, 'data-testid': 'speech' }, h('strong', { class: 'speaker' }, `${sentence.speaker}:`), ' "', said, '"'));
  return said;
}

// An empty span placed for the sentence, and the text it will show (speech has no space before its closing quote).
function placeSentence(p, sentence) {
  const slot = slotFor(p, sentence);
  const span = h('span', { class: sentence.line ? 'sentence line' : 'sentence', 'data-testid': sentence.line ? 'narration-line' : null });
  const text = slot === p ? `${sentence.text} ` : `${slot.childElementCount ? ' ' : ''}${sentence.text}`;
  slot.append(span);
  return { span, text };
}

function narrationNode(item) {
  const p = h('p', { class: `narr tone-${item.tone}`, 'data-id': item.id, 'data-testid': 'narration' });
  for (const sentence of item.sentences) {
    const { span, text } = placeSentence(p, sentence);
    span.textContent = text;
  }
  if (item.done) p.classList.add('done');
  return p;
}

function plainNode(item) {
  if (item.kind === 'event') return h('p', { class: 'event-line', 'data-testid': 'event-line' }, item.text);
  return h('p', { class: 'epilogue', 'data-testid': 'epilogue' }, h('strong', {}, t('table.epilogue')), ' ', item.text);
}

export function mountFeed(root, story, audio = null) {
  const log = h('div', { class: 'feed', role: 'log', 'aria-live': 'off', 'aria-label': t('table.feed'), tabindex: '0', 'data-testid': 'feed' });
  const empty = h('p', { class: 'hint feed-empty' }, t('table.feedEmpty'));
  // The log itself is silent (its text is typed letter by letter); a finished paragraph is read out once.
  const announce = h('p', { class: 'sr-only', role: 'status', 'aria-live': 'polite', 'data-testid': 'narration-live' });
  const typist = createTypist();
  const nodes = new Map();
  root.append(log, announce);

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
      const { span, text } = placeSentence(node, change.sentence);
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
      if (node) {
        typist.after(() => {
          node.classList.remove('typing');
          node.classList.add('done');
          announce.textContent = node.textContent.trim();
        });
      }
    }
  }

  renderAll();
  const stop = story.subscribe(onChange);
  return () => {
    stop();
    typist.stop();
  };
}
