---
name: octowiz-doctowiz
description: >
  The Octowiz doctor — diagnose, monitor, and fix the full octowiz + AELLI
  integration. Use whenever octowiz or AELLI isn't behaving correctly, a hook
  isn't firing, an advisory isn't returning, or you want a real-time activity
  feed. Also guides first-time setup, configuration from scratch, and upgrading
  from older versions (especially 0.5.x–0.9.x). Invoke as /octowiz:doctowiz for
  a full health check, or add a keyword: "monitor", "watch", "setup", "install",
  "update", "upgrade", "fix <symptom>".
---

# Doctowiz — Octowiz + AELLI Doctor

The Octowiz doctor. Diagnoses the full octowiz + AELLI integration stack,
interprets every failure with a plain-language explanation and a concrete fix
command, monitors live activity, and guides setup from scratch.

## Mode detection

Read the user's invocation text (or context of the conversation) to pick the mode:

| Trigger words | Mode |
|---|---|
| (nothing / "diagnose" / "check" / "health") | **Diagnose** (default) |
| "monitor" / "watch" / "tail" / "live" | **Monitor** |
| "setup" / "install" / "configure" / "start fresh" | **Setup guide** |
| "update" / "upgrade" / "migrate" / "I'm on 0.5" / "old version" | **Update helper (Mode 4)** |
| "fix <symptom>" / describes a specific error | **Targeted fix (Mode 5)** |

When uncertain, run Diagnose — it gives the most complete picture.

---

## Mode 1 — Diagnose (default)

Run the full diagnostic, interpret every non-passing check, and offer guided fixes.

### Step 1: Version inventory

Before running the diagnostic, collect version information:

```bash
# Octowiz plugin version
node -e "const p=require('$CLAUDE_PLUGIN_ROOT/package.json'); console.log('octowiz', p.version)"

# Installed plugin cache version
ls -1 ~/.claude/plugins/cache/integrahub/octowiz/ 2>/dev/null | tail -1

# AELLI version (if running locally)
node -e "try{const p=require(require('os').homedir()+'/Documents/aelli/package.json'); console.log('aelli', p.version)}catch(e){console.log('aelli not found locally')}"

# LiteLLM / AELLI env vars
echo "AELLI_BASE_URL:       ${AELLI_BASE_URL:-(not set)}"
echo "AELLI_AUTH_TOKEN:     ${AELLI_AUTH_TOKEN:-(not set)}"
echo "AELLI_LITELLM_BASE:   ${AELLI_LITELLM_BASE:-(not set)}"
echo "AELLI_ROUTER_URL:     ${AELLI_ROUTER_URL:-(not set)}"
echo "OCTOWIZ_ALLOWED_ROOTS:${OCTOWIZ_ALLOWED_ROOTS:-(not set)}"

# Local Python A2A server version (public /health since 0.9.16)
curl -s -m 3 "http://localhost:${OCTOWIZ_A2A_PORT:-8765}/health" 2>/dev/null \
  || echo "A2A server: not reachable (starts on next session open)"

# AELLI gateway health
[ -n "$AELLI_BASE_URL" ] && curl -s "$AELLI_BASE_URL/health" \
  -H "Authorization: Bearer $AELLI_AUTH_TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('aelli/litellm', d.get('status','?'))" 2>/dev/null \
  || echo "AELLI gateway: not reachable (expected if remote)"
```

Show a version summary before the diagnostic table. Flag:
- Plugin cache version ≠ source (`$CLAUDE_PLUGIN_ROOT`) → stale cache, run `claude plugins install octowiz --force`
- A2A `/health` version ≠ plugin version → stale Python server. Since 0.9.18 the
  session-start hook restarts it automatically (it verifies the recorded pid is
  the uvicorn on the configured port before killing); on older plugins use the
  `aelli_python` fix below.
- A2A `/health` returns `{"error":"Unauthorized"}` → the running server predates
  0.9.16 (when `/health` became public) — definitely stale, same fix.
- `AELLI_BASE_URL` missing → queue subscription and hook delivery both broken
- `AELLI_AUTH_TOKEN` missing → all AELLI requests will get 401
- `OCTOWIZ_ALLOWED_ROOTS` missing → daemon will refuse to start

