---
name: setup
description: >
  Setup orchestrator for the Octowiz Bridge. Re-runs the live environment check,
  builds a gap list, and runs only the phases needed: plugins, memory, repo, verify.
  Invoked automatically by octowiz:octowiz when hard gaps are detected.
---

# octowiz:setup

Setup orchestrator for the Octowiz Bridge. Runs only the phases with gaps.

## When invoked

Invoked by `octowiz:octowiz` when the live check reports gaps. Do not invoke directly.

## Pre-flight: run the live check

```bash
octowiz-cache check
```

Parse the JSON output. Store `hard_gaps` and `advisory_gaps`.

If `hard_gaps` is empty: delete `ONBOARDING.md` from the current directory if it exists, then return control to `octowiz:octowiz` to show the A/B/C/D menu.

## Create ONBOARDING.md

If `.octowiz/setup-state.json` does not exist in the current directory, create `ONBOARDING.md`:

```markdown
# Octowiz Setup

## Environment (per-machine)
- [STATUS] superpowers plugin
- [STATUS] mattpo-skills plugin
- [STATUS] antfu-skills plugin
- [STATUS] LiteLLM env vars (LITELLM_BASE_URL + API key)
- [STATUS] LiteLLM routing cache (verified within 24h)
- [STATUS] Project namespace seeded in LiteLLM Memory

## Project (per-repo)
- [STATUS] antfu skills setup (if TypeScript/Vue stack)
- [STATUS] Agent instructions file (AGENTS.md / CLAUDE.md / GEMINI.md)
- [STATUS] mattpo-skills section in agent file (## Agent skills)

## Next step
[What is about to run]
```

Use `[x]` for passing checks, `[ ]` for gaps, `[!]` for advisory items.

---

## Phase 1: Plugins

**Run if any of these are in `hard_gaps`:** `plugin_superpowers`, `plugin_mattpo-skills`, `plugin_antfu-skills`

For each missing plugin, explain what it does and why it is required, then show the install command. Verify after each install.

### superpowers

Provides workflow discipline skills — TDD, brainstorming, code review, git worktrees, subagent-driven development.

```bash
claude plugins install superpowers
```

Verify: `ls ~/.claude/plugins/cache/*/superpowers/ 2>/dev/null | head -1`

### mattpo-skills

Provides domain documentation and issue management skills — grill-with-docs, to-prd, to-issues, triage, diagnose, prototype.

Note: install ID is `mattpo-skills`; slash-command namespace is `/mattpocock-skills:` — these are different.

```bash
claude plugins install mattpo-skills
```

Verify: `ls ~/.claude/plugins/cache/*/mattpo-skills/ 2>/dev/null | head -1`

### antfu-skills

Provides TypeScript/Vue/Vite code quality skills — ESLint config, Vitest setup, Vite configuration, UnoCSS integration.

```bash
claude plugins install antfu-skills
```

Verify: `ls ~/.claude/plugins/cache/*/antfu-skills/ 2>/dev/null | head -1`

After all plugins are installed, update `machine-state.json`:

```bash
python3 -c "
import sys; sys.path.insert(0, '$(which octowiz-cache | xargs dirname 2>/dev/null || echo .)')
from octowiz_env import init_machine_state, save_machine_state, MACHINE_STATE_PATH
state = init_machine_state()
for pid in ['superpowers', 'mattpo-skills', 'antfu-skills']:
    state.plugins[pid] = 'verified'
save_machine_state(state)
print('machine-state.json updated')
"
```

---

## Phase 2: Memory

**Run if any of these are in `hard_gaps`:** `litellm_env`, `litellm_cache`
**Also run Step 2.4 alone** if hard_gaps has no Memory entries but `setup-state.json` has no `project_id` (i.e. this is the first `/octowiz` run in this repo on a machine already fully configured). Check with:

```bash
python3 -c "
from octowiz_env import load_repo_state
import pathlib
s = load_repo_state(pathlib.Path('.'))
print('seeded' if s and s.project_id else 'not-seeded')
"
```

If the output is `not-seeded`, skip Steps 2.1–2.3 and run only Step 2.4.

This phase covers all LiteLLM operations in sequence: env vars → role cache → project namespace seed.

### Step 2.1: LiteLLM env vars

If `litellm_env` is in `hard_gaps`, check current state:

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

Ask them to reload Claude Code so the env vars take effect, then verify before continuing.

### Step 2.2: Build role bundles

```bash
octowiz-cache build --all --namespace "${OCTOWIZ_NAMESPACE:-allspark}"
```

If this fails, check: Is LiteLLM running? `curl -s "${LITELLM_BASE_URL}/health"`

### Step 2.3: Verify routing bundle

```bash
octowiz-cache get --role routing --namespace "${OCTOWIZ_NAMESPACE:-allspark}" > /dev/null
```

If exit code is 0, record `routing_verified_at`:

```bash
python3 -c "
from octowiz_env import init_machine_state, save_machine_state, MACHINE_STATE_PATH, _now_iso
state = init_machine_state()
state.litellm['routing_verified_at'] = _now_iso()
save_machine_state(state)
print('routing_verified_at recorded')
"
```

