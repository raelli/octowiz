# Octowiz Group A+B Completion — Design Spec

**Date:** 2026-05-30
**Status:** Approved for implementation
**Scope:** Milestones 3–5 (complete half-built) + Milestone 6a (Agent View provider) + Milestone 8 (marketplace manifest)
**Deferred:** Milestones 6b (Sandcastle), 7 (Experience/MemPalace), 9 (VS Code/Cline) — blocked on external infra

---

## Context

Octowiz Engineering Runtime Plan v1 defines 9 milestones. After Phase 2 (A2A MVP) and Phase 5
(Bridge hooks) shipped, the repo sits at ~40–45% completion. Milestones 3–5 are half-built with
code in the wrong locations; Milestones 6–9 are open. This spec covers the work to reach a clean,
correctly-structured v0.1.0 state with all Group A+B milestones complete.

Current state:
- `hooks/bridge.py` — built, wrong location (target: `apps/claude_code_bridge/`)
- `apps/a2a-agent/advisor/` — built, wrong location (target: `packages/advisor/`)
- `octowiz_cache.py`, `octowiz_cache_cli.py`, `octowiz_env.py` — flat root modules (target: `packages/memory_client/`)
- `packages/`, `providers/` — directories do not exist
- Memory-client gaps: ADR writer, project rules loader, namespace loader — not yet built
- Agent View provider — not yet built
- Marketplace manifest — incomplete

---

## Target Structure

```
octowiz/
├── apps/
│   ├── a2a-agent/                   (unchanged — Phase 2 complete)
│   └── claude_code_bridge/          (moved from hooks/bridge.py)
│       ├── bridge.py
│       └── tests/
│
├── packages/
│   ├── advisor/                     (extracted from apps/a2a-agent/advisor/)
│   │   ├── __init__.py
│   │   ├── rules.py
│   │   ├── state.py
│   │   └── tests/
│   ├── events/                      (new — shared OctowizEvent contract)
│   │   └── __init__.py
│   └── memory_client/               (moved from root flat modules)
│       ├── __init__.py
│       ├── cache.py                 (was octowiz_cache.py)
│       ├── cli.py                   (was octowiz_cache_cli.py)
│       ├── env.py                   (was octowiz_env.py)
│       ├── adr.py                   (new — ADR writer)
│       ├── namespace.py             (new — namespace/project rules loader)
│       └── tests/
│
├── providers/
│   └── claude_agent_view/           (new — Phase 6a)
│       ├── __init__.py
│       ├── session.py               (AgentSession dataclass)
│       ├── parser.py                (CLI output → AgentSession)
│       ├── provider.py              (CodingExecutionProvider impl)
│       └── tests/
│
├── hooks/
│   ├── hooks.json                   (path updated)
│   └── upgrade-check.sh             (version gate updated)
│
├── skills/                          (unchanged)
├── .claude-plugin/plugin.json       (version + manifest updated)
└── pyproject.toml                   (packaging updated)
```

---

## Packaging Mechanism

### Current (flat py-modules)
```toml
[tool.setuptools]
py-modules = ["octowiz_cache", "octowiz_cache_cli", "import_litellm_memories", "octowiz_env"]
```

### After PR1 (find_packages)

`packages/` and `providers/` become proper Python packages by adding empty `__init__.py` at
each root:
- `packages/__init__.py` (new)
- `providers/__init__.py` (new)

```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["packages*", "providers*"]
```

`apps/` is intentionally excluded from the import tree — `apps/a2a-agent` and
`apps/claude_code_bridge` are run by path (subprocess / hooks.json), never imported.
`apps/a2a-agent` imports from `packages.*`; it is not itself an importable package.

Sub-packages under `packages/` and `providers/` become importable via dotted paths:
- `from packages.memory_client.env import init_repo_state`
- `from packages.advisor.rules import RulesAdvisor`
- `from providers.claude_agent_view.provider import ClaudeAgentViewProvider`

**Verification gate (must pass before PR1 merges):**
```bash
pip install -e . && python -c "import packages.memory_client.cli; import packages.advisor.rules"
```
If this ImportErrors, the packaging config is wrong.

### pyproject.toml changes
- Entry point: `octowiz-cache = "packages.memory_client.cli:main"`
- Move `httpx` and a2a-agent deps into `[project.dependencies]` / `[project.optional-dependencies]`
- Remove separate `pip install -r apps/a2a-agent/requirements.txt` from CI — replaced by single
  `pip install -e ".[dev]"`

### pytest discovery
Add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["apps", "packages", "providers", "tests"]
```

---

## Event/Type Contract

A minimal `packages/events/__init__.py` defines the `OctowizEvent` TypedDict and the string
literals for event types:

```python
from typing import TypedDict, List, Optional, Literal

