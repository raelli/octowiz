# Octowiz Group A+B Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure octowiz to its target monorepo layout, complete the memory-client, and add the Agent View provider — reaching a clean v0.1.0 state.

**Architecture:** Three PRs in sequence. PR1 is a pure mechanical restructure (zero new behaviour, all tests green before and after). PR2 adds missing memory-client functions (ADR writer, namespace loader). PR3 adds the Claude Agent View execution provider and completes the marketplace manifest.

**Tech Stack:** Python 3.8+, pytest, httpx, setuptools find_packages, FastAPI (a2a-agent only), dataclasses, subprocess (provider)

**Spec:** `docs/superpowers/specs/2026-05-30-octowiz-group-ab-completion-design.md`

---

## Baseline (run before any changes)

- [ ] **Record test baseline**

```bash
pip install -e ".[dev]"
pip install -r apps/a2a-agent/requirements.txt
python -m pytest tests/ -q --tb=no
python -m pytest apps/a2a-agent/tests/ --rootdir=apps/a2a-agent -q --tb=no
```

Expected: `195 passed` (root) and `15 passed` (a2a). Note the exact counts — PR1 must match them exactly.

---

## PR1 — Pure Restructure

**Branch:** `feat/pr1-restructure`

**Note on test_advisor.py:** The spec moves it to `packages/advisor/tests/`. This plan keeps it in `apps/a2a-agent/tests/` — it is an A2A integration test that instantiates the full FastAPI app, not a unit test for the advisor package. Moving it would require a fragile cross-directory sys.path hack. Only its imports are updated.

---

### Task 1: Create directory scaffold

**Files:**
- Create: `packages/__init__.py`
- Create: `packages/events/__init__.py`
- Create: `packages/advisor/__init__.py`
- Create: `packages/advisor/tests/__init__.py`
- Create: `packages/memory_client/__init__.py`
- Create: `packages/memory_client/tests/__init__.py`
- Create: `providers/__init__.py`
- Create: `providers/claude_agent_view/__init__.py`
- Create: `providers/claude_agent_view/tests/__init__.py`
- Create: `apps/claude_code_bridge/` (directory only — no `__init__.py`; run by path)
- Create: `apps/claude_code_bridge/tests/` (directory only)

- [ ] **Step 1: Create all package init files**

```bash
mkdir -p packages/events packages/advisor/tests packages/memory_client/tests
mkdir -p providers/claude_agent_view/tests
mkdir -p apps/claude_code_bridge/tests
touch packages/__init__.py
touch packages/events/__init__.py
touch packages/advisor/__init__.py packages/advisor/tests/__init__.py
touch packages/memory_client/__init__.py packages/memory_client/tests/__init__.py
touch providers/__init__.py
touch providers/claude_agent_view/__init__.py providers/claude_agent_view/tests/__init__.py
```

- [ ] **Step 2: Verify directories exist**

```bash
find packages providers apps/claude_code_bridge -name "__init__.py" -o -type d | sort
```

Expected output includes: `packages/__init__.py`, `packages/events/__init__.py`, `packages/advisor/__init__.py`, `providers/__init__.py`, `providers/claude_agent_view/__init__.py`

---

### Task 2: Create packages/events/__init__.py

**Files:**
- Modify: `packages/events/__init__.py`

- [ ] **Step 1: Write OctowizEvent contract**

```python
# packages/events/__init__.py
from __future__ import annotations

from typing import List, Literal, Optional

from typing_extensions import TypedDict  # noqa: F401 — use typing.TypedDict on 3.8+

try:
    from typing import TypedDict
except ImportError:  # pragma: no cover
    from typing_extensions import TypedDict  # type: ignore

EventType = Literal[
    "prompt",
    "file-edit",
    "file-write",
    "tool-used",
    "agent-run-started",
    "agent-run-finished",
    "risk-detected",
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

Wait — `typing.TypedDict` is available from Python 3.8 directly. Simplify:

```python
# packages/events/__init__.py
from __future__ import annotations

from typing import List, Literal, TypedDict

