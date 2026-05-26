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
REQUIRED_PLUGINS = ["superpowers", "mattpo-skills", "antfu-skills"]


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


# ---------------------------------------------------------------------------
# State file I/O
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_machine_state(path: Path = MACHINE_STATE_PATH) -> Optional[MachineState]:
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return MachineState(
        first_seen=data.get("first_seen", ""),
        plugins=data.get("plugins", {}),
        litellm=data.get("litellm", {
            "routing_verified_at": None,
            "planner_verified_at": None,
            "implementer_verified_at": None,
            "reviewer_verified_at": None,
        }),
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
    data = json.loads(state_path.read_text())
    return RepoState(
        created_at=data.get("created_at", ""),
        mattpocock_setup=data.get("mattpocock_setup", False),
        antfu_relevant=data.get("antfu_relevant"),
        antfu_setup=data.get("antfu_setup", False),
        antfu_deferred=data.get("antfu_deferred", False),
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
