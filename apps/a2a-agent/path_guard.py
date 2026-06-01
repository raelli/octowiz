"""Shared path validation — enforces OCTOWIZ_ALLOWED_ROOTS when set.

Extracted from capabilities/manage_agents.py so that both manage_agents and
dispatch can call the same guard without code duplication.
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
