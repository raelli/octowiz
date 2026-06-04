# Sandcastle Dual-Implementation Investigation

**Date:** 2026-06-04
**Status:** Investigation note (not an ADR)
**Author:** Architecture review pass

---

## Summary

Two implementations named `SandcastleProvider` exist in the octowiz repo:

- **JS wrapper** — `src/providers/sandcastle.js` — thin delegation to the `@ai-hero/sandcastle` npm package
- **Python implementation** — `providers/sandcastle/provider.py` + `providers/sandcastle/runner.py` — custom Docker/Podman subprocess management, used by the A2A agent via `apps/a2a-agent/capabilities/run_sandboxed.py`

The two implementations are **not diverged versions of the same thing**. They are architecturally distinct systems with different purposes and zero shared caller paths. The divergence is intentional and carries one real bug risk (documented below).

---

## File Inventory

| File | Language | Purpose |
|---|---|---|
| `src/providers/sandcastle.js` | JS | Thin wrapper around `@ai-hero/sandcastle` npm SDK |
| `providers/sandcastle/provider.py` | Python | In-process state manager for Docker/Podman subprocess runs |
| `providers/sandcastle/runner.py` | Python | Command builder + subprocess seams (`build_container_cmd`, `_start_container`, `_run_cmd`) |
| `providers/sandcastle/status.py` | Python | Single source of terminal state constants (`completed`, `error`, `timed_out`) |
| `apps/a2a-agent/capabilities/run_sandboxed.py` | Python | A2A capability layer: validates, dispatches, polls, and enforces timeouts |
| `tests/providers/sandcastle.test.js` | JS | JS wrapper tests — all use injected mock `runFn`, never invoke real Docker |
| `providers/sandcastle/tests/test_provider.py` | Python | Provider unit tests — mock `_start_container` / `_run_cmd` seams |
| `providers/sandcastle/tests/test_runner.py` | Python | Runner unit tests — command construction and subprocess seams |
| `apps/a2a-agent/tests/test_run_sandboxed.py` | Python | Capability-layer tests — `_MockSandcastleProvider` injects full mock |

---

## How Each Implementation Works

### JS Wrapper (`src/providers/sandcastle.js`)

**Container start:** Delegates entirely to `@ai-hero/sandcastle`'s `run()` function. No direct subprocess management.

**Monitoring:** Not implemented locally. The `@ai-hero/sandcastle` package handles the full agent lifecycle internally (Effect-based fiber runtime, with idle timeout and abort signal support per its README and dist source).

**Timeout:** Managed by `@ai-hero/sandcastle` internally (idle timeout, prompt expansion timeout — both are internal Effect fibers inside the npm package). The octowiz JS wrapper does not set any timeout itself.

**Cleanup/kill:** Fully delegated to `@ai-hero/sandcastle`. The JS wrapper has no kill or stop method.

**Branch default:** `defaultRun` hardcodes `branch: branch || "aelli-sandcastle"`. If no branch is passed, it falls back to `"aelli-sandcastle"` rather than leaving branch undefined/null.

---

### Python Implementation (`providers/sandcastle/provider.py` + `runner.py`)

**Container start:** `SandcastleProvider.dispatch()` calls `build_container_cmd()` (pure function) then `_start_container()` (Popen seam). Returns a `run_id` UUID. Log output is redirected to a tempfile. Container runs with `--rm` so it auto-removes on exit.

**Monitoring:** Polling-based. `get_status()` checks `proc.poll()` on each call. Status transitions: `running` → `completed` (exit 0) or `error` (exit != 0).

**Timeout:** Two-layer:
1. **Provider-level (`SANDCASTLE_TIMEOUT`):** `get_status()` compares `time.monotonic() - run.start_time > run.timeout`. On breach, immediately calls `_kill_container()` and transitions status to `timed_out`.
2. **Capability-level (`OCTOWIZ_DISPATCH_TIMEOUT`):** `handle_run_sandboxed` in `run_sandboxed.py` maintains a `deadline` with `time.monotonic()`. On breach, calls `provider.stop(run_id)` and returns `{"status": "error", "message": "timeout after Ns"}`.

**Cleanup/kill:** `_kill_container()` issues `[container_provider, "kill", container_name]` as a blocking subprocess call (30s timeout) via `_run_cmd()`, then also calls `proc.kill()` to terminate the Popen handle.

**`wait=False` mode:** Immediately returns `{"status": "dispatched", "run_id": ...}` and spawns an `asyncio.create_task` watchdog that sleeps `SANDCASTLE_TIMEOUT` seconds and then calls `provider.stop()`. This is the only async-fire-and-forget path.

**Branch handling:** Branch passed as positional arg to `sh -c 'git checkout "$1" && claude --print -- "$2"' -- branch task`. If no branch, uses `claude --print -- task` directly. No default branch name is injected.

