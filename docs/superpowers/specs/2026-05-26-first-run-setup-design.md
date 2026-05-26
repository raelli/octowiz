# First-Run Setup & Onboarding

**Date:** 2026-05-26
**Status:** Draft

---

## Problem statement

When a developer installs octowiz and invokes `/octowiz` for the first time, none of the dependent plugins (superpowers, mattpocock, antfu) are guaranteed to be installed, LiteLLM is unlikely to be configured, and the repo has no project-level scaffolding (CONTEXT.md, ADRs, CLAUDE.md agent skills section). The workflow skill silently proceeds as if everything is in place, producing confusing failures downstream.

There is also no mechanism to avoid re-running setup on subsequent invocations once it has been completed, or to resume gracefully if setup is interrupted mid-session.

---

## Proposed solution

A three-phase setup system:

- **Phase 0 (install-time):** A `post_install` script runs automatically when `pip install octowiz` completes. It does silent environment detection — no user interaction required.
- **Phase 1 (per-repo init):** The first time `octowiz-workflow` runs in a repo that has no `.octowiz/setup-state.json`, it creates the state file and `ONBOARDING.md`.
- **Phase 2 (interactive first-run):** `octowiz-workflow` auto-intercepts before presenting the A/B/C/D menu and invokes `octowiz:setup`, which delegates to four focused phase skills. Only incomplete items run.

---

## User stories

- As a developer who just installed octowiz, I want to be guided step-by-step through plugin installation and LiteLLM setup, with each step explained before it runs.
- As a developer working in a new repo, I want octowiz to scan the project and tell me exactly what it will set up and why, before doing anything.
- As a developer re-invoking `/octowiz` after setup is complete, I want no setup intercept — just the normal A/B/C/D workflow menu.
- As a developer who was interrupted mid-setup, I want `/octowiz` to resume from where it left off.
- As a developer on a second machine cloning a repo with `.octowiz/setup-state.json` committed, I want octowiz to run only the per-machine steps (plugins, cache), skipping the repo-level steps already marked done.

---

## Implementation decisions

### State files

Two persistent state files, one per scope:

**`~/.octowiz/machine-state.json`** — per-developer, never committed.
```json
{
  "installed_at": "2026-05-26T10:00:00Z",
  "plugins": {
    "superpowers": true,
    "mattpocock": false,
    "antfu": false
  },
  "litellm": {
    "base_url_set": false,
    "api_key_set": false,
    "cache_seeded": false
  }
}
```

**`.octowiz/setup-state.json`** — per-repo, committed.
```json
{
  "created_at": "2026-05-26T10:00:00Z",
  "mattpocock_setup": false,
  "context_md": false,
  "adr_scaffold": false,
  "antfu_relevant": null,
  "antfu_setup": false,
  "antfu_deferred": false
}
```

### ONBOARDING.md lifecycle

Created at Phase 1 init. Updated after each completed phase step. Deleted by `octowiz:setup-verify` when all items in both state files are complete. While active, it is a human-readable progress checklist and an agent resumption anchor.

Example structure:
```markdown
# Octowiz Setup

## Environment (per-machine)
- [x] Plugins installed — superpowers, mattpocock, antfu
- [ ] LiteLLM cache configured

## Project (per-repo)
- [ ] mattpocock skills setup
- [ ] CONTEXT.md scaffolded
- [ ] docs/adr/ scaffolded
- [~] antfu skills — Vue + TypeScript detected, setup pending

## Next step
Running octowiz:setup-cache...
```

Resumption: if `/octowiz` is re-invoked and ONBOARDING.md is present, the orchestrator reads both state files, finds the first incomplete item, and picks up there.

Stale file rule: if ONBOARDING.md is present but both state files are fully complete, delete ONBOARDING.md and proceed normally.

### Auto-intercept in octowiz-workflow

At the top of the skill, before Step 1 (Read project setup), check:

1. Does `~/.octowiz/machine-state.json` exist with all machine steps complete?
2. Does `.octowiz/setup-state.json` exist with all project steps complete (or marked not applicable)?

If either check fails → invoke `octowiz:setup` instead of the A/B/C/D menu.

### Phase skills

**`octowiz:setup`** (orchestrator)
- Reads both state files
- Calls phases in order: `setup-plugins` → `setup-cache` → `setup-repo` → `setup-verify`
- Skips any phase whose state entries are all complete

**`octowiz:setup-plugins`** (per-machine)
- For each plugin not yet in machine-state.json: explains what it does and why octowiz needs it, gives the exact `claude plugins install <url>` command, waits for user confirmation, then verifies presence
- Plugins: superpowers, mattpocock, antfu (all installed upfront — avoids a second pass after repo scan)
- Updates machine-state.json on completion

**`octowiz:setup-cache`** (per-machine)
- Checks `LITELLM_BASE_URL` and `LITELLM_ADMIN_API_KEY` env vars
- If missing, guides the user to add them to `~/.claude/settings.json`
- Seeds all four role bundles: routing, planner, implementer, reviewer
- Verifies end-to-end with `octowiz-cache get --role routing`
- Updates machine-state.json on completion

**`octowiz:setup-repo`** (per-repo)
- Scans the repo using the signal table below
- Writes the tailored checklist into ONBOARDING.md before running any steps
- Invokes `mattpocock:setup-matt-pocock-skills` if CLAUDE.md missing `## Agent skills`
- Scaffolds CONTEXT.md if absent
- Scaffolds `docs/adr/` if absent
- Applies the antfu decision tree
- Updates setup-state.json on completion

