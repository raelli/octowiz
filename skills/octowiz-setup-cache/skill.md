---
name: setup-cache
description: >
  Guides the developer through LiteLLM env var configuration and routing bundle
  verification. Sets LITELLM_BASE_URL and API key in ~/.claude/settings.json,
  runs octowiz-cache build --all, and records routing_verified_at timestamp.
---

# octowiz:setup-cache

Guides the developer through LiteLLM env var configuration and routing bundle verification.

## When invoked

Invoked by `octowiz:setup` when `litellm_env` or `litellm_cache` is in the gap list.

## Step 1: Check for litellm_env gap

If `litellm_env` is in the gap list, the `LITELLM_BASE_URL` or API key env var is missing.

Check current state:
```bash
echo "LITELLM_BASE_URL: ${LITELLM_BASE_URL:-<not set>}"
echo "LITELLM_ADMIN_API_KEY: ${LITELLM_ADMIN_API_KEY:-<not set>}"
echo "LITELLM_API_KEY: ${LITELLM_API_KEY:-<not set>}"
```

Guide the developer to add to `~/.claude/settings.json`:
```json
{
  "env": {
    "LITELLM_BASE_URL": "http://your-litellm-server:4000",
    "LITELLM_ADMIN_API_KEY": "your-admin-key-here"
  }
}
```

After the developer confirms they've updated settings.json, ask them to reload Claude Code (or open a new terminal) so the env vars take effect. Then verify:
```bash
echo "LITELLM_BASE_URL: ${LITELLM_BASE_URL:-<not set>}"
```
If still not set, wait and ask them to confirm before continuing.

## Step 2: Seed role bundles

Build all four role bundles from LiteLLM memory:
```bash
octowiz-cache build --all --namespace "${OCTOWIZ_NAMESPACE:-allspark}"
```

If this fails, check:
1. Is LiteLLM running? `curl -s "${LITELLM_BASE_URL}/health"`
2. Are the expected memory keys present? `octowiz-cache status --namespace "${OCTOWIZ_NAMESPACE:-allspark}"`

## Step 3: Verify routing bundle

```bash
octowiz-cache get --role routing --namespace "${OCTOWIZ_NAMESPACE:-allspark}" > /dev/null
```

If exit code is 0, the routing bundle is verified.

## Step 4: Record routing_verified_at in machine-state.json

```python
python3 -c "
from octowiz_env import init_machine_state, save_machine_state, MACHINE_STATE_PATH, _now_iso
state = init_machine_state()
state.litellm['routing_verified_at'] = _now_iso()
save_machine_state(state)
print('routing_verified_at recorded')
"
```

This prevents re-running the full cache setup on every `/octowiz` invocation. The timestamp expires after 24h, at which point the live check will request re-verification.

Note: `planner_verified_at`, `implementer_verified_at`, and `reviewer_verified_at` are set lazily the first time each workflow option (B/C/D) is selected. You do not need to set them here.

## After completing

Report that LiteLLM cache is configured and return control to `octowiz:setup`.
