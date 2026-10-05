// Combat controller: the ephemeral UI state of a fight (selected target, the action being aimed, hit-chance
// previews, suggestions, the friendly refusal text) and the one place that sends combat messages.
// Views subscribe with `controller.subscribe(fn)`; none of this state is persisted.
import { t } from '../strings.js';
import { combatOf, isEnemy, isLive, isMyTurn, myCreatureId, previewKey, tokenById } from './model.js';

const MESSAGE_MS = 6000;

export function createController({ store, client }) {
  const ui = { target: null, arming: null, chances: {}, suggestions: [], popup: null, message: '', sent: [] };
  const listeners = new Set();
  let lastPreview = '';
  let lastTurn = null;
  let lastRefusal = store.get().refusal?.n ?? 0;
  let messageTimer = null;

  const emit = () => listeners.forEach((fn) => fn(ui));

  function say(text) {
    ui.message = text;
    clearTimeout(messageTimer);
    if (text) messageTimer = setTimeout(() => { ui.message = ''; emit(); }, MESSAGE_MS);
    emit();
  }

  function send(command) {
    ui.arming = null;
    ui.popup = null;
    ui.message = '';
    client.send('combat_command', { command });
    emit();
  }

  function actor() {
    return myCreatureId(store.get());
  }

  /** Aim an action: `steps` are {need: 'creature'|'zone', count?, valid(token)?, prompt}; `build(picks)` returns the command. */
  function arm(spec) {
    ui.popup = null;
    ui.arming = { ...spec, step: 0, picks: spec.steps.map(() => []) };
    ui.message = '';
    emit();
  }

  function finish() {
    const a = ui.arming;
    if (a) send(a.build(a.picks));
  }

  function advance(a) {
    const spec = a.steps[a.step];
    const full = a.picks[a.step].length >= (spec.count ?? 1);
    if (!full) return emit();
    if (a.step + 1 >= a.steps.length) return finish();
    a.step += 1;
    emit();
  }

  function pickToken(token) {
    const a = ui.arming;
    if (!a) {
      if (isEnemy(token) && isLive(token)) selectTarget(token.creature_id);
      return;
    }
    const spec = a.steps[a.step];
    if (spec.need !== 'creature') return;
    if (spec.valid && !spec.valid(token)) return say(t('refusal.invalid_target'));
    a.picks[a.step].push(token.creature_id);
    advance(a);
  }

  function pickZone(zone) {
    const a = ui.arming;
    if (a) {
      const spec = a.steps[a.step];
      if (spec.need !== 'zone') return;
      a.picks[a.step].push(zone.id);
      advance(a);
      return;
    }
    const me = actor();
    if (!me || !isMyTurn(store.get())) return;
    send({ type: 'move', actor_id: me, zone_id: zone.id });
  }

  function doneEarly() {
    const a = ui.arming;
    if (a && a.picks[a.step].length > 0) finish();
  }

  function cancel() {
    if (!ui.arming && !ui.popup) return false;
    ui.arming = null;
    ui.popup = null;
    emit();
    return true;
  }

  function selectTarget(id) {
    ui.target = ui.target === id ? null : id;
    emit();
  }

  function setPopup(name) {
    ui.popup = ui.popup === name ? null : name;
    emit();
  }

  function requestChances(combat) {
    for (const token of combat.tokens) {
      if (isEnemy(token) && isLive(token)) client.send('request_hit_chances', { target_id: token.creature_id });
    }
  }

  function onState(state) {
    const combat = combatOf(state);
    if (!combat) {
      if (ui.target || ui.arming || lastPreview) Object.assign(ui, { target: null, arming: null, popup: null, chances: {}, suggestions: [], sent: [] });
      lastPreview = '';
      lastTurn = null;
      return;
    }
    if (combat.active_id !== lastTurn) {
      lastTurn = combat.active_id;
      Object.assign(ui, { arming: null, popup: null, suggestions: [], sent: [] });
    }
    const target = ui.target && tokenById(combat, ui.target);
    if (!target || !isLive(target)) ui.target = null;
    if (isMyTurn(state)) {
      if (!ui.target) ui.target = defaultTarget(combat);
      const key = previewKey(combat);
      if (key !== lastPreview) {
        lastPreview = key;
        ui.chances = {};
        requestChances(combat);
      }
    } else lastPreview = '';
    const refusal = state.refusal;
    if (refusal && refusal.n !== lastRefusal) {
      lastRefusal = refusal.n;
      const text = t(`refusal.${refusal.code}`);
      say(text === `refusal.${refusal.code}` ? t('refusal.generic') : text);
      return;
    }
    emit();
  }

  function defaultTarget(combat) {
    const me = tokenById(combat, actor());
    const foes = combat.tokens.filter((tk) => isEnemy(tk) && isLive(tk));
    return (foes.find((tk) => me && tk.zone_id === me.zone_id) ?? foes[0])?.creature_id ?? null;
  }

  store.on('hit_chances', (msg) => {
    ui.chances = { ...ui.chances, [msg.target_id]: Object.fromEntries(msg.chances.map((c) => [c.option, c])) };
    emit();
  });
  store.on('suggestion', (msg) => {
    ui.suggestions = [...ui.suggestions, { name: msg.name, text: msg.text }].slice(-4);
    emit();
  });
  store.on('reset', () => Object.assign(ui, { target: null, arming: null, chances: {}, suggestions: [] }));
  const stop = store.subscribe(onState);
  onState(store.get());

  return {
    ui,
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    actor,
    send,
    arm,
    pickToken,
    pickZone,
    doneEarly,
    cancel,
    selectTarget,
    setPopup,
    say,
    suggest(text) {
      if (client.send('suggestion', { text })) {
        ui.sent = [...ui.sent, text].slice(-3);
        emit();
      }
    },
    stop() {
      stop();
      clearTimeout(messageTimer);
    },
  };
}
