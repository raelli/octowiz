# aelli-cc-plugin → octowiz Migration Design

**Date:** 2026-06-01  
**Status:** Approved  
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

**`stop.js`**
- Reads `session_id` from stdin
- Posts `session-end` event with `sync: true, timeoutMs: 500` (best-effort)
- Exits 0 always

### `hooks/hooks.json` changes

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
    ],
    "Stop": [
      { "command": "node \"$CLAUDE_PLUGIN_ROOT/hooks/scripts/stop.js\"", "timeout": 10 }
    ]
  }
}
```

bridge.py removed from all hooks. Python dependency eliminated.

### Tests
- Unit tests for each script: mock `src/a2a-client`, feed stdin fixtures, assert correct `post()` call
- Bad/empty stdin → exits 0 (no crash)
- Missing env vars → exits 0 with warning

---

## Phase 2 — Per-session push subscriber migration

### Problem
`index.js` currently calls both `subscribe()` (push, per-session) and `daemon.start()` (pull, singleton). Spawning `index.js` per-session from a hook would cause daemon subscription collisions: `TaskQueue.subscribe(principal, deliver)` is last-writer-wins — all sessions share the same `AELLI_AUTH_TOKEN` principal, so only the most-recently-spawned session would receive delivered tasks.

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
| Var | Purpose |
|-----|---------|
| `AELLI_BASE_URL` | AELLI server URL (daemon task-queue subscriber) |
| `AELLI_LITELLM_BASE` | LiteLLM base for event forwarding (hooks) |
| `AELLI_AUTH_TOKEN` | Auth token for both daemon and hooks |
| `OCTOWIZ_ALLOWED_ROOTS` | Allowed cwd roots (daemon policy gate) |

### Pre-publish smoke test
1. Install octowiz from local path
2. Open CC session → verify `session-start` event reaches AELLI
3. Make a file edit → verify `file-edit` event
4. Submit a prompt → verify `prompt` event
5. Verify push task from AELLI delivered to CC session
6. Close CC session → verify `session-end` event

### Transition
Remove aelli-cc-plugin immediately after confirming octowiz 0.5.0 is installed and the smoke test passes. There may be one double-fire of session-start during the restart between removing the old plugin and the first new session — acceptable.

**Cleanup after removal:**
- `AELLI_API_BASE` env var no longer needed (was aelli-cc-plugin's old API base)
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
