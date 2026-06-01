# aelli-cc-plugin → octowiz Migration Design

**Date:** 2026-06-01  
**Status:** Revised (adversarial review 2026-06-01)  
**Scope:** Full integration of aelli-cc-plugin functionality into octowiz; deprecation of aelli-cc-plugin

---

## Context

Two Claude Code plugins currently share responsibilities:

- **octowiz v0.1.2** (installed): SessionStart/PostToolUse/UserPromptSubmit hooks call `bridge.py`, which posts to `OCTOWIZ_A2A_URL` (default `localhost:8000`). This URL no longer exists — event forwarding is completely broken in production.
- **aelli-cc-plugin v0.4.0** (installed): SessionStart hook spawns a per-session push subscriber; Stop hook posts `session-end` to AELLI. This still works.

**octowiz v0.5.0** (dev repo, not yet published): adds the Node.js pull-based daemon (`src/daemon.js`) that subscribes to AELLI's `/a2a/task-queue` SSE. This is a singleton service — one instance per machine, started out-of-band.

Goal: consolidate everything into octowiz, fix broken event forwarding, and remove aelli-cc-plugin.

---

## Architecture

### Current (broken)

```
CC session                 octowiz (0.1.2)                aelli-cc-plugin (0.4.0)
─────────────              ──────────────────────         ────────────────────────
SessionStart ─────────────► bridge.py → DEAD              start.js → push subscriber
PostToolUse  ─────────────► bridge.py → DEAD              (removed in bridge-split)
UserPromptSubmit ──────────► bridge.py → DEAD              (removed in bridge-split)
Stop ──────────────────────► (no hook)                    stop-hook.js → session-end
AELLI push ────────────────────────────────────────────── ► a2a-client.subscribe()
```

### Target (after migration)

```
CC session                 octowiz (0.5.0, published)
─────────────              ────────────────────────────────────────────────────────
SessionStart ─────────────► start.js → post session-start to AELLI
                                      → spawn per-session push subscriber (detached)
PostToolUse  ─────────────► report-event.js → post file event to AELLI
UserPromptSubmit ──────────► report-event.js → post prompt event to AELLI
Stop ──────────────────────► stop.js → post session-end + kill subscriber

AELLI push ────────────────► per-session subscriber (bin/session-subscriber.js, per PTY_SESSION_ID)
octowiz daemon ────────────► singleton, started out-of-band (node index.js / make start)
                             subscribes to /a2a/task-queue, handles capabilities
```

aelli-cc-plugin: removed.

---

## Phase 1 — Fix event forwarding (urgent, broken in prod)

### New files: `hooks/scripts/`

**`start.js`**
- Reads `session_id` + `cwd` from stdin (Claude Code hook JSON)
- Posts `session-start` event to AELLI via `src/a2a-client.post()` (fire-and-forget)
- Includes: sessionId, branch, repoRoot, repo from `src/git-context.js`
- Exits 0 always — never blocks the developer

**`report-event.js`**
- Reads stdin; detects event type:
  - `tool_name` in {Edit, MultiEdit, NotebookEdit} → `file-edit`
  - `tool_name` === `Write` → `file-write`
  - no `tool_name` (UserPromptSubmit) → `prompt`
- Builds payload via `src/event-builder.js`
- Posts to AELLI fire-and-forget
- Exits 0 always

### `hooks/hooks.json` changes

**Phase 1 hooks.json** — Stop hook is intentionally absent. aelli-cc-plugin's Stop hook remains the sole `session-end` emitter until Phase 3 removes that plugin. Shipping both simultaneously would cause duplicate `session-end` events for every session close.

```json
{
  "hooks": {
    "SessionStart": [
      { "command": "bash \"$CLAUDE_PLUGIN_ROOT/hooks/upgrade-check.sh\"", "timeout": 60 },
      { "command": "node \"$CLAUDE_PLUGIN_ROOT/hooks/scripts/start.js\"", "timeout": 10 }
    ],
    "PostToolUse": [
      { "matcher": "Edit|Write|MultiEdit|NotebookEdit",
        "command": "node \"$CLAUDE_PLUGIN_ROOT/hooks/scripts/report-event.js\"", "timeout": 10 }
    ],
    "UserPromptSubmit": [
      { "command": "node \"$CLAUDE_PLUGIN_ROOT/hooks/scripts/report-event.js\"", "timeout": 10 }
    ]
  }
}
```

bridge.py removed from all hooks. Python dependency eliminated.

`stop.js` is written in this phase (tested in isolation) but **not wired into hooks.json until Phase 3**.

### Observability requirements

The original bridge.py failure mode was silent: events were lost with no trace. This must not be recreated.

**Startup guard** — `start.js` checks `AELLI_LITELLM_BASE` and `AELLI_AUTH_TOKEN` at startup. If either is absent, it appends a warning to `~/.cache/aelli-cc/aelli-cc.log` and exits 0. No events are silently discarded due to misconfiguration without a log entry.

**Failure logging** — all `post()` calls wrap their `.catch()` to append failures to `aelli-cc.log` with timestamp, event type, and error message. This applies to both fire-and-forget and sync calls.

**Lifecycle events use sync with timeout** — `session-start` and `session-end` (once wired in Phase 3) use `sync: true, timeoutMs: 500`. On timeout or network failure, the error is logged (not silently dropped). `report-event.js` (file/prompt events) remains fire-and-forget — high-frequency, non-critical.

