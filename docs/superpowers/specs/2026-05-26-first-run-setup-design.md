# First-Run Setup & Onboarding

**Date:** 2026-05-26
**Status:** Draft (rev 3 — adds escape hatch, 24h cache TTL, GEMINI.md precedence, cleanup)

---

## Problem statement

When a developer installs octowiz and invokes `/octowiz` for the first time, none of the dependent plugins (superpowers, mattpocock, antfu) are guaranteed to be installed, LiteLLM is unlikely to be configured, and the repo may be missing project-level setup (agent instructions file, domain docs). The workflow skill silently proceeds as if everything is in place, producing confusing failures downstream.

There is also no mechanism to avoid re-running setup on subsequent invocations once complete, or to resume gracefully if setup is interrupted mid-session.

---

## Proposed solution

A two-phase setup system driven entirely by live environment observation. State files are used only as resume bookmarks — readiness is always recomputed from observed reality, not from stored flags.

- **Phase 1 (per-repo init):** The first time `octowiz-workflow` runs in a repo with no `.octowiz/setup-state.json`, it creates the file (as a resume bookmark skeleton) and `ONBOARDING.md`.
- **Phase 2 (interactive first-run):** `octowiz-workflow` runs a live environment check at the top. If any gap is detected, it invokes `octowiz:setup` instead of the A/B/C/D menu. `octowiz:setup` delegates to four focused phase skills. Only phases with real gaps run.

No install-time side effects. Machine bootstrap (`~/.octowiz/machine-state.json`) is created at runtime on first use if absent.

---

## User stories

- As a developer who just installed octowiz, I want to be guided step-by-step through plugin installation and LiteLLM setup, with each step explained before it runs.
- As a developer working in a new repo, I want octowiz to scan the project and tell me exactly what it found and what it will do, before doing anything.
- As a developer re-invoking `/octowiz` after setup is complete, I want no setup intercept — just the normal A/B/C/D workflow menu.
- As a developer who was interrupted mid-setup, I want `/octowiz` to resume from where it left off without re-running completed steps.
- As a developer on a second machine cloning a repo with `.octowiz/setup-state.json` committed, I want octowiz to run only the per-machine steps, skipping repo-level steps already confirmed done.

---

## Implementation decisions

### Readiness: observed state first, bookmarks second

On every `/octowiz` entry, the workflow runs a **live environment check** before anything else:

1. Are required plugins present on disk? (check `~/.claude/plugins/` directly)
2. Are `LITELLM_BASE_URL` and API key env vars set?
3. Has `octowiz-cache get --role routing` been verified to work? (cache the result in `machine-state.json`; re-verify if `cache_verified_at` is absent or older than 24h — the call is a live network request to LiteLLM)
4. Does an agent instructions file exist (`AGENTS.md`, `CLAUDE.md`, or `GEMINI.md`) with an `## Agent skills` section?
5. Has mattpocock setup been run? (observed: does the agent instructions file have octowiz-related skill entries?)
6. Is antfu setup done or deferred? (use `setup-state.json` as a resume bookmark)

If any check fails → intercept and run setup for that gap. If all pass → normal workflow.

State files record progress for resumption. They are **not** the source of truth for readiness. Committed booleans in `setup-state.json` that contradict observed reality are ignored for the readiness check.

### State files

Two resume-bookmark files, one per scope:

**`~/.octowiz/machine-state.json`** — per-developer, never committed. Created at runtime on first use if absent.
```json
{
  "first_seen": "2026-05-26T10:00:00Z",
  "plugins": {
    "superpowers": "verified",
    "mattpocock": "verified",
    "antfu": "pending"
  },
  "litellm": {
    "cache_verified_at": "2026-05-26T10:05:00Z"
  },
  "dismissed_checks": []
}
```

`dismissed_checks` is populated when the developer chooses to skip a failing check (see Escape hatch section). An empty array is the default; absent is treated as empty.

