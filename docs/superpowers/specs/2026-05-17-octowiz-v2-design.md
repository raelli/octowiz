# Octowiz v2 Design Spec

**Date:** 2026-05-17
**Status:** Approved for implementation

---

## Context

Octowiz v1 is a curated 24-memory pack for LiteLLM Proxy `/v1/memory` with a working importer. It holds AI coding operating doctrine outside the system prompt so agents fetch only what is relevant to their current role and phase.

v2 evolves it from an import pack into a working Claude Code integration. The addition is a coordinator skill (`/octowiz`) that reads LiteLLM memories at runtime, detects where the developer is in the workflow, and routes to the right installed skill combination. All skills are already served via the integrahub Skills Hub at `https://llm.integrahub.de/claude-code/marketplace.json`.

**Out of scope for v2:** LiteLLM pre-call hook, A2A agent servers. These belong to a separate project once the Claude Code integration is proven.

---

## Goals

- One `/octowiz` entry point covers the full development lifecycle
- Combined workflow uses the best skill from each library at each phase — not two separate workflows
- Any GitHub repo gains the full workflow by adding `LITELLM_API_KEY` to `~/.claude/settings.json` once
- Public OSS users can fork, import with their own namespace, and get the same result
- Importer is production-grade: schema validation, `--namespace` rewriting, tests

---

## Architecture

```
Developer in Claude Code
  │
  │  /octowiz
  ▼
skills/octowiz-workflow/skill.md        ← NEW coordinator skill
  ├── reads CLAUDE.md, README, git state
  ├── fetches memories via GET /v1/memory (LITELLM_BASE_URL + LITELLM_API_KEY)
  ├── uses retrieval contract (memory entry #25) to filter by phase
  └── routes to installed skills (all served via integrahub marketplace)

LiteLLM Proxy (llm.integrahub.de)
  └── /v1/memory  — 26 entries (24 doctrine + retrieval contract + skills-hub routing)

integrahub Skills Hub
  └── /claude-code/marketplace.json  — superpowers, mattpo-skills, antfu-skills
```

### Developer setup (once, not per repo)

```json
// ~/.claude/settings.json
{
  "env": {
    "LITELLM_BASE_URL": "https://llm.integrahub.de",
    "LITELLM_API_KEY": "sk-..."
  },
  "extraKnownMarketplaces": {
    "litellm": {
      "source": "url",
      "url": "https://llm.integrahub.de/claude-code/marketplace.json"
    }
  }
}
```

Repos ship `.env.example` as a fallback hint for new developers not yet using global settings:

```bash
# .env.example — optional if LITELLM_API_KEY is set in ~/.claude/settings.json
LITELLM_API_KEY=sk-your-integrahub-key
```

---

## Coordinator Skill — `/octowiz`

File: `skills/octowiz-workflow/skill.md`

### Entry point

On invocation the skill:
1. Reads project setup: CLAUDE.md, README, open issues, current branch, git status
2. Fetches memories from `$LITELLM_BASE_URL/v1/memory` using the retrieval contract (key `team:allspark:config:retrieval-contract`)
3. Uses the fetched memories to inform routing decisions
4. Presents the starting-point question:

```
Where are you starting from?

A) Fresh idea — no plan yet
   → brainstorming → grill-with-docs → to-prd → writing-plans → to-issues → triage

B) I have a plan to stress-test
   → grill-me → to-prd → writing-plans → to-issues → triage

C) Plan exists — ready to implement
   → using-git-worktrees → TDD → executing-plans

D) Code done — need review
   → zoom-out → requesting-code-review → receiving-code-review → verification-before-completion
```

Smart default: if open issues exist and a feature branch is active → suggest C. If the repo has no issues and no prior plan → suggest A. User can always override.

### Phase 0 — Repo setup (one-time)

`mattpo:setup-matt-pocock-skills`

