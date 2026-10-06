# Architecture

How `aidm` is put together. `SPEC.md` is the source of truth; this file is the map. Decisions and their
reasons are in [DECISIONS.md](DECISIONS.md) (build and design), [RULES_DECISIONS.md](RULES_DECISIONS.md) (rules
calls where BG3 and the SRD differ or BG3 is unknown) and the wire format is in [PROTOCOL.md](PROTOCOL.md)
(generated).

## Layers and dependency direction

```
  browser (aidm/web: vanilla ES modules, no build step)
        |  websocket JSON (ClientMsg / ServerMsg, generated schema)
  +-----v------------------------------------------------------------+
  | server   FastAPI app, /ws gateway, lobby, /healthz, /tts, assets  |
  | session  table actor, queue, votes, combat flow, reducer, saves   |
  | dm       LLM client, tools, adjudicator, narrator, context, guard |
  | rules    PURE engine: dice, checks, combat, spells, AI, leveling  |
  | models | data   pydantic state/events/commands/protocol | loaders |
  +-------------------------------------------------------------------+
        data/srd (vendored SRD 5.1)      data/bg3 (overlays as JSON)
```

Imports point only downward: `models, data` <- `rules` <- `dm` <- `session` <- `server`. This is enforced
by `import-linter` (`pyproject.toml`: a `layers` contract plus a `forbidden` contract that keeps `openai`,
`httpx`, `fastapi` and the upper layers out of `rules`). `scripts/check_structure.py` adds the size limits
(400 lines per file, 60 per function, no star imports or re-export shims). Both run in the gate.

- `aidm/models`: pydantic v2 only, no logic beyond validators.
- `aidm/data`: loaders and typed registries over `data/srd` and `data/bg3`. No game logic.
- `aidm/rules`: pure. State and inputs in, events out; RNG is injected (`random.Random(seed)`); no I/O, clock or network.
- `aidm/dm`: everything that talks to a model, and the guard that checks what it says.
- `aidm/session`: one actor per table, the reducer, persistence.
- `aidm/server`: transport and hosting only.

Content is data: spells, conditions, features, monsters, items and surfaces are JSON plus one generic
interpreter each (for example the spell effect DSL in `rules/spells.py`). There are no per-spell code branches.

## Event sourcing

All game state is `GameState` (`aidm/models/state.py`). Nothing mutates it directly.

1. Rules and AI tool executors never change state. They return a list of **events** (`aidm/models/events.py`
   and the campaign, world, encounter modules; one discriminated union).
2. The table actor applies each event through `session/reducer.apply(state, event)`, the **only** mutator. It
   is a pure function of `(state, event)` and is deterministic.
3. Every applied event is logged with its sequence number (`seq` = `state.event_count` before the event).
4. **Replay**: `replay(initial, events) == snapshot`. Property tests (hypothesis) and the table tests assert
   it, the simulation asserts it on the live server state, and loading a campaign recomputes it from disk.

Because the log is the truth, a torn snapshot never loses a campaign, and reconnecting clients catch up
from a `last_seq`.

## The turn pipeline (exploration)

```
 player text
    |
 precheck ------> deterministic intents (rest, shop, travel, inventory, look) -> vote / direct events
    |
 adjudicate ----> FAST/QUALITY model calls typed tools (<=5 per round, <=3 rounds)
    |
 execute tools -> executors call rules, return events (validated; errors go back as tool errors)
    |
 apply events --> reducer; dice and mechanics are broadcast immediately
    |
 narrate -------> QUALITY model streams prose from the events and the manifest (or template text offline)
    |
 guard ---------> per sentence: names, dead creatures, destroyed items, features, secrets; one retry, then fallback
    |
 commit --------> NarrationRecorded, memory/summary, autosave, snapshot to all seats
```

"AI proposes, engine disposes": the model can only call tools, the engine decides every number (DC tiers,
severity by party level, XP tiers, item value caps by region tier) and may refuse. A point-of-no-return tool
result (for example attacking a peaceful NPC) pauses for a confirmation from the acting player. In combat the
rules engine runs turns; the model narrates batched round segments (`narrate_round_segment`) and handles
`creative_action` only.

### Closed world, creation tools and the guard

Things exist only after a creation tool registered them (`introduce_npc`, `introduce_feature`, `grant_item`, and the
campaign plan install). `dm/context.py` is the ONE context builder: seven sections in a deterministic order
under a token budget, including the **manifest** (every name and feature that exists in the scene). Unrevealed
secrets are only given to `npc_voice` calls. `dm/guard.py` is the ONE guard: every prose output passes it, and
it rejects unlisted names, dead creatures acting, undestroyed items described as destroyed, unlisted features,
leaked secrets and unearned rewards. A failed check gets one retry with a scrubbed context, then a safe template
line. With no key, or on any model failure, `narration_templates.py` writes from the events, so the game stays
playable (fail soft, never silent, never a raw error to the player).

## The table actor

`session/table.py` runs one asyncio actor per table with two tasks:

- the **inbox** handles read-only and bookkeeping messages immediately (hello, ping, queueing, votes, chat,
  suggestions, hit chances, host routing) and turns every state-changing message into a job;
