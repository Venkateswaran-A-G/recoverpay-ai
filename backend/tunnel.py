"""Best-effort public origin so a WhatsApp tap can reach RecoverPay."""

from __future__ import annotations

import ipaddress
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

TUNNEL_FILE = Path(__file__).resolve().parent.parent / ".tunnel-url"
CLOUDFLARED = Path(__file__).resolve().parent.parent / "tools" / "cloudflared.exe"
_started = False
_lock = threading.Lock()
_tunnel_proc: subprocess.Popen | None = None
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
_CF_RESERVED_SUBS = {"api", "www", "dash", "developers", "one"}


def _test_mode() -> bool:
    return os.getenv("TEST_MODE", "").strip().lower() in {"1", "true", "yes"}


def parse_trycloudflare_origin(text: str) -> str | None:
    """Return a visitor origin, never Cloudflare's own ``api.trycloudflare.com``."""
    for match in re.finditer(r"https://([a-z0-9-]+)\.trycloudflare\.com", text or "", re.I):
        if match.group(1).lower() in _CF_RESERVED_SUBS:
            continue
        return match.group(0).rstrip("/")
    return None


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
        host = (urlparse(cached or "").hostname or "").lower()
        if host == "api.trycloudflare.com" or host.split(".")[0] in _CF_RESERVED_SUBS:
            try:
                TUNNEL_FILE.unlink()
            except OSError:
                pass
            cached = None
            host = ""
        cloudflare_ok = bool(
            cached
            and "trycloudflare.com" in cached
            and host not in {f"{s}.trycloudflare.com" for s in _CF_RESERVED_SUBS}
            and not host.startswith("api.")
            and probe_tunnel(cached)
        )
        loca_ok = bool(cached and "loca.lt" in cached and not CLOUDFLARED.is_file() and probe_tunnel(cached))
        if cloudflare_ok or loca_ok:
            _started = True
            print(f"[tunnel] reusing {cached}", file=sys.stderr)
            return
        _started = True
    threading.Thread(target=_spawn_public_tunnel, args=(port,), daemon=True).start()


def _write_tunnel_url(url: str) -> None:
    TUNNEL_FILE.write_text(url.rstrip("/") + "\n", encoding="utf-8")
    print(f"[tunnel] public origin {url}", file=sys.stderr)


def _spawn_public_tunnel(port: int) -> None:
    if CLOUDFLARED.is_file() and _spawn_cloudflared(port):
        return
    _spawn_localtunnel(port)


def _spawn_cloudflared(port: int) -> bool:
    global _tunnel_proc
    cmd = [
        str(CLOUDFLARED),
        "tunnel",
        "--url",
        f"http://127.0.0.1:{int(port)}",
        "--no-autoupdate",
    ]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:
        print(f"[tunnel] cloudflared failed to start: {exc}", file=sys.stderr)
        return False
    if proc.stdout is None:
        return False
    _tunnel_proc = proc
    found: dict[str, str | None] = {"url": None}

    def _drain() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            origin = parse_trycloudflare_origin(line)
            if origin and found["url"] is None:
                found["url"] = origin
            # Keep reading so cloudflared cannot block on a full pipe.

    threading.Thread(target=_drain, daemon=True).start()
    deadline = time.time() + 25
    while time.time() < deadline:
        if found["url"]:
            origin = found["url"]
            settle = time.time() + 8
            while time.time() < settle and not probe_tunnel(origin):
                time.sleep(0.4)
            _write_tunnel_url(origin)
            return True
        if proc.poll() is not None:
            break
        time.sleep(0.15)
    print("[tunnel] cloudflared exited without a public visitor URL", file=sys.stderr)
    return False


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
            _write_tunnel_url(url)
            return
