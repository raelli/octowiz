"""ClaudeCliAdapter — single seam for all `claude` CLI invocations."""
import re
import subprocess
from dataclasses import dataclass
from typing import Callable, List, Literal, Optional, Tuple, Union

Runner = Callable[[List[str]], Tuple[int, str, str]]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_SESSION_RE = re.compile(r"backgrounded\s*[·•]\s*(\S+)")


@dataclass
class SessionStarted:
    session_id: str


@dataclass
class CliError:
    kind: Literal["timeout", "nonzero_exit", "parse_failure"]
    message: str


def _default_runner(args: List[str], *, timeout: float) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "operation timed out"
    except OSError as exc:
        return 1, "", str(exc)


class ClaudeCliAdapter:
    _START_TIMEOUT: float = 10.0

    def __init__(self, runner: Optional[Runner] = None):
        self._runner = runner if runner is not None else (
            lambda args: _default_runner(args, timeout=self._START_TIMEOUT)
        )

    def start_session(
        self, task: str, cwd: str, name: Optional[str] = None
    ) -> Union[SessionStarted, CliError]:
        args = ["claude", "--bg", "--cwd", cwd]
        if name:
            args += ["--name", str(name)]
        args += ["--", task]

        rc, stdout, stderr = self._runner(args)
        if rc != 0:
            return CliError(kind="nonzero_exit", message=stderr or f"claude --bg exited {rc}")

        clean = _ANSI_RE.sub("", stdout)
        m = _SESSION_RE.search(clean)
        if not m:
            return CliError(kind="parse_failure", message="could not parse session id from output")

        return SessionStarted(session_id=m.group(1))