### Step 2: Service pre-flight

Check the three background services in parallel:

```bash
# Node daemon (launchd service)
launchctl list de.integrahub.octowiz-daemon 2>/dev/null

# Python A2A server — /health gives status AND version in one probe
curl -s -m 3 "http://localhost:${OCTOWIZ_A2A_PORT:-8765}/health" 2>/dev/null && echo " a2a:up" || echo "a2a:down"

# Allowed-roots coverage for current cwd
node -e "
const roots = (process.env.OCTOWIZ_ALLOWED_ROOTS || '').split(':').filter(Boolean);
const cwd = process.cwd();
const ok = roots.some(r => cwd.startsWith(r));
console.log(ok ? 'roots:ok' : 'roots:missing — cwd=' + cwd);
" 2>/dev/null || echo "roots:unknown"
```

Interpret:
- **Daemon PID missing or `-`** → daemon not running; fix: `daemon_start`
- **a2a:down** → Python A2A server not up; fix: `aelli_python`
- **roots:missing** → current repo not in `OCTOWIZ_ALLOWED_ROOTS`; fix: `allowed_roots`

### Step 3: Memory and doctrine health

Check whether octowiz-cache is functional and memories are seeded:

```bash
octowiz-cache check 2>&1
```

Parse the JSON. If `hard_gaps` is non-empty, note them — they explain why the
workflow may route incorrectly even when the pipeline itself is healthy.

Then verify the routing bundle is reachable:

```bash
octowiz-cache get --role routing --namespace "${OCTOWIZ_NAMESPACE:-allspark}" > /dev/null 2>&1 \
  && echo "routing bundle: OK" \
  || echo "routing bundle: UNREACHABLE"
```

### Step 4: Run the diagnostic script

```bash
node "$CLAUDE_PLUGIN_ROOT/apps/doctowiz/index.js"
```

Wait for it to complete (3–8 seconds — the pipeline live tests make real AELLI requests).

### Step 5: Interpret results

Display the full markdown output from the script. Then, for every FAIL or WARN
check, add an interpretation block below the table:

**[Check name]** — plain-language explanation of what this means for the developer
and why it matters, followed by the exact fix command from the **Fix reference**
section below.

Override the script's built-in fix hint for "Octowiz daemon" failures — the daemon
is now a launchd service, not a manual `node` invocation. Use `daemon_start` fix.

After all failures and warnings are explained, summarise the overall health:

- **HEALTHY**: "All systems nominal. The full hook → AELLI pipeline is working."
- **DEGRADED**: "The core pipeline is working but [N] warnings need attention. Advisories will still arrive — but [specific risk from the warning]."
- **UNHEALTHY**: "The pipeline has [N] hard failures. Advisories will not arrive until these are fixed."

Then ask: "Want me to fix any of these now?" If the user says yes, run the fix
command(s) inline and re-run the diagnostic to confirm.

### Step 6: Session activity

After the diagnostic, show a quick session snapshot:

```bash
# Recent hook activity — last 10 lines from the bridge log
tail -10 ~/.cache/aelli-cc/aelli-cc.log 2>/dev/null || echo "(no log file yet — no hooks have fired)"

# Daemon log — last 10 lines
tail -10 ~/.cache/aelli-cc/octowiz-daemon.log 2>/dev/null || echo "(no daemon log yet)"

# Active sessions in cache dir
ls ~/.cache/aelli-cc/ 2>/dev/null
```

Summarise: when the last hook fired and whether the daemon is actively processing
or idle. If the log is empty and everything is HEALTHY, note: "Setup looks correct
but no hooks have fired yet — open a Claude Code session and edit a file to trigger
the first hook."

---

## Mode 2 — Monitor (activity snapshot)

When the user wants to see what octowiz + AELLI have been doing. This is a
snapshot, not a blocking tail — it shows the most recent activity from both logs
and lets the user re-run it after triggering actions in another window.

Tell the user: "Here's a snapshot of recent octowiz + AELLI activity. Trigger
some actions in a Claude Code session (edit a file, submit a prompt), then
re-run `/octowiz:doctowiz monitor` to see what came through."

