"""Tree-sitter parsing: extract symbols and import paths from source files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Language instances are expensive to construct; build them once at module load.
_PARSERS: dict[str, Any] = {}  # lang_name -> tree_sitter.Parser
_LANGS: dict[str, Any] = {}    # lang_name -> tree_sitter.Language


def _get_parser(lang: str):  # type: ignore[return]
    """Return a cached Parser for the given language name, or None."""
    if lang in _PARSERS:
        return _PARSERS[lang]

    try:
        from tree_sitter import Language, Parser  # type: ignore

        if lang == "python":
            import tree_sitter_python as mod  # type: ignore
            language_obj = Language(mod.language())
        elif lang == "javascript":
            import tree_sitter_javascript as mod  # type: ignore
            language_obj = Language(mod.language())
        elif lang == "typescript":
            import tree_sitter_typescript as mod  # type: ignore
            language_obj = Language(mod.language_typescript())
        elif lang == "tsx":
            import tree_sitter_typescript as mod  # type: ignore
            language_obj = Language(mod.language_tsx())
        else:
            _PARSERS[lang] = None
            return None

        parser = Parser(language_obj)
        _PARSERS[lang] = parser
        _LANGS[lang] = language_obj
        return parser

    except Exception:  # noqa: BLE001  # any import/init failure → graceful fallback
        _PARSERS[lang] = None
        return None


def _ext_to_lang(path: Path) -> str | None:
    ext = path.suffix.lower()
    return {
        ".py": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
    }.get(ext)


def parse_file(path: Path) -> dict[str, Any]:
    """
    Parse a single file and return its language, symbols, and import paths.

    Returns:
        {
            "lang": str | None,
            "symbols": list[str],   # exported/top-level names
            "imports": list[str],   # module specifiers (e.g. "os", "corpus.scaffold")
        }
    """
    lang = _ext_to_lang(path)
    if lang is None:
        return {"lang": None, "symbols": [], "imports": []}

    parser = _get_parser(lang)
    if parser is None:
        return {"lang": lang, "symbols": [], "imports": []}

    try:
        src = path.read_bytes()
    except OSError:
        return {"lang": lang, "symbols": [], "imports": []}

    tree = parser.parse(src)
    root = tree.root_node

    if lang == "python":
        return {"lang": "python", **_parse_python(root)}
    elif lang in ("javascript", "typescript", "tsx"):
        display_lang = lang  # keep "typescript"/"tsx" as-is
        return {"lang": display_lang, **_parse_js_ts(root)}

    return {"lang": lang, "symbols": [], "imports": []}


# ---------------------------------------------------------------------------
# Python extraction
# ---------------------------------------------------------------------------

def _parse_python(root) -> dict[str, list[str]]:  # type: ignore[return]
    symbols: list[str] = []
    imports: list[str] = []

    for node in root.children:
        ntype = node.type

        if ntype == "function_definition":
            name = node.child_by_field_name("name")
            if name:
                symbols.append(name.text.decode())

        elif ntype == "class_definition":
            name = node.child_by_field_name("name")
            if name:
                symbols.append(name.text.decode())

        elif ntype == "decorated_definition":
            # decorated function or class
            inner = node.child_by_field_name("definition")
            if inner and inner.type in ("function_definition", "class_definition"):
                name = inner.child_by_field_name("name")
                if name:
                    symbols.append(name.text.decode())

        elif ntype == "expression_statement":
            # Catch __all__ = [...]
            assign = _first_child_of_type(node, "assignment")
            if assign:
                lhs = assign.child_by_field_name("left")
                rhs = assign.child_by_field_name("right")
                if (
                    lhs is not None
                    and lhs.type == "identifier"
                    and lhs.text == b"__all__"
                    and rhs is not None
                    and rhs.type == "list"
                ):
                    for item in rhs.children:
                        if item.type == "string":
                            raw = item.text.decode().strip("\"'")
                            if raw and raw not in symbols:
                                symbols.append(raw)

        elif ntype == "import_statement":
            # import os  /  import os, sys
            for child in node.children:
                if child.type in ("dotted_name", "aliased_import"):
                    name_node = (
                        child.child_by_field_name("name") or child
                        if child.type == "aliased_import"
                        else child
                    )
                    imports.append(name_node.text.decode())

        elif ntype == "import_from_statement":
            # from pathlib import Path  /  from . import foo  /  from .utils import helper
            module = node.child_by_field_name("module_name")
            if module:
                # module_name is either dotted_name (absolute) or relative_import (relative).
                # In both cases .text gives us the right raw text: "pathlib", ".utils", etc.
                raw = module.text.decode()
                # When the specifier is bare dots only (e.g. "." or ".."), each imported
                # name needs its own specifier so the resolver can distinguish them.
                # e.g. `from . import utils, helper` → [".utils", ".helper"]
                # e.g. `from .. import core` → ["..core"]
                # Without this, `"."` resolves to the package __init__.py (the importer
                # itself) and the self-import guard drops all edges.
                if raw.lstrip(".") == "":
                    # bare dots — synthesise one specifier per imported name
                    # e.g. `from . import utils, helper` → [".utils", ".helper"]
                    # e.g. `from .. import core` → ["..core"]
                    for idx, child in enumerate(node.children):
                        if node.field_name_for_child(idx) == "name":
                            imports.append(raw + child.text.decode())
                else:
                    imports.append(raw)

    # Deduplicate while preserving insertion order
    symbols = list(dict.fromkeys(symbols))
    imports = list(dict.fromkeys(imports))

    return {"symbols": symbols, "imports": imports}


def _first_child_of_type(node, type_name: str):
    for child in node.children:
        if child.type == type_name:
            return child
    return None


# ---------------------------------------------------------------------------
# JavaScript / TypeScript extraction
# ---------------------------------------------------------------------------

def _parse_js_ts(root) -> dict[str, list[str]]:
    symbols: list[str] = []
    imports: list[str] = []

    for node in root.children:
        ntype = node.type

        if ntype == "import_statement":
            # import React from 'react'
            # import { foo } from './utils'
            source = node.child_by_field_name("source")
            if source:
                raw = source.text.decode().strip("\"'`")
                imports.append(raw)

        elif ntype == "export_statement":
            _extract_js_export(node, symbols)

    return {"symbols": symbols, "imports": imports}


def _extract_js_export(node, symbols: list[str]) -> None:
    """Pull the exported name(s) out of an export_statement node."""
    for child in node.children:
        ctype = child.type

        if ctype in ("function_declaration", "generator_function_declaration"):
            name = child.child_by_field_name("name")
            if name:
                symbols.append(name.text.decode())

        elif ctype == "class_declaration":
            name = child.child_by_field_name("name")
            if name:
                symbols.append(name.text.decode())

        elif ctype == "lexical_declaration":
            # export const FOO = ...  /  export let bar = ...
            for decl in child.children:
                if decl.type == "variable_declarator":
                    name = decl.child_by_field_name("name")
                    if name:
                        symbols.append(name.text.decode())

        elif ctype == "variable_declaration":
            for decl in child.children:
                if decl.type == "variable_declarator":
                    name = decl.child_by_field_name("name")
                    if name:
                        symbols.append(name.text.decode())
