"""--https (M11.6): certificate creation and reuse, https LAN URL and QR, boot check over TLS."""

import datetime as dt
import os
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from unittest.mock import patch

from cryptography import x509

from aidm.server import lan
from aidm.server.cli import _banner, build_parser
from aidm.server.settings import ServerSettings
from aidm.server.tls import CERT_NAME, KEY_NAME, ensure_certificate, wanted_hosts

HOSTS = ["localhost", "127.0.0.1", "192.168.1.20"]


def _cert(path: Path) -> x509.Certificate:
    return x509.load_pem_x509_certificate(path.read_bytes())


def test_cert_is_created_with_the_wanted_names(tmp_path: Path) -> None:
    cert_path, key_path = ensure_certificate(tmp_path / "certs", HOSTS)
    assert cert_path.name == CERT_NAME and key_path.name == KEY_NAME
    san = _cert(cert_path).extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert san.get_values_for_type(x509.DNSName) == ["localhost"]
    assert sorted(str(ip) for ip in san.get_values_for_type(x509.IPAddress)) == [
        "127.0.0.1",
        "192.168.1.20",
    ]
    assert not list((tmp_path / "certs").glob("*.tmp"))


def test_cert_is_reused_while_names_match_and_replaced_when_they_change(tmp_path: Path) -> None:
    first, _ = ensure_certificate(tmp_path, HOSTS)
    serial = _cert(first).serial_number
    again, _ = ensure_certificate(tmp_path, list(reversed(HOSTS)))
    assert _cert(again).serial_number == serial
    changed, _ = ensure_certificate(tmp_path, [*HOSTS[:2], "10.0.0.7"])
    assert _cert(changed).serial_number != serial
    assert _cert(changed).not_valid_after_utc > dt.datetime.now(dt.UTC)


def test_garbage_cert_is_replaced(tmp_path: Path) -> None:
    (tmp_path / CERT_NAME).write_text("nope", encoding="ascii")
    (tmp_path / KEY_NAME).write_text("nope", encoding="ascii")
    cert_path, _ = ensure_certificate(tmp_path, HOSTS)
    assert _cert(cert_path).serial_number > 0


def test_wanted_hosts_adds_the_lan_address_once() -> None:
    assert wanted_hosts(None) == ["localhost", "127.0.0.1"]
    assert wanted_hosts("127.0.0.1") == ["localhost", "127.0.0.1"]
    assert wanted_hosts("192.168.1.20") == HOSTS


def test_lan_url_and_qr_use_https() -> None:
    with patch.object(lan, "lan_address", return_value="192.168.1.20"):
        assert lan.lan_url(8000, https=True) == "https://192.168.1.20:8000/"
        assert lan.lan_url(8000) == "http://192.168.1.20:8000/"
    assert lan.qr_svg("https://192.168.1.20:8000/").startswith(b"<?xml")


def test_banner_tells_players_about_the_warning() -> None:
    assert build_parser().parse_args(["--https"]).https is True
    text = _banner(ServerSettings(https=True, lan=True, lan_url="https://192.168.1.20:8000/"))
    assert "listening on https://" in text and "self-signed" in text and "Advanced" in text
    assert "LAN URL: https://192.168.1.20:8000/" in text
    assert text.isascii()


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_boot_check_healthz_over_https(tmp_path: Path) -> None:
    port = _free_port()
    env = {**os.environ, "AIDM_FAKE_LLM": "1"}
    cmd = [sys.executable, "-m", "aidm", "--https", "--port", str(port), "--saves", "saves"]
    proc = subprocess.Popen(
        cmd, cwd=tmp_path, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    body = b""
    try:
        for _ in range(100):
            try:
                url = f"https://127.0.0.1:{port}/healthz"
                with urllib.request.urlopen(url, context=context, timeout=2) as reply:
                    body = reply.read()
                break
            except OSError:
                time.sleep(0.2)
    finally:
        proc.terminate()
        proc.wait(timeout=15)
    assert b'"ok"' in body or b"true" in body
    assert b"PRIVATE KEY" not in body
    assert (tmp_path / "certs" / KEY_NAME).is_file()