```bash
echo "=== Octowiz daemon — launchd status ==="
launchctl list de.integrahub.octowiz-daemon 2>/dev/null || echo "(service not loaded)"

echo ""
echo "=== Octowiz daemon log (last 20 lines) ==="
tail -20 ~/.cache/aelli-cc/octowiz-daemon.log 2>/dev/null || echo "(daemon log not found)"

echo ""
echo "=== Bridge / AELLI hook log (last 20 lines) ==="
tail -20 ~/.cache/aelli-cc/aelli-cc.log 2>/dev/null || echo "(hook log not found — no hooks have fired yet)"
```

Interpret lines visible in the output:

| Log pattern | Meaning |
|---|---|
| `advisory delivered` | Hook fired and AELLI responded — pipeline working |
| `delivery failed` | Hook fired but AELLI rejected it — check auth token |
| `fail-open` | Bridge hit an error and silently let the hook pass through |
| `subscribed to` | Daemon picked up a new task from AELLI |
| `spec-deviation` | AELLI noticed a file edited outside the plan — informational |
| `no capability handler` | Daemon received a task type it doesn't recognise |
| `[start] AELLI_AUTH_TOKEN not set` | Hook started without auth — delivery disabled |
| `cwd … not within an allowed root` | Task rejected — cwd not in `OCTOWIZ_ALLOWED_ROOTS` |
| `[start] daemon path mismatch … restarting` | Node daemon was stale — auto-restarted via launchd plist (0.9.17+) |
| `[start] A2A server version skew … restarting pid` | Python A2A server was stale — auto-restarted (0.9.18+) |
| `[start] port … serves a non-octowiz service` | Something else owns the A2A port — auto-restart refused to touch it |
| `[start] not restarting A2A server` | Recorded pid failed identity check (not the uvicorn on that port) — no kill |

If both logs are empty or missing:

> "No activity yet. Make sure a Claude Code session with octowiz is running,
> then trigger a hook by editing a file or submitting a prompt. Re-run
> `/octowiz:doctowiz monitor` to see the output."

If the hook log has entries but the daemon log is empty, note: the hook pipeline
is working but the daemon launchd service may not be loaded — tasks won't be
dispatched. Check with `launchctl list de.integrahub.octowiz-daemon`.

---

## Mode 3 — Setup guide

When the user is doing a fresh install or reconfiguring from scratch. Walk through
these phases in order, confirming each before moving on.

### Phase 1 — Plugin installed?

```bash
ls ~/.claude/plugins/cache/integrahub/octowiz/ 2>/dev/null | tail -1
```

If missing: `claude plugins install octowiz`

After install, remind the user to restart Claude Code so `$CLAUDE_PLUGIN_ROOT`
is set correctly in the new session.

### Phase 2 — Dependencies installed?

```bash
ls ~/.claude/plugins/cache/*/superpowers/ 2>/dev/null | head -1
ls ~/.claude/plugins/cache/*/mattpocock-skills/ 2>/dev/null | head -1
```

If either is missing:
```bash
claude plugins install superpowers
claude plugins install mattpocock-skills
```

`superpowers` provides workflow discipline skills (TDD, brainstorming, worktrees).
`mattpocock-skills` provides issue management and domain documentation skills.

### Phase 3 — Environment variables set?

All required vars should be in `~/.claude/settings.json` under `"env"`:

```bash
echo "AELLI_BASE_URL:        ${AELLI_BASE_URL:-(NOT SET)}"
echo "AELLI_AUTH_TOKEN:      ${AELLI_AUTH_TOKEN:-(NOT SET)}"
echo "AELLI_LITELLM_BASE:    ${AELLI_LITELLM_BASE:-(NOT SET)}"
echo "AELLI_ROUTER_URL:      ${AELLI_ROUTER_URL:-(not set — optional)}"
echo "OCTOWIZ_ALLOWED_ROOTS: ${OCTOWIZ_ALLOWED_ROOTS:-(NOT SET)}"
```

Guide the user to add all to `~/.claude/settings.json`:

```json
{
  "env": {
    "AELLI_BASE_URL":        "https://llm.integrahub.de",
    "AELLI_AUTH_TOKEN":      "your-bearer-token",
    "AELLI_LITELLM_BASE":    "https://llm.integrahub.de",
    "AELLI_ROUTER_URL":      "https://llm.integrahub.de/a2a/aelli-router/message/send",
    "OCTOWIZ_ALLOWED_ROOTS": "/Users/you/Documents/myproject:/Users/you/Documents/other"
  }
}
```

