"""PUBLIC_BASE_URL handling for the optional localtunnel helper."""

from __future__ import annotations

import backend.tunnel as tunnel


def test_http_and_https_public_bases_are_configured():
    assert tunnel.is_configured_public_base("http://example.com") is True
    assert tunnel.is_configured_public_base("https://demo.recoverpay.test") is True
    assert tunnel.is_configured_public_base("http://127.0.0.1:8000") is False
    assert tunnel.is_configured_public_base("https://localhost") is False
    assert tunnel.is_configured_public_base("") is False


def test_ensure_public_tunnel_skips_http_public_base(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "false")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://example.com")
    monkeypatch.setattr(tunnel, "_started", False)
    spawned = {"n": 0}

    class _Thread:
        def __init__(self, *args, **kwargs):
            spawned["n"] += 1

        def start(self):
            return None

    monkeypatch.setattr(tunnel.threading, "Thread", _Thread)
    tunnel.ensure_public_tunnel()
    assert spawned["n"] == 0


def test_ensure_public_tunnel_skips_https_public_base(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "false")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://demo.recoverpay.test")
    monkeypatch.setattr(tunnel, "_started", False)
    spawned = {"n": 0}

    class _Thread:
        def __init__(self, *args, **kwargs):
            spawned["n"] += 1

        def start(self):
            return None

    monkeypatch.setattr(tunnel.threading, "Thread", _Thread)
    tunnel.ensure_public_tunnel()
    assert spawned["n"] == 0