**`.octowiz/setup-state.json`** — per-repo, committed. Used only for antfu deferral bookkeeping and resume progress.
```json
{
  "created_at": "2026-05-26T10:00:00Z",
  "mattpocock_setup": false,
  "antfu_relevant": null,
  "antfu_setup": false,
  "antfu_deferred": false
}
```

Note: `context_md` and `adr_scaffold` are not tracked — domain docs follow a lazy-creation model and are never scaffolded by setup (see Out-of-scope).

### Agent instructions file detection

Repos may use `AGENTS.md` (Codex/Claude/Gemini-compatible), `CLAUDE.md` (Claude-only), or neither. Detection precedence:

| Priority | File | Action |
|---|---|---|
| 1 | `AGENTS.md` exists | Use it as canonical agent instructions file |
| 2 | `CLAUDE.md` exists | Use it as canonical agent instructions file |
| 3 | `GEMINI.md` exists | Use it as canonical agent instructions file |
| 4 | None exist | Flag in ONBOARDING.md; defer to user — do not auto-create |

Setup is only allowed to **read and append** to whichever file is detected. It never creates a new agent instructions file from scratch or migrates content between files. If neither exists, octowiz notes it in ONBOARDING.md and proceeds — missing agent instructions does not block setup.

Antfu setup and mattpocock setup both append to the detected file. If no file exists, their additions are deferred and noted in ONBOARDING.md.

### ONBOARDING.md lifecycle

Created at Phase 1 init as a human-readable progress checklist and agent resumption anchor. Updated after each completed phase step. Deleted by `octowiz:setup-verify` when the live environment check passes cleanly.

Example structure:
```markdown
# Octowiz Setup

## Environment (per-machine)
- [x] Plugins installed — superpowers, mattpocock, antfu
- [ ] LiteLLM cache configured

## Project (per-repo)
- [ ] mattpocock skills setup (agent instructions file: AGENTS.md)
- [!] CONTEXT.md — not present; will be created lazily by /grill-with-docs
- [!] docs/adr/ — not present; will be created lazily by /grill-with-docs
- [~] antfu skills — Vue + TypeScript detected, setup pending

## Next step
Running octowiz:setup-cache...
```

Resumption: if `/octowiz` is re-invoked and ONBOARDING.md is present, the live check runs first. If the environment is now clean, ONBOARDING.md is deleted and normal workflow proceeds. Otherwise the orchestrator finds the first gap and resumes.

Stale file rule: if ONBOARDING.md is present but the live check passes, delete ONBOARDING.md and proceed normally.

### Auto-intercept in octowiz-workflow

At the top of the skill, before Step 1 (Read project setup):

1. Run live environment check (plugin dirs, env vars, agent instructions file, mattpocock setup)
2. If `machine-state.json` absent → create skeleton, set all plugin/litellm fields to `pending`
3. If `setup-state.json` absent → run Phase 1 init (create file + ONBOARDING.md)
4. If any live check fails → invoke `octowiz:setup`
5. If all live checks pass → proceed to A/B/C/D menu

### Phase skills

**`octowiz:setup`** (orchestrator)
- Re-runs the live environment check
- Builds a gap list from the results
- Calls phases in order: `setup-plugins` → `setup-cache` → `setup-repo` → `setup-verify`
- Passes the gap list to each phase; phases skip steps where no gap exists

**`octowiz:setup-plugins`** (per-machine)
- Checks `~/.claude/plugins/` directly for each plugin
- For each missing plugin: explains what it does and why octowiz needs it, gives the exact `claude plugins install <url>` command, waits for user confirmation, verifies presence after install
- Plugins: superpowers, mattpocock, antfu (all installed upfront — avoids a second pass after repo scan)
- Updates `machine-state.json` with `"verified"` once confirmed present on disk