EventType = Literal[
    "prompt", "file-edit", "file-write", "tool-used",
    "agent-run-started", "agent-run-finished", "risk-detected"
]

class OctowizEvent(TypedDict, total=False):
    type: EventType
    capability: str
    sessionId: str
    repoRoot: str
    branch: str
    live_modified_files: List[str]
    prompt_summary: str
```

Bridge produces `OctowizEvent`. Advisor consumes it. Agent View provider emits
`agent-run-started` / `agent-run-finished`. No external schema library — just the shared dict
shape in one place.

Note: `EventType` literals use kebab-case strings (`"file-edit"`, `"file-write"`) to match the
values already in the running `bridge.py`, not PascalCase from the plan's §11 TypeScript sketch.
This is intentional — follow the code, not the diagram.

---

## PR1 — Pure Restructure

**Goal:** Zero new behaviour. Every test that passes before passes after. Version bump to v0.1.0.

### File moves

| From | To |
|---|---|
| `hooks/bridge.py` | `apps/claude_code_bridge/bridge.py` |
| `hooks/tests/test_bridge.py` | `apps/claude_code_bridge/tests/test_bridge.py` |
| `apps/a2a-agent/advisor/__init__.py` | `packages/advisor/__init__.py` |
| `apps/a2a-agent/advisor/rules.py` | `packages/advisor/rules.py` |
| `apps/a2a-agent/advisor/state.py` | `packages/advisor/state.py` |
| `apps/a2a-agent/tests/test_advisor.py` | `packages/advisor/tests/test_advisor.py` |
| `octowiz_cache.py` | `packages/memory_client/cache.py` |
| `octowiz_cache_cli.py` | `packages/memory_client/cli.py` |
| `octowiz_env.py` | `packages/memory_client/env.py` |
| `tests/test_octowiz_cache.py` | `packages/memory_client/tests/test_cache.py` |
| `tests/test_octowiz_cache_cli_check.py` | `packages/memory_client/tests/test_cli_check.py` |
| `tests/test_octowiz_env.py` | `packages/memory_client/tests/test_env.py` |
| `tests/test_octowiz_env_integration.py` | `packages/memory_client/tests/test_env_integration.py` |
| `tests/test_seed.py` | `packages/memory_client/tests/test_seed.py` |
| `tests/test_importer.py` | `packages/memory_client/tests/test_importer.py` |
| `import_litellm_memories.py` | `packages/memory_client/importer.py` |

### Import updates

All internal imports updated to new dotted paths. Key patterns:

- `from octowiz_env import X` → `from packages.memory_client.env import X`
- `from octowiz_cache import X` → `from packages.memory_client.cache import X`
- `from octowiz_cache_cli import X` → `from packages.memory_client.cli import X`
- `from advisor.rules import X` → `from packages.advisor.rules import X`
- `from advisor.state import X` → `from packages.advisor.state import X`
- Bridge and advisor updated to import `OctowizEvent` from `packages.events`

**a2a-agent advisor consumers** — `apps/a2a-agent/dispatch.py`, `capabilities/advise.py`, and
`main.py` all import from the moved advisor. Rewrite all three in PR1. Run full
`apps/a2a-agent/tests/` suite (including `test_dispatch.py`) after the move to confirm no
consumer was missed.

### Skills update

`skills/octowiz-setup/skill.md` inline `python3 -c "..."` snippets updated:
- All `from octowiz_env import` → `from packages.memory_client.env import`

### hooks/hooks.json
```json
"command": "python3 \"$CLAUDE_PLUGIN_ROOT/apps/claude_code_bridge/bridge.py\""
```

### packages/memory_client/cli.py — add --version flag

Add `--version` as a subcommand/flag to `cli.py` that prints `octowiz-cache 0.1.0` and exits 0.
This is the v0.1.0-only feature the upgrade gate checks for.

### hooks/upgrade-check.sh version gate

New gate checks that `--version` succeeds (exists in v0.1.0+), not that it matches a specific
version string — avoids breaking forward-compat when v0.2.0 ships:
```bash
if octowiz-cache --version &>/dev/null; then
    exit 0  # v0.1.0+ already installed
fi
```

### .claude-plugin/plugin.json
- `"version": "0.1.0"`

### pyproject.toml
- `"version": "0.1.0"`
- Switch to `find_packages`
- New entry point
- Add `packages/events/__init__.py` (new file, not a move)

### Acceptance criteria
- `pytest apps/ packages/ providers/ tests/ -v` all green on Python 3.8, 3.11, 3.12
- `octowiz-cache check` works after `pip install -e .`
- `hooks.json` path resolves correctly in a fresh plugin install

---

## PR2 — Memory-Client Completions

**Goal:** Add the missing pieces from Milestone 3 into the now-correct location.

### packages/memory_client/adr.py

```python
def write_adr(base_url: str, api_key: str, project_id: str, slug: str, content: str) -> None:
    """Write an ADR entry to LiteLLM Memory under project:{id}:octowiz:adr:{date}-{slug}."""
