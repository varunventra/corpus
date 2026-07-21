"""Read and write corpus.yml; supply defaults."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# PyYAML is NOT a dependency — we write YAML manually for the default config
# and read it with a minimal parser sufficient for our controlled schema.
# This avoids adding pyyaml to dependencies for Phase 1a.

DEFAULT_CONFIG: dict[str, Any] = {
    "provider": "gemini",
    "gemini_model": "gemini-flash-lite-latest",
    "groq_model": "llama-3.3-70b-versatile",
    "limits": {
        "max_files_per_update": 50,
        "max_tokens_per_call": 8192,
        "max_calls_per_day": 100,
    },
    "ignore": [
        "**/.corpus/**",
        "**/node_modules/**",
        "**/__pycache__/**",
        "**/*.pyc",
        "**/.git/**",
        "**/dist/**",
        "**/build/**",
        "**/*.lock",
        "**/package-lock.json",
        "**/yarn.lock",
        "**/migrations/**",
        "**/*.min.js",
        "**/*.min.css",
        "**/*.map",
    ],
}

_DEFAULT_CORPUS_YML = """\
provider: gemini
gemini_model: gemini-flash-lite-latest
groq_model: llama-3.3-70b-versatile
limits:
  max_files_per_update: 50
  max_tokens_per_call: 8192
  max_calls_per_day: 100
ignore:
  # In addition to .gitignore, always ignore:
  - "**/.corpus/**"
  - "**/node_modules/**"
  - "**/__pycache__/**"
  - "**/*.pyc"
  - "**/.git/**"
  - "**/dist/**"
  - "**/build/**"
  - "**/*.lock"
  - "**/package-lock.json"
  - "**/yarn.lock"
  - "**/migrations/**"
  - "**/*.min.js"
  - "**/*.min.css"
  - "**/*.map"
"""


def write_default_config(corpus_yml_path: Path) -> None:
    """Write the default corpus.yml to disk."""
    corpus_yml_path.write_text(_DEFAULT_CORPUS_YML, encoding="utf-8")


def load_config(corpus_yml_path: Path) -> dict[str, Any]:
    """
    Parse corpus.yml using the stdlib only.

    We only need to extract the `ignore` list and `limits` block.
    The format is controlled (we wrote it), so a hand-rolled parser is safe.
    Falls back to DEFAULT_CONFIG values for any key not found.
    """
    if not corpus_yml_path.exists():
        return DEFAULT_CONFIG.copy()

    text = corpus_yml_path.read_text(encoding="utf-8")
    return _parse_corpus_yml(text)


def _parse_corpus_yml(text: str) -> dict[str, Any]:
    """
    Minimal YAML parser for corpus.yml's controlled schema.

    Handles:
    - top-level scalar keys (provider, gemini_model, groq_model)
    - nested scalar block (limits:)
    - sequence block (ignore:) with quoted or unquoted string items
    - comment lines (# ...)
    """
    config: dict[str, Any] = {
        "provider": DEFAULT_CONFIG["provider"],
        "gemini_model": DEFAULT_CONFIG["gemini_model"],
        "groq_model": DEFAULT_CONFIG["groq_model"],
        "limits": dict(DEFAULT_CONFIG["limits"]),
        "ignore": list(DEFAULT_CONFIG["ignore"]),
    }

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        # Top-level key: value  (no leading whitespace)
        if not line[0].isspace() and ":" in stripped:
            key, _, rest = stripped.partition(":")
            key = key.strip()
            rest = rest.strip()

            if key == "provider":
                config["provider"] = rest
            elif key == "gemini_model":
                config["gemini_model"] = rest
            elif key == "groq_model":
                config["groq_model"] = rest
            elif key == "limits":
                # Read indented sub-block
                i += 1
                while i < len(lines):
                    sub = lines[i]
                    sub_stripped = sub.strip()
                    if not sub_stripped or sub_stripped.startswith("#"):
                        i += 1
                        continue
                    if sub[0].isspace() and ":" in sub_stripped:
                        sk, _, sv = sub_stripped.partition(":")
                        sk = sk.strip()
                        sv = sv.strip()
                        try:
                            config["limits"][sk] = int(sv)
                        except ValueError:
                            pass
                        i += 1
                    else:
                        break  # back to outer loop without incrementing
                continue
            elif key == "ignore":
                # Read sequence items
                items: list[str] = []
                i += 1
                while i < len(lines):
                    sub = lines[i]
                    sub_stripped = sub.strip()
                    if not sub_stripped or sub_stripped.startswith("#"):
                        i += 1
                        continue
                    if sub_stripped.startswith("- "):
                        item = sub_stripped[2:].strip().strip('"').strip("'")
                        items.append(item)
                        i += 1
                    else:
                        break
                config["ignore"] = items
                continue

        i += 1

    return config