**`octowiz:setup-cache`** (per-machine)
- Checks `LITELLM_BASE_URL` and `LITELLM_ADMIN_API_KEY` env vars directly
- If missing, guides the user to add them to `~/.claude/settings.json`
- Seeds all four role bundles: routing, planner, implementer, reviewer
- Verifies end-to-end with `octowiz-cache get --role routing`
- Records `cache_verified_at` timestamp in `machine-state.json`
- On subsequent invocations: only re-verifies if `cache_verified_at` is absent or older than 24h

**`octowiz:setup-repo`** (per-repo)
- Scans the repo using the signal table below
- Detects agent instructions file (AGENTS.md > CLAUDE.md > GEMINI.md > none)
- Writes the tailored checklist into ONBOARDING.md before running any steps
- Invokes mattpocock setup if agent instructions file is missing the octowiz skill entries (appends to detected file; defers if no file)
- Flags missing CONTEXT.md and docs/adr/ in ONBOARDING.md as lazy-creation items — does NOT scaffold them
- Applies the antfu decision tree
- Updates `setup-state.json`

**`octowiz:setup-verify`** (final gate)
- Re-runs the full live environment check
- If all gaps are resolved: deletes ONBOARDING.md, marks `setup-state.json` complete
- If gaps remain: reports which checks still fail and what to do

### Repo scan signals

| Signal | Conclusion |
|---|---|
| No files except hidden | Empty project |
| `AGENTS.md` present | Use as canonical agent instructions file |
| `CLAUDE.md` present (no AGENTS.md) | Use as canonical agent instructions file |
| `GEMINI.md` present (no AGENTS.md or CLAUDE.md) | Use as canonical agent instructions file |
| None present | Flag in ONBOARDING.md; defer agent file creation to user |
| `package.json` with `vue`/`vite`/`typescript` | TypeScript/Vue — antfu highly relevant |
| `package.json` with `react` | React — antfu somewhat relevant |
| `package.json` only (no TS/Vue) | Generic JS — antfu low relevance |
| `pyproject.toml` / `setup.py` only | Python — antfu not applicable |
| Both `package.json` + `pyproject.toml` | Polyglot — antfu relevant for frontend layer |
| `CONTEXT.md` present | Note in ONBOARDING.md as already present |
| `docs/adr/` present | Note in ONBOARDING.md as already present |
| `git remote -v` has github.com | `gh` CLI available for issue tracker |

### Antfu decision tree

| Detected | Action |
|---|---|
| TypeScript / Vue / Vite | Run antfu setup |
| Python / Go / Rust only | Set `antfu_relevant: false`, skip |
| Empty project | Set `antfu_deferred: true`; re-check on next session when stack detected |
| Polyglot | Treat as TypeScript/Vue |

Antfu setup means: detect relevant sub-skills (vue, vite, vitest, pnpm, unocss) from `package.json`, append them to the `## Agent skills` section of the detected agent instructions file with a one-line description each. If no agent instructions file exists, defer and note in ONBOARDING.md.

### Re-run safety

Readiness is always re-derived from observed environment. State file values are treated as hints, not truth. Specific cases:

| Condition | Behaviour |
|---|---|
| Live check passes, ONBOARDING.md absent | Normal workflow |
| Live check passes, ONBOARDING.md present (stale) | Delete ONBOARDING.md, normal workflow |
| Live check fails for any reason | Auto-intercept, run setup for failing checks only |
| Plugin was installed but later removed | Live check detects absence → setup-plugins re-runs for that plugin |
| `mattpocock_setup: true` in state but entries missing from agent file | Live check detects gap → setup-repo re-runs mattpocock setup |
| `antfu_deferred: true` and TS/Vue now detected | Live check flags antfu gap → setup-repo runs antfu setup |
| New machine, cloned repo with setup-state.json committed | machine-state.json absent → live check fails for plugins/cache → runs per-machine phases only |
| Developer dismisses a check (e.g., offline, LiteLLM not available yet) | `dismissed_checks` field written to `machine-state.json`; that check is skipped on next invocation |