---

## Caller Map

### JS path callers

```
src/providers/sandcastle.js   ← only caller: tests/providers/sandcastle.test.js
```

The JS `SandcastleProvider` is **not imported by any production code** in `src/`, `hooks/`, `skills/`, `packages/`, `index.js`, or `src/daemon.js`. It is only exercised by its own test file.

`src/daemon.js` (the Node.js pull-based daemon) forwards **all** capability work to the Python A2A server via HTTP JSON-RPC (`_forwardToA2A`). There is no dynamic provider loading, no `readdirSync`-based plugin scan, and no string-keyed provider registry in `src/`. The daemon never touches `src/providers/sandcastle.js`.

### Python path callers

```
apps/a2a-agent/capabilities/run_sandboxed.py
  ← apps/a2a-agent/dispatch.py  (capability: "octowiz.run_sandboxed")
    ← A2A HTTP handler / test suite
```

The Python `SandcastleProvider` is the **only live execution path** for sandbox runs in production.

---

## Divergences

### 1. Timeout architecture (real divergence)

| Dimension | JS wrapper | Python implementation |
|---|---|---|
| Timeout enforcement | Delegated to `@ai-hero/sandcastle` (idle + prompt expansion timeouts; internal Effect fibers) | Two-layer: provider-level `SANDCASTLE_TIMEOUT` + capability-level `OCTOWIZ_DISPATCH_TIMEOUT` |
| Timeout on container kill | Not visible; npm package handles it | Explicit `docker kill <name>` + `proc.kill()` |
| Env var controlling timeout | None exposed | `SANDCASTLE_TIMEOUT` (provider) and `OCTOWIZ_DISPATCH_TIMEOUT` (capability) |
| Timeout when `wait=False` | N/A | Background `asyncio` watchdog fires `provider.stop()` after `SANDCASTLE_TIMEOUT` |

**Bug risk: None currently**, because JS and Python paths have zero caller overlap. However, if the JS path is ever wired into production (e.g., a Node.js capability dispatcher), a caller relying on `SANDCASTLE_TIMEOUT` env var would get no-op behavior — the JS wrapper has no timeout of its own and makes no contract about what timeout `@ai-hero/sandcastle` applies.

### 2. Branch default behavior (real divergence)

| Dimension | JS wrapper | Python implementation |
|---|---|---|
| No branch supplied | Falls back to `"aelli-sandcastle"` hardcoded | No branch passed to `build_container_cmd`; `claude --print -- task` used directly |

If both paths were ever used for the same task, branch behavior would differ silently. The Python path correctly represents "no branch" as `None`; the JS path injects a default branch name that may or may not exist.

### 3. JS wrapper API is incompatible with the installed `@ai-hero/sandcastle` package (critical)

The JS `defaultRun` calls:

```js
run({ task, cwd, branch: branch || "aelli-sandcastle" })
```

The installed package (`^0.7.0`, present in `node_modules`) exposes `run(options: RunOptions)` where `RunOptions` requires `{ agent: AgentProvider, sandbox: SandboxProvider, prompt?: string, promptFile?: string, ... }`. Neither `task` nor `branch` are valid `RunOptions` fields. `cwd` is an optional "host repo directory" field — unrelated to a task description.

Verified against `node_modules/@ai-hero/sandcastle/dist/index.d.ts` line 422.

**Conclusion:** `defaultRun` would pass invalid arguments at runtime. The JS `SandcastleProvider.run()` is not merely uncalled — it is non-functional against the version already installed. Any future attempt to activate the JS path would surface a silent incorrect call (no TypeScript enforcement at runtime in CJS) that would likely throw or return unexpected results.

This elevates the recommendation for the JS file: it should be removed rather than left with a "retained for future use" comment.

---

### 4. Container stop / cleanup API (structural divergence)

| Dimension | JS wrapper | Python implementation |
|---|---|---|
| Stop / kill API | No `stop()` method; no kill logic | `stop(run_id)` / `_kill_container(run)` — explicit `docker kill` + `proc.kill()` |
| Status tracking | No status tracking | In-memory `_SandboxRun` dataclass, polled per `get_status()` call |
| Log capture | Delegated to npm package | Explicit tempfile, read via `get_logs(run_id)` |

This is the most significant structural gap. If the JS wrapper were ever expected to support graceful cleanup on timeout or server shutdown, there is no equivalent surface for it to hook into.

### 5. Input validation (partial divergence)

