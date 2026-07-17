"""Ignore-rule logic: .gitignore + corpus.yml patterns + binary detection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pathspec

# These are always excluded regardless of what the user puts in corpus.yml.
ALWAYS_IGNORE = [
    "**/.corpus/**",
    "**/.git/**",
]

_ALWAYS_IGNORE_SPEC = pathspec.PathSpec.from_lines("gitwildmatch", ALWAYS_IGNORE)


def _load_gitignore_spec(root: Path) -> pathspec.PathSpec | None:
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return None
    patterns = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def _load_corpus_spec(config: dict[str, Any]) -> pathspec.PathSpec:
    patterns: list[str] = config.get("ignore", [])
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def _is_binary(path: Path) -> bool:
    """Return True if the file appears to be binary (non-UTF-8 in first 512 bytes)."""
    try:
        chunk = path.read_bytes()[:512]
        chunk.decode("utf-8")
        return False
    except (UnicodeDecodeError, OSError):
        return True


def get_tracked_files(
    root: Path, config: dict[str, Any]
) -> tuple[list[Path], int]:
    """
    Walk `root`, apply ignore rules, return (tracked_files, ignored_count).

    tracked_files: list of absolute Path objects for non-ignored, non-binary files.
    ignored_count: number of files skipped (ignored or binary).
    """
    gitignore_spec = _load_gitignore_spec(root)
    corpus_spec = _load_corpus_spec(config)

    tracked: list[Path] = []
    ignored_count = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        # Compute POSIX-style relative path for pathspec matching
        try:
            rel = path.relative_to(root)
        except ValueError:
            ignored_count += 1
            continue

        rel_posix = rel.as_posix()

        if _ALWAYS_IGNORE_SPEC.match_file(rel_posix):
            ignored_count += 1
            continue

        if corpus_spec.match_file(rel_posix):
            ignored_count += 1
            continue

        if gitignore_spec is not None and gitignore_spec.match_file(rel_posix):
            ignored_count += 1
            continue

        if _is_binary(path):
            ignored_count += 1
            continue

        tracked.append(path)

    tracked.sort()
    return tracked, ignored_count
