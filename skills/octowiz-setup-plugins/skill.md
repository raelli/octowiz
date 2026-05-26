# octowiz:setup-plugins

Guides the developer through installing missing octowiz dependency plugins.

## When invoked

Invoked by `octowiz:setup` when any required plugin is absent. You receive the list of missing plugin IDs in the gap list.

## For each missing plugin

Present the plugin name and explain what it does and why octowiz needs it. Then show the install command. After each install, verify that the plugin directory now exists.

### superpowers

**What it does:** Provides workflow discipline skills — TDD, brainstorming, code review, git worktrees, subagent-driven development. These are the core skills that power octowiz's A/B/C/D workflow options.

**Why required:** Without superpowers, `/octowiz:brainstorming`, `/octowiz:writing-plans`, and most workflow skills will not work.

**Install:**
```bash
claude plugins install superpowers
```

After install, verify:
```bash
ls ~/.claude/plugins/cache/*/superpowers/ 2>/dev/null | head -1
```
If this returns a path, the plugin is installed. If not, ask the developer to check their Claude Code plugin marketplace settings.

### mattpo-skills

**What it does:** Provides domain documentation and issue management skills — grill-with-docs, to-prd, to-issues, triage, diagnose, prototype. These power octowiz's workflow options A (fresh idea) and B (stress-test plan).

**Why required:** Without mattpo-skills, octowiz's option A flow (brainstorm → PRD → issues) and option B flow (grill-me → PRD) will not work.

**Note:** The install ID is `mattpo-skills`. Its slash-command namespace is `/mattpocock-skills:` — these are different. Always use `mattpo-skills` for installation.

**Install:**
```bash
claude plugins install mattpo-skills
```

After install, verify:
```bash
ls ~/.claude/plugins/cache/*/mattpo-skills/ 2>/dev/null | head -1
```

### antfu-skills

**What it does:** Provides TypeScript/Vue/Vite code quality skills — ESLint config, Vitest setup, Vite configuration, UnoCSS integration. Relevant for TypeScript and Vue projects.

**Why required:** Without antfu-skills, octowiz's repo setup phase cannot configure code quality tooling for TypeScript/Vue projects.

**Install:**
```bash
claude plugins install antfu-skills
```

After install, verify:
```bash
ls ~/.claude/plugins/cache/*/antfu-skills/ 2>/dev/null | head -1
```

## After all plugins are installed

Update `machine-state.json` plugins map: set each newly-installed plugin ID to `"verified"`. Use the Python module:

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

Report that all required plugins are now installed and return control to `octowiz:setup`.
