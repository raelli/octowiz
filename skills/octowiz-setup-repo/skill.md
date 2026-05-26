# octowiz:setup-repo

Scans the repository and runs per-repo setup steps.

## When invoked

Invoked by `octowiz:setup` when any of `antfu`, `agent_file`, or `mattpo_skills_setup` appear in the gap list.

## Step 1: Scan the repo

Run the live check to get current repo state:
```bash
octowiz-cache check
```

Store the result. Also detect the stack and agent file by inspecting the working directory:
- Check for `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` (in that priority order)
- Check `package.json` for vue/vite/react/typescript deps
- Check for `pyproject.toml` or `setup.py`
- Check for `CONTEXT.md` and `docs/adr/`

## Step 2: Update ONBOARDING.md with repo scan results

Update the "Project (per-repo)" section of `ONBOARDING.md` with findings:
- Agent instructions file: note which file was found (or flag if absent)
- mattpo-skills setup: note if `## Agent skills` section is present in the agent file
- CONTEXT.md: note if present or flag as lazy-creation item (`[!]`)
- docs/adr/: note if present or flag as lazy-creation item (`[!]`)
- antfu: note stack detection result and planned action

## Step 3: mattpo-skills setup (if gap: mattpo_skills_setup)

If the agent instructions file exists but has no `## Agent skills` section, invoke:
`/mattpocock-skills:setup-matt-pocock-skills`

This appends the required octowiz skill entries to the detected agent file.

If no agent instructions file exists: note in ONBOARDING.md that this step is deferred until the developer creates one. Do not create the file.

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

## Step 4: Antfu setup (if gap: antfu)

Check the detected stack:

**ts_vue or polyglot stack:**
- If agent file exists: detect which antfu sub-skills are relevant from `package.json`:
  - `vue` present → append `/antfu-skills:vue` skill entry
  - `vite` present → append `/antfu-skills:vite` skill entry
  - `vitest` present → append `/antfu-skills:vitest` skill entry
  - Check if pnpm is used: `cat package.json | grep -q pnpm` → append `/antfu-skills:pnpm`
  - `unocss` present in deps → append `/antfu-skills:unocss` skill entry

  Append to `## Agent skills` section of the detected agent file. Format:
  ```
  - /antfu-skills:vue — Vue 3 composition API patterns and best practices
  - /antfu-skills:vite — Vite configuration and build optimization
  ```

  Then update setup-state.json:
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

- If no agent file exists: note in ONBOARDING.md that antfu setup is deferred. Update:
  ```bash
  python3 -c "
  from octowiz_env import init_repo_state, save_repo_state
  import pathlib
  state = init_repo_state(pathlib.Path('.'))
  state.antfu_deferred = True
  state.antfu_relevant = True
  save_repo_state(state, pathlib.Path('.'))
  "
  ```

**python, react, generic_js, or empty stack:**
- Set `antfu_relevant: false` in setup-state.json:
  ```bash
  python3 -c "
  from octowiz_env import init_repo_state, save_repo_state
  import pathlib
  state = init_repo_state(pathlib.Path('.'))
  state.antfu_relevant = False
  save_repo_state(state, pathlib.Path('.'))
  "
  ```
- No antfu setup needed; note this in ONBOARDING.md.

## Step 5: Flag lazy-creation items

In ONBOARDING.md, add notes for any lazy-creation items that were NOT found:
- CONTEXT.md absent: `[!] CONTEXT.md — not present; will be created lazily by /grill-with-docs`
- docs/adr/ absent: `[!] docs/adr/ — not present; will be created lazily by /grill-with-docs`

Do NOT create these files. They follow a lazy-creation model via `/grill-with-docs`.

## After completing

Return control to `octowiz:setup`.
