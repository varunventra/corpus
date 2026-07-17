"""corpus init scaffolding logic."""

from __future__ import annotations

import json
from pathlib import Path

import click

from corpus.config import load_config, write_default_config
from corpus.ignore import get_tracked_files


_EMPTY_STATE = {"version": 1, "last_commit": None, "file_hashes": {}}


def run_init(root: Path) -> None:
    """
    Scaffold `.corpus/` under `root`.

    Prompts before overwriting if already initialized.
    """
    corpus_dir = root / ".corpus"
    corpus_yml = corpus_dir / "corpus.yml"
    state_json = corpus_dir / "state.json"

    already_init = corpus_dir.exists()

    if already_init:
        if not click.confirm(
            "Already initialized. Re-run init? (resets state.json only, corpus.yml kept)",
            default=False,
        ):
            click.echo("Aborted.")
            return

    # Create directory tree
    corpus_dir.mkdir(exist_ok=True)
    (corpus_dir / "docs").mkdir(exist_ok=True)
    (corpus_dir / "changelog").mkdir(exist_ok=True)

    # Write config only on first init; on re-init keep the user's corpus.yml
    if not already_init:
        write_default_config(corpus_yml)
    state_json.write_text(json.dumps(_EMPTY_STATE, indent=2), encoding="utf-8")

    # Load config (just wrote it) and scan files
    config = load_config(corpus_yml)
    tracked, ignored_count = get_tracked_files(root, config)

    click.echo(
        f"Found {len(tracked)} files ({ignored_count} ignored). "
        "Run 'corpus update' to generate docs."
    )
    click.echo(
        "To register with Claude Code, run:\n"
        "  claude mcp add corpus -- python -m corpus.mcp"
    )
