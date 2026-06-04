<div align="center">

<img src="assets/octowiz.jpeg" alt="octowiz — the octopus-wizard" width="720">

# octowiz

**Octowiz Bridge** — the Claude Code adapter for the Octowiz Engineering Agent.

[![license: MIT](https://img.shields.io/badge/license-MIT-eab308.svg)](LICENSE)
&nbsp;![python 3.8+](https://img.shields.io/badge/python-3.8%2B-3776AB.svg?logo=python&logoColor=white)
&nbsp;![LiteLLM Proxy compatible](https://img.shields.io/badge/LiteLLM_Proxy-compatible-7C3AED.svg)
&nbsp;![26 memories](https://img.shields.io/badge/memories-26-22c55e.svg)
&nbsp;![skills routed, not vendored](https://img.shields.io/badge/skills-routed,_not_vendored-f97316.svg)

[**Live overview ↗**](https://raelli.github.io/octowiz/) &nbsp;·&nbsp; [ÆLLI — orchestration brain](https://github.com/raelli/aelli) &nbsp;·&nbsp; [Install](#install)

</div>

---

This repository is the **Octowiz Bridge** — the Claude Code plugin component of the Octowiz Engineering Agent. It connects Claude Code sessions to the Octowiz memory stack and skill ecosystem. It stores AI-coding operating doctrine in [LiteLLM Proxy](https://docs.litellm.ai/) `/v1/memory` and exposes a `/octowiz` entry point that reads those memories at runtime and routes to the right combination of [superpowers](https://github.com/obra/superpowers) and [mattpocock/skills](https://github.com/mattpocock/skills) for the current phase.

Octowiz is ÆLLI's coding alter-ego — the engineering tentacle of the ÆLLI agent network. This Bridge plugin is one component of that system, handling the Claude Code interface while the Octowiz A2A agent server handles reasoning, memory, and cross-agent orchestration.

## Why this exists

Most AI coding tools give agents either a giant system prompt or nothing. Octowiz takes a third path: doctrine lives in a memory store, agents fetch only what is relevant to their current phase, and the coordinator skill routes to purpose-built skill libraries rather than trying to be everything itself.

The result is a context window that stays small and focused. A planner gets planning doctrine. An implementer gets TDD loops and deep-module principles. A reviewer gets fresh-context review discipline. None of them get the others' doctrine as noise.

> **Small context. No prompt soup.**

## Architecture

```mermaid
flowchart TD
    AELLI["ÆLLI<br/>orchestration brain"]:::brain
    AGENT["Octowiz A2A Agent &middot; server &middot; /a2a/octowiz<br/>plan &middot; review &middot; observe &middot; handoff<br/>context &middot; dispatch &middot; run_sandboxed<br/>manage_agents &middot; marketplace_info<br/>reads Memory + Knowledge + Diary &middot; escalates decisions"]:::node
    BRIDGE["Octowiz Bridge &middot; this repo<br/>skills/octowiz-workflow/skill.md<br/>reads project state + git &middot; routes A / B / C / D"]:::core
    MEM[("LiteLLM Proxy &middot; /v1/memory<br/>playbook 17 &middot; skills 3 &middot; agent 4 &middot; project:{id}:octowiz seeded")]:::mem
    SK["integrahub marketplace skills<br/>mattpocock/skills &middot; obra/superpowers"]:::skills

    AELLI -->|"A2A &middot; /a2a/octowiz"| AGENT
    AGENT -->|"events / advice"| BRIDGE
    BRIDGE -->|"GET / PUT /v1/memory"| MEM
    MEM -->|"routes to installed skills"| SK

    classDef brain fill:#1e1b4b,stroke:#7c3aed,color:#e9d5ff;
    classDef node fill:#15121f,stroke:#9333ea,color:#e9d5ff;
    classDef core fill:#3b1763,stroke:#c084fc,color:#ffffff,stroke-width:2px;
    classDef mem fill:#0f1b28,stroke:#3776ab,color:#bfdbfe;
    classDef skills fill:#2a1605,stroke:#f97316,color:#fed7aa;
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
|---|:--:|---|
| `playbook:*` | **17** | Workflow doctrine: how to plan, slice, implement, review, and ship. Derived from the transcript of Matt Pocock's [AI Engineer workshop](https://www.youtube.com/watch?v=-QFHIoCo-Ko). Covers context management, alignment interviews, PRD structure, tracer-bullet slicing, HITL vs AFK, TDD, fresh-context review, deep modules, frontend prototypes, parallel agents, and more. |
| `skills:*` | **3** | Routing summaries for the two upstream skill libraries (mattpocock/skills, obra/superpowers) and the marketplace skills hub. Tells agents which library handles which kind of task. |
| `agent:{role}:*` | **4** | Role-specific memory slices for `planner`, `implementer`, `reviewer`, and `qa`. Each agent pulls only its own slice to keep context tight. |
| `config:*` | **2** | Import guidance and the retrieval contract the coordinator reads on startup. |

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

> All three are required. `/octowiz` routes to skills from the other two — if either is missing the coordinator will fail mid-flow.

## Daemon setup

The Octowiz daemon runs as a singleton service per machine. It connects the Claude Code hooks to the AELLI A2A network, handles capability dispatch, and exposes the task queue for pull-based background execution.

**Start the daemon:**

```bash
make start
# or
node index.js
```

The Claude Code hooks (SessionStart, PostToolUse, UserPromptSubmit, Stop) fire automatically when the plugin is installed. They do not manage the daemon lifecycle.

**Required env vars:**

| Var | Purpose |
|-----|---------|
| `AELLI_LITELLM_BASE` | LiteLLM base URL for hook event forwarding (e.g. `https://llm.integrahub.de`) |
| `AELLI_AUTH_TOKEN` | Shared auth token used by both hooks and daemon |
| `OCTOWIZ_ALLOWED_ROOTS` | Comma-separated allowed cwd roots (e.g. `/Users/you/projects`) |

**Optional env vars:**

| Var | Default | Purpose |
|-----|---------|---------|
| `AELLI_BASE_URL` | derived from `AELLI_LITELLM_BASE` | Direct AELLI server URL override |
| `AELLI_ROUTER_URL` | derived from `AELLI_LITELLM_BASE` | Router endpoint for routing decisions |
| `OCTOWIZ_NAMESPACE` | `allspark` | Memory namespace |
| `OCTOWIZ_CACHE_DIR` | `~/.cache/octowiz` | Doctrine cache root |
| `OCTOWIZ_CACHE_TTL_SECONDS` | `3600` | Bundle revalidation interval |
| `OCTOWIZ_CACHE_BYPASS` | — | Set to `1` to skip cache entirely |

**Per-repo alternative:** add a `.env` file (gitignored) for project-scoped keys:

```bash
# .env
LITELLM_BASE_URL=https://your-proxy.example.com
LITELLM_API_KEY=sk-your-key
```

## A2A capabilities

When AELLI dispatches a task to Octowiz via `/a2a/octowiz`, the daemon routes it to the matching capability handler. All capabilities are pull-based — the daemon polls the task queue and executes locally inside the developer's Claude Code session.

| Capability | Description |
|---|---|
| `octowiz.plan` | Generate an implementation plan for a given task description |
| `octowiz.review` | Review a diff or file set and return structured findings |
| `octowiz.observe` | Observe and annotate an in-progress session without interrupting it |
| `octowiz.handoff` | Package current session context for handoff to the next agent or session |
| `octowiz.context` | Build a context package (files + git state + memory) for an incoming task |
| `octowiz.dispatch` | Dispatch a Claude Code background session for an autonomous task |
| `octowiz.run_sandboxed` | Execute a task inside an isolated Sandcastle container |
| `router.validation-request` | Handle an inbound validation request from AELLI's high-risk workflow gate |
| `octowiz.manage_agents` | List, start, stop, and inspect active Claude Code agents |
| `marketplace_info` | Query the IntegraHub Marketplace for available skills, plugins, and agents |

## Sandcastle — sandboxed execution

`octowiz.run_sandboxed` runs tasks inside a Docker/Podman container built from the official Octowiz sandbox image. The container has `node 22`, `git`, and the `claude` CLI pre-installed. No credentials are baked into the image — secrets are forwarded via name-only `--env` flags at runtime so they never appear in `argv` or `ps` output.

**Container image:** `ghcr.io/raelli/octowiz-sandbox:latest`

Built on `node:22-bookworm-slim`. Automatically rebuilt on every push to `containers/sandcastle/**` via GitHub Actions and tagged with both the commit SHA and `latest`.

**Build locally:**

```bash
make build-sandbox-image
# custom registry or tag:
SANDBOX_IMAGE=my-registry/octowiz-sandbox:dev make build-sandbox-image
```

**Env vars forwarded to the container at runtime:**

| Var | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Required for `claude` CLI inside the container |
| `ANTHROPIC_BASE_URL` | Optional — override the Anthropic API endpoint |
| `AELLI_AUTH_TOKEN` | Forward-looking — for future hooks inside the container |

The sandbox provider reads these from the host process at container start time. If a var is unset on the host, Docker/Podman silently skips it — no error, no crash.

## Marketplace integration

Octowiz publishes itself to the IntegraHub Marketplace and can query it for available skills, plugins, and agents via the `marketplace_info` capability.

The `packages/marketplace_client` library handles resolution:

```bash
# List all marketplace items
python -m packages.marketplace_client.cli list

# Resolve a specific item by name
python -m packages.marketplace_client.cli resolve octowiz
```

`octowiz-marketplace-manifest.json` is Octowiz's self-description in the marketplace. Keep it in sync with `package.json` version and the capability list when shipping a new release.

## Using /octowiz

After importing memories and installing the three required plugins, invoke the coordinator from any repo:

```
/octowiz
```

The coordinator reads your project setup, fetches the relevant memories from LiteLLM, and asks where you are in the workflow:

```mermaid
flowchart LR
    Q{"/octowiz<br/>where are you?"}:::core
    Q -->|"A &middot; fresh idea"| A["brainstorming"]:::plan
    Q -->|"B &middot; stress-test a plan"| B["grill-me"]:::plan
    Q -->|"C &middot; ready to implement"| C["using-git-worktrees + TDD"]:::build
    Q -->|"D &middot; code done, review"| D["zoom-out + requesting-code-review"]:::review

    classDef core fill:#3b1763,stroke:#c084fc,color:#fff,stroke-width:2px;
    classDef plan fill:#1e1b4b,stroke:#7c3aed,color:#e9d5ff;
    classDef build fill:#0e2618,stroke:#22c55e,color:#bbf7d0;
    classDef review fill:#2a0a1a,stroke:#e11d74,color:#fbcfe8;
```

| Option | Starting point | Entry skill |
|---|---|---|
| A | Fresh idea | `brainstorming` |
| B | Have a plan to stress-test | `grill-me` |
| C | Ready to implement | `using-git-worktrees` + TDD |
| D | Code done, need review | `zoom-out` + `requesting-code-review` |

### Skills in this plugin

| Slash command | Purpose |
|---|---|
| `/octowiz` | Coordinator — reads project state, loads doctrine, routes A/B/C/D |
| `/octowiz:setup` | Environment setup wizard — detects gaps (plugins, LiteLLM, memory), fixes them interactively |
| `/octowiz:octowiz-doctowiz` | Doctor — full multi-mode diagnostic for the octowiz + AELLI integration stack; monitors live activity, guides setup and upgrades |

Run `/mattpocock-skills:setup-matt-pocock-skills` once per repo before first use — it wires your issue tracker and domain docs so `to-prd`, `to-issues`, `triage`, and `diagnose` work correctly.

## What happens when you run /octowiz?

1. **Project state is read** — CLAUDE.md, README, open issues, current branch, git log.
2. **Routing doctrine is loaded** — `octowiz-cache get --role routing` fetches the cached retrieval contract. If the cache is cold it pulls from LiteLLM. If LiteLLM is unreachable and the cache is stale, it serves the stale bundle with a warning.
3. **You choose a starting point** — A, B, C, or D. The coordinator suggests a default based on project state (open issues + active branch → C; no plan → A).
4. **A role bundle is prepended to context** — planner doctrine for A/B, implementer for C, reviewer for D. Stable rules land early in the context window.
5. **Fresh project context is appended** — git status, open issues, your request. Never cached.
6. **The first skill in the chosen path is invoked** — brainstorming, grill-me, using-git-worktrees, or zoom-out.

## Retrieval per role

Each role pulls only its slice of the doctrine pack:

| Role | Memories to pull |
|---|---|
| **Planner** | `overview`, `grill-me-alignment`, `prd-destination-document`, `kanban-tracer-bullets`, `skill-sources`, `agent:planner:*` |
| **Implementer** | `context-smart-zone`, `tdd-feedback-loops`, `ralph-loop`, `skills:matt-pocock:*`, `skills:obra-superpowers:*`, `agent:implementer:*` |
| **Reviewer** | `fresh-context-review`, `push-pull-standards`, `skills:obra-superpowers:*`, `agent:reviewer:*` |
| **QA** | `manual-qa-taste`, `frontend-prototypes`, `agent:qa:*` |

## Skill routing

octowiz routes to two upstream skill libraries rather than vendoring them. Each gets a compact routing summary so agents know which to reach for without loading both.

**[mattpocock/skills](https://github.com/mattpocock/skills)** — alignment interviews, PRD generation, vertical slicing, TDD, debugging, architecture improvement, prototyping, handoff. Best fit when a task starts loose and needs structure.

**[obra/superpowers](https://github.com/obra/superpowers)** — brainstorming before code, written plans, git worktrees, subagent-driven development, systematic debugging, code review, verification before completion, finishing branches. Best fit when you want a strict end-to-end methodology.

Neither is bundled. Forks should keep the routing entries pointing at the real upstream so attribution and updates stay intact.

## Diagnostics

Run the Doctowiz skill for a full integration health check at any time:

```
/octowiz:octowiz-doctowiz
```

Doctowiz probes each layer in sequence: Claude Code plugin version, env vars, hook pipeline, LiteLLM connectivity, AELLI reachability, daemon status, and memory bundles. It reports a pass/fail table per check and suggests targeted fixes for anything red. It also includes an update helper (Mode 4) for upgrades from older versions.

Run the underlying script directly for a quick terminal check:

```bash
node "$CLAUDE_PLUGIN_ROOT/apps/doctowiz/index.js"
```

## Verify

Pull one memory to confirm the import landed:

```bash
curl "$LITELLM_BASE_URL/v1/memory/team%3Aallspark%3Askills%3Amatt-pocock%3Aai-engineering" \
  -H "Authorization: Bearer $LITELLM_ADMIN_API_KEY"
```

Or fetch a whole prefix:

```bash
curl "$LITELLM_BASE_URL/v1/memory?key_prefix=team:allspark:playbook:ai-coding-workflow:" \
  -H "Authorization: Bearer $LITELLM_ADMIN_API_KEY"
```

A clean import upserts 26/26. The three external skill-source entries have been verified live with `HTTP 200`.

## Memory caching

Octowiz caches stable doctrine bundles locally so repeated `/octowiz` runs load instantly without hitting LiteLLM on every invoke.

```mermaid
flowchart TD
    L["LiteLLM /v1/memory"]:::mem --> C["octowiz-cache<br/>hash + manifest"]:::core
    C --> D["~/.cache/octowiz/namespaces/allspark/bundles/"]:::node
    D --> S["/octowiz skill<br/>doctrine prepended &middot; fresh project state appended"]:::brain

    classDef mem fill:#0f1b28,stroke:#3776ab,color:#bfdbfe;
    classDef core fill:#3b1763,stroke:#c084fc,color:#fff,stroke-width:2px;
    classDef node fill:#15121f,stroke:#9333ea,color:#e9d5ff;
    classDef brain fill:#1e1b4b,stroke:#7c3aed,color:#e9d5ff;
```

**What is cached:** role playbooks, routing contracts, skill references — stable doctrine only.

**Never cached:** git status, source files, test output, open issues, user requests, review conclusions.

### Commands

```bash
octowiz-cache build --all             # warm all role bundles
octowiz-cache status                  # check freshness at a glance
octowiz-cache refresh --all           # force-rebuild from LiteLLM
octowiz-cache get --role planner      # print planner bundle to stdout
octowiz-cache clear                   # delete cache for current namespace
octowiz-cache clear --all-namespaces  # wipe entire cache
octowiz-cache seed                    # seed project namespace into LiteLLM Memory (idempotent)
octowiz-cache seed --project slug     # seed with explicit project ID
octowiz-cache check                   # environment health check (hard + advisory gaps)
octowiz-cache init                    # bootstrap missing state files
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

$ octowiz-cache check
{"status": "clean", "hard_gaps": [], "advisory_gaps": []}

$ # Now with LiteLLM unreachable:
$ LITELLM_BASE_URL=http://127.0.0.1:1 octowiz-cache get --role routing
[octowiz-cache] LiteLLM unavailable (...) — serving stale bundle for role 'routing' (updated 42s ago)
# Octowiz Doctrine Bundle: routing
...
```

## Security

- `LITELLM_ADMIN_API_KEY` is only needed when memory writes require elevated scope; read operations work with a standard `LITELLM_API_KEY`.
- The sandbox container image contains no credentials. Secrets are forwarded at container start time via name-only `--env VAR` flags — the value is read from the host environment by Docker/Podman and never enters `argv` or logs.
- `AELLI_AUTH_TOKEN` is a Bearer token shared by both the hooks and the daemon. Rotate it in `~/.claude/settings.json` and on the AELLI server simultaneously.
- The daemon validates `OCTOWIZ_ALLOWED_ROOTS` on every incoming task to prevent path-traversal dispatches outside the declared project roots.

## Attribution

Sources this pack draws from:

- **["Essential Skills for AI Coding from Planning to Production"](https://www.youtube.com/watch?v=-QFHIoCo-Ko)** — Matt Pocock's workshop at AI Engineer. The workflow doctrine in this pack is distilled from it.
- [mattpocock/skills](https://github.com/mattpocock/skills) — Matt Pocock
- [obra/superpowers](https://github.com/obra/superpowers) — Jesse Vincent / Prime Radiant

The two skill libraries aren't bundled. octowiz stores compact routing summaries that send agents to the right place when the current task calls for it.

## License

MIT. See [`LICENSE`](LICENSE).

<div align="center">

—

**[octowiz](https://github.com/raelli/octowiz)** &nbsp;·&nbsp; part of the **IntegraHub** engineering ecosystem &nbsp;·&nbsp; [ÆLLI ↗](https://github.com/raelli/aelli)

</div>
