"""CLI entry point for the corpus command."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import urllib.request
from pathlib import Path

import click

from corpus.scaffold import run_init


def _post_graph_event() -> None:
    """Fire-and-forget POST to sidecar after a successful corpus update.

    Silently ignored if the sidecar is not running.
    """
    payload = json.dumps({"event": "graph"}).encode()

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

    thread = threading.Thread(target=_send, daemon=False)
    thread.start()
    thread.join(timeout=1.5)


@click.group()
def main() -> None:
    """Corpus — living second representation of your codebase."""


@main.command()
def init() -> None:
    """Scaffold .corpus/ in the current directory."""
    run_init(Path.cwd())


@main.command()
def update() -> None:
    """Parse changed files and write .corpus/graph.json (incremental)."""
    root = Path.cwd()
    corpus_dir = root / ".corpus"
    corpus_yml = corpus_dir / "corpus.yml"

    if not corpus_yml.exists():
        raise click.ClickException(
            ".corpus/corpus.yml not found. Run 'corpus init' first."
        )

    from corpus.config import load_config
    from corpus.ignore import get_tracked_files
    from corpus.state import load_state, save_state, compute_hash
    from corpus.graph import build_graph, write_graph
    from corpus.diff import get_changed_files, get_invalidated_nodes

    config = load_config(corpus_yml)
    tracked, _ = get_tracked_files(root, config)

    state = load_state(corpus_dir)
    stored_commit: str | None = state.get("last_commit")
    stored_hashes: dict[str, str] = state.get("file_hashes") or {}

    # --- Determine current HEAD commit ---
    current_commit: str | None = None
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(root),
            timeout=10,
        )
        if res.returncode == 0:
            current_commit = res.stdout.strip() or None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Build rel-path set for currently tracked files
    tracked_rel: set[str] = set()
    for abs_path in tracked:
        try:
            rel = abs_path.relative_to(root).as_posix()
        except ValueError:
            rel = abs_path.as_posix()
        tracked_rel.add(rel)

    # On first run (no stored hashes), build_graph does full generation.
    # Pass stored_hashes to diff so it can detect changes from the stored state.
    changed = get_changed_files(root, stored_commit, stored_hashes)

    modified_paths: list[str] = changed["modified"]
    added_paths: list[str] = changed["added"]
    deleted_paths: list[str] = changed["deleted"]
    renamed_pairs: list[dict[str, str]] = changed["renamed"]

    # --- Load existing graph or build fresh ---
    graph_path = corpus_dir / "graph.json"
    if graph_path.exists():
        import json
        try:
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            graph = None
    else:
        graph = None

    if graph is None:
        # First run or corrupt graph: full rebuild
        graph = build_graph(tracked, root, state)
        added_paths = list(tracked_rel)  # everything is "new"
        modified_paths = []
        deleted_paths = []
        renamed_pairs = []
    else:
        # --- Incremental: apply renames, deletions, additions ---
        node_ids: dict[str, str] = state.get("node_ids") or {}
        allocated_ids: set[str] = {n["id"] for n in graph.get("nodes", [])}

        # Build path → node map for quick lookup
        path_to_node: dict[str, dict] = {n["path"]: n for n in graph.get("nodes", [])}

        # 1. Handle renames
        for pair in renamed_pairs:
            old_path = pair["old"]
            new_path = pair["new"]
            node = path_to_node.get(old_path)
            if node is not None:
                # Update node path
                node["path"] = new_path
                path_to_node[new_path] = node
                del path_to_node[old_path]

                # Move doc file
                old_doc = corpus_dir / "docs" / old_path
                old_doc_md = old_doc.parent / (old_doc.name + ".md")
                new_doc = corpus_dir / "docs" / new_path
                new_doc_md = new_doc.parent / (new_doc.name + ".md")
                if old_doc_md.exists():
                    new_doc_md.parent.mkdir(parents=True, exist_ok=True)
                    old_doc_md.rename(new_doc_md)

                # Update node["doc"] path if set
                if node.get("doc"):
                    node["doc"] = f"docs/{new_path}.md"

                # Update node_ids and stored_hashes
                if old_path in node_ids:
                    node_ids[new_path] = node_ids.pop(old_path)
                if old_path in stored_hashes:
                    stored_hashes[new_path] = stored_hashes.pop(old_path)

        # 2. Handle deletions (mark stale, keep node for history)
        for del_path in deleted_paths:
            node = path_to_node.get(del_path)
            if node is not None:
                node["stale"] = True
            stored_hashes.pop(del_path, None)

        # 3. Handle added files — parse them and add nodes to the graph
        from corpus.parser import parse_file
        from corpus.graph import _new_id

        for add_path in added_paths:
            # Only process if the path is in our current tracked set
            if add_path not in tracked_rel:
                continue
            if add_path in path_to_node:
                continue  # already exists (e.g. same path re-added)

            abs_path = root / add_path
            if not abs_path.exists():
                continue

            # Mint a new node ID
            if add_path not in node_ids:
                nid = _new_id(allocated_ids)
                node_ids[add_path] = nid
                allocated_ids.add(nid)

            parsed = parse_file(abs_path)
            new_node: dict = {
                "id": node_ids[add_path],
                "path": add_path,
                "type": "file",
                "lang": parsed["lang"],
                "symbols": parsed["symbols"],
                "importance": None,
                "doc": None,
                "stale": False,
            }
            graph["nodes"].append(new_node)
            path_to_node[add_path] = new_node

            # Ensure ancestor directory nodes exist
            _ensure_dir_ancestors(add_path, graph, node_ids, allocated_ids)

        # Persist updated node_ids back to state
        state["node_ids"] = node_ids

    # --- Compute file_hashes for current tracked files ---
    file_hashes: dict[str, str] = {}
    for abs_path in tracked:
        try:
            rel = abs_path.relative_to(root).as_posix()
        except ValueError:
            rel = abs_path.as_posix()
        try:
            file_hashes[rel] = compute_hash(abs_path)
        except OSError:
            click.echo(f"Warning: could not hash {rel}, skipping.", err=True)

    # --- Mark staleness on all nodes ---
    # Any tracked file whose current hash differs from the stored hash is stale.
    # Files with no prior hash are brand-new (added), not stale.
    stale_file_paths: set[str] = set()
    for rel, current_hash in file_hashes.items():
        old_hash = stored_hashes.get(rel)
        if old_hash is not None and current_hash != old_hash:
            stale_file_paths.add(rel)

    # Also mark deleted paths as stale
    for del_path in deleted_paths:
        stale_file_paths.add(del_path)

    # Apply stale flags to all nodes
    for node in graph.get("nodes", []):
        if node.get("type") == "file":
            node["stale"] = node["path"] in stale_file_paths
        elif node.get("type") == "dir":
            # Directory is stale if any descendant file is stale
            dir_prefix = node["path"] + "/"
            is_stale = any(
                fp == node["path"] or fp.startswith(dir_prefix)
                for fp in stale_file_paths
            )
            node["stale"] = is_stale

    # --- Build re-doc set ---
    # Changed = modified + added (in the git/hash sense)
    all_changed_for_redoc: list[str] = list(
        set(modified_paths) | set(added_paths) | stale_file_paths
    )

    # Bootstrap guard: if no docs exist yet, treat all file nodes as needing docs.
    # This handles the case where graph.json was built on a run with no API key,
    # so the incremental diff sees no changes but docs were never generated.
    docs_dir = corpus_dir / "docs"
    has_any_docs = docs_dir.exists() and any(docs_dir.rglob("*.md"))
    if not has_any_docs:
        redoc_ids = {n["id"] for n in graph.get("nodes", []) if n.get("type") == "file"}
    else:
        redoc_ids = get_invalidated_nodes(all_changed_for_redoc, graph)

    write_graph(corpus_dir, graph)

    n_nodes = len(graph["nodes"])
    n_edges = len(graph.get("edges", []))
    click.echo(f"Updated graph.json — {n_nodes} nodes, {n_edges} edges.")

    # Update state
    state["file_hashes"] = file_hashes
    state["last_commit"] = current_commit
    save_state(corpus_dir, state)

    # --- Doc generation ---
    has_gemini = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    has_groq = bool(os.environ.get("GROQ_API_KEY", "").strip())

    if not has_gemini and not has_groq:
        click.echo(
            "Warning: neither GEMINI_API_KEY nor GROQ_API_KEY is set. "
            "Skipping doc generation."
        )
        # Still report staleness summary
        n_stale = len(stale_file_paths)
        n_total = sum(1 for n in graph.get("nodes", []) if n.get("type") == "file")
        n_unchanged = n_total - n_stale
        click.echo(
            f"Re-documented 0 files ({n_unchanged} unchanged, {n_stale} stale)."
        )
        _post_graph_event()
        return

    from corpus.docs import generate_file_doc, generate_dir_rollup

    limits = config.get("limits", {})
    max_calls_per_day: int = limits.get("max_calls_per_day", 100)
    max_files_per_update: int = limits.get("max_files_per_update", 50)

    # File nodes only, restricted to the re-doc set
    all_file_nodes = [n for n in graph["nodes"] if n.get("type") == "file"]
    redoc_nodes = [n for n in all_file_nodes if n["id"] in redoc_ids]
    unchanged_count = len(all_file_nodes) - len(redoc_nodes)

    calls_made = 0
    dirs_with_docs: set[str] = set()

    for node in redoc_nodes:
        if calls_made >= max_calls_per_day:
            remaining = len(redoc_nodes) - calls_made
            click.echo(
                f"Warning: daily call limit reached ({max_calls_per_day}). "
                f"{remaining} files not documented."
            )
            for undoc_node in redoc_nodes[calls_made:]:
                undoc_node["stale"] = True
            break

        if calls_made >= max_files_per_update:
            remaining = len(redoc_nodes) - calls_made
            click.echo(
                f"Warning: max_files_per_update limit reached ({max_files_per_update}). "
                f"{remaining} files not documented."
            )
            for undoc_node in redoc_nodes[calls_made:]:
                undoc_node["stale"] = True
            break

        rel_path: str = node["path"]
        click.echo(f"  Documenting {rel_path}...")

        try:
            _doc_text, importance = generate_file_doc(
                node, graph, root, corpus_dir, config
            )
        except Exception as exc:  # noqa: BLE001
            click.echo(f"  Warning: failed to document {rel_path}: {exc}", err=True)
            node["stale"] = True
            calls_made += 1
            continue

        node["importance"] = importance
        node["stale"] = False
        calls_made += 1

        # Track ancestor directories for rollup regeneration
        slash_idx = rel_path.rfind("/")
        if slash_idx == -1:
            dirs_with_docs.add(".")
        else:
            segment = rel_path[:slash_idx]
            while segment:
                dirs_with_docs.add(segment)
                up = segment.rfind("/")
                if up == -1:
                    break
                segment = segment[:up]

    # Generate _dir.md rollups deepest-first for affected ancestors only
    for dir_path in sorted(dirs_with_docs, key=lambda p: p.count("/"), reverse=True):
        generate_dir_rollup(dir_path, corpus_dir, root)

    # Re-write graph.json with updated importance/doc/stale fields
    write_graph(corpus_dir, graph)

    n_stale_final = sum(
        1 for n in graph.get("nodes", [])
        if n.get("type") == "file" and n.get("stale")
    )
    click.echo(
        f"Re-documented {calls_made} files "
        f"({unchanged_count} unchanged, {n_stale_final} stale)."
    )
    _post_graph_event()


@main.command()
@click.option("--mcp", "use_mcp", is_flag=True, default=False, help="Launch the MCP server.")
def serve(use_mcp: bool) -> None:
    """Launch the graph viewer or (with --mcp) the FastMCP stdio server.

    Register MCP with: claude mcp add corpus -- python -m corpus.mcp
    """
    if use_mcp:
        from corpus.mcp import run as run_mcp
        run_mcp()
        return

    # --- Graph viewer mode ---
    import webbrowser
    import uvicorn

    root = Path.cwd()
    dist_index = root / "frontend" / "dist" / "index.html"

    if not dist_index.exists():
        click.echo("Building frontend...")
        result = subprocess.run(
            "npm run build",
            cwd=str(root / "frontend"),
            shell=True,
        )
        if result.returncode != 0:
            raise click.ClickException("Frontend build failed. See output above.")

    url = "http://localhost:7077"
    click.echo(f"Corpus graph viewer running at {url}")

    import threading
    def _open_browser():
        import time; time.sleep(1.5)
        webbrowser.open(url)
    threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(
        "corpus.server:app",
        host="127.0.0.1",
        port=7077,
        log_level="info",
    )


def _ensure_dir_ancestors(
    file_rel: str,
    graph: dict,
    node_ids: dict[str, str],
    allocated_ids: set[str],
) -> None:
    """
    Ensure directory nodes exist in graph for every ancestor of file_rel.
    Mutates graph['nodes'], node_ids, and allocated_ids in-place.
    """
    from corpus.graph import _new_id

    existing_paths: set[str] = {n["path"] for n in graph.get("nodes", [])}
    parts = file_rel.split("/")
    for depth in range(1, len(parts)):
        dir_rel = "/".join(parts[:depth])
        if dir_rel in existing_paths:
            continue
        if dir_rel not in node_ids:
            nid = _new_id(allocated_ids)
            node_ids[dir_rel] = nid
            allocated_ids.add(nid)
        dir_node = {
            "id": node_ids[dir_rel],
            "path": dir_rel,
            "type": "dir",
            "lang": None,
            "symbols": [],
            "importance": None,
            "doc": None,
            "stale": False,
        }
        graph["nodes"].append(dir_node)
        existing_paths.add(dir_rel)


if __name__ == "__main__":
    main()
