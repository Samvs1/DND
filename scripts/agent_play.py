"""Text harness for AI playtesters (M29.3, docs/next/GOAL_BALANCE.md "Layer 2").

    python scripts/agent_play.py new [--shape classic|martial|casters|solo|duo|fighter,cleric]
        [--live] [--seed N] [--port 8101] [--run NAME]
    python scripts/agent_play.py look
    python scripts/agent_play.py act "I ask the innkeeper about the beacon"
    python scripts/agent_play.py do attack 1 | dodge | dash | disengage | end | cast <spell> [foe#]
        | use <use_id> [foe#]
    python scripts/agent_play.py move <place or zone>
    python scripts/agent_play.py answer <fight|surprise|escape|parley|yes|no|confirm|cancel|id>
    python scripts/agent_play.py levelup
    python scripts/agent_play.py stop

`new` starts a background server on its own port (default 8101, never 8000) with a fresh
campaign under `saves/playtests/<run>/` and seats the heroes; later commands reconnect to it
(the run is the last `new`, or `--run NAME` / $AIDM_AGENT_RUN). `--as NAME` picks the hero (in a
fight the hero whose turn it is acts). `--live` uses the real DeepSeek model through the one
LLM client and the key in .env (never printed); without it the deterministic fake storyteller
answers. Every output ends with `[save <campaign id> | event <n>]` for bug reports.
"""

import argparse
import asyncio
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_PORT = 8101
DEFAULT_ROOT = ROOT / "saves" / "playtests"


def _common(default: object) -> argparse.ArgumentParser:
    """--root/--run/--as, accepted before or after the command (`default` hides the copy)."""
    parser = argparse.ArgumentParser(add_help=False)
    root = DEFAULT_ROOT if default is None else default
    parser.add_argument("--root", type=Path, default=root, help="runs folder")
    parser.add_argument("--run", default=default, help="run name (default: the last `new`)")
    parser.add_argument("--as", dest="as_name", default=default, help="hero name to act as")
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Drive an aidm game one command at a time.", parents=[_common(None)]
    )
    hidden = [_common(argparse.SUPPRESS)]
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new", parents=hidden, help="start a campaign and its server")
    new.add_argument("--shape", default="classic")
    new.add_argument("--live", action="store_true", help="real DeepSeek storyteller")
    new.add_argument("--seed", type=int, default=1)
    new.add_argument("--port", type=int, default=DEFAULT_PORT)
    for name in ("look", "stop", "levelup", "serve"):
        sub.add_parser(name, parents=hidden)
    sub.add_parser("act", parents=hidden).add_argument("text", nargs="+")
    for name in ("do", "answer"):
        sub.add_parser(name, parents=hidden).add_argument("words", nargs="+")
    sub.add_parser("move", parents=hidden).add_argument("where", nargs="+")
    return parser


async def dispatch(args: argparse.Namespace) -> str:
    from scripts.agent import ops

    root, run, who = args.root, args.run, args.as_name
    match args.command:
        case "new":
            return await ops.cmd_new(root, run, args.shape, args.seed, args.live, args.port)
        case "look":
            return await ops.cmd_look(root, run, who)
        case "act":
            return await ops.cmd_act(root, run, who, " ".join(args.text))
        case "do":
            return await ops.cmd_do(root, run, who, args.words)
        case "move":
            return await ops.cmd_move(root, run, who, " ".join(args.where))
        case "answer":
            return await ops.cmd_answer(root, run, who, args.words)
        case "levelup":
            return await ops.cmd_levelup(root, run, who)
        case _:
            return ops.cmd_stop(root, run)


def main(argv: list[str] | None = None) -> int:
    from scripts.agent.session import serve

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        asyncio.run(serve(args.root, args.run))
        return 0
    try:
        text = asyncio.run(dispatch(args))
    except SystemExit as err:
        print(f"ERROR: {err}")
        return 1
    print(text.encode("ascii", "replace").decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
