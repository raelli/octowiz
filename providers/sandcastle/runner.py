"""Sandcastle container execution — subprocess seams for testing."""
from __future__ import annotations

import re
import subprocess
from typing import List, Optional

VALID_CONTAINER_PROVIDERS: frozenset[str] = frozenset({"docker", "podman"})

# Permits alphanumeric start, then letters/digits/dots/underscores/hyphens/forward-slashes.
_BRANCH_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_./-]{0,127}$')


def build_container_cmd(
    container_provider: str,
    container_name: str,
    image: str,
    cwd: str,
    task: str,
    branch: Optional[str] = None,
) -> List[str]:
    """Build the container run command. Pure function — no side effects."""
    if container_provider not in VALID_CONTAINER_PROVIDERS:
        raise ValueError(f"unsupported container_provider: {container_provider!r}")
    if task.startswith("-"):
        raise ValueError(f"task must not start with '-': {task!r}")
    if branch is not None:
        if branch.startswith("-"):
            raise ValueError(f"branch must not start with '-': {branch!r}")
        if not _BRANCH_RE.fullmatch(branch):
            raise ValueError(f"invalid branch name: {branch!r}")

    cmd: List[str] = [
        container_provider, "run",
        "--rm",
        f"--name={container_name}",
        f"--volume={cwd}:{cwd}:rw",
        "--workdir", cwd,
    ]

    if branch:
        # Positional-param form: branch → $1, task → $2. No shell interpolation.
        cmd += [
            image,
            "sh", "-c",
            'git checkout -- "$1" && claude --print -- "$2"',
            "--", branch, task,
        ]
    else:
        cmd += [image, "claude", "--print", "--", task]

    return cmd


def _start_container(cmd: List[str], log_path: str) -> subprocess.Popen:
    """Launch container process, writing stdout+stderr to log_path. Mock seam."""
    log_fh = open(log_path, "w")
    return subprocess.Popen(cmd, stdout=log_fh, stderr=subprocess.STDOUT, close_fds=True)


def _run_cmd(cmd: List[str]) -> int:
    """Run a blocking command (e.g. docker kill). Returns returncode. Mock seam."""
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    return result.returncode
