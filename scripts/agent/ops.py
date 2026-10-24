"""The harness commands: new, look, act, do, move, answer, levelup, stop.

Each returns the text the playtester reads: a short digest of what the table said, then the
`look` view ending in the `[save <id> | event <n>]` footer. Errors a player could make come back
as a plain line (never a traceback); the footer is still printed so a report can point at it.

Public API: `cmd_new`, `cmd_look`, `cmd_act`, `cmd_do`, `cmd_move`, `cmd_answer`, `cmd_levelup`,
`cmd_stop`, `cmd_trade`, `parse_party`.
"""

import random
import time
from pathlib import Path

from scripts.agent.commands import UsageError, answer_message, build_command
from scripts.agent.hero_view import learned, roll_why
from scripts.agent.link import Link, Msg, open_link
from scripts.agent.party import heroes_block
from scripts.agent.session import (
    Session,
    alive,
    current_run,
    run_dir,
    set_current_unless_live,
    start_server,
    stop_server,
)
from scripts.agent.text import digest, foe_list, footer, look_text, no_fight_text
from scripts.agent.trade import (
    keepsake_text,
    match_line,
    open_stock,
    parse_trade,
    shopkeeper_of,
    stock_text,
)
from scripts.sim.levelup import build_choices
from scripts.sim.shapes import NAMES, PRIORITY, SHAPES, main_ability, smart_choices


def parse_party(shape: str) -> list[str]:
    """A named shape (classic, martial, casters, solo, duo) or a comma list of classes."""
    if shape in SHAPES:
        return [cls for _role, cls in SHAPES[shape]]
    classes = [c.strip() for c in shape.split(",") if c.strip()]
    bad = [c for c in classes if c not in PRIORITY]
    if bad or not 1 <= len(classes) <= 4:
        raise SystemExit(
            f"bad party {shape!r}: a shape ({', '.join(SHAPES)}) or 1-4 of {', '.join(PRIORITY)}"
        )
    return classes


async def _seat(session: Session, classes: list[str]) -> Link:
    """Create every hero (the first player is the host); returns the host's open link."""
    host: Link | None = None
    for index, cls in enumerate(classes):
        name = NAMES[index]
        link = await open_link(session, {"name": name})
        rng = random.Random(session.seed * 1000 + index)
        choices = smart_choices(cls, name, rng)
        mark = link.conn.mark()
        await link.conn.send({"type": "create_character", "choices": choices})
        res = await link.conn.wait_for(lambda m: m["type"] == "creation_result", 20.0, mark)
        if not res["ok"]:
            raise SystemExit(f"hero {cls} was refused: {res['errors']}")
        session.players.append(
            {
                "name": name,
                "class": cls,
                "token": link.conn.token,
                "hero_id": f"pc-{link.conn.player_id}",
            }
        )
        if host is None:
            host = link
        else:
            await link.close()
    assert host is not None
    return host


async def cmd_new(root: Path, run: str | None, shape: str, seed: int, live: bool, port: int) -> str:
    classes = parse_party(shape)
    name = run or time.strftime("run-%m%d-%H%M%S")
    session = Session(run=name, port=port, live=live, shape=shape, seed=seed)
    start_server(session, root)
    moved = set_current_unless_live(root, name)
    host = await _seat(session, classes)
    session.save(root)
    mark = host.conn.mark()
    await host.conn.send({"type": "host_start"})
    wait = 300.0 if live else 60.0
    await host.conn.wait_for(lambda m: m["type"] == "narration_done", wait * 3, mark)
    out = digest(await host.settle(mark))
    head = f"New run {name}: {shape} ({'live' if live else 'fake'} storyteller), port {port}."
    if not moved:
        head += f" Another run is live: pass --run {name} to every command for this one."
    try:
        return "\n".join([head, out, _view(host, session.players[0], None)]).strip()
    finally:
        await host.close()


def _pending(link: Link) -> str | None:
    """The hostile-act or travel confirmation the table re-sent to this hero on connect."""
    for m in reversed(link.conn.log):
        if m["type"] == "pending_confirmation" and m.get("player_id") == link.conn.player_id:
            return str(m["prompt"])
    return None


def _view(
    link: Link,
    player: Msg,
    sheet: Msg | None,
    level_up: bool = False,
    extra: list[str] | None = None,
) -> str:
    state = link.state
    pending = _pending(link)
    return look_text(state, link.seq, player["hero_id"], sheet, level_up, pending, extra)


def _player(session: Session, name: str | None, state: Msg) -> Msg:
    if name:
        found = next((p for p in session.players if p["name"].lower() == name.lower()), None)
        if found is None:
            raise SystemExit(
                f"no hero called {name!r}: {', '.join(p['name'] for p in session.players)}"
            )
        return found
    active = (state.get("combat") or {}).get("active_id")
    return next((p for p in session.players if p["hero_id"] == active), session.players[0])


