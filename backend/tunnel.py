"""Best-effort public origin so a WhatsApp tap can reach RecoverPay."""

from __future__ import annotations

import ipaddress
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse

TUNNEL_FILE = Path(__file__).resolve().parent.parent / ".tunnel-url"
_started = False
_lock = threading.Lock()
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _test_mode() -> bool:
    return os.getenv("TEST_MODE", "").strip().lower() in {"1", "true", "yes"}


def is_configured_public_base(url: str) -> bool:
    """True when PUBLIC_BASE_URL is a public http(s) origin (not loopback/LAN)."""
    raw = (url or "").strip()
    if not raw:
        return False
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        return False
    if host in _LOOPBACK_HOSTS or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    except ValueError:
        pass
    return True


def read_tunnel_base() -> str | None:
    if not TUNNEL_FILE.is_file():
        return None
    url = TUNNEL_FILE.read_text(encoding="utf-8").strip().rstrip("/")
    return url or None


def probe_tunnel(base: str) -> bool:
    try:
        import requests

        resp = requests.get(
            f"{base.rstrip('/')}/health",
            timeout=4,
            headers={"Bypass-Tunnel-Reminder": "true"},
        )
        return resp.status_code == 200
    except Exception:
        return False


def ensure_public_tunnel(port: int = 8000) -> None:
    """Start localtunnel in the background when no public PUBLIC_BASE_URL is set."""
    global _started
    if _test_mode():
        return
    env = os.getenv("PUBLIC_BASE_URL", "").strip()
    if is_configured_public_base(env):
        return
    with _lock:
        if _started:
            return
        cached = read_tunnel_base()
        if cached and probe_tunnel(cached):
            _started = True
            print(f"[tunnel] reusing {cached}", file=sys.stderr)
            return
        _started = True
    threading.Thread(target=_spawn_localtunnel, args=(port,), daemon=True).start()


def _spawn_localtunnel(port: int) -> None:
    cmd = f"npx --yes localtunnel --port {int(port)}"
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=True,
        )
    except Exception as exc:
        print(f"[tunnel] localtunnel failed to start: {exc}", file=sys.stderr)
        return
    if proc.stdout is None:
        return
    for line in proc.stdout:
        match = re.search(r"https://[a-zA-Z0-9.-]+\.loca\.lt", line)
        if match:
            url = match.group(0).rstrip("/")
            TUNNEL_FILE.write_text(url + "\n", encoding="utf-8")
            print(f"[tunnel] public origin {url}", file=sys.stderr)
            return
