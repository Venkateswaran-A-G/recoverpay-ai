"""Placeholder defaults only — live secrets come from the process environment.

``.env`` is never loaded. Copy names from ``.env.example`` into the OS
environment, CI secrets, or a vault. ``override=False`` so a vault/OS value
always wins over placeholder defaults.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLE = _ROOT / ".env.example"

try:
    from dotenv import load_dotenv

    if _EXAMPLE.is_file():
        load_dotenv(_EXAMPLE, override=False)
except ImportError:
    pass