- the **worker** runs jobs strictly in order and is the only mutator of `GameState`.

So players can queue, vote and chat during a 10 to 45 second model call without racing the state.

- **Queue**: FIFO with one waiting action per player. A fight drops waiting entries with a notice.
- **Votes**: travel, rest and shop open a vote (30 s). The proposer counts as ready; strict majority passes;
  silence abstains; the host can force. A disconnected voter is dropped, solo play passes at once.
- **Combat ownership**: the rules engine decides whose turn it is. Only the owner of the active hero gets a
  `turn_prompt` and may send combat commands; others may suggest. A downed or disconnected hero plays the safe
  default turn; a 90 s turn timer does the same. Monster and ally turns are played by `rules/monster_ai.py`
  and `party_ai.py` through the same command path as players (`CombatRunner`).
- **Timers** go through a `Clock` (`LoopClock`, `ManualClock` in tests), so the actor never sleeps.
- A job that raises is logged and every seat gets an in-fiction notice; the table keeps running.

## Public projection and privacy

The server never sends raw state. `session/views.py` builds the public state per snapshot and
`session/public_feed.py` is THE projection for event lines (live broadcast, seq catch-up and the
`story_history` sent after every hello all go through it; private events are not sent). Monsters show a coarse
health state, NPCs only as `PublicNpcView`, secrets and campaign plan motives never leave the server, and the
simulation asserts that no secret text appears in any received message. `/healthz` returns booleans only.

## Persistence

`session/persistence.py`, `saves/<campaign_id>/` (gitignored): `initial.json` (replay base), `events.jsonl`
(append-only, fsynced), `snapshot.json` and `table.json` (seats and tokens; atomic temp file plus `os.replace`).
Autosave runs after every job. On load the log is replayed and compared with the snapshot; the log wins and a
corrupt snapshot or a torn last line is recovered, never fatal.

## Protocol and codegen

`aidm/models/protocol*.py` define `ClientMsg` and `ServerMsg` as discriminated unions.
`scripts/gen_protocol.py` writes `aidm/web/protocol.json` and `docs/PROTOCOL.md`; `--check` is a gate step, so
the schema cannot drift. A frontend test asserts every `ServerMsg` type has a JS handler. Sockets carry JSON text
frames; malformed, binary or oversized (>64 KB) frames get a typed `error` and the socket stays open.

## Frontend

`aidm/web` is vanilla ES modules with CSS variables and no build step. All UI text is in `js/strings.js`; the
client store plus a handler registry (`handlers.js`) turn server messages into state, and views (lobby, wizard,
table, `/screen`) mount components that read the store. Players never see raw error text: typed refusals map
to friendly strings.

## Assets: manifest and placeholders

Every image and sound is requested by key through ONE server helper `asset_url(key)` and ONE frontend helper
`assetUrl(key)`. `aidm/web/static/assets/manifest.json` (built by `scripts/build_manifest.py` from the data
registries) marks each key `real` (a file exists) or `placeholder`. Placeholders are deterministic SVGs drawn by
`server/placeholders.py` at `/assets/placeholder/<kind>/<slug>.svg`; a missing sound is silence. `ASSETS_TODO.md`
lists what is still missing with generation prompts. A test proves the game runs with all real art hidden.

## TTS pipeline

`server/tts.py` is the one Fish adapter: `synthesize(text, tone) -> Path | None`, lazy SDK import, content-addressed
mp3 cache in `logs/tts_cache`, `None` on any failure (and zero cost when off). `session/narration_pipe.py`
starts synthesis for each streamed sentence at once and sends `narration_chunk`s strictly in order, each held at
most 8 s for its audio, with `audio_url` in the same message. The client plays clips in order and types the text
at reading speed when there is no audio. Music beds crossfade by game state in `js/audio/music.js`; `/screen`
is registered as a spectator (no seat) and becomes the default audio device.

## Testing strategy and gates

- `tests/unit` and `tests/property`: golden values (AC, DCs, slots, HP, spells, monsters) with SRD citations,
  hypothesis invariants (HP bounds, replay equals snapshot, seeded determinism); `rules/` coverage at least 90%.
- `tests/ai`: `FakeLLM` (scripted tool calls, streaming, malformed JSON, truncation, timeouts, hallucinations),
  guard, injection suite, no-key end to end. Never the network.
- `tests/session`: queue, votes, combat ownership, reconnect, kick, pause, persistence, protocol, QA regressions.
- `tests/sim` and `scripts/simulate_party.py`: 3 bot players over real websockets plus chaos probes.
- `tests/ui`: Playwright with `AIDM_FAKE_LLM=1`, two browser contexts, screenshots in `artifacts/ui/`.
- `tests/live`: opt-in (`RUN_LIVE=1`) real DeepSeek and Fish.
- Gate (`scripts/gate.ps1`): pytest, ruff check, ruff format, pyright (strict on `rules` and `models`),
  lint-imports, check_structure, check_secrets, gen_protocol `--check`, build_manifest `--check`,
  gen_assets_todo `--check`. A milestone closes only on a full green gate.