`AELLI_BASE_URL` and `AELLI_LITELLM_BASE` are typically the same value.
`OCTOWIZ_ALLOWED_ROOTS` is a colon-separated list of absolute paths the daemon
is allowed to operate in — the daemon exits at startup if this is not set.

### Phase 4 — Background services running?

The daemon is a launchd service (auto-starts at login). The Python A2A server is
auto-started by the Claude Code session hook.

```bash
# Check daemon
launchctl list de.integrahub.octowiz-daemon 2>/dev/null || echo "not loaded"

# Check Python A2A server
nc -z 127.0.0.1 8765 2>/dev/null && echo "a2a:up" || echo "a2a:down"
```

**If daemon not loaded:**
```bash
# First time — create the launchd service
# Plist at: ~/Library/LaunchAgents/de.integrahub.octowiz-daemon.plist
# (see fix reference daemon_start for plist content)
launchctl load ~/Library/LaunchAgents/de.integrahub.octowiz-daemon.plist
```

**If Python A2A server down** — start manually:
```bash
cd ~/Documents/octowiz/apps/a2a-agent
python3 -m uvicorn main:app --host 127.0.0.1 --port 8765 &
```
It will also be auto-started on the next Claude Code session open.

**Note on AELLI (port 3456):** AELLI runs on the remote integra42 server, not
localhost. Port 3456 being closed locally is expected. The daemon connects to
`AELLI_BASE_URL` (remote) via the task queue — it does not need a local AELLI.

### Phase 5 — Memory seeded?

```bash
octowiz-cache check 2>&1
octowiz-cache seed 2>&1
```

If `octowiz-cache` is not found, install the Python package from the plugin root:
```bash
pip install -e "$CLAUDE_PLUGIN_ROOT"
```

### Phase 6 — End-to-end verification

Run the diagnostic to confirm everything is wired up:

```bash
node "$CLAUDE_PLUGIN_ROOT/apps/doctowiz/index.js"
```

All checks should be green. If any remain red, use the targeted fix commands below.

---

## Mode 4 — Update helper

When the user is on an older version and needs to upgrade.
This mode auto-detects what's stale, explains each breaking change, and walks
through the steps in order. Run it once after a `claude plugins install octowiz --force`.

### Step 1: Detect installed version

```bash
# Version reported by the running plugin
node -e "try{const p=require('$CLAUDE_PLUGIN_ROOT/package.json'); console.log(p.version)}catch(e){console.log('unknown')}"

# Version in the plugin cache
ls -1 ~/.claude/plugins/cache/integrahub/octowiz/ 2>/dev/null | sort -V | tail -1
```

If the cache still shows a version older than current, reinstall:

```bash
claude plugins install octowiz --force
```

Then restart Claude Code before continuing.

### Step 2: Breaking change — env vars renamed (0.5.x → 0.8.0)

```bash
echo "Old (0.5.x) — should be EMPTY now:"
echo "  OCTOWIZ_A2A_URL:        ${OCTOWIZ_A2A_URL:-(not set — good)}"
echo "  OCTOWIZ_INBOUND_SECRET: ${OCTOWIZ_INBOUND_SECRET:-(not set — good)}"
echo ""
echo "New (0.9.x) — must be set:"
echo "  AELLI_AUTH_TOKEN:    ${AELLI_AUTH_TOKEN:-(NOT SET — fix required)}"
echo "  AELLI_BASE_URL:      ${AELLI_BASE_URL:-${AELLI_LITELLM_BASE:-(NOT SET — fix required)}}"
```

**Why this changed:** In v0.5.x, `bridge.py` POSTed hook events directly to the
Octowiz A2A server (`OCTOWIZ_A2A_URL`). From v0.6.0 (PR #67, single advisory
path), it routes through the LiteLLM gateway, which handles routing to the right
AELLI service. The auth secret became a standard Bearer token (`AELLI_AUTH_TOKEN`).

**If the old vars are still set and the new ones are missing:**