### Escape hatch from the intercept loop

If every `/octowiz` invocation re-intercepts because a gap cannot be satisfied (e.g., developer is offline, LiteLLM is not configured yet, or a plugin is intentionally absent), the developer can choose to proceed anyway. The intercept prompt always offers:

> "Setup incomplete. Skip this check and proceed to the workflow? (y/N)"

If the developer responds `y`, the specific failing check is recorded in `dismissed_checks` in `machine-state.json`:

```json
{
  "dismissed_checks": ["litellm_cache", "plugin_antfu"]
}
```

On subsequent invocations, dismissed checks are skipped by the live environment check. To re-enable a dismissed check, the developer removes the entry from `dismissed_checks` (or deletes `machine-state.json`) and re-invokes `/octowiz`.

Dismissed checks are per-machine and never committed. This prevents a developer on a constrained machine (no LiteLLM, missing plugin) from being permanently blocked.

---

## Testing decisions

- Unit tests for live environment check logic (plugin dir scan, env var check, agent file detection)
- Unit tests for state file read/write and "first gap" resumption logic
- Unit tests for repo scan signal detection (package.json parsing, agent instructions file detection)
- Unit tests for agent instructions file precedence (AGENTS.md > CLAUDE.md > GEMINI.md > none)
- Integration test: simulate a full first-run sequence with a temp directory; assert machine-state.json created at runtime (not install), ONBOARDING.md created then deleted, live check passes at end
- No tests for the interactive guided flows — those are skill (Markdown) content, not Python code

---

## Modules likely to change

- `octowiz_cache.py` — add offline doctrine bundle fallback (for pre-LiteLLM use)
- `octowiz_cache_cli.py` — new subcommand for live environment check (plugin dir scan, env var read)
- `skills/octowiz-workflow/skill.md` — add live-check + auto-intercept preamble
- New: `skills/octowiz-setup/skill.md` (orchestrator)
- New: `skills/octowiz-setup-plugins/skill.md`
- New: `skills/octowiz-setup-cache/skill.md`
- New: `skills/octowiz-setup-repo/skill.md`
- New: `skills/octowiz-setup-verify/skill.md`
- `.claude-plugin/plugin.json` — register the four new skills

No changes to `pyproject.toml` (post_install hook removed). No new `octowiz_setup.py`.

---

## Out-of-scope decisions

- `CONTEXT.md` and `docs/adr/` scaffolding — these follow a lazy-creation model via `/grill-with-docs` and are never created by setup; octowiz only flags their absence in ONBOARDING.md
- Auto-creating agent instructions files — setup only reads and appends to existing files; creating `AGENTS.md`, `CLAUDE.md`, or `GEMINI.md` from scratch is a user action
- Uninstalling or upgrading plugins — octowiz detects and installs missing plugins; removal is detected by the live check on next invocation
- LiteLLM server provisioning — octowiz assumes LiteLLM is already running; it only guides env var configuration
- Windows support — path assumptions (`~/.claude/plugins/`, `~/.octowiz/`) are Unix-only for now

---

## Definition of done

- [ ] First `/octowiz` invocation in a new repo runs the live check, creates machine-state.json at runtime, intercepts, and runs the full guided setup
- [ ] Second invocation where live check passes goes straight to the A/B/C/D menu
- [ ] Setup interrupted mid-session resumes from the first failing live check on next invocation
- [ ] Cloning a repo with `setup-state.json` committed on a new machine runs only per-machine phases
- [ ] Plugin removed after setup is re-detected and re-triggered on next `/octowiz` invocation
- [ ] Repos using `AGENTS.md` are correctly detected; setup appends to AGENTS.md not CLAUDE.md
- [ ] `antfu_deferred` repos re-prompt for antfu setup when TS/Vue is detected in a later session
- [ ] All new Python code has unit tests; integration test covers the full first-run sequence
- [ ] `.claude/worktrees/` is in `.gitignore`
