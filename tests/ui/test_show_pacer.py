"""The presentation queue (M26.5, js/show/pacer.js) on a manual clock: what waits behind a
roll's show, for how long, and what never waits. docs/next/GOAL_DICE.md "Timing (the hard rule)"."""

from typing import Any

from playwright.sync_api import Browser, Page

from tests.ui.conftest import LiveServer

# A pacer with a fake dispatch (it logs [time, type, seq]), a fake store and a manual clock.
# `advance(ms)` runs the due timers in time order and lets promise callbacks settle in between.
HARNESS = """
  window.__aidmShowScale = 1;
  const { createPacer } = await import('/web/js/show/pacer.js');
  const log = [];
  const sent = [];
  let now = 0;
  let next = 1;
  const pending = new Map();
  const timers = {
    set(fn, ms) {
      const id = next++;
      pending.set(id, { at: now + ms, fn });
      return id;
    },
    clear(id) { pending.delete(id); },
  };
  const settle = () => new Promise((r) => setTimeout(r, 0));
  async function advance(ms) {
    const end = now + ms;
    for (;;) {
      await settle();
      let best = null;
      for (const [id, t] of pending) {
        if (t.at <= end && (!best || t.at < best[1].at)) best = [id, t];
      }
      if (!best) break;
      pending.delete(best[0]);
      now = best[1].at;
      best[1].fn();
    }
    await settle();
    now = end;
  }
  let snapshot = null;
  const store = { get: () => ({ snapshot }) };
  const dispatch = (m) => log.push([now, m.type, m.seq ?? null]);
  const pacer = createPacer({ dispatch, store, timers });
  const roll = (seq, dice) => ({
    type: 'dice_roll', seq,
    dice: { rolls: [12], expression: '1d20', adv: 'normal', ...dice },
  });
  const ev = (seq, extra = {}) => ({
    type: 'event', seq, kind: 'check_resolved', line: 'x', ...extra,
  });
  const at = (type, seq) => {
    const hit = log.find((e) => e[1] === type && (seq === undefined || e[2] === seq));
    return hit ? hit[0] : null;
  };
"""


def _run(page: Page, body: str) -> Any:
    return page.evaluate(f"async () => {{ {HARNESS} {body} }}")


def _page(browser: Browser, live_server: LiveServer) -> Page:
    page = browser.new_page()
    page.goto(f"{live_server.base}/play")
    return page


def test_lines_and_narration_wait_for_the_roll_stage(
    browser: Browser, live_server: LiveServer
) -> None:
    page = _page(browser, live_server)
    result = _run(
        page,
        """
        pacer.push(roll(5, { kind: 'check', success: true }));
        pacer.push(ev(6));
        pacer.push({ type: 'narration_chunk', id: 'n1', index: 0, text: 'The guards look away.' });
        await advance(3339);
        const early = log.map((e) => e[1]);
        await advance(1);
        return { early, line: at('event', 6), told: at('narration_chunk') };
        """,
    )
    assert result["early"] == ["dice_roll"]  # nothing spoils the roll before its show ends
    # a roll on an idle table first waits 40 ms for the rest of its burst, then the 3.3 s stage
    assert result["line"] == 3340 and result["told"] == 3340


def test_a_board_attack_and_its_damage_hold_in_turn(
    browser: Browser, live_server: LiveServer
) -> None:
    page = _page(browser, live_server)
    result = _run(
        page,
        """
        snapshot = { state: { combat: { round: 1 } } };
        pacer.push(roll(10, { kind: 'attack', success: true }));
        pacer.push(roll(11, { kind: 'damage', rolls: [4, 5], expression: '1d6+1d6' }));
        pacer.push(ev(12, { kind: 'damage_taken', subject_id: 'gb', amount: 12 }));
        pacer.push({ type: 'combat_state', combat: { round: 1 } });
        await advance(10000);
        return [at('dice_roll', 11), at('event', 12), at('combat_state')];
        """,
    )
    # 40 ms gather; hit 1100 (2 shows wait behind it: 0.7x), damage 600 + 130 (1 waiting), float 500
    assert result == [40 + 770, 40 + 770 + 730, 40 + 770 + 730 + 500]


