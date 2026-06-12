"""
octowiz_env.py — environment detection, state-file I/O, and repo scan for first-run setup.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

MACHINE_STATE_DIR = Path.home() / ".octowiz"
MACHINE_STATE_PATH = MACHINE_STATE_DIR / "machine-state.json"
OCTOWIZ_DIR = ".octowiz"
SETUP_STATE_FILENAME = "setup-state.json"
ONBOARDING_FILENAME = "ONBOARDING.md"
PLUGINS_CACHE_BASE = Path.home() / ".claude" / "plugins" / "cache"
REQUIRED_PLUGINS = ["superpowers", "mattpocock-skills", "antfu-skills"]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class MachineState:
    first_seen: str = ""
    plugins: Dict[str, str] = field(default_factory=dict)
    litellm: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "routing_verified_at": None,
        "planner_verified_at": None,
        "implementer_verified_at": None,
        "reviewer_verified_at": None,
    })
    dismissed_checks: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class RepoState:
    created_at: str = ""
    mattpocock_setup: bool = False
    antfu_relevant: Optional[bool] = None
    antfu_setup: bool = False
    antfu_deferred: bool = False
    project_id: Optional[str] = None


# ---------------------------------------------------------------------------
# State file I/O
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_machine_state(path: Path = MACHINE_STATE_PATH) -> Optional[MachineState]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return MachineState(
        first_seen=data.get("first_seen", ""),
        plugins=data.get("plugins", {}),
        litellm=data.get("litellm") or {
            "routing_verified_at": None,
            "planner_verified_at": None,
            "implementer_verified_at": None,
            "reviewer_verified_at": None,
        },
        dismissed_checks=data.get("dismissed_checks", {}),
    )


def save_machine_state(state: MachineState, path: Path = MACHINE_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2))


def init_machine_state(path: Path = MACHINE_STATE_PATH) -> MachineState:
    """Return existing state if present; otherwise create and save a skeleton."""
    existing = load_machine_state(path)
    if existing is not None:
        return existing
    state = MachineState(first_seen=_now_iso())
    save_machine_state(state, path)
    return state


def load_repo_state(cwd: Path) -> Optional[RepoState]:
    state_path = cwd / OCTOWIZ_DIR / SETUP_STATE_FILENAME
    if not state_path.exists():
        return None
    try:
        data = json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return RepoState(
        created_at=data.get("created_at", ""),
        mattpocock_setup=data.get("mattpocock_setup", False),
        antfu_relevant=data.get("antfu_relevant"),
        antfu_setup=data.get("antfu_setup", False),
        antfu_deferred=data.get("antfu_deferred", False),
        project_id=data.get("project_id"),
    )


def save_repo_state(state: RepoState, cwd: Path) -> None:
    state_path = cwd / OCTOWIZ_DIR / SETUP_STATE_FILENAME
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(asdict(state), indent=2))


def init_repo_state(cwd: Path) -> RepoState:
    """Return existing repo state if present; otherwise create skeleton."""
    existing = load_repo_state(cwd)
    if existing is not None:
        return existing
    state = RepoState(created_at=_now_iso())
    save_repo_state(state, cwd)
    return state


# ---------------------------------------------------------------------------
# Plugin detection
# ---------------------------------------------------------------------------


def detect_plugin(plugin_id: str, plugins_base: Path = PLUGINS_CACHE_BASE) -> bool:
    """Return True if any marketplace subdirectory contains <plugin_id>/."""
    if not plugins_base.exists():
        return False
    return any(m.exists() for m in plugins_base.glob(f"*/{plugin_id}"))


def detect_all_plugins(
    plugin_ids: List[str] = REQUIRED_PLUGINS,
    plugins_base: Path = PLUGINS_CACHE_BASE,
) -> Dict[str, bool]:
    return {pid: detect_plugin(pid, plugins_base) for pid in plugin_ids}


# ---------------------------------------------------------------------------
# Repo scan
# ---------------------------------------------------------------------------


@dataclass
class RepoScan:
    agent_file: Optional[str]   # "AGENTS.md" | "CLAUDE.md" | "GEMINI.md" | None
    agent_has_skills_section: bool
    stack: str  # "ts_vue" | "react" | "generic_js" | "python" | "polyglot" | "empty"
    has_context_md: bool
    has_adr: bool
    has_github_remote: bool


def _detect_agent_file(cwd: Path) -> Optional[str]:
    for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        if (cwd / name).exists():
            return name
    return None


def _has_skills_section(cwd: Path, agent_file: str) -> bool:
    try:
        content = (cwd / agent_file).read_text(errors="replace")
        return "## Agent skills" in content
    except OSError:
        return False


def _detect_stack(cwd: Path) -> str:
    has_package_json = (cwd / "package.json").exists()
    has_pyproject = (cwd / "pyproject.toml").exists() or (cwd / "setup.py").exists()

    if has_package_json and has_pyproject:
        return "polyglot"
    if has_pyproject:
        return "python"
    if has_package_json:
        try:
            pkg = json.loads((cwd / "package.json").read_text())
        except Exception:
            return "generic_js"
        deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
        keys = set(deps.keys())
        if keys & {"vue", "vite"}:
            return "ts_vue"
        if "react" in keys:
            return "react"
        return "generic_js"
    return "empty"


def _has_github_remote(cwd: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "remote", "-v"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "github.com" in result.stdout
    except Exception:
        return False


def scan_repo(cwd: Path) -> RepoScan:
    agent_file = _detect_agent_file(cwd)
    agent_has_skills = _has_skills_section(cwd, agent_file) if agent_file else False
    return RepoScan(
        agent_file=agent_file,
        agent_has_skills_section=agent_has_skills,
        stack=_detect_stack(cwd),
        has_context_md=(cwd / "CONTEXT.md").exists(),
        has_adr=(cwd / "docs" / "adr").is_dir(),
        has_github_remote=_has_github_remote(cwd),
    )


# ---------------------------------------------------------------------------
# Live environment check
# ---------------------------------------------------------------------------

CACHE_TTL_HOURS = 24


@dataclass
class CheckResult:
    hard_gaps: List[str]      # failing hard-gate check IDs (after dismissals filtered out)
    advisory_gaps: List[str]  # failing advisory check IDs (after dismissals filtered out)
    machine_state_absent: bool   # True if machine-state.json did not exist before this call
    repo_state_absent: bool      # True if setup-state.json did not exist before this call


def _litellm_env_ok() -> bool:
    """Return True if LITELLM_BASE_URL and at least one API key env var are set."""
    has_base_url = bool(os.environ.get("LITELLM_BASE_URL"))
    has_key = bool(os.environ.get("LITELLM_ADMIN_API_KEY") or os.environ.get("LITELLM_API_KEY"))
    return has_base_url and has_key


def _litellm_cache_ok(machine_state: Optional[MachineState]) -> bool:
    """Return True if routing_verified_at exists and is within CACHE_TTL_HOURS."""
    if machine_state is None:
        return False
    litellm = machine_state.litellm
    if not isinstance(litellm, dict):
        return False
    routing_ts = litellm.get("routing_verified_at")
    if not routing_ts or not isinstance(routing_ts, str):
        return False
    try:
        verified_at = datetime.fromisoformat(routing_ts.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - verified_at
        return age.total_seconds() < CACHE_TTL_HOURS * 3600
    except (ValueError, TypeError):
        return False


def _antfu_gap(scan: RepoScan, repo_state: Optional[RepoState]) -> bool:
    """Return True if antfu setup is needed but not done.

    antfu is only a hard gate for ts_vue and polyglot stacks.
    antfu_deferred means "no agent file existed at setup time" — re-flag on every
    invocation so setup-repo can retry once an agent file is present.
    """
    if scan.stack not in {"ts_vue", "polyglot"}:
        return False
    if repo_state is None:
        return True  # no state file yet → antfu not set up
    return not repo_state.antfu_setup


def _repo_key(cwd: Path) -> str:
    """Return the canonical key for dismissed_checks — the git repo root, or cwd.resolve() as fallback."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return str(cwd.resolve())


