---
name: octowiz-doctowiz
description: Run a full live diagnostic of the octowiz + AELLI integration — processes, endpoints, hook pipeline, and log health. Produces a markdown report.
---

# Doctowiz — Octowiz + AELLI Diagnostic

When this skill is invoked, run the doctowiz diagnostic and display the full report.

## Steps

**1. Run the diagnostic:**
```bash
node "$CLAUDE_PLUGIN_ROOT/apps/doctowiz/index.js"
```

**2. Display the complete markdown output** — do not summarise or truncate it.

**3. After the report:**
- If **HEALTHY**: confirm all systems nominal.
- If **DEGRADED**: explain each warning and whether action is needed.
- If **UNHEALTHY**: identify the failing component and provide the fix command.

## What the diagnostic covers

| Phase | Tests |
|-------|-------|
| Process health | Daemon, AELLI Node.js, AELLI Python A2A, session-subscriber count |
| Configuration | Auth token, LiteLLM base URL, bridge.py path |
| Endpoint health | Port 3456, port 8765, LiteLLM gateway reachability |
| Hook pipeline (live) | Runs bridge.py with real UserPromptSubmit + PostToolUse events |
| Log analysis | Error rate last 1h/24h, daemon subscription status, last activity |

## Notes

- Pipeline tests make real requests to AELLI — expect 3–8s total runtime.
- A `spec-deviation` advisory is expected when cwd is the octowiz dev repo with modified files.
- Session subscriber warnings are harmless if count ≤ 5; sessions created before PR #73 merged won't self-clean until restarted.
