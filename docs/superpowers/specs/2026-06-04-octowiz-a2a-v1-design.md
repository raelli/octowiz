# Octowiz A2A v1 — Design Spec

**Date:** 2026-06-04
**Repos:** raelli/aelli (primary), raelli/octowiz (stability fix)
**Milestone:** Stable v1 — context packager + stability

---

## Problem statement

AELLI has four live skills but no dedicated endpoint for the Octowiz engineering workflow.
The octowiz Bridge (Claude Code plugin) fetches doctrine from LiteLLM Memory via `octowiz-cache`
but cannot ask AELLI for a context package tailored to the current task or consuming model.
ÆLLI has no structured entry point to dispatch coding work into the Bridge's workflow.

Additionally, both repos have open stability gaps that, left unresolved, undermine the value
of any new capability built on top of them.

---

## Proposed solution

Ship a stable v1 milestone consisting of:

1. **Octowiz A2A skill** — new `src/skills/octowiz/` in AELLI, registered at `/a2a/octowiz`.
   Implements `octowiz.plan` and `octowiz.review`. Composes model-tier-aware context bundles
   from existing infrastructure (MemPalace playbook, session snapshot, doctrine, Qdrant).

2. **Gap 2 fix** — merge `fix/gap2-retire-subscribe` in octowiz. Stops the daemon's silent
   reconnect loop to a non-existent AELLI endpoint.

3. **Self-improve guard** — add a size/breadth threshold to the hourly improvement cron in AELLI.
   Changes exceeding the threshold are flagged for human review instead of auto-committed.

---

## Architecture

```
ÆLLI or octowiz Bridge
        │
        │  POST /a2a/octowiz
        │  { type: "octowiz.plan" | "octowiz.review",
        │    scope, routerTier, task }
        ▼
src/skills/octowiz/index.js   (new)
        │
        ├── model-tier.js     routerTier enum → COMPACT | STANDARD | FULL
        ├── bundle-builder.js composes the context package at the resolved tier
        │         │
        │         ├── PgStore            agent:aelli:playbook:<scope>
        │         ├── session-lifecycle  branch, recent_files, active_task, events
        │         ├── memory client      planner / reviewer doctrine bundle (fallback)
        │         └── engineering skill  Qdrant query (FULL tier only)
        │
        └── operations.js     plan + review handlers
```

Call direction: both top-down (ÆLLI dispatches) and bottom-up (Bridge requests context).
The skill holds no exclusive state — it reads from infrastructure other skills already write.

---

## Components

### `src/skills/octowiz/card.json`

```json
{
  "name": "Octowiz Coding Agent",
  "id": "octowiz",
  "version": "1.0.0",
  "protocolVersion": "0.3.0",
  "description": "Model-tier-aware context packager for octowiz.plan and octowiz.review",
  "url": "http://aelli:3456/a2a/octowiz",
  "capabilities": { "streaming": false },
  "skills": [
    {
      "id": "octowiz:plan",
      "name": "Plan",
      "description": "Compose a planning context bundle scaled to the consuming model tier",
      "tags": ["planning", "context", "bundle"]
    },
    {
      "id": "octowiz:review",
      "name": "Review",
      "description": "Compose a review context bundle scaled to the consuming model tier",
      "tags": ["review", "context", "bundle"]
    }
  ]
}
```

### `src/skills/octowiz/model-tier.js`

Maps the caller's `routerTier` field to a bundle tier. Uses the router's existing enum
so no string-scanning on model names is needed:

| routerTier (from classify.js) | Bundle tier |
|---|---|
| `SIMPLE` | `COMPACT` |
| `MEDIUM` | `COMPACT` |
| `COMPLEX` | `COMPACT` |
| `REASONING` | `STANDARD` |
| `NORMAL` / `HIGH` / `XHIGH` / `MAX` (coding tiers) | `FULL` |
| not provided / unknown | `STANDARD` |

Callers who already know their desired tier can pass `bundleTier: "COMPACT"` directly to
skip inference. `bundleTier` takes precedence over `routerTier` when both are present.

### `src/skills/octowiz/bundle-builder.js`

Assembles the context package. Each layer degrades gracefully — an absent playbook, empty
Qdrant results, or missing session state all produce valid (possibly empty) fields rather
than errors.

**COMPACT** — target: 27B models (Gemma 27B, Nemotron SIMPLE/MEDIUM/COMPLEX)

```js
{
  tier: "COMPACT",
  scope,
  playbook: firstN(playbookText, 600) || fallbackDoctrineKey,
  session: { branch, recent_files: last(5), active_task },
  doctrine: compressedDoctrine(operation, 300)   // key rules only
}
```

**STANDARD** — target: REASONING-tier models (Nemotron 30B agentic)

```js
{
  tier: "STANDARD",
  scope,
  playbook: playbookText || fallbackDoctrineKey,
  session: { branch, recent_files: last(10), active_task, recent_events: last(10) },
  doctrine: fullDoctrine(operation)
}
```

**FULL (plan)** — target: Opus, Codex, any coding-tier model

```js
{
  tier: "FULL",
  scope,
  playbook: playbookText || fallbackDoctrine,
  session: { branch, recent_files: last(10), active_task, recent_events: last(10) },
  doctrine: fullDoctrine("plan"),
  knowledge: qdrantHits              // top-5 Qdrant results for task query
}
```

**FULL (review)** — same shape, adds experiences_summary

```js
{
  tier: "FULL",
  scope,
  playbook: playbookText || fallbackDoctrine,
  session: {
    branch, recent_files: last(10), active_task, recent_events: last(10),
    experiences_summary              // last 10 MemPalace entries summarised
  },
  doctrine: fullDoctrine("review"),
  knowledge: qdrantHits
}
```