Remove from `settings.json`:
```json
"OCTOWIZ_A2A_URL": "...",
"OCTOWIZ_INBOUND_SECRET": "..."
```

Add to `settings.json`:
```json
"AELLI_AUTH_TOKEN": "your-bearer-token",
"AELLI_BASE_URL":   "https://llm.integrahub.de"
```

### Step 3: OCTOWIZ_ALLOWED_ROOTS (new in 0.9.x)

The daemon now requires `OCTOWIZ_ALLOWED_ROOTS` to be set at startup (it exits
immediately if missing). Add it to `settings.json` AND to the launchd plist:

```json
"OCTOWIZ_ALLOWED_ROOTS": "/Users/you/Documents/repo1:/Users/you/Documents/repo2"
```

Then reload the launchd service:
```bash
launchctl unload ~/Library/LaunchAgents/de.integrahub.octowiz-daemon.plist
launchctl load  ~/Library/LaunchAgents/de.integrahub.octowiz-daemon.plist
```

### Step 4: Daemon is now a launchd service (0.9.4+)

The daemon previously had to be started manually (`node index.js`). From 0.9.4
it runs as a launchd service — auto-starts at login and restarts on crash.

If upgrading from a manual setup, stop the old process and load the service:
```bash
pkill -f "octowiz/index.js" 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/de.integrahub.octowiz-daemon.plist
```

### Step 5: Clean up stale session-subscribers

v0.5.x spawned a long-lived session-subscriber process per session. Clean up:

```bash
pkill -f session-subscriber.js 2>/dev/null && echo "cleaned" || echo "none running"
```

### Step 6: Rebuild memory bundles

```bash
octowiz-cache build --all --namespace "${OCTOWIZ_NAMESPACE:-allspark}"
```

### Step 7: Verify with the full diagnostic

```bash
node "$CLAUDE_PLUGIN_ROOT/apps/doctowiz/index.js"
```

### What changed at each version (reference)

| Version | What changed | User action required |
|---|---|---|
| 0.5.0 | Thin daemon + StoreRegistry baseline | — |
| 0.6.0 | Single advisory path; Python advisor deleted; bridge routes through LiteLLM — **env vars renamed** | Rename env vars (see Step 2) |
| 0.7.0 | DispatchSession state machine | Restart AELLI |
| 0.8.0 | Bridge routing and auth header hardened | None (vars already renamed in 0.6.0) |
| 0.8.1 | `octowiz.observe` capability handler added | None |
| 0.8.3 | Session-subscriber idle fix; doctowiz skill added | `pkill -f session-subscriber.js` |
| 0.9.0 | Full A2A suite (gaps 1–5), Sandcastle runner + container image, Marketplace integration, AELLI router client, doctowiz full diagnostic | Run `/plugin update` in Claude Code |
| 0.9.1 | DispatchSession wired to LiteLLM Workflow Runs API | None |
| 0.9.2 | pnpm migration; Dockerfile + husky pre-commit gate | Use `pnpm` instead of `npm` |
| 0.9.3 | Architecture improvements: deep modules, dead-code removal, seam documentation; rename dependency `mattpo-skills` → `mattpocock-skills` | `claude plugins install mattpocock-skills` if missing |
| 0.9.4 | `OCTOWIZ_ALLOWED_ROOTS` required; daemon runs as launchd service; service pre-flight in octowiz-workflow skill | Add `OCTOWIZ_ALLOWED_ROOTS` to settings + plist; `launchctl load` the service |
| 0.9.5 | Doctowiz: WARN (not FAIL) when AELLI is remote; service pre-flight added to octowiz-workflow skill | None |
| 0.9.6 | README restructure + SVG architecture diagrams | None |
| 0.9.7–0.9.9 | Purple badge logger (`--*`) on all octowiz output; AELLI advisory styled with `[æ]` badge in terminal | None |
| 0.9.10 | AELLI advisory badge refinements | None |
| 0.9.11 | CI auto-syncs plugin to IntegraHub marketplace on tag push; DEPLOYING.md added | None |
| 0.9.12 | Arch refactor: path guard alignment, dead-code removal, SSE backoff, retry matrix tests | Run `/plugin update` |
| 0.9.13 | Badge format unified; advisory type validation against allowlist; SSE preamble skip fix | Run `/plugin update` |
| 0.9.14 | Doctowiz: fix 2 false-positive diagnostic checks (AELLI process + routing bundle) | Run `/plugin update` |
| 0.9.15 | Bridge: iterate all SSE `data:` lines in `_route_event` (fixes routing response parse); arch deviations resolved | Run `/plugin update` |
| 0.9.16 | Bridge: plugin dirs excluded from spec-deviation `live_modified_files` | Run `/plugin update` |
| 0.9.17 | Public `GET /health` on the A2A server (`{"status","version"}`); Node daemon auto-restarts on version skew (launchd plist path check); arch pass 2: `src/config.js` single env owner, `src/a2a-transport.js` single JSON-RPC transport, `AgentRunProvider` protocol, `err()/require()` error-envelope owner | Run `/plugin update` — daemon restarts itself on next session start |
| 0.9.18 | Python A2A server auto-restarts on version skew (pid-verified); jest runs no longer pollute `~/.cache/aelli-cc/aelli-cc.log` | Run `/plugin update` |

