// The story log: narration, mechanical event lines, epilogue and dice rolls, collected from the moment
// the socket opens (before the table view mounts) so a view can render the whole feed when it appears.
// Views read `items` / `dice` and subscribe to live changes: {type: 'item' | 'chunk' | 'done' | 'dice' | 'reset'}.

const MAX_ITEMS = 400;
const MAX_DICE = 12;
// Only outcomes the players should read in the feed. Setup lines (cast introductions, campaign
// install, facts, summaries) are never shown: the server sends them to every seat.
const FEED_EVENTS = new Set([
  'attack_rolled',
  'check_resolved',
  'damage_taken',
  'creature_died',
  'death_save_rolled',
  'stabilized',
  'spell_cast',
  'condition_applied',
  'condition_removed',
  'party_moved',
  'quest_updated',
  'level_gained',
  'xp_gained',
  'gold_changed',
  'reward_granted',
  'short_rest_taken',
  'long_rest_taken',
  'items_traded',
  'secret_revealed',
  'encounter_started',
  'encounter_ended',
]);

export function createStory(store) {
  let items = [];
  let dice = [];
  const byId = new Map();
  const seenSeq = new Set();
  const listeners = new Set();

  function emit(change) {
    for (const fn of [...listeners]) fn(change);
  }

  function push(item) {
    items.push(item);
    if (items.length > MAX_ITEMS) items = items.slice(-MAX_ITEMS);
    emit({ type: 'item', item });
  }

  function onChunk(msg) {
    let item = byId.get(msg.id);
    if (!item) {
      item = { kind: 'narration', id: msg.id, tone: msg.tone || 'exploration', sentences: [], done: false };
      byId.set(msg.id, item);
      push(item);
    }
    const sentence = { index: msg.index, text: msg.text, audio: msg.audio_url || null };
    item.sentences.push(sentence);
    emit({ type: 'chunk', item, sentence });
  }

  function onDone(msg) {
    const item = byId.get(msg.id);
    if (!item) return;
    item.done = true;
    emit({ type: 'done', item });
  }

  function onEvent(msg) {
    if (!msg.line || !FEED_EVENTS.has(msg.kind) || seenSeq.has(msg.seq)) return;
    seenSeq.add(msg.seq);
    push({ kind: 'event', seq: msg.seq, text: msg.line, eventKind: msg.kind });
  }

  function onDice(msg) {
    const roll = { seq: msg.seq, ...msg.dice, at: Date.now() };
    dice = [roll, ...dice].slice(0, MAX_DICE);
    emit({ type: 'dice', roll });
  }

  function reset() {
    items = [];
    dice = [];
    byId.clear();
    seenSeq.clear();
    emit({ type: 'reset' });
  }

  store.on('narration_chunk', onChunk);
  store.on('narration_done', onDone);
  store.on('event', onEvent);
  store.on('dice_roll', onDice);
  store.on('epilogue', (msg) => push({ kind: 'epilogue', text: msg.text }));
  store.on('reset', reset);

  return {
    get items() {
      return items;
    },
    get dice() {
      return dice;
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
}
