---
name: octowiz
description: >
  Octowiz AI coding workflow coordinator. Reads IntegraHub memory doctrine at runtime,
  detects where you are in the development lifecycle, and routes to the right skill
  combination from superpowers + mattpocock-skills.
  Use this skill at the START of any development work — whether you have a fresh idea,
  an existing plan to stress-test, code ready to implement, or work ready for review.
  Invoke when the user types /octowiz, starts a new feature, asks how to begin a
  coding task, or says something like "let's build X", "I want to work on Y",
  "I have a plan", or "can you review my code".
---

# Octowiz Workflow Coordinator

You are the entry point for the AI-assisted coding workflow. Read the project, fetch
operating doctrine from IntegraHub memory, and route to the right installed skills.

## Pre-flight: Auto-intercept check

**Run this before anything else — before reading the project, before loading doctrine.**

### 1. Run the live environment check

```bash
octowiz-cache check
```

Parse the JSON output (`{"status": "...", "hard_gaps": [...], "advisory_gaps": [...]}`).

### 2. Bootstrap machine state if absent

If `~/.octowiz/machine-state.json` does not exist, create it now:

```bash
python3 -c "
from octowiz_env import init_machine_state
init_machine_state()
print('machine-state.json created')
"
```

### 3. Bootstrap repo state if absent (Phase 1 init)

If `.octowiz/setup-state.json` does not exist in the current directory, this is the first time octowiz has run in this repo. Create it and write `ONBOARDING.md`:

```bash
python3 -c "
from octowiz_env import init_repo_state
import pathlib
init_repo_state(pathlib.Path('.'))
print('setup-state.json created')
"
```

Then create `ONBOARDING.md` in the current directory with a skeleton checklist (actual statuses will be filled in by `octowiz:setup`):

```markdown
# Octowiz Setup

## Environment (per-machine)
- [ ] superpowers plugin
- [ ] mattpo-skills plugin
- [ ] antfu-skills plugin
- [ ] LiteLLM env vars (LITELLM_BASE_URL + API key)
- [ ] LiteLLM routing cache

## Project (per-repo)
- [ ] antfu skills setup (if TypeScript/Vue stack)
- [ ] Agent instructions file
- [ ] mattpo-skills section (## Agent skills)

## Next step
Running octowiz:setup...
```

### 4. Intercept decision

**If `hard_gaps` is non-empty:** Invoke `octowiz:setup`. Do NOT proceed to the steps below. `octowiz:setup` will run the required phases and, when complete, return to this skill to show the A/B/C/D menu.

**If `hard_gaps` is empty and `ONBOARDING.md` exists (stale):** The environment is now clean. Delete ONBOARDING.md:
```bash
rm -f ONBOARDING.md
```
Then proceed to Step 1 below.

**If `hard_gaps` is empty and `ONBOARDING.md` is absent:** Proceed to Step 1 below.

---

## Step 1 — Read project setup

Run each of the following and note what you find:

```bash
cat CLAUDE.md 2>/dev/null || echo "No CLAUDE.md"
head -50 README.md 2>/dev/null || echo "No README.md"
git status
git log --oneline -5
```

If an issue tracker is configured in CLAUDE.md, list open issues. Note whether:
- A feature branch is active (branch name ≠ main/master)
- Open issues exist
- There are uncommitted changes or a plan file in docs/

## Step 2 — Load routing doctrine

Run:

```bash
octowiz-cache get --role routing --namespace "${OCTOWIZ_NAMESPACE:-allspark}"
```

If `octowiz-cache` is not installed or exits non-zero, fall back to:

```bash
curl -s "$LITELLM_BASE_URL/v1/memory/team%3A${OCTOWIZ_NAMESPACE:-allspark}%3Aconfig%3Aretrieval-contract" \
  -H "Authorization: Bearer ${LITELLM_ADMIN_API_KEY:-$LITELLM_API_KEY}"
```

If both fail, or if `LITELLM_BASE_URL` and API key env vars are not set, tell the developer:

> "Set LITELLM_BASE_URL and LITELLM_ADMIN_API_KEY (or LITELLM_API_KEY) in
> ~/.claude/settings.json to enable memory-backed doctrine. See the octowiz README
> for setup instructions. Continuing with built-in workflow."

Then continue using the built-in routing below — do not stop.

After the user chooses a workflow option, load the corresponding role bundle before
appending fresh project state:

- Options A or B → `octowiz-cache get --role planner --namespace "${OCTOWIZ_NAMESPACE:-allspark}"`
- Option C → `octowiz-cache get --role implementer --namespace "${OCTOWIZ_NAMESPACE:-allspark}"`
- Option D → `octowiz-cache get --role reviewer --namespace "${OCTOWIZ_NAMESPACE:-allspark}"`

Prepend the bundle content to the context before fresh git status, open issues, and user request.
Do not suppress stderr from `octowiz-cache` — let warnings surface to the developer.

## Step 3 — Check for setup-matt-pocock-skills

Look for `## Agent skills` in CLAUDE.md. If it is missing, say:

