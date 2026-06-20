"""Shared path validation — enforces OCTOWIZ_ALLOWED_ROOTS.

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
"""
import os


def validate_cwd(cwd: str) -> str:
    """Canonicalize cwd and enforce OCTOWIZ_ALLOWED_ROOTS.

    Returns the canonicalized absolute path on success.
    Raises ValueError when cwd is relative, when OCTOWIZ_ALLOWED_ROOTS is
    unset/empty (deny-all, matching policy.js checkStartup behaviour), or when
    cwd is outside every allowed root.
    """
    if not os.path.isabs(cwd):
        raise ValueError(f"cwd must be an absolute path: {cwd!r}")
    canonical = os.path.realpath(cwd)
    allowed_roots_env = os.environ.get("OCTOWIZ_ALLOWED_ROOTS", "")
    # Match policy.js: empty/unset allowlist is deny-all, not allow-all.
    # Split on the OS-native separator (os.pathsep == ':' on POSIX, ';' on
    # Windows) to stay in sync with policy.js parseRoots(), which uses
    # path.delimiter. A hardcoded ':' would mis-split Windows drive-letter
    # paths the daemon already accepted.
    roots = [r.strip() for r in allowed_roots_env.split(os.pathsep) if r.strip()]
    if not roots:
        raise ValueError(
            "OCTOWIZ_ALLOWED_ROOTS is not set — all paths denied. "
            "Set it to an os.pathsep-separated list of allowed absolute paths."
        )
    # Resolve each root to canonicalize symlinks, matching policy.js fs.realpathSync().
    resolved_roots = []
    for r in roots:
        try:
            resolved_roots.append(os.path.realpath(r))
        except OSError:
            pass  # skip roots that don't exist on this machine
    if not any(canonical == r or canonical.startswith(r + os.sep) for r in resolved_roots):
        raise ValueError(f"cwd {canonical!r} is not within an allowed root")
    return canonical