### Tests
- Unit tests for each script: mock `src/a2a-client`, feed stdin fixtures, assert correct `post()` call
- Bad/empty stdin → exits 0 (no crash)
- Missing `AELLI_LITELLM_BASE` → exits 0 and appends warning to log
- `post()` failure → appends to log, does not throw or exit non-zero

---

## Phase 2 — Per-session push subscriber migration

### Problem
`index.js` currently calls both `subscribe()` (push, per-session) and `daemon.start()` (pull, singleton). Spawning `index.js` per-session from a hook would cause daemon subscription collisions: `TaskQueue.subscribe(principal, deliver)` is last-writer-wins — all sessions share the same `AELLI_AUTH_TOKEN` principal, so only the most-recently-spawned session would receive delivered tasks.

### Env var consolidation (prerequisite)

`src/a2a-client.js` currently reads `AELLI_API_BASE` for `subscribe()` and `updateTask()`. The daemon uses `AELLI_BASE_URL`. These are two names for the same server — the divergence is historical. Before Phase 2 ships, `src/a2a-client.js` must be updated to use `AELLI_BASE_URL` as the canonical var, with `AELLI_API_BASE` accepted as a fallback alias for backward compatibility. This unifies the env var surface and makes it safe to eventually drop `AELLI_API_BASE`.

`AELLI_API_BASE` must **not** be removed from `~/.claude/settings.json` until this refactor is confirmed deployed.

### Solution: separate entry points

**`src/session-subscriber.js`** (new)
- Extracted from `index.js`
- Calls `subscribe(onTask)` only — no `daemon.start()`
- `onTask` handler: receives push task from AELLI, processes it, writes `systemMessage` to stdout to surface advice inline in the CC session, calls `updateTask` to mark completed

**`index.js`** (updated)
- Removes `subscribe()` call
- Keeps only `daemon.start()`
- Clear comment: "daemon only — start once out-of-band"

**`bin/session-subscriber.js`** (new)
- Thin entry point: sets `PTY_SESSION_ID` from env, requires `src/session-subscriber.js`
- This is what hooks spawn as a detached process

### Hook integration

**`start.js`** (updated from Phase 1):
After posting `session-start`, also:
1. Spawns `bin/session-subscriber.js` detached with `PTY_SESSION_ID=<sessionId>`
2. Writes child PID to `~/.cache/aelli-cc/<sessionId>.pid`

**`stop.js`** (updated from Phase 1):
Before or alongside posting `session-end`:
1. Reads PID from `~/.cache/aelli-cc/<sessionId>.pid`
2. Sends SIGTERM to subscriber process
3. Deletes PID file

### Tests
- `index.js` no longer calls `subscribe()` after refactor
- Subscriber spawns cleanly and exits cleanly on SIGTERM
- Push task handler correctly calls `updateTask` and writes `systemMessage`
- PID file written on start, deleted on stop

---

## Phase 3 — Publish and deprecate

### Version bump
- `plugin.json` → `0.5.0` (matches `package.json`)
- README: document daemon setup (`make start` / `node index.js`) and required env vars

### Required env vars (documented)
| Var | Purpose | Notes |
|-----|---------|-------|
| `AELLI_BASE_URL` | AELLI server URL — daemon task-queue + session subscriber | Canonical after Phase 2 refactor |
| `AELLI_LITELLM_BASE` | LiteLLM base for hook event forwarding | Required for hooks; startup guard warns if absent |
| `AELLI_AUTH_TOKEN` | Auth token for daemon, hooks, and subscriber | |
| `OCTOWIZ_ALLOWED_ROOTS` | Allowed cwd roots (daemon policy gate) | |
| `AELLI_API_BASE` | Legacy alias for `AELLI_BASE_URL` | Accepted as fallback; remove only after Phase 2 ships and is confirmed working |

### Pre-publish smoke test
1. Install octowiz from local path
2. Open CC session → verify `session-start` event reaches AELLI
3. Make a file edit → verify `file-edit` event
4. Submit a prompt → verify `prompt` event
5. Verify push task from AELLI delivered to CC session
6. Close CC session → verify `session-end` event

### Stop hook wired in Phase 3

`stop.js` (written in Phase 1, tested in isolation) is added to `hooks/hooks.json` in this phase only, simultaneously with removing aelli-cc-plugin. This is the atomic handoff: the old plugin's Stop hook goes away at the exact moment the new one activates, so `session-end` is never emitted twice.

Phase 3 `hooks/hooks.json` adds:
```json
"Stop": [
  { "command": "node \"$CLAUDE_PLUGIN_ROOT/hooks/scripts/stop.js\"", "timeout": 10 }
]
```

### Transition
Remove aelli-cc-plugin and publish octowiz 0.5.0 in the same operation (plugin update + removal). The only acceptable double-fire window is a single session restart during the swap — not every session close between Phase 1 and Phase 3.

**Cleanup after removal:**
- Confirm `AELLI_BASE_URL` is set and working before removing `AELLI_API_BASE` from `~/.claude/settings.json`
- Archive `raelli/aelli-cc-plugin` repo

---

## Phasing and dependencies

```
Phase 1 (event forwarding fix)   — independent, ships first, fixes prod immediately
Phase 2 (session push migration)  — depends on Phase 1 hook scripts (extends them)
Phase 3 (publish + deprecate)     — depends on Phase 1 + Phase 2 complete and tested
```

Each phase is a separate PR. Phase 1 can be reviewed and merged independently.

---

## Out of scope
- Daemon deployment model changes (singleton, started out-of-band — no change)
- Per-session principal isolation in TaskQueue (not needed with singleton daemon)
- Changes to raelli/aelli task-queue endpoints (already complete)
