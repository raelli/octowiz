# LiteLLM Agent Memories — AI Coding Workflow Stack

A small, reusable memory pack for LiteLLM Proxy `/v1/memory` that turns an AI-coding workflow into durable, retrievable agent instructions.

The pack combines:

- workflow memories for planning, implementation, review, QA, and orchestration
- role-specific agent memories for planner, implementer, reviewer, and QA agents
- curated pointers to two external skill systems:
  - [mattpocock/skills](https://github.com/mattpocock/skills)
  - [obra/superpowers](https://github.com/obra/superpowers)

The goal is not to dump a giant prompt into every agent turn. The goal is to store useful operating doctrine once, retrieve the relevant slices by key or prefix, and keep agent context focused.

## Why this is useful

LLM coding agents perform better when the software process is explicit:

- align before implementation
- convert vague requests into PRDs or destination documents
- slice work into small vertical issues
- distinguish human-in-the-loop decisions from AFK-safe implementation
- use TDD and fast feedback loops
- review in a fresh context
- keep human QA and product taste in the loop
- retrieve only the memories relevant to the current agent role

This repository packages those practices as LiteLLM memory entries that can be imported into a LiteLLM Proxy and reused across agents.

## Contents

| File | Purpose |
| --- | --- |
| `litellm_agent_memories_matt_pocock_ai_coding.json` | Importable JSON list of `{key, value, metadata}` memory objects. |
| `litellm_agent_memories_matt_pocock_ai_coding.jsonl` | Same memories as JSONL for pipelines. |
| `large_memory_ai_coding_agent_operating_doctrine.md` | Single large playbook version for direct prompt injection or manual reference. |
| `import_litellm_memories.py` | Idempotent importer using `PUT /v1/memory/{key}`. |

Current pack size: **24 memory entries**.

## Memory layout

The memories use namespaced keys:

- `team:allspark:playbook:ai-coding-workflow:*` — shared workflow doctrine
- `team:allspark:skills:*` — curated external skill-source summaries
- `agent:{role}:memory:ai-coding-workflow` — role-specific operating memory
- `project:allspark:config:*` — import and namespacing guidance

`allspark` is an example team/project namespace. Forks should replace it with their own namespace if they want organization-specific keys.

## Key memories

Core workflow memories include:

- `overview`
- `context-smart-zone`
- `grill-me-alignment`
- `prd-destination-document`
- `kanban-tracer-bullets`
- `hitl-vs-afk`
- `ralph-loop`
- `tdd-feedback-loops`
- `fresh-context-review`
- `manual-qa-taste`
- `deep-modules`
- `module-interface-first`
- `push-pull-standards`
- `frontend-prototypes`
- `doc-rot`
- `parallel-agents`

External skill-source memories:

- `team:allspark:playbook:ai-coding-workflow:skill-sources`
- `team:allspark:skills:matt-pocock:ai-engineering`
- `team:allspark:skills:obra-superpowers:agent-methodology`

Agent role memories:

- `agent:planner:memory:ai-coding-workflow`
- `agent:implementer:memory:ai-coding-workflow`
- `agent:reviewer:memory:ai-coding-workflow`
- `agent:qa:memory:ai-coding-workflow`

## Installation

Install the only runtime dependency:

```bash
python -m pip install httpx
```

Set your LiteLLM Proxy URL and an API key that is allowed to write memories:

```bash
export LITELLM_BASE_URL="https://your-litellm-proxy.example.com"
export LITELLM_ADMIN_API_KEY="sk-..."
```

Use a real LiteLLM virtual key value that starts with `sk-`. Do not wrap key values in `{{ ... }}` when exporting them.

## Dry run

Preview what will be imported without writing anything:

```bash
python import_litellm_memories.py litellm_agent_memories_matt_pocock_ai_coding.json --dry-run
```

Expected shape:

```text
Preparing to upsert 24 memories into https://your-litellm-proxy.example.com
DRY RUN: team:allspark:playbook:ai-coding-workflow:overview (... chars)
...
```

## Import

Run the importer:

```bash
python import_litellm_memories.py litellm_agent_memories_matt_pocock_ai_coding.json
```

The importer uses `PUT /v1/memory/{key}`, so the operation is idempotent for stable keys. Re-running the import updates existing entries instead of creating duplicates.

Team-scoped writes such as `team:allspark:*` may require a proxy-admin-capable key depending on your LiteLLM Proxy configuration. The importer prefers `LITELLM_ADMIN_API_KEY` and falls back to `LITELLM_API_KEY` if the admin key is not set.

## Import only a subset

Use `--key-prefix` to import or test a subset:

```bash
python import_litellm_memories.py litellm_agent_memories_matt_pocock_ai_coding.json \
  --key-prefix "team:allspark:skills:"
```

## Verify imported memories

Fetch one memory:

```bash
curl "$LITELLM_BASE_URL/v1/memory/team%3Aallspark%3Askills%3Amatt-pocock%3Aai-engineering" \
  -H "Authorization: Bearer $LITELLM_ADMIN_API_KEY"
```

Fetch a prefix, if your LiteLLM Proxy supports prefix listing:

```bash
curl "$LITELLM_BASE_URL/v1/memory?key_prefix=team:allspark:playbook:ai-coding-workflow:" \
  -H "Authorization: Bearer $LITELLM_ADMIN_API_KEY"
```

A completed import of this pack should upsert **24/24** memory entries. The three external skill-source memories have been verified with HTTP `200` responses in a live LiteLLM Proxy environment.

## Retrieval strategy

Do not inject every memory into every agent turn. Retrieve by phase and role.

Planner agents usually need:

- `team:allspark:playbook:ai-coding-workflow:overview`
- `team:allspark:playbook:ai-coding-workflow:grill-me-alignment`
- `team:allspark:playbook:ai-coding-workflow:prd-destination-document`
- `team:allspark:playbook:ai-coding-workflow:kanban-tracer-bullets`
- `team:allspark:playbook:ai-coding-workflow:skill-sources`
- `agent:planner:memory:ai-coding-workflow`

Implementer agents usually need:

- `team:allspark:playbook:ai-coding-workflow:context-smart-zone`
- `team:allspark:playbook:ai-coding-workflow:tdd-feedback-loops`
- `team:allspark:playbook:ai-coding-workflow:ralph-loop`
- `team:allspark:skills:matt-pocock:ai-engineering`
- `team:allspark:skills:obra-superpowers:agent-methodology`
- `agent:implementer:memory:ai-coding-workflow`

Reviewer agents usually need:

- `team:allspark:playbook:ai-coding-workflow:fresh-context-review`
- `team:allspark:playbook:ai-coding-workflow:push-pull-standards`
- `team:allspark:skills:obra-superpowers:agent-methodology`
- `agent:reviewer:memory:ai-coding-workflow`

QA agents usually need:

- `team:allspark:playbook:ai-coding-workflow:manual-qa-taste`
- `team:allspark:playbook:ai-coding-workflow:frontend-prototypes`
- `agent:qa:memory:ai-coding-workflow`

## External skill-source routing

The included skill-source memories are intentionally summaries and routing guidance, not vendored copies of the upstream skill repos.

Use [mattpocock/skills](https://github.com/mattpocock/skills) when a task needs stronger support for:

- grilling/alignment
- PRD generation
- vertical-slice issue creation
- TDD
- diagnosis/debugging
- architecture improvement
- prototyping
- handoff

Use [obra/superpowers](https://github.com/obra/superpowers) when a task needs a stricter end-to-end agent methodology:

- brainstorming before coding
- writing plans
- git worktrees
- subagent-driven development
- test-driven development
- systematic debugging
- code review
- verification before completion
- finishing branches

## Security notes

- Never commit real LiteLLM API keys.
- Prefer short-lived or scoped keys where possible.
- Use `LITELLM_ADMIN_API_KEY` only for memory writes that require elevated permissions.
- Unset credentials after import if you are working in a shared shell:

```bash
unset LITELLM_ADMIN_API_KEY LITELLM_API_KEY
```

## Public release checklist

Before making a fork public:

- replace private LiteLLM URLs with placeholders
- confirm no real `sk-...` keys are committed
- decide whether to keep or rename the `allspark` namespace
- add an explicit license if you want others to reuse the repository
- verify attribution links to upstream skill repos remain intact

## Attribution

This repository is a derived memory pack inspired by public AI-coding workflow material and by the following public skill libraries:

- [mattpocock/skills](https://github.com/mattpocock/skills) by Matt Pocock
- [obra/superpowers](https://github.com/obra/superpowers) by Jesse Vincent / Prime Radiant

The upstream repositories are not vendored here. This pack stores compact routing summaries and LiteLLM memory entries that point agents toward the right kind of skill for the current workflow phase.

## Is this worth making public?

Yes, if it is positioned as a practical example of using LiteLLM memory as an agent operating layer rather than as a universal framework. The valuable part is the combination of durable memory keys, role-specific retrieval, idempotent import, and links to external skill systems. Keep the scope clear: this is a starter memory pack and runbook, not a replacement for the upstream skill repos.