### Step 2.4: Seed project namespace

Seed the project namespace into LiteLLM Memory (idempotent — safe to re-run):

```bash
octowiz-cache seed
```

This writes `project:{id}:octowiz:config` and `project:{id}:octowiz:rules` if they do not already exist. The `project_id` is derived from the git remote URL (UUID fallback) and stored in `.octowiz/setup-state.json` for stability across runs.

If this fails with a connection error, LiteLLM is not reachable. Revisit Steps 2.1 and 2.2 before retrying.

---

## Phase 3: Repo

**Run if any of these are in `hard_gaps` or `advisory_gaps`:** `antfu`, `agent_file`, `mattpo_skills_setup`

### Step 3.1: Scan the repo

```bash
octowiz-cache check
```

Also detect manually:
- Agent file: check for `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` (in that priority order)
- Stack: check `package.json` for vue/vite/react/typescript; check for `pyproject.toml`
- Check for `CONTEXT.md` and `docs/adr/`

Update the "Project (per-repo)" section of `ONBOARDING.md` with findings.

### Step 3.2: mattpo-skills setup

If `mattpo_skills_setup` is in advisory gaps and the agent file exists but has no `## Agent skills` section, invoke:

`/mattpocock-skills:setup-matt-pocock-skills`

If no agent file exists: note in ONBOARDING.md that this step is deferred. Do not create the file.

Update `setup-state.json`:

```bash
python3 -c "
from octowiz_env import init_repo_state, save_repo_state
import pathlib
state = init_repo_state(pathlib.Path('.'))
state.mattpocock_setup = True
save_repo_state(state, pathlib.Path('.'))
"
```

### Step 3.3: Antfu setup

**ts_vue or polyglot stack only.**

If agent file exists, detect which antfu sub-skills are relevant from `package.json` and append to `## Agent skills`:

```
- /antfu-skills:vue    — Vue 3 composition API patterns
- /antfu-skills:vite   — Vite configuration and build optimization
- /antfu-skills:vitest — Vitest setup and patterns
- /antfu-skills:pnpm   — pnpm workspace commands
- /antfu-skills:unocss — UnoCSS integration
```

Update `setup-state.json`:

```bash
python3 -c "
from octowiz_env import init_repo_state, save_repo_state
import pathlib
state = init_repo_state(pathlib.Path('.'))
state.antfu_setup = True
state.antfu_relevant = True
save_repo_state(state, pathlib.Path('.'))
"
```

If no agent file exists or stack is not ts_vue/polyglot: note in ONBOARDING.md, set `antfu_relevant = False` if applicable.

### Step 3.4: Flag lazy-creation items

In ONBOARDING.md, note any items that follow lazy-creation:

- `CONTEXT.md` absent: `[!] CONTEXT.md — not present; will be created lazily by /grill-with-docs`
- `docs/adr/` absent: `[!] docs/adr/ — not present; will be created lazily by /grill-with-docs`

Do NOT create these files now.

---

## Phase 4: Verify

Always run last, after all other phases complete.

### Step 4.1: Re-run the live check

```bash
octowiz-cache check
```

### Step 4.2: If hard_gaps is empty — setup complete

1. Delete `ONBOARDING.md` from the current directory:
   ```bash
   rm -f ONBOARDING.md
   ```
2. Report: "Setup complete. All required plugins are installed, LiteLLM Memory is configured and seeded, repo setup is done. Proceeding to the workflow menu."
3. Return control to `octowiz:octowiz` to show the A/B/C/D menu.

### Step 4.3: If hard_gaps remain — offer escape hatch

Report remaining gaps. For each:

| Gap ID | Message |
|---|---|
| `plugin_superpowers` | superpowers plugin not found. Run: `claude plugins install superpowers` |
| `plugin_mattpo-skills` | mattpo-skills plugin not found. Run: `claude plugins install mattpo-skills` |
| `plugin_antfu-skills` | antfu-skills plugin not found. Run: `claude plugins install antfu-skills` |
| `litellm_env` | LITELLM_BASE_URL or API key not set. Add to `~/.claude/settings.json` under `"env"`. |
| `litellm_cache` | LiteLLM routing bundle not verified. Run: `octowiz-cache build --all` |
| `antfu` | Antfu setup needed for this TypeScript/Vue project. Re-run Phase 3. |

Offer the escape hatch:

> "Setup is incomplete. You can skip this and proceed anyway — but some features may not work.
>
> To skip a specific check: respond with the check ID (e.g., `litellm_env`).
> To skip all and proceed: respond `skip all`.
> To fix: respond `fix`."

To dismiss a check:

```bash
python3 -c "
from octowiz_env import dismiss_check, MACHINE_STATE_PATH
import pathlib
dismiss_check('<check_id>', pathlib.Path('.'), MACHINE_STATE_PATH)
print('check dismissed')
"
```

Advisory gaps (`agent_file`, `mattpo_skills_setup`) are noted but do not block Phase 4 from passing.
