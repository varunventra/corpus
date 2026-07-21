"""LLM wrapper: Gemini 2.5 Flash primary, Groq fallback on HTTP 429."""

from __future__ import annotations

import os
import re
import time
import warnings

import requests

# Gemini free tier: 15 requests/minute. Enforce 4.5s minimum gap between calls.
_GEMINI_MIN_INTERVAL = 4.5
_last_gemini_call: float = 0.0

SYSTEM_PROMPT = """\
You are a senior software engineer writing internal documentation for a codebase.
Your output will be stored as a plain markdown file and read by both developers and AI agents.

Rules:
- Write only what is directly supported by the source code provided. Do not speculate.
- Be specific. Name the actual functions, classes, and modules involved.
- Gotchas must be genuinely non-obvious. Do not list things any reader can see in the first two lines.
- Importance must reflect this file's role in THIS repository, not generic importance of its pattern.
- Output exactly the five sections below, in order, with exactly these H2 headings. No other text before, between, or after them.

## Purpose
## Symbols
## Connections
## Gotchas
## Importance"""

_GEMINI_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

_IMPORTANCE_RE = re.compile(r"Rating:\s*([1-5])\s*/\s*5", re.IGNORECASE)


class LLMError(Exception):
    """Raised when all LLM providers are exhausted or all responses are malformed."""


def _is_malformed(text: str) -> bool:
    """Return True if the response is missing required section headings.

    Checks only structural completeness (presence of the five H2 headings).
    The Rating: N/5 line in ## Importance is desirable but not structural —
    a missing rating simply yields importance=None from extract_importance(),
    which is handled gracefully by callers.
    """
    required = ["## Purpose", "## Symbols", "## Connections", "## Gotchas", "## Importance"]
    return not all(heading in text for heading in required)


def _call_gemini(
    prompt: str, max_tokens: int, model: str
) -> tuple[str | None, int | None]:
    """
    Call Gemini. Returns (response_text, http_status).
    response_text is None on non-200 responses.
    """
    global _last_gemini_call
    elapsed = time.time() - _last_gemini_call
    if elapsed < _GEMINI_MIN_INTERVAL:
        time.sleep(_GEMINI_MIN_INTERVAL - elapsed)
    _last_gemini_call = time.time()

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None, None

    url = _GEMINI_URL_TEMPLATE.format(model=model)
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    resp = requests.post(
        url,
        json=body,
        headers={"x-goog-api-key": api_key},
        timeout=120,
    )
    if resp.status_code == 429:
        return None, 429
    if resp.status_code != 200:
        return None, resp.status_code

    data = resp.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text, 200
    except (KeyError, IndexError, TypeError):
        return None, 200


def _call_groq(prompt: str, max_tokens: int, model: str) -> str | None:
    """
    Call Groq. Returns response text or None on failure.
    """
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return None

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
    }
    resp = requests.post(
        _GROQ_URL,
        json=body,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=120,
    )
    if resp.status_code != 200:
        return None

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None


def generate(prompt: str, max_tokens: int, config: dict | None = None) -> str:
    """
    Generate a doc string using Gemini (primary), falling back to Groq on 429.

    Model names are read from config keys 'gemini_model' and 'groq_model'.
    Retries once on malformed response (missing required section headings).
    Raises LLMError only when both providers fail or both responses are malformed.
    """
    cfg = config or {}
    gemini_model: str = cfg.get("gemini_model", "gemini-flash-lite-latest")
    groq_model: str = cfg.get("groq_model", "llama-3.3-70b-versatile")

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    groq_key = os.environ.get("GROQ_API_KEY", "")

    if not gemini_key and not groq_key:
        raise LLMError("No API keys available: set GEMINI_API_KEY or GROQ_API_KEY.")

    # --- Attempt 1: Gemini ---
    use_groq_fallback = False
    gemini_text: str | None = None

    if gemini_key:
        text, status = _call_gemini(prompt, max_tokens, gemini_model)
        if status == 429:
            use_groq_fallback = True
        elif text is not None and not _is_malformed(text):
            return text
        elif text is not None:
            # Malformed — one retry on Gemini
            text2, status2 = _call_gemini(prompt, max_tokens, gemini_model)
            if text2 is not None and not _is_malformed(text2):
                return text2
            # Both Gemini attempts malformed; fall through to Groq if available
            gemini_text = text  # keep first response as last resort
            use_groq_fallback = True
        else:
            # Non-200 non-429 error from Gemini — try Groq
            use_groq_fallback = True
    else:
        use_groq_fallback = True

    # --- Attempt 2: Groq ---
    if use_groq_fallback and groq_key:
        groq_text = _call_groq(prompt, max_tokens, groq_model)
        if groq_text is not None and not _is_malformed(groq_text):
            return groq_text
        if groq_text is not None:
            # Malformed — one retry on Groq
            groq_text2 = _call_groq(prompt, max_tokens, groq_model)
            if groq_text2 is not None and not _is_malformed(groq_text2):
                return groq_text2
            # Both Groq attempts malformed
            # If we have any text at all, the doc is still useful — caller handles importance=None
            if groq_text2 is not None:
                warnings.warn(
                    "LLM response malformed after retry (missing ## Purpose or Rating). "
                    "Storing doc text but importance will be null.",
                    stacklevel=2,
                )
                return groq_text2
            if groq_text is not None:
                warnings.warn(
                    "LLM response malformed after retry (missing ## Purpose or Rating). "
                    "Storing doc text but importance will be null.",
                    stacklevel=2,
                )
                return groq_text

    # --- Total failure ---
    raise LLMError(
        "All LLM providers exhausted or all responses malformed. "
        "Check GEMINI_API_KEY / GROQ_API_KEY and network connectivity."
    )


def extract_importance(response_text: str) -> int | None:
    """Return the importance integer (1-5) from the LLM response, or None if not found."""
    match = _IMPORTANCE_RE.search(response_text)
    if match:
        return int(match.group(1))
    return None
