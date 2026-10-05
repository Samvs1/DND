// View registry. To add a view: create views/<name>.js exporting mount<Name>(root, ctx) -> unmount,
// register it here and return its key from pickView().
import { hasHero } from '../state.js';
import { mountLobby } from './lobby.js';
import { mountScreen } from './screen.js';
import { mountTable } from './table.js';
import { mountWizard } from './wizard.js';

export const VIEWS = {
  lobby: mountLobby,
  table: mountTable,
  wizard: mountWizard,
  screen: mountScreen,
};

/** Which view the state calls for. */
export function pickView(state, mode) {
  if (mode === 'screen') return 'screen';
  if (!state.joined || !state.snapshot) return 'lobby';
  const building = state.phase === 'lobby' || state.phase === 'play';
  if (building && (state.wizardOpen ?? !hasHero(state))) return 'wizard';
  return state.phase === 'lobby' || state.phase === 'generating' ? 'lobby' : 'table';
}
