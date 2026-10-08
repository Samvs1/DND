// Voice input (M11.6): a Speak button that fills the action box using the Web Speech API. It exists only
// in a secure context (https or localhost) where SpeechRecognition is available; the player still presses send.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

function recognitionClass() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function micSupported() {
  return window.isSecureContext === true && recognitionClass() !== null;
}

export function createMic(slot, input, say, changed) {
  const button = h('button', { type: 'button', class: 'btn', 'data-testid': 'mic-button', 'aria-pressed': 'false' }, t('ct.micStart'));
  slot.append(button);
  let rec = null;

  function done() {
    rec = null;
    button.textContent = t('ct.micStart');
    button.setAttribute('aria-pressed', 'false');
  }

  function start() {
    const Recognition = recognitionClass();
    try {
      rec = new Recognition();
      rec.lang = document.documentElement.lang || 'en-US';
      rec.interimResults = false;
      rec.onresult = (event) => {
        const text = [...event.results].map((r) => r[0].transcript).join(' ').trim();
        if (!text) return;
        input.value = input.value ? `${input.value.trimEnd()} ${text}` : text;
        changed();
      };
      rec.onerror = () => {
        say(t('ct.micError'));
        done();
      };
      rec.onend = done;
      rec.start();
      button.textContent = t('ct.micStop');
      button.setAttribute('aria-pressed', 'true');
    } catch {
      say(t('ct.micError'));
      done();
    }
  }

  button.addEventListener('click', () => (rec ? rec.stop() : start()));
}
