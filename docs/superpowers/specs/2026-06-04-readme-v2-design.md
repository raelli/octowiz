# README v2 — Design Spec

**Date:** 2026-06-04
**Repo:** raelli/octowiz
**Branch:** worktree-worktree-readme-v2

---

## Problem statement

The current README has three issues:

1. **Stale content** — commands, file paths, badge counts, and capability lists have drifted from the codebase. Nothing has been verified against the live repo.
2. **Poor structure** — 23 top-level sections with related content scattered across them (env vars appear in three places; setup is split across four sections; architecture and its glossary are separated by unrelated content).
3. **Mermaid diagrams** — three Mermaid blocks that render inconsistently and use a cluttered multi-color palette that doesn't match the project's visual identity.

---

## Solution

Rewrite the README with:

1. **Restructured sections** — 23 sections collapsed to 7 top-level sections following a concept-first narrative: Why → What → Setup → Use → Reference.
2. **Custom SVG diagrams** — three hand-crafted SVGs committed to `assets/diagrams/`, replacing all Mermaid blocks. Two-tone purple palette.
3. **Full verification sweep** — every claim, command, file path, env var, and link verified against the live repo before the rewrite finalises content.
4. **Best-practice polish** — proper TOC, language-tagged code blocks, consistent table formatting, no naked code dumps.

---

## Section structure (Approach B — concept-first)

### 1. Hero
- `assets/octowiz.jpeg` image, title, tagline unchanged
- Badges: license, python version, LiteLLM compatible, memory count (verify against JSON), version (from `package.json`)
- Nav links: Live overview · ÆLLI · Install · Diagnostics
- HTML TOC: `[Architecture](#architecture) · [Setup](#setup) · [Using /octowiz](#using-octowiz) · [Reference](#reference)`
- Drop `&nbsp;` between badges; use single space

### 2. Why this exists
- Keep existing prose; tighten opening paragraph from 3 sentences to 2
- Keep `> **Small context. No prompt soup.**` blockquote

### 3. Architecture
- `<img src="assets/diagrams/architecture.svg">` replaces Mermaid flowchart TD
- Component glossary table immediately below SVG (merged from current standalone section)
- Memory namespace breakdown table below glossary (merged from current standalone section)
- Raw namespace code block removed — key info promoted into the table

### 4. Setup
- Lead: "Four steps to a working /octowiz" numbered overview
- `<img src="assets/diagrams/setup-flow.svg">` at section top (new diagram)
- **Sub-section A — LiteLLM memory import:** Python import commands; clarify this is the memory layer, not the main runtime install; fix `pip install -e .` if verification shows it's stale
- **Sub-section B — Claude Code plugin:** `settings.json` block + `/plugins` install table; verify marketplace URL is live
- **Sub-section C — Daemon:** `pnpm start`; clarify Node.js daemon (not Python)
- **Sub-section D — Verify:** move curl verification commands here from orphaned "Verify" section
- Consolidated env var reference table at end (daemon vars + cache vars merged)

### 5. Using /octowiz
- `<img src="assets/diagrams/routing.svg">` replaces Mermaid flowchart LR
- A/B/C/D routing table kept
- "Retrieval per role" table folded directly below A/B/C/D table (section removed)
- "What happens when you run /octowiz?" numbered list kept
- Skill routing descriptions kept (mattpocock vs superpowers)

### 6. Reference
Sub-sections in order:
- **A2A capabilities** — table (verify against `apps/a2a-agent/dispatch.py`)
- **Memory caching** — short prose + commands table; Mermaid block replaced with prose; terminal transcript demo removed
- **Sandcastle** — kept as-is pending verification
- **Marketplace integration** — kept as-is pending verification
- **Diagnostics** — `/octowiz:octowiz-doctowiz` section moved here from orphaned position
- **Security** — kept; one redundant sentence trimmed

### 7. Attribution · License
- Unchanged

---

## SVG diagram specifications

All three SVGs use the same palette:

| Element | Value |
|---|---|
| SVG background | transparent (renders on GitHub dark `#0d1117` and light) |
| Node fill | `#13111c` |
| Node border (default) | `#4a3570` · `stroke-width="1"` |
| Node border (focal) | `#7c3aed` · `stroke-width="2"` |
| Node text (default) | `#c4b5fd` |
| Node text (focal) | `#ede9fe` · `font-weight="600"` |
| Connector lines | `#4a3570` · `stroke-width="1"` |
| Connector labels | `#6b7280` · `font-size="9–10"` |
| Arrow heads | `#4a3570` fill |
| Font family | `'SF Mono', monospace` |

### Diagram 1 — `assets/diagrams/architecture.svg`
- Placement: Architecture section
- Layout: vertical flow, 440×340px
- Nodes top to bottom: ÆLLI → Octowiz A2A Agent → **Octowiz Bridge** (focal) → LiteLLM + Skills (row)
- Connector labels: "A2A · /a2a/octowiz", "events / advice", "GET / PUT /v1/memory"

### Diagram 2 — `assets/diagrams/setup-flow.svg`
- Placement: Setup section (new, no Mermaid equivalent)
- Layout: horizontal steps, 620×90px
- Nodes left to right: 1. Import memories → 2. Install plugins → 3. Start daemon → **4. /octowiz** (focal)
- Step subtitles: "26 entries → LiteLLM", "octowiz · matt · superpowers", "pnpm start", "routes A / B / C / D"

### Diagram 3 — `assets/diagrams/routing.svg`
- Placement: Using /octowiz section
- Layout: hub and spokes, 560×240px
- Center hub: **/octowiz** (focal) with subtitle "where are you?"
- Four spokes: A · fresh idea (brainstorming), B · stress-test (grill-me), C · implement (worktrees + TDD), D · review (zoom-out + review)

---

## Verification plan

Run before finalising any content change. Each item is a discrete check.

| Check | Method |
|---|---|
| File paths referenced in README | `ls` / `find` against repo filesystem |
| Commands (pnpm, node, make, python) | Dry-run or `--help` flag |
| Env var names | `grep` across `src/`, `apps/`, hooks source |
| A2A capability list (10 entries) | Compare against `apps/a2a-agent/dispatch.py` |
| Memory count badge (26) | Count entries in `litellm_agent_memories_matt_pocock_ai_coding.json` |
| Plugin names in marketplace | Fetch marketplace URL |
| `octowiz-cache` command list | `octowiz-cache --help` |
| Sandbox image ref | Check `containers/` or Makefile |
| `packages/marketplace_client` CLI | `python -m packages.marketplace_client.cli --help` |
| `/a2a/dev-advisor` alias | Check `apps/a2a-agent/` routing |
| `import_litellm_memories.py` | File exists + `--help` |
| `pip install -e .` — still valid? | Check `setup.py` / `pyproject.toml` vs `package.json` |
| Daemon env var table (8 vars) | Cross-ref `src/daemon.js` and hooks |
| Doctowiz command path | Verify `apps/doctowiz/index.js` exists |
| External links | HTTP HEAD request per URL |

**Expected findings (pre-flagged for the verifier):**
- `pip install -e .` is likely stale — repo is primarily Node.js; may need splitting into separate Python and Node install paths
- `python -m pytest tests/ -v` — main suite is now `pnpm test`; Python tests live under `apps/a2a-agent/`
- Memory count badge "26" — must match JSON entry count
- `/a2a/dev-advisor` alias — verify still registered in dispatch

---

## Best practices applied

- Every section has a one-line description above its first code block (no naked code dumps)
- All code blocks have language tags (`bash`, `json`, `text`)
- Table column headers are sentence-case
- Proper HTML TOC in hero section with anchor links to all 4 main sections
- No section named "Contents" (GitHub auto-generates one; the explicit list is redundant)
- `.superpowers/` added to `.gitignore`

---

## Files created / modified

| File | Action |
|---|---|
| `README.md` | Rewritten |
| `assets/diagrams/architecture.svg` | Created |
| `assets/diagrams/setup-flow.svg` | Created |
| `assets/diagrams/routing.svg` | Created |
| `assets/diagrams/` directory | Created |
| `.gitignore` | Add `.superpowers/` entry |
| `docs/superpowers/specs/2026-06-04-readme-v2-design.md` | This file |

---

## Out of scope

- Changes to any source code, hooks, or tests
- Changes to the A2A agent, daemon, or Python packages
- Documentation other than `README.md`
