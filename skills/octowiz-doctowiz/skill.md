---
name: octowiz-doctowiz
description: >
  The Octowiz doctor — diagnose, monitor, and fix the full octowiz + AELLI
  integration. Use whenever octowiz or AELLI isn't behaving correctly, a hook
  isn't firing, an advisory isn't returning, or you want a real-time activity
  feed. Also guides first-time setup, configuration from scratch, and upgrading
  from older versions (especially 0.5.x). Invoke as /octowiz:doctowiz for a full
  health check, or add a keyword: "monitor", "watch", "setup", "install",
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

# AELLI version (if running)
node -e "try{const p=require(require('os').homedir()+'/Documents/aelli/package.json'); console.log('aelli', p.version)}catch(e){console.log('aelli not found locally')}"

# LiteLLM — two separate env var groups are required:
# Group A: octowiz-cache (memory / doctrine reads)
echo "LITELLM_BASE_URL:      ${LITELLM_BASE_URL:-(not set)}"
echo "LITELLM_ADMIN_API_KEY: ${LITELLM_ADMIN_API_KEY:-${LITELLM_API_KEY:-(not set)}}"
# Group B: bridge.py (hook delivery)
echo "AELLI_LITELLM_BASE:    ${AELLI_LITELLM_BASE:-(not set, falls back to AELLI_DEV_ADVISOR_URL)}"
echo "AELLI_AUTH_TOKEN:      ${AELLI_AUTH_TOKEN:-(not set)}"
# Health check (uses Group A)
[ -n "$LITELLM_BASE_URL" ] && curl -s "$LITELLM_BASE_URL/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print('litellm', d.get('status','?'))" 2>/dev/null || echo "litellm gateway: not reachable"
```

Show a version summary before the diagnostic table. Flag:
- Plugin cache version ≠ source (`$CLAUDE_PLUGIN_ROOT`) → stale cache, run `claude plugins install octowiz --force`
- `LITELLM_BASE_URL` missing → `octowiz-cache` will fail (memory/doctrine reads broken)
- `AELLI_LITELLM_BASE` missing → bridge delivery falls back to direct AELLI on localhost

### Step 2: Memory and doctrine health

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

### Step 3: Run the diagnostic script

```bash
node "$CLAUDE_PLUGIN_ROOT/apps/doctowiz/index.js"
```

Wait for it to complete (3–8 seconds — the pipeline live tests make real AELLI requests).

### Step 4: Interpret results

Display the full markdown output from the script. Then, for every FAIL or WARN
check, add an interpretation block below the table:

**[Check name]** — plain-language explanation of what this means for the developer
and why it matters, followed by the exact fix command from the **Fix reference**
section below.

After all failures and warnings are explained, summarise the overall health:

- **HEALTHY**: "All systems nominal. The full hook → AELLI pipeline is working."
- **DEGRADED**: "The core pipeline is working but [N] warnings need attention. Advisories will still arrive — but [specific risk from the warning]."
- **UNHEALTHY**: "The pipeline has [N] hard failures. Advisories will not arrive until these are fixed."

Then ask: "Want me to fix any of these now?" If the user says yes, run the fix
command(s) inline and re-run the diagnostic to confirm.

### Step 5: Session activity

After the diagnostic, show a quick session snapshot:

```bash
# Recent hook activity — last 10 lines from the bridge log
tail -10 ~/.cache/aelli-cc/aelli-cc.log 2>/dev/null || echo "(no log file yet — no hooks have fired)"

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
echo "=== Octowiz daemon (last 20 lines) ==="
tail -20 /private/tmp/octowiz-daemon.log 2>/dev/null || echo "(daemon log not found)"

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

If both logs are empty or missing:

> "No activity yet. Make sure a Claude Code session with octowiz is running,
> then trigger a hook by editing a file or submitting a prompt. Re-run
> `/octowiz:doctowiz monitor` to see the output."

