"""CLI entry point for the corpus command."""

from __future__ import annotations

import os
from pathlib import Path

import click

from corpus.scaffold import run_init


@click.group()
def main() -> None:
    """Corpus — living second representation of your codebase."""


@main.command()
def init() -> None:
    """Scaffold .corpus/ in the current directory."""
    run_init(Path.cwd())


@main.command()
def update() -> None:
    """Parse all tracked files and write .corpus/graph.json."""
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

    config = load_config(corpus_yml)
    tracked, _ = get_tracked_files(root, config)

    state = load_state(corpus_dir)

    graph = build_graph(tracked, root, state)

    # Update file_hashes in state
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
    state["file_hashes"] = file_hashes

    write_graph(corpus_dir, graph)
    save_state(corpus_dir, state)

    n_nodes = len(graph["nodes"])
    n_edges = len(graph["edges"])
    click.echo(f"Updated graph.json — {n_nodes} nodes, {n_edges} edges.")

    # --- Doc generation ---
    has_gemini = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    has_groq = bool(os.environ.get("GROQ_API_KEY", "").strip())

    if not has_gemini and not has_groq:
        click.echo(
            "Warning: neither GEMINI_API_KEY nor GROQ_API_KEY is set. "
            "Skipping doc generation."
        )
        return

    from corpus.docs import generate_file_doc, generate_dir_rollup

    limits = config.get("limits", {})
    max_calls_per_day: int = limits.get("max_calls_per_day", 100)
    max_files_per_update: int = limits.get("max_files_per_update", 50)

    # File nodes only
    file_nodes = [n for n in graph["nodes"] if n.get("type") == "file"]

    calls_made = 0
    dirs_with_docs: set[str] = set()

    for node in file_nodes:
        if calls_made >= max_calls_per_day:
            remaining = len(file_nodes) - calls_made
            click.echo(
                f"Warning: daily call limit reached ({max_calls_per_day}). "
                f"{remaining} files not documented."
            )
            # Mark undocumented nodes as stale
            for undoc_node in file_nodes[calls_made:]:
                undoc_node["stale"] = True
            break

        if calls_made >= max_files_per_update:
            remaining = len(file_nodes) - calls_made
            click.echo(
                f"Warning: max_files_per_update limit reached ({max_files_per_update}). "
                f"{remaining} files not documented."
            )
            for undoc_node in file_nodes[calls_made:]:
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
        calls_made += 1

        # Track this file's directory and all ancestor directories (for rollups)
        slash_idx = rel_path.rfind("/")
        if slash_idx == -1:
            dirs_with_docs.add(".")
        else:
            # Walk up from immediate parent to the topmost segment
            segment = rel_path[:slash_idx]
            while segment:
                dirs_with_docs.add(segment)
                up = segment.rfind("/")
                if up == -1:
                    break
                segment = segment[:up]

    # Generate _dir.md rollups deepest-first so parent rollups can read child _dir.md files
    for dir_path in sorted(dirs_with_docs, key=lambda p: p.count("/"), reverse=True):
        generate_dir_rollup(dir_path, corpus_dir, root)

    # Re-write graph.json with updated importance/doc fields
    write_graph(corpus_dir, graph)
    click.echo(f"Docs written. {calls_made} files documented.")