| Check | JS wrapper | Python implementation |
|---|---|---|
| `task` required | Yes (`run()`) | Yes (capability layer) |
| `cwd` required | Yes (`run()`) | Yes (capability layer) |
| `task` starts with `-` | No | Yes (capability layer + `build_container_cmd`) |
| `branch` starts with `-` | No | Yes (both layers) |
| `branch` regex validation | No | Yes (`_BRANCH_RE` in both layers) |
| `container_provider` allowlist | No | Yes (`_VALID_CONTAINER_PROVIDERS`) |
| `shutil.which` availability check | No | Yes |
| `cwd` absolute path / allowed-roots guard | No | Yes (`validate_cwd`) |

The JS wrapper only checks `task` and `cwd` presence. All injection-prevention guards live in the Python layer. This is not a bug in the current setup (different execution environments), but would become a security gap if the JS path were ever used without a separate validation layer in front of it.

---

## Test Coverage Assessment

### JS tests (`tests/providers/sandcastle.test.js`)

All 5 tests inject a mock `runFn`. The test suite:
- Verifies `SandcastleProvider` exports and instantiates
- Verifies `run()` calls the injected function with correct args
- Verifies guard throws for missing `task` / `cwd`
- Verifies error propagation

`defaultRun` (the path that calls `@ai-hero/sandcastle`) is **never exercised by tests**. There are no integration tests or container-level tests for the JS path.

### Python tests

- `test_provider.py`: 17 tests covering `dispatch`, `get_status`, `get_logs`, `stop`, and status constant helpers. Uses `_start_container` and `_run_cmd` as injectable mock seams.
- `test_runner.py`: 22 tests covering `build_container_cmd` (all branches: no-branch, with-branch, env passthrough, validation), `_start_container` seam, and `_run_cmd` seam.
- `test_run_sandboxed.py`: Full capability-layer tests with a `_MockSandcastleProvider`. Covers validation, `wait=True/False`, watchdog, timeout-stops-container, branch/provider forwarding, and dispatch routing.

Python test coverage is thorough. JS test coverage is shallow (mock-only, no real subprocess path tested).

---

## Is the Divergence Real and Bug-Prone?

**The divergence is real but currently inert.** Because the JS `SandcastleProvider` has no production callers, bugs introduced by architectural differences cannot manifest at runtime. The two implementations are not in competition — they are architecturally isolated.

**The JS wrapper is effectively dormant.** It delegates everything to `@ai-hero/sandcastle`, an opinionated TypeScript SDK designed to manage the full agent lifecycle (worktrees, branch strategy, merge-back, idle timeout). This is a higher-level abstraction than the Python path, which manages raw Docker/Podman subprocesses with explicit poll/kill/log mechanics.

The Python path is the production implementation and is well-tested.

---

## Recommendation

**Do not pursue convergence as a code change.** The two exist in different execution environments (Node.js daemon vs. Python A2A agent) and serve different levels of abstraction. The JS wrapper is not merely unused — it is broken against the installed SDK.

Recommended actions (in priority order):

1. **Remove `src/providers/sandcastle.js` and `tests/providers/sandcastle.test.js`.** The JS wrapper:
   - Has no production callers (daemon forwards everything to Python via HTTP)
   - Is non-functional against `@ai-hero/sandcastle@^0.7.0` (wrong `run()` call shape)
   - Was introduced in PR #63 (feat: replace Python server with Node.js pull-based daemon) as a transitional artifact that was never wired up
   - Carries misleading naming (same class name as the live Python implementation)

   The `@ai-hero/sandcastle` package can always be re-introduced when a concrete JS sandbox use-case exists, with a correct implementation.

2. **The Python implementation requires no changes.** Timeout, cleanup, and input validation are all correct, well-tested, and actively in production.

3. **If a future Node.js capability for sandbox runs is ever needed**, do not reuse the current `src/providers/sandcastle.js` stub. Start fresh with:
   - Correct `@ai-hero/sandcastle` API usage (`agent`, `sandbox`, `prompt` fields)
   - A `stop()` equivalent or AbortController integration
   - Input validation equivalent to the Python layer (task/branch injection guards, `cwd` allowlist)
   - Explicit timeout control

---

## Git History Note

`src/providers/sandcastle.js` was introduced in PR #63 ("feat: replace Python server with Node.js pull-based daemon"). That PR converted octowiz from a Python-only A2A server to the current architecture where a Node.js daemon forwards all capabilities to the Python A2A server via HTTP. The JS sandcastle file appears to be a leftover stub from that transition, never connected to any dispatch path.

---

## Files Referenced

- `src/providers/sandcastle.js`
- `providers/sandcastle/provider.py`
- `providers/sandcastle/runner.py`
- `providers/sandcastle/status.py`
- `apps/a2a-agent/capabilities/run_sandboxed.py`
- `apps/a2a-agent/dispatch.py`
- `tests/providers/sandcastle.test.js`
- `providers/sandcastle/tests/test_provider.py`
- `providers/sandcastle/tests/test_runner.py`
- `apps/a2a-agent/tests/test_run_sandboxed.py`
