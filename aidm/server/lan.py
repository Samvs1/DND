"""LAN helpers: the address other devices use, and the lobby QR code as inline SVG (SPEC 4).

Public API: `lan_address() -> str | None`, `lan_url(port) -> str | None`, `qr_svg(url) -> bytes`.
"""

import socket
from io import BytesIO

import qrcode
import qrcode.image.svg


def lan_address() -> str | None:
    """The machine's LAN IPv4 address (no packet is sent), or None when there is none."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("10.255.255.255", 1))
        address = str(probe.getsockname()[0])
    except OSError:
        return None
    finally:
        probe.close()
    return None if address.startswith("127.") else address


def lan_url(port: int) -> str | None:
    address = lan_address()
    return f"http://{address}:{port}/" if address is not None else None


def qr_svg(url: str) -> bytes:
    image = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buffer = BytesIO()
    image.save(buffer)
    return buffer.getvalue()
