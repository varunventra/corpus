"""
Phase 1a acceptance-criteria tests + edge-case / error-path coverage.

Acceptance criteria (from PLAN.md Phase 1a):
  AC1 - pip install -e . succeeds and `corpus --help` prints the command list
  AC2 - corpus init creates .corpus/corpus.yml and .corpus/state.json
  AC3 - corpus init prints "Found N files (N ignored)" without error
  AC4 - Running corpus init a second time does not clobber existing config
  AC5 - .corpus/ itself does not appear in the scan list (self-exclusion)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from corpus.cli import main
from corpus.config import load_config, write_default_config, DEFAULT_CONFIG
from corpus.ignore import get_tracked_files, ALWAYS_IGNORE
from corpus.scaffold import run_init


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_git_repo(tmp_path: Path) -> Path:
    """Initialise a minimal git repo so corpus init has a real root to work in.

    Uses subprocess.PIPE instead of capture_output=True to work around a
    Python 3.14 / Windows handle-inheritance bug with capture_output.
    """
    subprocess.run(
        ["git", "init", str(tmp_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return tmp_path


def _invoke(args: list[str], cwd: Path | None = None, input: str | None = None):
    """Run the CLI via Click's CliRunner, optionally changing cwd first."""
    runner = CliRunner()
    old_cwd = os.getcwd()
    try:
        if cwd:
            os.chdir(cwd)
        result = runner.invoke(main, args, input=input, catch_exceptions=False)
    finally:
        os.chdir(old_cwd)
    return result


# ---------------------------------------------------------------------------
# AC1 — pip install -e . + corpus --help
# ---------------------------------------------------------------------------

class TestAC1HelpCommand:
    def test_help_exit_code_zero(self):
        """--help must exit 0."""
        result = _invoke(["--help"])
        assert result.exit_code == 0, f"Exit code was {result.exit_code}\n{result.output}"

    def test_help_shows_init_command(self):
        """--help output must mention 'init'."""
        result = _invoke(["--help"])
        assert "init" in result.output

    def test_help_shows_update_command(self):
        """--help output must mention 'update'."""
        result = _invoke(["--help"])
        assert "update" in result.output

    def test_corpus_importable(self):
        """corpus package must be importable (proves pip install -e . succeeded)."""
        import corpus  # noqa: F401 — import is the test
        assert corpus.__version__ == "0.1.0"

    def test_init_subcommand_help(self):
        """'corpus init --help' must work."""
        result = _invoke(["init", "--help"])
        assert result.exit_code == 0

    def test_update_subcommand_help(self):
        """'corpus update --help' must work."""
        result = _invoke(["update", "--help"])
        assert result.exit_code == 0

    def test_update_produces_output(self):
        """'corpus update' must exit 0 and print something to stdout."""
        result = _invoke(["update"])
        assert result.exit_code == 0
        assert result.output.strip() != ""

    def test_unknown_command_nonzero_exit(self):
        """Unknown subcommand must exit non-zero."""
        runner = CliRunner()
        result = runner.invoke(main, ["doesnotexist"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# AC2 — corpus init creates .corpus/corpus.yml and .corpus/state.json
# ---------------------------------------------------------------------------

class TestAC2FilesCreated:
    def test_corpus_yml_exists(self, tmp_path):
        _make_git_repo(tmp_path)
        result = _invoke(["init"], cwd=tmp_path)
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".corpus" / "corpus.yml").exists()

    def test_state_json_exists(self, tmp_path):
        _make_git_repo(tmp_path)
        result = _invoke(["init"], cwd=tmp_path)
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".corpus" / "state.json").exists()

    def test_state_json_is_valid_json(self, tmp_path):
        _make_git_repo(tmp_path)
        _invoke(["init"], cwd=tmp_path)
        state_path = tmp_path / ".corpus" / "state.json"
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert "version" in data
        assert "file_hashes" in data

    def test_corpus_yml_is_readable(self, tmp_path):
        _make_git_repo(tmp_path)
        _invoke(["init"], cwd=tmp_path)
        yml_path = tmp_path / ".corpus" / "corpus.yml"
        text = yml_path.read_text(encoding="utf-8")
        assert "provider" in text
        assert "ignore" in text

    def test_docs_subdir_created(self, tmp_path):
        """scaffold must create .corpus/docs/ directory."""
        _make_git_repo(tmp_path)
        _invoke(["init"], cwd=tmp_path)
        assert (tmp_path / ".corpus" / "docs").is_dir()

    def test_changelog_subdir_created(self, tmp_path):
        """scaffold must create .corpus/changelog/ directory."""
        _make_git_repo(tmp_path)
        _invoke(["init"], cwd=tmp_path)
        assert (tmp_path / ".corpus" / "changelog").is_dir()

    def test_state_json_initial_structure(self, tmp_path):
        """state.json must have version=1, last_commit=None, file_hashes={}."""
        _make_git_repo(tmp_path)
        _invoke(["init"], cwd=tmp_path)
        data = json.loads(
            (tmp_path / ".corpus" / "state.json").read_text(encoding="utf-8")
        )
        assert data["version"] == 1
        assert data["last_commit"] is None
        assert data["file_hashes"] == {}


