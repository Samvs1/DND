"""A playtest run on disk and its background server.

`saves/playtests/<run>/` holds `session.json` (port, pid, mode, the seated players and their
tokens), `server.log`, `stop.flag` and the server's own `saves/` folder (the campaign save).
`start_server` launches `agent_play.py serve` detached and waits for its port; `stop_server`
asks it to stop (the table autosaves on shutdown) and kills it only if it ignores that.

Public API: `Session`, `run_dir`, `current_run`, `start_server`, `stop_server`, `serve`, `alive`.
"""

import asyncio
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORT = 8101
_RUN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,40}$")


@dataclass
class Session:
    run: str
    port: int
    live: bool = False
    shape: str = "classic"
    seed: int = 1
    pid: int = 0
    players: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/ws"

    def save(self, root: Path) -> None:
        folder = run_dir(root, self.run)
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / "session.json.tmp"
        tmp.write_text(json.dumps(asdict(self), indent=1), encoding="utf-8")
        os.replace(tmp, folder / "session.json")

    @staticmethod
    def load(root: Path, run: str) -> "Session":
        path = run_dir(root, run) / "session.json"
        if not path.exists():
            raise SystemExit(f"no session {run!r}: run `new` first")
        return Session(**json.loads(path.read_text(encoding="utf-8")))


def run_dir(root: Path, run: str) -> Path:
    if not _RUN_RE.fullmatch(run):
        raise SystemExit(f"bad run name {run!r}: letters, digits, - and _ only")
    return root / run


def current_run(root: Path, given: str | None) -> str:
    """`--run`, else $AIDM_AGENT_RUN, else the run `new` made last (`CURRENT` file)."""
    name = given or os.environ.get("AIDM_AGENT_RUN")
    if name:
        return name
    pointer = root / "CURRENT"
    if pointer.exists():
        return pointer.read_text(encoding="utf-8").strip()
    raise SystemExit("no current run: run `new` first")


def set_current(root: Path, run: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "CURRENT").write_text(run, encoding="utf-8")


def set_current_unless_live(root: Path, run: str) -> bool:
    """Point CURRENT at `run` unless another run's server is live (H5: runs keep their own
    pointer; pass --run). Returns whether the pointer moved."""
    pointer = root / "CURRENT"
    if pointer.exists():
        other = pointer.read_text(encoding="utf-8").strip()
        path = run_dir(root, other) / "session.json" if other and other != run else None
        if path is not None and path.exists() and alive(Session.load(root, other)):
            return False
    set_current(root, run)
    return True


def port_open(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def alive(session: Session) -> bool:
    return session.pid > 0 and port_open(session.port)


def start_server(session: Session, root: Path, wait_s: float = 120.0) -> None:
    """Launch the detached server for `session` and wait until its port answers."""
    if port_open(session.port):
        raise SystemExit(f"port {session.port} is already in use: pick another with --port")
    folder = run_dir(root, session.run)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "stop.flag").unlink(missing_ok=True)
    cmd = [sys.executable, str(ROOT / "scripts" / "agent_play.py"), "serve"]
    cmd += ["--root", str(root), "--run", session.run]
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    with (folder / "server.log").open("ab") as log:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=flags, cwd=ROOT
        )
    session.pid = proc.pid
    session.save(root)
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        if port_open(session.port):
            return
        if proc.poll() is not None:
            raise SystemExit(f"the server exited early; see {folder / 'server.log'}")
        time.sleep(0.3)
    raise SystemExit(f"the server did not start in {wait_s:.0f}s; see {folder / 'server.log'}")


def stop_server(session: Session, root: Path, wait_s: float = 45.0) -> str:
    """Stop the run's server; returns what happened (for the CLI line)."""
    if not alive(session):
        return "server was not running"
    folder = run_dir(root, session.run)
    (folder / "stop.flag").write_text("stop", encoding="utf-8")
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        if not port_open(session.port):
            return "server stopped"
        time.sleep(0.3)
    try:
        os.kill(session.pid, signal.SIGTERM)
    except OSError:
        return "server did not answer and could not be killed"
    return "server killed"


async def serve(root: Path, run: str) -> None:
    """The background server: a `SimServer` (fake or live storyteller) until `stop.flag`."""
    from scripts.sim.server import SimServer  # the one in-process server plumbing

    session = Session.load(root, run)
    folder = run_dir(root, run)
    srv = SimServer(
        session.seed,
        folder / "saves",
        live_ai=session.live,
        port=session.port,
        no_timers=True,
    )
    await srv.start()
    print(f"serving {run} on {session.port} campaign {srv.state.campaign_id}", flush=True)
    flag = folder / "stop.flag"
    while not flag.exists():
        await asyncio.sleep(0.5)
    await srv.stop()
    print("stopped", flush=True)