```

- Formats the memory key as `project:{project_id}:octowiz:adr:{YYYY-MM-DD}-{slug}`
- POSTs to `{base_url}/v1/memory` with the structured content
- Raises on HTTP error; caller decides whether to surface or swallow

### packages/memory_client/namespace.py

```python
def load_project_rules(base_url: str, api_key: str, project_id: str) -> dict:
    """Fetch project rules from LiteLLM Memory: project:{id}:octowiz:rules"""

def load_role_bundle(base_url: str, api_key: str, role: str, namespace: str) -> dict:
    """Fetch a role bundle: team:{namespace}:octowiz:roles:{role}"""
```

Consolidates the inline `octowiz-cache get --role X` calls currently scattered across skills
into importable functions with consistent error handling.

### Tests
- `test_adr.py` — mocked httpx, verifies key format and payload shape
- `test_namespace.py` — mocked httpx, verifies correct namespace construction

### Acceptance criteria
- `write_adr` produces correct LiteLLM Memory key format
- `load_project_rules` and `load_role_bundle` return parsed dicts on 200, raise on 4xx/5xx
- Tests pass on all three Python versions

---

## PR3 — Agent View Provider + Marketplace Manifest

**Goal:** Milestone 6a complete; marketplace manifest reflects the full plugin surface.

### providers/claude_agent_view/session.py

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class AgentSession:
    id: str
    status: str               # running | stopped | waiting | error
    branch: Optional[str]
    repo: Optional[str]
    needs_input: bool
    ready_for_review: bool
    created_at: Optional[str]
```

### providers/claude_agent_view/parser.py

```python
from typing import List

def parse_sessions(json_output: str) -> List[AgentSession]:
    """Parse `claude agents --json` output into AgentSession list.
    Isolated so CLI schema changes only touch this function."""
```

- Returns empty list on parse error (never raises — CLI output is untrusted)
- Maps CLI status strings to normalised `AgentSession.status` values
- `needs_input` and `ready_for_review` derived from status + message fields

### providers/claude_agent_view/provider.py

```python
class ClaudeAgentViewProvider:
    def list_sessions(self) -> List[AgentSession]: ...
    def dispatch(self, task: str, repo: str) -> str: ...      # returns run_id
    def get_status(self, run_id: str) -> AgentSession: ...
    def get_logs(self, run_id: str) -> str: ...
    def stop(self, run_id: str) -> None: ...
```

Shells out to `claude` CLI. All subprocess calls go through a single `_run_claude(args)` helper
so tests can mock at one seam.

### Tests
- `test_parser.py` — fixture JSON snapshots, no subprocess
- `test_provider.py` — mocked `_run_claude`, integration tests gated on
  `OCTOWIZ_INTEGRATION_TESTS=1` env flag

### .claude-plugin/plugin.json manifest additions

```json
{
  "version": "0.1.0",
  "skills": ["./skills/octowiz-workflow", "./skills/octowiz-setup"],
  "hooks": ["./hooks/hooks.json"],
  "providers": ["./providers/claude_agent_view"],
  "dependencies": {
    "plugins": ["superpowers", "mattpocock-skills"],
    "python": ">=3.8"
  }
}
```

### Acceptance criteria
- `ClaudeAgentViewProvider.list_sessions()` returns `[]` (not an error) when `claude` CLI is absent
- `parse_sessions` returns `[]` on malformed input, never raises
- Manifest validates against plugin schema
- All new tests green on Python 3.8, 3.11, 3.12

---

## Backwards Compatibility

**Version gate update (upgrade-check.sh):** v0.1.0 exposes `octowiz-cache --version`. The
SessionStart hook detects pre-v0.1.0 installs by checking for this flag and auto-upgrades via
`pip install --upgrade git+https://github.com/raelli/octowiz.git`.

**Skills inline imports:** updated in PR1. Plugin cache refreshes atomically with the package
upgrade on next SessionStart — no window where CLI and skills are out of sync.

**No shims.** The upgrade path is closed by the existing upgrade-check.sh mechanism.

---

## Out of Scope

- Milestone 6b (Sandcastle provider) — blocked on Sandcastle infra
- Milestone 7 (Experience Loop / MemPalace) — blocked on MemPalace
- Milestone 9 (VS Code / Cline) — separate project/repo
- `packages/agent_control`, `packages/execution`, `packages/observability`, `packages/policy`,
  `packages/types`, `packages/knowledge_client`, `packages/experience_client`,
  `packages/marketplace_client` — deferred to Groups C/D