async def _actor(session: Session, name: str | None) -> tuple[Link, Msg]:
    """Open the acting hero's link: `--as`, else whoever's turn it is in a fight, else the host."""
    host = await open_link(session, session.players[0])
    chosen = _player(session, name, host.state)
    if chosen is session.players[0]:
        return host, chosen
    await host.close()
    return await open_link(session, chosen), chosen


def _session(root: Path, run: str | None) -> Session:
    session = Session.load(root, current_run(root, run))
    if not alive(session):
        raise SystemExit(
            f"the server of run {session.run} is not running: use `new` (or `stop` is done)"
        )
    return session


async def _report(link: Link, player: Msg, said: list[Msg], note: str = "") -> str:
    """The digest of `said` plus a view built from a FRESH snapshot (H3: the state after the
    command's events, not the last snapshot this link happened to receive)."""
    fresh = await open_link(link.session, player)
    try:
        combat = fresh.state.get("combat")
        got = await fresh.sheet_msg()
        mine = bool(combat and combat.get("active_id") == player["hero_id"])
        sheet = got["sheet"] if got and mine else None
        extra = await heroes_block(link.session, fresh.state)
        if roll := roll_why(fresh.last_roll()):
            extra.append(roll)
        up = bool(got and got.get("level_up"))
        parts = [note, digest(said), _view(fresh, player, sheet, up, extra)]
        return "\n".join(p for p in parts if p).strip()
    finally:
        await fresh.close()


async def cmd_look(root: Path, run: str | None, as_name: str | None) -> str:
    link, player = await _actor(_session(root, run), as_name)
    try:
        asked = await link.what_now() if _has_active_quest(link.state) else []
        return await _report(link, player, asked)
    finally:
        await link.close()


def _has_active_quest(state: Msg) -> bool:
    return any(q.get("state") == "active" for q in state.get("quests", []))


async def cmd_act(root: Path, run: str | None, as_name: str | None, text: str) -> str:
    link, player = await _actor(_session(root, run), as_name)
    try:
        said = await link.send({"type": "submit_action", "text": text})
        note = f"{player['name']} acts: {text[:100]}"
        if not digest(said):
            note += "\n(the table said nothing for this line: no narration, roll or notice)"
        return await _report(link, player, said, note)
    finally:
        await link.close()


async def cmd_do(root: Path, run: str | None, as_name: str | None, words: list[str]) -> str:
    link, player = await _actor(_session(root, run), as_name)
    try:
        combat = link.state.get("combat")
        if not combat:
            return f"{no_fight_text(link.state)}\n{footer(link.state['campaign_id'], link.seq)}"
        foes = foe_list(combat, player["hero_id"])
        try:
            sheet = await link.sheet()
            cmd = build_command(words, player["hero_id"], foes, sheet, combat)
        except UsageError as err:
            return f"{err}\n{await _report(link, player, [])}"
        said = await link.command(cmd)
        note = f"{player['name']} does: {' '.join(words)}"
        if words[0].lower() == "flee" and not _refused(said):
            note += f"\n{player['name']} fled: left the fight and the zone."
        return await _report(link, player, said, note)
    finally:
        await link.close()


def _refused(said: list[Msg]) -> bool:
    return any(m["type"] == "error" for m in said)


async def cmd_move(root: Path, run: str | None, as_name: str | None, where: str) -> str:
    link, player = await _actor(_session(root, run), as_name)
    try:
        if link.state.get("combat"):
            cmd = {"type": "move", "actor_id": player["hero_id"], "zone_id": where}
            said = await link.command(cmd)
        else:
            said = await link.send({"type": "submit_action", "text": f"I travel to {where}"})
        note = "" if _refused(said) else f"{player['name']} moves: {where}"
        return await _report(link, player, said, note)
    finally:
        await link.close()


async def cmd_answer(root: Path, run: str | None, as_name: str | None, words: list[str]) -> str:
    session = _session(root, run)
    link, player = await _actor(session, as_name)
    try:
        try:
            msgs = answer_message(link.state, words, _pending(link))
        except UsageError as err:
            return f"{err}\n{await _report(link, player, [])}"
        said: list[Msg] = []
        defeat = msgs[0]["type"].startswith("defeat_")
        held = await _hold_seats(session, player) if defeat else []
        try:
            for msg in msgs:
                said += await link.send(msg)
                if msg["type"] == "vote" and not as_name:
                    said += await _others_vote(session, player, msg)
        finally:
            for other in held:
                await other.close()
        return await _report(link, player, said, f"{player['name']} answers: {' '.join(words)}")
    finally:
        await link.close()


