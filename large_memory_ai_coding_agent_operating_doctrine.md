# Large Memory: AI Coding Agent Operating Doctrine

Source: Full Walkthrough: Workflow for AI Coding — Matt Pocock  
Purpose: Durable LiteLLM team playbook for coding agents working on Allspark / IntegraHub-style software projects.

## Core Thesis

AI coding works best when old-school software engineering discipline is made explicit for agents. The goal is not “specs to code” with no understanding of the code. The goal is a shared design concept, small agent-safe work units, strong feedback loops, and human taste at the right points.

## Context Management

Agents have a reliable working zone and a degraded zone. Keep persistent instructions small. Avoid huge always-on prompts. Prefer fresh contexts for distinct phases: alignment, implementation, review, and QA. Use subagents for exploration when their output can be summarized back to the orchestrator. Track token usage in long coding sessions.

Compacting is useful but should not become the default architecture. A clean reset is often better because it returns the agent to a known state.

## Workflow

1. Start with the idea or brief.
2. Run a grill-me alignment interview.
3. Produce a PRD/destination document.
4. Convert the PRD into vertical-slice issues on a dependency-aware Kanban board.
5. Classify issues as HITL or AFK.
6. Run AFK implementers only on clear, unblocked tasks.
7. Require TDD and feedback loops.
8. Review in a fresh context.
9. Human QA validates taste, UX, product fit, and acceptance.
10. Archive temporary planning docs when complete to avoid doc rot.

## Grill-Me Alignment

The agent should interview the human/domain expert relentlessly but usefully. Ask one question at a time. Each question should include a recommended answer. Resolve branches of the design tree. Surface hidden decisions such as data model, retroactivity, migrations, permissions, metrics, UI placement, testability, and rollout.

The output of this phase is not primarily a plan. The output is shared understanding.

## PRD as Destination Document

A PRD should capture where the work is going. It should include problem, solution, user stories, implementation decisions, testing decisions, modules likely to change, out-of-scope items, and definition of done.

Do not over-polish the PRD. Once alignment is good, the highest-value human effort shifts to issue slicing and QA.

## Vertical Slices / Tracer Bullets

Agents tend to code horizontally by layer: database first, then API, then UI. This delays feedback until late. Prefer thin vertical slices that cross layers and produce visible/testable behavior early.

Each implementation issue should be independently grabbable, small, explicitly blocked/unblocked, and tagged HITL or AFK.

## AFK Implementation

AFK agents should read the backlog, select the highest-priority unblocked AFK issue, explore the repo, implement with TDD, run feedback loops, commit, and mark/report status. They must not pick HITL tasks or silently expand scope.

## TDD and Feedback Loops

TDD is a major reliability booster. Write a failing test before implementation. Confirm red, implement green, then refactor. Strong tests, type checks, linting, migrations, and local run commands are the ceiling for agent output quality.

If an agent performs badly, inspect the feedback loops before blaming the model.

## Review

Review should happen in a fresh context. Push coding standards into reviewer context. Review for correctness, test quality, scope creep, security, data migrations, permissions, edge cases, module boundaries, and maintainability.

## Human QA

Automated review is useful, but product QA needs humans. Humans validate taste, UX, copy, interaction quality, user confusion, and whether the feature actually solves the problem. Do not automate away judgment.

## Architecture for Agents

Agents work better in codebases with deep modules: simple public interface, meaningful internal behavior, and clear test boundaries. Avoid shallow modules scattered across many tiny files with implicit dependencies.

Use interface-first delegation: humans/architects define the interface and behavior of important modules; agents implement internals behind those boundaries.

## Coding Standards: Push vs Pull

Implementers should be able to pull coding standards and skills when needed. Reviewers should receive coding standards pushed directly into context so they can compare the diff against them.

## Documentation Hygiene

Temporary PRDs and issue plans can rot. Once work is complete, close/archive them or mark them historical/superseded. Do not leave stale docs in active repo context where agents may treat them as truth.

## Parallel Agents

Parallel execution needs dependency-aware issues. Planner selects unblocked tasks, each implementer works in a sandbox/worktree/branch, reviewer checks each branch, and merger resolves integration. Parallelization increases review load, so tasks must stay small.