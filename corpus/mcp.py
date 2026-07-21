"""FastMCP stdio server exposing six Corpus query tools.

The .corpus/ directory is resolved lazily per call from cwd — the server can
be launched from any working directory as long as .corpus/ exists there.
Run with: python -m corpus.mcp
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

mcp = FastMCP("corpus")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _corpus_dir() -> Path:
    """Return the .corpus/ directory relative to the current working directory.

    Resolved per call so that the server works regardless of which directory
    it was imported from.
    """
    return Path.cwd() / ".corpus"


def _load_graph() -> dict[str, Any]:
    """Read graph.json fresh from disk (no cache)."""
    graph_path = _corpus_dir() / "graph.json"
    if not graph_path.exists():
        return {"nodes": [], "edges": []}
    try:
        return json.loads(graph_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"nodes": [], "edges": []}


def _load_state() -> dict[str, Any]:
    """Read state.json fresh from disk (no cache)."""
    state_path = _corpus_dir() / "state.json"
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _post_event(tool: str, node_id: str | None) -> None:
    """POST a fire-and-forget usage event to the sidecar at localhost:7077.

    Silently drops if the sidecar is not running — never raises.
    Dispatched on a daemon thread so MCP tools never block on the sidecar.
    """
    import threading

    payload = json.dumps(
        {
            "event": "query",
            "tool": tool,
            "node_id": node_id,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()

    def _send() -> None:
        try:
            req = urllib.request.Request(
                "http://localhost:7077/event",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=0.5)
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=_send, daemon=True).start()


def _node_by_path(graph: dict[str, Any], path: str) -> dict[str, Any] | None:
    for node in graph.get("nodes", []):
        if node.get("path") == path:
            return node
    return None


def _read_doc(node: dict[str, Any]) -> str:
    """Read the doc file for a node; return empty string if missing or out of bounds."""
    doc_rel = node.get("doc")
    if not doc_rel:
        return ""
    corpus = _corpus_dir()
    doc_path = corpus / doc_rel
    # Containment check: reject paths that escape .corpus/ (path traversal guard)
    if not doc_path.resolve().is_relative_to(corpus.resolve()):
        return ""
    try:
        return doc_path.read_text(encoding="utf-8")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
def corpus_overview() -> dict[str, Any]:
    """Return a high-level summary of the project from .corpus/ metadata.

    Includes project name, file/node/edge counts, stale node count,
    last-update timestamp, and the content of .corpus/docs/_dir.md if present.
    No source files are read.
    """
    graph = _load_graph()
    state = _load_state()

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    file_nodes = [n for n in nodes if n.get("type") == "file"]
    stale_nodes = [n for n in nodes if n.get("stale")]

    dir_md_path = _corpus_dir() / "docs" / "_dir.md"
    dir_md_content: str | None = None
    if dir_md_path.exists():
        try:
            dir_md_content = dir_md_path.read_text(encoding="utf-8")
        except OSError:
            pass

    # Derive project name from cwd
    project_name = Path.cwd().name

    result: dict[str, Any] = {
        "project": project_name,
        "file_count": len(file_nodes),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "stale_count": len(stale_nodes),
        "last_update": state.get("last_commit"),
    }
    if dir_md_content is not None:
        result["dir_md"] = dir_md_content

    _post_event("corpus_overview", None)
    return result


@mcp.tool()
def corpus_doc(path: str) -> dict[str, Any]:
    """Return the generated doc for a file, including staleness flag.

    Args:
        path: File path relative to repo root (e.g. "corpus/cli.py").

    Returns a dict with node id, path, importance, stale flag, and full doc text.
    Returns {"error": "..."} if the path is not found in graph.json.
    """
    graph = _load_graph()
    node = _node_by_path(graph, path)

    if node is None:
        _post_event("corpus_doc", None)
        return {"error": f"path '{path}' not found in graph.json. Has 'corpus update' been run?"}

    doc_text = _read_doc(node)
    _post_event("corpus_doc", node["id"])
    return {
        "id": node["id"],
        "path": node["path"],
        "importance": node.get("importance"),
        "stale": node.get("stale", False),
        "doc": doc_text,
    }


@mcp.tool()
def corpus_relations(path: str) -> dict[str, Any]:
    """Return all graph edges connected to the given file.

    Args:
        path: File path relative to repo root.

    Returns a dict with the node info and a list of related nodes,
    each with path, edge type, and direction (imports / imported_by).
    Returns {"error": "..."} if the path is not found.
    """
    graph = _load_graph()
    node = _node_by_path(graph, path)

    if node is None:
        _post_event("corpus_relations", None)
        return {"error": f"path '{path}' not found in graph.json."}

    node_id = node["id"]
    edges = graph.get("edges", [])
    nodes_by_id: dict[str, dict] = {n["id"]: n for n in graph.get("nodes", [])}

    relations: list[dict[str, Any]] = []
    for edge in edges:
        frm = edge.get("from")
        to = edge.get("to")
        edge_type = edge.get("type", "unknown")

        if frm == node_id:
            peer = nodes_by_id.get(to)
            if peer:
                relations.append({
                    "path": peer["path"],
                    "type": edge_type,
                    "direction": "imports",
                })
        elif to == node_id:
            peer = nodes_by_id.get(frm)
            if peer:
                relations.append({
                    "path": peer["path"],
                    "type": edge_type,
                    "direction": "imported_by",
                })

    _post_event("corpus_relations", node_id)
    return {
        "id": node_id,
        "path": node["path"],
        "relations": relations,
    }


@mcp.tool()
def corpus_find(symbol: str) -> list[dict[str, Any]]:
    """Search for nodes whose symbols list contains the given symbol.

    Args:
        symbol: Symbol name to search for (case-insensitive substring match).

    Returns a list of matching nodes with path, importance, and stale flag.
    """
    if not symbol.strip():
        return []

    graph = _load_graph()
    symbol_lower = symbol.lower()

    matches: list[dict[str, Any]] = []
    for node in graph.get("nodes", []):
        node_symbols: list[str] = node.get("symbols") or []
        if any(symbol_lower in s.lower() for s in node_symbols):
            matches.append({
                "id": node["id"],
                "path": node["path"],
                "importance": node.get("importance"),
                "stale": node.get("stale", False),
                "matched_symbols": [s for s in node_symbols if symbol_lower in s.lower()],
            })

    _post_event("corpus_find", None)
    return matches


@mcp.tool()
def corpus_changes() -> list[dict[str, Any]]:
    """Return nodes that have changed since the last 'corpus update' run.

    These are nodes marked stale — their source file has been modified but
    their doc has not been regenerated yet. Sorted by path.
    """
    graph = _load_graph()

    stale = [
        {
            "path": n["path"],
            "importance": n.get("importance"),
            "stale": True,
            "changed_since_last_update": True,
        }
        for n in graph.get("nodes", [])
        if n.get("stale")
    ]
    stale.sort(key=lambda x: x["path"])

    _post_event("corpus_changes", None)
    return stale


@mcp.tool()
def corpus_stale() -> list[dict[str, Any]]:
    """Return the raw list of all stale nodes with all fields.

    A node is stale when its source file hash differs from what was recorded
    during the last 'corpus update'. Sorted by path.
    """
    graph = _load_graph()

    stale = [
        {k: v for k, v in n.items()}
        for n in graph.get("nodes", [])
        if n.get("stale")
    ]
    stale.sort(key=lambda x: x.get("path", ""))

    _post_event("corpus_stale", None)
    return stale


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run() -> None:
    """Launch the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
