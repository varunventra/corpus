# Corpus

Living second representation of your codebase — per-file docs, a structural dependency graph, and six MCP query tools for Claude Code.

## Install

```bash
pip install -e .
```

Requires Python 3.11+.

## Usage

```bash
# Inside any project directory:
corpus init       # scaffold .corpus/, scan files, print summary
corpus update     # (Phase 1b+) regenerate docs for changed files
```

## API keys

Corpus uses free-tier LLM providers. Set these environment variables before running `corpus update`:

| Variable | Provider | Get one at |
|---|---|---|
| `GEMINI_API_KEY` | Gemini 2.5 Flash (primary) | https://aistudio.google.com/app/apikey |
| `GROQ_API_KEY` | Groq / Llama 3.3 70B (fallback on rate limit) | https://console.groq.com/keys |

Neither key is required for `corpus init`.

## Claude Code integration

After running `corpus init`, register the MCP server with Claude Code:

```bash
claude mcp add corpus -- python -m corpus.mcp
```

## Configuration

`corpus init` writes `.corpus/corpus.yml` with defaults. Edit it to change the provider, model, rate limits, or ignore patterns.
