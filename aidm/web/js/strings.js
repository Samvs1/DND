// Every user-visible string of the UI lives here (SPEC 12). Other modules use keys via t().
// Placeholders look like {name}. Never put raw server error text in the UI: map codes to these.

export const STRINGS = {
  app: {
    title: 'AI Dungeon Master',
    tagline: 'A tale told by the table, for the table',
  },
  conn: {
    connecting: 'Reaching the table...',
    down: 'The connection to the table was lost. Trying again.',
    retry: 'Retry now',
  },
  banner: {
    fallback: 'The storyteller lost the thread and is using a plain telling for now.',
    retry: 'Try again',
    dismiss: 'Dismiss',
  },
  errors: {
    generic: 'Something went wrong at the table. Please try again.',
    not_joined: 'Join the table first.',
    not_host: 'Only the host can do that.',
    wrong_phase: 'That is not possible right now.',
    no_character: 'Create your character first.',
    not_your_turn: 'It is not your turn.',
    already_queued: 'You already have an action waiting.',
    refused: 'The table did not allow that.',
    invalid: 'That did not look right. Please check and try again.',
    unknown_target: 'That target is not here.',
    no_vote: 'There is nothing to vote on.',
    paused: 'The table is paused.',
  },
  join: {
    heading: 'Join the table',
    nameLabel: 'Your name',
    namePlaceholder: 'Wanderer',
    button: 'Join',
    nameRequired: 'Please enter a name.',
  },
  lobby: {
    heading: 'The Lobby',
    roster: 'At the table',
    you: 'you',
    host: 'host',
    away: 'away',
    empty: 'Nobody has joined yet.',
    themeLabel: 'Campaign theme',
    themePlaceholder: 'Surprise me',
    start: 'Start the adventure',
    waitingHost: 'Waiting for the host to start the adventure.',
    generating: 'The world is being forged. This can take a minute.',
    invite: 'Invite friends',
    inviteHint: 'Scan the code or open the address on the same network.',
    localOnly: 'Only this computer can join. Start the server with --lan to invite friends.',
    qrAlt: 'QR code with the address of this table',
    status: 'Table status',
  },
  table: {
    heading: 'The table',
    soon: 'The adventure is under way. The table view arrives with the next update.',
  },
  screen: {
    heading: 'Spectator screen',
    waiting: 'Waiting for the adventure to begin.',
  },
};

/** Look up "a.b.c" and fill {placeholders}. Unknown keys return the key itself (visible in dev). */
export function t(key, params = {}) {
  let node = STRINGS;
  for (const part of key.split('.')) {
    node = node && typeof node === 'object' ? node[part] : undefined;
  }
  if (typeof node !== 'string') return key;
  return node.replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? ''));
}