async def _hold_seats(session: Session, acting: Msg) -> list[Link]:
    """Connect the other heroes while a retry or load rebuilds the table, so they get their
    turns prompted (a reloaded table treats seats nobody holds as away and plays them)."""
    return [await open_link(session, p) for p in session.players if p is not acting]


async def _others_vote(session: Session, first: Msg, msg: Msg) -> list[Msg]:
    said: list[Msg] = []
    for other in session.players:
        if other is first:
            continue
        link = await open_link(session, other)
        try:
            if link.state.get("vote"):
                said += await link.send(msg)
        finally:
            await link.close()
    return said


async def cmd_levelup(root: Path, run: str | None, as_name: str | None) -> str:
    link, player = await _actor(_session(root, run), as_name)
    try:
        sheet_msg = await _level_options(link)
        if sheet_msg is None:
            return f"No level-up is available.\n{await _report(link, player, [])}"
        picks = build_choices(sheet_msg, True, main_ability(player["class"]))
        before = await link.sheet()
        said = await link.send({"type": "level_up", "choices": picks})
        after = await link.sheet()
        note = f"{player['name']} levels up\n{learned(before, after)}".strip()
        return await _report(link, player, said, note)
    finally:
        await link.close()


def _took(picks: Msg) -> str:
    """The level-up choices the harness made for the player, in one line."""
    bits = [f"subclass {picks['subclass']}"] if picks.get("subclass") else []
    if picks.get("asi"):
        bits.append(
            "ability score increase " + ", ".join(f"{k}+{v}" for k, v in picks["asi"].items())
        )
    for key in ("class_choices", "feature_choices"):
        for gid, got in (picks.get(key) or {}).items():
            bits.append(f"{gid} {got}")
    return "; ".join(bits) or "none needed"


async def _level_options(link: Link) -> Msg | None:
    mark = link.conn.mark()
    await link.conn.send({"type": "request_sheet"})
    got = await link.conn.wait_for(lambda m: m["type"] in ("sheet", "error"), 10.0, mark)
    return got.get("level_up") if got["type"] == "sheet" else None


def cmd_stop(root: Path, run: str | None) -> str:
    name = current_run(root, run)
    session = Session.load(root, name)
    result = stop_server(session, root)
    return f"Run {name}: {result}. Save: {run_dir(root, name) / 'saves'}"


async def cmd_trade(root: Path, run: str | None, as_name: str | None, words: list[str]) -> str:
    session = _session(root, run)
    link, player = await _actor(session, as_name)
    try:
        try:
            verb, item, qty = parse_trade(words)
            keeper = shopkeeper_of(link.state)
            stock = await open_stock(session, link, keeper)
            if stock is None:
                late = "The shop stock has not arrived yet (the storyteller is slow): run it again."
                return f"{late}\n{await _report(link, player, [])}"
            said, note = await _trade_step(link, stock, verb, item, qty)
        except UsageError as err:
            return f"{err}\n{await _report(link, player, [])}"
        return await _report(link, player, said, note)
    finally:
        await link.close()


async def _trade_step(
    link: Link, stock: Msg, verb: str, item: str, qty: int
) -> tuple[list[Msg], str]:
    sheet = await link.sheet()
    gold = (sheet or {}).get("gold")
    if verb == "list":
        pack = ", ".join(f"{i['item']} x{i['qty']}" for i in (sheet or {}).get("inventory", []))
        shown = f"{stock_text(stock, gold)}\nYour pack: {pack or 'empty'}"
        return [], f"{shown}\n{keepsake_text(sheet)}"
    npc = stock["npc_id"]
    if verb == "buy":
        line = match_line(stock["stock"], item, "item_id", "name")
        msg: Msg = {"type": "shop_buy", "npc_id": npc, "item_id": line["item_id"], "qty": qty}
    else:
        line = match_line((sheet or {}).get("inventory", []), item, "item", "name")
        msg = {"type": "shop_sell", "npc_id": npc, "item_id": line["item"], "qty": qty}
    return await link.send(msg), f"Trade {verb} {qty} x {item}"


async def cmd_equip(
    root: Path, run: str | None, as_name: str | None, words: list[str], put_on: bool
) -> str:
    """`equip <item>` / `unequip <item>`: the protocol's `equip` and `unequip` messages."""
    link, player = await _actor(_session(root, run), as_name)
    try:
        sheet = await link.sheet()
        try:
            if not words:
                raise UsageError("equip <item> | unequip <item> (an item of your pack)")
            line = match_line((sheet or {}).get("inventory", []), " ".join(words), "item", "name")
        except UsageError as err:
            return f"{err}\n{await _report(link, player, [])}"
        kind = "equip" if put_on else "unequip"
        said = await link.send({"type": kind, "item_id": line["item"]})
        return await _report(link, player, said, f"{player['name']} {kind}s {line['item']}")
    finally:
        await link.close()
