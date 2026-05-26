---
name: setup-verify
description: >
  Final verification gate for octowiz setup. Re-runs the live check and confirms all
  hard gates pass. On success deletes ONBOARDING.md and returns to the octowiz workflow
  menu. Provides per-check fix instructions and dismiss escape hatch if gaps remain.
---

# octowiz:setup-verify

Final verification gate. Re-runs the live check and confirms all hard gates pass.

## When invoked

Always invoked last by `octowiz:setup`, after all other phases complete.

## Step 1: Re-run the live check

```bash
octowiz-cache check
```

Parse the JSON output.

## Step 2: If hard_gaps is empty — setup complete

All hard gates pass. Proceed:

1. Delete `ONBOARDING.md` from the current directory if it exists:
   ```bash
   rm -f ONBOARDING.md
   ```

2. Report to the developer:
   > "Setup complete. All required plugins are installed, LiteLLM is configured, and repo setup is done. Proceeding to the workflow menu."

3. Return control to `octowiz:octowiz` to show the A/B/C/D menu.

## Step 3: If hard_gaps is non-empty — gaps remain

Report the remaining gaps clearly. For each gap, explain what is missing and what to do:

| Gap ID | Message |
|---|---|
| `plugin_superpowers` | superpowers plugin not found. Run: `claude plugins install superpowers` |
| `plugin_mattpo-skills` | mattpo-skills plugin not found. Run: `claude plugins install mattpo-skills` |
| `plugin_antfu-skills` | antfu-skills plugin not found. Run: `claude plugins install antfu-skills` |
| `litellm_env` | LITELLM_BASE_URL or API key not set. Add to ~/.claude/settings.json under "env". |
| `litellm_cache` | LiteLLM routing bundle not verified. Run: `octowiz-cache build --all --namespace <ns>` |
| `antfu` | Antfu setup needed for this TypeScript/Vue project. Re-invoke `/octowiz:setup-repo`. |

After listing remaining gaps, offer the escape hatch:

> "Setup is incomplete. You can skip this and proceed to the workflow anyway — but some features may not work correctly.
>
> To skip a specific check: respond with the check ID (e.g., `litellm_env`) and I will dismiss it for this repo.
> To skip all remaining checks and proceed: respond `skip all`.
> To try fixing the gaps: respond `fix`."

If the developer responds with a check ID: call `dismiss_check` for that check and re-run the live check. If they respond `skip all`: dismiss all remaining hard_gaps and proceed. If they respond `fix`: re-invoke the appropriate phase skill.

## Advisory gaps

Advisory gaps (`agent_file`, `mattpo_skills_setup`) are noted to the developer but do not block setup-verify from passing. Mention them once, then proceed.

## Dismissing a check

To dismiss a check from within a skill, run:
```bash
python3 -c "
from octowiz_env import dismiss_check, MACHINE_STATE_PATH
import pathlib
dismiss_check('<check_id>', pathlib.Path('.'), MACHINE_STATE_PATH)
print('check dismissed')
"
```
