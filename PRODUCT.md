# Corpus — Product Document

**v1 · Type:** Developer tool, personal & internal use
**Form:** CLI + MCP server + live graph
**Status:** Design locked, pre-build

> A living second representation of your codebase — one that keeps itself current, that you can see, and that your coding agent can think with.

---

## 01 · The Problem

Every project carries a second, invisible artifact: the understanding of how it works. Today that artifact lives in two fragile places — documentation nobody maintains, and the fading memory of whoever wrote the code.

### Part one · Documentation rots
Writing docs is tedious. Keeping them true is worse. Whether you document as you go or all at the end, it's manual work that competes with building. And it's needed twice over — readable docs for humans, and structured context for AI agents working on the codebase. Both go stale the moment the code changes, and nobody goes back to fix them.

### Part two · Comprehension lags
Keeping up with your own codebase — and your agent — is hard. As Claude Code works, it changes things faster than you can follow. And when you ask an agent about your project, it explores your files blind, every single session. There's no persistent, always-current picture of the project that humans can navigate visually and agents can query precisely.

---

## 02 · The Idea

Corpus is a second representation of your codebase — documentation, structure, and history — that regenerates from the code itself. You never maintain it. You run one command, and it catches up to reality.

It serves two audiences from one source of truth. For you: an Obsidian-style visual map of your project, where every node opens into plain-language docs. For your agent: a set of precise query tools, so it understands your project instantly instead of crawling it blind.

> **Design principle:** Structure is computed. Meaning is generated. The map of the project — files, folders, connections — is derived mechanically from the code, so it can never drift or hallucinate. Only the explanations are written by AI, in the one place where being wrong is cheap to fix.

> **Honesty principle:** Corpus always tells you what it doesn't know. Anything that changed since the last update is visibly flagged as **stale** — in the graph, and to the agent. A corpus that admits its blind spots is one you can trust.

---

## 03 · How It Works — Three Surfaces, One Brain

Built in this order, because each one stands on the last.

### 1. The Engine
*A CLI — run `corpus update` whenever you choose.*

The heart of the system. After a feature, after a session, whenever you want — one command. The engine looks at what changed since the last update, re-reads only those parts of the code, and patches exactly the documentation they affect. Out comes an updated set of per-module docs and a fresh map of the project's structure.

- Docs exist at two zoom levels: every file gets its own, every folder gets a rollup summary.
- The map is always derived from the code — imports, connections, structure — never maintained by hand, so it can't go stale.
- Each doc carries an importance rating, so the interface can foreground what matters and tuck away what doesn't.
- First version regenerates everything; updating only what changed is the core engineering challenge, and it comes second.

### 2. The Bridge
*An MCP server — Corpus, plugged into Claude Code.*

Corpus becomes a native set of tools inside Claude Code: project overview, per-module docs, symbol relations, recent changes. Instead of grep-crawling your repo every session, the agent asks Corpus and gets precise answers — fewer tool calls, faster work, less guessing.

- Creates a self-reinforcing loop: the agent uses Corpus → codes faster → `corpus update` absorbs the changes → the next session is smarter.
- No custom chat interface is built. Claude Code **is** the chat — asking your terminal is asking Corpus.
- Every query the agent makes is broadcast as an event — which powers the third surface.

### 3. The Window
*A live graph viewer — watch your project, and your agent, think.*

An Obsidian-style force-directed graph of your codebase. Folders are nodes; click to unfold them into files; click any node to read its docs. Important files are prominent, minor ones tuck behind a "show all" — the graph breathes at the level you care about.

- **The live agent monitor:** as Claude Code queries Corpus, the nodes it touches light up in real time. You watch the agent navigate your project while it works — a window into its head.
- Anything changed since the last update glows **amber** — stale, and honest about it.

---

## 04 · The Experience — A Session with Corpus

1. **You start work.** You open Claude Code on your project. Corpus is already connected — the agent greets your first request with real knowledge of the architecture, not a cold crawl of your files.
2. **The agent works, you watch.** On your second screen, the graph is open. As the agent reasons about the auth flow, the auth nodes glow and the path it consults traces across the map. You can see exactly which parts of your project it's thinking with.
3. **Code changes, Corpus admits it.** The agent edits three files. Their nodes flip to amber — Corpus marking, honestly, that its picture of them is now behind reality.
4. **One command, caught up.** You run `corpus update`. The engine reads the diff, patches the affected docs, refreshes the map. Amber turns back to teal. Corpus is current again — and the next session starts smarter than this one did.
5. **Any time later.** You open the graph just to look — to browse the docs, to remember how a module works, to see the shape of what you've built. Your project, finally visible.

---

## 05 · Deliberate Omissions

Every one of these was on the table. Cutting them is what makes the product finishable — and better.

| Cut | Why |
|---|---|
| **Vector search / RAG** | Wrong retrieval model for code. Codebases have exact structure — imports, calls, symbols — and Corpus uses it directly. Similarity search would add a fourth, fuzziest copy of the codebase that needs its own syncing. Precision beats vibes. |
| **A custom chat UI** | Claude Code already is a world-class chat interface with Corpus plugged in. Building a second one would be weeks of redundant work producing a worse version. |
| **Auto-triggering watchers** | Updating on every keystroke or commit sounds magical and behaves annoyingly. A deliberate command keeps the developer in control; automation can come later as a convenience, not a foundation. |
| **AI-decided structure** | The LLM never chooses what counts as a module or where boundaries sit — that judgment drifts between runs and corrupts history. AI writes the meaning; deterministic rules build the structure. Always. |

---

## 06 · Roadmap — Five Milestones, Each Demoable

| Milestone | Name | What it delivers |
|---|---|---|
| **M1** | The static brain | Point the CLI at a repo → per-file docs, folder rollups, and the structural map. Full regeneration each run. Ugly but real. |
| **M2** | Incremental updates | Only what changed gets re-documented — including docs affected indirectly through the dependency map. The hardest engineering in the project, and the reason updates stay fast and cheap. |
| **M3** | The bridge | The MCP server connects Corpus to Claude Code. Then a week of daily use — dogfooding will reshape the doc format better than any planning. |
| **M4** | The window, static | The graph renders. Folders unfold, nodes open docs, importance shapes the view. |
| **M5** | The window, alive | The live wire — agent queries stream to the graph, nodes light up as it thinks. The demo. |

**After the core:** per-module changelog ("what changed in the scraper this month") · "Explain this diff" — plain-English summary of uncommitted work · health overlays (churn, last-touched) · onboarding tour mode.

---

## 07 · Honest Framing — What This Is, and Isn't

- **Not a novel category.** Comparable open-source tools exist and thrive. This is built for learning, for personal use, and for internal use — with reference implementations studied, not ignored. The live agent monitor is the one surface where this goes further than what's out there.
- **Not a cure for not reading code.** Corpus makes understanding cheap; it can't make it happen. A summary is a door to comprehension, not a substitute for walking through it.
- **Not a production service.** One developer, their repos, their machine. Free-tier AI, local files, no accounts, no cloud.