# ---------------------------------------------------------------------------
# AC3 — corpus init prints file count summary
# ---------------------------------------------------------------------------

class TestAC3FileSummary:
    def test_summary_line_present(self, tmp_path):
        """Output must contain 'Found' and 'ignored'."""
        _make_git_repo(tmp_path)
        result = _invoke(["init"], cwd=tmp_path)
        assert result.exit_code == 0, result.output
        assert "Found" in result.output
        assert "ignored" in result.output.lower()

    def test_summary_counts_are_integers(self, tmp_path):
        """The counts in the summary must be parseable integers."""
        _make_git_repo(tmp_path)
        (tmp_path / "hello.py").write_text("print('hi')", encoding="utf-8")
        result = _invoke(["init"], cwd=tmp_path)
        match = re.search(r"Found (\d+) files?\s*\((\d+) ignored\)", result.output)
        assert match, f"Could not find count summary in output:\n{result.output}"
        found = int(match.group(1))
        ignored = int(match.group(2))
        assert found >= 1
        assert ignored >= 0

    def test_mcp_hint_present(self, tmp_path):
        """Init must print the claude mcp add hint (per scaffold.py)."""
        _make_git_repo(tmp_path)
        result = _invoke(["init"], cwd=tmp_path)
        assert "claude mcp add corpus" in result.output

    def test_empty_repo_summary(self, tmp_path):
        """An empty git repo (no source files) should print 'Found 0 files'."""
        _make_git_repo(tmp_path)
        result = _invoke(["init"], cwd=tmp_path)
        assert re.search(r"Found 0 files?", result.output), (
            f"Expected 'Found 0 files' in output:\n{result.output}"
        )

    def test_multiple_tracked_files_counted(self, tmp_path):
        """Multiple source files must all appear in the count."""
        _make_git_repo(tmp_path)
        (tmp_path / "a.py").write_text("a = 1\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("b = 2\n", encoding="utf-8")
        (tmp_path / "c.py").write_text("c = 3\n", encoding="utf-8")
        result = _invoke(["init"], cwd=tmp_path)
        match = re.search(r"Found (\d+) files?", result.output)
        assert match
        count = int(match.group(1))
        assert count >= 3, f"Expected at least 3, got {count}"


# ---------------------------------------------------------------------------
# AC4 — second corpus init does not clobber corpus.yml
# ---------------------------------------------------------------------------

class TestAC4SecondInitNoClobber:
    def test_second_init_skipped_preserves_corpus_yml(self, tmp_path):
        """Answering 'n' at re-init prompt must leave corpus.yml unchanged."""
        _make_git_repo(tmp_path)
        _invoke(["init"], cwd=tmp_path)
        yml_path = tmp_path / ".corpus" / "corpus.yml"
        original_text = yml_path.read_text(encoding="utf-8")
        sentinel = original_text + "\n# SENTINEL_MARKER\n"
        yml_path.write_text(sentinel, encoding="utf-8")

        result = _invoke(["init"], cwd=tmp_path, input="n\n")
        assert result.exit_code == 0, result.output
        assert "SENTINEL_MARKER" in yml_path.read_text(encoding="utf-8")

    def test_second_init_aborted_message(self, tmp_path):
        """Answering 'n' must produce an abort/skip message."""
        _make_git_repo(tmp_path)
        _invoke(["init"], cwd=tmp_path)
        result = _invoke(["init"], cwd=tmp_path, input="n\n")
        output_lower = result.output.lower()
        assert (
            "abort" in output_lower
            or "skip" in output_lower
            or "cancelled" in output_lower
        ), f"No abort/skip message in output:\n{result.output}"

    def test_second_init_confirmed_resets_state_json(self, tmp_path):
        """Answering 'y' must reset state.json to empty state."""
        _make_git_repo(tmp_path)
        _invoke(["init"], cwd=tmp_path)
        state_path = tmp_path / ".corpus" / "state.json"
        state_path.write_text(
            '{"version": 1, "last_commit": null, "file_hashes": {"fake.py": "abc123"}}',
            encoding="utf-8",
        )
        result = _invoke(["init"], cwd=tmp_path, input="y\n")
        assert result.exit_code == 0, result.output
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert data["file_hashes"] == {}

    def test_second_init_confirmed_preserves_corpus_yml(self, tmp_path):
        """Answering 'y' must NOT overwrite corpus.yml."""
        _make_git_repo(tmp_path)
        _invoke(["init"], cwd=tmp_path)
        yml_path = tmp_path / ".corpus" / "corpus.yml"
        sentinel = yml_path.read_text(encoding="utf-8") + "\n# SENTINEL_MARKER\n"
        yml_path.write_text(sentinel, encoding="utf-8")

        result = _invoke(["init"], cwd=tmp_path, input="y\n")
        assert result.exit_code == 0, result.output
        assert "SENTINEL_MARKER" in yml_path.read_text(encoding="utf-8")

    def test_second_init_prompts_user(self, tmp_path):
        """Re-init must include a confirmation prompt mentioning 'already initialized'."""
        _make_git_repo(tmp_path)
        _invoke(["init"], cwd=tmp_path)
        result = _invoke(["init"], cwd=tmp_path, input="n\n")
        output_lower = result.output.lower()
        assert (
            "already" in output_lower
            or "re-run" in output_lower
            or "initialized" in output_lower
        ), f"Expected re-init prompt in output:\n{result.output}"

    def test_second_init_no_prompt_on_first_run(self, tmp_path):
        """First-time init must NOT show a confirmation prompt."""
        _make_git_repo(tmp_path)
        result = _invoke(["init"], cwd=tmp_path)
        output_lower = result.output.lower()
        assert "already" not in output_lower
        assert "re-run" not in output_lower


# ---------------------------------------------------------------------------
# AC5 — .corpus/ does not appear in the tracked file list
# ---------------------------------------------------------------------------

class TestAC5SelfExclusion:
    def test_corpus_dir_not_in_tracked_files(self, tmp_path):
        """.corpus/ contents must not appear in get_tracked_files()."""
        _make_git_repo(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        (corpus_dir / "corpus.yml").write_text("provider: gemini\n", encoding="utf-8")
        (corpus_dir / "state.json").write_text("{}", encoding="utf-8")
        (corpus_dir / "docs").mkdir()
        (corpus_dir / "docs" / "some.md").write_text("# doc", encoding="utf-8")

        config = load_config(corpus_dir / "corpus.yml")
        tracked, _ = get_tracked_files(tmp_path, config)
        tracked_strs = [str(p) for p in tracked]
        for p in tracked_strs:
            assert ".corpus" not in p, f".corpus path leaked into tracked list: {p}"

    def test_corpus_dir_excluded_from_init_output(self, tmp_path):
        """After init, the file count must exclude .corpus/ contents."""
        _make_git_repo(tmp_path)
        (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")
        result = _invoke(["init"], cwd=tmp_path)
        assert result.exit_code == 0, result.output
        match = re.search(r"Found (\d+) files?", result.output)
        assert match, f"No count found in: {result.output}"
        count = int(match.group(1))
        # Only main.py should be tracked; .corpus/ files must not inflate the count
        assert count == 1, (
            f"Expected 1 tracked file (main.py only), got {count}. "
            f"Possible .corpus/ self-inclusion. Output:\n{result.output}"
        )

    def test_always_ignore_contains_corpus_pattern(self):
        """ALWAYS_IGNORE must include a pattern covering .corpus/."""
        corpus_patterns = [p for p in ALWAYS_IGNORE if ".corpus" in p]
        assert corpus_patterns, "ALWAYS_IGNORE does not contain any .corpus pattern"

    def test_git_dir_not_in_tracked_files(self, tmp_path):
        """.git/ contents must also be excluded (sanity check alongside .corpus/)."""
        _make_git_repo(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        tracked, _ = get_tracked_files(tmp_path, config)
        for p in tracked:
            assert ".git" not in str(p), f".git path leaked into tracked list: {p}"

    def test_second_init_does_not_increase_count_from_self(self, tmp_path):
        """Running init twice must report same tracked count (no self-contamination)."""
        _make_git_repo(tmp_path)
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")

        result1 = _invoke(["init"], cwd=tmp_path)
        m1 = re.search(r"Found (\d+) files?", result1.output)
        assert m1, f"No count in first init output:\n{result1.output}"
        count1 = int(m1.group(1))

        result2 = _invoke(["init"], cwd=tmp_path, input="y\n")
        m2 = re.search(r"Found (\d+) files?", result2.output)
        assert m2, f"No count in second init output:\n{result2.output}"
        count2 = int(m2.group(1))

        assert count1 == count2, (
            f"Tracked count changed between first ({count1}) and second ({count2}) init. "
            "Likely .corpus/ self-inclusion on re-run."
        )

    def test_corpus_subfiles_individually_excluded(self, tmp_path):
        """Each file type placed inside .corpus/ must be individually excluded."""
        _make_git_repo(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)

        # Populate .corpus/ with representative files
        (corpus_dir / "state.json").write_text("{}", encoding="utf-8")
        docs = corpus_dir / "docs"
        docs.mkdir()
        (docs / "README.md").write_text("# docs", encoding="utf-8")
        changelog = corpus_dir / "changelog"
        changelog.mkdir()
        (changelog / "log.jsonl").write_text("{}\n", encoding="utf-8")

        tracked, _ = get_tracked_files(tmp_path, config)
        tracked_names = {p.name for p in tracked}
        for name in ("state.json", "README.md", "log.jsonl"):
            assert name not in tracked_names, (
                f"File '{name}' inside .corpus/ was tracked — should be excluded"
            )


# ---------------------------------------------------------------------------
# Error paths and edge cases
# ---------------------------------------------------------------------------

class TestErrorPaths:
    def test_corpus_yml_malformed_falls_back_to_defaults(self, tmp_path):
        """A corrupted corpus.yml must not crash; must fall back to defaults."""
        _make_git_repo(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        yml.write_text(":::invalid yaml:::\nignore:\n  not_a_list", encoding="utf-8")
        config = load_config(yml)
        assert "ignore" in config

    def test_load_config_missing_file_returns_defaults(self, tmp_path):
        """load_config on nonexistent path must return DEFAULT_CONFIG."""
        config = load_config(tmp_path / "nonexistent.yml")
        assert config["provider"] == DEFAULT_CONFIG["provider"]

    def test_binary_file_excluded(self, tmp_path):
        """Binary files must not be tracked."""
        _make_git_repo(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)

        binary_file = tmp_path / "image.png"
        binary_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")

        tracked, _ = get_tracked_files(tmp_path, config)
        tracked_names = [p.name for p in tracked]
        assert "image.png" not in tracked_names

    def test_lockfile_excluded_by_default(self, tmp_path):
        """*.lock files must be excluded by default corpus.yml patterns."""
        _make_git_repo(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)

        (tmp_path / "Pipfile.lock").write_text('{"_meta": {}}', encoding="utf-8")
        tracked, _ = get_tracked_files(tmp_path, config)
        tracked_names = [p.name for p in tracked]
        assert "Pipfile.lock" not in tracked_names

    def test_pyc_file_excluded(self, tmp_path):
        """*.pyc files must be excluded by default ignore patterns."""
        _make_git_repo(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)

        (tmp_path / "module.pyc").write_bytes(b"\x00\x00\x00\x00")
        tracked, _ = get_tracked_files(tmp_path, config)
        tracked_names = [p.name for p in tracked]
        assert "module.pyc" not in tracked_names

    def test_gitignored_file_excluded(self, tmp_path):
        """.gitignore patterns must be respected."""
        _make_git_repo(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)

        (tmp_path / ".gitignore").write_text("secret.txt\n", encoding="utf-8")
        (tmp_path / "secret.txt").write_text("top secret", encoding="utf-8")
        (tmp_path / "public.txt").write_text("public", encoding="utf-8")

        tracked, _ = get_tracked_files(tmp_path, config)
        tracked_names = [p.name for p in tracked]
        assert "secret.txt" not in tracked_names
        assert "public.txt" in tracked_names

    def test_unicode_filename_tracked(self, tmp_path):
        """Files with unicode names (non-ASCII) must not crash the scanner."""
        _make_git_repo(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)

        try:
            uni_file = tmp_path / "donn\u00e9es.py"
            uni_file.write_text("x = 1\n", encoding="utf-8")
            tracked, _ = get_tracked_files(tmp_path, config)
            tracked_names = [p.name for p in tracked]
            assert "donn\u00e9es.py" in tracked_names
        except (OSError, UnicodeError):
            pytest.skip("Filesystem does not support unicode filenames")

    def test_nested_node_modules_excluded(self, tmp_path):
        """node_modules/ at any depth must be excluded."""
        _make_git_repo(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)

        nm = tmp_path / "frontend" / "node_modules" / "lodash"
        nm.mkdir(parents=True)
        (nm / "lodash.js").write_text("// lodash", encoding="utf-8")
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")

        tracked, _ = get_tracked_files(tmp_path, config)
        tracked_names = [p.name for p in tracked]
        assert "lodash.js" not in tracked_names
        assert "app.py" in tracked_names

    def test_pycache_excluded(self, tmp_path):
        """__pycache__/ contents must be excluded."""
        _make_git_repo(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)

        cache_dir = tmp_path / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "module.cpython-311.pyc").write_bytes(b"\x00" * 16)

        tracked, _ = get_tracked_files(tmp_path, config)
        for p in tracked:
            assert "__pycache__" not in str(p)

    def test_write_default_config_idempotent(self, tmp_path):
        """Writing default config twice to same path must produce identical content."""
        yml = tmp_path / "corpus.yml"
        write_default_config(yml)
        first = yml.read_text(encoding="utf-8")
        write_default_config(yml)
        second = yml.read_text(encoding="utf-8")
        assert first == second

    def test_corpus_yml_custom_ignore_honoured(self, tmp_path):
        """Custom ignore patterns written to corpus.yml must be loaded and applied."""
        _make_git_repo(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        yml.write_text(
            textwrap.dedent("""\
                provider: gemini
                gemini_model: gemini-2.5-flash
                groq_model: llama-3.3-70b-versatile
                limits:
                  max_files_per_update: 50
                  max_tokens_per_call: 8192
                  max_calls_per_day: 100
                ignore:
                  - "**/*.secret"
            """),
            encoding="utf-8",
        )
        config = load_config(yml)
        (tmp_path / "hidden.secret").write_text("shh", encoding="utf-8")
        (tmp_path / "visible.py").write_text("x=1", encoding="utf-8")

        tracked, _ = get_tracked_files(tmp_path, config)
        tracked_names = [p.name for p in tracked]
        assert "hidden.secret" not in tracked_names
        assert "visible.py" in tracked_names

    def test_corpus_yml_user_cannot_override_always_ignore(self, tmp_path):
        """Even if user removes .corpus pattern from corpus.yml, ALWAYS_IGNORE still blocks it."""
        _make_git_repo(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        # Empty ignore list — user trying to unblock .corpus/
        yml.write_text(
            textwrap.dedent("""\
                provider: gemini
                gemini_model: gemini-2.5-flash
                groq_model: llama-3.3-70b-versatile
                limits:
                  max_files_per_update: 50
                  max_tokens_per_call: 8192
                  max_calls_per_day: 100
                ignore:
            """),
            encoding="utf-8",
        )
        config = load_config(yml)
        (corpus_dir / "sneak.py").write_text("evil = True\n", encoding="utf-8")

        tracked, _ = get_tracked_files(tmp_path, config)
        for p in tracked:
            assert ".corpus" not in str(p), (
                f"ALWAYS_IGNORE failed: .corpus file appeared in tracked list: {p}"
            )

    def test_tracked_files_sorted(self, tmp_path):
        """get_tracked_files must return a sorted list."""
        _make_git_repo(tmp_path)
        corpus_dir = tmp_path / ".corpus"
        corpus_dir.mkdir()
        yml = corpus_dir / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)

        for name in ["zebra.py", "alpha.py", "middle.py"]:
            (tmp_path / name).write_text("x=1\n", encoding="utf-8")

        tracked, _ = get_tracked_files(tmp_path, config)
        assert tracked == sorted(tracked), "get_tracked_files must return sorted paths"


# ---------------------------------------------------------------------------
# Config parser unit tests
# ---------------------------------------------------------------------------

class TestConfigParser:
    def test_limits_parsed_as_integers(self, tmp_path):
        yml = tmp_path / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        assert isinstance(config["limits"]["max_files_per_update"], int)
        assert isinstance(config["limits"]["max_tokens_per_call"], int)
        assert isinstance(config["limits"]["max_calls_per_day"], int)

    def test_ignore_list_parsed_as_list_of_strings(self, tmp_path):
        yml = tmp_path / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        assert isinstance(config["ignore"], list)
        assert all(isinstance(p, str) for p in config["ignore"])

    def test_provider_default_is_gemini(self, tmp_path):
        yml = tmp_path / "corpus.yml"
        write_default_config(yml)
        config = load_config(yml)
        assert config["provider"] == "gemini"

    def test_custom_provider_parsed(self, tmp_path):
        yml = tmp_path / "corpus.yml"
        yml.write_text(
            textwrap.dedent("""\
                provider: groq
                gemini_model: gemini-2.5-flash
                groq_model: llama-3.3-70b-versatile
                limits:
                  max_files_per_update: 10
                  max_tokens_per_call: 4096
                  max_calls_per_day: 50
                ignore:
                  - "**/*.pyc"
            """),
            encoding="utf-8",
        )
        config = load_config(yml)
        assert config["provider"] == "groq"
        assert config["limits"]["max_files_per_update"] == 10

    def test_comment_lines_ignored(self, tmp_path):
        """Comment lines in corpus.yml must not cause errors."""
        yml = tmp_path / "corpus.yml"
        yml.write_text(
            textwrap.dedent("""\
                # This is a comment
                provider: gemini
                # Another comment
                gemini_model: gemini-2.5-flash
                groq_model: llama-3.3-70b-versatile
                limits:
                  # nested comment
                  max_files_per_update: 50
                  max_tokens_per_call: 8192
                  max_calls_per_day: 100
                ignore:
                  # In addition to .gitignore, always ignore:
                  - "**/.corpus/**"
            """),
            encoding="utf-8",
        )
        config = load_config(yml)
        assert config["provider"] == "gemini"
        assert "**/.corpus/**" in config["ignore"]

    def test_default_config_has_expected_limits(self):
        """DEFAULT_CONFIG must have all three limit keys."""
        assert "max_files_per_update" in DEFAULT_CONFIG["limits"]
        assert "max_tokens_per_call" in DEFAULT_CONFIG["limits"]
        assert "max_calls_per_day" in DEFAULT_CONFIG["limits"]

    def test_default_ignore_contains_corpus_pattern(self):
        """Default ignore list must include .corpus pattern."""
        corpus_patterns = [p for p in DEFAULT_CONFIG["ignore"] if ".corpus" in p]
        assert corpus_patterns

    def test_default_ignore_contains_git_pattern(self):
        """Default ignore list must include .git pattern."""
        git_patterns = [p for p in DEFAULT_CONFIG["ignore"] if ".git" in p]
        assert git_patterns
