"""ClaudeCliAdapter — single seam for all `claude` CLI invocations."""
import json
import re
import subprocess
from dataclasses import dataclass
from typing import Callable, Dict, List, Literal, Optional, Tuple, Union

Runner = Callable[[List[str], Optional[str]], Tuple[int, str, str]]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_SESSION_RE = re.compile(r"backgrounded\s*[·•]\s*(\S+)")


@dataclass
class SessionStarted:
    session_id: str


@dataclass
class SessionInfo:
    session_id: str
    name: str
    status: str
    cwd: str
    pid: Optional[int]
    started_at: Optional[int]


@dataclass
class CliError:
    kind: Literal["timeout", "nonzero_exit", "parse_failure"]
    message: str


def _default_runner(args: List[str], cwd: Optional[str] = None, *, timeout: float) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "operation timed out"
    except OSError as exc:
        return 1, "", str(exc)


class ClaudeCliAdapter:
    _START_TIMEOUT: float = 10.0
    _AGENTS_TIMEOUT: float = 30.0

    def __init__(self, runner: Optional[Runner] = None):
        self._injected_runner = runner

    def _run(self, args: List[str], timeout: float, *, cwd: Optional[str] = None) -> Tuple[int, str, str]:
        if self._injected_runner is not None:
            return self._injected_runner(args, cwd)
        return _default_runner(args, cwd, timeout=timeout)

    def start_session(
        self, task: str, cwd: str, name: Optional[str] = None
    ) -> Union[SessionStarted, CliError]:
        args = ["claude", "--bg"]
        if name:
            args += ["--name", str(name)]
        args += ["--", task]

        rc, stdout, stderr = self._run(args, self._START_TIMEOUT, cwd=cwd)
        if rc != 0:
            return CliError(kind="nonzero_exit", message=stderr or f"claude --bg exited {rc}")

        clean = _ANSI_RE.sub("", stdout)
        m = _SESSION_RE.search(clean)
        if not m:
            return CliError(kind="parse_failure", message="could not parse session id from output")

        return SessionStarted(session_id=m.group(1))

    def list_sessions(
        self, cwd: Optional[str] = None
    ) -> Union[List[SessionInfo], CliError]:
        args = ["claude", "agents", "--json"]
        if cwd:
            args += ["--cwd", cwd]

        rc, stdout, stderr = self._run(args, self._AGENTS_TIMEOUT)
        if rc != 0:
            return CliError(kind="nonzero_exit", message=stderr or f"claude agents exited {rc}")

        try:
            raw: List[Dict] = json.loads(stdout or "[]")
        except Exception:
            return CliError(kind="parse_failure", message="could not parse agents JSON output")

        return [
            SessionInfo(
                session_id=s.get("sessionId", ""),
                name=s.get("name", ""),
                status=s.get("status", ""),
                cwd=s.get("cwd", ""),
                pid=s.get("pid"),
                started_at=s.get("startedAt"),
            )
            for s in raw
        ]

    def control(self, op: str, session_id: str) -> Union[str, CliError]:
        rc, stdout, stderr = self._run(["claude", op, "--", session_id], self._AGENTS_TIMEOUT)
        if rc != 0:
            return CliError(kind="nonzero_exit", message=stderr or f"claude {op} exited {rc}")
        return stdout
