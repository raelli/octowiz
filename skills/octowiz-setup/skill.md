# octowiz:setup

Setup orchestrator. Re-runs the live environment check, builds a gap list, and runs only the phases needed.

## When invoked

This skill is invoked by `octowiz:octowiz-workflow` when the live check reports gaps. Do not invoke this skill directly for any other purpose.

## Step 1: Run the live check

Run:
```bash
octowiz-cache check
```

Parse the JSON output. Store the `hard_gaps` and `advisory_gaps` arrays.

If exit code is 0 (status "clean"): delete ONBOARDING.md from the current directory if it exists, then proceed directly to the A/B/C/D workflow menu in `octowiz:octowiz-workflow`. Do not run any phase skills.

## Step 2: Create ONBOARDING.md if absent

If `.octowiz/setup-state.json` does not exist in the current directory, create it with:
```bash
octowiz-cache check  # already done above
```

Then create `ONBOARDING.md` in the current directory with this structure (fill in actual check statuses):

```markdown
# Octowiz Setup

## Environment (per-machine)
- [STATUS] superpowers plugin
- [STATUS] mattpo-skills plugin  
- [STATUS] antfu-skills plugin
- [STATUS] LiteLLM env vars (LITELLM_BASE_URL + API key)
- [STATUS] LiteLLM routing cache (verified within 24h)

## Project (per-repo)
- [STATUS] antfu skills setup (if TypeScript/Vue stack)
- [STATUS] Agent instructions file (AGENTS.md / CLAUDE.md / GEMINI.md)
- [STATUS] mattpo-skills section in agent file (## Agent skills)

## Next step
[What is about to run]
```

Use `[x]` for passing checks, `[ ]` for gaps, `[!]` for advisory items.

## Step 3: Run phase skills in order

Only run a phase if it has relevant gaps:

**setup-plugins** — run if any of these are in hard_gaps: `plugin_superpowers`, `plugin_mattpo-skills`, `plugin_antfu-skills`
Invoke: `octowiz:setup-plugins` passing the list of missing plugin IDs.

**setup-cache** — run if any of these are in hard_gaps: `litellm_env`, `litellm_cache`
Invoke: `octowiz:setup-cache`.

**setup-repo** — run if any of these are in hard_gaps or advisory_gaps: `antfu`, `agent_file`, `mattpo_skills_setup`
Invoke: `octowiz:setup-repo`.

**setup-verify** — always run after the above phases complete.
Invoke: `octowiz:setup-verify`.

## Step 4: After setup-verify

`octowiz:setup-verify` will either:
- Pass → proceed to the A/B/C/D workflow menu
- Fail → report remaining gaps and ask the developer how to proceed