**Fallback when playbook is empty:**

If `PgStore.get("agent:aelli:playbook:<scope>")` returns null or empty, `bundle-builder`
calls the memory client to fetch the role-appropriate doctrine bundle:

- `octowiz.plan` → `agent:planner:memory:ai-coding-workflow`
- `octowiz.review` → `agent:reviewer:memory:ai-coding-workflow`

This is the same key the octowiz-cache CLI serves. On a brand-new repo with no MemPalace
history, callers still get a useful context package.

### `src/skills/octowiz/operations.js`

**`octowiz.plan`**

```
Input:  { type: "octowiz.plan", scope, routerTier?, bundleTier?, task }
Steps:
  1. Resolve tier (bundleTier || routerTier → model-tier.js)
  2. Read playbook from PgStore — fallback if absent
  3. Read session snapshot from session-lifecycle
  4. If FULL: query engineering:query with task for Qdrant hits
  5. Return bundle
```

**`octowiz.review`**

```
Input:  { type: "octowiz.review", scope, routerTier?, bundleTier?, task }
Steps:
  1. Resolve tier
  2. Read playbook — fallback if absent (reviewer doctrine key)
  3. Read session snapshot
  4. If FULL: read last 10 MemPalace experiences → append experiences_summary
  5. If FULL: query engineering:query with task
  6. Return bundle
```

The two operations differ in:
- Fallback doctrine key (planner vs reviewer)
- `experiences_summary` on FULL (review only — a reviewer benefits from past session history)

### `src/skills/index.js` — wiring change

```js
const { createOctowizSkill } = require('./octowiz');

// inside createSkills({ pgStore, sessionLifecycle, memoryClient, litellmBase, litellmKey }):
const octowiz = createOctowizSkill({
  pgStore, sessionLifecycle, memoryClient, engineering, litellmBase, litellmKey
});
return [...existing, octowiz];
```

Mounting is automatic — index.js iterates all returned skills. No other changes to index.js.

---

## Stability items

### Gap 2 — octowiz retire-subscribe (octowiz repo)

PR `fix/gap2-retire-subscribe` is open. Merge it as part of this milestone.

**Effect:** daemon stops spawning a silent reconnect loop when AELLI is unreachable.
**Risk:** none — the PR disables a reconnect path that was producing noise with no benefit.

### Self-improve guard (aelli repo)

Add a size/breadth check after `npm test` passes in the improvement cron. If the diff
exceeds the threshold, write a summary to `.octowiz/improve-review-queue.jsonl` and skip
the commit:

```
Threshold: changed_lines > 50 OR changed_files > 2
→ flag (write to review queue, no commit)
→ else: commit as today
```

**Why these numbers:** the intended improvement run touches one function in one file.
A run that touches 3+ files or 50+ lines is doing something structural — that warrants
a human look before it lands on main.

### Advisory ownership declaration

`src/skills/octowiz/index.js` includes a comment at the top:

```js
// octowiz.advise and octowiz.improve are NOT implemented here in v1.
// PROMPT-event advisory is owned by dev-advisor.
// Improvement runs are owned by the hourly self-improve cron.
// Do not add PROMPT handling to this skill without a deliberate decision.
```

No code change elsewhere — this makes the boundary visible and prevents the self-improve
loop from accidentally unifying the two paths.

---

## Testing

| File | What it verifies |
|---|---|
| `tests/skills/octowiz/model-tier.test.js` | Each routerTier maps to the correct bundle tier; bundleTier override takes precedence; unknown tier defaults to STANDARD |
| `tests/skills/octowiz/bundle-builder.test.js` | COMPACT/STANDARD/FULL output shape; empty playbook triggers fallback fetch; FULL calls engineering:query; Qdrant [] produces valid bundle |
| `tests/skills/octowiz/plan.test.js` | plan operation returns correct bundle; FULL tier calls engineering:query |
| `tests/skills/octowiz/review.test.js` | review operation uses reviewer doctrine key; FULL tier appends experiences_summary |
| `tests/skills/octowiz/octowiz.skill.test.js` | Unknown operation type returns a clean error; skill registers at id "octowiz" |
| `tests/cron/self-improve-guard.test.js` | Run exceeding threshold writes to review queue and skips commit; run within threshold commits |
| All existing tests | Must still pass — the skill is additive |

---

## Out of scope (v1)

- `octowiz.advise` — deferred; dev-advisor owns PROMPT advisory
- `octowiz.improve` — deferred; hourly cron owns improvement runs
- Bridge modifications — octowiz-workflow skill continues using octowiz-cache; wiring to `/a2a/octowiz` is a follow-up PR
- Streaming responses — both operations return synchronous JSON; SSE is not needed for context packaging

---

## Definition of done

- [ ] `src/skills/octowiz/` exists with all 5 files (card.json, index.js, model-tier.js, bundle-builder.js, operations.js)
- [ ] `/a2a/octowiz` responds to agent-card requests
- [ ] `octowiz.plan` returns a valid COMPACT/STANDARD/FULL bundle with correct fields
- [ ] `octowiz.review` returns a valid bundle; FULL tier includes experiences_summary
- [ ] Empty playbook path: fallback doctrine is fetched from memory client, not an error
- [ ] All new tests pass; all existing tests still pass
- [ ] octowiz Gap 2 PR merged
- [ ] Self-improve guard implemented with threshold and review queue
- [ ] Advisory ownership comment in octowiz/index.js