def _get_dismissed_checks(cwd: Path, machine_state: Optional[MachineState]) -> List[str]:
    """Return the list of dismissed check IDs for the current repo root."""
    if machine_state is None:
        return []
    return list(machine_state.dismissed_checks.get(_repo_key(cwd), []))


def run_live_check(
    cwd: Path,
    machine_state_path: Path = MACHINE_STATE_PATH,
    plugins_base: Path = PLUGINS_CACHE_BASE,
) -> CheckResult:
    machine_state = load_machine_state(machine_state_path)
    repo_state = load_repo_state(cwd)
    machine_state_absent = machine_state is None
    repo_state_absent = repo_state is None

    dismissed = _get_dismissed_checks(cwd, machine_state)
    hard_gaps: List[str] = []
    advisory_gaps: List[str] = []

    # Check 1: plugins (hard gate)
    plugin_results = detect_all_plugins(REQUIRED_PLUGINS, plugins_base)
    for plugin_id, present in plugin_results.items():
        if not present:
            check_id = f"plugin_{plugin_id}"
            if check_id not in dismissed:
                hard_gaps.append(check_id)

    # Check 2: litellm env vars (hard gate)
    if not _litellm_env_ok():
        if "litellm_env" not in dismissed:
            hard_gaps.append("litellm_env")

    # Check 3: litellm cache TTL (hard gate)
    if not _litellm_cache_ok(machine_state):
        if "litellm_cache" not in dismissed:
            hard_gaps.append("litellm_cache")

    # Checks 4–6 need repo scan
    scan = scan_repo(cwd)

    # Check 4: agent file (advisory)
    if scan.agent_file is None:
        if "agent_file" not in dismissed:
            advisory_gaps.append("agent_file")

    # Check 5: mattpo skills setup (advisory) — only if agent file exists
    if scan.agent_file is not None and not scan.agent_has_skills_section:
        if "mattpo_skills_setup" not in dismissed:
            advisory_gaps.append("mattpo_skills_setup")

    # Check 6: antfu (hard gate) — state file as truth
    if _antfu_gap(scan, repo_state):
        if "antfu" not in dismissed:
            hard_gaps.append("antfu")

    return CheckResult(
        hard_gaps=hard_gaps,
        advisory_gaps=advisory_gaps,
        machine_state_absent=machine_state_absent,
        repo_state_absent=repo_state_absent,
    )


