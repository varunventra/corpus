"""Build graph.json from tracked files and their parsed metadata."""

from __future__ import annotations

import json
import random
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from corpus.parser import parse_file


def _new_id(existing_ids: set[str]) -> str:
    """Generate a unique `n_XXXXXX` id not already in `existing_ids`."""
    attempts = 0
    while True:
        candidate = "n_" + "".join(random.choices(string.hexdigits[:16], k=6))
        if candidate not in existing_ids:
            return candidate
        attempts += 1
        if attempts >= 10_000:
            raise RuntimeError(
                f"_new_id: could not find a unique ID after 10,000 attempts "
                f"({len(existing_ids)} IDs already allocated). ID space may be exhausted."
            )


def build_graph(
    tracked_files: list[Path],
    repo_root: Path,
    existing_state: dict[str, Any],
) -> dict[str, Any]:
    """
    Parse all tracked files, build nodes + edges, write .corpus/graph.json.

    Args:
        tracked_files: absolute Paths of every file corpus should include.
        repo_root:     root of the repository (used to compute relative paths).
        existing_state: the loaded state dict (contains node_ids, file_hashes, …).

    Returns:
        Updated state dict (with new node_ids entries merged in).
        Also writes graph.json as a side effect.
    """
    node_ids: dict[str, str] = existing_state.get("node_ids", {}) or {}
    allocated_ids: set[str] = set(node_ids.values())

    # -----------------------------------------------------------------------
    # 1. Assign IDs and parse every tracked file
    # -----------------------------------------------------------------------
    file_meta: dict[str, dict[str, Any]] = {}  # rel_posix -> parse result + id

    for abs_path in tracked_files:
        try:
            rel = abs_path.relative_to(repo_root).as_posix()
        except ValueError:
            rel = abs_path.as_posix()

        # Reuse existing ID or mint a new one
        if rel not in node_ids:
            nid = _new_id(allocated_ids)
            node_ids[rel] = nid
            allocated_ids.add(nid)

        parsed = parse_file(abs_path)
        file_meta[rel] = {
            "id": node_ids[rel],
            "lang": parsed["lang"],
            "symbols": parsed["symbols"],
            "imports": parsed["imports"],
        }

    # -----------------------------------------------------------------------
    # 2. Build directory nodes
    # -----------------------------------------------------------------------
    # Collect all unique ancestor directories of tracked files
    dir_paths: set[str] = set()
    for rel in file_meta:
        parts = rel.split("/")
        for depth in range(1, len(parts)):
            dir_paths.add("/".join(parts[:depth]))

    dir_ids: dict[str, str] = {}
    for dir_rel in dir_paths:
        if dir_rel not in node_ids:
            nid = _new_id(allocated_ids)
            node_ids[dir_rel] = nid
            allocated_ids.add(nid)
        dir_ids[dir_rel] = node_ids[dir_rel]

    # -----------------------------------------------------------------------
    # 3. Assemble nodes list
    # -----------------------------------------------------------------------
    nodes: list[dict[str, Any]] = []

    # File nodes
    for rel, meta in file_meta.items():
        nodes.append(
            {
                "id": meta["id"],
                "path": rel,
                "type": "file",
                "lang": meta["lang"],
                "symbols": meta["symbols"],
                "importance": None,
                "doc": None,
                "stale": False,
            }
        )

    # Directory nodes
    for dir_rel, dir_id in dir_ids.items():
        nodes.append(
            {
                "id": dir_id,
                "path": dir_rel,
                "type": "dir",
                "lang": None,
                "symbols": [],
                "importance": None,
                "doc": None,
                "stale": False,
            }
        )

    # -----------------------------------------------------------------------
    # 4. Assemble edges
    # -----------------------------------------------------------------------
    edges: list[dict[str, str]] = []
    _seen_edges: set[tuple[str, str, str]] = set()

    def _add_edge(from_id: str, to_id: str, edge_type: str) -> None:
        key = (from_id, to_id, edge_type)
        if key not in _seen_edges:
            _seen_edges.add(key)
            edges.append({"from": from_id, "to": to_id, "type": edge_type})

    # Build lookup: rel_path -> id (files + dirs)
    path_to_id: dict[str, str] = {rel: m["id"] for rel, m in file_meta.items()}
    path_to_id.update(dir_ids)

    # contains edges: each node's immediate parent dir → node
    for rel in list(file_meta.keys()) + list(dir_ids.keys()):
        parent = _parent_dir(rel)
        if parent and parent in path_to_id:
            _add_edge(path_to_id[parent], path_to_id[rel], "contains")

    # imports edges: resolve module specifiers to tracked files
    tracked_set = set(file_meta.keys())
    for rel, meta in file_meta.items():
        src_id = meta["id"]
        lang = meta["lang"]
        for imp in meta["imports"]:
            target = _resolve_import(imp, rel, lang, tracked_set)
            if target and target != rel:
                target_id = path_to_id.get(target)
                if target_id:
                    _add_edge(src_id, target_id, "imports")

    # -----------------------------------------------------------------------
    # 5. Build the graph document
    # -----------------------------------------------------------------------
    graph = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes,
        "edges": edges,
    }

    # Update state with new node_ids
    existing_state["node_ids"] = node_ids
    return graph


