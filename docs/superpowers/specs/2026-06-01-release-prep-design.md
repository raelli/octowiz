# Release Prep Design — raelli/aelli · raelli/octowiz · raelli/aelli-cc-plugin

**Date:** 2026-06-01  
**Goal:** Prepare all three repos for first team presentation. No new features — review, verify, and prove the setup is complete and working end-to-end.  
**Approach:** Parallel hygiene + review → fix findings → full A2A round-trip demo.

---

## Section 1 — Branch & Repo Hygiene

Runs in parallel with Section 2. Four concrete actions plus a public safety scan.

1. **aelli**: merge `feat/local-model-backend` → `main`. Adds dual LLM backend env var (`AELLI_LLM_BACKEND`), updated default model names, and jest `.claude/` ignore pattern. All 74 tests pass on the branch.

2. **aelli-cc-plugin**: `git pull` — fast-forward 1 commit (`chore: sync plugin.json to v0.4.0`).

3. **aelli-cc-plugin**: prune 5 stale worktrees (`sp1-impl`, `bridge-split`, `fix+packaging-guardrails`, `setup-agent-skills`, `logical-rolling-key`). Jest must report 4 suites / 43 tests, not 23 suites / 250.

4. **octowiz**: `fix/version-bump-0.2.0` tracks `origin/main` and is identical in content — the local `main` branch is stale (behind `origin/main`). Run `git fetch && git checkout main && git pull` to sync local main, then commit the untracked architecture docs from `docs/` into the repo. The Codex-findings fixes will land via a separate PR to main.

5. **Public repo safety scan (all three)**: check for hardcoded secrets, tokens, API keys, committed or referenced `.env` files with real values, sensitive comments, private hostnames/IPs, or any data that must not be public. Produce a per-repo finding list — fix or redact everything before the presentation.

**Exit criteria:** all three repos on `main`, clean working trees, accurate test output, zero public-safety findings outstanding.

---

## Section 2 — Parallel Review Phase

Four workstreams run simultaneously via workflow agents.

### Code Review (one agent per repo)

- **aelli**: A2A dispatch, dev-advisor session handling, orchestrator LLM client, auth middleware
- **octowiz**: ClaudeCliAdapter, dispatch/manage_agents capability, InvocationPolicy, A2A bridge
- **aelli-cc-plugin**: a2a-client SSE handling, event-builder, git-context, hooks wiring

### Security Review (one agent per repo)

- Auth token handling and transmission (`AELLI_AUTH_TOKEN`, `x-octowiz-secret`)
- Input validation at A2A boundaries
- Subprocess injection risk in ClaudeCliAdapter (cwd/task args)
- SSE stream trust boundary in the plugin
- Any findings carried forward from the public safety scan (Section 1, step 5)

### Architecture Conformance Check (single agent)

Cross-reference the four architecture docs against the actual implementation:

- Capabilities listed in `card.py` that are not yet implemented
- A2A flows described in the docs that are not wired in code
- Memory layers referenced in the ÆLLI Architecture Vision that are absent or stubbed
- Any divergence between the Rollenmodell routing rules and actual LLM client behaviour

### aelli-cc-plugin vs octowiz Merge Analysis (single agent)

- Map overlapping responsibilities: octowiz has `claude_code_bridge`, `ClaudeCliAdapter`, session dispatch; the plugin also bridges Claude Code to aelli via hooks and SSE
- What the plugin does that octowiz does not: user-side hook lifecycle, git context extraction, event building, Claude Code plugin packaging format
- What octowiz does that the plugin does not: server-side session management, InvocationPolicy, manage_agents, advise/plan/review capabilities
- Deployment model evaluation: plugin is installed per-user inside Claude Code; octowiz is a server process — merging changes the distribution story
- Output: a clear recommendation (merge and how / keep separate and why / extract a shared library)

**Output from all workstreams:** prioritised findings — P0 blocker / P1 should-fix / P2 nice-to-have. The merge analysis produces a separate recommendation document. Only P0 and P1 findings advance to Section 3.

---

## Section 3 — Fix Phase

All P0 and P1 findings addressed before integration testing begins.

**P0 blockers first:** fixed one at a time, full test suite re-run after each to confirm no regression.

**P1 should-fix:** batched by repo and applied together, then full test suite re-run per repo.

**Merge analysis decision gate:** if the analysis recommends merging aelli-cc-plugin into octowiz, a go/no-go decision is made with the user before any consolidation work begins. A merge is scoped as a separate workstream — it does not block the release demo.

**Exit criteria:** all P0 and P1 findings resolved, all three test suites green, each repo has a clean commit or PR summarising fixes.

---

## Section 4 — Integration Verification (Full A2A Round-Trip Demo)

Verifies the live system works end-to-end with all three repos running.

### Environment Prerequisites

Before starting any server, confirm the following env vars are set (or documented in a `.env.example` if not using real values for the test):

- `AELLI_AUTH_TOKEN` — shared secret for plugin → aelli auth
- `OCTOWIZ_INBOUND_SECRET` — shared secret for octowiz A2A auth (`x-octowiz-secret` header, read by FastAPI middleware and bridge)
- `LITELLM_BASE_URL` / `LITELLM_API_KEY` — or `AELLI_LLM_BACKEND=local` with `AELLI_LOCAL_LLM_URL`
- `OCTOWIZ_BASE_URL` — octowiz server address as seen by aelli (default: `http://localhost:8000`)
- `AELLI_DEV_ADVISOR_URL` — aelli address as seen by the plugin (default: `http://localhost:3456/a2a/dev-advisor`)

### Startup Sequence

1. Start aelli: `node index.js` (port 3456) — confirm `[AELLI] Server running on port 3456`
2. Start octowiz: `uvicorn apps.a2a-agent.main:app` — confirm agent card at `/a2a/octowiz/.well-known/agent.json`
3. Load aelli-cc-plugin into a Claude Code session — confirm `[AELLI CC Plugin v0.4.0] starting...` and `plugin-ready`

### Three Verification Flows

1. **Plugin → aelli observe**: trigger a Claude Code tool use, confirm the hook fires, the event arrives at aelli's `/a2a/dev-advisor`, and aelli returns a valid A2A response
2. **aelli → octowiz dispatch**: send an `octowiz.dispatch` request, confirm octowiz starts a background Claude Code session and returns a `sessionId`
3. **octowiz → aelli advise**: send an `octowiz.advise` request with a sample event, confirm octowiz processes it and returns a risk advisory response (`octowiz.escalate_to_aelli` is not yet implemented; `octowiz.advise` is the correct implemented capability to verify this direction)

### Pass Criteria

- All three flows complete without errors
- No unhandled exceptions in server logs
- Auth headers validated correctly (bad token is rejected)
- Plugin reconnects cleanly if aelli is restarted mid-session

**Exit criteria:** all three flows verified, logs clean, auth tested — system is demo-ready.