Sets up CLAUDE.md with issue tracker config (GitHub / GitLab / local markdown), triage label vocabulary, and domain doc layout. Required before `to-prd`, `to-issues`, `triage`, `diagnose`, `tdd`, `improve-codebase-architecture`, `zoom-out` work correctly. The coordinator checks for this block in CLAUDE.md and prompts to run setup if missing.

### Phase 1 — Align

| Skill | Source | Purpose |
|---|---|---|
| `brainstorming` | superpowers | Broad exploration. Surfaces hidden requirements, walks design options, produces a written spec. Strong structured entry for fresh work. Ends by invoking `writing-plans`. |
| `grill-with-docs` | mattpo | Challenges the plan against the existing domain model. Sharpens terminology, updates CONTEXT.md and ADRs inline. Run after brainstorming when an existing codebase with domain docs is present. |
| `grill-me` | mattpo | Entry point B only. Relentless one-question-at-a-time interview for stress-testing a plan the developer already has. Walks every branch of the decision tree before moving to planning. |

### Phase 2 — Plan

| Skill | Source | Purpose |
|---|---|---|
| `writing-plans` | superpowers | Converts approved spec into concrete implementation tasks. Already invoked at end of `brainstorming`; can run standalone. |
| `to-prd` | mattpo | Synthesises current conversation context into a formal PRD and publishes to the issue tracker. Does NOT interview — pure synthesis from what alignment established. |
| `to-issues` | mattpo | Breaks PRD into independently-grabbable vertical slice issues using tracer-bullet slicing. Creates the dependency-aware kanban structure. |
| `triage` | mattpo | Classifies issues as HITL or AFK. Writes agent briefs for AFK tasks ready for autonomous implementation. |

### Phase 3 — Implement

| Skill | Source | Purpose |
|---|---|---|
| `using-git-worktrees` | superpowers | Isolated workspace before touching code. Ensures a clean baseline. |
| `test-driven-development` | superpowers | TDD discipline and structure: red/green/refactor loop, strict methodology. |
| `tdd` | mattpo | Technical TDD depth: deep modules, mocking at system boundaries only, interface design for testability. Used alongside `test-driven-development`, not instead of it. |
| `executing-plans` | superpowers | Execute the written plan in a separate context window with review checkpoints. |
| `prototype` | mattpo | Throwaway exploration — logic prototype (terminal app) or UI prototype (multiple variants). Use before committing when the design needs to be felt out. |
| `diagnose` | mattpo | Disciplined debugging: reproduce → minimise → hypothesise → instrument → fix → regression-test. |

### Phase 4 — Review

| Skill | Source | Purpose |
|---|---|---|
| `zoom-out` | mattpo | Directive to step back and understand broader context before reviewing. |
| `improve-codebase-architecture` | mattpo | Find deepening opportunities, architecture improvements. Runs against domain language from CONTEXT.md and ADRs. |
| `requesting-code-review` | superpowers | Formal review request with full context package. |
| `receiving-code-review` | superpowers | Process review feedback systematically. |
| `verification-before-completion` | superpowers | Evidence-before-assertions gate. Must pass before claiming work done or creating PR. |

### Phase 5 — Finish

| Skill | Source | Purpose |
|---|---|---|
| `finishing-a-development-branch` | superpowers | Structured options for merge, PR, or cleanup. Guides the final integration decision. |
| `handoff` | mattpo | Compact context transfer to next session or next agent. |

---

## Memory Changes

### Entry #25 — Retrieval contract

Key: `team:allspark:config:retrieval-contract`

A JSON value mapping each starting point to the memory keys the coordinator fetches for that route. The coordinator reads this entry first on every invocation — one call that tells it everything it needs.