**`octowiz:setup-verify`** (final gate)
- Smoke-tests: `octowiz-cache get --role routing`, confirms plugins loadable, checks CONTEXT.md and CLAUDE.md in place
- Updates ONBOARDING.md to all-complete, then deletes it
- Marks both state files fully complete

### Repo scan signals

| Signal | Conclusion |
|---|---|
| No files except hidden | Empty project |
| `package.json` with `vue`/`vite`/`typescript` | TypeScript/Vue — antfu highly relevant |
| `package.json` with `react` | React — antfu somewhat relevant |
| `package.json` only (no TS/Vue) | Generic JS — antfu low relevance |
| `pyproject.toml` / `setup.py` only | Python — antfu not applicable |
| Both `package.json` + `pyproject.toml` | Polyglot — antfu relevant for frontend layer |
| `CONTEXT.md` present | Skip CONTEXT.md scaffolding |
| `docs/adr/` present | Skip ADR scaffolding |
| `CLAUDE.md` with `## Agent skills` | Skip mattpocock setup |
| `git remote -v` has github.com | `gh` CLI available for issue tracker |

### Antfu decision tree

| Detected | Action |
|---|---|
| TypeScript / Vue / Vite | Run antfu setup |
| Python / Go / Rust only | Set `antfu_relevant: false`, skip |
| Empty project | Set `antfu_deferred: true`; prompt on next session when stack detected |
| Polyglot | Treat as TypeScript/Vue |

Antfu setup means: detect relevant sub-skills (vue, vite, vitest, pnpm, unocss) from `package.json`, add them to the `## Agent skills` section in CLAUDE.md with a one-line description each. No config files are modified.

### Re-run safety

| Condition | Behaviour |
|---|---|
| Both state files complete, ONBOARDING.md absent | Normal workflow, no intercept |
| Either state file has incomplete items | Auto-intercept, resume from first incomplete item |
| ONBOARDING.md present but state files complete | Stale file — delete it, proceed normally |
| Plugin missing from machine-state (e.g. uninstalled) | Re-run setup-plugins for that plugin only |
| `mattpocock_setup: false` | Re-run mattpocock setup even if rest of project setup is done |
| `antfu_deferred: true` and TS/Vue now detected | Prompt once for antfu setup, mark done afterwards |
| New machine, cloned repo with setup-state.json committed | Per-machine state absent → run plugins + cache only |

### Phase 0: install-time detection

Implemented as a `post_install` script in `pyproject.toml`. Runs silently on `pip install octowiz`:

- Creates `~/.octowiz/` directory
- Writes `machine-state.json` skeleton with `installed_at` timestamp
- Scans `~/.claude/plugins/` to detect already-installed plugins
- Checks `LITELLM_BASE_URL` and API key env vars
- Bundles offline doctrine into the package as a fallback for `octowiz-cache get` before LiteLLM is configured

---

## Testing decisions

- Unit tests for Phase 0 detection logic (plugin scan, env var check) using mocked filesystem and env
- Unit tests for state file read/write and the "first incomplete item" resumption logic
- Unit tests for repo scan signal detection (package.json parsing, CLAUDE.md section check)
- Integration test: simulate a full first-run sequence with a temp directory, assert state files are written correctly and ONBOARDING.md is created then deleted
- No tests for the interactive guided flows — those are skill (Markdown) content, not Python code

---

## Modules likely to change

- `pyproject.toml` — add post_install hook entry point
- `octowiz_cache.py` — add offline doctrine bundle fallback
- `octowiz_cache_cli.py` — may need new subcommands for state file reads
- `skills/octowiz-workflow/skill.md` — add auto-intercept preamble
- New: `skills/octowiz-setup/skill.md` (orchestrator)
- New: `skills/octowiz-setup-plugins/skill.md`
- New: `skills/octowiz-setup-cache/skill.md`
- New: `skills/octowiz-setup-repo/skill.md`
- New: `skills/octowiz-setup-verify/skill.md`
- New: `octowiz_setup.py` — Phase 0 post_install script
- `.claude-plugin/plugin.json` — register the four new skills

---

## Out-of-scope decisions

- Uninstalling or upgrading plugins — octowiz detects missing plugins but does not manage upgrades
- LiteLLM server provisioning — octowiz assumes LiteLLM is already running; it only guides env var configuration
- Windows support — Phase 0 path assumptions are Unix-only for now
- Auto-detecting `.env` files or shell rc files for env vars — only `~/.claude/settings.json` is targeted

---

## Definition of done

- [ ] `pip install octowiz` runs Phase 0 silently and writes `~/.octowiz/machine-state.json`
- [ ] First `/octowiz` invocation in a new repo intercepts and runs the full guided setup
- [ ] Second invocation in the same repo goes straight to the A/B/C/D menu
- [ ] Setup interrupted mid-session resumes correctly on next invocation
- [ ] Cloning a repo with `.octowiz/setup-state.json` on a new machine runs only per-machine phases
- [ ] `antfu_deferred` repos re-prompt for antfu setup when TS/Vue is detected in a later session
- [ ] All new Python code has unit tests; integration test covers the full first-run sequence
- [ ] `.claude/worktrees/` is in `.gitignore`