def seed_project_namespace(project_id: str, client: "httpx.Client") -> None:
    """Write default config and rules keys for a project namespace into LiteLLM Memory.

    Uses merge/upsert: reads existing keys first, writes only absent or empty fields.
    Raises RuntimeError on connection failure.
    """
    import json as _json
    import urllib.parse

    namespace = f"project:{project_id}:octowiz"
    config_key = f"{namespace}:config"
    rules_key = f"{namespace}:rules"

    def _exists(key: str) -> bool:
        resp = client.get(f"/v1/memory/{urllib.parse.quote(key, safe='')}")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    def _read_value(key: str) -> Optional[str]:
        resp = client.get(f"/v1/memory/{urllib.parse.quote(key, safe='')}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        return data.get("value") or data.get("memory")

    def _put(key: str, value: str) -> None:
        resp = client.put(
            f"/v1/memory/{urllib.parse.quote(key, safe='')}",
            json={"value": value, "metadata": {}},
        )
        resp.raise_for_status()

    if not _exists(config_key):
        _put(config_key, _json.dumps({"namespace": namespace, "created_at": _now_iso()}))

    existing_rules = _read_value(rules_key)
    if existing_rules is None:
        _put(rules_key, _json.dumps([]))


def derive_project_id(cwd: Path) -> str:
    """Return a stable project slug derived from the git remote URL, or a UUID fallback."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            url = result.stdout.strip().rstrip("/")
            # Strip .git suffix
            if url.endswith(".git"):
                url = url[:-4]
            # Handle SSH: git@github.com:org/repo → org/repo
            if ":" in url and not url.startswith("http"):
                url = url.split(":", 1)[1]
            # Take last two path segments: org/repo
            parts = url.replace("\\", "/").split("/")
            parts = [p for p in parts if p]
            slug = "-".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
            return slug.lower()
    except Exception:
        pass
    import uuid
    return uuid.uuid4().hex


def dismiss_check(
    check_id: str,
    cwd: Path,
    machine_state_path: Path = MACHINE_STATE_PATH,
) -> None:
    """Record a dismissed check for the current repo root in machine-state.json."""
    state = load_machine_state(machine_state_path)
    if state is None:
        state = MachineState(first_seen=_now_iso())
    repo_root = _repo_key(cwd)
    existing = list(state.dismissed_checks.get(repo_root, []))
    if check_id not in existing:
        existing.append(check_id)
    state.dismissed_checks[repo_root] = existing
    save_machine_state(state, machine_state_path)
