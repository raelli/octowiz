# LiteLLM Agent Memories — Matt Pocock AI Coding Workflow

This folder contains prepared LiteLLM `/v1/memory` entries derived from:

- `Full Walkthrough_ Workflow for AI Coding — Matt Pocock.md`
- LiteLLM `/memory` endpoint notes from `markdown.md eingefügt`
- External skill sources:
  - `https://github.com/mattpocock/skills`
  - `https://github.com/obra/superpowers`

## Files

- `litellm_agent_memories_matt_pocock_ai_coding.json`  
  Importable list of `{key, value, metadata}` memory objects.

- `litellm_agent_memories_matt_pocock_ai_coding.jsonl`  
  Same content as JSONL, useful for pipelines.

- `large_memory_ai_coding_agent_operating_doctrine.md`  
  One large memory/playbook for direct prompt injection or single LiteLLM memory entry.

- `import_litellm_memories.py`  
  Idempotent importer using `PUT /v1/memory/{key}`.

## Recommended import

```bash
cd litellm_agent_memories
python -m pip install httpx
export LITELLM_BASE_URL="https://llm.integrahub.de"
export LITELLM_ADMIN_API_KEY="sk-..."
export LITELLM_API_KEY="sk-..."

python import_litellm_memories.py litellm_agent_memories_matt_pocock_ai_coding.json --dry-run
python import_litellm_memories.py litellm_agent_memories_matt_pocock_ai_coding.json
```

Important:
- Use a real LiteLLM virtual key value that starts with `sk-`.
- Do not wrap key values in `{{ ... }}` when exporting.
- Team-scoped writes (for example `team:allspark:*`) may require a proxy-admin-capable key on stricter deployments.

## Verified import runbook

The following flow was validated end-to-end for this project:

1. Export:
   - `LITELLM_BASE_URL=https://llm.integrahub.de`
   - `LITELLM_ADMIN_API_KEY=sk-...` (proxy-admin-capable key)
2. Run:
   - `python import_litellm_memories.py litellm_agent_memories_matt_pocock_ai_coding.json`
3. Expected result:
   - `Preparing to upsert 24 memories ...`
   - `OK: ...` for all 24 keys
   - Exit code `0`
4. Verification:
   - Queried each imported key via `GET /v1/memory/{key}`
   - Current extended import target: `Total keys checked: 24`, `OK: 24`, `FAIL: 0`
5. Cleanup:
   - `unset LITELLM_ADMIN_API_KEY LITELLM_API_KEY`

## Migration completion record
Base migration status: complete.
Skill-source extension status: source prepared and dry-run validated; run the import command again with `LITELLM_ADMIN_API_KEY` exported to upsert the three new skill memories.

Final migration execution:
- Command: `python import_litellm_memories.py litellm_agent_memories_matt_pocock_ai_coding.json`
- Auth used: `LITELLM_ADMIN_API_KEY` (valid LiteLLM virtual key starting with `sk-`)
- Base result: 21/21 keys upserted successfully (`OK` for all entries, exit code `0`)
- Extension result: 3 additional skill-source keys added for Matt Pocock Skills and Obra Superpowers, bringing the source file to 24 memories

Post-migration verification:
- Single-key API verification: `team:allspark:playbook:ai-coding-workflow:overview` returned HTTP `200`
- Remaining critical verification via API:
  - Team playbook keys: 15/15
  - Agent role memories: 4/4
  - Project config key: 1/1
- Base aggregate retrieval verification: 21/21 keys retrievable, 0 failures
- Extended source validation: 24/24 JSON entries, 24 unique keys, JSONL synchronized, importer dry-run successful
- Skill-source live API verification: 3/3 new keys retrievable, 0 failures
  - `team:allspark:playbook:ai-coding-workflow:skill-sources` returned HTTP `200`
  - `team:allspark:skills:matt-pocock:ai-engineering` returned HTTP `200`
  - `team:allspark:skills:obra-superpowers:agent-methodology` returned HTTP `200`

Authentication fix confirmed:
- Importer now prefers `LITELLM_ADMIN_API_KEY` for write operations and falls back to `LITELLM_API_KEY` only if admin key is unset.
- Keys exported with literal `{{ ... }}` wrappers will fail authentication; export raw key values only.

## External skill source memories

The memory set includes three curated skill-source memories:

- `team:allspark:playbook:ai-coding-workflow:skill-sources`  
  Routes external skills to the right workflow phase: alignment, PRD, issue slicing, implementation, review, QA, parallel agents, or meta skill work.
- `team:allspark:skills:matt-pocock:ai-engineering`  
  Summarizes `mattpocock/skills` as a composable engineering skill catalog. Best fit: grill sessions, PRDs, vertical-slice issues, TDD, diagnosis, architecture improvement, prototyping, and handoff.
- `team:allspark:skills:obra-superpowers:agent-methodology`  
  Summarizes `obra/superpowers` as an end-to-end agentic development methodology. Best fit: brainstorming, planning, git worktrees, subagent-driven development, TDD, systematic debugging, code review, verification, and finishing branches.

Retrieval rule:
Use these memories selectively by workflow phase. Do not inject the full external skill-source set into every agent turn.

## Recommended retrieval

Fetch all shared workflow memories:

```bash
curl "$LITELLM_BASE_URL/v1/memory?key_prefix=team:allspark:playbook:ai-coding-workflow:" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

Fetch one agent role memory:

```bash
curl "$LITELLM_BASE_URL/v1/memory/agent:planner:memory:ai-coding-workflow" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

## Prompt injection pattern

Do not inject every memory into every agent turn. Retrieve by prefix and role.

Example:
- Planner gets:
  - `team:allspark:playbook:ai-coding-workflow:overview`
  - `team:allspark:playbook:ai-coding-workflow:grill-me-alignment`
  - `team:allspark:playbook:ai-coding-workflow:prd-destination-document`
  - `team:allspark:playbook:ai-coding-workflow:kanban-tracer-bullets`
  - `agent:planner:memory:ai-coding-workflow`

- Implementer gets:
  - `team:allspark:playbook:ai-coding-workflow:context-smart-zone`
  - `team:allspark:playbook:ai-coding-workflow:tdd-feedback-loops`
  - `team:allspark:playbook:ai-coding-workflow:ralph-loop`
  - `agent:implementer:memory:ai-coding-workflow`

- Reviewer gets:
  - `team:allspark:playbook:ai-coding-workflow:fresh-context-review`
  - `team:allspark:playbook:ai-coding-workflow:push-pull-standards`
  - `agent:reviewer:memory:ai-coding-workflow`