"""Shared path validation — enforces OCTOWIZ_ALLOWED_ROOTS when set.

Extracted from capabilities/manage_agents.py so that both manage_agents and
dispatch can call the same guard without code duplication.

SECONDARY DEFENCE-IN-DEPTH CHECK
---------------------------------
src/policy.js (Node.js daemon) is the canonical enforcement point for
OCTOWIZ_ALLOWED_ROOTS.  The daemon calls policy.validateCwd() before any task
payload is forwarded here, so a bad cwd should never reach this code in normal
operation.

This validator exists as a second line of defence in case the Python capabilities
are invoked outside the daemon, or the daemon guard is bypassed.

These two validators MUST stay in sync.  If OCTOWIZ_ALLOWED_ROOTS logic changes
in policy.js, update this file as well.

Known divergences vs. policy.js (2026-06-04):
  1. Root paths are NOT resolved via os.path.realpath() before comparison; only
     cwd is canonicalized.  Symlinked roots that policy.js would resolve correctly
     may not be matched here.
  2. An empty / unset OCTOWIZ_ALLOWED_ROOTS is treated as "allow all" in this
     file, whereas policy.js (checkStartup) treats it as a fatal startup error.
"""
import os


def validate_cwd(cwd: str) -> str:
    """Canonicalize cwd and enforce OCTOWIZ_ALLOWED_ROOTS when set.

    Returns the canonicalized absolute path on success.
    Raises ValueError when cwd is relative or outside the allowed roots.
    """
    if not os.path.isabs(cwd):
        raise ValueError(f"cwd must be an absolute path: {cwd!r}")
    canonical = os.path.realpath(cwd)
    allowed_roots_env = os.environ.get("OCTOWIZ_ALLOWED_ROOTS", "")
    if allowed_roots_env:
        roots = [r.strip() for r in allowed_roots_env.split(":") if r.strip()]
        if not any(canonical == r or canonical.startswith(r + os.sep) for r in roots):
            raise ValueError(f"cwd {canonical!r} is not within an allowed root")
    return canonical