def write_graph(corpus_dir: Path, graph: dict[str, Any]) -> None:
    """Write graph.json to corpus_dir (atomic write-then-rename)."""
    corpus_dir.mkdir(parents=True, exist_ok=True)
    tmp = corpus_dir / "graph.json.tmp"
    out = corpus_dir / "graph.json"
    tmp.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    tmp.replace(out)


# ---------------------------------------------------------------------------
# Import resolution helpers
# ---------------------------------------------------------------------------

def _parent_dir(rel: str) -> str | None:
    """Return the immediate parent directory of a relative path, or None if root."""
    idx = rel.rfind("/")
    if idx == -1:
        return None
    return rel[:idx]


def _resolve_import(
    specifier: str,
    importer_rel: str,
    lang: str | None,
    tracked_set: set[str],
) -> str | None:
    """
    Try to map an import specifier to a tracked file's relative path.

    Returns the matched relative path, or None if unresolvable / external.
    """
    if lang == "python":
        return _resolve_python_import(specifier, importer_rel, tracked_set)
    elif lang in ("javascript", "typescript", "tsx"):
        return _resolve_js_import(specifier, importer_rel, tracked_set)
    return None


def _resolve_python_import(
    specifier: str, importer_path: str, tracked_set: set[str]
) -> str | None:
    """
    Convert a Python module specifier to a tracked file path.

    Handles both absolute imports (`corpus.scaffold`) and relative imports
    (`.utils`, `..helpers`).  Returns the matched relative path or None.
    """
    dot_count = len(specifier) - len(specifier.lstrip("."))

    if dot_count > 0:
        # Relative import — resolve against the importer's package directory.
        rel_module = specifier[dot_count:]  # strip leading dots
        importer_parts = Path(importer_path).parent.parts  # e.g. ('corpus',)

        # Each extra dot beyond the first goes one more level up.
        if dot_count > 1 and len(importer_parts) >= dot_count - 1:
            importer_parts = importer_parts[:-(dot_count - 1)]
        elif dot_count > 1:
            # Relative import escapes the repo root — unresolvable.
            return None

        if rel_module:
            candidate_parts = importer_parts + tuple(rel_module.split("."))
        else:
            candidate_parts = importer_parts

        if not candidate_parts:
            return None

        base = "/".join(candidate_parts)
        candidates = [f"{base}.py", f"{base}/__init__.py"]
        for c in candidates:
            if c in tracked_set:
                return c
        return None

    # Absolute import — existing logic unchanged.
    as_path = specifier.replace(".", "/")
    candidates = [f"{as_path}.py", f"{as_path}/__init__.py"]
    for c in candidates:
        if c in tracked_set:
            return c
    return None


def _resolve_js_import(
    specifier: str, importer_rel: str, tracked_set: set[str]
) -> str | None:
    """
    Resolve a JS/TS import specifier.

    Only resolves relative imports (starting with `.` or `..`).
    Bare module specifiers (npm packages) are skipped.
    """
    if not specifier.startswith("."):
        return None  # bare specifier → external npm package, skip

    importer_dir = _parent_dir(importer_rel) or ""
    # Join importer dir with relative specifier
    if importer_dir:
        joined = importer_dir + "/" + specifier
    else:
        joined = specifier

    # Normalise the path (resolve . and ..)
    parts: list[str] = []
    for part in joined.split("/"):
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part)
    base = "/".join(parts)

    # Try common extensions in priority order
    extensions = [".js", ".ts", ".tsx", ".jsx", "/index.js", "/index.ts"]
    # First try exact match (specifier already has extension)
    if base in tracked_set:
        return base
    for ext in extensions:
        candidate = base + ext
        if candidate in tracked_set:
            return candidate

    return None
