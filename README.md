# octowiz
<img src="assets/octowiz.jpeg" alt="octowiz cover image" width="666">

**Octowiz Bridge** — Claude Code adapter for the Octowiz Engineering Agent.

---

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-eab308.svg" alt="license: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.8%2B-3776AB.svg?logo=python&logoColor=white" alt="python 3.8+">
  <img src="https://img.shields.io/badge/LiteLLM_Proxy-compatible-7C3AED.svg" alt="LiteLLM Proxy compatible">
  <img src="https://img.shields.io/badge/memories-26-22c55e.svg" alt="26 memories">
  <img src="https://img.shields.io/badge/skills-routed,_not_vendored-f97316.svg" alt="skills routed, not vendored">
</p>

This repository is the **Octowiz Bridge** — the Claude Code plugin component of the Octowiz Engineering Agent. It connects Claude Code sessions to the Octowiz memory stack and skill ecosystem. It stores AI-coding operating doctrine in [LiteLLM Proxy](https://docs.litellm.ai/) `/v1/memory` and exposes a `/octowiz` entry point that reads those memories at runtime and routes to the right combination of [superpowers](https://github.com/obra/superpowers) and [mattpocock/skills](https://github.com/mattpocock/skills) for the current phase.

Octowiz is ÆLLI's coding alter-ego — the engineering tentacle of the ÆLLI agent network. This Bridge plugin is one component of that system, handling the Claude Code interface while the Octowiz A2A agent server handles reasoning, memory, and cross-agent orchestration.

## Why this exists

Most AI coding tools give agents either a giant system prompt or nothing. Octowiz takes a third path: doctrine lives in a memory store, agents fetch only what is relevant to their current phase, and the coordinator skill routes to purpose-built skill libraries rather than trying to be everything itself.

The result is a context window that stays small and focused. A planner gets planning doctrine. An implementer gets TDD loops and deep-module principles. A reviewer gets fresh-context review discipline. None of them get the others' doctrine as noise.

## Architecture

```
        ÆLLI (orchestration brain)
          │
          │  A2A  /a2a/octowiz
          ▼
        ┌──────────────────────────────────────┐
        │     Octowiz A2A Agent  (server)      │  ← coming in Phase 2
        │ ──────────────────────────────────── │
        │  octowiz.plan / review / advise      │
        │  reads Memory + Knowledge + Diary    │
        │  escalates strategic decisions       │
        └─────────────────┬────────────────────┘
                          │
                          │  events / advice
                          ▼
        ┌──────────────────────────────────────┐
        │   Octowiz Bridge  (this repo)        │  ← Claude Code plugin
        │ ──────────────────────────────────── │
        │  skills/octowiz-workflow/skill.md    │
        │  reads project state + git status    │
        │  fetches routing doctrine            │
        │  routes A / B / C / D                │
        └─────────────────┬────────────────────┘
                          │
                          │  GET/PUT /v1/memory
                          ▼
        ┌──────────────────────────────────────┐
        │     LiteLLM Proxy · /v1/memory       │
        │ ──────────────────────────────────── │
        │     playbook:*           17 entries  │
        │     skills:*              3 entries  │
        │     agent:{role}:*        4 entries  │
        │     project:{id}:octowiz:*  seeded   │
        └─────────────────┬────────────────────┘
                          │
                          │  routes to installed skills
                          ▼
        ┌──────────────────────────────────────┐
        │   integrahub marketplace skills      │
        │ ──────────────────────────────────── │
        │     ▸ mattpocock/skills              │
        │     ▸ obra/superpowers               │
        └──────────────────────────────────────┘
```

## Component glossary

| Name | What it is |
|---|---|
| **Octowiz Bridge** | This repo. The Claude Code plugin. Hooks into developer sessions, routes to skills, seeds project memory. Install name: `octowiz`. |
| **Octowiz Agent** | The A2A server (`/a2a/octowiz`). Handles reasoning, advisor rules, diary writing, and escalation to ÆLLI. Built separately — not in this repo. |
| **Octowiz Advisor** | Capability inside the Agent. Detects spec drift, file conflicts, and branch deviations. Formerly "Dev Advisor". |
| **ÆLLI** | The orchestration brain. Delegates coding work to Octowiz via A2A. Makes strategic decisions Octowiz escalates up. |
| **LiteLLM** | Platform layer. Hosts the A2A Gateway, Memory API, and IntegraHub Marketplace. |
| `/a2a/dev-advisor` | Compatibility alias for `/a2a/octowiz`. Maintained while clients migrate. |

### Memory namespace breakdown

| Prefix | Count | What it contains |
|---|---|---|
| `playbook:*` | 17 | Workflow doctrine: how to plan, slice, implement, review, and ship. Derived from the transcript of Matt Pocock's [AI Engineer workshop](https://www.youtube.com/watch?v=-QFHIoCo-Ko). Covers context management, alignment interviews, PRD structure, tracer-bullet slicing, HITL vs AFK, TDD, fresh-context review, deep modules, frontend prototypes, parallel agents, and more. |
| `skills:*` | 3 | Routing summaries for the two upstream skill libraries (mattpocock/skills, obra/superpowers) and the marketplace skills hub. Tells agents which library handles which kind of task. |
| `agent:{role}:*` | 4 | Role-specific memory slices for `planner`, `implementer`, `reviewer`, and `qa`. Each agent pulls only its own slice to keep context tight. |
| `config:*` | 2 | Import guidance and the retrieval contract the coordinator reads on startup. |

## Contents

| File | Purpose |
|---|---|
| `litellm_agent_memories_matt_pocock_ai_coding.json` | The 26 memories, ready to import. |
| `litellm_agent_memories_matt_pocock_ai_coding.jsonl` | Same content as JSONL, for streaming or pipeline use. |
| `large_memory_ai_coding_agent_operating_doctrine.md` | The whole playbook as one document, if you'd rather read than retrieve. |
| `import_litellm_memories.py` | The importer. Idempotent. Uses `PUT /v1/memory/{key}`. |
| `LICENSE` | MIT. |

### Namespace layout

```
team:allspark:playbook:ai-coding-workflow:*   shared doctrine
team:allspark:skills:*                        external skill routing
agent:{role}:memory:ai-coding-workflow        role-specific
project:allspark:config:*                     import / namespacing
```

`allspark` is the example namespace. If you fork this, swap it for your own — nobody wants to debug under someone else's project name.

<details>
<summary><b>Full memory inventory (26 entries)</b></summary>

**Workflow doctrine** — `overview`, `context-smart-zone`, `grill-me-alignment`, `prd-destination-document`, `kanban-tracer-bullets`, `hitl-vs-afk`, `ralph-loop`, `tdd-feedback-loops`, `fresh-context-review`, `manual-qa-taste`, `deep-modules`, `module-interface-first`, `push-pull-standards`, `frontend-prototypes`, `doc-rot`, `parallel-agents`

**External skill routing** — `playbook:ai-coding-workflow:skill-sources`, `skills:matt-pocock:ai-engineering`, `skills:obra-superpowers:agent-methodology`

**Agent roles** — `planner`, `implementer`, `reviewer`, `qa`

</details>

## Install

```bash
pip install -e .
export LITELLM_BASE_URL="https://your-proxy.example.com"
export LITELLM_ADMIN_API_KEY="sk-..."
```

Dry run before you commit to anything:

```bash
python import_litellm_memories.py litellm_agent_memories_matt_pocock_ai_coding.json --dry-run
```

When it looks right:

```bash
python import_litellm_memories.py litellm_agent_memories_matt_pocock_ai_coding.json
```

`PUT /v1/memory/{key}` is idempotent. Safe to rerun — entries get refreshed, not duplicated.

Run the test suite to verify your setup:

```bash
python -m pytest tests/ -v
```

Expected: all tests pass.

Team-scoped writes under `team:allspark:*` usually want proxy-admin scope. The importer reads `LITELLM_ADMIN_API_KEY` first and falls back to `LITELLM_API_KEY` if you didn't set the admin one.

Want just a subset? Prefix-filter the import:

```bash
python import_litellm_memories.py litellm_agent_memories_matt_pocock_ai_coding.json \
  --key-prefix "team:allspark:skills:"
```

## Claude Code setup

Install the marketplace plugin once — no per-repo setup needed.

Add to `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "integrahub": {
      "source": "url",
      "url": "https://llm.integrahub.de/claude-code/marketplace.json"
    }
  },
  "env": {
    "LITELLM_BASE_URL": "https://your-proxy.example.com",
    "LITELLM_API_KEY": "sk-..."
  }
}
```

Point `LITELLM_BASE_URL` at your own LiteLLM proxy. Skills are public — the key is only needed for memory retrieval and AI model access.

**Install the required plugins.** Adding the marketplace to `settings.json` only registers it as a known source — plugins are not installed automatically. Open Claude Code and run:

```
/plugins
```

Install these three plugins from the marketplace:

| Plugin | Provides |
|---|---|
| `octowiz` | The `/octowiz` coordinator skill (this repo) |
| `mattpocock-skills` | Alignment, PRD, TDD, diagnosis, architecture, handoff skills |
| `superpowers` | Brainstorming, plans, worktrees, subagents, review, verification skills |

All three are required. `/octowiz` routes to skills from the other two — if either is missing the coordinator will fail mid-flow.

## Daemon setup

The octowiz daemon handles agent capabilities (dispatch, advise, manage-agents). It runs as a singleton service — start it once per machine, not per Claude Code session.

**Required env vars:**

| Var | Purpose |
|-----|---------|
| `AELLI_BASE_URL` | AELLI server URL (e.g. `http://localhost:3456`) |
| `AELLI_LITELLM_BASE` | LiteLLM base URL for event forwarding hooks |
| `AELLI_AUTH_TOKEN` | Shared auth token (daemon + hooks) |
| `OCTOWIZ_ALLOWED_ROOTS` | Comma-separated allowed cwd roots (e.g. `/Users/you/projects`) |

**Start the daemon:**

```bash
make start
# or
node index.js
```

The Claude Code hooks (SessionStart, PostToolUse, UserPromptSubmit, Stop) run automatically when the plugin is installed. They do not start or stop the daemon.

**Per-repo alternative:** add a `.env` file (gitignored) if you prefer project-scoped keys:

```bash
# .env
LITELLM_BASE_URL=https://your-proxy.example.com
LITELLM_API_KEY=sk-your-key
```

## Using /octowiz

After importing memories and installing the marketplace and all three skills (octowiz,mattpo-skills,superpowers are mandatory the rest is optional), invoke the coordinator from any repo:

```
/octowiz
```

The coordinator reads your project setup, fetches the relevant memories from LiteLLM, and asks where you are in the workflow:

| Option | Starting point | Entry skill |
|---|---|---|
| A | Fresh idea | `brainstorming` |
| B | Have a plan to stress-test | `grill-me` |
| C | Ready to implement | `using-git-worktrees` + TDD |
| D | Code done, need review | `zoom-out` + `requesting-code-review` |

Run `/mattpocock-skills:setup-matt-pocock-skills` once per repo before first use — it wires up your issue tracker and domain docs so `to-prd`, `to-issues`, `triage`, and `diagnose` work correctly.

## What happens when you run /octowiz?

1. **Project state is read** — CLAUDE.md, README, open issues, current branch, git log.
2. **Routing doctrine is loaded** — `octowiz-cache get --role routing` fetches the cached retrieval contract. If the cache is cold, it pulls from LiteLLM. If LiteLLM is unreachable and the cache is stale, it serves the stale bundle with a warning.
3. **You choose a starting point** — A (fresh idea), B (stress-test a plan), C (implement), or D (review). The coordinator suggests a default based on project state.
4. **A role bundle is prepended to context** — planner doctrine for A/B, implementer for C, reviewer for D. This lands early in the context window so stable rules outweigh ephemeral noise.
5. **Fresh project context is appended** — git status, open issues, your request. These change every run and are never cached.
6. **The first skill in the chosen path is invoked** — brainstorming, grill-me, using-git-worktrees, or zoom-out, depending on your choice.

## Retrieval per role

Each role only needs a slice of the pack. Suggested mapping:

| Role | Memories to pull |
|---|---|
| **Planner** | `overview`, `grill-me-alignment`, `prd-destination-document`, `kanban-tracer-bullets`, `skill-sources`, `agent:planner:*` |
| **Implementer** | `context-smart-zone`, `tdd-feedback-loops`, `ralph-loop`, `skills:matt-pocock:*`, `skills:obra-superpowers:*`, `agent:implementer:*` |
| **Reviewer** | `fresh-context-review`, `push-pull-standards`, `skills:obra-superpowers:*`, `agent:reviewer:*` |
| **QA** | `manual-qa-taste`, `frontend-prototypes`, `agent:qa:*` |

## Skill routing

octowiz points at two upstream skill libraries instead of vendoring them. Each gets a short routing summary so agents know which to reach for.

**[mattpocock/skills](https://github.com/mattpocock/skills)** — alignment, PRD generation, vertical slicing, TDD, diagnosis and debugging, architecture work, prototyping, handoff. Best fit when a task starts loose and needs structure.

**[obra/superpowers](https://github.com/obra/superpowers)** — brainstorming before code, written plans, git worktrees, subagent-driven development, systematic debugging, code review, verification before completion, finishing branches. Best fit when you want a strict end-to-end methodology.

Neither is bundled. Forks should keep the routing entries pointing at the real upstream so attribution and updates stay intact.

## Verify

Pull one memory just to confirm it landed:

```bash
curl "$LITELLM_BASE_URL/v1/memory/team%3Aallspark%3Askills%3Amatt-pocock%3Aai-engineering" \
  -H "Authorization: Bearer $LITELLM_ADMIN_API_KEY"
```

Or fetch a whole prefix, if your proxy supports listing:

```bash
curl "$LITELLM_BASE_URL/v1/memory?key_prefix=team:allspark:playbook:ai-coding-workflow:" \
  -H "Authorization: Bearer $LITELLM_ADMIN_API_KEY"
```

A clean import upserts 26/26. The three external skill-source entries have been verified live with `HTTP 200`.

## Memory caching

Octowiz caches stable doctrine bundles locally so repeated `/octowiz` runs load instantly without hitting LiteLLM every time.

```
LiteLLM /v1/memory
        │
        ▼
octowiz-cache (hash + manifest)
        │
        ▼
~/.cache/octowiz/namespaces/allspark/bundles/
        │
        ▼
/octowiz skill — doctrine prepended, fresh project state appended
```

**What is cached:** role playbooks, routing contracts, skill references — stable doctrine only.

**Never cached:** git status, source files, test output, open issues, user requests, review conclusions.

### Commands

```bash
octowiz-cache build --all          # warm all role bundles
octowiz-cache status               # check freshness at a glance
octowiz-cache refresh --all        # force-rebuild from LiteLLM
octowiz-cache get --role planner   # print planner bundle to stdout
octowiz-cache clear                # delete cache for current namespace
octowiz-cache clear --all-namespaces  # wipe entire cache
octowiz-cache seed                 # seed project namespace into LiteLLM Memory (idempotent)
octowiz-cache seed --project slug  # seed with explicit project ID
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `OCTOWIZ_CACHE_DIR` | `~/.cache/octowiz` | Cache root directory |
| `OCTOWIZ_CACHE_TTL_SECONDS` | `3600` | Seconds before revalidation |
| `OCTOWIZ_CACHE_BYPASS` | — | Set to `1` to skip cache entirely |
| `OCTOWIZ_NAMESPACE` | `allspark` | Namespace for memory key substitution |

### Behaviour when LiteLLM is unavailable

If the cache is stale and LiteLLM cannot be reached, `octowiz-cache` serves the stale bundle with a stderr warning rather than failing. `/octowiz` continues normally. If no cached bundle exists at all, it falls back to built-in routing.

### Demo

```
$ octowiz-cache build --all
[octowiz-cache] built: planner
[octowiz-cache] built: implementer
[octowiz-cache] built: reviewer
[octowiz-cache] built: qa
[octowiz-cache] built: routing

$ octowiz-cache status
planner         ✓ fresh (0m ago)
implementer     ✓ fresh (0m ago)
reviewer        ✓ fresh (0m ago)
qa              ✓ fresh (0m ago)
routing         ✓ fresh (0m ago)

$ octowiz-cache build --all   # run again — memories unchanged, same hashes, no fetch
[octowiz-cache] built: planner
[octowiz-cache] built: implementer
[octowiz-cache] built: reviewer
[octowiz-cache] built: qa
[octowiz-cache] built: routing

$ # Now with LiteLLM unreachable:
$ LITELLM_BASE_URL=http://127.0.0.1:1 octowiz-cache get --role routing
[octowiz-cache] LiteLLM unavailable (...) — serving stale bundle for role 'routing' (updated 42s ago)
# Octowiz Doctrine Bundle: routing
...
```

## Security

- `LITELLM_ADMIN_API_KEY` is only needed when memory writes require elevated scope.

## Attribution

Sources this pack draws from:

- **["Essential Skills for AI Coding from Planning to Production"](https://www.youtube.com/watch?v=-QFHIoCo-Ko)** — Matt Pocock's workshop at AI Engineer. The workflow doctrine in this pack is distilled from it.
- [mattpocock/skills](https://github.com/mattpocock/skills) — Matt Pocock
- [obra/superpowers](https://github.com/obra/superpowers) — Jesse Vincent / Prime Radiant

The two skill libraries aren't bundled. octowiz stores compact routing summaries that send agents to the right place when the current task calls for it.

## License

MIT. See [`LICENSE`](LICENSE).
