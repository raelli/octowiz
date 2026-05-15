# LiteLLM Agent Memories — Matt Pocock AI Coding Workflow

This folder contains prepared LiteLLM `/v1/memory` entries derived from:

- `Full Walkthrough_ Workflow for AI Coding — Matt Pocock.md`
- LiteLLM `/memory` endpoint notes from `markdown.md eingefügt`

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
   - `Preparing to upsert 21 memories ...`
   - `OK: ...` for all 21 keys
   - Exit code `0`
4. Verification:
   - Queried each imported key via `GET /v1/memory/{key}`
   - Result: `Total keys checked: 21`, `OK: 21`, `FAIL: 0`
5. Cleanup:
   - `unset LITELLM_ADMIN_API_KEY LITELLM_API_KEY`

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