def test_a_backlog_of_rolls_plays_faster(browser: Browser, live_server: LiveServer) -> None:
    page = _page(browser, live_server)
    times = _run(
        page,
        """
        snapshot = { state: { combat: { round: 1 } } };
        for (let i = 0; i < 5; i++) pacer.push(roll(20 + i, { kind: 'attack', success: false }));
        pacer.push(ev(30));
        await advance(20000);
        return log.map((e) => e[0]);
        """,
    )
    # a miss holds 1300 at full speed; 4 waiting -> 0.5x, 3 and 2 -> 0.7x, then full speed
    assert times == [40, 690, 1600, 2510, 3810, 5110]
    assert times[-1] < 5 * 1300


def test_story_history_flushes_the_queue_at_once(browser: Browser, live_server: LiveServer) -> None:
    page = _page(browser, live_server)
    result = _run(
        page,
        """
        pacer.push(roll(5, { kind: 'check', success: false }));
        pacer.push(ev(6));
        pacer.push({ type: 'story_history', entries: [], dice: [] });
        await advance(0);
        return { line: at('event', 6), history: at('story_history'), busy: pacer.busy() };
        """,
    )
    assert result == {"line": 0, "history": 0, "busy": False}


def test_answers_to_this_device_never_wait(browser: Browser, live_server: LiveServer) -> None:
    page = _page(browser, live_server)
    result = _run(
        page,
        """
        pacer.push(roll(5, { kind: 'check', success: true }));
        pacer.push({ type: 'pong' });
        pacer.push({ type: 'error', code: 'not_your_turn' });
        pacer.push({ type: 'hit_chances', chances: [] });
        pacer.push({ type: 'turn_prompt', creature_id: 'mi', seconds: 180 });
        return [at('pong'), at('error'), at('hit_chances'), at('turn_prompt')];
        """,
    )
    assert result == [0, 0, 0, None]  # the turn prompt is story: it waits for the roll


def test_the_screen_reports_what_it_has_shown(browser: Browser, live_server: LiveServer) -> None:
    page = _page(browser, live_server)
    sent = _run(
        page,
        """
        pacer.bindSend((type, fields) => { sent.push([now, type, fields.seq]); return true; });
        pacer.push(ev(3));
        pacer.push(roll(4, { kind: 'save', success: true }));
        pacer.push(ev(5));
        await advance(1000);
        const mid = sent.length;
        await advance(5000);
        return { mid, sent };
        """,
    )
    assert sent["mid"] == 1  # seq 3 at once; the save is not shown yet
    assert [s[2] for s in sent["sent"]] == [3, 4, 5]
    assert all(s[1] == "presented" for s in sent["sent"])
    assert sent["sent"][1][0] == 40 + 3300


def test_the_director_sets_the_pace_and_can_never_stall_it(
    browser: Browser, live_server: LiveServer
) -> None:
    page = _page(browser, live_server)
    result = _run(
        page,
        """
        pacer.setDirector((msg, { ms }) => msg.seq === 1
          ? new Promise((r) => timers.set(r, 500))
          : new Promise(() => {}));
        pacer.push(roll(1, { kind: 'check', success: true }));
        pacer.push(ev(2));
        pacer.push(roll(3, { kind: 'check', success: true }));
        pacer.push(ev(4));
        await advance(20000);
        pacer.setDirector(() => { throw new Error('broken show'); });
        pacer.push(roll(5, { kind: 'check', success: true }));
        pacer.push(ev(6));
        const before = now;
        await advance(20000);
        return { two: at('event', 2), four: at('event', 4), six: at('event', 6) - before };
        """,
    )
    assert result["two"] == 40 + 500  # the TV's show is the truth
    assert result["four"] == 40 + 500 + 3300 + 2000  # a stuck show is capped
    assert result["six"] == 40 + 3300  # a broken show falls back to the nominal hold


def test_skip_ends_the_show_early(browser: Browser, live_server: LiveServer) -> None:
    page = _page(browser, live_server)
    released = _run(
        page,
        """
        pacer.push(roll(1, { kind: 'check', success: true }));
        pacer.push(ev(2));
        await advance(100);
        pacer.skip();
        await advance(5000);
        return at('event', 2);
        """,
    )
    assert released == 800