> "Run /mattpocock-skills:setup-matt-pocock-skills first to configure your issue
> tracker and domain docs. It's required for to-prd, to-issues, triage, diagnose,
> and tdd to work correctly."

Ask whether they want to run it now before continuing.

## Step 4 — Present starting-point options

Use the project state from Step 1 to suggest a smart default:
- Open issues + feature branch active → suggest C
- No issues, no prior plan, fresh repo → suggest A
- Developer said "I have a plan" in the invocation → suggest B
- Recent commits, no open PR → suggest D

Always show all four options regardless of the suggestion:

```
Where are you starting from?

A) Fresh idea — no plan yet
   brainstorming → grill-with-docs (if CONTEXT.md/ADRs exist) → to-prd → writing-plans → to-issues → triage

B) I have a plan to stress-test
   grill-me → to-prd → writing-plans → to-issues → triage

C) Plan exists — ready to implement
   using-git-worktrees → test-driven-development + tdd → executing-plans

D) Code done — need review
   zoom-out → requesting-code-review → receiving-code-review →
   verification-before-completion → finishing-a-development-branch → handoff
```

Wait for the user to choose before proceeding.

---

## Phase routing

### Option A — Fresh idea

Invoke in sequence, waiting for each to complete before moving to the next.

1. `/superpowers:brainstorming` — explore the idea space, surface hidden requirements,
   produce a written spec. Ends by invoking writing-plans.
2. `/mattpocock-skills:grill-with-docs` — **only** if the codebase has CONTEXT.md or
   docs/adr/ entries. Challenges the plan against the existing domain model and
   sharpens terminology.
3. `/mattpocock-skills:to-prd` — synthesise the brainstorming output into a formal PRD
   on the issue tracker. Pure synthesis — does not interview.
4. `/superpowers:writing-plans` — may already have run at the end of brainstorming;
   run standalone if not.
5. `/mattpocock-skills:to-issues` — break the PRD into independently-grabbable vertical
   slice issues using tracer-bullet slicing.
6. `/mattpocock-skills:triage` — classify issues as HITL or AFK, write agent briefs for
   AFK tasks.

### Option B — Stress-test a plan

For when the developer arrives with a plan already formed and wants rigorous challenge
before committing to implementation.

1. `/mattpocock-skills:grill-me` — relentless one-question-at-a-time interview until
   every branch of the decision tree is resolved.
2. `/mattpocock-skills:to-prd` — synthesise the grilled plan into a formal PRD.
3. `/superpowers:writing-plans` — implementation task breakdown.
4. `/mattpocock-skills:to-issues` — vertical slice issues on the tracker.
5. `/mattpocock-skills:triage` — HITL/AFK classification and agent briefs.

### Option C — Ready to implement

1. `/superpowers:using-git-worktrees` — isolated workspace before touching any code.
2. `/superpowers:test-driven-development` — TDD discipline and structure.
   Also invoke `/mattpocock-skills:tdd` for the technical depth it adds: deep modules,
   mocking only at system boundaries, interface design for testability.
   These two skills complement each other — use both, not one instead of the other.
3. `/superpowers:executing-plans` — execute the written plan with review checkpoints.
   Use `/superpowers:subagent-driven-development` if you want fresh subagents per task.

Available on demand during implementation:
- `/mattpocock-skills:prototype` — throwaway exploration for logic or UI questions
  before committing to an approach.
- `/mattpocock-skills:diagnose` — disciplined debugging: reproduce → minimise →
  hypothesise → instrument → fix → regression-test.

### Option D — Need review

1. `/mattpocock-skills:zoom-out` — step back, understand broader context before
   reviewing. Prevents narrow-context review mistakes.
2. `/mattpocock-skills:improve-codebase-architecture` — optional; surface when
   architecture concerns emerge during review.
3. `/superpowers:requesting-code-review` — formal review request with full context
   package.
4. `/superpowers:receiving-code-review` — process review feedback systematically.
5. `/superpowers:verification-before-completion` — evidence-before-assertions gate.
   Must pass before claiming work done or opening a PR.
6. `/superpowers:finishing-a-development-branch` — structured merge/PR/cleanup
   decision.
7. `/mattpocock-skills:handoff` — compact context transfer to next session or agent.

---

## Doctrine reference

Key principles from the operating memories (used when memory fetch fails or as
a reminder):

- **Context smart zone** — keep context windows small; split large work into focused
  tasks. A large context window is a liability, not an asset.
- **HITL vs AFK** — alignment and product decisions stay human-in-the-loop. Only
  well-scoped, testable, dependency-resolved tasks go AFK.
- **Tracer bullets** — prefer thin vertical slices over horizontal layers. The first
  slice should cross schema, service, and UI together.
- **TDD** — write the failing test before the implementation. Always.
- **Fresh context review** — never review in the same context window used for
  implementation. Open a new window, re-read the spec cold.
- **Deep modules** — design interfaces that are narrow on the outside and rich on the
  inside. If the implementation bleeds into the call site, the boundary is wrong.