```json
{
  "entry_points": {
    "A_fresh": [
      "team:allspark:playbook:ai-coding-workflow:overview",
      "team:allspark:playbook:ai-coding-workflow:grill-me-alignment",
      "team:allspark:playbook:ai-coding-workflow:context-smart-zone",
      "team:allspark:skills:matt-pocock:ai-engineering",
      "team:allspark:skills:obra-superpowers:agent-methodology",
      "team:allspark:skills:integrahub:skills-hub"
    ],
    "B_stress_test": [
      "team:allspark:playbook:ai-coding-workflow:grill-me-alignment",
      "team:allspark:playbook:ai-coding-workflow:prd-destination-document",
      "team:allspark:skills:matt-pocock:ai-engineering"
    ],
    "C_implement": [
      "team:allspark:playbook:ai-coding-workflow:ralph-loop",
      "team:allspark:playbook:ai-coding-workflow:tdd-feedback-loops",
      "team:allspark:playbook:ai-coding-workflow:hitl-vs-afk",
      "team:allspark:playbook:ai-coding-workflow:deep-modules",
      "team:allspark:skills:matt-pocock:ai-engineering",
      "team:allspark:skills:obra-superpowers:agent-methodology"
    ],
    "D_review": [
      "team:allspark:playbook:ai-coding-workflow:fresh-context-review",
      "team:allspark:playbook:ai-coding-workflow:push-pull-standards",
      "team:allspark:skills:obra-superpowers:agent-methodology"
    ]
  }
}
```

### Entry #26 — integrahub Skills Hub routing

Key: `team:allspark:skills:integrahub:skills-hub`

Describes the integrahub Skills Gateway as the primary distribution point for all registered skills. Includes the `extraKnownMarketplaces` install snippet and the full list of available skill packages so agents can surface the install path to developers who haven't set it up yet.

---

## Importer Improvements

### Schema validation

Added to `import_litellm_memories.py` before the import loop. Fails fast with a clear error rather than silently importing malformed entries.

Required fields: `key` (string), `value` (string)
Optional recommended fields: `metadata.version`, `metadata.agent_roles` (array)

```
ERROR: Entry 3 missing required field 'value'
ERROR: Entry 7 'key' must be a string, got int
```

### `--namespace` flag

Rewrites `team:allspark:` → `team:<namespace>:` and `project:allspark:` → `project:<namespace>:` across all keys at import time. Enables public forks to import under their own namespace without editing the JSON.

```bash
python import_litellm_memories.py memories.json --namespace integrahub
# team:allspark:playbook:* → team:integrahub:playbook:*
```

---

## Requirements

`requirements.txt`:
```
httpx>=0.27.0
```

No other runtime dependencies. Tests use stdlib `unittest.mock` only.

---

## Tests

File: `tests/test_importer.py`

8 test cases covering:

1. Load JSON list
2. Load JSON object with `memories` key
3. Load JSONL
4. Prefix filter (`--key-prefix`) excludes non-matching entries
5. Dry-run makes no HTTP calls
6. URL encoding of keys containing colons
7. `--namespace` rewrites `allspark` → custom namespace in keys
8. Schema validation rejects entry missing `value`, exits non-zero

---

## README Updates

Two new sections added:

**Marketplace install** — `extraKnownMarketplaces` snippet for `~/.claude/settings.json` and explanation of global vs per-repo setup.

**Using /octowiz** — entry point options (A/B/C/D), phase-by-phase skill table, note on `setup-matt-pocock-skills` prerequisite, env var requirements.

Existing sections unchanged.

---

## File Layout After v2

```
octowiz/
  litellm_agent_memories_matt_pocock_ai_coding.json   ← +2 entries (contract + skills-hub)
  litellm_agent_memories_matt_pocock_ai_coding.jsonl  ← +2 entries (same)
  import_litellm_memories.py                          ← +schema validation +--namespace
  requirements.txt                                    ← NEW
  skills/
    octowiz-workflow/
      skill.md                                        ← NEW coordinator skill
  tests/
    test_importer.py                                  ← NEW
  docs/
    superpowers/
      specs/
        2026-05-17-octowiz-v2-design.md               ← this file
  large_memory_ai_coding_agent_operating_doctrine.md  ← unchanged
  README.md                                           ← +marketplace section +/octowiz section
  LICENSE                                             ← unchanged
```

---

## Open Questions

None — all design decisions resolved in brainstorming session.