EventType = Literal[
    "prompt",
    "file-edit",
    "file-write",
    "tool-used",
    "agent-run-started",
    "agent-run-finished",
    "risk-detected",
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

- [ ] **Step 2: Verify import works on Python 3.8+**

```bash
python -c "from packages.events import OctowizEvent, EventType; print('OK')"
```

Expected: `OK`

---

### Task 3: Move memory_client — source files

**Files:**
- `git mv octowiz_cache.py packages/memory_client/cache.py`
- `git mv octowiz_cache_cli.py packages/memory_client/cli.py`
- `git mv octowiz_env.py packages/memory_client/env.py`
- `git mv import_litellm_memories.py packages/memory_client/importer.py`
- Modify: `packages/memory_client/cli.py` (update imports + add --version)

- [ ] **Step 1: Move the files**

```bash
git mv octowiz_cache.py packages/memory_client/cache.py
git mv octowiz_cache_cli.py packages/memory_client/cli.py
git mv octowiz_env.py packages/memory_client/env.py
git mv import_litellm_memories.py packages/memory_client/importer.py
```

- [ ] **Step 2: Update imports in packages/memory_client/cli.py**

Find the lines (currently near the top after the docstring):
```python
import octowiz_cache
from octowiz_cache import (
```

Replace with relative imports:
```python
from . import cache as octowiz_cache
from .cache import (
```

Also update the `cmd_seed` function body — find any bare `octowiz_cache.X` references and confirm they still work via the alias. Run a quick grep:

```bash
grep -n "octowiz_cache\|octowiz_env\|octowiz_cache_cli" packages/memory_client/cli.py
```

If any `octowiz_env` imports appear, replace with `from .env import X`.

- [ ] **Step 3: Add --version to cli.py**

Find the `main()` function and add a version subcommand/flag. Locate the argparse setup and add:

```python
parser.add_argument("--version", action="version", version="octowiz-cache 0.1.0")
```

This must be added to the top-level parser (before subparsers), so `octowiz-cache --version` exits 0 and prints the version string.

- [ ] **Step 4: Verify no remaining old-style imports in cli.py**

```bash
grep -n "import octowiz_cache$\|from octowiz_cache\|from octowiz_env\|from octowiz_cache_cli" packages/memory_client/cli.py
```

Expected: no output.

---

### Task 4: Move memory_client — tests

**Files:**
- `git mv tests/test_octowiz_cache.py packages/memory_client/tests/test_cache.py`
- `git mv tests/test_octowiz_cache_cli_check.py packages/memory_client/tests/test_cli_check.py`
- `git mv tests/test_octowiz_env.py packages/memory_client/tests/test_env.py`
- `git mv tests/test_octowiz_env_integration.py packages/memory_client/tests/test_env_integration.py`
- `git mv tests/test_seed.py packages/memory_client/tests/test_seed.py`
- `git mv tests/test_importer.py packages/memory_client/tests/test_importer.py`
- Modify each test file: update all import paths and mock.patch strings

- [ ] **Step 1: Move all test files**

```bash
git mv tests/test_octowiz_cache.py packages/memory_client/tests/test_cache.py
git mv tests/test_octowiz_cache_cli_check.py packages/memory_client/tests/test_cli_check.py
git mv tests/test_octowiz_env.py packages/memory_client/tests/test_env.py
git mv tests/test_octowiz_env_integration.py packages/memory_client/tests/test_env_integration.py
git mv tests/test_seed.py packages/memory_client/tests/test_seed.py
git mv tests/test_importer.py packages/memory_client/tests/test_importer.py
```

- [ ] **Step 2: Update imports in test_cache.py**

Find:
```python
import octowiz_cache
from octowiz_cache import (
```
Replace with:
```python
from packages.memory_client import cache as octowiz_cache
from packages.memory_client.cache import (
```

Find all `mock.patch("octowiz_cache.` strings and replace with `mock.patch("packages.memory_client.cache.`:
```bash
sed -i '' 's/mock\.patch("octowiz_cache\./mock.patch("packages.memory_client.cache./g' packages/memory_client/tests/test_cache.py
```

- [ ] **Step 3: Update imports in test_cli_check.py**

Find:
```python
from octowiz_cache_cli import cmd_check
from octowiz_env import CheckResult
```
Replace with:
```python
from packages.memory_client.cli import cmd_check
from packages.memory_client.env import CheckResult
```

Find all `patch("octowiz_env.` and replace:
```bash
sed -i '' 's/patch("octowiz_env\./patch("packages.memory_client.env./g' packages/memory_client/tests/test_cli_check.py
```

- [ ] **Step 4: Update imports in test_env.py**

Find all `from octowiz_env import` lines and replace `octowiz_env` with `packages.memory_client.env`:
```bash
sed -i '' 's/from octowiz_env import/from packages.memory_client.env import/g' packages/memory_client/tests/test_env.py
```

Find all `patch("octowiz_env.`:
```bash
sed -i '' 's/patch("octowiz_env\./patch("packages.memory_client.env./g' packages/memory_client/tests/test_env.py
```

- [ ] **Step 5: Update imports in test_env_integration.py**

```bash
sed -i '' 's/from octowiz_env import/from packages.memory_client.env import/g' packages/memory_client/tests/test_env_integration.py
sed -i '' 's/patch("octowiz_env\./patch("packages.memory_client.env./g' packages/memory_client/tests/test_env_integration.py
```

- [ ] **Step 6: Update imports in test_seed.py**

Find:
```python
from octowiz_env import derive_project_id, seed_project_namespace
```
Replace with:
```python
from packages.memory_client.env import derive_project_id, seed_project_namespace
```

Find:
```python
from octowiz_cache_cli import cmd_seed
import octowiz_cache
```
Replace with:
```python
from packages.memory_client.cli import cmd_seed
from packages.memory_client import cache as octowiz_cache
```

Find all `patch("octowiz_env.` and `patch("octowiz_cache.`:
```bash
sed -i '' 's/patch("octowiz_env\./patch("packages.memory_client.env./g' packages/memory_client/tests/test_seed.py
sed -i '' 's/patch("octowiz_cache\./patch("packages.memory_client.cache./g' packages/memory_client/tests/test_seed.py
```

- [ ] **Step 7: Update imports in test_importer.py**

```bash
grep -n "octowiz_cache\|octowiz_env" packages/memory_client/tests/test_importer.py
```

Update any found imports to use `packages.memory_client.*` paths.

- [ ] **Step 8: Run memory_client tests to verify**

```bash
python -m pytest packages/memory_client/tests/ -q --tb=short
```

Expected: all 195 tests pass (same count as baseline root tests).

---

### Task 5: Move advisor — source files

**Files:**
- `git mv apps/a2a-agent/advisor/rules.py packages/advisor/rules.py`
- `git mv apps/a2a-agent/advisor/state.py packages/advisor/state.py`
- Modify: `apps/a2a-agent/capabilities/advise.py` (update advisor imports)
- Modify: `apps/a2a-agent/tests/test_advisor.py` (update advisor imports — file stays here)

- [ ] **Step 1: Move advisor source files**

```bash
git mv apps/a2a-agent/advisor/rules.py packages/advisor/rules.py
git mv apps/a2a-agent/advisor/state.py packages/advisor/state.py
# Remove now-empty advisor dir from a2a-agent (keep __init__.py if needed)
git rm apps/a2a-agent/advisor/__init__.py 2>/dev/null || true
rmdir apps/a2a-agent/advisor 2>/dev/null || true
```

- [ ] **Step 2: Update capabilities/advise.py**

Find:
```python
from advisor.state import store
from advisor.rules import RulesAdvisor
```
Replace with:
```python
from packages.advisor.state import store
from packages.advisor.rules import RulesAdvisor
```

- [ ] **Step 3: Update test_advisor.py (stays in apps/a2a-agent/tests/)**

Find:
```python
import advisor.state as _state_mod
importlib.reload(_state_mod)
import capabilities.advise as _adv_mod
```
Replace with:
```python
import packages.advisor.state as _state_mod
importlib.reload(_state_mod)
import capabilities.advise as _adv_mod
```

- [ ] **Step 4: Run a2a tests to verify**

```bash
python -m pytest apps/a2a-agent/tests/ --rootdir=apps/a2a-agent -q --tb=short
```

Expected: `15 passed`

---

### Task 6: Move bridge

**Files:**
- `git mv hooks/bridge.py apps/claude_code_bridge/bridge.py`
- `git mv hooks/tests/test_bridge.py apps/claude_code_bridge/tests/test_bridge.py`

- [ ] **Step 1: Move bridge files**

```bash
git mv hooks/bridge.py apps/claude_code_bridge/bridge.py
git mv hooks/tests/test_bridge.py apps/claude_code_bridge/tests/test_bridge.py
rmdir hooks/tests 2>/dev/null || true
```

- [ ] **Step 2: Check bridge for any old-style imports**

```bash
grep -n "from octowiz\|import octowiz\|from advisor" apps/claude_code_bridge/bridge.py
```

Expected: no output (bridge uses only stdlib + httpx).

- [ ] **Step 3: Run bridge tests to verify**

```bash
python -m pytest apps/claude_code_bridge/tests/ -q --tb=short
```

Expected: all bridge tests pass.

---

### Task 7: Update pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Rewrite pyproject.toml**

Replace the entire file with:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "octowiz"
version = "0.1.0"
description = "Octowiz Engineering Agent — Claude Code adapter, A2A bridge, and execution coordinator"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.8"
dependencies = [
    "httpx>=0.27.0",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
]

[project.optional-dependencies]
dev = ["pytest>=7"]

[tool.setuptools.packages.find]
where = ["."]
include = ["packages*", "providers*"]

[project.scripts]
octowiz-cache = "packages.memory_client.cli:main"

[tool.pytest.ini_options]
testpaths = ["packages", "providers", "tests"]
```

Note: `apps/` is excluded from testpaths — a2a tests are run separately per CI config (they need their own rootdir for sys.path to work correctly).

Note: `tests/` remains in testpaths to catch any remaining root-level tests during the transition.

- [ ] **Step 2: Reinstall and verify package is importable**

```bash
pip install -e ".[dev]"
python -c "import packages.memory_client.cli; import packages.advisor.rules; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Verify CLI entry point works**

```bash
octowiz-cache --version
```

Expected: `octowiz-cache 0.1.0`

---

### Task 8: Update hooks.json and upgrade-check.sh

**Files:**
- Modify: `hooks/hooks.json`
- Modify: `hooks/upgrade-check.sh`

- [ ] **Step 1: Update hooks.json bridge path**

In `hooks/hooks.json`, find:
```json
"command": "python3 \"$CLAUDE_PLUGIN_ROOT/hooks/bridge.py\""
```
Replace with:
```json
"command": "python3 \"$CLAUDE_PLUGIN_ROOT/apps/claude_code_bridge/bridge.py\""
```

- [ ] **Step 2: Update upgrade-check.sh version gate**

Find the current gate block (checks for `init --help`):
```bash
if octowiz-cache init --help &>/dev/null; then
    exit 0  # Already current
fi
```
Replace with:
```bash
if octowiz-cache --version &>/dev/null; then
    exit 0  # v0.1.0+ already installed
fi
```

- [ ] **Step 3: Verify hooks.json is valid JSON**

```bash
python3 -c "import json; json.load(open('hooks/hooks.json')); print('valid')"
```

Expected: `valid`

---

### Task 9: Update skills/octowiz-setup/skill.md

**Files:**
- Modify: `skills/octowiz-setup/skill.md`

- [ ] **Step 1: Update all inline python3 -c import snippets**

Find all occurrences of `from octowiz_env import` in the skill file and replace with `from packages.memory_client.env import`:

```bash
grep -n "from octowiz_env import" skills/octowiz-setup/skill.md
```

For each line found, update manually (skill.md has 6 such occurrences per the spec):
```
from octowiz_env import init_machine_state, save_machine_state, MACHINE_STATE_PATH
→
from packages.memory_client.env import init_machine_state, save_machine_state, MACHINE_STATE_PATH

from octowiz_env import load_repo_state
→
from packages.memory_client.env import load_repo_state

from octowiz_env import init_machine_state, save_machine_state, MACHINE_STATE_PATH, _now_iso
→
from packages.memory_client.env import init_machine_state, save_machine_state, MACHINE_STATE_PATH, _now_iso

from octowiz_env import init_repo_state, save_repo_state
→
from packages.memory_client.env import init_repo_state, save_repo_state

from octowiz_env import dismiss_check, MACHINE_STATE_PATH
→
from packages.memory_client.env import dismiss_check, MACHINE_STATE_PATH
```

Use sed for the bulk replacement:
```bash
sed -i '' 's/from octowiz_env import/from packages.memory_client.env import/g' skills/octowiz-setup/skill.md
```

- [ ] **Step 2: Verify no old-style imports remain**

```bash
grep -n "octowiz_env\|octowiz_cache\b\|octowiz_cache_cli" skills/octowiz-setup/skill.md
```

Expected: no output.

---

### Task 10: Update plugin.json version

**Files:**
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Bump version to 0.1.0**

In `.claude-plugin/plugin.json`, change:
```json
"version": "0.0.6"
```
to:
```json
"version": "0.1.0"
```

---

### Task 11: Full verification gate

- [ ] **Step 1: Run import verification gate**

```bash
pip install -e ".[dev]"
python -c "import packages.memory_client.cli; import packages.advisor.rules; print('gate: PASS')"
```

Expected: `gate: PASS`

- [ ] **Step 2: Run full root test suite**

```bash
python -m pytest packages/ providers/ tests/ -q --tb=short
```

Expected: **195 passed** (same as baseline). Any different count = a test was lost or added; investigate before continuing.

- [ ] **Step 3: Run a2a tests**

```bash
python -m pytest apps/a2a-agent/tests/ --rootdir=apps/a2a-agent -q --tb=short
```

Expected: **15 passed**

- [ ] **Step 4: Verify CLI works end-to-end**

```bash
octowiz-cache --version
octowiz-cache check
```

Expected: `octowiz-cache 0.1.0` then a JSON object `{"status": "clean", ...}`.

---

### Task 12: Commit PR1

- [ ] **Step 1: Stage all changes**

```bash
git add -A
git status
```

Review the staged files — confirm all old paths are deleted, all new paths are added, no `.env` files staged.

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
refactor: restructure to target monorepo layout — v0.1.0

Move bridge → apps/claude_code_bridge/, advisor → packages/advisor/,
cache/cli/env → packages/memory_client/. Add packages/events/ OctowizEvent
contract. Switch pyproject.toml to find_packages, update entry point to
packages.memory_client.cli:main. Add --version flag to CLI. Update hooks.json
bridge path and upgrade-check.sh version gate. All 195+15 tests pass.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## PR2 — Memory-Client Completions

**Branch:** `feat/pr2-memory-client`

Checkout from the PR1 branch (or from main after PR1 merges).

---

### Task 13: Implement packages/memory_client/adr.py (TDD)

**Files:**
- Create: `packages/memory_client/tests/test_adr.py`
- Create: `packages/memory_client/adr.py`

- [ ] **Step 1: Write failing test**

```python
# packages/memory_client/tests/test_adr.py
"""Tests for ADR writer — writes ADR entries to LiteLLM Memory."""
import unittest
from unittest.mock import MagicMock, patch


class TestWriteAdr(unittest.TestCase):

    def test_memory_key_format(self):
        """write_adr posts to the correct namespaced key."""
        with patch("packages.memory_client.adr.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_httpx.put.return_value = mock_response

            from packages.memory_client.adr import write_adr
            write_adr(
                base_url="http://localhost:4000",
                api_key="sk-test",
                project_id="proj-abc",
                slug="use-packages-layout",
                content="We restructured to packages/ for clean imports.",
                date="2026-05-30",
            )

            call_args = mock_httpx.put.call_args
            url = call_args[0][0]
            self.assertIn("project:proj-abc:octowiz:adr:2026-05-30-use-packages-layout", url)

    def test_raises_on_http_error(self):
        """write_adr propagates HTTP errors to the caller."""
        import httpx
        with patch("packages.memory_client.adr.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock()
            )
            mock_httpx.put.return_value = mock_response
            mock_httpx.HTTPStatusError = httpx.HTTPStatusError

            from packages.memory_client.adr import write_adr
            with self.assertRaises(httpx.HTTPStatusError):
                write_adr(
                    base_url="http://localhost:4000",
                    api_key="sk-test",
                    project_id="proj-abc",
                    slug="test-error",
                    content="test",
                )

    def test_authorization_header_sent(self):
        """write_adr includes the API key as Bearer token."""
        with patch("packages.memory_client.adr.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_httpx.put.return_value = mock_response

            from packages.memory_client.adr import write_adr
            write_adr(
                base_url="http://localhost:4000",
                api_key="sk-test-key",
                project_id="proj-abc",
                slug="test",
                content="content",
            )

            _, kwargs = mock_httpx.put.call_args
            headers = kwargs.get("headers", {})
            self.assertIn("Authorization", headers)
            self.assertEqual(headers["Authorization"], "Bearer sk-test-key")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest packages/memory_client/tests/test_adr.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'packages.memory_client.adr'`

- [ ] **Step 3: Implement packages/memory_client/adr.py**

```python
# packages/memory_client/adr.py
"""ADR writer — persists Architecture Decision Records to LiteLLM Memory."""
from __future__ import annotations

from datetime import date as _date
from urllib.parse import quote

import httpx


def write_adr(
    base_url: str,
    api_key: str,
    project_id: str,
    slug: str,
    content: str,
    date: str = "",
) -> None:
    """Write an ADR to LiteLLM Memory under project:{id}:octowiz:adr:{date}-{slug}.

    Args:
        base_url: LiteLLM Proxy base URL (e.g. https://llm.integrahub.de)
        api_key: API key for Authorization: Bearer header
        project_id: Project namespace identifier
        slug: Short kebab-case name for this ADR (e.g. use-packages-layout)
        content: Full ADR text to store
        date: ISO date string (YYYY-MM-DD); defaults to today
    """
    effective_date = date or str(_date.today())
    key = f"project:{project_id}:octowiz:adr:{effective_date}-{slug}"
    url = f"{base_url.rstrip('/')}/v1/memory/{quote(key, safe='')}"
    response = httpx.put(
        url,
        json={"content": content},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    response.raise_for_status()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest packages/memory_client/tests/test_adr.py -v
```

Expected: `3 passed`

---

### Task 14: Implement packages/memory_client/namespace.py (TDD)

**Files:**
- Create: `packages/memory_client/tests/test_namespace.py`
- Create: `packages/memory_client/namespace.py`

- [ ] **Step 1: Write failing tests**

```python
# packages/memory_client/tests/test_namespace.py
"""Tests for namespace/project-rules loader."""
import unittest
from unittest.mock import MagicMock, patch
import json


class TestLoadProjectRules(unittest.TestCase):

    def test_fetches_correct_memory_key(self):
        """load_project_rules fetches project:{id}:octowiz:rules."""
        with patch("packages.memory_client.namespace.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"content": json.dumps({"rule": "no force push"})}
            mock_httpx.get.return_value = mock_response

            from packages.memory_client.namespace import load_project_rules
            result = load_project_rules(
                base_url="http://localhost:4000",
                api_key="sk-test",
                project_id="proj-abc",
            )

            call_args = mock_httpx.get.call_args
            url = call_args[0][0]
            self.assertIn("project:proj-abc:octowiz:rules", url)

    def test_returns_parsed_dict_on_200(self):
        """load_project_rules returns parsed dict on success."""
        with patch("packages.memory_client.namespace.httpx") as mock_httpx:
            rules = {"no_force_push": True, "require_review": True}
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"content": json.dumps(rules)}
            mock_httpx.get.return_value = mock_response

            from packages.memory_client.namespace import load_project_rules
            result = load_project_rules("http://localhost:4000", "sk-test", "proj-abc")

            self.assertEqual(result, rules)

    def test_raises_on_http_error(self):
        """load_project_rules propagates HTTP errors."""
        import httpx
        with patch("packages.memory_client.namespace.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock()
            )
            mock_httpx.get.return_value = mock_response
            mock_httpx.HTTPStatusError = httpx.HTTPStatusError

            from packages.memory_client.namespace import load_project_rules
            with self.assertRaises(httpx.HTTPStatusError):
                load_project_rules("http://localhost:4000", "sk-test", "proj-x")


class TestLoadRoleBundle(unittest.TestCase):

    def test_fetches_correct_role_key(self):
        """load_role_bundle fetches team:{namespace}:octowiz:roles:{role}."""
        with patch("packages.memory_client.namespace.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"content": json.dumps({"role": "implementer"})}
            mock_httpx.get.return_value = mock_response

            from packages.memory_client.namespace import load_role_bundle
            load_role_bundle(
                base_url="http://localhost:4000",
                api_key="sk-test",
                role="implementer",
                namespace="allspark",
            )

            url = mock_httpx.get.call_args[0][0]
            self.assertIn("team:allspark:octowiz:roles:implementer", url)

    def test_returns_parsed_dict_on_200(self):
        """load_role_bundle returns parsed dict from content field."""
        with patch("packages.memory_client.namespace.httpx") as mock_httpx:
            bundle = {"tdd": True, "deep_modules": True}
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"content": json.dumps(bundle)}
            mock_httpx.get.return_value = mock_response

            from packages.memory_client.namespace import load_role_bundle
            result = load_role_bundle("http://localhost:4000", "sk-test", "planner", "allspark")

            self.assertEqual(result, bundle)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest packages/memory_client/tests/test_namespace.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'packages.memory_client.namespace'`

- [ ] **Step 3: Implement packages/memory_client/namespace.py**

```python
# packages/memory_client/namespace.py
"""Namespace and project-rules loader — fetches doctrine bundles from LiteLLM Memory."""
from __future__ import annotations

import json
from urllib.parse import quote

import httpx


def load_project_rules(base_url: str, api_key: str, project_id: str) -> dict:
    """Fetch project rules from LiteLLM Memory: project:{id}:octowiz:rules.

    Returns the parsed dict stored in the memory entry's 'content' field.
    Raises httpx.HTTPStatusError on 4xx/5xx.
    """
    key = f"project:{project_id}:octowiz:rules"
    return _fetch(base_url, api_key, key)


def load_role_bundle(base_url: str, api_key: str, role: str, namespace: str) -> dict:
    """Fetch a role bundle: team:{namespace}:octowiz:roles:{role}.

    Returns the parsed dict stored in the memory entry's 'content' field.
    Raises httpx.HTTPStatusError on 4xx/5xx.
    """
    key = f"team:{namespace}:octowiz:roles:{role}"
    return _fetch(base_url, api_key, key)


def _fetch(base_url: str, api_key: str, key: str) -> dict:
    url = f"{base_url.rstrip('/')}/v1/memory/{quote(key, safe='')}"
    response = httpx.get(url, headers={"Authorization": f"Bearer {api_key}"})
    response.raise_for_status()
    data = response.json()
    content = data.get("content", "{}")
    if isinstance(content, str):
        return json.loads(content)
    return content
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest packages/memory_client/tests/test_namespace.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
python -m pytest packages/ providers/ -q --tb=short
```

Expected: all previously passing tests still pass, plus 8 new tests (3 adr + 5 namespace).

---

### Task 15: Commit PR2

- [ ] **Step 1: Stage and commit**

```bash
git add packages/memory_client/adr.py packages/memory_client/namespace.py \
        packages/memory_client/tests/test_adr.py packages/memory_client/tests/test_namespace.py
git commit -m "$(cat <<'EOF'
feat: add ADR writer and namespace loader to packages/memory_client

Completes Milestone 3: write_adr() persists Architecture Decision Records
to LiteLLM Memory under project:{id}:octowiz:adr:{date}-{slug}.
load_project_rules() and load_role_bundle() consolidate the inline
octowiz-cache get calls scattered across skills into importable functions.
8 new tests, all green on 3.8/3.11/3.12.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## PR3 — Agent View Provider + Marketplace Manifest

**Branch:** `feat/pr3-agent-view-provider`

Checkout from PR2 branch (or from main after PR2 merges).

---

### Task 16: Implement AgentSession dataclass and parser (TDD)

**Files:**
- Create: `providers/claude_agent_view/session.py`
- Create: `providers/claude_agent_view/parser.py`
- Create: `providers/claude_agent_view/tests/test_parser.py`

- [ ] **Step 1: Write failing parser tests with fixture JSON**

```python
# providers/claude_agent_view/tests/test_parser.py
"""Tests for AgentSession parser — isolates CLI output schema from the rest of Octowiz."""
import unittest
import json

FIXTURE_RUNNING = json.dumps([
    {
        "id": "bg-abc123",
        "status": "running",
        "branch": "feat/my-feature",
        "repoRoot": "/Users/dev/myrepo",
        "needsInput": False,
        "createdAt": "2026-05-30T08:00:00Z",
    }
])

FIXTURE_NEEDS_INPUT = json.dumps([
    {
        "id": "bg-def456",
        "status": "waiting_for_input",
        "branch": "main",
        "repoRoot": "/Users/dev/myrepo",
        "needsInput": True,
        "createdAt": "2026-05-30T09:00:00Z",
    }
])

FIXTURE_EMPTY = json.dumps([])
FIXTURE_MALFORMED = "this is not json {"
FIXTURE_WRONG_TYPE = json.dumps({"not": "a list"})


class TestParseSessions(unittest.TestCase):

    def test_parses_running_session(self):
        from providers.claude_agent_view.parser import parse_sessions
        sessions = parse_sessions(FIXTURE_RUNNING)
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s.id, "bg-abc123")
        self.assertEqual(s.status, "running")
        self.assertEqual(s.branch, "feat/my-feature")
        self.assertFalse(s.needs_input)
        self.assertFalse(s.ready_for_review)

    def test_parses_needs_input_session(self):
        from providers.claude_agent_view.parser import parse_sessions
        sessions = parse_sessions(FIXTURE_NEEDS_INPUT)
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s.id, "bg-def456")
        self.assertEqual(s.status, "waiting")
        self.assertTrue(s.needs_input)

    def test_returns_empty_list_for_empty_array(self):
        from providers.claude_agent_view.parser import parse_sessions
        self.assertEqual(parse_sessions(FIXTURE_EMPTY), [])

    def test_returns_empty_list_on_malformed_json(self):
        from providers.claude_agent_view.parser import parse_sessions
        self.assertEqual(parse_sessions(FIXTURE_MALFORMED), [])

    def test_returns_empty_list_when_output_is_not_a_list(self):
        from providers.claude_agent_view.parser import parse_sessions
        self.assertEqual(parse_sessions(FIXTURE_WRONG_TYPE), [])

    def test_never_raises_on_unknown_status_value(self):
        fixture = json.dumps([{"id": "x", "status": "some_future_status", "branch": None,
                               "repoRoot": None, "needsInput": False, "createdAt": None}])
        from providers.claude_agent_view.parser import parse_sessions
        sessions = parse_sessions(fixture)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].status, "some_future_status")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest providers/claude_agent_view/tests/test_parser.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'providers.claude_agent_view.parser'`

- [ ] **Step 3: Implement session.py**

```python
# providers/claude_agent_view/session.py
"""AgentSession dataclass — normalised view of a Claude Code background session."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentSession:
    id: str
    status: str               # running | stopped | waiting | error | <unknown>
    branch: Optional[str]
    repo: Optional[str]
    needs_input: bool
    ready_for_review: bool
    created_at: Optional[str]
```

- [ ] **Step 4: Implement parser.py**

```python
# providers/claude_agent_view/parser.py
"""Parses `claude agents --json` output into AgentSession objects.

