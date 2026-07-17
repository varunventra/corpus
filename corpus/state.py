"""State persistence: load/save .corpus/state.json and compute file hashes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


_DEFAULT_STATE: dict[str, Any] = {
    "version": 1,
    "last_commit": None,
    "node_ids": {},
    "file_hashes": {},
}


def load_state(corpus_dir: Path) -> dict[str, Any]:
    """Read .corpus/state.json; return default structure if missing or corrupt."""
    state_path = corpus_dir / "state.json"
    if not state_path.exists():
        return _default()

    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _default()

    # Ensure all expected keys are present (handles old state.json from Phase 1a)
    result = _default()
    result.update(data)
    # Guarantee sub-dicts exist even if the file had them as null
    if not isinstance(result.get("node_ids"), dict):
        result["node_ids"] = {}
    if not isinstance(result.get("file_hashes"), dict):
        result["file_hashes"] = {}
    return result


def save_state(corpus_dir: Path, state: dict[str, Any]) -> None:
    """Write state to .corpus/state.json atomically (write-then-rename)."""
    corpus_dir.mkdir(parents=True, exist_ok=True)
    state_path = corpus_dir / "state.json"
    tmp_path = corpus_dir / "state.json.tmp"
    tmp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp_path.replace(state_path)


def compute_hash(path: Path) -> str:
    """Return SHA-256 hex digest of the file's contents."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _default() -> dict[str, Any]:
    return {
        "version": 1,
        "last_commit": None,
        "node_ids": {},
        "file_hashes": {},
    }
