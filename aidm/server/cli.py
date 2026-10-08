"""`python -m aidm`: parse flags, build the settings from `.env` + environment, run uvicorn (M6.4).

Defaults to `127.0.0.1:8000` (`AIDM_HOST`, `AIDM_PORT`); `--lan` binds 0.0.0.0 and prints the LAN
URL; the lobby shows its QR code from `/api/lan-qr.svg`. `--load` with a missing or damaged save
prints one line and exits with code 2 (QA-14). Console output is ASCII and never shows
environment values.

Public API: `build_parser`, `main`.
"""

import argparse
import io
import sys
from dataclasses import replace
from pathlib import Path

import uvicorn

from aidm.server.app import create_app
from aidm.server.lan import lan_address, lan_url
from aidm.server.settings import ServerSettings, load_env, server_settings_from_env
from aidm.server.tls import ensure_certificate, wanted_hosts
from aidm.session.persistence import CampaignLoadError, CampaignStore

CERTS_DIR = Path("certs")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m aidm",
        description="AI Dungeon Master server (D&D 5e with BG3 rules).",
    )
    parser.add_argument("--host", help="bind address (default AIDM_HOST or 127.0.0.1)")
    parser.add_argument("--port", type=int, help="port (default AIDM_PORT or 8000)")
    parser.add_argument(
        "--lan", action="store_true", help="bind 0.0.0.0, print the LAN URL, serve the lobby QR"
    )
    parser.add_argument(
        "--https", action="store_true", help="serve https with a self-signed certificate (certs/)"
    )
    parser.add_argument("--saves", type=Path, help="saves folder (default ./saves)")
    parser.add_argument("--load", metavar="CAMPAIGN_ID", help="open this saved campaign at start")
    return parser


def _banner(settings: ServerSettings) -> str:
    scheme = "https" if settings.https else "http"
    lines = [f"aidm {settings.version} listening on {scheme}://{settings.host}:{settings.port}/"]
    if settings.https:
        lines.append(
            "https uses a self-signed certificate: each browser warns once; "
            "choose Advanced, then Continue to the site."
        )
    if settings.lan_url is not None:
        note = "self-signed TLS" if settings.https else "no TLS"
        lines.append(f"LAN URL: {settings.lan_url} ({note}, trusted networks only)")
    elif settings.lan:
        lines.append("LAN URL: not found (no network address detected)")
    return "\n".join(lines)


def _loadable(saves: Path, campaign_id: str) -> bool:
    """Check `--load` before the server starts: a friendly ASCII line, never a traceback."""
    try:
        CampaignStore(saves).load(campaign_id)
    except CampaignLoadError as exc:
        text = f"Cannot load saved campaign {campaign_id!r}: {exc}"
        print(text.encode("ascii", "replace").decode("ascii"), file=sys.stderr, flush=True)
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    settings = server_settings_from_env(
        load_env(), lan=args.lan, host=args.host, port=args.port, saves_dir=args.saves
    )
    settings = replace(settings, https=args.https)
    if settings.lan:
        settings = replace(settings, lan_url=lan_url(settings.port, args.https))
    if args.load is not None and not _loadable(settings.saves_dir, args.load):
        return 2
    print(_banner(settings), flush=True)
    app = create_app(settings, campaign_id=args.load)
    certfile: str | None = None
    keyfile: str | None = None
    if settings.https:
        cert, key = ensure_certificate(CERTS_DIR, wanted_hosts(lan_address()))
        certfile, keyfile = str(cert), str(key)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
        ssl_certfile=certfile,
        ssl_keyfile=keyfile,
    )
    return 0
