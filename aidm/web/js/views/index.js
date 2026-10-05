// View registry. To add a view: create views/<name>.js exporting mount<Name>(root, ctx) -> unmount,
// register it here and return its key from pickView().
import { mountLobby } from './lobby.js';
import { mountScreen } from './screen.js';
import { mountTable } from './table.js';

export const VIEWS = {
  lobby: mountLobby,
  table: mountTable,
  screen: mountScreen,
};

/** Which view the state calls for. */
export function pickView(state, mode) {
  if (mode === 'screen') return 'screen';
  if (!state.joined) return 'lobby';
  return state.phase === 'lobby' || state.phase === 'generating' ? 'lobby' : 'table';
}
