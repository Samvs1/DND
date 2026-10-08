"""Self-signed certificate for `--https` (M11.6): needed so phones get a secure context (mic).

The certificate and key live in `certs/` (gitignored). An existing certificate is reused while it
is still valid for 30 days and its subject alternative names match the wanted hosts; otherwise a
new one is made. Files are written atomically (temp file, then `os.replace`). The key is never
printed or logged.

Public API: `ensure_certificate(certs_dir, hosts) -> tuple[Path, Path]`, `wanted_hosts`.
"""

import datetime as dt
import ipaddress
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

CERT_NAME = "aidm-cert.pem"
KEY_NAME = "aidm-key.pem"
VALID_DAYS = 365
RENEW_MARGIN = dt.timedelta(days=30)


def wanted_hosts(lan_address: str | None) -> list[str]:
    hosts = ["localhost", "127.0.0.1"]
    if lan_address is not None and lan_address not in hosts:
        hosts.append(lan_address)
    return hosts


def _san_entries(hosts: list[str]) -> list[x509.GeneralName]:
    entries: list[x509.GeneralName] = []
    for host in hosts:
        try:
            entries.append(x509.IPAddress(ipaddress.ip_address(host)))
        except ValueError:
            entries.append(x509.DNSName(host))
    return entries


def _cert_hosts(cert: x509.Certificate) -> set[str]:
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    found = {str(name) for name in san.get_values_for_type(x509.DNSName)}
    return found | {str(ip) for ip in san.get_values_for_type(x509.IPAddress)}


def _reusable(cert_path: Path, key_path: Path, hosts: list[str]) -> bool:
    if not (cert_path.is_file() and key_path.is_file()):
        return False
    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        matches = _cert_hosts(cert) == set(hosts)
    except (ValueError, x509.ExtensionNotFound, OSError):
        return False
    expires = cert.not_valid_after_utc
    return matches and expires > dt.datetime.now(dt.UTC) + RENEW_MARGIN


def _atomic_write(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def _make(hosts: list[str]) -> tuple[bytes, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "aidm local")])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=VALID_DAYS))
        .add_extension(x509.SubjectAlternativeName(_san_entries(hosts)), critical=False)
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    return cert.public_bytes(serialization.Encoding.PEM), key_pem


def ensure_certificate(certs_dir: Path, hosts: list[str]) -> tuple[Path, Path]:
    """(certificate path, key path); reuses the saved pair when it still fits `hosts`."""
    cert_path = certs_dir / CERT_NAME
    key_path = certs_dir / KEY_NAME
    if _reusable(cert_path, key_path, hosts):
        return cert_path, key_path
    certs_dir.mkdir(parents=True, exist_ok=True)
    cert_pem, key_pem = _make(hosts)
    _atomic_write(key_path, key_pem)
    _atomic_write(cert_path, cert_pem)
    return cert_path, key_path
