# octowiz
<img src="assets/octowiz.jpeg" alt="octowiz cover image" width="666">

A skill-backed memory stack for coding agents.

---

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-eab308.svg" alt="license: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.8%2B-3776AB.svg?logo=python&logoColor=white" alt="python 3.8+">
  <img src="https://img.shields.io/badge/LiteLLM_Proxy-compatible-7C3AED.svg" alt="LiteLLM Proxy compatible">
  <img src="https://img.shields.io/badge/memories-26-22c55e.svg" alt="26 memories">
  <img src="https://img.shields.io/badge/skills-routed,_not_vendored-f97316.svg" alt="skills routed, not vendored">
</p>

octowiz is a memory stack and coordinator skill for AI-assisted development in Claude Code. It stores AI-coding operating doctrine in [LiteLLM Proxy](https://docs.litellm.ai/) `/v1/memory` — how to plan, write tests, review, and ship — and exposes a `/octowiz` entry point that reads those memories at runtime and routes to the right combination of [superpowers](https://github.com/obra/superpowers) and [mattpocock/skills](https://github.com/mattpocock/skills) for the current phase. One source of truth; each session fetches only what is relevant to the step it is on.

## Architecture

```
        Developer in Claude Code
          │
          │  /octowiz
          ▼
        ┌──────────────────────────────────────┐
        │     /octowiz coordinator skill       │
        │  skills/octowiz-workflow/skill.md    │
        │ ──────────────────────────────────── │
        │  reads project state + git status    │
        │  fetches retrieval contract          │
        │  routes A / B / C / D               │
        └─────────────────┬────────────────────┘
                          │
                          │  GET /v1/memory
                          ▼
        ┌──────────────────────────────────────┐
        │     LiteLLM Proxy · /v1/memory       │
        │ ──────────────────────────────────── │
        │     playbook:*           16 entries  │
        │     skills:*              4 entries  │
        │     agent:{role}:*        4 entries  │
        │     config:*              2 entries  │
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

Three layers. The coordinator reads the project and fetches the relevant doctrine slice; LiteLLM holds the doctrine; installed skills do the work — referenced, never copied.

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
pip install httpx
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
    "litellm": {
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

**Per-repo alternative:** add a `.env` file (gitignored) if you prefer project-scoped keys:

```bash
# .env
LITELLM_BASE_URL=https://your-proxy.example.com
LITELLM_API_KEY=sk-your-key
```

## Using /octowiz

After importing memories and installing the marketplace, invoke the coordinator from any repo:

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
