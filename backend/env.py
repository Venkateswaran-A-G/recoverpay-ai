"""Load local config without committing secrets.

Order (later files do not override already-set values):
1. Process / OS environment (vault, CI, user env) — always wins
2. Gitignored ``.env`` — local live keys for demo
3. ``.env.example`` — placeholders only for missing names
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_LOCAL = _ROOT / ".env"
_EXAMPLE = _ROOT / ".env.example"

try:
    from dotenv import load_dotenv

    if _LOCAL.is_file():
        load_dotenv(_LOCAL, override=False)
    if _EXAMPLE.is_file():
        load_dotenv(_EXAMPLE, override=False)
except ImportError:
    pass
