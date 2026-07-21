"""Compute changed files between stored state and current working tree."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any


def get_changed_files(
    repo_root: Path,
    stored_commit: str | None,
    file_hashes: dict[str, str],
) -> dict[str, Any]:
    """
    Return a dict describing which tracked files changed since the last update.

    Keys:
      'modified': list of repo-relative posix paths (content changed)
      'added':    list of repo-relative posix paths (new tracked files)
      'deleted':  list of repo-relative posix paths (removed from tracking)
      'renamed':  list of {'old': path, 'new': path} dicts

    Strategy:
    1. If stored_commit is not None and git is available, run
       `git diff -M --name-status {stored_commit} HEAD` to detect renames and
       git-level changes (M/A/D/R).
    2. Supplement with content-hash comparison: any tracked file not already
       classified as modified/added whose hash differs from file_hashes is added
       to 'modified'. This catches uncommitted edits.
    3. If stored_hashes is empty (first run), returns empty lists for all
       categories; the caller is responsible for treating the first run as a
       full rebuild.
    """
    if stored_commit is None:
        # No stored commit — return empty lists; caller handles full rebuild.
        return {
            "modified": [],
            "added": [],
            "deleted": [],
            "renamed": [],
        }

    modified: list[str] = []
    added: list[str] = []
    deleted: list[str] = []
    renamed: list[dict[str, str]] = []

    # Set of paths accounted for by git diff (skip hash check for these)
    git_accounted: set[str] = set()

    # --- 1. git diff -M ---
    try:
        result = subprocess.run(
            ["git", "diff", "-M", "--name-status", stored_commit, "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            timeout=30,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t")
                if not parts:
                    continue
                status = parts[0].strip()

                if status == "M" and len(parts) >= 2:
                    path = parts[1].strip()
                    modified.append(path)
                    git_accounted.add(path)

                elif status == "A" and len(parts) >= 2:
                    path = parts[1].strip()
                    added.append(path)
                    git_accounted.add(path)

                elif status == "D" and len(parts) >= 2:
                    path = parts[1].strip()
                    deleted.append(path)
                    git_accounted.add(path)

                elif status.startswith("R") and len(parts) >= 3:
                    # R100\told_path\tnew_path
                    old_path = parts[1].strip()
                    new_path = parts[2].strip()
                    renamed.append({"old": old_path, "new": new_path})
                    git_accounted.add(old_path)
                    git_accounted.add(new_path)
        else:
            print(
                f"Warning: git diff failed (returncode {result.returncode}); "
                "falling back to hash-only change detection. Rename detection disabled.",
                file=sys.stderr,
            )

    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        # git not available or timed out — fall through to hash-only
        pass

    # --- 2. Content-hash supplement ---
    # Check every known file whose hash we stored. This catches uncommitted edits
    # that git diff (which compares commits) would not see.
    for rel_path, stored_hash in file_hashes.items():
        if rel_path in git_accounted:
            continue
        abs_path = repo_root / rel_path
        if not abs_path.exists():
            # File disappeared from disk but wasn't caught by git diff
            if rel_path not in deleted:
                deleted.append(rel_path)
            continue
        try:
            h = hashlib.sha256()
            h.update(abs_path.read_bytes())
            current_hash = h.hexdigest()
        except OSError:
            continue
        if current_hash != stored_hash:
            modified.append(rel_path)

    return {
        "modified": modified,
        "added": added,
        "deleted": deleted,
        "renamed": renamed,
    }


def get_invalidated_nodes(
    changed_paths: list[str],
    graph: dict[str, Any],
) -> set[str]:
    """
    Return set of node IDs that need to be re-documented.

    The re-doc set includes:
    - Nodes for each changed file path
    - Direct importers of those nodes (one hop only), because a change in a
      file's exported symbols can affect how importing files are documented.

    'Direct importer' means: an edge where type='imports' and to==changed_node_id.
    The importing node is edge['from'].
    """
    if not changed_paths:
        return set()

    # Build path → node_id map
    path_to_id: dict[str, str] = {}
    for node in graph.get("nodes", []):
        if node.get("type") == "file":
            path_to_id[node["path"]] = node["id"]

    # Collect IDs for the changed paths
    changed_ids: set[str] = set()
    for path in changed_paths:
        nid = path_to_id.get(path)
        if nid:
            changed_ids.add(nid)

    if not changed_ids:
        return set()

    # Find direct importers (one hop)
    importer_ids: set[str] = set()
    for edge in graph.get("edges", []):
        if edge.get("type") != "imports":
            continue
        if edge.get("to") in changed_ids:
            src = edge.get("from")
            if src and src not in changed_ids:
                importer_ids.add(src)

    return changed_ids | importer_ids