All schema knowledge is isolated here — schema changes only require edits to
this file, not to the rest of the provider.
"""
from __future__ import annotations

import json
from typing import List

from .session import AgentSession

_STATUS_MAP = {
    "running": "running",
    "stopped": "stopped",
    "waiting_for_input": "waiting",
    "error": "error",
    "exited": "stopped",
}


def parse_sessions(json_output: str) -> List[AgentSession]:
    """Parse `claude agents --json` output into a list of AgentSession.

    Returns an empty list on any parse error — CLI output is untrusted.
    Never raises.
    """
    try:
        data = json.loads(json_output)
        if not isinstance(data, list):
            return []
        return [_parse_one(item) for item in data if isinstance(item, dict)]
    except Exception:
        return []


def _parse_one(item: dict) -> AgentSession:
    raw_status = item.get("status", "")
    status = _STATUS_MAP.get(raw_status, raw_status)
    needs_input = bool(item.get("needsInput", False))
    ready_for_review = status == "stopped" and not needs_input
    return AgentSession(
        id=str(item.get("id", "")),
        status=status,
        branch=item.get("branch") or None,
        repo=item.get("repoRoot") or None,
        needs_input=needs_input,
        ready_for_review=ready_for_review,
        created_at=item.get("createdAt") or None,
    )
```

- [ ] **Step 5: Run parser tests to verify they pass**

```bash
python -m pytest providers/claude_agent_view/tests/test_parser.py -v
```

Expected: `6 passed`

---

### Task 17: Implement ClaudeAgentViewProvider (TDD)

**Files:**
- Create: `providers/claude_agent_view/provider.py`
- Create: `providers/claude_agent_view/tests/test_provider.py`

- [ ] **Step 1: Write failing provider tests**

```python
# providers/claude_agent_view/tests/test_provider.py
"""Tests for ClaudeAgentViewProvider — mocks _run_claude at the subprocess seam."""
import json
import unittest
from unittest.mock import patch, MagicMock


FIXTURE_SESSIONS = json.dumps([
    {"id": "bg-abc", "status": "running", "branch": "main",
     "repoRoot": "/repo", "needsInput": False, "createdAt": "2026-05-30T08:00:00Z"}
])


class TestListSessions(unittest.TestCase):

    def test_returns_sessions_from_cli(self):
        with patch("providers.claude_agent_view.provider._run_claude") as mock_run:
            mock_run.return_value = FIXTURE_SESSIONS
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            provider = ClaudeAgentViewProvider()
            sessions = provider.list_sessions()
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].id, "bg-abc")
            mock_run.assert_called_once_with(["agents", "--json"])

    def test_returns_empty_list_when_cli_absent(self):
        with patch("providers.claude_agent_view.provider._run_claude") as mock_run:
            mock_run.return_value = ""
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            provider = ClaudeAgentViewProvider()
            sessions = provider.list_sessions()
            self.assertEqual(sessions, [])

    def test_returns_empty_list_when_cli_errors(self):
        with patch("providers.claude_agent_view.provider._run_claude") as mock_run:
            mock_run.side_effect = FileNotFoundError("claude not found")
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            provider = ClaudeAgentViewProvider()
            sessions = provider.list_sessions()
            self.assertEqual(sessions, [])


class TestGetLogs(unittest.TestCase):

    def test_get_logs_calls_claude_logs(self):
        with patch("providers.claude_agent_view.provider._run_claude") as mock_run:
            mock_run.return_value = "log output here"
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            provider = ClaudeAgentViewProvider()
            logs = provider.get_logs("bg-abc")
            self.assertEqual(logs, "log output here")
            mock_run.assert_called_once_with(["logs", "bg-abc"])


class TestStop(unittest.TestCase):

    def test_stop_calls_claude_stop(self):
        with patch("providers.claude_agent_view.provider._run_claude") as mock_run:
            mock_run.return_value = ""
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            provider = ClaudeAgentViewProvider()
            provider.stop("bg-abc")
            mock_run.assert_called_once_with(["stop", "bg-abc"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest providers/claude_agent_view/tests/test_provider.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'providers.claude_agent_view.provider'`

- [ ] **Step 3: Implement provider.py**

```python
# providers/claude_agent_view/provider.py
"""ClaudeAgentViewProvider — wraps `claude agents` CLI as an execution provider."""
from __future__ import annotations

import subprocess
from typing import List, Optional

from .parser import parse_sessions
from .session import AgentSession


def _run_claude(args: List[str]) -> str:
    """Run `claude <args>` and return stdout. Raises FileNotFoundError if claude absent."""
    result = subprocess.run(
        ["claude"] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


class ClaudeAgentViewProvider:
    """Execution provider backed by Claude Code Agent View (claude agents CLI)."""

    def list_sessions(self) -> List[AgentSession]:
        """Return all current agent sessions. Returns [] if claude CLI is absent."""
        try:
            output = _run_claude(["agents", "--json"])
            return parse_sessions(output)
        except Exception:
            return []

    def dispatch(self, task: str, repo: str) -> str:
        """Start a new background session for task in repo. Returns the session id."""
        output = _run_claude(["--bg", "--cwd", repo, task])
        # claude --bg prints the session id on the first line
        return output.splitlines()[0].strip() if output else ""

    def get_status(self, run_id: str) -> Optional[AgentSession]:
        """Return the session for run_id, or None if not found."""
        sessions = self.list_sessions()
        for s in sessions:
            if s.id == run_id:
                return s
        return None

    def get_logs(self, run_id: str) -> str:
        """Return stdout log for run_id."""
        return _run_claude(["logs", run_id])

    def stop(self, run_id: str) -> None:
        """Stop the session with run_id."""
        _run_claude(["stop", run_id])
```

- [ ] **Step 4: Run provider tests to verify they pass**

```bash
python -m pytest providers/claude_agent_view/tests/test_provider.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Run full provider test suite**

```bash
python -m pytest providers/ -v --tb=short
```

Expected: `11 passed` (6 parser + 5 provider)

---

### Task 18: Update .claude-plugin/plugin.json marketplace manifest

**Files:**
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Update plugin.json with full manifest**

Replace the contents with:

```json
{
  "name": "octowiz",
  "description": "Octowiz Engineering Agent — Claude Code adapter, A2A bridge, and execution coordinator.",
  "version": "0.1.0",
  "author": {
    "name": "IntegraHub",
    "email": "support@integrahub.de"
  },
  "homepage": "https://github.com/raelli/octowiz",
  "repository": "https://github.com/raelli/octowiz",
  "license": "MIT",
  "keywords": [
    "claude-code",
    "mattpocock",
    "superpowers",
    "integrahub",
    "memory",
    "workflow",
    "a2a",
    "agent-view"
  ],
  "skills": [
    "./skills/octowiz-workflow",
    "./skills/octowiz-setup"
  ],
  "hooks": ["./hooks/hooks.json"],
  "providers": ["./providers/claude_agent_view"],
  "dependencies": {
    "plugins": ["superpowers", "mattpocock-skills"],
    "python": ">=3.8"
  }
}
```

- [ ] **Step 2: Verify valid JSON**

```bash
python3 -c "import json; d=json.load(open('.claude-plugin/plugin.json')); print('version:', d['version'], '— valid')"
```

Expected: `version: 0.1.0 — valid`

---

### Task 19: Final verification and commit PR3

- [ ] **Step 1: Run complete test suite**

```bash
python -m pytest packages/ providers/ -q --tb=short
```

Expected: all tests pass. Count should be baseline (195) + 8 (PR2) + 11 (PR3) = **214 passed** minimum.

- [ ] **Step 2: Run a2a tests**

```bash
python -m pytest apps/a2a-agent/tests/ --rootdir=apps/a2a-agent -q --tb=short
```

Expected: `15 passed`

- [ ] **Step 3: Verify list_sessions returns [] when claude CLI absent**

```bash
python -c "
from unittest.mock import patch
with patch('providers.claude_agent_view.provider._run_claude', side_effect=FileNotFoundError()):
    from providers.claude_agent_view.provider import ClaudeAgentViewProvider
    p = ClaudeAgentViewProvider()
    assert p.list_sessions() == [], 'Should return empty list'
    print('list_sessions resilience: PASS')
"
```

Expected: `list_sessions resilience: PASS`

- [ ] **Step 4: Commit PR3**

```bash
git add providers/ .claude-plugin/plugin.json
git commit -m "$(cat <<'EOF'
feat: add Claude Agent View provider and complete marketplace manifest

Completes Milestone 6a: ClaudeAgentViewProvider wraps claude agents CLI
behind an AgentSession dataclass. parser.py isolates CLI schema changes.
list_sessions() returns [] when claude CLI absent (never errors). Updated
plugin.json with hooks, providers, and dependency declarations.
11 new tests. Plugin version 0.1.0 final.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```