---

## Mode 5 — Targeted fix

When the user describes a specific symptom, map it to the likely cause and fix:

| Symptom | Most likely cause | Fix ref |
|---|---|---|
| "Advisories not arriving" | Bad or missing auth token | `auth_token` |
| "Hook fires but nothing happens" | Bridge delivery failure | `bridge_delivery` |
| "Daemon not running" | launchd service not loaded | `daemon_start` |
| "Daemon exits immediately" | `OCTOWIZ_ALLOWED_ROOTS` not set | `allowed_roots` |
| "Task rejected: cwd not within allowed root" | Repo missing from `OCTOWIZ_ALLOWED_ROOTS` | `allowed_roots` |
| "octowiz-cache not found" | Python package not installed | `pip install -e $CLAUDE_PLUGIN_ROOT` |
| "Changes to skill not taking effect" | Stale plugin cache | `plugin_cache` |
| "Too many session-subscriber processes" | Pre-PR-#73 sessions | `session_subscribers` |
| "spec-deviation on every edit" | Normal in octowiz dev repo | No fix — expected |
| "Was on 0.5.x, just updated, still broken" | Env vars not migrated | Switch to Mode 4 (Update helper) |
| "LiteLLM shows workflow runs all 'failed' with 'server restarted'" | AELLI restarting during in-flight workflows (auto-deploy) | `workflow_runs_failing` |
| "Plugin updated but A2A server still serves old code" | Long-running server predates auto-restart (pre-0.9.18) | `aelli_python` |
| "/health returns Unauthorized" | Running A2A server predates 0.9.16 (public /health) | `aelli_python` |

Run the diagnostic after each fix to confirm the check turns green.

---

## Fix reference

### `auth_token`
Add or correct `AELLI_AUTH_TOKEN` in `~/.claude/settings.json`:
```json
{ "env": { "AELLI_AUTH_TOKEN": "your-token-here" } }
```
Reload Claude Code so the env var takes effect in hook processes.

### `bridge_delivery`
Run bridge.py with verbose logging to see the exact failure:
```bash
OCTOWIZ_VERBOSE=1 echo '{"hook_event_name":"UserPromptSubmit","session_id":"test","cwd":"/tmp","prompt":"test"}' \
  | python3 "$CLAUDE_PLUGIN_ROOT/apps/claude_code_bridge/bridge.py"
```
The stderr output shows the URL attempted and the HTTP status returned.

### `daemon_start`
The daemon runs as a launchd service. Check and start:
```bash
# Check status
launchctl list de.integrahub.octowiz-daemon

# Start (if not loaded)
launchctl load ~/Library/LaunchAgents/de.integrahub.octowiz-daemon.plist

# Restart
launchctl unload ~/Library/LaunchAgents/de.integrahub.octowiz-daemon.plist
launchctl load  ~/Library/LaunchAgents/de.integrahub.octowiz-daemon.plist

# Check logs
tail -20 ~/.cache/aelli-cc/octowiz-daemon.log
```

Plist location: `~/Library/LaunchAgents/de.integrahub.octowiz-daemon.plist`