If the hook log has entries but the daemon log is empty, note: the hook pipeline
is working but the daemon is not running — advisories arrive but tasks won't
be dispatched.

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
ls ~/.claude/plugins/cache/*/mattpo-skills/ 2>/dev/null | head -1
```

If either is missing:
```bash
claude plugins install superpowers
claude plugins install mattpo-skills
```

`superpowers` provides workflow discipline skills (TDD, brainstorming, worktrees).
`mattpo-skills` provides issue management and domain documentation skills.

### Phase 3 — Environment variables set?

There are two independent groups. Check both:

```bash
echo "--- Group A: octowiz-cache (memory / doctrine) ---"
echo "LITELLM_BASE_URL:      ${LITELLM_BASE_URL:-(NOT SET)}"
echo "LITELLM_ADMIN_API_KEY: ${LITELLM_ADMIN_API_KEY:-${LITELLM_API_KEY:-(NOT SET)}}"
echo ""
echo "--- Group B: bridge.py (hook delivery) ---"
echo "AELLI_LITELLM_BASE:    ${AELLI_LITELLM_BASE:-(not set — uses AELLI_DEV_ADVISOR_URL fallback)}"
echo "AELLI_AUTH_TOKEN:      ${AELLI_AUTH_TOKEN:-(NOT SET)}"
```

**Group A** (`LITELLM_BASE_URL` + `LITELLM_ADMIN_API_KEY`) is required for
`octowiz-cache` to read and write doctrine memories. Without it, workflow routing
will fall back to built-in doctrine and memory seeding will fail.

**Group B** (`AELLI_LITELLM_BASE` + `AELLI_AUTH_TOKEN`) is required for `bridge.py`
to deliver hook events through the LiteLLM gateway. Without `AELLI_LITELLM_BASE`,
it falls back to `AELLI_DEV_ADVISOR_URL` (default: `http://localhost:3456/a2a/dev-advisor`)
— which works for local development but not remote AELLI.

Guide the user to add all four to `~/.claude/settings.json`:

```json
{
  "env": {
    "LITELLM_BASE_URL":      "http://your-litellm-server:4000",
    "LITELLM_ADMIN_API_KEY": "your-admin-key",
    "AELLI_LITELLM_BASE":    "http://your-litellm-server:4000",
    "AELLI_AUTH_TOKEN":      "your-bearer-token"
  }
}
```

`LITELLM_BASE_URL` and `AELLI_LITELLM_BASE` are typically the same value — two
different consumers just read different vars. Explain why `settings.json` and not
`.env`: hook processes are spawned by Claude Code directly and inherit only from
`settings.json` env.

### Phase 4 — AELLI services running?

```bash
node -e "
const net = require('net');
[3456, 8765].forEach(port => {
  const s = net.createConnection({port});
  s.setTimeout(1000);
  s.on('connect', () => { console.log(port + ': open'); s.destroy(); });
  s.on('error', () => console.log(port + ': closed'));
  s.on('timeout', () => { console.log(port + ': timeout'); s.destroy(); });
});
"
```

If ports are closed:
- Port 3456 → AELLI Node.js: `cd ~/Documents/aelli && node index.js`
- Port 8765 → AELLI Python A2A: auto-started by AELLI on first session, or
  `cd ~/Documents/aelli && python -m uvicorn main:app --port 8765`

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

## Mode 4 — Update helper _(temporary — remove once all users are on 0.8.x+)_

When the user is on an older version (especially 0.5.x) and needs to upgrade.
This mode auto-detects what's stale, explains each breaking change, and walks
through the steps in order. Run it once after a `claude plugins install octowiz --force`.

### Step 1: Detect installed version

```bash
# Version reported by the running plugin
node -e "try{const p=require('$CLAUDE_PLUGIN_ROOT/package.json'); console.log(p.version)}catch(e){console.log('unknown')}"

# Version in the plugin cache
ls -1 ~/.claude/plugins/cache/integrahub/octowiz/ 2>/dev/null | sort -V | tail -1
```

If both are `0.8.3` (or higher) and the user just updated: proceed through the
post-upgrade checklist below. If the cache still shows `0.5.x`, the plugin hasn't
been reinstalled yet — do that first:

```bash
claude plugins install octowiz --force
```

Then restart Claude Code before continuing.

### Step 2: Breaking change — env vars renamed (0.5.x → 0.8.0)

This is the change that breaks every 0.5.x installation silently. Check:

```bash
echo "Old (0.5.x) — should be EMPTY now:"
echo "  OCTOWIZ_A2A_URL:       ${OCTOWIZ_A2A_URL:-(not set — good)}"
echo "  OCTOWIZ_INBOUND_SECRET: ${OCTOWIZ_INBOUND_SECRET:-(not set — good)}"
echo ""
echo "New (0.8.x) — must be set:"
echo "  AELLI_AUTH_TOKEN:    ${AELLI_AUTH_TOKEN:-(NOT SET — fix required)}"
echo "  AELLI_LITELLM_BASE:  ${AELLI_LITELLM_BASE:-${LITELLM_BASE_URL:-(NOT SET — fix required)}}"
```

**Why this changed:** In v0.5.x, `bridge.py` POSTed hook events directly to the
Octowiz A2A server (`OCTOWIZ_A2A_URL`). From v0.6.0 (PR #67, single advisory
path), it routes through the LiteLLM gateway (`AELLI_LITELLM_BASE`), which
handles routing to the right AELLI service. The auth secret became a standard
Bearer token (`AELLI_AUTH_TOKEN`).

**If the old vars are still set and the new ones are missing**, guide the user to
update `~/.claude/settings.json`:

Remove from `settings.json`:
```json
"OCTOWIZ_A2A_URL": "...",
"OCTOWIZ_INBOUND_SECRET": "..."
```

Add to `settings.json`:
```json
"AELLI_AUTH_TOKEN": "your-bearer-token",
"AELLI_LITELLM_BASE": "http://your-litellm-server:4000"
```

The bearer token value is the same secret — the format changed, not the value.
Reload Claude Code after editing `settings.json`.

### Step 3: Clean up stale session-subscribers

v0.5.x spawned a long-lived session-subscriber process per session. These
accumulate and are harmless but wasteful. Clean them up:

```bash
pkill -f session-subscriber.js 2>/dev/null && echo "cleaned" || echo "none running"
```

### Step 4: Rebuild memory bundles

The LiteLLM memory schema may have changed between versions. Rebuild:

```bash
octowiz-cache build --all --namespace "${OCTOWIZ_NAMESPACE:-allspark}"
```

If `octowiz-cache` is not found, reinstall the Python package:
```bash
pip install -e "$CLAUDE_PLUGIN_ROOT"
```

### Step 5: Verify with the full diagnostic

```bash
node "$CLAUDE_PLUGIN_ROOT/apps/doctowiz/index.js"
```

All five check phases should now be green. Pay special attention to:
- **Hook pipeline** — if still failing after env var fix, verify the bearer token value is correct
- **LiteLLM delivery route** — if 404, the `aelli-dev-advisor` route may not be registered; check the LiteLLM config on the server
- **AELLI Python A2A** — if port 8765 is still closed, AELLI may need to be restarted to pick up the new architecture

### What changed at each version (reference)

| Version | What changed | User action required |
|---|---|---|
| 0.5.0 | Thin daemon + StoreRegistry baseline | — |
| 0.6.0 | Single advisory path; Python advisor deleted; bridge now routes through LiteLLM — **env vars renamed** | Rename env vars (see Step 2) |
| 0.7.0 | DispatchSession state machine | Restart AELLI |
| 0.8.0 | Bridge routing and auth header hardened | None (vars already renamed in 0.6.0) |
| 0.8.1 | `octowiz.observe` capability handler added | None |
| 0.8.3 | Session-subscriber idle fix; doctowiz skill added | `pkill -f session-subscriber.js` |

---

## Mode 5 — Targeted fix

When the user describes a specific symptom, map it to the likely cause and fix:

| Symptom | Most likely cause | Fix ref |
|---|---|---|
| "Advisories not arriving" | Bad or missing auth token | `auth_token` |
| "Hook fires but nothing happens" | Bridge delivery failure | `bridge_delivery` |
| "Daemon not running" | Process died / never started | `daemon_start` |
| "octowiz-cache not found" | Python package not installed | `pip install -e $CLAUDE_PLUGIN_ROOT` |
| "Port 3456 connection refused" | AELLI Node not running | `aelli_node` |
| "Changes to skill not taking effect" | Stale plugin cache | `plugin_cache` |
| "Too many session-subscriber processes" | Pre-PR-#73 sessions | `session_subscribers` |
| "spec-deviation on every edit" | Normal in octowiz dev repo | No fix — expected |
| "Was on 0.5.x, just updated, still broken" | Env vars not migrated | Switch to Mode 4 (Update helper) |

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
```bash
node "$CLAUDE_PLUGIN_ROOT/index.js" &
```
Confirm it started: `tail -5 /private/tmp/octowiz-daemon.log`

### `aelli_node`
```bash
cd ~/Documents/aelli && node index.js
```

### `aelli_python`
AELLI auto-starts the Python A2A on first session. If still closed:
```bash
cd ~/Documents/aelli && python -m uvicorn main:app --port 8765
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

---

## Notes

- Pipeline live tests (Mode 1 Step 3) make real requests to AELLI — expect 3–8s.
- A `spec-deviation` advisory in the octowiz dev repo is expected and harmless.
- Session subscribers ≤ 5 are harmless; they clear when sessions end.
- `octowiz-cache` "command not found" → run `pip install -e "$CLAUDE_PLUGIN_ROOT"`.
