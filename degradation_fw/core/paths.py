"""Project paths and a helper for importing vendored third_party code."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
THIRD_PARTY_DIR = PROJECT_ROOT / "third_party"


def use_third_party(name: str) -> Path:
    """Put ``third_party/<name>`` on sys.path so its modules can be imported
    the way the original project imports them. Returns that folder.

    Example (inside an adapter)::

        root = use_third_party("fog_xxx")
        from fog_model import add_fog   # module from third_party/fog_xxx/
    """
    folder = THIRD_PARTY_DIR / name
    if not folder.is_dir():
        raise FileNotFoundError(f"third_party/{name} not found at {folder}")
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    return folder