### `allowed_roots`
The daemon rejects any task whose `cwd` is not under a path in `OCTOWIZ_ALLOWED_ROOTS`.
Add the missing repo path to both `settings.json` and the launchd plist, then reload:

1. Edit `~/.claude/settings.json` — add to `"env"`:
```json
"OCTOWIZ_ALLOWED_ROOTS": "/Users/razu/Documents/octowiz:/Users/razu/Documents/aelli:/Users/razu/Documents/gfe-allspark"
```

2. Edit `~/Library/LaunchAgents/de.integrahub.octowiz-daemon.plist` — update the
   `OCTOWIZ_ALLOWED_ROOTS` string in `EnvironmentVariables` to include the new path.

3. Reload:
```bash
launchctl unload ~/Library/LaunchAgents/de.integrahub.octowiz-daemon.plist
launchctl load  ~/Library/LaunchAgents/de.integrahub.octowiz-daemon.plist
```

### `aelli_python`
The Python A2A server lives in the plugin at `apps/a2a-agent`. The session-start
hook auto-starts it, and since 0.9.18 also auto-restarts it on version skew
(checking `/health` against the installed plugin version, killing only the
pid-verified uvicorn on the configured port). Manual restart for older plugins
or a wedged server:
```bash
# stop the recorded pid (verify it is the uvicorn first)
PID=$(cat ~/.cache/aelli-cc/a2a-agent.pid 2>/dev/null)
ps -p "$PID" -o command= | grep -q uvicorn && kill "$PID"

# respawn from the installed plugin
cd "$CLAUDE_PLUGIN_ROOT/apps/a2a-agent"
python3 -m uvicorn main:app --host 127.0.0.1 --port 8765 &
```
Confirm version matches the plugin:
```bash
curl -s http://localhost:8765/health
node -e "console.log(require('$CLAUDE_PLUGIN_ROOT/package.json').version)"
```

### `plugin_cache`
Force reinstall the plugin from the registry:
```bash
claude plugins install octowiz --force
```
For dev work: point `CLAUDE_PLUGIN_ROOT` at the source repo and restart Claude Code.

### `session_subscribers`
```bash
pkill -f session-subscriber.js
```

### `routing_bundle`
Rebuild the LiteLLM memory bundles:
```bash
octowiz-cache build --all --namespace "${OCTOWIZ_NAMESPACE:-allspark}"
```

### `workflow_runs_failing`
Workflow runs show `{"error": "server restarted"}` because AELLI was redeployed
while they were in-flight. The `cleanupStalledRuns()` on startup marks all
`status=running` runs as failed.

**Fix:** Upgrade AELLI to v1.2.7+ which adds a SIGTERM drain (30s) and sets
`stop_grace_period: 35s` in docker-compose. Workflows that complete within the
drain window will land their terminal PATCH before the process exits.

Verify the fix is active:
```bash
ssh integra42 "docker inspect aelli --format '{{.Config.StopTimeout}}'"
# Should print: 35
```

If still on an older version, deploy the latest:
```bash
ssh integra42 "cd /opt/integrahub/aelli && git pull && docker compose up -d --build aelli"
```

---

## Notes

- Pipeline live tests (Mode 1 Step 4) make real requests to AELLI — expect 3–8s.
- A `spec-deviation` advisory in the octowiz dev repo is expected and harmless.
- Session subscribers ≤ 5 are harmless; they clear when sessions end.
- `octowiz-cache` "command not found" → run `pip install -e "$CLAUDE_PLUGIN_ROOT"`.
- Port 3456 (AELLI Node) is remote (integra42) — being closed locally is expected.
- Daemon logs: `~/.cache/aelli-cc/octowiz-daemon.log`
- Hook/bridge logs: `~/.cache/aelli-cc/aelli-cc.log`
- `GET http://localhost:8765/health` is public (0.9.16+) and returns
  `{"status":"ok","version":"<plugin version>"}` — the fastest staleness check.
- Both background services self-heal on version skew at session start: the Node
  daemon since 0.9.17 (plist path), the Python A2A server since 0.9.18
  (/health version + pid-verified kill).
- Since 0.9.18 jest runs write to a temp cache dir — entries in
  `aelli-cc.log` are real production events, not test fixtures.
